from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .events import sse_app, start_event_listener
from .events.websocket import manager
from .routers import analise, auth, cadastros, health, relatorios, tesouraria


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN401
    await init_db()
    await start_event_listener()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(cadastros.router, prefix="/api/v1/cadastros", tags=["cadastros"])
app.include_router(analise.router, prefix="/api/v1/analise", tags=["analise"])
app.include_router(tesouraria.router, prefix="/api/v1/tesouraria", tags=["tesouraria"])
app.include_router(relatorios.router, prefix="/api/v1/relatorios", tags=["relatorios"])

app.mount("/api/v1/sse", sse_app)


@app.websocket("/api/v1/ws/updates")
async def websocket_updates(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            await manager.broadcast(message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
