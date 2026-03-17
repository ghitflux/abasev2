import os

from django.core.asgi import get_asgi_application

from config.runtime import configure_local_mysqlclient

configure_local_mysqlclient()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

application = get_asgi_application()
