from fastapi import APIRouter
from app.services import sse

router = APIRouter()


@router.post("/agent-frame")
async def agent_frame(data: dict):
    await sse.publish(data["session_id"], "agent_frame", {
        "agent_id": data["agent_id"],
        "step": data.get("step"),
        "url": data.get("url"),
        "screenshot": data.get("screenshot"),
    })
    return {"ok": True}
