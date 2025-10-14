from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EventLogRead(BaseModel):
    id: int
    entity_type: str
    entity_id: str
    event_type: str
    payload: dict[str, object]
    actor_id: UUID | None
    correlation_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True
