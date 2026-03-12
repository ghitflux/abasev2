import os

from django.core.wsgi import get_wsgi_application

from config.runtime import configure_local_mysqlclient

configure_local_mysqlclient()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

application = get_wsgi_application()
