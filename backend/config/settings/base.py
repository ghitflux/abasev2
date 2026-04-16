from datetime import timedelta
from pathlib import Path

from decouple import config

from config.runtime import enforce_mysql_only

BASE_DIR = Path(__file__).resolve().parents[2]


def config_bool(name: str, default: bool = False) -> bool:
    value = config(name, default=None)
    if value is None:
        return default

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on", "debug", "development"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off", "release", "prod", "production"}:
        return False

    raise ValueError(f"Invalid truth value for {name}: {value}")

SECRET_KEY = config("SECRET_KEY", default="change-me")
DEBUG = config_bool("DEBUG", default=False)

# Kill switch do app mobile — ative com APP_MAINTENANCE_MODE=true no servidor
APP_MAINTENANCE_MODE = config_bool("APP_MAINTENANCE_MODE", default=False)
APP_MAINTENANCE_MESSAGE = config(
    "APP_MAINTENANCE_MESSAGE",
    default="O aplicativo está temporariamente indisponível para manutenção. Tente novamente em breve.",
)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,backend",
    cast=lambda value: [item.strip() for item in value.split(",") if item.strip()],
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "django_filters",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_celery_results",
    "core",
    "apps.accounts",
    "apps.associados",
    "apps.contratos",
    "apps.esteira",
    "apps.refinanciamento",
    "apps.tesouraria",
    "apps.importacao",
    "apps.financeiro",
    "apps.relatorios",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DATABASE_NAME", default="abase_v2"),
        "USER": config("DATABASE_USER", default="abase"),
        "PASSWORD": config("DATABASE_PASSWORD", default="abase"),
        "HOST": config("DATABASE_HOST", default="127.0.0.1"),
        "PORT": config("DATABASE_PORT", default="3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

enforce_mysql_only(DATABASES, "config.settings.base")

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
    "apps.accounts.hashers.LegacyLaravelBcryptPasswordHasher",
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Fortaleza"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "apps.accounts.backends.LegacyLaravelUserBackend",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsSetPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ABASE API",
    "DESCRIPTION": "API REST do sistema de gestão de associados ABASE.",
    "VERSION": "1.0.0",
    "ENUM_NAME_OVERRIDES": {
        "AssociadoStatusEnum": "config.spectacular_enums.ASSOCIADO_STATUS",
        "DocumentoTipoEnum": "config.spectacular_enums.DOCUMENTO_TIPO",
        "DocumentoStatusEnum": "config.spectacular_enums.DOCUMENTO_STATUS",
        "EsteiraEtapaEnum": "config.spectacular_enums.ESTEIRA_ETAPA",
        "EsteiraSituacaoEnum": "config.spectacular_enums.ESTEIRA_SITUACAO",
        "PendenciaStatusEnum": "config.spectacular_enums.PENDENCIA_STATUS",
        "DocIssueStatusEnum": "config.spectacular_enums.DOC_ISSUE_STATUS",
        "ContratoStatusEnum": "config.spectacular_enums.CONTRATO_STATUS",
        "CicloStatusEnum": "config.spectacular_enums.CICLO_STATUS",
        "ParcelaStatusEnum": "config.spectacular_enums.PARCELA_STATUS",
        "RefinanciamentoStatusEnum": "config.spectacular_enums.REFINANCIAMENTO_STATUS",
        "ComprovanteTipoEnum": "config.spectacular_enums.COMPROVANTE_TIPO",
        "ComprovantePapelEnum": "config.spectacular_enums.COMPROVANTE_PAPEL",
        "ComprovanteOrigemEnum": "config.spectacular_enums.COMPROVANTE_ORIGEM",
        "ComprovanteStatusValidacaoEnum": (
            "config.spectacular_enums.COMPROVANTE_STATUS_VALIDACAO"
        ),
        "DevolucaoAssociadoTipoEnum": "config.spectacular_enums.DEVOLUCAO_ASSOCIADO_TIPO",
        "ConfirmacaoTipoEnum": "config.spectacular_enums.CONFIRMACAO_TIPO",
        "ConfirmacaoStatusEnum": "config.spectacular_enums.CONFIRMACAO_STATUS",
        "PagamentoStatusEnum": "config.spectacular_enums.PAGAMENTO_STATUS",
        "DespesaStatusEnum": "config.spectacular_enums.DESPESA_STATUS",
        "DespesaTipoEnum": "config.spectacular_enums.DESPESA_TIPO",
        "ArquivoRetornoStatusEnum": "config.spectacular_enums.ARQUIVO_RETORNO_STATUS",
        "ArquivoRetornoFormatoEnum": "config.spectacular_enums.ARQUIVO_RETORNO_FORMATO",
    },
}

_JWT_SIGNING_KEY = config("JWT_SIGNING_KEY", default=None)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_TOKEN_LIFETIME", default=2880, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_REFRESH_TOKEN_LIFETIME", default=10080, cast=int)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Chave de assinatura separada do SECRET_KEY.
    # Trocar JWT_SIGNING_KEY no servidor invalida TODOS os tokens ativos imediatamente.
    **({"SIGNING_KEY": _JWT_SIGNING_KEY} if _JWT_SIGNING_KEY else {}),
}

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:8000,http://127.0.0.1:8000",
    cast=lambda value: [item.strip() for item in value.split(",") if item.strip()],
)

REDIS_URL = config("REDIS_URL", default="redis://redis:6379/0")
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://redis:6379/2"
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
