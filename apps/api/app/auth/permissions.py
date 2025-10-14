from __future__ import annotations

from enum import Enum, unique
from typing import Iterable, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import SecurityScopes

from ..dependencies.auth import get_current_active_user
from ..schemas.user import UserRead


@unique
class Permission(str, Enum):
    """System-wide permission codes."""

    # Cadastros
    CADASTRO_CREATE = "cadastro.create"
    CADASTRO_READ = "cadastro.read"
    CADASTRO_UPDATE = "cadastro.update"
    CADASTRO_DELETE = "cadastro.delete"
    CADASTRO_SUBMIT = "cadastro.submit"

    # Análise
    ANALISE_VIEW = "analise.view"
    ANALISE_APPROVE = "analise.approve"
    ANALISE_REJECT = "analise.reject"
    ANALISE_REQUEST_CHANGES = "analise.request_changes"

    # Tesouraria
    TESOURARIA_VIEW = "tesouraria.view"
    TESOURARIA_PROCESS = "tesouraria.process"
    TESOURARIA_GENERATE_CONTRACT = "tesouraria.generate_contract"
    TESOURARIA_VALIDATE_NUVIDEO = "tesouraria.validate_nuvideo"
    TESOURARIA_SIGN = "tesouraria.sign"
    TESOURARIA_COMPLETE = "tesouraria.complete"

    # Relatórios
    RELATORIO_VIEW = "relatorio.view"
    RELATORIO_EXPORT = "relatorio.export"

    # Administração
    ADMIN_USERS_MANAGE = "admin.users.manage"
    ADMIN_SYSTEM_CONFIG = "admin.system.config"


@unique
class Role(str, Enum):
    """Predefined roles."""

    ADMIN = "ADMIN"
    ANALISTA = "ANALISTA"
    TESOURARIA = "TESOURARIA"
    AGENTE = "AGENTE"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.ANALISTA: {
        Permission.CADASTRO_READ,
        Permission.ANALISE_VIEW,
        Permission.ANALISE_APPROVE,
        Permission.ANALISE_REJECT,
        Permission.ANALISE_REQUEST_CHANGES,
        Permission.RELATORIO_VIEW,
        Permission.RELATORIO_EXPORT,
    },
    Role.TESOURARIA: {
        Permission.CADASTRO_READ,
        Permission.TESOURARIA_VIEW,
        Permission.TESOURARIA_PROCESS,
        Permission.TESOURARIA_GENERATE_CONTRACT,
        Permission.TESOURARIA_VALIDATE_NUVIDEO,
        Permission.TESOURARIA_SIGN,
        Permission.TESOURARIA_COMPLETE,
        Permission.RELATORIO_VIEW,
        Permission.RELATORIO_EXPORT,
    },
    Role.AGENTE: {
        Permission.CADASTRO_CREATE,
        Permission.CADASTRO_READ,
        Permission.CADASTRO_UPDATE,
        Permission.CADASTRO_SUBMIT,
        Permission.RELATORIO_VIEW,
    },
}


def has_permissions(user: UserRead, permissions: Iterable[Permission]) -> bool:
    if not user.roles:
        return False

    required = {Permission(p if isinstance(p, str) else p) for p in permissions}
    user_perms: set[Permission] = set()

    for role_name in user.roles:
        try:
            role_enum = Role(role_name)
        except ValueError:
            continue
        user_perms |= ROLE_PERMISSIONS.get(role_enum, set())

    return required.issubset(user_perms)


def require_permissions(perms: Sequence[Permission]):
    """FastAPI dependency ensuring the current user has the provided permissions."""

    async def dependency(
        security_scopes: SecurityScopes,
        current_user: UserRead = Depends(get_current_active_user),
    ) -> UserRead:
        needed = set(perms)
        needed |= {Permission(scope) for scope in security_scopes.scopes}
        if not has_permissions(current_user, needed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient_permissions",
            )
        return current_user

    return dependency
