"""
Middleware de autenticação para Django Ninja

Este middleware:
- Extrai JWT de header Authorization ou cookies
- Valida o token
- Carrega usuário no request
- Implementa rate limiting
- Bloqueia requisições não autenticadas (exceto whitelist)
"""
from typing import Optional, Callable
from ninja import NinjaAPI
from ninja.errors import HttpError
from django.http import HttpRequest, HttpResponse
from django.core.cache import cache
from core.auth.managers import AuthenticationManager, AuthorizationError
import time


class AuthMiddleware:
    """Middleware de autenticação para Django Ninja"""

    # Endpoints que não requerem autenticação
    PUBLIC_ENDPOINTS = [
        "/api/v1/auth/oidc/callback",
        "/api/v1/auth/refresh",
        "/api/v1/health",
        "/api/docs",
        "/api/openapi.json",
        "/admin",
    ]

    # Rate limit: requisições por minuto por usuário
    RATE_LIMIT_PER_MINUTE = 60
    RATE_LIMIT_WINDOW = 60  # segundos

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.auth_manager = AuthenticationManager()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Processa requisição"""
        path = request.path

        # Verifica se endpoint é público
        if self._is_public_endpoint(path):
            return self.get_response(request)

        # Extrai e valida token
        token = self._extract_token(request)

        if not token:
            raise HttpError(401, "missing_token")

        # Valida token e carrega usuário
        try:
            claims = self.auth_manager.validate_request(token)
        except AuthorizationError as e:
            raise HttpError(401, str(e))
        except Exception as e:
            raise HttpError(401, "invalid_token")

        # Verifica rate limiting
        user_id = claims.get("user_id")
        if user_id and not self._check_rate_limit(user_id, path):
            raise HttpError(429, "rate_limit_exceeded")

        # Adiciona claims ao request para uso nos endpoints
        request.auth_claims = claims
        request.user_id = user_id

        response = self.get_response(request)
        return response

    def _is_public_endpoint(self, path: str) -> bool:
        """Verifica se endpoint é público"""
        for public_path in self.PUBLIC_ENDPOINTS:
            if path.startswith(public_path):
                return True
        return False

    def _extract_token(self, request: HttpRequest) -> Optional[str]:
        """Extrai JWT do header Authorization ou cookie"""
        # Tenta header Authorization
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header.split(" ", 1)[1]

        # Tenta cookie
        token = request.COOKIES.get("access_token")
        if token:
            return token

        return None

    def _check_rate_limit(self, user_id: str, path: str) -> bool:
        """Verifica rate limit do usuário"""
        # Cria chave única para o usuário e minuto atual
        current_minute = int(time.time() / self.RATE_LIMIT_WINDOW)
        cache_key = f"rate_limit:{user_id}:{current_minute}"

        # Incrementa contador
        count = cache.get(cache_key, 0)

        if count >= self.RATE_LIMIT_PER_MINUTE:
            return False

        # Incrementa e define TTL
        cache.set(cache_key, count + 1, self.RATE_LIMIT_WINDOW)
        return True


def setup_auth_middleware(api: NinjaAPI):
    """
    Configura middleware de autenticação no Django Ninja

    Usage:
        from api.middleware.auth_middleware import setup_auth_middleware
        api = NinjaAPI()
        setup_auth_middleware(api)
    """
    # Django Ninja usa decorators para autenticação
    # O middleware Django padrão já foi adicionado no MIDDLEWARE em settings
    pass
