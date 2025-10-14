from __future__ import annotations

from typing import AsyncIterator

from ..db import get_session


async def get_db_session():
    """Alias dependency for database session."""
    async for session in get_session():
        yield session
