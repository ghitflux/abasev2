"""
Sistema de Controle de Acesso Baseado em Funções (RBAC)

Define roles, permissões e decoradores para controle de acesso
"""
from enum import Enum
from typing import Set, Optional, Callable
from functools import wraps
from ninja.errors import HttpError
from django.http import HttpRequest


class Role(str, Enum):
    """Roles disponíveis no sistema"""
    ADMIN = "ADMIN"
    ANALISTA = "ANALISTA"
    TESOUREIRO = "TESOUREIRO"
    AGENTE = "AGENTE"
    ASSOCIADO = "ASSOCIADO"


class Permission(str, Enum):
    """Permissões granulares do sistema"""
    # Cadastros
    CADASTROS_CREATE = "cadastros.create"
    CADASTROS_READ = "cadastros.read"
    CADASTROS_UPDATE = "cadastros.update"
    CADASTROS_DELETE = "cadastros.delete"
    CADASTROS_SUBMIT = "cadastros.submit"

    # Análise
    ANALISE_APROVAR = "analise.aprovar"
    ANALISE_PENDENCIAR = "analise.pendenciar"
    ANALISE_CANCELAR = "analise.cancelar"
    ANALISE_DEVOLVER = "analise.devolver"

    # Tesouraria
    TESOURARIA_RECEBER_PAGAMENTO = "tesouraria.receber_pagamento"
    TESOURARIA_UPLOAD_COMPROVANTE = "tesouraria.upload_comprovante"
    TESOURARIA_GERAR_CONTRATO = "tesouraria.gerar_contrato"
    TESOURARIA_ENVIAR_ASSINATURA = "tesouraria.enviar_assinatura"
    TESOURARIA_CONCLUIR = "tesouraria.concluir"

    # Relatórios
    RELATORIOS_VIEW = "relatorios.view"
    RELATORIOS_EXPORT = "relatorios.export"

    # Administração
    ADMIN_USERS_MANAGE = "admin.users.manage"
    ADMIN_SYSTEM_CONFIG = "admin.system.config"


# Mapeamento de Roles para Permissões
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.ADMIN: {
        # Admin tem todas as permissões
        *list(Permission),
    },

    Role.ANALISTA: {
        Permission.CADASTROS_READ,
        Permission.ANALISE_APROVAR,
        Permission.ANALISE_PENDENCIAR,
        Permission.ANALISE_CANCELAR,
        Permission.ANALISE_DEVOLVER,
        Permission.RELATORIOS_VIEW,
    },

    Role.TESOUREIRO: {
        Permission.CADASTROS_READ,
        Permission.TESOURARIA_RECEBER_PAGAMENTO,
        Permission.TESOURARIA_UPLOAD_COMPROVANTE,
        Permission.TESOURARIA_GERAR_CONTRATO,
        Permission.TESOURARIA_ENVIAR_ASSINATURA,
        Permission.TESOURARIA_CONCLUIR,
        Permission.RELATORIOS_VIEW,
        Permission.RELATORIOS_EXPORT,
    },

    Role.AGENTE: {
        Permission.CADASTROS_CREATE,
        Permission.CADASTROS_READ,
        Permission.CADASTROS_UPDATE,
        Permission.CADASTROS_SUBMIT,
    },

    Role.ASSOCIADO: {
        Permission.CADASTROS_READ,  # Apenas próprios cadastros
    },
}


def get_user_permissions(role: str) -> Set[Permission]:
    """Retorna permissões de um role"""
    try:
        user_role = Role(role)
        return ROLE_PERMISSIONS.get(user_role, set())
    except ValueError:
        return set()


def has_permission(role: str, permission: Permission) -> bool:
    """Verifica se um role tem uma permissão específica"""
    user_permissions = get_user_permissions(role)
    return permission in user_permissions


def has_role(role: str, required_roles: list[Role]) -> bool:
    """Verifica se um role está na lista de roles permitidos"""
    try:
        user_role = Role(role)
        return user_role in required_roles
    except ValueError:
        return False


# Decoradores para endpoints Django Ninja

def require_authenticated():
    """
    Decorator que requer autenticação

    Usage:
        @router.get("/endpoint")
        @require_authenticated()
        def my_endpoint(request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not hasattr(request, "auth_claims") or not request.auth_claims:
                raise HttpError(401, "authentication_required")
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(*roles: Role):
    """
    Decorator que requer um ou mais roles específicos

    Usage:
        @router.get("/endpoint")
        @require_role(Role.ADMIN, Role.ANALISTA)
        def my_endpoint(request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not hasattr(request, "auth_claims") or not request.auth_claims:
                raise HttpError(401, "authentication_required")

            user_role = request.auth_claims.get("perfil")

            if not user_role or not has_role(user_role, list(roles)):
                raise HttpError(403, "insufficient_permissions")

            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_permission(*permissions: Permission):
    """
    Decorator que requer uma ou mais permissões específicas

    Usage:
        @router.post("/aprovar")
        @require_permission(Permission.ANALISE_APROVAR)
        def aprovar_cadastro(request, cadastro_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not hasattr(request, "auth_claims") or not request.auth_claims:
                raise HttpError(401, "authentication_required")

            user_role = request.auth_claims.get("perfil")

            if not user_role:
                raise HttpError(403, "insufficient_permissions")

            # Verifica se usuário tem pelo menos uma das permissões
            user_permissions = get_user_permissions(user_role)
            has_any = any(perm in user_permissions for perm in permissions)

            if not has_any:
                raise HttpError(403, "insufficient_permissions")

            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_owner_or_role(*roles: Role):
    """
    Decorator que permite acesso se:
    - Usuário é dono do recurso (user_id == resource.user_id), OU
    - Usuário tem um dos roles especificados

    O endpoint deve ter um parâmetro 'entity_user_id' para comparação

    Usage:
        @router.get("/cadastros/{cadastro_id}")
        @require_owner_or_role(Role.ADMIN, Role.ANALISTA)
        def get_cadastro(request, cadastro_id: int, entity_user_id: str):
            # entity_user_id deve ser passado pela lógica do endpoint
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not hasattr(request, "auth_claims") or not request.auth_claims:
                raise HttpError(401, "authentication_required")

            user_id = request.auth_claims.get("user_id")
            user_role = request.auth_claims.get("perfil")

            # Verifica se é o dono
            entity_user_id = kwargs.get("entity_user_id")
            if entity_user_id and str(user_id) == str(entity_user_id):
                return func(request, *args, **kwargs)

            # Verifica se tem role permitido
            if user_role and has_role(user_role, list(roles)):
                return func(request, *args, **kwargs)

            raise HttpError(403, "insufficient_permissions")
        return wrapper
    return decorator


# Helper para verificar permissões em runtime

class PermissionChecker:
    """Classe helper para verificar permissões em runtime"""

    def __init__(self, request: HttpRequest):
        self.request = request
        self.user_id = getattr(request, "user_id", None)
        self.claims = getattr(request, "auth_claims", {})
        self.role = self.claims.get("perfil")

    def has_permission(self, permission: Permission) -> bool:
        """Verifica se usuário tem uma permissão"""
        if not self.role:
            return False
        return has_permission(self.role, permission)

    def has_role(self, *roles: Role) -> bool:
        """Verifica se usuário tem um dos roles"""
        if not self.role:
            return False
        return has_role(self.role, list(roles))

    def is_owner(self, entity_user_id: str) -> bool:
        """Verifica se usuário é dono do recurso"""
        return str(self.user_id) == str(entity_user_id)

    def can_access(self, entity_user_id: Optional[str], *roles: Role) -> bool:
        """Verifica se pode acessar (dono ou tem role)"""
        if entity_user_id and self.is_owner(entity_user_id):
            return True
        return self.has_role(*roles)
