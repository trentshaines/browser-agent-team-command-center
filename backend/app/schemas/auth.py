from pydantic import BaseModel
import uuid


class GoogleAuthRequest(BaseModel):
    code: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    profile_image: str | None
    is_admin: bool

    model_config = {"from_attributes": True}
