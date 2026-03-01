"""
Shared test fixtures.

Unit tests (auth pure functions, SSEBus) run without any real DB or network.
Integration tests that need a DB should use a Neon branch or a local Postgres;
they can override `get_db` via FastAPI's dependency_overrides mechanism.
"""
import os
import pytest

from app.config import get_settings


# ---------------------------------------------------------------------------
# Settings override
# ---------------------------------------------------------------------------

TEST_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
    "SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256",
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "OPENROUTER_API_KEY": "test-openrouter-key",
    "ENVIRONMENT": "test",
}


@pytest.fixture(autouse=True)
def override_settings(monkeypatch):
    """Inject test environment variables and clear the settings LRU cache."""
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
