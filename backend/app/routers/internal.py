import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services import sse, agent_registry

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentFrameData(BaseModel):
    session_id: str = Field(..., max_length=36)
    agent_id: str = Field(..., max_length=36)
    step: int | None = Field(None, ge=0, le=10_000)
    url: str | None = Field(None, max_length=2048)
    screenshot: str | None = Field(None, max_length=500_000)  # ~375 KB base64 limit


class AgentEventData(BaseModel):
    session_id: str = Field(..., max_length=36)
    type: str = Field(..., max_length=32)
    agent_id: str = Field(..., max_length=36)
    task: str | None = Field(None, max_length=4096)
    # log fields
    step: int | None = Field(None, ge=0, le=10_000)
    url: str | None = Field(None, max_length=2048)
    action_type: str | None = Field(None, max_length=128)
    action_params: dict | None = None
    thought: str | None = Field(None, max_length=4096)
    evaluation: str | None = Field(None, max_length=4096)
    memory: str | None = Field(None, max_length=4096)
    extracted_content: str | None = Field(None, max_length=8192)
    success: bool | None = None
    error: str | None = Field(None, max_length=2048)
    # complete fields
    result: str | None = Field(None, max_length=8192)
    total_steps: int | None = None


async def verify_internal_token(x_internal_token: Annotated[str, Header()] = "") -> None:
    settings = get_settings()
    if settings.internal_api_token and x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=403, detail="Forbidden")


class AgentClaimRequest(BaseModel):
    session_id: str = Field(..., max_length=36)


@router.post("/agent-claim")
async def agent_claim(
    data: AgentClaimRequest,
    _: Annotated[None, Depends(verify_internal_token)],
) -> dict:
    agent_run_id = await agent_registry.claim(data.session_id)
    return {"agent_run_id": agent_run_id}


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


@router.post("/agent-event")
async def agent_event(
    data: AgentEventData,
    _: Annotated[None, Depends(verify_internal_token)],
) -> dict:
    if data.type == "agent_spawned":
        await sse.publish(data.session_id, "agent_event", {
            "type": "agent_spawned",
            "agent_id": data.agent_id,
            "task": data.task,
        })
    elif data.type == "agent_log":
        await sse.publish(data.session_id, "agent_log", {
            "agent_run_id": data.agent_id,
            "step": data.step,
            "url": data.url,
            "action_type": data.action_type,
            "action_params": data.action_params,
            "thought": data.thought,
            "evaluation": data.evaluation,
            "memory": data.memory,
            "extracted_content": data.extracted_content,
            "success": data.success,
            "error": data.error,
        })
    elif data.type == "agent_complete":
        await sse.publish(data.session_id, "agent_event", {
            "type": "agent_complete",
            "agent_run_id": data.agent_id,
            "result": data.result,
            "total_steps": data.total_steps,
        })
    return {"ok": True}
