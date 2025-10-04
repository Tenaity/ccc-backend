"""Domain representations for Department aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class DepartmentDTO:
    id: int
    name: str
    code: str
    color: str
    icon: str
    description: Optional[str]
    is_active: bool
    settings: dict
    staff_count: Optional[int] = None
    shift_count: Optional[int] = None


__all__ = ["DepartmentDTO"]
