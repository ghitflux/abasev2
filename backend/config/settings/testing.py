from decouple import config

from config.runtime import enforce_mysql_only
from .base import *

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
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

DATABASES["default"]["USER"] = config("TEST_DATABASE_USER", default="root")
DATABASES["default"]["PASSWORD"] = config(
    "TEST_DATABASE_PASSWORD",
    default=config("DATABASE_PASSWORD", default="abase"),
)
DATABASES["default"]["NAME"] = config("TEST_DATABASE_NAME", default="test_abase_v2")

enforce_mysql_only(DATABASES, "config.settings.testing")
