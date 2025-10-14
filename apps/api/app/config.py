from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="")

    app_name: str = "ABASE Manager API"
    version: str = "2.0.0"
    environment: Literal["development", "production", "test"] = "development"

    database_url: Annotated[
        str,
        Field(
            default="postgresql+asyncpg://abase:localpass@postgres:5432/abase_v2",
            alias="DATABASE_URL",
        ),
    ]
    redis_url: Annotated[
        str,
        Field(default="redis://redis:6379/0", alias="REDIS_URL"),
    ]

    secret_key: str = Field(default="super-secret-key-change-me", alias="SECRET_KEY", min_length=16)
    jwt_audience: str = "abase-api"
    jwt_issuer: str = "abase-manager"
    access_token_ttl_minutes: int = Field(default=15, ge=1)
    refresh_token_ttl_minutes: int = Field(default=60 * 24 * 7, ge=60)

    oidc_client_id: str | None = Field(default=None, alias="OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(default=None, alias="OIDC_CLIENT_SECRET")
    oidc_issuer: str | None = Field(default=None, alias="OIDC_ISSUER")
    oidc_redirect_uri: str | None = Field(default=None, alias="OIDC_REDIRECT_URI")

    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")

    sse_channel_prefix: str = "sse"
    websocket_channel_prefix: str = "ws"

    def postgres_dsn(self) -> PostgresDsn:
        """Return a validated Postgres DSN string."""
        try:
            return PostgresDsn(self.database_url)
        except ValidationError as exc:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL DSN") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()  # type: ignore[call-arg]
