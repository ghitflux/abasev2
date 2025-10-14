from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Associado(Base):
    __tablename__ = "associados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cpf: Mapped[str] = mapped_column(String(14), unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    endereco: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    cadastros = relationship("Cadastro", back_populates="associado", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Associado {self.nome} ({self.cpf})>"
