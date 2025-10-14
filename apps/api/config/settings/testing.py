from .base import *  # noqa: F401, F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

DATABASES["default"]["NAME"] = os.environ.get("TEST_DATABASE", DATABASES["default"]["NAME"])
