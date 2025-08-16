# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

Shift = str  # "K" | "CA1" | "CA2" | "HC" | "Đ" | "P"
Position = str | None  # "TD" | "PGD" | "K_WHITE" | "D_WHITE" | None
DayKind = str  # "WEEKDAY" | "SAT" | "SUN" | "HOLIDAY"

CREDIT: Dict[Shift, float] = {"CA1": 1, "CA2": 1, "HC": 1, "K": 1.25, "Đ": 1.5, "P": 0}

# Các mã ca để API /api/shifts và UI dùng
SHIFT_DEFS = ["CA1", "CA2", "K", "HC", "Đ", "P"]

@dataclass(frozen=True)
class DayDetail:
    TD: Dict[str, int]        # {"K_leader":1, "CA1":2, "CA2":4}
    PGD: Dict[Shift, int]     # {"K":1, "CA2":1}
    K_WHITE: int = 0          # 1 on Saturday

@dataclass(frozen=True)
class NightDetail:
    leader: int    # số trưởng ca đêm (Đ@TD)
    TD_white: int  # số Đ trắng tại tổng đài (Đ@D_WHITE)
    PGD: int       # số Đ tại PGD (Đ@PGD)

class RuleProfile:
    """Interface cho profile phòng ban."""
    name: str = "BASE"

    def day_detail(self, kind: DayKind) -> DayDetail:
        raise NotImplementedError

    def night_detail(self, kind: DayKind) -> NightDetail:
        raise NotImplementedError

    def credit(self) -> Dict[Shift, float]:
        return CREDIT