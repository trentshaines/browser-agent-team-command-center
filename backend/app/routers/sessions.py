import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.session import Session
from app.models.user import User
from app.routers.auth import get_current_user_required
from app.schemas.session import SessionCreate, SessionRead, SessionUpdate

router = APIRouter()


@router.get("", response_model=list[SessionRead])
async def list_sessions(
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(desc(Session.updated_at))
    )
    return result.scalars().all()


@router.post("", response_model=SessionRead)
async def create_session(
    data: SessionCreate,
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    session = Session(user_id=user.id, title=data.title)
    db.add(session)
    await db.flush()
    return session


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.title = data.title
    return session


@router.delete("/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user_required)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    return {"ok": True}
