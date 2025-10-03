"""Shared constants for API calculations."""
from __future__ import annotations

BASE_HOURS_PER_CREDIT = 8.0

SHIFT_CREDIT = {
    "CA1": 1,
    "CA2": 1,
    "K": 1.25,
    "Đ": 1.5,
    "HC": 1,
    "P": 0,
}

SHIFT_HOURS = {code: credit * BASE_HOURS_PER_CREDIT for code, credit in SHIFT_CREDIT.items()}

NIGHT_SHIFT_CODES = {"Đ"}

DEFAULT_MAX_HOURS_PER_STAFF = 208.0
