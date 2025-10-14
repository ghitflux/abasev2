class DomainError(Exception):
    """Base exception for predictable domain failures."""


class ValidationError(DomainError):
    """Raised when business rules are violated."""
