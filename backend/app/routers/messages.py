import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
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
    # Save user message
    user_msg = Message(session_id=session_id, role="user", content=data.content)
    db.add(user_msg)

    # Create placeholder assistant message
    assistant_msg = Message(session_id=session_id, role="assistant", content="")
    db.add(assistant_msg)
    await db.flush()

    # Auto-title session from first message
    if session.title == "New Chat":
        session.title = data.content[:60] + ("..." if len(data.content) > 60 else "")

    assistant_msg_id = assistant_msg.id

    # Build conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .where(Message.id != assistant_msg_id)
        .order_by(Message.created_at)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
        if m.content  # skip empty placeholders
    ]

    async def run_orchestrator():
        async with AsyncSessionLocal() as bg_db:
            try:
                await run_turn(
                    session_id=session_id,
                    assistant_message_id=assistant_msg_id,
                    history=history,
                    db=bg_db,
                )
                await bg_db.commit()
            except Exception:
                logger.exception("Orchestrator failed for session %s", session_id)
                await bg_db.rollback()
                await sse.publish(str(session_id), "error_event", {"message_id": str(assistant_msg_id)})

    background_tasks.add_task(run_orchestrator)

    return assistant_msg


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
