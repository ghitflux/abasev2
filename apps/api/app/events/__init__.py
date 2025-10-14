from __future__ import annotations

import asyncio
import json
from typing import Any, Dict
from uuid import uuid4

from fastapi_sse import SSEApp

from ..cache import get_redis_client
from ..config import get_settings
from .websocket import manager


sse_app = SSEApp()
_settings = get_settings()
_channel = f"{_settings.sse_channel_prefix}:broadcast"
_instance_id = uuid4().hex
_listener_task: asyncio.Task[None] | None = None


async def start_event_listener() -> None:
    global _listener_task  # noqa: PLW0603
    if _listener_task and not _listener_task.done():
        return

    async def _listen() -> None:
        redis = get_redis_client()
        pubsub = redis.pubsub()
        await pubsub.subscribe(_channel)
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                payload = json.loads(message["data"])
            except (TypeError, json.JSONDecodeError):
                continue
            if payload.get("origin") == _instance_id:
                continue
            await _dispatch(payload)

    _listener_task = asyncio.create_task(_listen())


async def publish_event(channel: str, data: Dict[str, Any], event: str | None = None) -> None:
    payload = {"channel": channel, "data": data, "event": event, "origin": _instance_id}
    redis = get_redis_client()
    await redis.publish(_channel, json.dumps(payload))
    await _dispatch(payload)


async def _dispatch(payload: Dict[str, Any]) -> None:
    channel = payload["channel"]
    data = payload["data"]
    event = payload.get("event")
    await sse_app.publish(data=json.dumps(data), event=event, channel=channel)
    await manager.broadcast({"channel": channel, "data": data, "event": event})
