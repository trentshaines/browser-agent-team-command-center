"""Shared helpers: Bedrock calls, LLM judges, step summarisation, enums, and constants."""

import base64
import json
import os
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

from browser_use_sdk.types.task_step_view import TaskStepView

from event_queue import EventType


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 2
MAX_RECOVERY_ATTEMPTS = 2
MAX_GOAL_CHECKS = 5
JUDGE_EVERY_N_STEPS = 3


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentState(Enum):
	PENDING = "pending"
	RUNNING = "running"
	PAUSED = "paused"
	COMPLETE = "complete"
	ERROR = "error"


class LogAction(Enum):
	THINKING = "thinking"
	NAVIGATION = "navigation"
	OUTPUT = "output"
	RETRY = "retry"
	JUDGE = "judge"
	CORRECTION = "correction"
	HANDOFF = "handoff"
	PAUSED = "paused"
	RESUMED = "resumed"
	ERROR = "error"


LOG_ACTION_TO_EVENT: dict[str, EventType] = {
	"thinking": EventType.THINKING,
	"navigation": EventType.NAVIGATION,
	"output": EventType.OUTPUT,
	"retry": EventType.RETRY,
	"judge": EventType.JUDGE,
	"correction": EventType.CORRECTION,
	"handoff": EventType.HANDOFF,
	"paused": EventType.PAUSED,
	"resumed": EventType.RESUMED,
	"error": EventType.AGENT_ERROR,
}


# ---------------------------------------------------------------------------
# Bedrock helpers
# ---------------------------------------------------------------------------

def _bedrock_request(body: dict) -> str:
	"""Send a request to Bedrock and return the text response."""
	token = os.environ["AWS_BEARER_TOKEN_BEDROCK"]
	region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
	model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
	url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke"
	resp = httpx.post(url, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=60)
	resp.raise_for_status()
	return resp.json()["content"][0]["text"]


def _bedrock_call(system_prompt: str, user_message: str, max_tokens: int = 1024) -> str:
	return _bedrock_request({
		"anthropic_version": "bedrock-2023-05-31",
		"max_tokens": max_tokens,
		"system": system_prompt,
		"messages": [{"role": "user", "content": user_message}],
	})


def _bedrock_call_haiku(system_prompt: str, user_message: str, max_tokens: int = 512) -> str:
	"""Fast/cheap Haiku call for message rewriting."""
	token = os.environ["AWS_BEARER_TOKEN_BEDROCK"]
	region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
	model_id = "us.anthropic.claude-haiku-3-5-20241022-v1:0"
	url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke"
	body = {
		"anthropic_version": "bedrock-2023-05-31",
		"max_tokens": max_tokens,
		"system": system_prompt,
		"messages": [{"role": "user", "content": user_message}],
	}
	resp = httpx.post(url, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=30)
	resp.raise_for_status()
	return resp.json()["content"][0]["text"]


def _bedrock_vision_call(image_url: str, prompt: str, max_tokens: int = 1024) -> str:
	img_resp = httpx.get(image_url, timeout=30, follow_redirects=True)
	img_resp.raise_for_status()
	media_type = img_resp.headers.get("content-type", "image/png").split(";")[0].strip()
	if media_type not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
		media_type = "image/png"
	return _bedrock_request({
		"anthropic_version": "bedrock-2023-05-31",
		"max_tokens": max_tokens,
		"messages": [{
			"role": "user",
			"content": [
				{"type": "image", "source": {
					"type": "base64", "media_type": media_type,
					"data": base64.b64encode(img_resp.content).decode(),
				}},
				{"type": "text", "text": prompt},
			],
		}],
	})


# ---------------------------------------------------------------------------
# Step summarisation
# ---------------------------------------------------------------------------

def summarize_steps(
	steps: list[TaskStepView],
	include_eval: bool = False,
	max_actions: int | None = None,
) -> str:
	"""Build a newline-separated summary from a list of steps."""
	lines = []
	for s in steps:
		parts = []
		if include_eval and s.evaluation_previous_goal:
			parts.append(f"eval: {s.evaluation_previous_goal}")
		if s.next_goal:
			parts.append(f"goal: {s.next_goal}" if include_eval else s.next_goal)
		if s.url:
			parts.append(f"url: {s.url}")
		if s.actions:
			actions = s.actions[:max_actions] if max_actions else s.actions
			parts.append(f"actions: {', '.join(actions)}")
		lines.append(f"Step {s.number}: {' | '.join(parts)}")
	return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM judge / goal-check functions
# ---------------------------------------------------------------------------

def check_goal(goal: str, output: str, steps: list[TaskStepView] | None = None) -> tuple[str, str]:
	"""Hard-check whether the goal has been fully achieved.

	Returns (verdict, detail):
		("COMPLETE", "")           — goal fully achieved.
		("AGENT", "<instruction>") — agent can keep going.
		("HUMAN", "<reason>")      — needs human intervention.
	"""
	step_context = ""
	if steps:
		step_context = "\n\nRECENT STEPS:\n" + summarize_steps(steps[-5:], max_actions=3)

	text = _bedrock_call(
		system_prompt=(
			"You are strictly evaluating whether a web-browsing agent fully completed its goal.\n\n"
			"Be rigorous. The goal must be FULLY and VERIFIABLY achieved — not partially done, "
			"not 'likely done', not 'the page was reached'. If the goal was to apply for a job, "
			"the application must have been submitted. If the goal was to purchase something, "
			"the order must be confirmed.\n\n"
			"Respond with exactly ONE of these three formats:\n\n"
			"1. COMPLETE — the goal is fully, verifiably achieved.\n\n"
			"2. AGENT: <instruction> — the goal is NOT complete, but the agent can continue "
			"autonomously. Write a specific follow-up instruction after the colon.\n\n"
			"3. HUMAN: <reason> — the goal is NOT complete and requires human intervention "
			"(e.g. filling credentials, solving captcha, entering payment info, uploading files, "
			"providing personal details the agent doesn't have). Write the reason after the colon."
		),
		user_message=f"GOAL: {goal}\n\nAGENT OUTPUT: {output}{step_context}",
		max_tokens=512,
	).strip()

	for prefix, key in [("COMPLETE", "COMPLETE"), ("HUMAN:", "HUMAN"), ("AGENT:", "AGENT")]:
		if text.startswith(prefix):
			return (key, text[len(prefix):].strip() if prefix.endswith(":") else "")
	return ("AGENT", text)


def judge_step(goal: str, steps: list[TaskStepView]) -> str | None:
	"""Judge whether the agent is on track. Returns None if on track, else a correction."""
	text = _bedrock_call(
		system_prompt=(
			"You are a judge monitoring a web-browsing agent that is trying to accomplish a goal.\n\n"
			"Given the original goal and the agent's recent steps, respond with exactly ONE of:\n\n"
			"1. ON_TRACK — the agent is making progress toward the goal.\n\n"
			"2. NEEDS_HUMAN: <reason> — the agent is stuck on something that requires a human to "
			"resolve in the browser (e.g. CAPTCHA, reCAPTCHA, login/password prompt, two-factor "
			"authentication, email verification, cookie consent that won't dismiss, age verification, "
			"or any interactive challenge it cannot handle). Include a brief reason after the colon.\n\n"
			"3. A correction instruction — if the agent is off track (navigating to irrelevant pages, "
			"stuck in a loop, doing something unrelated). Write the instruction directly, no preamble."
		),
		user_message=f"GOAL: {goal}\n\nRECENT STEPS:\n" + summarize_steps(steps, include_eval=True),
		max_tokens=256,
	).strip()
	return None if text.startswith("ON_TRACK") else text


def needs_handoff(goal: str, step: TaskStepView) -> str | None:
	"""Use vision to decide whether the current step requires human handoff."""
	if not step.screenshot_url:
		return None
	result = _bedrock_vision_call(step.screenshot_url, (
		"You are given the image of a webpage. An automated agent is working toward a goal "
		"but may be stuck.\n\n"
		"Determine if human intervention is needed. Intervention is likely needed when:\n"
		" - A CAPTCHA or reCAPTCHA is visible\n"
		" - A login/authentication form requiring credentials the agent doesn't have\n"
		" - A payment/checkout form requiring card details\n"
		" - A form asking for personal information (address, phone, etc.)\n"
		" - An age/identity verification gate\n"
		" - A two-factor authentication or email verification prompt\n\n"
		"If NO intervention is needed, respond with exactly: none\n\n"
		"If intervention IS needed, respond with a short, clear instruction addressed to the "
		"human telling them exactly what to do on the page. Do NOT include any preamble."
	)).strip()
	return None if result.lower().startswith("none") else result


def build_recovery_prompt(goal: str, steps: list[TaskStepView], error: str) -> str:
	"""Build a context-aware recovery prompt from a failed agent's history."""
	return _bedrock_call(
		system_prompt=(
			"A web-browsing agent was trying to accomplish a goal but failed. "
			"Given the original goal, what the agent did before failing, and the error, "
			"write a new instruction for a fresh browser agent to accomplish the same goal.\n\n"
			"The new agent will start in a fresh browser session. If the previous agent made "
			"progress, incorporate that context so the new agent can pick up efficiently "
			"(e.g. 'Go to <url> and continue from where the previous attempt left off').\n\n"
			"If the previous attempt hit a dead end, suggest an alternative approach.\n\n"
			"Write the instruction directly, no preamble."
		),
		user_message=(
			f"GOAL: {goal}\n\nPREVIOUS STEPS:\n"
			+ summarize_steps(steps[-10:], max_actions=3)
			+ f"\n\nERROR: {error}"
		),
		max_tokens=512,
	)


# ---------------------------------------------------------------------------
# File store (Convex-backed)
# ---------------------------------------------------------------------------

CONVEX_URL = os.environ.get("CONVEX_URL", "http://127.0.0.1:3210")

# Extensions we can read as text
_TEXT_EXTENSIONS = {
	".txt", ".md", ".csv", ".json", ".xml", ".html", ".yml", ".yaml",
	".toml", ".ini", ".cfg", ".log", ".py", ".js", ".ts", ".sh",
}

resp = httpx.post(
			f"{CONVEX_URL}/api/query",
			json={"path": "files:list", "args": {}},
			timeout=10,
		)
print(f"CONVEX_URL: {CONVEX_URL}")
print(resp)


def _fetch_convex_files() -> list[dict] | None:
	"""Query the Convex files:list function for all uploaded files."""
	try:
		resp = httpx.post(
			f"{CONVEX_URL}/api/query",
			json={"path": "files:list", "args": {}},
			timeout=10,
		)
		resp.raise_for_status()
		data = resp.json()
		# Convex HTTP API wraps the result in a { "value": ... } or returns it directly
		if isinstance(data, dict) and "value" in data:
			return data["value"]
		if isinstance(data, list):
			return data
		return None
	except Exception:
		return None


def _download_file(url: str) -> bytes | None:
	"""Download file bytes from a Convex storage URL."""
	try:
		resp = httpx.get(url, timeout=30, follow_redirects=True)
		resp.raise_for_status()
		return resp.content
	except Exception:
		return None


def _read_file_content_from_bytes(raw: bytes, name: str, mime_type: str) -> str | None:
	"""Read file content from raw bytes. Uses vision for PDFs/images."""
	suffix = Path(name).suffix.lower()

	if suffix in _TEXT_EXTENSIONS or mime_type.startswith("text/"):
		try:
			return raw.decode("utf-8", errors="replace")
		except Exception:
			return None

	if suffix == ".pdf" or mime_type == "application/pdf":
		return _extract_pdf_bytes(raw)

	if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp") or mime_type.startswith("image/"):
		media_map = {".png": "image/png", ".jpg": "image/jpeg",
		             ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
		media = media_map.get(suffix, mime_type if mime_type.startswith("image/") else "image/png")
		return _extract_image_bytes(raw, media)

	return None


def _extract_pdf_bytes(raw: bytes) -> str | None:
	"""Extract text from PDF bytes using Bedrock vision."""
	try:
		return _bedrock_request({
			"anthropic_version": "bedrock-2023-05-31",
			"max_tokens": 4096,
			"messages": [{
				"role": "user",
				"content": [
					{"type": "document", "source": {
						"type": "base64", "media_type": "application/pdf",
						"data": base64.b64encode(raw).decode(),
					}},
					{"type": "text", "text": (
						"Extract ALL text content from this PDF. "
						"Return the full text, preserving structure. No commentary."
					)},
				],
			}],
		})
	except Exception:
		return None


def _extract_image_bytes(raw: bytes, media_type: str) -> str | None:
	"""Describe an image using Bedrock vision."""
	try:
		return _bedrock_request({
			"anthropic_version": "bedrock-2023-05-31",
			"max_tokens": 2048,
			"messages": [{
				"role": "user",
				"content": [
					{"type": "image", "source": {
						"type": "base64", "media_type": media_type,
						"data": base64.b64encode(raw).decode(),
					}},
					{"type": "text", "text": (
						"Describe all text and information visible in this image. "
						"Be thorough. No commentary."
					)},
				],
			}],
		})
	except Exception:
		return None


def check_file_store(handoff_reason: str) -> str | None:
	"""Check if Convex file store contains files that can resolve a handoff.

	Returns a context string with relevant file contents if found, None otherwise.
	"""
	files = _fetch_convex_files()
	print(f"Files: {files}")
	if not files:
		return None

	# Build inventory from Convex file records
	inventory = "\n".join(
		f"- {f['name']} ({Path(f['name']).suffix}, {f['size']} bytes)"
		for f in files
	)

	# Ask LLM which files are relevant
	verdict = _bedrock_call(
		system_prompt=(
			"A browser agent needs human intervention. You must decide if any files "
			"in the user's file store can provide the information needed instead.\n\n"
			"Respond with EXACTLY one of:\n"
			"- RELEVANT: filename1, filename2 — if specific files can help\n"
			"- NONE — if no files are relevant\n\n"
			"Examples of matches:\n"
			"- 'Please upload your resume' + 'resume.pdf' → RELEVANT: resume.pdf\n"
			"- 'Enter your address' + 'personal_info.txt' → RELEVANT: personal_info.txt\n"
			"- 'Solve the CAPTCHA' + 'resume.pdf' → NONE (no file helps with a captcha)\n"
			"- 'Enter payment details' + 'CV.pdf' → NONE (wrong file type for the need)"
		),
		user_message=f"HANDOFF REASON: {handoff_reason}\n\nAVAILABLE FILES:\n{inventory}",
		max_tokens=256,
	).strip()

	if not verdict.startswith("RELEVANT:"):
		return None

	# Parse relevant filenames
	relevant_names = {n.strip() for n in verdict[len("RELEVANT:"):].split(",")}
	file_map = {f["name"]: f for f in files}

	# Download and read contents of matching files
	parts = []
	for name in relevant_names:
		file_rec = file_map.get(name)
		if not file_rec or not file_rec.get("url"):
			continue
		raw = _download_file(file_rec["url"])
		if not raw:
			continue
		content = _read_file_content_from_bytes(raw, name, file_rec.get("type", ""))
		if content:
			parts.append(f"=== {name} ===\n{content}")

	if not parts:
		return None

	return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Task decomposition & summarisation
# ---------------------------------------------------------------------------

def task_refiner(prompt: str) -> list[str]:
	"""Decompose a user goal into independent, parallelisable browser-agent tasks."""
	text = _bedrock_call(
		system_prompt=(
			"You are a task planner for a system that dispatches multiple BROWSER AGENTS "
			"in parallel. Each agent gets its own full browser and acts autonomously.\n\n"
			"Given a user's goal, decide whether it should be handled by one agent or split "
			"across multiple agents.\n\n"
			"CRITICAL RULES:\n"
			"- Only split into multiple agents when the goal contains genuinely independent "
			"actions that can happen simultaneously in separate browsers.\n"
			"- A single end-to-end workflow (e.g. 'apply to a job', 'book a flight', "
			"'buy a product') is ALWAYS one agent, even if it involves many steps.\n"
			"- Research/gathering that feeds into a single action is NOT a reason to split. "
			"The one agent doing the action can research as part of its workflow.\n"
			"- Only split when the user asks for multiple distinct things that don't depend "
			"on each other. Examples:\n"
			"  - 'Book a hotel in Paris AND find flights from NYC' → 2 agents\n"
			"  - 'Apply to jobs at Google, Meta, and Amazon' → 3 agents\n"
			"  - 'Find reviews for product X on Amazon, Best Buy, and Reddit' → 3 agents\n"
			"  - 'Apply to a software engineering job at Decagon' → 1 agent\n"
			"  - 'Research Decagon and apply for a job there' → 1 agent (sequential)\n"
			"  - 'Get the weather in NYC' → 1 agent\n\n"
			"- Maximum 5 agents.\n"
			"- When in doubt, use fewer agents. One agent doing everything is better than "
			"multiple agents doing fragments.\n\n"
			"Return your response as a JSON array of strings (task descriptions).\n"
			"Return ONLY the JSON array, nothing else."
		),
		user_message=prompt,
	)
	try:
		tasks = json.loads(text)
	except json.JSONDecodeError:
		return [prompt]
	if not isinstance(tasks, list) or not tasks:
		return [prompt]
	return [str(t) for t in tasks[:5]]


def summarize_results(original_goal: str, agents: list[Any]) -> str:
	"""Synthesize all agent outputs into a single cohesive summary.

	Accepts any objects with .state, .result, .prompt, and .error attributes.
	"""
	sections = []
	for i, agent in enumerate(agents, 1):
		status = "COMPLETED" if agent.state == AgentState.COMPLETE else "FAILED"
		output = (agent.result.output or "No output") if agent.result else (agent.error or "No output")
		sections.append(f"AGENT {i} ({status})\nTask: {agent.prompt}\nOutput: {output}")

	return _bedrock_call(
		system_prompt=(
			"You are a research assistant summarizing the results from multiple web-browsing agents "
			"that were dispatched to accomplish parts of a user's goal.\n\n"
			"Synthesize their outputs into a single, cohesive, well-organized summary that directly "
			"addresses the user's original goal. Combine overlapping information, resolve contradictions, "
			"highlight key findings, and note any gaps where agents failed or produced no results.\n\n"
			"Write in a clear, informative style. Use markdown formatting."
		),
		user_message=f"ORIGINAL GOAL: {original_goal}\n\n" + "\n\n".join(sections),
		max_tokens=2048,
	)
