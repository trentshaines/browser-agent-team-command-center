import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=32_000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message content cannot be blank")
        return v


class MessageRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
