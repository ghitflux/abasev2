try:
    from .celery import app as celery_app
except ImportError:  # pragma: no cover - optional celery dependency
    celery_app = None

__all__ = ("celery_app",)
