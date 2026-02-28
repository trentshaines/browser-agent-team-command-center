import uuid
from datetime import datetime
from pydantic import BaseModel


class AgentRunRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    message_id: uuid.UUID
    task: str
    status: str
    result: str | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
