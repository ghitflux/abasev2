from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.manager import AuthenticationManager
from ..auth.strategies import Credentials
from ..cache import get_redis
from .db import get_db_session
from ..schemas.user import UserRead

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", scopes={})
auth_manager = AuthenticationManager()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> UserRead:
    """Validate JWT access token and return the current user."""
    payload = await auth_manager.validate_token("jwt", token, session=session, redis=redis)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    user_data = payload.get("user")
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_payload")
    return UserRead(**user_data)


async def get_current_active_user(
    security_scopes: SecurityScopes,
    user: UserRead = Depends(get_current_user),
) -> UserRead:
    """Ensure the current user is active and has required scopes."""
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="inactive_user")
    return user


async def authenticate_user(
    credentials: Credentials,
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> dict[str, object]:
    """Helper dependency for authenticating via strategy manager."""
    return await auth_manager.authenticate(session=session, redis=redis, creds=credentials)
