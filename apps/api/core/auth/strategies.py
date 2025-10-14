from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import httpx
import jwt
from django.conf import settings
from django.core.cache import cache


@dataclass
class Credentials:
    provider: str
    token: Optional[str] = None
    code: Optional[str] = None
    metadata: Dict[str, Any] | None = None


class BaseStrategy:
    async def authenticate(self, creds: Credentials) -> Tuple[bool, Dict[str, Any]]:
        ...

    async def validate_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        ...

    async def refresh_token(self, refresh_token: str) -> Tuple[bool, Optional[str]]:
        ...

    async def revoke_token(self, token: str) -> bool:
        ...


class OIDCStrategy(BaseStrategy):
    async def authenticate(self, creds: Credentials) -> Tuple[bool, Dict[str, Any]]:
        if not creds.code:
            return (False, {"error": "authorization_code_required"})
        issuer = settings.OIDC_ISSUER
        async with httpx.AsyncClient() as client:
            disc = (await client.get(f"{issuer}/.well-known/openid-configuration")).json()
            response = await client.post(
                disc["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": creds.code,
                    "redirect_uri": settings.OIDC_REDIRECT_URI,
                    "client_id": settings.OIDC_CLIENT_ID,
                    "client_secret": settings.OIDC_CLIENT_SECRET,
                    "code_verifier": (creds.metadata or {}).get("code_verifier", ""),
                },
            )
            if response.status_code != 200:
                return (False, {"error": "token_exchange_failed", "details": response.text})
            tokens = response.json()
            id_token = tokens.get("id_token")
            claims = jwt.decode(
                id_token,
                options={"verify_signature": False},
                audience=settings.OIDC_CLIENT_ID,
            )
            return (
                True,
                {
                    "id": claims.get("sub"),
                    "email": claims.get("email"),
                    "name": claims.get("name"),
                    "access_token": tokens.get("access_token"),
                    "refresh_token": tokens.get("refresh_token"),
                    "expires_in": tokens.get("expires_in", 3600),
                },
            )

    async def validate_token(self, token: str):
        return (True, {})

    async def refresh_token(self, refresh_token: str):
        return (False, None)

    async def revoke_token(self, token: str) -> bool:
        cache.set(f"blacklist:{token}", True, 86400)
        return True


class JWTStrategy(BaseStrategy):
    algorithm = "HS256"

    def _make_token(self, payload: Dict[str, Any]) -> str:
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=self.algorithm)

    async def authenticate(self, creds: Credentials) -> Tuple[bool, Dict[str, Any]]:
        user_id = (creds.metadata or {}).get("user_id")
        if not user_id:
            return (False, {"error": "user_id_required"})
        from django.contrib.auth import get_user_model
        from datetime import datetime, timedelta

        User = get_user_model()
        try:
            user = await User.objects.aget(id=user_id)
        except User.DoesNotExist:
            return (False, {"error": "user_not_found"})

        now = datetime.utcnow()
        perfil = getattr(user, "perfil", "AGENTE")
        email = getattr(user, "email", "")
        access = self._make_token(
            {
                "user_id": str(user.id),
                "email": email,
                "perfil": perfil,
                "type": "access",
                "iat": now,
                "exp": now + timedelta(minutes=15),
                "iss": "abase-v2",
                "aud": "abase-api",
            }
        )
        refresh = self._make_token(
            {
                "user_id": str(user.id),
                "type": "refresh",
                "iat": now,
                "exp": now + timedelta(days=7),
                "iss": "abase-v2",
            }
        )

        cache.set(
            f"session:{user.id}",
            {"user_id": str(user.id), "email": email, "perfil": perfil},
            7 * 24 * 3600,
        )
        return (
            True,
            {
                "access_token": access,
                "refresh_token": refresh,
                "expires_in": 900,
                "user": {
                    "id": str(user.id),
                    "email": email,
                    "name": getattr(user, "nome_completo", ""),
                    "perfil": perfil,
                },
            },
        )

    async def validate_token(self, token: str):
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[self.algorithm],
                audience="abase-api",
                issuer="abase-v2",
            )
            if not cache.get(f"session:{payload.get('user_id')}"):
                return (False, None)
            return (True, payload)
        except Exception:
            return (False, None)

    async def refresh_token(self, refresh_token: str):
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[self.algorithm],
                options={"verify_aud": False},
            )
            if payload.get("type") != "refresh":
                return (False, None)
            from datetime import datetime, timedelta

            now = datetime.utcnow()
            new_access = self._make_token(
                {
                    "user_id": payload["user_id"],
                    "type": "access",
                    "iat": now,
                    "exp": now + timedelta(minutes=15),
                    "iss": "abase-v2",
                    "aud": "abase-api",
                }
            )
            return (True, new_access)
        except Exception:
            return (False, None)

    async def revoke_token(self, token: str) -> bool:
        cache.set(f"blacklist:{token}", True, 86400)
        return True


class StrategyFactory:
    @staticmethod
    def get(provider: str) -> BaseStrategy:
        if provider == "oidc":
            return OIDCStrategy()
        return JWTStrategy()
