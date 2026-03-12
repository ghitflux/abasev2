from decouple import config

from config.runtime import enforce_mysql_only
from .base import *

DEBUG = True

JWT_ENABLE_TOKEN_BLACKLIST = config(
    "JWT_ENABLE_TOKEN_BLACKLIST",
    default=False,
    cast=bool,
)
if (
    not JWT_ENABLE_TOKEN_BLACKLIST
    and "rest_framework_simplejwt.token_blacklist" in INSTALLED_APPS
):
    INSTALLED_APPS.remove("rest_framework_simplejwt.token_blacklist")
SIMPLE_JWT["ROTATE_REFRESH_TOKENS"] = JWT_ENABLE_TOKEN_BLACKLIST
SIMPLE_JWT["BLACKLIST_AFTER_ROTATION"] = JWT_ENABLE_TOKEN_BLACKLIST

# Executa tasks Celery de forma sincronas (sem necessidade de worker em dev)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

enforce_mysql_only(DATABASES, "config.settings.development")
