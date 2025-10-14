import threading
from typing import Dict, Any, Optional
from .strategies import StrategyFactory, Credentials
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()


class AuthenticationError(Exception):
    ...


class AuthorizationError(Exception):
    ...


class AuthenticationManager:
    _instance: Optional["AuthenticationManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_init", False):
            return
        self.contexts = {
            "oidc": StrategyFactory.get("oidc"),
            "jwt": StrategyFactory.get("jwt"),
        }
        self._init = True

    async def authenticate_user(self, provider: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        ok, data = await self.contexts[provider].authenticate(
            Credentials(provider=provider, **credentials)
        )
        if not ok:
            raise AuthenticationError(data.get("error", "auth_failed"))
        if provider == "oidc":
            user = await self._get_or_create_user(data)
            ok_jwt, jwt_data = await self.contexts["jwt"].authenticate(
                Credentials(provider="jwt", metadata={"user_id": str(user.id)})
            )
            if not ok_jwt:
                raise AuthenticationError("jwt_failed")
            data.update(jwt_data)
        return data

    async def validate_request(self, token: str, required_permissions: Optional[list] = None) -> Dict[str, Any]:
        ok, claims = await self.contexts["jwt"].validate_token(token)
        if not ok:
            raise AuthorizationError("invalid_token")
        # TODO: validate permissions once we map user roles to permissions
        return claims or {}

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        ok, new_token = await self.contexts["jwt"].refresh_token(refresh_token)
        if not ok:
            raise AuthenticationError("refresh_failed")
        return {"access_token": new_token, "expires_in": 900}

    async def logout_user(self, user_id: str, token: str, global_logout: bool = False):
        await self.contexts["jwt"].revoke_token(token)
        if global_logout:
            cache.delete(f"session:{user_id}")

    async def _get_or_create_user(self, data: Dict[str, Any]):
        email = data.get("email")
        try:
            user = await User.objects.aget(email=email)
        except User.DoesNotExist:
            user = await User.objects.acreate(email=email, username=email, is_active=True)
        return user
