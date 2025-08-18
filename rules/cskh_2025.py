# backend/rules/cskh_2025.py
from __future__ import annotations
from .base import RuleProfile, DayDetail, NightDetail
from .types import DayKind, ShiftCode

class CSKH2025(RuleProfile):
    name = "CSKH_2025"

    def day_detail(self, kind: DayKind | str) -> DayDetail:
        k = DayKind(kind) if isinstance(kind, str) else kind

        if k == DayKind.WEEKDAY:
            # TD: 1 K_leader + 2 CA1 + 4 CA2
            # PGD: 1 K + 1 CA2
            return DayDetail(
                TD={"K_leader": 1, "CA1": 2, "CA2": 4},
                PGD={ShiftCode.K: 1, ShiftCode.CA2: 1},
                K_WHITE=0,
            )
        if k == DayKind.SAT:
            # TD: 1 K_leader + 2 CA1 + 2 CA2 + K_WHITE (1)
            # PGD: 1 K
            return DayDetail(
                TD={"K_leader": 1, "CA1": 2, "CA2": 2},
                PGD={ShiftCode.K: 1},
                K_WHITE=1,
            )
        # SUN / HOLIDAY
        return DayDetail(
            TD={"K_leader": 1, "CA1": 1, "CA2": 1},
            PGD={},  # none at PGD
            K_WHITE=0,
        )

    def night_detail(self, kind: DayKind | str) -> NightDetail:
        k = DayKind(kind) if isinstance(kind, str) else kind

        if k in (DayKind.WEEKDAY, DayKind.SAT):
            # Night: TD leader 1 + 2 TD_WHITE + 2 PGD
            return NightDetail(leader=1, TD_white=2, PGD=2)

        # SUN / HOLIDAY: 0 leader, 0 TD_WHITE, 2 PGD
        return NightDetail(leader=0, TD_white=0, PGD=2)