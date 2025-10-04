"""Domain representations for Holiday aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(slots=True)
class HolidayDTO:
    id: Optional[int]
    day: date
    name: str
    kind: Optional[str]
    official: bool
    source: Optional[str]


__all__ = ["HolidayDTO"]
