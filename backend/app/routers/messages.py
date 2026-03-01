import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, AsyncSessionLocal
from app.models.message import Message
from app.models.session import Session
from app.models.user import User
from app.routers.auth import get_current_user_required
from app.schemas.message import MessageCreate, MessageRead
from app.services import sse
from app.services.orchestrator import run_turn

router = APIRouter()


@router.get("/{session_id}/messages", response_model=list[MessageRead])
async def list_messages(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify session belongs to user
    s = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == user.id))
    if not s.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return result.scalars().all()


@router.post("/{session_id}/messages", response_model=MessageRead)
async def send_message(
    session_id: uuid.UUID,
    data: MessageCreate,
    background_tasks: BackgroundTasks,
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify session
    s_result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = s_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

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

    user_msg_id = user_msg.id
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

    # Kick off orchestrator in background with its own DB session
    async def run_orchestrator():
        async with AsyncSessionLocal() as bg_db:
            await run_turn(
                session_id=session_id,
                assistant_message_id=assistant_msg_id,
                history=history,
                db=bg_db,
            )
            await bg_db.commit()

    background_tasks.add_task(run_orchestrator)

    return assistant_msg


@router.get("/{session_id}/stream")
async def stream_session(
    session_id: uuid.UUID,
    request: Request,
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify session belongs to user
    s = await db.execute(select(Session).where(Session.id == session_id, Session.user_id == user.id))
    if not s.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamingResponse(
        sse.stream(str(session_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
