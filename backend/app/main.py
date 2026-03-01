from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, sessions, messages, internal


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


settings = get_settings()

app = FastAPI(
    title="Browser Agent Command Center",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(messages.router, prefix="/sessions", tags=["messages"])
app.include_router(internal.router, prefix="/internal", tags=["internal"])


@app.get("/health")
async def health():
    return {"status": "ok"}
