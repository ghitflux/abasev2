from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.manager import AuthenticationManager
from ..auth.strategies import Credentials
from ..cache import get_redis
from ..config import get_settings
from ..dependencies.auth import get_current_user, oauth2_scheme
from ..dependencies.db import get_db_session
from ..schemas import LoginRequest, RefreshRequest, TokenResponse, UserRead

router = APIRouter()
auth_manager = AuthenticationManager()


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
    global_logout: bool = False


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    metadata: dict[str, Any] = payload.metadata or {}
    provider = payload.provider
    if (
        provider == "oidc"
        and payload.username
        and payload.password
    ):
        provider = "local"

    if provider == "local":
        metadata.setdefault("email", payload.username)
        metadata.setdefault("password", payload.password)
    elif provider == "oidc":
        if payload.redirect_uri:
            metadata["redirect_uri"] = payload.redirect_uri

    creds = Credentials(
        provider=provider,
        code=payload.code,
        metadata=metadata,
        token=None,
    )
    try:
        result = await auth_manager.authenticate(session=session, redis=redis, creds=creds)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return TokenResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    user_id = await redis.get(f"refresh:{payload.refresh_token}")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh_invalid")

    new_access = await auth_manager.refresh_token(
        payload.provider, payload.refresh_token, session=session, redis=redis
    )
    if not new_access:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh_failed")

    settings = get_settings()
    expires_in = settings.access_token_ttl_minutes * 60
    user_payload: dict[str, Any] = {}
    session_raw = await redis.get(f"session:{user_id}")
    if session_raw:
        user_payload = json.loads(session_raw)

    return TokenResponse(
        access_token=new_access,
        refresh_token=payload.refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=user_payload,
    )


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> dict[str, str]:
    decoded = await auth_manager.validate_token(
        "jwt", token, session=session, redis=redis
    )
    await auth_manager.revoke_token("jwt", token, session=session, redis=redis)

    if payload.refresh_token:
        await redis.delete(f"refresh:{payload.refresh_token}")

    if payload.global_logout and decoded:
        claims = decoded.get("claims") or {}
        sub = claims.get("sub")
        if sub:
            await redis.delete(f"session:{sub}")

    return {"status": "logged_out"}


@router.get("/me", response_model=UserRead)
async def me(current_user: UserRead = Depends(get_current_user)) -> UserRead:
    return current_user
