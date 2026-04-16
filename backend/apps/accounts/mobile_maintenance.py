from __future__ import annotations

from rest_framework.views import APIView

from .mobile_maintenance_policy import (
    MobileMaintenanceMode,
    enforce_mobile_maintenance,
    enforce_mobile_maintenance_for_user,
    get_mobile_maintenance_message,
    is_mobile_maintenance_enabled,
)


class MobileMaintenanceMixin(APIView):
    def initial(self, request, *args, **kwargs):
        enforce_mobile_maintenance()
        super().initial(request, *args, **kwargs)
