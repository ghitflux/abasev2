from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from .config import get_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """Hash a password for storing."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hashed value."""
    return pwd_context.verify(password, hashed)


def generate_token(payload: dict[str, Any], expires_in_seconds: int) -> str:
    """Generate a JWT token with the provided payload."""
    settings = get_settings()
    to_encode = payload.copy()
    now = utc_now()
    to_encode.setdefault("iat", int(now.timestamp()))
    to_encode.setdefault("exp", int((now.timestamp()) + expires_in_seconds))
    to_encode.setdefault("iss", settings.jwt_issuer)
    to_encode.setdefault("aud", settings.jwt_audience)
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def generate_refresh_token() -> str:
    """Return a secure random string for refresh tokens."""
    return secrets.token_urlsafe(48)
