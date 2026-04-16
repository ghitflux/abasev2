from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication

from .mobile_maintenance_policy import enforce_mobile_maintenance_for_user


class MaintenanceAwareJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result
        enforce_mobile_maintenance_for_user(user)
        return user, validated_token
