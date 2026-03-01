from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str

    # Auth
    secret_key: str
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    auth_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"
    cookie_secure: bool = False  # Set True in production (COOKIE_SECURE=true)
    cookie_samesite: str = "lax"  # Use "none" in production for cross-domain (requires cookie_secure=true)
    cookie_domain: str | None = None

    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:5173/auth/callback/google"

    # Claude / LLM
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    browser_agent_model: str = "google/gemini-2.0-flash-001"

    # AWS Bedrock
    aws_region: str = "us-east-1"
    aws_bearer_token_bedrock: str = ""
    llm_provider: str = ""  # set to "bedrock" to force Bedrock for the orchestrator

    # Internal API
    internal_api_token: str = ""  # Set to a strong random secret in production

    # Observability
    sentry_dsn: str = ""

    # App
    frontend_url: str = "http://localhost:5173"
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
