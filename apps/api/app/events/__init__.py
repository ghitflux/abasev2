from __future__ import annotations

import asyncio
import json
from typing import Any, Dict
from uuid import uuid4

from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse

from ..cache import get_redis_client
from ..config import get_settings
from .websocket import manager


# Create a simple FastAPI app for SSE endpoints
sse_app = FastAPI()
_settings = get_settings()
_channel = f"{_settings.sse_channel_prefix}:broadcast"
_instance_id = uuid4().hex
_listener_task: asyncio.Task[None] | None = None

# Store active SSE connections
_sse_connections: Dict[str, asyncio.Queue] = {}


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
    
    # Send to SSE connections
    for connection_id, queue in _sse_connections.items():
        try:
            await queue.put({
                "data": json.dumps(data),
                "event": event or "message",
                "channel": channel
            })
        except Exception:
            # Remove dead connections
            _sse_connections.pop(connection_id, None)
    
    # Send to WebSocket connections
    await manager.broadcast({"channel": channel, "data": data, "event": event})


@sse_app.get("/{channel}")
async def sse_endpoint(channel: str, request: Request):
    """SSE endpoint for real-time updates."""
    connection_id = uuid4().hex
    queue = asyncio.Queue()
    _sse_connections[connection_id] = queue

    async def event_generator():
        try:
            while True:
                # Check if client is still connected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for events with timeout
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "data": event_data["data"],
                        "event": event_data["event"],
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"comment": "keepalive"}
        except Exception:
            pass
        finally:
            _sse_connections.pop(connection_id, None)

    return EventSourceResponse(event_generator())
