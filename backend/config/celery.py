import os

from celery import Celery

from config.runtime import configure_local_mysqlclient

configure_local_mysqlclient()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("abase_v2")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
