"""Common validation utilities for reducing code duplication.

This module provides reusable validators and normalizers for common
validation patterns across services (dates, integers, months, codes, etc.).
"""

from __future__ import annotations

from datetime import date

from src.domain.exceptions import ValidationError


def validate_date_iso(value: str | None, field_name: str = "date") -> date:
    """Parse and validate ISO format date string.

    Args:
        value: Date string in ISO format (YYYY-MM-DD)
        field_name: Field name for error message

    Returns:
        Parsed date object

    Raises:
        ValidationError: If date format is invalid
    """
    if not value:
        raise ValidationError(f"{field_name} is required")
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"{field_name} must be in ISO format (YYYY-MM-DD)") from exc


def validate_month_range(month: int) -> None:
    """Validate month is in valid range 1-12.

    Args:
        month: Month value

    Raises:
        ValidationError: If month is invalid
    """
    if not isinstance(month, int) or month < 1 or month > 12:
        raise ValidationError("month must be an integer between 1 and 12")


def validate_year(year: int) -> None:
    """Validate year is reasonable (1900-2100).

    Args:
        year: Year value

    Raises:
        ValidationError: If year is invalid
    """
    if not isinstance(year, int) or year < 1900 or year > 2100:
        raise ValidationError("year must be an integer between 1900 and 2100")


def validate_integer(value: str | int | None, field_name: str, *, min_val: int | None = None, max_val: int | None = None) -> int:
    """Convert and validate integer value.

    Args:
        value: Value to convert (can be string or int)
        field_name: Field name for error message
        min_val: Optional minimum value (inclusive)
        max_val: Optional maximum value (inclusive)

    Returns:
        Validated integer

    Raises:
        ValidationError: If conversion or validation fails
    """
    if value is None or value == "":
        raise ValidationError(f"{field_name} is required")
    try:
        result = int(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc

    if min_val is not None and result < min_val:
        raise ValidationError(f"{field_name} must be >= {min_val}")
    if max_val is not None and result > max_val:
        raise ValidationError(f"{field_name} must be <= {max_val}")

    return result


def validate_float(value: str | float | None, field_name: str = "price") -> float | None:
    """Convert and validate float value.

    Args:
        value: Value to convert (can be string, float, or None)
        field_name: Field name for error message

    Returns:
        Validated float or None if input is None/empty

    Raises:
        ValidationError: If conversion fails
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"{field_name} must be numeric") from exc


def normalize_code(value: str | None) -> str:
    """Normalize code by stripping and converting to uppercase.

    Args:
        value: Code string (can be None)

    Returns:
        Normalized code in uppercase
    """
    return (value or "").strip().upper()


def normalize_string(value: str | None) -> str:
    """Normalize string by stripping whitespace.

    Args:
        value: String value (can be None)

    Returns:
        Stripped string
    """
    return (value or "").strip()


def validate_pagination(page: int, page_size: int, *, max_page_size: int = 200) -> tuple[int, int]:
    """Validate pagination parameters.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        max_page_size: Maximum allowed page size

    Returns:
        Tuple of (page, page_size)

    Raises:
        ValidationError: If parameters are invalid
    """
    if page < 1:
        raise ValidationError("page must be >= 1")
    if page_size < 1 or page_size > max_page_size:
        raise ValidationError(f"page_size must be between 1 and {max_page_size}")
    return page, page_size


__all__ = [
    "validate_date_iso",
    "validate_month_range",
    "validate_year",
    "validate_integer",
    "validate_float",
    "normalize_code",
    "normalize_string",
    "validate_pagination",
]
