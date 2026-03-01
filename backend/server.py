"""Minimal FastAPI server wrapping agent.py.

Start:
    uv run uvicorn backend.server:app --port 8000 --reload

Endpoints:
    POST /sessions/{session_id}/task       — create a task within a session
    GET  /sessions/{session_id}/stream     — SSE stream (can connect before task creation)
    POST /task/{task_id}/respond/{agent_id} — unpause a human-handoff agent
    POST /task/{task_id}/agent/{agent_id}/reprompt — reprompt an agent on its existing session
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent import BrowserAgent, Orchestrator, task_refiner, summarize_results
from backend.helpers import _bedrock_call_haiku

app = FastAPI(title="Browser Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

@dataclass
class TaskState:
    orchestrator: Orchestrator
    agents: list[BrowserAgent] = field(default_factory=list)
    done: bool = False


tasks: dict[str, TaskState] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AgentSpec(BaseModel):
    name: str
    task: str


class CreateTaskRequest(BaseModel):
    prompt: str
    agents: list[AgentSpec] | None = None


class CreateTaskResponse(BaseModel):
    task_id: str


class RepromptRequest(BaseModel):
    prompt: str


class PlanRequest(BaseModel):
    prompt: str


class PlanResponse(BaseModel):
    title: str
    agents: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Session-level subscriber queues — allows SSE to connect before any task is created.
session_queues: dict[str, list[asyncio.Queue]] = {}
session_to_task: dict[str, str] = {}

# Event log file — one JSON object per line, easy to tail/parse.
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / "events.jsonl"
_log_handle = open(_LOG_FILE, "a", buffering=1)  # line-buffered


def _log_event(session_id: str, event: dict) -> None:
    """Append a translated SSE event to the JSONL log file."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        **event,
    }
    # Strip screenshot data to keep the file readable
    record.pop("screenshot", None)
    _log_handle.write(json.dumps(record) + "\n")


def _translate_event(event_type: str, data: dict[str, Any], state: TaskState | None) -> dict:
    """Translate backend event types to the SSE event names the frontend expects.

      agent_spawned  → SSE event "agent_event", data.type = "agent_spawned"
      agent_status   → SSE event "agent_event", data.type = "agent_complete"
      agent_step     → SSE event "agent_log",   data.agent_run_id = agent_id
      agent_frame    → SSE event "agent_frame"  (pass-through)
      done           → SSE event "done"
    """
    if event_type == "agent_spawned":
        return {"event": "agent_event", "type": "agent_spawned",
                "task": data.get("prompt"), **data}
    elif event_type == "agent_status":
        agent_id = data.get("agent_id")
        total_steps = 0
        if state:
            for agent in state.agents:
                if agent.task_id == agent_id:
                    total_steps = len(agent.steps)
                    break
        return {
            "event": "agent_event",
            "type": "agent_complete",
            "agent_run_id": agent_id,
            "result": data.get("result"),
            "total_steps": total_steps,
        }
    elif event_type == "agent_step":
        return {
            "event": "agent_log",
            "agent_run_id": data.get("agent_id"),
            **{k: v for k, v in data.items() if k != "agent_id"},
        }
    elif event_type == "agent_frame":
        return {"event": "agent_frame", **data}
    elif event_type in ("handoff", "human_input_received"):
        return {"event": event_type, **data}
    elif event_type == "done":
        return {"event": "done", **data}
    else:
        return {"event": event_type, **data}


def _make_session_callback(session_id: str):
    """Return an async callback that pushes translated events to session queues."""
    async def on_event(event_type: str, data: dict[str, Any]) -> None:
        queues = session_queues.get(session_id, [])
        task_id = session_to_task.get(session_id)
        state = tasks.get(task_id) if task_id else None

        event = _translate_event(event_type, data, state)
        _log_event(session_id, event)
        for q in queues:
            await q.put(event)

        if event_type == "done":
            if state:
                state.done = True
            for q in queues:
                await q.put(None)
    return on_event


async def _run_task(task_id: str, session_id: str) -> None:
    """Background coroutine that runs the orchestrator to completion."""
    state = tasks.get(task_id)
    if not state:
        return
    queues = session_queues.get(session_id, [])
    try:
        await state.orchestrator.run()
    except Exception as e:
        event = {"event": "error", "error": str(e)}
        for q in queues:
            await q.put(event)
    finally:
        state.done = True
        for q in queues:
            await q.put(None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/plan", response_model=PlanResponse)
async def plan_task(req: PlanRequest):
    """Decompose a prompt into parallelisable agent tasks."""
    subtasks = task_refiner(req.prompt)
    agents = [{"name": f"Agent {i+1}", "task": t} for i, t in enumerate(subtasks)]
    title = req.prompt[:60].strip()
    if len(req.prompt) > 60:
        title += "…"
    return PlanResponse(title=title, agents=agents)


@app.post("/sessions/{session_id}/task")
async def create_session_task(session_id: str, req: CreateTaskRequest):
    """Create a task and associate it with a frontend session ID."""
    task_id = str(uuid.uuid4())

    callback = _make_session_callback(session_id)
    orch = Orchestrator(on_event=callback)

    state = TaskState(orchestrator=orch)
    tasks[task_id] = state
    session_to_task[session_id] = task_id

    if session_id not in session_queues:
        session_queues[session_id] = []

    if req.agents:
        agent_specs = [(a.name, a.task) for a in req.agents]
    else:
        subtasks = task_refiner(req.prompt)
        agent_specs = [(f"Agent {i+1}", t) for i, t in enumerate(subtasks)]

    for name, task_prompt in agent_specs:
        agent = orch.add_prompt(task_prompt, name=name)
        state.agents.append(agent)

    asyncio.create_task(_run_task(task_id, session_id))

    return CreateTaskResponse(task_id=task_id)


@app.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str):
    """SSE stream using the frontend's session ID. Can connect before any task is created."""
    if session_id not in session_queues:
        session_queues[session_id] = []

    q: asyncio.Queue = asyncio.Queue()
    session_queues[session_id].append(q)

    async def event_generator():
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                event_type = event.pop("event", "message")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
        finally:
            queues = session_queues.get(session_id, [])
            if q in queues:
                queues.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class NarrateRequest(BaseModel):
    agent_name: str
    task: str
    logs: list[str]
    completed: bool = False
    result: str | None = None


class NarrateResponse(BaseModel):
    message: str


@app.post("/narrate", response_model=NarrateResponse)
async def narrate_agent(req: NarrateRequest):
    """Synthesize agent logs into a conversational chat message using Haiku."""
    logs_text = "\n".join(f"- {log}" for log in req.logs) if req.logs else "(no recent activity)"

    if req.completed:
        user_message = (
            f"AGENT: {req.agent_name}\n"
            f"TASK: {req.task}\n"
            f"STATUS: Completed\n"
            f"RECENT ACTIVITY:\n{logs_text}\n"
            f"RESULT: {req.result or '(no result)'}"
        )
    else:
        user_message = (
            f"AGENT: {req.agent_name}\n"
            f"TASK: {req.task}\n"
            f"STATUS: In progress\n"
            f"RECENT ACTIVITY:\n{logs_text}"
        )

    try:
        raw = _bedrock_call_haiku(
            system_prompt=(
                "You are a team member giving a brief status update in a Slack channel. "
                "Given an agent's recent activity logs, write a casual 1-2 sentence update "
                "as if YOU are the one doing the work. Use first person. Be concise and natural. "
                "Don't say 'I navigated to' for every page — summarize what you're actually doing. "
                "If the task is completed, summarize the key finding or outcome. "
                "Write ONLY the message, no preamble."
            ),
            user_message=user_message,
            max_tokens=256,
        )
        return NarrateResponse(message=raw.strip())
    except Exception:
        # Fallback: generate a simple message without LLM
        if req.completed:
            fallback = req.result[:200] if req.result else "Done"
            return NarrateResponse(message=f"Finished up — {fallback}")
        last_log = req.logs[-1] if req.logs else "working on it"
        return NarrateResponse(message=f"Still at it — {last_log}")


@app.post("/task/{task_id}/respond/{agent_id}")
async def respond(
    task_id: str,
    agent_id: str,
    prompt: str = Form(""),
    file: UploadFile | None = File(None),
):
    """Respond to a paused agent. Empty prompt = unpause and continue.

    Non-empty prompt can be used to give the agent additional instructions.
    """
    state = tasks.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")

    target = None
    for agent in state.agents:
        if agent.task_id == agent_id:
            target = agent
            break

    if not target:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Empty prompt = just unpause (human finished in the browser)
    target.signal_human_done()
    return {"ok": True}


@app.post("/task/{task_id}/agent/{agent_id}/reprompt")
async def reprompt_agent(task_id: str, agent_id: str, req: RepromptRequest):
    state = tasks.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")

    # Find the agent by its UUID
    target = None
    for agent in state.agents:
        if agent.id == agent_id:
            target = agent
            break

    if not target:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Launch retry on the agent's existing session as a background task
    async def _do_reprompt():
        async for _step in target.retry(req.prompt):
            pass

    asyncio.create_task(_do_reprompt())

    return {"ok": True}
