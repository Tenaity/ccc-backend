"""Unified error handling decorator for API endpoints.

This module provides a decorator pattern to eliminate repeated exception
handling across all API endpoints, reducing code duplication by 150-200 lines.
"""

from __future__ import annotations

import functools
import logging
from http import HTTPStatus
from typing import Any, Callable, Dict, Optional

from src.domain.exceptions import ConflictError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Helper to format error responses consistently."""

    @staticmethod
    def bad_request(message: str) -> tuple[dict[str, str], int]:
        """Return 400 Bad Request error response."""
        return {"error": message}, HTTPStatus.BAD_REQUEST

    @staticmethod
    def not_found(message: str) -> tuple[dict[str, str], int]:
        """Return 404 Not Found error response."""
        return {"error": message}, HTTPStatus.NOT_FOUND

    @staticmethod
    def conflict(message: str) -> tuple[dict[str, str], int]:
        """Return 409 Conflict error response."""
        return {"error": message}, HTTPStatus.CONFLICT

    @staticmethod
    def internal_error(message: str = "Internal server error") -> tuple[dict[str, str], int]:
        """Return 500 Internal Server Error response."""
        return {"error": message}, HTTPStatus.INTERNAL_SERVER_ERROR


def handle_errors(
    *,
    error_messages: Optional[Dict[type, str]] = None,
    log_success: Optional[Callable] = None,
) -> Callable:
    """Decorator to handle domain exceptions in API endpoints.

    Automatically catches and converts domain exceptions to appropriate HTTP responses,
    reducing duplicated try-except blocks across endpoints.

    Args:
        error_messages: Optional dict mapping exception types to custom error messages
        log_success: Optional callable to log successful operations

    Returns:
        Decorated function with unified error handling

    Example:
        @chatbot_data_bp.get("/<string:record_id>")
        @handle_errors()
        def get_record(record_id: str):
            dto = service.get_record(record_id)
            return jsonify(_serialize(dto))
    """
    error_messages = error_messages or {}

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> tuple[dict, int] | Any:
            try:
                result = func(*args, **kwargs)
                if log_success:
                    log_success()
                return result
            except ValidationError as exc:
                msg = error_messages.get(ValidationError, str(exc))
                logger.warning("Validation error in %s: %s", func.__name__, exc)
                return ErrorResponse.bad_request(msg)
            except NotFoundError as exc:
                msg = error_messages.get(NotFoundError, str(exc))
                logger.warning("Not found error in %s: %s", func.__name__, exc)
                return ErrorResponse.not_found(msg)
            except ConflictError as exc:
                msg = error_messages.get(ConflictError, str(exc))
                logger.warning("Conflict error in %s: %s", func.__name__, exc)
                return ErrorResponse.conflict(msg)
            except Exception as exc:
                logger.exception("Unexpected error in %s: %s", func.__name__, exc)
                return ErrorResponse.internal_error()

        return wrapper

    return decorator


def handle_json_errors(
    *,
    success_status: int = HTTPStatus.OK,
    error_messages: Optional[Dict[type, str]] = None,
) -> Callable:
    """Variant of handle_errors that wraps JSON responses.

    Automatically wraps successful responses in jsonify() while preserving
    error responses from exception handlers.

    Args:
        success_status: HTTP status code for successful responses (default 200)
        error_messages: Optional dict mapping exception types to custom error messages

    Returns:
        Decorated function with unified error handling and JSON wrapping
    """
    from flask import jsonify

    error_messages = error_messages or {}

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = func(*args, **kwargs)
                # If result is a tuple (response, status), return as-is
                if isinstance(result, tuple):
                    return result
                # Wrap dict in jsonify with success status
                if isinstance(result, dict):
                    return jsonify(result), success_status
                return result, success_status
            except ValidationError as exc:
                msg = error_messages.get(ValidationError, str(exc))
                logger.warning("Validation error in %s: %s", func.__name__, exc)
                return {"error": msg}, HTTPStatus.BAD_REQUEST
            except NotFoundError as exc:
                msg = error_messages.get(NotFoundError, str(exc))
                logger.warning("Not found error in %s: %s", func.__name__, exc)
                return {"error": msg}, HTTPStatus.NOT_FOUND
            except ConflictError as exc:
                msg = error_messages.get(ConflictError, str(exc))
                logger.warning("Conflict error in %s: %s", func.__name__, exc)
                return {"error": msg}, HTTPStatus.CONFLICT
            except Exception as exc:
                logger.exception("Unexpected error in %s: %s", func.__name__, exc)
                return {"error": "Internal server error"}, HTTPStatus.INTERNAL_SERVER_ERROR

        return wrapper

    return decorator


__all__ = [
    "handle_errors",
    "handle_json_errors",
    "ErrorResponse",
]
