"""Domain-level exception types."""


class DomainError(Exception):
    """Base class for domain-specific errors."""


class NotFoundError(DomainError):
    """Raised when an entity cannot be located."""


class ConflictError(DomainError):
    """Raised when creating/updating would violate a uniqueness constraint."""


class ValidationError(DomainError):
    """Raised when incoming data fails validation rules."""


__all__ = [
    "DomainError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
]
