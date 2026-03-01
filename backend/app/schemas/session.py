import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class SessionCreate(BaseModel):
    title: str = Field("New Chat", min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def title_strip(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            return "New Chat"
        return stripped


class SessionUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def title_strip(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Session title cannot be blank")
        return stripped


class SessionRead(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
