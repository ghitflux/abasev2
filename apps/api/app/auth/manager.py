from __future__ import annotations

from typing import Any, Dict

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..utils import hash_password
from .strategies import (
    AuthStrategy,
    Credentials,
    JWTStrategy,
    LocalStrategy,
    OIDCStrategy,
)


class AuthenticationManager:
    """Singleton-style manager that orchestrates authentication strategies."""

    _instance: "AuthenticationManager | None" = None

    def __new__(cls) -> "AuthenticationManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        jwt_strategy = JWTStrategy()
        self._strategies: Dict[str, AuthStrategy] = {
            "oidc": OIDCStrategy(),
            "jwt": jwt_strategy,
            "local": LocalStrategy(jwt_strategy),
        }

    def get_strategy(self, name: str) -> AuthStrategy:
        try:
            return self._strategies[name]
        except KeyError as exc:
            raise ValueError(f"Strategy '{name}' is not registered") from exc

    async def authenticate(
        self,
        session: AsyncSession,
        redis: Redis,
        creds: Credentials,
    ) -> Dict[str, Any]:
        strategy = self.get_strategy(creds.provider)
        success, payload = await strategy.authenticate(session, redis, creds)
        if not success:
            raise ValueError(payload.get("error", "authentication_failed"))

        if creds.provider == "oidc":
            user = await self._get_or_create_user(session, payload)
            session_payload = await self._issue_tokens(session, redis, user)
            return {**payload, **session_payload}

        return payload

    async def validate_token(
        self,
        provider: str,
        token: str,
        session: AsyncSession,
        redis: Redis,
    ) -> Dict[str, Any] | None:
        strategy = self.get_strategy(provider)
        success, payload = await strategy.validate_token(session, redis, token)
        return payload if success else None

    async def refresh_token(
        self,
        provider: str,
        refresh_token: str,
        session: AsyncSession,
        redis: Redis,
    ) -> str | None:
        strategy = self.get_strategy(provider)
        success, token = await strategy.refresh_token(session, redis, refresh_token)
        return token if success else None

    async def revoke_token(
        self,
        provider: str,
        token: str,
        session: AsyncSession,
        redis: Redis,
    ) -> bool:
        strategy = self.get_strategy(provider)
        return await strategy.revoke_token(session, redis, token)

    async def _issue_tokens(
        self,
        session: AsyncSession,
        redis: Redis,
        user: User,
    ) -> Dict[str, Any]:
        creds = Credentials(provider="jwt", metadata={"user_id": str(user.id)})
        strategy = self.get_strategy("jwt")
        success, payload = await strategy.authenticate(session, redis, creds)
        if not success:
            raise ValueError(payload.get("error", "jwt_issue_failed"))
        return payload

    async def _get_or_create_user(
        self,
        session: AsyncSession,
        payload: Dict[str, Any],
    ) -> User:
        email = payload.get("email")
        if not email:
            raise ValueError("email_required_for_oidc")

        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            return user

        user = User(
            email=email,
            full_name=payload.get("name", ""),
            password_hash=hash_password(email + "@oauth"),
            roles=["AGENTE"],
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
