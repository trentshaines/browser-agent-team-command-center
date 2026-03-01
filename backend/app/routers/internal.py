import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services import sse

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentFrameData(BaseModel):
    session_id: str = Field(..., max_length=36)
    agent_id: str = Field(..., max_length=36)
    step: int | None = Field(None, ge=0, le=10_000)
    url: str | None = Field(None, max_length=2048)
    screenshot: str | None = Field(None, max_length=500_000)  # ~375 KB base64 limit


async def verify_internal_token(x_internal_token: Annotated[str, Header()] = "") -> None:
    settings = get_settings()
    if settings.internal_api_token and x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/agent-frame")
async def agent_frame(
    data: AgentFrameData,
    _: Annotated[None, Depends(verify_internal_token)],
) -> dict:
    await sse.publish(data.session_id, "agent_frame", {
        "agent_id": data.agent_id,
        "step": data.step,
        "url": data.url,
        "screenshot": data.screenshot,
    })
    return {"ok": True}
