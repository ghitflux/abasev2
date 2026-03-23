from drf_spectacular.extensions import OpenApiAuthenticationExtension


class LegacyMobileTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.mobile_legacy_auth.LegacyMobileTokenAuthentication"
    name = "LegacyMobileToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "LegacyMobileToken",
            "description": (
                "Bearer token do mobile legado. "
                "O backend também aceita ?token=<chave> para compatibilidade."
            ),
        }
