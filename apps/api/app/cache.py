from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator

import redis.asyncio as redis

from .config import get_settings


@lru_cache(maxsize=1)
def _get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)


def get_redis_client() -> redis.Redis:
    return _get_redis_client()


async def get_redis() -> AsyncIterator[redis.Redis]:
    client = _get_redis_client()
    try:
        yield client
    finally:
        # connection pool handled by redis client, no immediate close required
        pass
