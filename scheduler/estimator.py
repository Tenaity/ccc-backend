# backend/estimate.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Dict

from models import SessionLocal, Staff, Holiday
from rules import get_profile
from scheduler.utils import ymd, month_last_day
from scheduler.utils import day_kind as kind_of_day  # dùng hàm đã có
from rules.base import CREDIT  # K=1.25, CA1=1, CA2=1, Đ=1.5, HC=1, P=0

@dataclass
class Totals:
    counts: Dict[str, int]
    credits: float

def estimate_month(year: int, month: int):
    first = ymd(year, month, 1)
    last  = ymd(year, month, month_last_day(year, month))

    prof = get_profile()

    # --- holidays chỉ trong THÁNG ---
    with SessionLocal() as s:
        holidays = {r.day for r in s.query(Holiday).all() if first <= r.day <= last}
        # supply = tổng base_quota của staff active (>0)
        supply_credits = sum(float(x.base_quota or 0.0) for x in s.query(Staff).all() if float(x.base_quota or 0) > 0)

    # --- demand (đếm theo NGÀY trong tháng) ---
    counts = {"K":0, "CA1":0, "CA2":0, "Đ":0, "HC":0, "P":0}
    d = first
    while d <= last:
        k = kind_of_day(d, holidays)  # "WEEKDAY" | "SAT" | "SUN" | "HOLIDAY"

        # Day detail
        dd = prof.day_detail(k)
        # TD
        counts["K"]   += dd.TD.get("K_leader", 0)  # K leader ở TD
        counts["CA1"] += dd.TD.get("CA1", 0)
        counts["CA2"] += dd.TD.get("CA2", 0)
        # PGD
        counts["K"]   += dd.PGD.get("K", 0)
        counts["CA2"] += dd.PGD.get("CA2", 0)
        # K_WHITE (tính là K công 1.25)
        counts["K"]   += getattr(dd, "K_WHITE", 0)

        # Night detail
        nd = prof.night_detail(k)
        counts["Đ"] += (nd.leader + nd.TD_white + nd.PGD)

        d += timedelta(days=1)

    # credits demand
    credits = (
        counts["K"]   * CREDIT["K"]   +
        counts["CA1"] * CREDIT["CA1"] +
        counts["CA2"] * CREDIT["CA2"] +
        counts["Đ"]   * CREDIT["Đ"]
        # HC/P nếu có rule riêng thì cộng thêm
    )

    return {
        "ok": True,
        "month": f"{year}-{str(month).zfill(2)}",
        "demand": {"counts": counts, "credits": round(credits, 2)},
        "supply": {"credits": round(supply_credits, 2)},
        "delta":  round(supply_credits - credits, 2),
    }