from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AssociadoBase(BaseModel):
    cpf: str = Field(max_length=14)
    nome: str = Field(max_length=150)
    email: str | None = None
    telefone: str | None = None
    endereco: str | None = None


class AssociadoCreate(AssociadoBase):
    pass


class AssociadoUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=150)
    email: str | None = None
    telefone: str | None = None
    endereco: str | None = None


class AssociadoRead(AssociadoBase):
    id: int
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True
