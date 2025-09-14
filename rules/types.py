# backend/rules/types.py
from __future__ import annotations

from enum import Enum


class ShiftCode(str, Enum):
    CA1 = "CA1"
    CA2 = "CA2"
    K = "K"
    HC = "HC"
    D = "Đ"  # night shift
    P = "P"  # placeholder/absent/other (0 credit)

    @classmethod
    def from_str(cls, s: str) -> "ShiftCode":
        for m in cls:
            if m.value == s:
                return m
        raise ValueError(f"Unknown ShiftCode: {s}")


class Position(str, Enum):
    TD = "TD"  # Tổng đài
    PGD = "PGD"  # Phòng giao dịch


class DayKind(str, Enum):
    WEEKDAY = "WEEKDAY"
    SAT = "SAT"
    SUN = "SUN"
    HOLIDAY = "HOLIDAY"


CREDITS = {
    ShiftCode.CA1: 1.0,
    ShiftCode.CA2: 1.0,
    ShiftCode.HC: 1.0,
    ShiftCode.K: 1.25,
    ShiftCode.D: 1.5,
    ShiftCode.P: 0.0,
}
