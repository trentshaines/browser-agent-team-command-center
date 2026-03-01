import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = Field("New Chat", min_length=1, max_length=200)


class SessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class SessionRead(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
