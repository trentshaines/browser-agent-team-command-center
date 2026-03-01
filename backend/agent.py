"""Orchestrator that manages concurrent browser-use cloud agents.

Usage:
	orch = Orchestrator()
	task_id, agents = orch.create_task("Find reviews on quincy and get the weather in NYC")
	# Agents run in the background. Watch events via SSE or await completion.
"""

import asyncio
import os
import sys
import threading
import uuid
from typing import AsyncIterator

from dotenv import load_dotenv
load_dotenv()

from browser_use_sdk import AsyncBrowserUse
from browser_use_sdk.types.task_step_view import TaskStepView
from browser_use_sdk.types.task_view import TaskView

from event_queue import EventType, add_event
from backend.helpers import (
	MAX_RETRIES,
	MAX_RECOVERY_ATTEMPTS,
	MAX_GOAL_CHECKS,
	JUDGE_EVERY_N_STEPS,
	AgentState,
	LogAction,
	LOG_ACTION_TO_EVENT,
	check_file_store,
	check_goal,
	judge_step,
	needs_handoff,
	build_recovery_prompt,
	task_refiner,
	summarize_results,
)


client = AsyncBrowserUse(api_key=os.environ["BROWSER_USE_API_KEY"])


# ---------------------------------------------------------------------------
# BrowserAgent — autonomous, runs a task to completion
# ---------------------------------------------------------------------------

_SERVER_EVENT_NAMES = {
	"agent_started": "agent_spawned",
	"agent_completed": "agent_status",
	"step": "agent_step",
}


class BrowserAgent:
	"""Autonomous browser agent that handles judging, handoff, correction,
	and recovery internally. Call run() and wait for it to finish."""

	def __init__(self, client: AsyncBrowserUse, prompt: str,
	             on_event=None, name: str = ""):
		self.id = str(uuid.uuid4())
		self.client = client
		self.prompt = prompt
		self.on_event = on_event
		self.name = name or prompt[:30]
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
		self._human_context: str = ""
		self._printed_urls: bool = False

	# -- low-level helpers ------------------------------------------------

	def _emit(self, event_type: EventType, data: dict) -> None:
		"""Emit an event via callback (if set) or global event_queue fallback."""
		if self.on_event is not None:
			name = _SERVER_EVENT_NAMES.get(event_type.value, event_type.value)
			try:
				loop = asyncio.get_running_loop()
				loop.create_task(self.on_event(name, data))
			except RuntimeError:
				pass
		else:
			add_event(event_type, data)

	def _log(self, action: LogAction, content: str,
	         step: TaskStepView | None = None, handoff_url: str | None = None) -> None:
		event_type = LOG_ACTION_TO_EVENT.get(action.value, EventType.OUTPUT)
		data: dict = {"agent_id": self.id, "prompt": self.prompt, "content": content}
		if step:
			data.update(step=step.number, url=step.url, actions=step.actions)
		if handoff_url:
			data["handoff_url"] = handoff_url
		self._emit(event_type, data)
		if step and step.url and step.url.startswith(("http://", "https://")):
			self.last_url = step.url

	def _set_error(self, e: Exception) -> None:
		self.error = str(e)
		self.state = AgentState.ERROR
		self._log(LogAction.ERROR, str(e))

	async def _create_session(self, start_url: str | None = None) -> None:
		kwargs: dict = {"keep_alive": True, "persist_memory": True}
		if start_url:
			kwargs["start_url"] = start_url
		session = await self.client.sessions.create_session(**kwargs)
		self.session_id = session.id
		self.live_url = session.live_url
		try:
			share = await self.client.sessions.create_session_public_share(self.session_id)
			self.share_url = share.share_url
		except Exception:
			pass

	async def _stream_task(self, prompt: str) -> AsyncIterator[TaskStepView]:
		task = await self.client.tasks.create_task(task=prompt, session_id=self.session_id)
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
		self.result = await self.client.tasks.get_task(self.task_id)
		self.state = AgentState.COMPLETE
		self._log(LogAction.OUTPUT, self.result.output or "No output")

	async def get_share_url(self) -> str:
		return self.live_url

	# -- pause / resume ---------------------------------------------------

	async def handoff(self, reason: str = "") -> None:
		"""Stop the task for human intervention (keeps session alive)."""
		try:
			await self.client.tasks.update_task(self.task_id, action="stop")
		except Exception:
			pass
		self.state = AgentState.PAUSED
		self._resume_event.clear()
		self._log(LogAction.PAUSED, reason or "Handed off to user")

	async def wait_for_human(self) -> None:
		await self._resume_event.wait()

	def signal_human_done(self, context: str = "") -> None:
		"""Called externally (server/CLI) when the human is finished."""
		if context:
			self._human_context = context
		self._resume_event.set()

	# -- public entry point -----------------------------------------------

	async def run(self) -> None:
		"""Run this agent to completion. Handles judging, handoff,
		correction, recovery, and goal-checking internally.

		When this returns, self.state is COMPLETE or ERROR.
		"""
		label = self.prompt[:50]

		# Phase 1: Initial execution with inline judging
		try:
			await self._execute_with_judging(label)
		except Exception as e:
			self._set_error(e)

		# Phase 2: Recovery if initial run failed
		if self.state == AgentState.ERROR:
			await self._attempt_recovery(label)
			return

		# Phase 3: Goal-check loop
		await self._goal_check_loop(label)

		# Phase 4: Final recovery fallback
		if self.state in (AgentState.ERROR, AgentState.RUNNING):
			await self._attempt_recovery(label)

	# -- internal: execute + judge ----------------------------------------

	async def _execute_with_judging(
		self, label: str,
		follow_up: str | None = None,
		stream: AsyncIterator[TaskStepView] | None = None,
	) -> None:
		"""Run a stream with inline judging, then apply any corrections."""
		if stream is None:
			stream = self._start_stream() if follow_up is None else self.retry(follow_up)
		correction = await self._drain_and_judge(stream, label)
		await self._apply_corrections(label, correction)

	async def _start_stream(self) -> AsyncIterator[TaskStepView]:
		"""Create session and begin the initial task."""
		self.state = AgentState.RUNNING
		await self._create_session()
		self._emit(EventType.AGENT_STARTED, {
			"agent_id": self.id, "prompt": self.prompt,
			"session_id": self.session_id, "live_url": self.live_url,
		})
		async for step in self._stream_task(self.prompt):
			yield step
		self._emit(EventType.AGENT_COMPLETED, {
			"agent_id": self.id, "prompt": self.prompt,
			"output": self.result.output or "",
		})

	async def retry(self, follow_up_prompt: str) -> AsyncIterator[TaskStepView]:
		"""Run a follow-up task on the same browser session."""
		self.state = AgentState.RUNNING
		self._log(LogAction.RETRY, follow_up_prompt)
		try:
			async for step in self._stream_task(follow_up_prompt):
				yield step
		except Exception as e:
			self._set_error(e)
			raise

	# -- internal: drain + judge ------------------------------------------

	async def _drain_and_judge(
		self, stream: AsyncIterator[TaskStepView], label: str,
	) -> str | None:
		"""Consume a step stream with inline judging and handoff detection.

		Returns None if completed normally, or a correction string.
		Handoffs are handled inline: pause → wait → resume → continue.
		"""
		while True:
			try:
				result = await self._drain_one_stream(stream, label)
			except Exception as e:
				print(f"[{label}] ERROR: {e}")
				return None

			if result != "__HANDOFF__":
				return result

			# Handoff: wait for human, then build continuation stream
			await self.wait_for_human()
			self._emit(EventType.HUMAN_INPUT_RECEIVED, {"agent_id": self.id})
			print(f"[{label}] Human done, continuing on same session...")
			stream = self._continue_after_handoff_stream()

	async def _drain_one_stream(
		self, stream: AsyncIterator[TaskStepView], label: str,
	) -> str | None:
		"""Drain a single stream. Returns None, a correction, or '__HANDOFF__'."""
		async for step in stream:
			if not self._printed_urls:
				self._printed_urls = True
				if self.live_url:
					print(f"[{label}] Live view:  {self.live_url}")
				if self.share_url:
					print(f"[{label}] Share link: {self.share_url}")

			print(
				f"[{label}] step {step.number}: {step.next_goal}"
				+ (f"  url={step.url}" if step.url else "")
			)
			self._emit(EventType.STEP, {
				"agent_id": self.id, "step": step.number,
				"goal": step.next_goal, "url": step.url, "actions": step.actions,
			})

			# Vision check for forms / captchas / checkouts
			handoff_reason = needs_handoff(self.prompt, step)
			if handoff_reason:
				auto = await self._try_auto_resolve(label, handoff_reason)
				if auto is not None:
					return auto
				await self._do_handoff(label, handoff_reason, step, source="vision")
				return "__HANDOFF__"

			# Judge every N steps
			if step.number > 0 and step.number % JUDGE_EVERY_N_STEPS == 0:
				recent = self.steps[-JUDGE_EVERY_N_STEPS:]
				verdict = judge_step(self.prompt, recent)
				if verdict is not None:
					if verdict.startswith("NEEDS_HUMAN:"):
						reason = verdict[len("NEEDS_HUMAN:"):].strip()
						auto = await self._try_auto_resolve(label, reason)
						if auto is not None:
							return auto
						await self._do_handoff(label, reason, step, source="judge")
						return "__HANDOFF__"
					# Off track — stop task and return correction
					self._log(LogAction.JUDGE, f"OFF TRACK: {verdict}", step)
					self._emit(EventType.CORRECTION, {"agent_id": self.id, "correction": verdict})
					print(f"[{label}] JUDGE: Off track at step {step.number}, stopping task...")
					try:
						await self.client.tasks.update_task(self.task_id, action="stop")
					except Exception:
						pass
					return verdict
				self._log(LogAction.JUDGE, "ON_TRACK", step)

		return None

	# -- internal: handoff ------------------------------------------------

	async def _try_auto_resolve(self, label: str, reason: str) -> str | None:
		"""Check file_store before handing off to a human.

		If relevant files are found, stops the current task and returns a
		correction string so the agent retries with the file context.
		Returns None if no files matched (caller should proceed with handoff).
		"""
		file_context = check_file_store(reason)
		if file_context is None:
			return None

		print(f"[{label}] File store has what we need, skipping handoff")
		self._log(LogAction.THINKING, f"Auto-resolved from file store: {reason}")
		try:
			await self.client.tasks.update_task(self.task_id, action="stop")
		except Exception:
			pass
		return (
			f"The user has provided the following information from their files. "
			f"Use it to continue toward the goal.\n\n{file_context}"
		)

	async def _do_handoff(self, label: str, reason: str,
	                       step: TaskStepView | None = None, source: str = "") -> None:
		"""Full handoff ceremony: log, emit event, print, pause."""
		handoff_url = await self.get_share_url()
		self._log(LogAction.HANDOFF, reason, step, handoff_url=handoff_url)
		self._emit(EventType.HANDOFF, {
			"agent_id": self.id, "message": reason,
			"handoff_url": handoff_url, "source": source,
		})
		print(f"\n[{label}] HANDOFF — {reason}")
		print(f"[{label}] >>> Resolve it here: {handoff_url}")
		print(f"[{label}] >>> Then resume agent {self.id}\n")
		await self.handoff(reason)

	def _continue_after_handoff_stream(self) -> AsyncIterator[TaskStepView]:
		"""Build a continuation stream after human handoff."""
		continuation = (
			f"The user just completed a manual step in the browser (the page may have changed). "
			f"Continue working toward the original goal: {self.prompt}"
		)
		if self._human_context:
			continuation += f"\n\nAdditional context from the user: {self._human_context}"
			self._human_context = ""
		self._log(LogAction.RESUMED, "Human done, continuing on same session")
		return self.retry(continuation)

	# -- internal: corrections --------------------------------------------

	async def _apply_corrections(self, label: str, correction: str | None) -> None:
		"""Retry loop for judge corrections."""
		for _ in range(MAX_RETRIES):
			if correction is None:
				break
			print(f"[{label}] Judge correcting: {correction}")
			self._log(LogAction.CORRECTION, correction)
			try:
				correction = await self._drain_and_judge(self.retry(correction), label)
			except Exception as e:
				print(f"[{label}] CORRECTION ERROR: {e}")
				break

	# -- internal: goal-check loop ----------------------------------------

	async def _goal_check_loop(self, label: str) -> None:
		"""Check if this agent's goal is met; retry or handoff as needed."""
		for attempt in range(MAX_GOAL_CHECKS):
			if self.state != AgentState.COMPLETE or not self.result:
				break

			verdict, detail = check_goal(self.prompt, self.result.output or "", self.steps)

			if verdict == "COMPLETE":
				print(f"[{label}] Goal complete.")
				return

			if verdict == "HUMAN":
				# Check file store before escalating to human
				file_context = check_file_store(detail)
				if file_context:
					print(f"[{label}] File store resolved handoff, continuing...")
					self._human_context = file_context
					try:
						await self._execute_with_judging(
							label, stream=self._continue_after_handoff_stream()
						)
					except Exception as e:
						print(f"[{label}] POST-FILE-STORE ERROR: {e}")
						break
				else:
					await self._do_handoff(label, detail, source="goal_check")
					await self.wait_for_human()
					self._emit(EventType.HUMAN_INPUT_RECEIVED, {"agent_id": self.id})
					print(f"[{label}] Human done, continuing...")
					try:
						await self._execute_with_judging(
							label, stream=self._continue_after_handoff_stream()
						)
					except Exception as e:
						print(f"[{label}] POST-HANDOFF ERROR: {e}")
						break
			else:
				# AGENT — keep going with the follow-up instruction
				print(f"[{label}] Goal incomplete (attempt {attempt + 1}/{MAX_GOAL_CHECKS}): {detail[:120]}")
				try:
					await self._execute_with_judging(label, follow_up=detail)
				except Exception as e:
					print(f"[{label}] RETRY ERROR: {e}")
					break

	# -- internal: recovery -----------------------------------------------

	async def _attempt_recovery(self, label: str) -> None:
		"""Try to recover with a fresh browser session."""
		for attempt in range(MAX_RECOVERY_ATTEMPTS):
			error_msg = self.error or "Unknown error"
			last_url = self.last_url
			print(f"[{label}] Recovery attempt {attempt + 1}/{MAX_RECOVERY_ATTEMPTS}...")

			recovery_prompt = build_recovery_prompt(self.prompt, self.steps, error_msg)
			print(f"[{label}] Recovery plan: {recovery_prompt[:120]}...")
			if last_url:
				print(f"[{label}] Starting from: {last_url}")

			try:
				self._emit(EventType.RECOVERY_STARTED, {
					"agent_id": self.id, "attempt": attempt + 1,
					"recovery_prompt": recovery_prompt, "start_url": last_url,
				})
				stream = self._recover_stream(recovery_prompt, last_url)
				await self._execute_with_judging(label, stream=stream)
			except Exception as e:
				print(f"[{label}] RECOVERY ERROR: {e}")
				continue

			if self.state == AgentState.COMPLETE:
				self._emit(EventType.RECOVERY_COMPLETED, {"agent_id": self.id})
				print(f"[{label}] Recovered successfully.")
				return

		print(f"[{label}] All recovery attempts exhausted.")

	async def _recover_stream(
		self, recovery_prompt: str, start_url: str | None,
	) -> AsyncIterator[TaskStepView]:
		"""Create a fresh session and stream a recovery task."""
		self.state = AgentState.RUNNING
		self.error = None
		self.result = None
		self._log(LogAction.RETRY, f"Recovering with new session: {recovery_prompt}")
		await self._create_session(start_url)
		async for step in self._stream_task(recovery_prompt):
			yield step


# ---------------------------------------------------------------------------
# Orchestrator — high-level coordinator
# ---------------------------------------------------------------------------

class Orchestrator:
	"""Splits goals into sub-tasks, launches autonomous agents, checks completion."""

	def __init__(self, on_event=None):
		self._on_event = on_event
		self._agents: list[BrowserAgent] = []
		self._tasks: dict[str, list[BrowserAgent]] = {}
		self._running_tasks: dict[str, asyncio.Task] = {}

	def _emit(self, event_type: EventType, data: dict) -> None:
		"""Emit an event via callback (if set) or global event_queue fallback."""
		if self._on_event is not None:
			name = _SERVER_EVENT_NAMES.get(event_type.value, event_type.value)
			try:
				loop = asyncio.get_running_loop()
				loop.create_task(self._on_event(name, data))
			except RuntimeError:
				pass
		else:
			add_event(event_type, data)

	# -- public API (used by server.py) -----------------------------------

	def add_prompt(self, prompt: str, name: str = "") -> "BrowserAgent":
		"""Add an agent for the given prompt. Returns the agent."""
		agent = BrowserAgent(client, prompt, on_event=self._on_event, name=name)
		self._agents.append(agent)
		return agent

	async def run(self) -> None:
		"""Run all agents added via add_prompt in parallel."""
		if not self._agents:
			return
		await asyncio.gather(*[a.run() for a in self._agents], return_exceptions=True)

	def create_task(self, prompt: str) -> tuple[str, list[BrowserAgent]]:
		"""Decompose prompt into sub-tasks, create agents, launch them.

		Returns (task_id, agents) immediately. Agents run in the background.
		"""
		task_id = str(uuid.uuid4())

		sub_prompts = task_refiner(prompt)

		agents: list[BrowserAgent] = []
		for sub_prompt in sub_prompts:
			agent = BrowserAgent(client, sub_prompt, on_event=self._on_event)
			self._agents.append(agent)
			agents.append(agent)

		self._tasks[task_id] = agents

		bg_task = asyncio.create_task(
			self._run_task(task_id, prompt, agents),
			name=f"task-{task_id[:8]}",
		)
		self._running_tasks[task_id] = bg_task

		return task_id, agents

	def get_agent(self, agent_id: str) -> BrowserAgent | None:
		return next((a for a in self._agents if a.id == agent_id), None)

	def resume_agent(self, agent_id: str, context: str = "") -> bool:
		agent = self.get_agent(agent_id)
		if agent and agent.state == AgentState.PAUSED:
			agent.signal_human_done(context)
			return True
		return False

	def get_paused_agents(self) -> list[BrowserAgent]:
		return [a for a in self._agents if a.state == AgentState.PAUSED]

	async def wait_for_task(self, task_id: str) -> list[BrowserAgent]:
		"""Wait for a task to finish and return its agents."""
		bg_task = self._running_tasks.get(task_id)
		if bg_task:
			await bg_task
		return self._tasks.get(task_id, [])

	# -- internal: the orchestration loop ---------------------------------

	async def _run_task(
		self, task_id: str, original_goal: str, agents: list[BrowserAgent],
	) -> None:
		"""Launch agents, wait, summarize, goal-check, possibly re-launch."""
		for goal_round in range(MAX_GOAL_CHECKS):
			# Launch all pending/errored agents in parallel
			agent_coros = [
				agent.run() for agent in agents
				if agent.state in (AgentState.PENDING, AgentState.ERROR)
			]
			if agent_coros:
				await asyncio.gather(*agent_coros, return_exceptions=True)

			# Summarize results from ALL agents across all rounds
			all_agents = self._tasks[task_id]
			summary = summarize_results(original_goal, all_agents)
			print(f"\n{'=' * 60}")
			print(f"[Orchestrator] Round {goal_round + 1} summary:\n{summary}")
			print(f"{'=' * 60}\n")
			self._emit(EventType.SUMMARY, {"task_id": task_id, "summary": summary})

			# Check if overall goal is met
			all_outputs = summary
			verdict, detail = check_goal(original_goal, all_outputs)

			if verdict == "COMPLETE":
				print(f"[Orchestrator] Goal fully achieved.")
				return

			if verdict == "HUMAN":
				print(f"[Orchestrator] Overall goal needs human: {detail}")
				self._emit(EventType.HANDOFF, {
					"task_id": task_id,
					"message": detail,
					"source": "orchestrator_goal_check",
				})
				return

			# AGENT — spawn follow-up agents for the next round
			print(f"[Orchestrator] Goal incomplete (round {goal_round + 1}): {detail[:120]}")
			follow_up_prompts = task_refiner(detail)
			agents = []
			for sub_prompt in follow_up_prompts:
				agent = BrowserAgent(client, sub_prompt, on_event=self._on_event)
				self._agents.append(agent)
				self._tasks[task_id].append(agent)
				agents.append(agent)

		print(f"[Orchestrator] Max rounds exhausted for task {task_id[:8]}.")

	# -- convenience ------------------------------------------------------

	@property
	def is_running(self) -> bool:
		return any(not t.done() for t in self._running_tasks.values())

	@property
	def agents(self) -> list[BrowserAgent]:
		return list(self._agents)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _stdin_reader(orch: Orchestrator) -> None:
	"""Blocking stdin reader that runs in a daemon thread."""
	while True:
		try:
			line = sys.stdin.readline()
		except (EOFError, OSError):
			break
		if not line:
			break
		line = line.strip()
		if not line:
			continue
		if line.startswith("resume "):
			agent_id = line[len("resume "):].strip()
			if orch.resume_agent(agent_id):
				print(f">>> Resuming agent {agent_id}")
			else:
				print(f">>> No paused agent with id={agent_id}")
				paused = orch.get_paused_agents()
				if paused:
					print("    Paused agents:")
					for a in paused:
						print(f"      {a.id}  {a.prompt[:60]}")
		elif line == "paused":
			paused = orch.get_paused_agents()
			if paused:
				for a in paused:
					print(f"  {a.id}  {a.prompt[:60]}")
			else:
				print("  No paused agents.")


async def main():
	prompt = "Apply to a software engineering job at decagon for me"
	prompt = "Find good arbitrage opportunities on Temu vs Amazon"

	orch = Orchestrator()
	task_id, agents = orch.create_task(prompt)

	print(f"Task {task_id[:8]} launched with {len(agents)} sub-agent(s):")
	for a in agents:
		print(f"  - {a.id[:8]}: {a.prompt[:80]}")

	# Start stdin listener for resume commands
	threading.Thread(target=_stdin_reader, args=(orch,), daemon=True).start()

	# Wait for the task to complete
	results = await orch.wait_for_task(task_id)

	print("\n" + "=" * 60)
	print("AGENT RESULTS")
	print("=" * 60)
	for agent in results:
		status = "OK" if agent.state == AgentState.COMPLETE else "FAIL"
		output = (agent.result.output or "—") if agent.result else (agent.error or "—")
		print(f"[{status}] {agent.prompt}")
		print(f"       {output[:200]}")
		print()

	print("Done.")


if __name__ == "__main__":
	asyncio.run(main())
