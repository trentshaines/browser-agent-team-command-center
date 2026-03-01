"""Minimal FastAPI server wrapping agent.py.

Start:
    uv run uvicorn backend.server:app --port 8000 --reload

Endpoints:
    POST /task                              — create a task (auto-decompose or manual agents)
    GET  /task/{task_id}/stream             — SSE stream of all events for a task
    POST /task/{task_id}/agent/{agent_id}/reprompt — reprompt an agent on its existing session
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent import BrowserAgent, Orchestrator, task_refiner, summarize_results

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
    queues: list[asyncio.Queue] = field(default_factory=list)
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

def _make_event_callback(task_id: str):
    """Return an async callback that pushes events to all subscriber queues.

    Translates backend event types to the SSE event names the frontend expects:
      agent_spawned  → SSE event "agent_event", data.type = "agent_spawned"
      agent_status   → SSE event "agent_event", data.type = "agent_complete"
      agent_step     → SSE event "agent_log",   data.agent_run_id = agent_id
      agent_frame    → SSE event "agent_frame"  (pass-through)
      done           → SSE event "done"
    """
    async def on_event(event_type: str, data: dict[str, Any]) -> None:
        state = tasks.get(task_id)
        if not state:
            return

        if event_type == "agent_spawned":
            event = {"event": "agent_event", "type": "agent_spawned", **data}
        elif event_type == "agent_status":
            # Map to agent_complete (frontend uses this for both success and error)
            agent_id = data.get("agent_id")
            # Count total steps from the matching agent
            total_steps = 0
            for agent in state.agents:
                if agent.task_id == agent_id:
                    total_steps = len(agent.steps)
                    break
            event = {
                "event": "agent_event",
                "type": "agent_complete",
                "agent_run_id": agent_id,
                "result": data.get("result"),
                "total_steps": total_steps,
            }
        elif event_type == "agent_step":
            # Map to agent_log with agent_run_id field the frontend expects
            event = {
                "event": "agent_log",
                "agent_run_id": data.get("agent_id"),
                **{k: v for k, v in data.items() if k != "agent_id"},
            }
        elif event_type == "agent_frame":
            event = {"event": "agent_frame", **data}
        elif event_type == "done":
            event = {"event": "done", **data}
        else:
            event = {"event": event_type, **data}

        for q in state.queues:
            await q.put(event)

        if event_type == "done":
            state.done = True
            for q in state.queues:
                await q.put(None)
    return on_event


async def _run_task(task_id: str, state: TaskState) -> None:
    """Background coroutine that runs the orchestrator to completion."""
    try:
        await state.orchestrator.run()
    except Exception as e:
        # Push an error event if the orchestrator itself crashes
        event = {"event": "error", "error": str(e)}
        for q in state.queues:
            await q.put(event)
    finally:
        state.done = True
        for q in state.queues:
            await q.put(None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/plan", response_model=PlanResponse)
async def plan_task(req: PlanRequest):
    """Decompose a prompt into parallelisable agent tasks."""
    subtasks = task_refiner(req.prompt)
    agents = [{"name": f"Agent {i+1}", "task": t} for i, t in enumerate(subtasks)]
    # Use the first few words of the prompt as a title
    title = req.prompt[:60].strip()
    if len(req.prompt) > 60:
        title += "…"
    return PlanResponse(title=title, agents=agents)


@app.post("/task", response_model=CreateTaskResponse)
async def create_task(req: CreateTaskRequest):
    task_id = str(uuid.uuid4())

    callback = _make_event_callback(task_id)
    orch = Orchestrator(on_event=callback)

    state = TaskState(orchestrator=orch)
    tasks[task_id] = state

    # Determine agent specs
    if req.agents:
        agent_specs = [(a.name, a.task) for a in req.agents]
    else:
        subtasks = task_refiner(req.prompt)
        agent_specs = [(f"Agent {i+1}", t) for i, t in enumerate(subtasks)]

    # Add agents to orchestrator (real agent IDs come via SSE agent_spawned events)
    for name, task_prompt in agent_specs:
        agent = orch.add_prompt(task_prompt, name=name)
        state.agents.append(agent)

    # Launch orchestrator in background
    asyncio.create_task(_run_task(task_id, state))

    return CreateTaskResponse(task_id=task_id)


@app.get("/task/{task_id}/stream")
async def stream_task(task_id: str):
    state = tasks.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")

    q: asyncio.Queue = asyncio.Queue()
    state.queues.append(q)

    async def event_generator():
        try:
            while True:
                event = await q.get()
                if event is None:
                    # Stream is done
                    break
                event_type = event.pop("event", "message")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
        finally:
            # Clean up subscriber queue
            if q in state.queues:
                state.queues.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Session-compatible endpoints (the frontend connects to /sessions/{id}/stream)
# ---------------------------------------------------------------------------

# Session-level subscriber queues — allows SSE to connect before any task is created.
session_queues: dict[str, list[asyncio.Queue]] = {}
session_to_task: dict[str, str] = {}


def _make_session_callback(session_id: str):
    """Like _make_event_callback but pushes to session-level queues."""
    async def on_event(event_type: str, data: dict[str, Any]) -> None:
        queues = session_queues.get(session_id, [])
        task_id = session_to_task.get(session_id)
        state = tasks.get(task_id) if task_id else None

        if event_type == "agent_spawned":
            event = {"event": "agent_event", "type": "agent_spawned", **data}
        elif event_type == "agent_status":
            agent_id = data.get("agent_id")
            total_steps = 0
            if state:
                for agent in state.agents:
                    if agent.task_id == agent_id:
                        total_steps = len(agent.steps)
                        break
            event = {
                "event": "agent_event",
                "type": "agent_complete",
                "agent_run_id": agent_id,
                "result": data.get("result"),
                "total_steps": total_steps,
            }
        elif event_type == "agent_step":
            event = {
                "event": "agent_log",
                "agent_run_id": data.get("agent_id"),
                **{k: v for k, v in data.items() if k != "agent_id"},
            }
        elif event_type == "agent_frame":
            event = {"event": "agent_frame", **data}
        elif event_type == "done":
            event = {"event": "done", **data}
        else:
            event = {"event": event_type, **data}

        for q in queues:
            await q.put(event)

        if event_type == "done":
            if state:
                state.done = True
            for q in queues:
                await q.put(None)
    return on_event


@app.post("/sessions/{session_id}/task")
async def create_session_task(session_id: str, req: CreateTaskRequest):
    """Create a task and associate it with a frontend session ID."""
    task_id = str(uuid.uuid4())

    callback = _make_session_callback(session_id)
    orch = Orchestrator(on_event=callback)

    state = TaskState(orchestrator=orch)
    tasks[task_id] = state
    session_to_task[session_id] = task_id

    # Ensure session queue list exists
    if session_id not in session_queues:
        session_queues[session_id] = []

    # Determine agent specs
    if req.agents:
        agent_specs = [(a.name, a.task) for a in req.agents]
    else:
        subtasks = task_refiner(req.prompt)
        agent_specs = [(f"Agent {i+1}", t) for i, t in enumerate(subtasks)]

    # Add agents to orchestrator (real agent IDs come via SSE agent_spawned events)
    for name, task_prompt in agent_specs:
        agent = orch.add_prompt(task_prompt, name=name)
        state.agents.append(agent)

    # Launch orchestrator in background
    asyncio.create_task(_run_task(task_id, state))

    return CreateTaskResponse(task_id=task_id)


@app.get("/sessions/{session_id}/stream")
async def stream_session(session_id: str):
    """SSE stream using the frontend's session ID. Can connect before any task is created."""
    # Ensure session queue list exists (may be called before POST /sessions/{id}/task)
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


@app.post("/task/{task_id}/agent/{agent_id}/reprompt")
async def reprompt_agent(task_id: str, agent_id: str, req: RepromptRequest):
    state = tasks.get(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")

    # Find the agent by its browser-use task_id
    target = None
    for agent in state.agents:
        if agent.task_id == agent_id:
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
