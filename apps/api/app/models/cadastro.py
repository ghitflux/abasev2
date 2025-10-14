from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:  # pragma: no cover
    from .associado import Associado
    from .user import User


class CadastroStatus(str, Enum):
    RASCUNHO = "RASCUNHO"
    ENVIADO_ANALISE = "ENVIADO_ANALISE"
    PENDENTE_CORRECAO = "PENDENTE_CORRECAO"
    APROVADO_ANALISE = "APROVADO_ANALISE"
    CANCELADO = "CANCELADO"
    EM_TESOURARIA = "EM_TESOURARIA"
    AGUARDANDO_COMPROVANTES = "AGUARDANDO_COMPROVANTES"
    EM_VALIDACAO_NUVIDEO = "EM_VALIDACAO_NUVIDEO"
    CONTRATO_GERADO = "CONTRATO_GERADO"
    ASSINADO = "ASSINADO"
    CONCLUIDO = "CONCLUIDO"


class Cadastro(Base):
    __tablename__ = "cadastros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    associado_id: Mapped[int] = mapped_column(ForeignKey("associados.id", ondelete="CASCADE"))
    status: Mapped[CadastroStatus] = mapped_column(
        SqlEnum(CadastroStatus, native_enum=False, length=32),
        default=CadastroStatus.RASCUNHO,
        nullable=False,
    )
    criado_por_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    atualizado_por_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    associado: Mapped["Associado"] = relationship(
        "Associado", back_populates="cadastros"
    )
    criado_por: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[criado_por_id]
    )
    atualizado_por: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[atualizado_por_id]
    )

    def __repr__(self) -> str:
        return f"<Cadastro {self.id} - {self.status}>"
