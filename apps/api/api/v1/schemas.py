from ninja import Schema
from typing import Optional


class UserOut(Schema):
    id: str
    email: str
    name: Optional[str] = ""
    perfil: str


class AuthOut(Schema):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserOut


class AssociadoIn(Schema):
    cpf: str
    nome: str
    email: Optional[str] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None


class AssociadoOut(AssociadoIn):
    id: int


class CadastroIn(Schema):
    associado_id: int
    observacao: Optional[str] = None


class CadastroOut(Schema):
    id: int
    associado_id: int
    status: str
    observacao: Optional[str] = None
