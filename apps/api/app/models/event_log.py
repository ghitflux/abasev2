from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    actor_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_event_logs_entity", "entity_type", "entity_id", "event_type"),
    )
