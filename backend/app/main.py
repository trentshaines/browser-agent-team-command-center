from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import get_settings
from app.routers import auth, sessions, messages, internal

settings = get_settings()

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os
    s = get_settings()

    # Configure Bedrock environment when llm_provider is set to "bedrock"
    if s.llm_provider == "bedrock":
        os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
        os.environ["AWS_REGION"] = s.aws_region
        # Pin model versions to prevent breakage on new releases
        os.environ.setdefault("ANTHROPIC_MODEL", s.anthropic_model)
        os.environ.setdefault("ANTHROPIC_SMALL_FAST_MODEL", s.anthropic_small_fast_model)

    if s.aws_bearer_token_bedrock:
        os.environ.setdefault("AWS_BEARER_TOKEN_BEDROCK", s.aws_bearer_token_bedrock)
    yield


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


@app.get("/sentry-test")
async def sentry_test():
    raise RuntimeError("Sentry test error — ignore this")
