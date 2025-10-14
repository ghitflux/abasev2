"""Authentication package exposing strategy factory and manager."""

from .manager import AuthenticationManager
from .strategies import AuthStrategy, Credentials, OIDCStrategy, JWTStrategy, LocalStrategy
from .permissions import require_permissions, Role, Permission
from .factories import TokenFactory, SessionFactory

__all__ = [
    "AuthenticationManager",
    "AuthStrategy",
    "Credentials",
    "OIDCStrategy",
    "JWTStrategy",
    "LocalStrategy",
    "require_permissions",
    "Role",
    "Permission",
    "TokenFactory",
    "SessionFactory",
]
