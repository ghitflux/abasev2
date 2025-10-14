#!/usr/bin/env bash
set -euo pipefail
shopt -s extglob

note() { printf '\033[1;36m›\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
okay() { printf '\033[1;32m✓\033[0m %s\n' "$*"; }

require_dir() { mkdir -p "$1"; }

write_file() {
  local path="$1"
  require_dir "$(dirname "$path")"
  cat >"$path"
  okay "wrote: $path"
}

append_unique() {
  local path="$1"
  local needle="$2"
  local payload="$3"
  if [ -f "$path" ] && grep -qF "$needle" "$path"; then
    warn "skip (present): $needle in $path"
    return 0
  fi
  require_dir "$(dirname "$path")"
  printf '%s' "$payload" >>"$path"
  okay "append: $needle → $path"
}

note "ABASE v2 — Fase 2 apply starting..."

# --------------------------------------------------------------------------------------
# 0) Python deps (API) — garante dependências mínimas
# --------------------------------------------------------------------------------------
require_dir apps/api
if [ -f apps/api/requirements.txt ]; then
  append_unique apps/api/requirements.txt "django-ninja" $'\ndjango-ninja>=0.23\n'
  append_unique apps/api/requirements.txt "django-redis" 'django-redis>=5.4
'
  append_unique apps/api/requirements.txt "httpx" 'httpx>=0.27
'
  append_unique apps/api/requirements.txt "PyJWT" 'PyJWT>=2.9
'
  append_unique apps/api/requirements.txt "redis" 'redis>=5.0
'
  append_unique apps/api/requirements.txt "celery" 'celery>=5.4
'
else
  write_file apps/api/requirements.txt <<'EOF'
django>=5.0
django-ninja>=0.23
django-redis>=5.4
httpx>=0.27
PyJWT>=2.9
redis>=5.0
celery>=5.4
psycopg2-binary>=2.9
EOF
fi

# --------------------------------------------------------------------------------------
# 1) Settings snippets — Redis cache, Celery, CORS, Ninja
# --------------------------------------------------------------------------------------
write_file apps/api/config/settings/fase2.py <<'EOF'
from datetime import timedelta
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = False

SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
ACCOUNT_LOCKOUT_MINUTES = int(os.getenv("ACCOUNT_LOCKOUT_MINUTES", "30"))
REQUIRE_MFA = os.getenv("REQUIRE_MFA", "false").lower() == "true"
ALLOWED_ORIGINS = (
    os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []
)
EOF

if [ -f apps/api/config/settings/base.py ]; then
  append_unique apps/api/config/settings/base.py "from .fase2 import *" '
# ABASE v2 — Fase 2
from .fase2 import *
'
fi

# --------------------------------------------------------------------------------------
# 2) Celery app
# --------------------------------------------------------------------------------------
write_file apps/api/config/celery.py <<'EOF'
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
app = Celery("abase")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
EOF

write_file apps/api/config/__init__.py <<'EOF'
from .celery import app as celery_app

__all__ = ("celery_app",)
EOF

# --------------------------------------------------------------------------------------
# 3) Infra Redis helper (pub/sub p/ SSE)
# --------------------------------------------------------------------------------------
write_file apps/api/infrastructure/cache/redis_client.py <<'EOF'
import os
import redis
from django.conf import settings

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(
            getattr(settings, "REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        )
    return _pool


def get_client():
    return redis.Redis(connection_pool=get_pool())


def publish(channel: str, message: str):
    get_client().publish(channel, message)
EOF

# --------------------------------------------------------------------------------------
# 4) Core Auth (Strategy/Factory/Singleton condensado)
# --------------------------------------------------------------------------------------
write_file apps/api/core/auth/__init__.py <<'EOF'
from .managers import AuthenticationManager, AuthenticationError, AuthorizationError
from .permissions import Permission, ROLE_PERMISSIONS

__all__ = [
    "AuthenticationManager",
    "AuthenticationError",
    "AuthorizationError",
    "Permission",
    "ROLE_PERMISSIONS",
]
EOF

write_file apps/api/core/auth/permissions.py <<'EOF'
from enum import Enum


class Permission(Enum):
    CADASTRO_CREATE = "cadastro.create"
    CADASTRO_READ_OWN = "cadastro.read_own"
    CADASTRO_READ_ALL = "cadastro.read_all"
    CADASTRO_UPDATE_OWN = "cadastro.update_own"
    CADASTRO_UPDATE_ALL = "cadastro.update_all"
    CADASTRO_DELETE = "cadastro.delete"
    CADASTRO_SUBMIT = "cadastro.submit"

    ANALISE_VIEW = "analise.view"
    ANALISE_APPROVE = "analise.approve"
    ANALISE_REJECT = "analise.reject"
    ANALISE_REQUEST_CHANGES = "analise.request_changes"

    TESOURARIA_VIEW = "tesouraria.view"
    TESOURARIA_PROCESS = "tesouraria.process"
    TESOURARIA_GENERATE_CONTRACT = "tesouraria.generate_contract"
    TESOURARIA_VALIDATE_NUVIDEO = "tesouraria.validate_nuvideo"
    TESOURARIA_SIGN = "tesouraria.sign"
    TESOURARIA_COMPLETE = "tesouraria.complete"

    RELATORIO_VIEW_OWN = "relatorio.view_own"
    RELATORIO_VIEW_ALL = "relatorio.view_all"
    RELATORIO_EXPORT = "relatorio.export"

    RENOVACAO_REQUEST = "renovacao.request"
    RENOVACAO_APPROVE = "renovacao.approve"


ROLE_PERMISSIONS = {
    "AGENTE": [
        Permission.CADASTRO_CREATE.value,
        Permission.CADASTRO_READ_OWN.value,
        Permission.CADASTRO_UPDATE_OWN.value,
        Permission.CADASTRO_SUBMIT.value,
        Permission.RENOVACAO_REQUEST.value,
        Permission.RELATORIO_VIEW_OWN.value,
    ],
    "ANALISTA": [
        Permission.CADASTRO_READ_ALL.value,
        Permission.ANALISE_VIEW.value,
        Permission.ANALISE_APPROVE.value,
        Permission.ANALISE_REJECT.value,
        Permission.ANALISE_REQUEST_CHANGES.value,
        Permission.RENOVACAO_APPROVE.value,
        Permission.RELATORIO_VIEW_ALL.value,
        Permission.RELATORIO_EXPORT.value,
    ],
    "TESOURARIA": [
        Permission.CADASTRO_READ_ALL.value,
        Permission.TESOURARIA_VIEW.value,
        Permission.TESOURARIA_PROCESS.value,
        Permission.TESOURARIA_GENERATE_CONTRACT.value,
        Permission.TESOURARIA_VALIDATE_NUVIDEO.value,
        Permission.TESOURARIA_SIGN.value,
        Permission.TESOURARIA_COMPLETE.value,
        Permission.RELATORIO_VIEW_ALL.value,
        Permission.RELATORIO_EXPORT.value,
    ],
    "DIRETORIA": [
        Permission.CADASTRO_READ_ALL.value,
        Permission.RELATORIO_VIEW_ALL.value,
        Permission.RELATORIO_EXPORT.value,
    ],
    "ADMIN": ["*"],
}
EOF

write_file apps/api/core/auth/strategies.py <<'EOF'
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
EOF

write_file apps/api/core/auth/managers.py <<'EOF'
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
EOF

# --------------------------------------------------------------------------------------
# 5) Domain Models (Bloco 3) — Associado/Cadastro + EventLog
# --------------------------------------------------------------------------------------
write_file apps/api/core/models/__init__.py <<'EOF'
from .associado import Associado
from .cadastro import Cadastro, CadastroStatus
from .event_log import EventLog

__all__ = ["Associado", "Cadastro", "CadastroStatus", "EventLog"]
EOF

write_file apps/api/core/models/associado.py <<'EOF'
from django.db import models


class Associado(models.Model):
    cpf = models.CharField(max_length=14, unique=True)
    nome = models.CharField(max_length=150)
    email = models.EmailField(blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    endereco = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.nome} ({self.cpf})"
EOF

write_file apps/api/core/models/cadastro.py <<'EOF'
from django.db import models
from django.conf import settings
from .associado import Associado


class CadastroStatus(models.TextChoices):
    RASCUNHO = "RASCUNHO"
    ENVIADO_ANALISE = "ENVIADO_ANALISE"
    PENDENTE_CORRECAO = "PENDENTE_CORRECAO"
    APROVADO_ANALISE = "APROVADO_ANALISE"
    CANCELADO = "CANCELADO"
    EM_TESOURARIA = "EM_TESOURARIA"
    AGUARDANDO_COMPROVANTES = "AGUARDANDO_COMPROVANTES"
    EM_VALIDACAO_NUVIDEO = "EM_VALIDACAO_NUVIDEO"
    CONTRATO_GERADO = "CONTRATO_GERADO"
    ASSINADO = "ASSINADO"
    CONCLUIDO = "CONCLUIDO"


class Cadastro(models.Model):
    associado = models.ForeignKey(Associado, on_delete=models.CASCADE, related_name="cadastros")
    status = models.CharField(
        max_length=32, choices=CadastroStatus.choices, default=CadastroStatus.RASCUNHO
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cadastros_criados",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="cadastros_atualizados",
    )
    observacao = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Cadastro #{self.id} — {self.associado}"
EOF

write_file apps/api/core/models/event_log.py <<'EOF'
from django.db import models
from django.conf import settings


class EventLog(models.Model):
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    actor_id = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    correlation_id = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["entity_type", "entity_id", "event_type"])]
EOF

# --------------------------------------------------------------------------------------
# 6) Services (Bloco 5) — Regras de negócio + Event publish
# --------------------------------------------------------------------------------------
write_file apps/api/core/services/cadastro_service.py <<'EOF'
from django.db import transaction
from typing import Optional
from ..models import Cadastro, CadastroStatus, EventLog
from infrastructure.cache.redis_client import publish

CHANNEL_ALL = "events:all"


class CadastroService:
    @staticmethod
    @transaction.atomic
    def submit(cadastro: Cadastro, actor_id: Optional[str] = None) -> Cadastro:
        cadastro.status = CadastroStatus.ENVIADO_ANALISE
        cadastro.save(update_fields=["status", "atualizado_em"])
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="submitted",
            payload={"status": cadastro.status},
            actor_id=actor_id,
        )
        publish(CHANNEL_ALL, f"cadastro:{cadastro.id}:submitted")
        return cadastro

    @staticmethod
    @transaction.atomic
    def aprovar(cadastro: Cadastro, actor_id: Optional[str] = None) -> Cadastro:
        cadastro.status = CadastroStatus.APROVADO_ANALISE
        cadastro.save(update_fields=["status", "atualizado_em"])
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="approved",
            payload={"status": cadastro.status},
            actor_id=actor_id,
        )
        publish(CHANNEL_ALL, f"cadastro:{cadastro.id}:approved")
        return cadastro

    @staticmethod
    @transaction.atomic
    def pendenciar(cadastro: Cadastro, motivo: str, actor_id: Optional[str] = None) -> Cadastro:
        cadastro.status = CadastroStatus.PENDENTE_CORRECAO
        cadastro.observacao = motivo
        cadastro.save(update_fields=["status", "observacao", "atualizado_em"])
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="needs_changes",
            payload={"motivo": motivo},
            actor_id=actor_id,
        )
        publish(CHANNEL_ALL, f"cadastro:{cadastro.id}:needs_changes")
        return cadastro

    @staticmethod
    @transaction.atomic
    def cancelar(cadastro: Cadastro, motivo: str, actor_id: Optional[str] = None) -> Cadastro:
        cadastro.status = CadastroStatus.CANCELADO
        cadastro.observacao = motivo
        cadastro.save(update_fields=["status", "observacao", "atualizado_em"])
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="canceled",
            payload={"motivo": motivo},
            actor_id=actor_id,
        )
        publish(CHANNEL_ALL, f"cadastro:{cadastro.id}:canceled")
        return cadastro
EOF

# --------------------------------------------------------------------------------------
# 7) API Ninja (Bloco 4) — routers v1 (auth, cadastros, analise, tesouraria, sse)
# --------------------------------------------------------------------------------------
write_file apps/api/api/v1/__init__.py <<'EOF'
# routers package marker
EOF

write_file apps/api/api/v1/schemas.py <<'EOF'
from ninja import Schema
from typing import Optional


class UserOut(Schema):
    id: str
    email: str
    name: Optional[str] = ""
    perfil: str


class AuthOut(Schema):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserOut


class AssociadoIn(Schema):
    cpf: str
    nome: str
    email: Optional[str] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None


class AssociadoOut(AssociadoIn):
    id: int


class CadastroIn(Schema):
    associado_id: int
    observacao: Optional[str] = None


class CadastroOut(Schema):
    id: int
    associado_id: int
    status: str
    observacao: Optional[str] = None
EOF

write_file apps/api/api/v1/auth_router.py <<'EOF'
from ninja import Router
from ninja.errors import HttpError
from core.auth import AuthenticationManager
from .schemas import AuthOut, UserOut

router = Router(tags=["auth"])
manager = AuthenticationManager()


@router.post("/oidc/callback", response=AuthOut)
async def oidc_callback(request, code: str, code_verifier: str = ""):
    data = await manager.authenticate_user(
        "oidc", {"code": code, "metadata": {"code_verifier": code_verifier}}
    )
    return data


@router.post("/refresh")
async def refresh(request, refresh_token: str):
    return await manager.refresh_access_token(refresh_token)


@router.post("/logout")
async def logout(request, token: str, user_id: str, global_logout: bool = False):
    await manager.logout_user(user_id, token, global_logout)
    return {"ok": True}


@router.get("/me", response=UserOut)
async def me(request):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HttpError(401, "missing_token")
    token = auth_header.split(" ", 1)[1]
    claims = await manager.validate_request(token)
    return {
        "id": claims.get("user_id"),
        "email": claims.get("email", ""),
        "name": "",
        "perfil": claims.get("perfil", "AGENTE"),
    }


@router.post("/validate")
async def validate(request):
    return {"ok": True}
EOF

write_file apps/api/api/v1/cadastros_router.py <<'EOF'
from asgiref.sync import sync_to_async
from ninja import Router
from ninja.errors import HttpError
from django.shortcuts import get_object_or_404
from core.models import Associado, Cadastro
from core.services.cadastro_service import CadastroService
from .schemas import AssociadoIn, AssociadoOut, CadastroIn, CadastroOut

router = Router(tags=["cadastros"])


async def _get_associado_or_404(assoc_id: int) -> Associado:
    return await sync_to_async(get_object_or_404, thread_sensitive=True)(Associado, id=assoc_id)


async def _get_cadastro_or_404(cad_id: int) -> Cadastro:
    return await sync_to_async(get_object_or_404, thread_sensitive=True)(Cadastro, id=cad_id)


@router.post("/associados", response=AssociadoOut)
async def criar_associado(request, payload: AssociadoIn):
    exists = await Associado.objects.filter(cpf=payload.cpf).aexists()
    if exists:
        raise HttpError(400, "cpf_duplicado")
    associado = await Associado.objects.acreate(**payload.dict())
    data = payload.dict()
    data["id"] = associado.id
    return data


@router.get("/associados/{assoc_id}", response=AssociadoOut)
async def obter_associado(request, assoc_id: int):
    associado = await _get_associado_or_404(assoc_id)
    return {
        "id": associado.id,
        "cpf": associado.cpf,
        "nome": associado.nome,
        "email": associado.email,
        "telefone": associado.telefone,
        "endereco": associado.endereco,
    }


@router.post("/cadastros", response=CadastroOut)
async def criar_cadastro(request, payload: CadastroIn):
    associado = await _get_associado_or_404(payload.associado_id)
    cadastro = await Cadastro.objects.acreate(associado=associado, observacao=payload.observacao)
    return {
        "id": cadastro.id,
        "associado_id": associado.id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/submit", response=CadastroOut)
async def submit(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await sync_to_async(CadastroService.submit, thread_sensitive=True)(cadastro)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }
EOF

write_file apps/api/api/v1/analise_router.py <<'EOF'
from asgiref.sync import sync_to_async
from ninja import Router
from django.shortcuts import get_object_or_404
from core.models import Cadastro
from core.services.cadastro_service import CadastroService
from .schemas import CadastroOut

router = Router(tags=["analise"])


async def _get_cadastro_or_404(cad_id: int) -> Cadastro:
    return await sync_to_async(get_object_or_404, thread_sensitive=True)(Cadastro, id=cad_id)


@router.post("/cadastros/{cad_id}/aprovar", response=CadastroOut)
async def aprovar(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await sync_to_async(CadastroService.aprovar, thread_sensitive=True)(cadastro)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/pendenciar", response=CadastroOut)
async def pendenciar(request, cad_id: int, motivo: str):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await sync_to_async(CadastroService.pendenciar, thread_sensitive=True)(cadastro, motivo)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/cancelar", response=CadastroOut)
async def cancelar(request, cad_id: int, motivo: str):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await sync_to_async(CadastroService.cancelar, thread_sensitive=True)(cadastro, motivo)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }
EOF

write_file apps/api/api/v1/tesouraria_router.py <<'EOF'
from asgiref.sync import sync_to_async
from ninja import Router
from django.shortcuts import get_object_or_404
from core.models import Cadastro
from core.models.cadastro import CadastroStatus
from .schemas import CadastroOut

router = Router(tags=["tesouraria"])


async def _get_cadastro_or_404(cad_id: int) -> Cadastro:
    return await sync_to_async(get_object_or_404, thread_sensitive=True)(Cadastro, id=cad_id)


async def _update_status(cadastro: Cadastro, status: str):
    cadastro.status = status
    await sync_to_async(cadastro.save, thread_sensitive=True)(update_fields=["status"])
    return cadastro


@router.post("/cadastros/{cad_id}/receber", response=CadastroOut)
async def receber(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await _update_status(cadastro, CadastroStatus.EM_TESOURARIA)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/comprovantes", response=CadastroOut)
async def comprovantes(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await _update_status(cadastro, CadastroStatus.AGUARDANDO_COMPROVANTES)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/nuvideo", response=CadastroOut)
async def nuvideo(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await _update_status(cadastro, CadastroStatus.EM_VALIDACAO_NUVIDEO)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/gerar-contrato", response=CadastroOut)
async def gerar_contrato(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await _update_status(cadastro, CadastroStatus.CONTRATO_GERADO)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/assinar", response=CadastroOut)
async def assinar(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await _update_status(cadastro, CadastroStatus.ASSINADO)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }


@router.post("/cadastros/{cad_id}/concluir", response=CadastroOut)
async def concluir(request, cad_id: int):
    cadastro = await _get_cadastro_or_404(cad_id)
    cadastro = await _update_status(cadastro, CadastroStatus.CONCLUIDO)
    return {
        "id": cadastro.id,
        "associado_id": cadastro.associado_id,
        "status": cadastro.status,
        "observacao": cadastro.observacao,
    }
EOF

write_file apps/api/api/v1/sse_router.py <<'EOF'
from ninja import Router
from django.http import StreamingHttpResponse
from infrastructure.cache.redis_client import get_client

router = Router(tags=["sse"])


@router.get("/stream")
def stream(request):
    channel = "events:all"
    client = get_client()
    pubsub = client.pubsub()
    pubsub.subscribe(channel)

    def event_stream():
        yield "retry: 5000\n\n"
        for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield f"data: {data}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    return response
EOF

write_file apps/api/api/v1/router.py <<'EOF'
from ninja import NinjaAPI
from .auth_router import router as auth_router
from .cadastros_router import router as cadastros_router
from .analise_router import router as analise_router
from .tesouraria_router import router as tesouraria_router
from .sse_router import router as sse_router

api = NinjaAPI(title="ABASE v2 API", version="1.0.0")

api.add_router("/auth", auth_router)
api.add_router("/cadastros", cadastros_router)
api.add_router("/analise", analise_router)
api.add_router("/tesouraria", tesouraria_router)
api.add_router("/sse", sse_router)


@api.get("/health")
def health_check(request):
    return {"status": "ok"}
EOF

# --------------------------------------------------------------------------------------
# 8) URLs — hook da API v1 nas urls do projeto
# --------------------------------------------------------------------------------------
write_file apps/api/config/urls_api.py <<'EOF'
from django.contrib import admin
from django.urls import path
from api.v1.router import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
]
EOF

if [ -f apps/api/config/urls.py ]; then
  warn "apps/api/config/urls.py já existe. Inclua manualmente Ninja API se necessário."
fi

# --------------------------------------------------------------------------------------
# 9) Exception handlers (Error Boundary server-side)
# --------------------------------------------------------------------------------------
write_file apps/api/api/exception_handlers.py <<'EOF'
from ninja.errors import ValidationError
from ninja import NinjaAPI


def register_handlers(api: NinjaAPI):
    @api.exception_handler(ValidationError)
    def on_validation_error(request, exc):
        return api.create_response(
            request, {"error": "validation_error", "details": exc.errors}, status=422
        )

    @api.exception_handler(Exception)
    def on_any_error(request, exc):
        return api.create_response(request, {"error": "internal_error"}, status=500)
EOF

# --------------------------------------------------------------------------------------
# 10) Jobs de Importação (Bloco 6) — Celery task
# --------------------------------------------------------------------------------------
write_file apps/api/infrastructure/jobs/imports.py <<'EOF'
from celery import shared_task
import csv
from ...core.models import Associado


@shared_task
def import_associados_csv(path: str) -> int:
    count = 0
    with open(path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            Associado.objects.update_or_create(
                cpf=row["cpf"],
                defaults={
                    "nome": row.get("nome", ""),
                    "email": row.get("email") or None,
                    "telefone": row.get("telefone") or None,
                    "endereco": row.get("endereco") or None,
                },
            )
            count += 1
    return count
EOF

# --------------------------------------------------------------------------------------
# 11) Frontend: SSE hook + ErrorBoundary + UI otimista (exemplo)
# --------------------------------------------------------------------------------------
write_file apps/web/src/hooks/useSSE.ts <<'EOF'
"use client";
import { useEffect, useRef } from "react";

export function useSSE(url: string, onMessage: (data: string) => void) {
  const ref = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(url);
    ref.current = es;
    es.onmessage = (event) => onMessage(event.data);
    es.onerror = () => {
      // errors are logged in devtools; keep silent to avoid noisy UI
    };

    return () => {
      es.close();
    };
  }, [url, onMessage]);

  return ref;
}
EOF

write_file apps/web/src/components/core/ErrorBoundary.tsx <<'EOF'
"use client";
import React from "react";

type Props = {
  children: React.ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown, info: unknown) {
    console.error("ErrorBoundary caught", error, info);
  }

  render() {
    if (this.state.hasError) {
      return <div>Algo deu errado.</div>;
    }

    return this.props.children;
  }
}
EOF

write_file "apps/web/src/app/(dashboard)/cadastros/actions.ts" <<'EOF'
"use server";

export async function submitCadastro(id: number) {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/cadastros/cadastros/${id}/submit`,
    {
      method: "POST",
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new Error("Falha ao submeter cadastro");
  }

  return response.json();
}
EOF

# --------------------------------------------------------------------------------------
# 12) Docs de referência p/ Claude Code (artefato consultável)
# --------------------------------------------------------------------------------------
write_file docs/BLOCO_2_FASE_2.md <<'EOF'
# ABASE v2 — Bloco 2 e Fase 2

## Regras Absolutas
- Nunca usar SQLite.
- Usar Redis para cache/sessões/blacklist.
- JWT de 15 min + Refresh 7 dias; httpOnly cookies no BFF.
- Strategy + Factory + Singleton em Auth.

## Endpoints (principais)
- POST /api/v1/auth/oidc/callback
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me
- POST /api/v1/cadastros/associados
- POST /api/v1/cadastros/cadastros {associado_id}
- POST /api/v1/cadastros/cadastros/{id}/submit
- POST /api/v1/analise/cadastros/{id}/aprovar|pendenciar|cancelar
- POST /api/v1/tesouraria/cadastros/{id}/(receber|comprovantes|nuvideo|gerar-contrato|assinar|concluir)
- GET  /api/v1/sse/stream (SSE canal global)

## SSE
- Backend publica Redis channel `events:all`; frontend consome via EventSource.

## Event Sourcing Light
- Tabela `EventLog(entity_type, entity_id, event_type, payload, actor_id, created_at)`.

## Erros
- Exception handlers em `api/exception_handlers.py`.

## Jobs
- `infrastructure/jobs/imports.py:import_associados_csv(path)` com Celery.

## Segurança
- Lockout pós N tentativas (usar cache keys `failed_attempts:`) — extensível.

## Padrões
- Strategy: `core/auth/strategies.py`
- Factory: criação de tokens (na estratégia) e serviços de domínio centralizados
- Singleton: `AuthenticationManager`
EOF

# --------------------------------------------------------------------------------------
# 13) Compose — serviços Celery (opcional)
# --------------------------------------------------------------------------------------
if [ -f docker-compose.yml ]; then
  append_unique docker-compose.yml "celery:" '
  celery:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
    command: bash -lc "celery -A config worker -l info"
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.development
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./apps/api:/app
    depends_on:
      - api
'
fi

okay "Fase 2 files generated."
