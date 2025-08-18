# -*- coding: utf-8 -*-
from __future__ import annotations
import os

# Export các kiểu & profile base
from .base import RuleProfile, DayDetail, NightDetail, SHIFT_DEFS
# ===== NEW: alias tương thích ngược cho placements.py =====
from .types import CREDITS as CREDIT, ShiftCode, Position, DayKind

# Load profile CSKH_2025
from .cskh_2025 import CSKH2025

_PROFILES: dict[str, RuleProfile] = {
    "CSKH_2025": CSKH2025(),
}

def get_profile(name: str | None = None) -> RuleProfile:
    key = (name or os.getenv("SCHEDULE_PROFILE") or "CSKH_2025").strip()
    return _PROFILES.get(key, _PROFILES["CSKH_2025"])

__all__ = [
    "RuleProfile", "DayDetail", "NightDetail", "SHIFT_DEFS",
    "get_profile",
    # enum/types (tuỳ frontend có xài hay không)
    "ShiftCode", "Position", "DayKind",
    # ===== giữ tương thích ngược =====
    "CREDIT",   # alias -> CREDITS
]