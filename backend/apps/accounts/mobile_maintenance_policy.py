from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException


class MobileMaintenanceMode(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "O aplicativo está temporariamente indisponível para manutenção. "
        "Tente novamente em breve."
    )
    default_code = "mobile_maintenance"


def is_mobile_maintenance_enabled() -> bool:
    return bool(getattr(settings, "APP_MAINTENANCE_MODE", False))


def get_mobile_maintenance_message() -> str:
    return getattr(settings, "APP_MAINTENANCE_MESSAGE", MobileMaintenanceMode.default_detail)


def enforce_mobile_maintenance() -> None:
    if is_mobile_maintenance_enabled():
        raise MobileMaintenanceMode(detail=get_mobile_maintenance_message())


def is_mobile_self_service_user(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False

    role_codes = set(
        user.user_roles.filter(deleted_at__isnull=True).values_list("role__codigo", flat=True)
    )
    if not role_codes:
        return False
    return role_codes.issubset({"ASSOCIADO", "ASSOCIADODOIS"})


def enforce_mobile_maintenance_for_user(user) -> None:
    if is_mobile_self_service_user(user):
        enforce_mobile_maintenance()
