"""Compatibility shim for persistence models.

The project historically exposed SQLAlchemy models at the top-level ``models``
module. As part of the Clean Architecture refactor the concrete persistence
implementation now lives under ``src.infrastructure.persistence``.

To avoid touching every import site (including tests) we simply re-export the
public attributes from the new location.
"""

from src.infrastructure.persistence.models import *  # noqa: F401,F403
from src.infrastructure.persistence import models as _models
from src.infrastructure.persistence.database import get_session_factory, init_db as _init_db


class _SessionLocalFactory:
    """Legacy compatibility wrapper for database sessions.

    Tests and older code expect SessionLocal to be callable and return
    session objects that support the context manager protocol.
    """

    def __call__(self):
        """Get a new session instance."""
        factory = get_session_factory()
        return factory()


# Create the singleton instance
SessionLocal = _SessionLocalFactory()


def init_db():
    """Initialize database tables."""
    return _init_db()


__all__ = getattr(_models, "__all__", []) + ["SessionLocal", "init_db"]
