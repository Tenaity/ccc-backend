# -*- coding: utf-8 -*-
from __future__ import annotations

import os

# Export các kiểu & profile base
from .base import SHIFT_DEFS, DayDetail, NightDetail, RuleProfile

# Load profile CSKH_2025
from .cskh_2025 import CSKH2025

# Alias tương thích ngược
from .types import CREDITS as CREDIT
from .types import DayKind, Position, ShiftCode

_PROFILES: dict[str, RuleProfile] = {
    "CSKH_2025": CSKH2025(),
}


def get_profile(name: str | None = None) -> RuleProfile:
    key = (name or os.getenv("SCHEDULE_PROFILE") or "CSKH_2025").strip()
    return _PROFILES.get(key, _PROFILES["CSKH_2025"])


__all__ = [
    "RuleProfile",
    "DayDetail",
    "NightDetail",
    "SHIFT_DEFS",
    "get_profile",
    "ShiftCode",
    "Position",
    "DayKind",
    "CREDIT",
]
