# backend/rules/cskh_2025.py
from __future__ import annotations

from .base import DayDetail, NightDetail, RuleProfile
from .types import DayKind, ShiftCode


class CSKH2025(RuleProfile):
    name = "CSKH_2025"

    def day_detail(self, kind: DayKind | str) -> DayDetail:
        k = DayKind(kind) if isinstance(kind, str) else kind

        if k == DayKind.WEEKDAY:
            # T2–T6
            return DayDetail(
                TD={ShiftCode.K: 1, ShiftCode.CA1: 2, ShiftCode.CA2: 4},
                PGD={ShiftCode.K: 1, ShiftCode.CA2: 1},  # K đỏ trực chatbot
            )
        if k == DayKind.SAT:
            # Thứ 7
            return DayDetail(
                TD={ShiftCode.K: 1, ShiftCode.CA1: 2, ShiftCode.CA2: 2},
                PGD={
                    ShiftCode.K: 2
                },  # 1 K “đỏ trực chatbot” + 1 K “trắng” (engine xác định position)
            )
        # CN / Lễ
        return DayDetail(
            TD={ShiftCode.K: 1, ShiftCode.CA1: 1, ShiftCode.CA2: 1},
            PGD={},
        )

    def night_detail(self, kind: DayKind | str) -> NightDetail:
        k = DayKind(kind) if isinstance(kind, str) else kind

        if k in (DayKind.WEEKDAY, DayKind.SAT):
            # Đêm T2–T7: 1 Đ leader, 2 Đ trắng, 2 Đ PGD
            # Ở đây chỉ định số lượng ca Đ chung, vị trí (leader/white/PGD) để engine phân
            return NightDetail(
                TD={ShiftCode.D: 3},  # gồm 1 leader + 2 trắng
                PGD={ShiftCode.D: 2},  # 2 PGD
            )
        # CN / Lễ: chỉ có 2 PGD
        # Ở đây chỉ định số lượng ca Đ PGD, không có trưởng cả cho ngày chủ nhật
        return NightDetail(
            TD={},
            PGD={ShiftCode.D: 2},
        )
