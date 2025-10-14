from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
