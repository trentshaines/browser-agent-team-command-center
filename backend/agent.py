"""Orchestrator that manages concurrent browser-use cloud agents.

Usage:
	orch = Orchestrator()
	orch.add_prompt("Find reviews on quincy")
	orch.add_prompt("Get the weather in NYC")
	results = await orch.run()

	# Or add prompts while running:
	async def main():
		orch = Orchestrator()
		orch.add_prompt("task 1")
		run_task = asyncio.create_task(orch.run())
		await asyncio.sleep(2)
		orch.add_prompt("task 2")  # added mid-flight
		results = await run_task
"""

import asyncio
import base64
import json
import os
from enum import Enum
from typing import Any, AsyncIterator, Callable, Coroutine

import httpx
from pydantic import BaseModel

# Type alias for the event callback: async fn(event_type: str, data: dict) -> None
EventCallback = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]

from dotenv import load_dotenv
load_dotenv()

from browser_use_sdk import AsyncBrowserUse
from browser_use_sdk.types.task_step_view import TaskStepView
from browser_use_sdk.types.task_view import TaskView


client = AsyncBrowserUse(api_key=os.environ["BROWSER_USE_API_KEY"])


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


class BrowserAgentLog(BaseModel):
	agent_id: str
	prompt: str
	step: int | None = None
	action: str
	content: str
	url: str | None = None
	actions: list[str] = []
	handoff_url: str | None = None


# Global log sink — the backend can read this at any time
agent_logs: list[BrowserAgentLog] = []
LOG_PATH = "agent_logs.json"


def _flush_logs() -> None:
	"""Write all logs to disk. Called on every new log entry."""
	with open(LOG_PATH, "w") as f:
		json.dump([log.model_dump() for log in agent_logs], f, indent=2)


MAX_RETRIES = 2
MAX_RECOVERY_ATTEMPTS = 2
MAX_GOAL_CHECKS = 5


def _check_goal(goal: str, output: str, steps: list[TaskStepView] | None = None) -> tuple[str, str]:
	"""Hard-check whether the goal has been fully achieved.

	Returns a tuple of (verdict, detail):
		("COMPLETE", "")           — goal fully achieved, stop.
		("AGENT", "<instruction>") — agent can keep going, use this instruction.
		("HUMAN", "<reason>")      — needs human in the browser to proceed.
	"""
	step_context = ""
	if steps:
		last_steps = steps[-5:]
		summaries = []
		for s in last_steps:
			parts = []
			if s.next_goal:
				parts.append(s.next_goal)
			if s.url:
				parts.append(f"url: {s.url}")
			if s.actions:
				parts.append(f"actions: {', '.join(s.actions[:3])}")
			summaries.append(f"Step {s.number}: {' | '.join(parts)}")
		step_context = "\n\nRECENT STEPS:\n" + "\n".join(summaries)

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

	if text.startswith("COMPLETE"):
		return ("COMPLETE", "")
	if text.startswith("HUMAN:"):
		return ("HUMAN", text[len("HUMAN:"):].strip())
	if text.startswith("AGENT:"):
		return ("AGENT", text[len("AGENT:"):].strip())
	# Fallback: treat unstructured response as an agent instruction
	return ("AGENT", text)


JUDGE_EVERY_N_STEPS = 3


def _judge_step(goal: str, steps: list[TaskStepView]) -> str | None:
	"""Judge whether the agent is on track after recent steps.

	Returns:
		None — agent is on track, keep going.
		"NEEDS_HUMAN: <reason>" — stuck on something requiring human intervention.
		"<correction>" — off track, use this as a correction prompt.
	"""
	step_summaries = []
	for s in steps:
		parts = []
		if s.evaluation_previous_goal:
			parts.append(f"eval: {s.evaluation_previous_goal}")
		if s.next_goal:
			parts.append(f"goal: {s.next_goal}")
		if s.url:
			parts.append(f"url: {s.url}")
		if s.actions:
			parts.append(f"actions: {', '.join(s.actions)}")
		step_summaries.append(f"Step {s.number}: {' | '.join(parts)}")

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
		user_message=f"GOAL: {goal}\n\nRECENT STEPS:\n" + "\n".join(step_summaries),
		max_tokens=256,
	).strip()
	if text.startswith("ON_TRACK"):
		return None
	return text


def _needs_handoff(goal: str, step: TaskStepView) -> str | None:
	"""Use an LLM judge to decide whether the current step requires human handoff.

	Returns a human-facing instruction string if handoff is needed, None otherwise.
	"""
	if not step.screenshot_url:
		return None

	PROMPT = """You are given the image of a webpage. An automated agent is working toward a goal but may be stuck.

Determine if human intervention is needed. Intervention is likely needed when:
 - A CAPTCHA or reCAPTCHA is visible
 - A login/authentication form requiring credentials the agent doesn't have
 - A payment/checkout form requiring card details
 - A form asking for personal information (address, phone, etc.)
 - An age/identity verification gate
 - A two-factor authentication or email verification prompt

If NO intervention is needed, respond with exactly: none

If intervention IS needed, respond with a short, clear instruction addressed to the human telling them exactly what to do on the page. Examples:
 - "Please solve the CAPTCHA displayed on the page."
 - "Please log in with your credentials — the agent needs to be authenticated to proceed."
 - "Please fill in your payment details to complete the checkout."
 - "Please enter your shipping address in the form."

Do NOT include any preamble. Just 'none' or the instruction."""

	result = _bedrock_vision_call(step.screenshot_url, PROMPT).strip()

	if result.lower().startswith("none"):
		return None

	return result


def _build_recovery_prompt(goal: str, steps: list[TaskStepView], error: str) -> str:
	"""Build a context-aware recovery prompt from a failed agent's history."""
	step_summaries = []
	for s in steps[-10:]:  # last 10 steps for context
		parts = []
		if s.next_goal:
			parts.append(s.next_goal)
		if s.url:
			parts.append(f"url: {s.url}")
		if s.actions:
			parts.append(f"actions: {', '.join(s.actions[:3])}")
		step_summaries.append(f"Step {s.number}: {' | '.join(parts)}")

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
			f"GOAL: {goal}\n\n"
			f"PREVIOUS STEPS:\n" + "\n".join(step_summaries) + "\n\n"
			f"ERROR: {error}"
		),
		max_tokens=512,
	)


class BrowserAgent:
	"""Wraps a single browser-use cloud task."""

	def __init__(self, client: AsyncBrowserUse, prompt: str, on_event: EventCallback | None = None, name: str | None = None):
		self.client = client
		self.prompt = prompt
		self.on_event = on_event
		self.name = name
		self.state = AgentState.PENDING
		self.task_id: str | None = None
		self.session_id: str | None = None
		self.live_url: str | None = None
		self.share_url: str | None = None
		self.result: TaskView | None = None
		self.error: str | None = None
		self.steps: list[TaskStepView] = []
		self.last_url: str | None = None
		self._resume_event = asyncio.Event()

	def _log(self, action: LogAction, content: str, step: TaskStepView | None = None, handoff_url: str | None = None) -> None:
		entry = BrowserAgentLog(
			agent_id=self.task_id or "pending",
			prompt=self.prompt,
			step=step.number if step else None,
			action=action.value,
			content=content,
			url=step.url if step else None,
			actions=step.actions if step else [],
			handoff_url=handoff_url,
		)
		agent_logs.append(entry)
		_flush_logs()

		# Fire event callback
		if self.on_event:
			asyncio.ensure_future(self.on_event("agent_step", entry.model_dump()))

		# Track last real URL visited
		if step and step.url and step.url.startswith(("http://", "https://")):
			self.last_url = step.url

	async def _emit(self, event_type: str, data: dict[str, Any]) -> None:
		"""Emit an event via the callback if one is registered."""
		if self.on_event:
			await self.on_event(event_type, data)

	def _emit_frame(self, step: "TaskStepView") -> None:
		"""Fire-and-forget: download step screenshot and emit agent_frame."""
		if not step.screenshot_url or not self.on_event:
			return

		async def _download_and_emit():
			try:
				async with httpx.AsyncClient() as http:
					resp = await http.get(step.screenshot_url, timeout=15, follow_redirects=True)
					resp.raise_for_status()
				b64 = base64.b64encode(resp.content).decode()
				await self._emit("agent_frame", {
					"agent_id": self.task_id,
					"step": step.number,
					"url": step.url,
					"screenshot": b64,
				})
			except Exception:
				pass  # non-critical — don't block the step loop

		asyncio.ensure_future(_download_and_emit())

	async def start(self) -> AsyncIterator[TaskStepView]:
		"""Create a persistent session, then create a task on it and stream steps."""
		self.state = AgentState.RUNNING
		try:
			# Create a persistent session first
			session = await self.client.sessions.create_session(
				keep_alive=True,
				persist_memory=True,
			)
			self.session_id = session.id
			self.live_url = session.live_url

			try:
				share = await self.client.sessions.create_session_public_share(self.session_id)
				self.share_url = share.share_url
			except Exception:
				pass

			# Create and run the task on the session
			task = await self.client.tasks.create_task(
				task=self.prompt,
				session_id=self.session_id,
			)
			self.task_id = task.id
			await self._emit("agent_spawned", {
				"agent_id": self.task_id,
				"name": self.name,
				"task": self.prompt,
				"session_id": self.session_id,
				"live_url": self.live_url,
				"share_url": self.share_url,
			})

			async for step in task.stream():
				self.steps.append(step)

				# Log the thinking / evaluation
				if step.evaluation_previous_goal:
					self._log(LogAction.THINKING, step.evaluation_previous_goal, step)
				if step.next_goal:
					self._log(LogAction.THINKING, step.next_goal, step)

				# Log each navigation action
				for act in step.actions:
					self._log(LogAction.NAVIGATION, act, step)

				yield step
				self._emit_frame(step)

			# Fetch the final result once streaming ends
			self.result = await self.client.tasks.get_task(self.task_id)
			self.state = AgentState.COMPLETE

			# Log final output
			self._log(LogAction.OUTPUT, self.result.output or "No output")
			await self._emit("agent_status", {
				"agent_id": self.task_id,
				"status": "complete",
				"result": self.result.output,
			})
		except Exception as e:
			self.error = str(e)
			self.state = AgentState.ERROR
			self._log(LogAction.ERROR, str(e))
			await self._emit("agent_status", {
				"agent_id": self.task_id,
				"status": "error",
				"error": str(e),
			})
			raise

	async def retry(self, follow_up_prompt: str) -> AsyncIterator[TaskStepView]:
		"""Run a follow-up task on the same browser session to finish the goal."""
		self.state = AgentState.RUNNING
		self._log(LogAction.RETRY, follow_up_prompt)
		try:
			task = await self.client.tasks.create_task(
				task=follow_up_prompt,
				session_id=self.session_id,
			)
			self.task_id = task.id

			async for step in task.stream():
				self.steps.append(step)

				if step.evaluation_previous_goal:
					self._log(LogAction.THINKING, step.evaluation_previous_goal, step)
				if step.next_goal:
					self._log(LogAction.THINKING, step.next_goal, step)

				for act in step.actions:
					self._log(LogAction.NAVIGATION, act, step)

				yield step
				self._emit_frame(step)

			self.result = await self.client.tasks.get_task(self.task_id)
			self.state = AgentState.COMPLETE
			self._log(LogAction.OUTPUT, self.result.output or "No output")
			await self._emit("agent_status", {
				"agent_id": self.task_id,
				"status": "complete",
				"result": self.result.output,
			})
		except Exception as e:
			self.error = str(e)
			self.state = AgentState.ERROR
			self._log(LogAction.ERROR, str(e))
			await self._emit("agent_status", {
				"agent_id": self.task_id,
				"status": "error",
				"error": str(e),
			})
			raise

	async def handoff(self, reason: str = "") -> None:
		"""Stop the task for human intervention (keeps session alive)."""
		try:
			await self.client.tasks.update_task(self.task_id, action="stop")
		except Exception:
			pass  # task may already be stopped
		self.state = AgentState.PAUSED
		self._resume_event.clear()
		self._log(LogAction.PAUSED, reason or "Handed off to user")

	async def wait_for_human(self) -> None:
		"""Block until the human signals they are done."""
		await self._resume_event.wait()

	def signal_human_done(self) -> None:
		"""Called externally (CLI or endpoint) when the human is finished."""
		self._resume_event.set()

	async def continue_after_handoff(self, extra_context: str = "") -> AsyncIterator[TaskStepView]:
		"""Create a new task on the same session to continue after human handoff."""
		self.state = AgentState.RUNNING
		continuation = (
			f"The user just completed a manual step in the browser (the page may have changed). "
			f"Continue working toward the original goal: {self.prompt}"
		)
		if extra_context:
			continuation += f"\n\nAdditional context from the user: {extra_context}"
		self._log(LogAction.RESUMED, "Human done, continuing on same session")
		async for step in self.retry(continuation):
			yield step

	async def recover(self, recovery_prompt: str, start_url: str | None = None) -> AsyncIterator[TaskStepView]:
		"""Start a fresh session to recover from a failure."""
		self.state = AgentState.RUNNING
		self.error = None
		self.result = None
		self._log(LogAction.RETRY, f"Recovering with new session: {recovery_prompt}")
		try:
			# Create a new persistent session for recovery
			session_kwargs: dict = {"keep_alive": True, "persist_memory": True}
			if start_url:
				session_kwargs["start_url"] = start_url

			session = await self.client.sessions.create_session(**session_kwargs)
			self.session_id = session.id
			self.live_url = session.live_url

			try:
				share = await self.client.sessions.create_session_public_share(self.session_id)
				self.share_url = share.share_url
			except Exception:
				pass

			# Create and run the task on the new session
			task = await self.client.tasks.create_task(
				task=recovery_prompt,
				session_id=self.session_id,
			)
			self.task_id = task.id
			await self._emit("agent_spawned", {
				"agent_id": self.task_id,
				"name": self.name,
				"task": self.prompt,
				"live_url": self.live_url,
				"share_url": self.share_url,
			})

			async for step in task.stream():
				self.steps.append(step)

				if step.evaluation_previous_goal:
					self._log(LogAction.THINKING, step.evaluation_previous_goal, step)
				if step.next_goal:
					self._log(LogAction.THINKING, step.next_goal, step)
				for act in step.actions:
					self._log(LogAction.NAVIGATION, act, step)

				yield step
				self._emit_frame(step)

			self.result = await self.client.tasks.get_task(self.task_id)
			self.state = AgentState.COMPLETE
			self._log(LogAction.OUTPUT, self.result.output or "No output")
			await self._emit("agent_status", {
				"agent_id": self.task_id,
				"status": "complete",
				"result": self.result.output,
			})
		except Exception as e:
			self.error = str(e)
			self.state = AgentState.ERROR
			self._log(LogAction.ERROR, str(e))
			await self._emit("agent_status", {
				"agent_id": self.task_id,
				"status": "error",
				"error": str(e),
			})
			raise

	async def get_share_url(self) -> str:
		return self.live_url


class Orchestrator:
	"""Runs multiple BrowserAgents concurrently, supports adding new ones mid-flight."""

	def __init__(self, on_event: EventCallback | None = None):
		self._agents: list[BrowserAgent] = []
		self._pending: asyncio.Queue[BrowserAgent] = asyncio.Queue()
		self._running = False
		self.on_event = on_event

	# -- public API ----------------------------------------------------------

	def resume_agent(self, task_id: str) -> bool:
		"""Signal that the human is done with a handed-off agent. Returns True if found."""
		for agent in self._agents:
			if agent.task_id == task_id and agent.state == AgentState.PAUSED:
				agent.signal_human_done()
				return True
		return False

	def get_paused_agents(self) -> list[BrowserAgent]:
		"""Return all currently paused agents."""
		return [a for a in self._agents if a.state == AgentState.PAUSED]

	def add_prompt(self, prompt: str, name: str | None = None) -> BrowserAgent:
		"""Add a new browser agent. Safe to call before or during run()."""
		agent = BrowserAgent(client, prompt, on_event=self.on_event, name=name)
		self._agents.append(agent)
		if self._running:
			self._pending.put_nowait(agent)
		return agent

	async def run(self) -> list[BrowserAgent]:
		"""Start all agents and block until every one has finished.

		Returns the full list of agents with their results.
		"""
		self._running = True
		tasks: set[asyncio.Task] = set()

		def _launch(agent: BrowserAgent) -> None:
			t = asyncio.create_task(
				self._run_agent(agent),
				name=f"agent-{agent.prompt[:40]}",
			)
			tasks.add(t)
			t.add_done_callback(tasks.discard)

		# Launch everything already queued
		for agent in self._agents:
			if agent.state == AgentState.PENDING:
				_launch(agent)

		# Keep going until all tasks done and nothing pending
		while tasks or not self._pending.empty():
			# Pick up dynamically-added agents
			while not self._pending.empty():
				try:
					_launch(self._pending.get_nowait())
				except asyncio.QueueEmpty:
					break

			if not tasks:
				await asyncio.sleep(0.1)
				continue

			# Wait for at least one task to finish (or timeout to re-check queue)
			await asyncio.wait(tasks, timeout=0.5, return_when=asyncio.FIRST_COMPLETED)

		self._running = False

		# Emit done event with all agent results
		if self.on_event:
			await self.on_event("done", {
				"agents": [
					{
						"agent_id": a.task_id,
						"status": a.state.value,
						"result": (a.result.output if a.result else None),
					}
					for a in self._agents
				]
			})

		return self._agents

	# -- internal ------------------------------------------------------------

	async def _run_agent(self, agent: BrowserAgent) -> None:
		"""Drain all steps from an agent, judge mid-flight, recover on failure."""
		label = agent.prompt[:50]
		correction = await self._run_and_judge(agent, label)

		# If the judge stopped the task, run the correction on the same session
		for _ in range(MAX_RETRIES):
			if correction is None:
				break
			print(f"[{label}] Judge correcting: {correction}")
			agent._log(LogAction.CORRECTION, correction)
			try:
				correction = await self._run_and_judge(agent, label, follow_up=correction)
			except Exception as e:
				print(f"[{label}] CORRECTION ERROR: {e}")
				break

		# If agent failed, try to recover with a new session
		if agent.state == AgentState.ERROR:
			await self._attempt_recovery(agent, label)
			return

		# Goal-check loop: keep going until the goal is verifiably complete
		for attempt in range(MAX_GOAL_CHECKS):
			if agent.state != AgentState.COMPLETE or not agent.result:
				break

			output = agent.result.output or ""
			verdict, detail = _check_goal(agent.prompt, output, agent.steps)

			if verdict == "COMPLETE":
				print(f"[{label}] Goal complete.")
				return

			if verdict == "HUMAN":
				# Needs human intervention — handoff, wait, then continue
				handoff_url = await agent.get_share_url()
				print(f"\n[{label}] GOAL CHECK: Needs human — {detail}")
				print(f"[{label}] >>> Complete it here: {handoff_url}")
				print(f"[{label}] >>> Then type: resume {agent.task_id}\n")
				agent._log(LogAction.HANDOFF, detail, handoff_url=handoff_url)
				await agent._emit("handoff", {
					"agent_id": agent.task_id,
					"message": detail,
					"handoff_url": handoff_url,
					"source": "goal_check",
				})
				await agent.handoff(detail)
				await agent.wait_for_human()
				await agent._emit("human_input_received", {"agent_id": agent.task_id})
				print(f"[{label}] Human done, continuing...")
				try:
					correction = await self._run_and_judge(
						agent, label, stream=agent.continue_after_handoff()
					)
					# Handle any judge corrections after handoff
					for _ in range(MAX_RETRIES):
						if correction is None:
							break
						correction = await self._run_and_judge(agent, label, follow_up=correction)
				except Exception as e:
					print(f"[{label}] POST-HANDOFF ERROR: {e}")
					break
			else:
				# verdict == "AGENT" — agent can keep going
				print(f"[{label}] Goal incomplete (attempt {attempt + 1}/{MAX_GOAL_CHECKS}): {detail[:120]}")
				try:
					correction = await self._run_and_judge(agent, label, follow_up=detail)
					for _ in range(MAX_RETRIES):
						if correction is None:
							break
						agent._log(LogAction.CORRECTION, correction)
						correction = await self._run_and_judge(agent, label, follow_up=correction)
				except Exception as e:
					print(f"[{label}] RETRY ERROR: {e}")
					break

		# If still not complete after all checks, attempt recovery
		if agent.state in (AgentState.ERROR, AgentState.RUNNING):
			await self._attempt_recovery(agent, label)

	async def _attempt_recovery(self, agent: BrowserAgent, label: str) -> None:
		"""Try to recover a failed agent with a new session."""
		for attempt in range(MAX_RECOVERY_ATTEMPTS):
			error_msg = agent.error or "Unknown error"
			print(f"[{label}] Recovery attempt {attempt + 1}/{MAX_RECOVERY_ATTEMPTS}...")

			last_url = agent.last_url

			# Build a smart recovery prompt using LLM
			recovery_prompt = _build_recovery_prompt(agent.prompt, agent.steps, error_msg)
			print(f"[{label}] Recovery plan: {recovery_prompt[:120]}...")
			if last_url:
				print(f"[{label}] Starting from: {last_url}")

			try:
				await agent._emit("recovery_started", {
					"agent_id": agent.task_id or "pending",
					"attempt": attempt + 1,
					"recovery_prompt": recovery_prompt,
					"start_url": last_url,
				})
				recovery_stream = agent.recover(recovery_prompt, start_url=last_url)
				correction = await self._run_and_judge(agent, label, stream=recovery_stream)

				# Handle corrections from the judge during recovery
				for _ in range(MAX_RETRIES):
					if correction is None:
						break
					print(f"[{label}] Judge correcting during recovery: {correction}")
					agent._log(LogAction.CORRECTION, correction)
					correction = await self._run_and_judge(agent, label, follow_up=correction)
			except Exception as e:
				print(f"[{label}] RECOVERY ERROR: {e}")
				continue

			if agent.state == AgentState.COMPLETE:
				await agent._emit("recovery_completed", {"agent_id": agent.task_id})
				print(f"[{label}] Recovered successfully.")
				return

		print(f"[{label}] All recovery attempts exhausted.")

	async def _run_and_judge(
		self,
		agent: "BrowserAgent",
		label: str,
		follow_up: str | None = None,
		stream: AsyncIterator[TaskStepView] | None = None,
	) -> str | None:
		"""Run an agent (or a follow-up), judging every N steps.

		Returns None if the task finished normally, or a correction prompt if the
		judge stopped the task for being off track.
		"""
		printed_urls = False
		if stream is None:
			stream = agent.retry(follow_up) if follow_up else agent.start()

		async def _drain(step_stream: AsyncIterator[TaskStepView]) -> str | None:
			nonlocal printed_urls
			async for step in step_stream:
				if not printed_urls:
					printed_urls = True
					if agent.live_url:
						print(f"[{label}] Live view:  {agent.live_url}")
					if agent.share_url:
						print(f"[{label}] Share link: {agent.share_url}")
				print(
					f"[{label}] step {step.number}: {step.next_goal}"
					+ (f"  url={step.url}" if step.url else "")
				)
				await agent._emit("step", {
					"agent_id": agent.task_id,
					"step": step.number,
					"goal": step.next_goal,
					"url": step.url,
					"actions": step.actions,
				})

				# Check every step for forms / captchas / checkouts
				handoff_reason = _needs_handoff(agent.prompt, step)
				if handoff_reason:
					handoff_url = await agent.get_share_url()
					agent._log(LogAction.HANDOFF, handoff_reason, step, handoff_url=handoff_url)
					await agent._emit("handoff", {
						"agent_id": agent.task_id,
						"message": handoff_reason,
						"handoff_url": handoff_url,
						"source": "vision",
					})
					print(f"\n[{label}] HANDOFF — {handoff_reason}")
					print(f"[{label}] >>> Complete it here: {handoff_url}")
					print(f"[{label}] >>> Then type: resume {agent.task_id}\n")
					await agent.handoff(handoff_reason)
					return "__HANDOFF__"

				# Judge every N steps using the last N steps as context
				if step.number > 0 and step.number % JUDGE_EVERY_N_STEPS == 0:
					recent = agent.steps[-JUDGE_EVERY_N_STEPS:]
					verdict = _judge_step(agent.prompt, recent)
					if verdict is not None:
						if verdict.startswith("NEEDS_HUMAN:"):
							reason = verdict[len("NEEDS_HUMAN:"):].strip()
							handoff_url = await agent.get_share_url()
							agent._log(LogAction.HANDOFF, reason, step, handoff_url=handoff_url)
							await agent._emit("handoff", {
								"agent_id": agent.task_id,
								"message": reason,
								"handoff_url": handoff_url,
								"source": "judge",
							})
							print(f"\n[{label}] HANDOFF — {reason}")
							print(f"[{label}] >>> Resolve it here: {handoff_url}")
							print(f"[{label}] >>> Then type: resume {agent.task_id}\n")
							await agent.handoff(reason)
							return "__HANDOFF__"
						else:
							agent._log(LogAction.JUDGE, f"OFF TRACK: {verdict}", step)
							await agent._emit("correction", {
								"agent_id": agent.task_id,
								"correction": verdict,
							})
							print(f"[{label}] JUDGE: Off track at step {step.number}, stopping task...")
							try:
								await agent.client.tasks.update_task(agent.task_id, action="stop")
							except Exception:
								pass
							return verdict
					else:
						agent._log(LogAction.JUDGE, "ON_TRACK", step)
			return None

		try:
			result = await _drain(stream)

			# Handle handoff cycle — stop, wait for human, retry on same session
			while result == "__HANDOFF__":
				await agent.wait_for_human()
				await agent._emit("human_input_received", {"agent_id": agent.task_id})
				print(f"[{label}] Human done, continuing on same session...")
				result = await _drain(agent.continue_after_handoff())

			return result
		except Exception as e:
			print(f"[{label}] ERROR: {e}")
			return None

	# -- convenience ---------------------------------------------------------

	@property
	def is_running(self) -> bool:
		return self._running

	@property
	def agents(self) -> list[BrowserAgent]:
		return list(self._agents)


def _bedrock_call(system_prompt: str, user_message: str, max_tokens: int = 1024) -> str:
	"""Shared helper for calling Bedrock."""
	token = os.environ["AWS_BEARER_TOKEN_BEDROCK"]
	region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
	model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"

	url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke"
	body = {
		"anthropic_version": "bedrock-2023-05-31",
		"max_tokens": max_tokens,
		"system": system_prompt,
		"messages": [{"role": "user", "content": user_message}],
	}

	resp = httpx.post(
		url,
		json=body,
		headers={"Authorization": f"Bearer {token}"},
		timeout=60,
	)
	resp.raise_for_status()
	return resp.json()["content"][0]["text"]


def _bedrock_vision_call(image_url: str, prompt: str, max_tokens: int = 1024) -> str:
	"""Call Bedrock with an image URL and a text prompt (vision)."""
	token = os.environ["AWS_BEARER_TOKEN_BEDROCK"]
	region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
	model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"

	# Download the image and encode as base64
	import base64
	img_resp = httpx.get(image_url, timeout=30, follow_redirects=True)
	img_resp.raise_for_status()

	content_type = img_resp.headers.get("content-type", "image/png")
	# Normalise to a media type Bedrock accepts
	media_type = content_type.split(";")[0].strip()
	if media_type not in ("image/png", "image/jpeg", "image/gif", "image/webp"):
		media_type = "image/png"

	img_b64 = base64.b64encode(img_resp.content).decode()

	url = f"https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke"
	body = {
		"anthropic_version": "bedrock-2023-05-31",
		"max_tokens": max_tokens,
		"messages": [
			{
				"role": "user",
				"content": [
					{
						"type": "image",
						"source": {
							"type": "base64",
							"media_type": media_type,
							"data": img_b64,
						},
					},
					{
						"type": "text",
						"text": prompt,
					},
				],
			}
		],
	}

	resp = httpx.post(
		url,
		json=body,
		headers={"Authorization": f"Bearer {token}"},
		timeout=60,
	)
	resp.raise_for_status()
	return resp.json()["content"][0]["text"]


def task_refiner(prompt: str) -> list[str]:
	"""Decompose a user goal into independent, parallelisable browser-agent tasks."""
	text = _bedrock_call(
		system_prompt=(
			"You are a task planner for a system that dispatches multiple web-browsing agents "
			"in parallel. Given a user's goal, determine which tasks can be executed simultaneously "
			"by independent browser agents.\n\n"
			"Rules:\n"
			"- Each task MUST be fully independent — no task should depend on the output of another.\n"
			"- Tasks that require sequential steps (e.g. log in then do X) should be a single task.\n"
			"- Prefer splitting by different information sources, websites, or search queries.\n"
			"- Maximum 5 tasks.\n"
			"- Each task should be self-contained with enough context to execute on its own.\n\n"
			"Return your response as a JSON array of strings.\n"
			"Return ONLY the JSON array, nothing else."
		),
		user_message=prompt,
	)
	goals = json.loads(text)
	return goals[:5]


def summarize_results(original_goal: str, agents: list["BrowserAgent"]) -> str:
	"""Synthesize all agent outputs into a single cohesive summary."""
	agent_sections = []
	for i, agent in enumerate(agents, 1):
		status = "COMPLETED" if agent.state == AgentState.COMPLETE else "FAILED"
		output = (agent.result.output or "No output") if agent.result else (agent.error or "No output")
		agent_sections.append(f"AGENT {i} ({status})\nTask: {agent.prompt}\nOutput: {output}")

	return _bedrock_call(
		system_prompt=(
			"You are a research assistant summarizing the results from multiple web-browsing agents "
			"that were dispatched to accomplish parts of a user's goal.\n\n"
			"Synthesize their outputs into a single, cohesive, well-organized summary that directly "
			"addresses the user's original goal. Combine overlapping information, resolve contradictions, "
			"highlight key findings, and note any gaps where agents failed or produced no results.\n\n"
			"Write in a clear, informative style. Use markdown formatting."
		),
		user_message=f"ORIGINAL GOAL: {original_goal}\n\n{''.join(chr(10) + chr(10) + s for s in agent_sections)}",
		max_tokens=2048,
	)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _stdin_reader(orch: Orchestrator) -> None:
	"""Blocking stdin reader that runs in a daemon thread."""
	import sys
	while True:
		try:
			line = sys.stdin.readline()
		except (EOFError, OSError):
			break
		if not line:  # EOF
			break
		line = line.strip()
		if not line:
			continue
		if line.startswith("resume "):
			task_id = line[len("resume "):].strip()
			if orch.resume_agent(task_id):
				print(f">>> Resuming agent {task_id}")
			else:
				print(f">>> No paused agent with task_id={task_id}")
				paused = orch.get_paused_agents()
				if paused:
					print("    Paused agents:")
					for a in paused:
						print(f"      {a.task_id}  {a.prompt[:60]}")
		elif line == "paused":
			paused = orch.get_paused_agents()
			if paused:
				for a in paused:
					print(f"  {a.task_id}  {a.prompt[:60]}")
			else:
				print("  No paused agents.")


async def main():
	import sys

	prompt = "Apply to a software engineering job at decagon for me"

	orch = Orchestrator()
	orch.add_prompt(prompt)

	# Start stdin listener as a daemon thread (dies automatically on exit)
	import threading
	threading.Thread(target=_stdin_reader, args=(orch,), daemon=True).start()

	results = await orch.run()

	print("\n" + "=" * 60)
	print("AGENT RESULTS")
	print("=" * 60)
	for agent in results:
		status = "OK" if agent.state == AgentState.COMPLETE else "FAIL"
		output = (agent.result.output or "—") if agent.result else (agent.error or "—")
		print(f"[{status}] {agent.prompt}")
		print(f"       {output[:200]}")
		print()

	# Summarize all results into a single report
	print("=" * 60)
	print("SUMMARY")
	print("=" * 60)
	summary = summarize_results(prompt, results)
	print(summary)
	# Summary event not emitted in CLI mode (no callback)

	print(f"\nWrote {len(agent_logs)} log entries to {LOG_PATH}")


if __name__ == "__main__":
	asyncio.run(main())
