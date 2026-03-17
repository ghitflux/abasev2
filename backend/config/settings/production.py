from config.runtime import enforce_mysql_only
from .base import *

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

enforce_mysql_only(DATABASES, "config.settings.production")
