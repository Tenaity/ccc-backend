"""Database query helper utilities for reducing code duplication.

This module provides common database query patterns used across services
to eliminate repetitive code for fetching, existence checking, and filtering.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError

# Type variable for generic query helpers
T = TypeVar("T")


class QueryHelper(Generic[T]):
    """Base query helper for common database operations."""

    def __init__(self, model_class: Type[T]):
        self.model_class = model_class

    def get_or_404(self, session: Session, pk: Any) -> T:
        """Fetch entity by primary key or raise NotFoundError.

        Args:
            session: SQLAlchemy session
            pk: Primary key value

        Returns:
            The model instance

        Raises:
            NotFoundError: If entity not found
        """
        row = session.get(self.model_class, pk)
        if not row:
            model_name = self.model_class.__name__
            raise NotFoundError(f"{model_name} not found")
        return row

    def exists_or_error(self, session: Session, where_clause: Any, error_msg: str) -> bool:
        """Check if entity exists with given condition or raise error.

        Args:
            session: SQLAlchemy session
            where_clause: SQLAlchemy where clause
            error_msg: Error message if entity exists

        Raises:
            ConflictError: If entity matches condition (delegated to caller)

        Returns:
            True if exists, raises otherwise
        """
        from src.domain.exceptions import ConflictError

        query = select(self.model_class).where(where_clause)
        result = session.execute(query).scalar_one_or_none()
        if result:
            raise ConflictError(error_msg)
        return False

    def find_one_or_none(self, session: Session, where_clause: Any) -> Optional[T]:
        """Fetch single entity by condition or None if not found.

        Args:
            session: SQLAlchemy session
            where_clause: SQLAlchemy where clause

        Returns:
            Model instance or None
        """
        query = select(self.model_class).where(where_clause)
        return session.execute(query).scalar_one_or_none()

    def find_all(
        self,
        session: Session,
        where_clause: Any = None,
        order_by: Any = None,
    ) -> List[T]:
        """Fetch multiple entities with optional filtering and ordering.

        Args:
            session: SQLAlchemy session
            where_clause: Optional SQLAlchemy where clause
            order_by: Optional SQLAlchemy order_by clause

        Returns:
            List of model instances
        """
        query = select(self.model_class)
        if where_clause is not None:
            query = query.where(where_clause)
        if order_by is not None:
            query = query.order_by(order_by)
        return session.execute(query).scalars().all()

    def count(self, session: Session, where_clause: Any = None) -> int:
        """Count entities matching condition.

        Args:
            session: SQLAlchemy session
            where_clause: Optional SQLAlchemy where clause

        Returns:
            Count of matching entities
        """
        from sqlalchemy import func

        query = select(func.count(self.model_class.id))
        if where_clause is not None:
            query = query.where(where_clause)
        return session.execute(query).scalar() or 0


def date_range_between(model_field: Any, start: date, end: date) -> Any:
    """Create a between clause for date range filtering.

    Args:
        model_field: SQLAlchemy column to filter
        start: Start date (inclusive)
        end: End date (inclusive)

    Returns:
        SQLAlchemy between clause
    """
    return model_field.between(start, end)


def string_normalize(value: Optional[str], uppercase: bool = False) -> str:
    """Normalize string input by stripping whitespace.

    Args:
        value: Input string (can be None)
        uppercase: If True, convert to uppercase

    Returns:
        Normalized string
    """
    result = (value or "").strip()
    if uppercase:
        result = result.upper()
    return result


__all__ = [
    "QueryHelper",
    "date_range_between",
    "string_normalize",
]
