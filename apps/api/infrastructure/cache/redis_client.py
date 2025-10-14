import os
import redis
from django.conf import settings

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            getattr(settings, "REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        )
    return _pool


def get_client():
    return redis.Redis(connection_pool=get_pool())


def publish(channel: str, message: str):
    get_client().publish(channel, message)
