from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, Tuple

import httpx
from jose import JWTError, jwt
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import User
from ..utils import utc_now, verify_password
from .factories import SessionFactory, TokenFactory


@dataclass(slots=True)
class Credentials:
    """Credentials payload passed to authentication strategies."""

    provider: str
    token: Optional[str] = None
    code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthStrategy(Protocol):
    """Protocol for authentication strategies."""

    async def authenticate(
        self,
        session: AsyncSession,
        redis: Redis,
        creds: Credentials,
    ) -> Tuple[bool, Dict[str, Any]]:
        ...

    async def validate_token(
        self,
        session: AsyncSession,
        redis: Redis,
        token: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        ...

    async def refresh_token(
        self,
        session: AsyncSession,
        redis: Redis,
        refresh_token: str,
    ) -> Tuple[bool, Optional[str]]:
        ...

    async def revoke_token(
        self,
        session: AsyncSession,
        redis: Redis,
        token: str,
    ) -> bool:
        ...


class OIDCStrategy:
    """Authenticate users using an external OIDC provider."""

    async def authenticate(
        self,
        session: AsyncSession,
        redis: Redis,
        creds: Credentials,
    ) -> Tuple[bool, Dict[str, Any]]:
        if not creds.code:
            return (False, {"error": "authorization_code_required"})

        settings = get_settings()
        if not settings.oidc_issuer or not settings.oidc_client_id:
            return (False, {"error": "oidc_not_configured"})

        async with httpx.AsyncClient(timeout=10) as client:
            discovery_resp = await client.get(
                f"{settings.oidc_issuer}/.well-known/openid-configuration"
            )
            discovery_resp.raise_for_status()
            discovery = discovery_resp.json()

            token_resp = await client.post(
                discovery["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": creds.code,
                    "redirect_uri": creds.metadata.get("redirect_uri", settings.oidc_redirect_uri),
                    "client_id": settings.oidc_client_id,
                    "client_secret": settings.oidc_client_secret,
                    "code_verifier": creds.metadata.get("code_verifier", ""),
                },
            )
            if token_resp.status_code != 200:
                return (
                    False,
                    {
                        "error": "token_exchange_failed",
                        "details": token_resp.text,
                    },
                )

            tokens = token_resp.json()
            id_token = tokens.get("id_token")
            if not id_token:
                return (False, {"error": "id_token_missing"})

            claims = jwt.decode(
                id_token,
                options={"verify_signature": False},
                audience=settings.oidc_client_id,
            )

            return (
                True,
                {
                    "id": claims.get("sub"),
                    "email": claims.get("email"),
                    "name": claims.get("name"),
                    "access_token": tokens.get("access_token"),
                    "refresh_token": tokens.get("refresh_token"),
                    "expires_in": tokens.get("expires_in", 3600),
                    "claims": claims,
                },
            )

    async def validate_token(
        self,
        session: AsyncSession,
        redis: Redis,
        token: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        # Validation is delegated to the issuer; for now assume valid when provided
        return True, {"token": token}

    async def refresh_token(
        self,
        session: AsyncSession,
        redis: Redis,
        refresh_token: str,
    ) -> Tuple[bool, Optional[str]]:
        settings = get_settings()
        if not settings.oidc_issuer or not settings.oidc_client_id:
            return (False, None)
        async with httpx.AsyncClient(timeout=10) as client:
            discovery_resp = await client.get(
                f"{settings.oidc_issuer}/.well-known/openid-configuration"
            )
            discovery_resp.raise_for_status()
            discovery = discovery_resp.json()

            token_resp = await client.post(
                discovery["token_endpoint"],
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": settings.oidc_client_id,
                    "client_secret": settings.oidc_client_secret,
                },
            )
            if token_resp.status_code != 200:
                return (False, None)
            data = token_resp.json()
            return True, data.get("access_token")

    async def revoke_token(
        self,
        session: AsyncSession,
        redis: Redis,
        token: str,
    ) -> bool:
        # Rely on JWT strategy for revocation. OIDC revocation could call endpoint.
        return True


class JWTStrategy:
    """Authenticate users using JWT tokens managed internally."""

    async def authenticate(
        self,
        session: AsyncSession,
        redis: Redis,
        creds: Credentials,
    ) -> Tuple[bool, Dict[str, Any]]:
        user_id = creds.metadata.get("user_id")
        if not user_id:
            return (False, {"error": "user_id_required"})

        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return (False, {"error": "user_not_found"})

        settings = get_settings()
        access_payload = {
            "email": user.email,
            "roles": list(user.roles),
        }
        refresh_payload: Dict[str, Any] = {}

        access_token = TokenFactory.access_token(str(user.id), access_payload)
        refresh_token = TokenFactory.refresh_token(str(user.id), refresh_payload)

        session_data = SessionFactory.user_session(
            str(user.id),
            {
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "roles": list(user.roles),
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            },
        )

        ttl_access = settings.access_token_ttl_minutes * 60
        ttl_refresh = settings.refresh_token_ttl_minutes * 60

        await redis.setex(
            f"session:{user.id}", ttl_refresh, json.dumps(session_data)
        )
        await redis.setex(
            f"refresh:{refresh_token}", ttl_refresh, str(user.id)
        )

        return (
            True,
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": ttl_access,
                "user": session_data,
            },
        )

    async def validate_token(
        self,
        session: AsyncSession,
        redis: Redis,
        token: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=["HS256"],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
            )
        except JWTError:
            return (False, None)

        if payload.get("scope") != "access":
            return (False, None)

        jti = payload.get("jti")
        if jti and await redis.get(f"blacklist:{jti}"):
            return (False, None)

        session_raw = await redis.get(f"session:{payload.get('sub')}")
        if not session_raw:
            return (False, None)
        session_data = json.loads(session_raw)

        return True, {"claims": payload, "user": session_data}

    async def refresh_token(
        self,
        session: AsyncSession,
        redis: Redis,
        refresh_token: str,
    ) -> Tuple[bool, Optional[str]]:
        settings = get_settings()
        stored_user_id = await redis.get(f"refresh:{refresh_token}")
        if not stored_user_id:
            return (False, None)

        try:
            payload = jwt.decode(
                refresh_token,
                settings.secret_key,
                algorithms=["HS256"],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
            )
        except JWTError:
            return (False, None)

        if payload.get("scope") != "refresh":
            return (False, None)

        result = await session.execute(select(User).where(User.id == stored_user_id))
        user = result.scalar_one_or_none()
        if not user:
            return (False, None)

        access_payload = {
            "email": user.email,
            "roles": list(user.roles),
        }
        new_access_token = TokenFactory.access_token(str(user.id), access_payload)

        ttl_access = settings.access_token_ttl_minutes * 60
        session_raw = await redis.get(f"session:{user.id}")
        if not session_raw:
            session_data = SessionFactory.user_session(
                str(user.id),
                {
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "roles": list(user.roles),
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                },
            )
            await redis.setex(
                f"session:{user.id}", settings.refresh_token_ttl_minutes * 60, json.dumps(session_data)
            )

        return True, new_access_token

    async def revoke_token(
        self,
        session: AsyncSession,
        redis: Redis,
        token: str,
    ) -> bool:
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=["HS256"],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
            )
        except JWTError:
            return False

        jti = payload.get("jti")
        if not jti:
            return False

        ttl = payload.get("exp", int(utc_now().timestamp())) - int(utc_now().timestamp())
        ttl = max(ttl, 0)
        await redis.setex(f"blacklist:{jti}", ttl, "1")
        return True


class LocalStrategy:
    """Authenticate users with local credentials and reuse JWT issuance."""

    def __init__(self, delegate: Optional[JWTStrategy] = None) -> None:
        self.delegate = delegate or JWTStrategy()

    async def authenticate(
        self,
        session: AsyncSession,
        redis: Redis,
        creds: Credentials,
    ) -> Tuple[bool, Dict[str, Any]]:
        email = creds.metadata.get("email") or creds.metadata.get("username")
        password = creds.metadata.get("password")
        if not email or not password:
            return (False, {"error": "email_and_password_required"})

        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            return (False, {"error": "user_not_found"})
        if not user.is_active:
            return (False, {"error": "user_inactive"})
        if not verify_password(password, user.password_hash):
            return (False, {"error": "invalid_credentials"})

        creds.metadata["user_id"] = str(user.id)
        return await self.delegate.authenticate(session, redis, creds)

    async def validate_token(
        self,
        session: AsyncSession,
        redis: Redis,
        token: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        return await self.delegate.validate_token(session, redis, token)

    async def refresh_token(
        self,
        session: AsyncSession,
        redis: Redis,
        refresh_token: str,
    ) -> Tuple[bool, Optional[str]]:
        return await self.delegate.refresh_token(session, redis, refresh_token)

    async def revoke_token(
        self,
        session: AsyncSession,
        redis: Redis,
        token: str,
    ) -> bool:
        return await self.delegate.revoke_token(session, redis, token)
