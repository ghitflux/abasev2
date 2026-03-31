from rest_framework.permissions import BasePermission


class BaseRolePermission(BasePermission):
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.has_role(*self.allowed_roles))
        )


class IsAgente(BaseRolePermission):
    allowed_roles = ("AGENTE",)


class IsAnalista(BaseRolePermission):
    allowed_roles = ("ANALISTA",)


class IsCoordenador(BaseRolePermission):
    allowed_roles = ("COORDENADOR",)


class IsTesoureiro(BaseRolePermission):
    allowed_roles = ("TESOUREIRO",)


class IsAdmin(BaseRolePermission):
    allowed_roles = ("ADMIN",)


class IsAgenteOrAdmin(BaseRolePermission):
    allowed_roles = ("AGENTE", "ADMIN")


class IsAgenteOrAnalistaOrCoordenadorOrAdmin(BaseRolePermission):
    allowed_roles = ("AGENTE", "ANALISTA", "COORDENADOR", "ADMIN")


class IsAnalistaOrAdmin(BaseRolePermission):
    allowed_roles = ("ANALISTA", "ADMIN")


class IsCoordenadorOrAdmin(BaseRolePermission):
    allowed_roles = ("COORDENADOR", "ADMIN")


class IsTesoureiroOrAdmin(BaseRolePermission):
    allowed_roles = ("TESOUREIRO", "ADMIN")


class IsOperacionalOrAdmin(BaseRolePermission):
    allowed_roles = ("AGENTE", "COORDENADOR", "ANALISTA", "TESOUREIRO", "ADMIN")


class IsAgenteOrTesoureiroOrAdmin(BaseRolePermission):
    allowed_roles = ("AGENTE", "TESOUREIRO", "ADMIN")


class IsCoordenadorOrTesoureiroOrAdmin(BaseRolePermission):
    allowed_roles = ("COORDENADOR", "TESOUREIRO", "ADMIN")


class IsAssociado(BaseRolePermission):
    allowed_roles = ("ASSOCIADO", "ASSOCIADODOIS")


class IsAssociadoOrAdmin(BaseRolePermission):
    allowed_roles = ("ASSOCIADO", "ASSOCIADODOIS", "ADMIN")
