import logging
import uuid
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import GoogleAuthRequest, RefreshTokenRequest, Token, UserRead
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    exchange_google_code,
    get_user_by_email,
    get_user_by_google_id,
    get_user_by_id,
    get_user_by_username,
    create_user,
)

router = APIRouter()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.auth_cookie_name, path="/")
    response.delete_cookie(key=settings.refresh_cookie_name, path="/")


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return await get_user_by_id(db, uuid.UUID(user_id))


async def get_current_user_required(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


@router.get("/google")
async def google_auth_redirect():
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@router.post("/google", response_model=Token)
async def google_auth(
    request: Request,
    data: GoogleAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        google_user = await exchange_google_code(data.code)
    except httpx.HTTPError as e:
        logger.warning("Google OAuth code exchange failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid Google auth code")

    google_id = google_user.get("id")
    email = google_user.get("email")
    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Could not get user info from Google")

    user = await get_user_by_google_id(db, google_id)
    if not user:
        user = await get_user_by_email(db, email)
        if user:
            user.google_id = google_id
            user.email_verified = True
        else:
            base = email.split("@")[0][:40]
            username = base
            counter = 1
            while await get_user_by_username(db, username):
                username = f"{base}{counter}"
                counter += 1
            user = await create_user(db=db, email=email, username=username, google_id=google_id, email_verified=True)
            picture = google_user.get("picture", "")
            if picture and picture.startswith("https://"):
                user.profile_image = picture

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    response = JSONResponse(content=Token(access_token=access_token, refresh_token=refresh_token).model_dump())
    set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/refresh")
async def refresh_tokens(
    request: Request,
    data: RefreshTokenRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token and data:
        token = data.refresh_token
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    response = JSONResponse(content=Token(access_token=access_token, refresh_token=new_refresh).model_dump())
    set_auth_cookies(response, access_token, new_refresh)
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "Logged out"})
    clear_auth_cookies(response)
    return response


@router.get("/me", response_model=UserRead)
async def get_me(user: Annotated[User, Depends(get_current_user_required)]):
    return user
