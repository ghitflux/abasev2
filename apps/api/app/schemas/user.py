from __future__ import annotations

from datetime import datetime
from typing import Literal, Sequence

from pydantic import BaseModel, EmailStr, Field

RoleLiteral = Literal["ADMIN", "ANALISTA", "TESOURARIA", "AGENTE"]


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(default="")
    is_active: bool = Field(default=True)
    roles: Sequence[RoleLiteral] = Field(default_factory=list)


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    roles: Sequence[RoleLiteral] | None = None
    password: str | None = Field(default=None, min_length=8)


class UserRead(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
