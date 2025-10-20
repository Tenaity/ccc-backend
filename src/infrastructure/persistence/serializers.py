"""Base serializer for converting DTOs to API response dictionaries.

This module provides unified serialization patterns to eliminate duplicated
_serialize() methods across API endpoints (50-100 lines saved).
"""

from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


class BaseSerializer:
    """Base class for DTO to dictionary serialization."""

    @staticmethod
    def to_dict(dto: Any, field_mapping: Optional[Dict[str, str]] = None) -> dict:
        """Convert DTO to dictionary with optional field name mapping.

        Args:
            dto: Data transfer object to serialize
            field_mapping: Optional dict mapping DTO field names to API field names

        Returns:
            Dictionary representation of the DTO

        Example:
            field_mapping = {
                "raw_text": "rawText",
                "major_section": "majorSection",
            }
            result = BaseSerializer.to_dict(dto, field_mapping)
        """
        if is_dataclass(dto):
            result = asdict(dto)
        elif hasattr(dto, "__dict__"):
            result = dto.__dict__.copy()
        else:
            result = dict(dto)

        # Apply field mapping if provided
        if field_mapping:
            remapped = {}
            for key, value in result.items():
                api_key = field_mapping.get(key, key)
                remapped[api_key] = value
            return remapped

        return result

    @staticmethod
    def to_list(items: list[T], field_mapping: Optional[Dict[str, str]] = None) -> list[dict]:
        """Convert list of DTOs to list of dictionaries.

        Args:
            items: List of DTOs to serialize
            field_mapping: Optional dict mapping DTO field names to API field names

        Returns:
            List of dictionary representations
        """
        return [BaseSerializer.to_dict(item, field_mapping) for item in items]

    @staticmethod
    def paginated(
        items: list[T],
        page: int,
        page_size: int,
        total: int,
        field_mapping: Optional[Dict[str, str]] = None,
    ) -> dict:
        """Serialize paginated response.

        Args:
            items: List of paginated items
            page: Current page number
            page_size: Number of items per page
            total: Total number of items
            field_mapping: Optional field name mapping

        Returns:
            Paginated response dictionary
        """
        return {
            "items": BaseSerializer.to_list(items, field_mapping),
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @staticmethod
    def filtered_dict(
        dto: Any,
        include_fields: Optional[list[str]] = None,
        exclude_fields: Optional[list[str]] = None,
        field_mapping: Optional[Dict[str, str]] = None,
    ) -> dict:
        """Convert DTO to dictionary with field filtering.

        Args:
            dto: DTO to serialize
            include_fields: If provided, only include these fields
            exclude_fields: If provided, exclude these fields
            field_mapping: Optional field name mapping

        Returns:
            Filtered dictionary representation
        """
        result = BaseSerializer.to_dict(dto)

        if include_fields:
            result = {k: v for k, v in result.items() if k in include_fields}

        if exclude_fields:
            result = {k: v for k, v in result.items() if k not in exclude_fields}

        if field_mapping:
            remapped = {}
            for key, value in result.items():
                api_key = field_mapping.get(key, key)
                remapped[api_key] = value
            return remapped

        return result


class FieldMapping:
    """Builder for field mapping dictionaries."""

    def __init__(self):
        self._mapping: Dict[str, str] = {}

    def add(self, dto_field: str, api_field: str) -> FieldMapping:
        """Add a field mapping."""
        self._mapping[dto_field] = api_field
        return self

    def build(self) -> Dict[str, str]:
        """Build the final mapping dictionary."""
        return self._mapping.copy()

    @staticmethod
    def create() -> FieldMapping:
        """Create a new FieldMapping builder."""
        return FieldMapping()


def serialize_dto(
    dto: T,
    *,
    field_mapping: Optional[Dict[str, str]] = None,
    include_fields: Optional[list[str]] = None,
    exclude_fields: Optional[list[str]] = None,
) -> dict:
    """Convenience function to serialize a single DTO.

    Args:
        dto: DTO to serialize
        field_mapping: Optional field name mapping
        include_fields: Optional list of fields to include
        exclude_fields: Optional list of fields to exclude

    Returns:
        Serialized dictionary
    """
    return BaseSerializer.filtered_dict(
        dto,
        include_fields=include_fields,
        exclude_fields=exclude_fields,
        field_mapping=field_mapping,
    )


def serialize_list(
    items: list[T],
    *,
    field_mapping: Optional[Dict[str, str]] = None,
    include_fields: Optional[list[str]] = None,
    exclude_fields: Optional[list[str]] = None,
) -> list[dict]:
    """Convenience function to serialize a list of DTOs.

    Args:
        items: List of DTOs to serialize
        field_mapping: Optional field name mapping
        include_fields: Optional list of fields to include
        exclude_fields: Optional list of fields to exclude

    Returns:
        List of serialized dictionaries
    """
    result = []
    for item in items:
        serialized = BaseSerializer.filtered_dict(
            item,
            include_fields=include_fields,
            exclude_fields=exclude_fields,
            field_mapping=field_mapping,
        )
        result.append(serialized)
    return result


__all__ = [
    "BaseSerializer",
    "FieldMapping",
    "serialize_dto",
    "serialize_list",
]
