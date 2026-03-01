import logging
import uuid
from typing import Annotated

import sentry_sdk
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models.agent_run import AgentRun
from app.models.message import Message
from app.models.session import Session
from app.routers.sessions import get_owned_session
from app.schemas.message import MessageCreate, MessageRead
from app.services import sse
from app.services.orchestrator import run_turn

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{session_id}/messages", response_model=list[MessageRead])
async def list_messages(
    session_id: uuid.UUID,
    _session: Annotated[Session, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return result.scalars().all()


@router.post("/{session_id}/messages", response_model=MessageRead)
async def send_message(
    session_id: uuid.UUID,
    data: MessageCreate,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Fetch existing history BEFORE inserting new messages
    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    existing_messages = history_result.scalars().all()

    # Save user message
    user_msg = Message(session_id=session_id, role="user", content=data.content)
    db.add(user_msg)

    # Create placeholder assistant message
    assistant_msg = Message(session_id=session_id, role="assistant", content="")
    db.add(assistant_msg)
    await db.flush()

    # Auto-title session from first message (use stripped content)
    if session.title == "New Chat":
        stripped = data.content.strip()
        session.title = stripped[:60] + ("..." if len(stripped) > 60 else "")

    assistant_msg_id = assistant_msg.id

    # Commit immediately so the connection is released before background task starts.
    # Without this, get_db cleanup may fail (especially with Neon pooler) and
    # prevent the background task from running.
    await db.commit()

    # Build conversation history in-memory (no second DB query needed)
    history = [
        {"role": m.role, "content": m.content}
        for m in existing_messages
        if m.content  # skip empty placeholders
    ]
    history.append({"role": "user", "content": data.content})

    logger.info("Registering orchestrator background task for session %s, message %s", session_id, assistant_msg_id)

    async def run_orchestrator():
        logger.info("Background orchestrator started for session %s, message %s", session_id, assistant_msg_id)
        async with AsyncSessionLocal() as bg_db:
            try:
                await run_turn(
                    session_id=session_id,
                    assistant_message_id=assistant_msg_id,
                    history=history,
                    db=bg_db,
                )
                await bg_db.commit()
            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.exception("Orchestrator failed for session %s", session_id)
                error_text = f"_Something went wrong: {exc}_"
                # Persist error into the assistant message so it's visible after reload
                try:
                    result = await bg_db.execute(
                        select(Message).where(Message.id == assistant_msg_id)
                    )
                    msg = result.scalar_one_or_none()
                    if msg:
                        msg.content = error_text
                    await bg_db.commit()
                except Exception:
                    logger.exception("Failed to persist error message")
                    await bg_db.rollback()
                await sse.publish(str(session_id), "error_event", {
                    "message_id": str(assistant_msg_id),
                    "error": str(exc),
                })

    background_tasks.add_task(run_orchestrator)

    return assistant_msg


@router.get("/{session_id}/agent-runs")
async def list_agent_runs(
    session_id: uuid.UUID,
    _session: Annotated[Session, Depends(get_owned_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.session_id == session_id)
        .order_by(AgentRun.created_at)
        .options(selectinload(AgentRun.logs))
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "task": r.task,
            "status": r.status,
            "result": r.result,
            "total_steps": len(r.logs),
            "steps": [
                {
                    "step": log.step,
                    "url": log.url,
                    "action_type": log.action_type,
                    "thought": log.thought,
                    "evaluation": log.evaluation,
                    "success": log.success,
                    "extracted_content": log.extracted_content,
                    "error": log.error,
                }
                for log in sorted(r.logs, key=lambda l: l.step)
            ],
        }
        for r in runs
    ]


@router.get("/{session_id}/stream")
async def stream_session(
    session_id: uuid.UUID,
    request: Request,
    _session: Annotated[Session, Depends(get_owned_session)],
):
    return StreamingResponse(
        sse.stream(str(session_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
