"""API routers grouped by domain."""

from . import auth, cadastros, analise, tesouraria, relatorios, health

__all__ = ["auth", "cadastros", "analise", "tesouraria", "relatorios", "health"]
