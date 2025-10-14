from __future__ import annotations

from typing import Any, Dict, List

from fastapi import WebSocket


class ConnectionManager:
    """Simple in-memory WebSocket connection manager."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a JSON message to all connected clients."""
        for connection in self.active_connections:
            await connection.send_json(message)


manager = ConnectionManager()
