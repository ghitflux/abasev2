"""
Módulo de segurança: Lockout de contas e Rate Limiting

Implementa mecanismos de segurança para prevenir:
- Brute force attacks (lockout após N tentativas falhas)
- DDoS e abuse (rate limiting por usuário/IP)
"""
from typing import Optional
from django.core.cache import cache
from django.conf import settings
import time


# Configurações (com fallback para valores padrão)
MAX_FAILED_LOGIN_ATTEMPTS = getattr(settings, "MAX_FAILED_LOGIN_ATTEMPTS", 5)
ACCOUNT_LOCKOUT_MINUTES = getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 30)
RATE_LIMIT_PER_MINUTE = getattr(settings, "RATE_LIMIT_PER_MINUTE", 60)


def track_failed_login(username: str) -> int:
    """
    Registra uma tentativa de login falha

    Args:
        username: Nome de usuário ou email que tentou fazer login

    Returns:
        Número total de tentativas falhas no período de lockout

    Usage:
        failed_count = track_failed_login("user@example.com")
        if failed_count >= MAX_FAILED_LOGIN_ATTEMPTS:
            # Bloquear login
    """
    cache_key = f"failed_attempts:{username}"
    failed_count = cache.get(cache_key, 0) + 1

    # Armazena contador com TTL igual ao tempo de lockout
    cache.set(cache_key, failed_count, ACCOUNT_LOCKOUT_MINUTES * 60)

    return failed_count


def reset_failed_login(username: str) -> None:
    """
    Reseta contador de tentativas falhas após login bem-sucedido

    Args:
        username: Nome de usuário ou email

    Usage:
        if login_successful:
            reset_failed_login("user@example.com")
    """
    cache_key = f"failed_attempts:{username}"
    cache.delete(cache_key)


def is_locked_out(username: str) -> bool:
    """
    Verifica se uma conta está bloqueada

    Args:
        username: Nome de usuário ou email

    Returns:
        True se conta está bloqueada, False caso contrário

    Usage:
        if is_locked_out("user@example.com"):
            raise HttpError(403, "account_locked")
    """
    cache_key = f"failed_attempts:{username}"
    failed_count = cache.get(cache_key, 0)

    return failed_count >= MAX_FAILED_LOGIN_ATTEMPTS


def get_lockout_time_remaining(username: str) -> Optional[int]:
    """
    Retorna tempo restante de lockout em segundos

    Args:
        username: Nome de usuário ou email

    Returns:
        Segundos restantes de lockout, ou None se não está bloqueado

    Usage:
        remaining = get_lockout_time_remaining("user@example.com")
        if remaining:
            return {"error": "locked_out", "retry_after": remaining}
    """
    if not is_locked_out(username):
        return None

    cache_key = f"failed_attempts:{username}"
    ttl = cache.ttl(cache_key)

    return ttl if ttl > 0 else None


def unlock_account(username: str) -> None:
    """
    Desbloqueia uma conta manualmente (admin action)

    Args:
        username: Nome de usuário ou email

    Usage:
        # Endpoint de admin para desbloquear contas
        @require_role(Role.ADMIN)
        def unlock_user(request, username: str):
            unlock_account(username)
            return {"message": "account_unlocked"}
    """
    cache_key = f"failed_attempts:{username}"
    cache.delete(cache_key)


def check_rate_limit(identifier: str, limit: int = RATE_LIMIT_PER_MINUTE, window: int = 60) -> bool:
    """
    Verifica rate limit genérico

    Args:
        identifier: Identificador único (user_id, IP, etc)
        limit: Número máximo de requisições
        window: Janela de tempo em segundos

    Returns:
        True se dentro do limite, False se excedeu

    Usage:
        if not check_rate_limit(f"user:{user_id}", limit=100, window=60):
            raise HttpError(429, "rate_limit_exceeded")
    """
    cache_key = f"rate_limit:{identifier}:{int(time.time() / window)}"
    count = cache.get(cache_key, 0)

    if count >= limit:
        return False

    # Incrementa contador
    cache.set(cache_key, count + 1, window)
    return True


def check_endpoint_rate_limit(user_id: str, endpoint: str, limit: int = 10, window: int = 60) -> bool:
    """
    Rate limit específico por endpoint

    Args:
        user_id: ID do usuário
        endpoint: Nome ou path do endpoint
        limit: Número máximo de chamadas
        window: Janela de tempo em segundos

    Returns:
        True se dentro do limite, False se excedeu

    Usage:
        @router.post("/expensive-operation")
        def expensive_op(request):
            if not check_endpoint_rate_limit(request.user_id, "expensive_operation", limit=5, window=3600):
                raise HttpError(429, "endpoint_rate_limit_exceeded")
            ...
    """
    identifier = f"endpoint:{user_id}:{endpoint}"
    return check_rate_limit(identifier, limit, window)


def check_ip_rate_limit(ip_address: str, limit: int = 100, window: int = 60) -> bool:
    """
    Rate limit por IP (proteção contra DDoS)

    Args:
        ip_address: Endereço IP
        limit: Número máximo de requisições
        window: Janela de tempo em segundos

    Returns:
        True se dentro do limite, False se excedeu

    Usage:
        ip = request.META.get("REMOTE_ADDR")
        if not check_ip_rate_limit(ip, limit=1000, window=60):
            raise HttpError(429, "ip_rate_limit_exceeded")
    """
    identifier = f"ip:{ip_address}"
    return check_rate_limit(identifier, limit, window)


def get_rate_limit_remaining(identifier: str, limit: int, window: int = 60) -> int:
    """
    Retorna número de requisições restantes no rate limit

    Args:
        identifier: Identificador único
        limit: Limite total
        window: Janela de tempo em segundos

    Returns:
        Número de requisições restantes

    Usage:
        remaining = get_rate_limit_remaining(f"user:{user_id}", 100)
        # Incluir no header: X-RateLimit-Remaining: {remaining}
    """
    cache_key = f"rate_limit:{identifier}:{int(time.time() / window)}"
    count = cache.get(cache_key, 0)
    return max(0, limit - count)


class RateLimiter:
    """
    Classe helper para rate limiting com contexto

    Usage:
        limiter = RateLimiter(request)
        if not limiter.check_user_limit():
            raise HttpError(429, "rate_limit_exceeded")
    """

    def __init__(self, request):
        self.request = request
        self.user_id = getattr(request, "user_id", None)
        self.ip_address = request.META.get("REMOTE_ADDR")

    def check_user_limit(self, limit: int = RATE_LIMIT_PER_MINUTE, window: int = 60) -> bool:
        """Verifica rate limit do usuário"""
        if not self.user_id:
            return True
        return check_rate_limit(f"user:{self.user_id}", limit, window)

    def check_ip_limit(self, limit: int = 100, window: int = 60) -> bool:
        """Verifica rate limit do IP"""
        if not self.ip_address:
            return True
        return check_ip_rate_limit(self.ip_address, limit, window)

    def check_endpoint_limit(self, endpoint: str, limit: int = 10, window: int = 60) -> bool:
        """Verifica rate limit de um endpoint específico"""
        if not self.user_id:
            return True
        return check_endpoint_rate_limit(self.user_id, endpoint, limit, window)

    def get_user_remaining(self, limit: int = RATE_LIMIT_PER_MINUTE) -> int:
        """Retorna requisições restantes do usuário"""
        if not self.user_id:
            return limit
        return get_rate_limit_remaining(f"user:{self.user_id}", limit)
