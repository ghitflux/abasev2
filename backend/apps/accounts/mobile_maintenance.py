from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import APIView


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


class MobileMaintenanceMixin(APIView):
    def initial(self, request, *args, **kwargs):
        enforce_mobile_maintenance()
        super().initial(request, *args, **kwargs)
