from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict
from uuid import uuid4

from jose import jwt

from ..config import get_settings
from ..utils import utc_now


class TokenFactory:
    """Factory responsible for generating signed JWT tokens."""

    @staticmethod
    def _common_claims(subject: str, scope: str) -> Dict[str, Any]:
        settings = get_settings()
        now = utc_now()
        return {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": subject,
            "scope": scope,
            "iat": int(now.timestamp()),
            "jti": uuid4().hex,
        }

    @classmethod
    def access_token(cls, subject: str, data: Dict[str, Any]) -> str:
        settings = get_settings()
        expires = utc_now() + timedelta(minutes=settings.access_token_ttl_minutes)
        payload = {**cls._common_claims(subject, "access"), **data, "exp": int(expires.timestamp())}
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")

    @classmethod
    def refresh_token(cls, subject: str, data: Dict[str, Any]) -> str:
        settings = get_settings()
        expires = utc_now() + timedelta(minutes=settings.refresh_token_ttl_minutes)
        payload = {**cls._common_claims(subject, "refresh"), **data, "exp": int(expires.timestamp())}
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")


class SessionFactory:
    """Factory for building session payloads stored in Redis."""

    @staticmethod
    def user_session(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        session = {"user_id": user_id, "id": user_id, **payload}
        session.setdefault("roles", [])
        return session
