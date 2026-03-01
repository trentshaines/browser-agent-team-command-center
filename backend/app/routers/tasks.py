import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.agent_run_log import AgentRunLog
from app.models.message import Message
from app.models.session import Session
from app.routers.sessions import get_owned_session
from app.schemas.message import MessageRead
from app.services import sse, agent_registry

logger = logging.getLogger(__name__)

router = APIRouter()

# backend/app/routers/ -> backend/
_BACKEND_DIR = Path(__file__).parent.parent.parent


class AgentSpec(BaseModel):
    name: str
    task: str


class TaskCreate(BaseModel):
    prompt: str
    agents: list[AgentSpec]


@router.post("/{session_id}/task", response_model=MessageRead)
async def create_task(
    session_id: uuid.UUID,
    data: TaskCreate,
    session: Annotated[Session, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Directly spawn one or more named browser agents for a given prompt,
    bypassing Claude's planning step.
    """
    # Save the prompt as a user message
    user_msg = Message(session_id=session_id, role="user", content=data.prompt)
    db.add(user_msg)

    # Placeholder assistant message (filled in when all agents complete)
    assistant_msg = Message(session_id=session_id, role="assistant", content="")
    db.add(assistant_msg)
    await db.flush()

    if session.title == "New Chat":
        stripped = data.prompt.strip()
        session.title = stripped[:60] + ("..." if len(stripped) > 60 else "")

    assistant_msg_id = assistant_msg.id
    session_id_str = str(session_id)

    # Create an AgentRun for each agent, register its ID, and announce it on SSE
    agent_run_specs: list[tuple[uuid.UUID, str, str]] = []  # (run_id, name, task)
    for spec in data.agents:
        agent_run = AgentRun(
            session_id=session_id,
            message_id=assistant_msg_id,
            task=spec.task,
            status=AgentRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db.add(agent_run)
        await db.flush()
        agent_registry.push(session_id_str, str(agent_run.id))
        await sse.publish(session_id_str, "agent_event", {
            "type": "agent_spawned",
            "agent_id": str(agent_run.id),
            "task": spec.task,
            "name": spec.name,
        })
        agent_run_specs.append((agent_run.id, spec.name, spec.task))
        logger.info("Task: queued agent run=%s name=%s", agent_run.id, spec.name)

    await db.commit()

    # Run all subprocesses in the background
    asyncio.create_task(_run_all_agents(session_id_str, assistant_msg_id, agent_run_specs))

    return assistant_msg


async def _run_all_agents(
    session_id_str: str,
    message_id: uuid.UUID,
    agent_run_specs: list[tuple[uuid.UUID, str, str]],
) -> None:
    await asyncio.gather(
        *[_run_single_agent(session_id_str, run_id, task) for run_id, _name, task in agent_run_specs],
        return_exceptions=True,
    )

    # All agents done — write summary and emit 'done'
    count = len(agent_run_specs)
    summary = f"{count} agent{'s' if count != 1 else ''} completed."
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Message).where(Message.id == message_id))
        msg = result.scalar_one_or_none()
        if msg:
            msg.content = summary
        await db.commit()

    await sse.publish(session_id_str, "done", {
        "message_id": str(message_id),
        "content": summary,
    })


async def _run_single_agent(
    session_id_str: str,
    agent_run_id: uuid.UUID,
    task: str,
) -> None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "python", "scripts/browser_agent.py",
            "--task", task,
            "--session-id", session_id_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=_BACKEND_DIR,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()

        if stderr_bytes:
            for line in stderr_bytes.decode(errors="replace").splitlines():
                logger.warning("browser_agent stderr [run=%s]: %s", agent_run_id, line)

        # Parse JSONL stdout and persist to DB
        steps: list[dict] = []
        final_result: dict | None = None
        for line in stdout_bytes.decode(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if rec.get("type") == "browser_step":
                    steps.append(rec)
                elif rec.get("type") == "browser_result":
                    final_result = rec
            except json.JSONDecodeError:
                pass

        if not steps and not final_result:
            logger.error("Agent run %s produced no output", agent_run_id)

        async with AsyncSessionLocal() as db:
            for step in steps:
                db.add(AgentRunLog(
                    agent_run_id=agent_run_id,
                    step=step.get("step", 0),
                    url=step.get("url"),
                    action_type=step.get("action_type"),
                    action_params=step.get("action_params"),
                    thought=step.get("thought"),
                    evaluation=step.get("evaluation"),
                    memory=step.get("memory"),
                    extracted_content=step.get("extracted_content"),
                    success=step.get("success"),
                    error=step.get("error"),
                    step_start_time=step.get("step_start_time"),
                    step_end_time=step.get("step_end_time"),
                    duration_seconds=step.get("duration_seconds"),
                ))

            result = await db.execute(select(AgentRun).where(AgentRun.id == agent_run_id))
            agent_run = result.scalar_one_or_none()
            if agent_run:
                success = bool(final_result and final_result.get("success"))
                agent_run.status = AgentRunStatus.COMPLETE if success else AgentRunStatus.ERROR
                agent_run.result = final_result.get("result") if final_result else None
                agent_run.completed_at = datetime.now(timezone.utc)
            await db.commit()

    except Exception:
        logger.exception("_run_single_agent failed for run=%s", agent_run_id)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(AgentRun).where(AgentRun.id == agent_run_id))
            agent_run = result.scalar_one_or_none()
            if agent_run:
                agent_run.status = AgentRunStatus.ERROR
                agent_run.completed_at = datetime.now(timezone.utc)
            await db.commit()
