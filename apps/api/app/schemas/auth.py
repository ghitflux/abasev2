from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    provider: str = Field(default="oidc")
    code: str | None = None
    username: str | None = None
    password: str | None = None
    redirect_uri: str | None = None
    metadata: dict[str, str] | None = None


class RefreshRequest(BaseModel):
    refresh_token: str
    provider: str = Field(default="jwt")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict[str, object]
