from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID as UUIDType
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class User(Base):
    """User table."""

    __tablename__ = "users"

    id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    roles: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(String(32)), default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "roles": list(self.roles),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
