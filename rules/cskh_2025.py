# -*- coding: utf-8 -*-
from __future__ import annotations
from .base import RuleProfile, DayDetail, NightDetail

class CSKH2025(RuleProfile):
    name = "CSKH_2025"

    def day_detail(self, kind: str) -> DayDetail:
        # Thứ 2–6
        if kind == "WEEKDAY":
            # Tổng đài: 1 leader K + 2 CA1 + 4 CA2
            # PGD: 1 K + 1 CA2
            return DayDetail(TD={"K_leader": 1, "CA1": 2, "CA2": 4}, PGD={"K": 1, "CA2": 1})
        # Thứ 7
        if kind == "SAT":
            # Tổng đài: 1 leader K + 2 CA1 + 2 CA2 + 1 K_WHITE
            # PGD: 1 K
            return DayDetail(TD={"K_leader": 1, "CA1": 2, "CA2": 2}, PGD={"K": 1}, K_WHITE=1)
        # Chủ nhật & Lễ
        return DayDetail(TD={"K_leader": 1, "CA1": 1, "CA2": 1}, PGD={})

    def night_detail(self, kind: str) -> NightDetail:
        # Thứ 2–6 & Thứ 7: 1 leader + 2 Đ trắng @ Tổng đài + 2 Đ @ PGD
        if kind in ("WEEKDAY", "SAT"):
            return NightDetail(leader=1, TD_white=2, PGD=2)
        # Chủ nhật & Lễ: không leader, không Đ trắng; 2 Đ @ PGD
        return NightDetail(leader=0, TD_white=0, PGD=2)