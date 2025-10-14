from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.cadastro import CadastroStatus
from .associado import AssociadoRead
from .user import UserRead


class CadastroBase(BaseModel):
    associado_id: int
    observacao: str | None = Field(default=None, max_length=2000)
    status: CadastroStatus = CadastroStatus.RASCUNHO


class CadastroCreate(CadastroBase):
    pass


class CadastroUpdate(BaseModel):
    observacao: str | None = Field(default=None, max_length=2000)
    status: CadastroStatus | None = None


class CadastroRead(BaseModel):
    id: int
    status: CadastroStatus
    observacao: str | None
    associado: AssociadoRead
    criado_por: UserRead | None
    atualizado_por: UserRead | None
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True
