"""Compatibility shim for persistence models.

The project historically exposed SQLAlchemy models at the top-level ``models``
module. As part of the Clean Architecture refactor the concrete persistence
implementation now lives under ``src.infrastructure.persistence``.

To avoid touching every import site (including tests) we simply re-export the
public attributes from the new location.
"""

from src.infrastructure.persistence.models import *  # noqa: F401,F403
from src.infrastructure.persistence import models as _models

__all__ = getattr(_models, "__all__", [])
