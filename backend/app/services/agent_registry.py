"""In-memory queue for browser agent run ID claiming.

When the orchestrator detects a Task tool call it creates an AgentRun in the DB and
pushes the run ID here. When browser_agent.py starts it calls /internal/agent-claim
to pop that ID and use it for all subsequent HTTP posts, so both systems share the
same UUID and the frontend never gets duplicate/ghost entries.
"""
import asyncio
from typing import Optional

_queues: dict[str, asyncio.Queue[str]] = {}


def _get_queue(session_id: str) -> "asyncio.Queue[str]":
    if session_id not in _queues:
        _queues[session_id] = asyncio.Queue()
    return _queues[session_id]


def flush(session_id: str) -> None:
    """Discard any unclaimed IDs from a previous turn before starting a new one."""
    if session_id in _queues:
        q = _queues[session_id]
        while not q.empty():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                break


def push(session_id: str, agent_run_id: str) -> None:
    _get_queue(session_id).put_nowait(agent_run_id)


async def claim(session_id: str, timeout: float = 5.0) -> Optional[str]:
    """Wait up to `timeout` seconds for an agent_run_id to become available."""
    try:
        return await asyncio.wait_for(_get_queue(session_id).get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None
