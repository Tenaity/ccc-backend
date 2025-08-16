# backend/scheduler/estimate.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import calendar
from datetime import date, timedelta
from collections import defaultdict

from models import SessionLocal, Staff, Holiday
from rules import get_profile

SHIFT_LIST = ["CA1", "CA2", "K", "HC", "Đ", "P"]
CREDIT = {"CA1":1.0, "CA2":1.0, "HC":1.0, "K":1.25, "Đ":1.5, "P":0.0}

def month_last_day(y:int, m:int) -> int:
    return calendar.monthrange(y, m)[1]

def day_kind(d: date, holidays: set[date]) -> str:
    if d in holidays:
        return "HOLIDAY"
    wd = d.weekday()  # 0=Mon..6=Sun
    if wd == 5: return "SAT"
    if wd == 6: return "SUN"
    return "WEEKDAY"

def estimate_month(year: int, month: int):
    first = date(year, month, 1)
    last  = date(year, month, month_last_day(year, month))

    req_by_shift = {k: 0 for k in SHIFT_LIST}
    required_credits_by_shift = {k: 0.0 for k in SHIFT_LIST}
    supply_by_staff: dict[int, float] = {}
    delta_by_staff: dict[int, float] = {}

    with SessionLocal() as s:
        # holidays của THÁNG
        holidays = {r.day for r in s.query(Holiday).all() if (r.day >= first and r.day <= last)}

        profile = get_profile()  # CSKH_2025
        # Nhu cầu theo từng ngày
        d = first
        while d <= last:
            kind = day_kind(d, holidays)
            day_det = profile.day_detail(kind)
            night_det = profile.night_detail(kind)

            # TD (ngày)
            req_by_shift["K"]   += day_det.TD.get("K_leader", 0)  # K leader tại tổng đài
            req_by_shift["CA1"] += day_det.TD.get("CA1", 0)
            req_by_shift["CA2"] += day_det.TD.get("CA2", 0)
            # PGD (ngày)
            req_by_shift["K"]   += day_det.PGD.get("K", 0)
            req_by_shift["CA2"] += day_det.PGD.get("CA2", 0)
            # K trắng T7: vẫn là mã K
            req_by_shift["K"]   += getattr(day_det, "K_WHITE", 0) or 0

            # Đêm
            # leader + TD_WHITE + PGD đều là mã "Đ"
            req_by_shift["Đ"]   += (night_det.leader or 0) + (night_det.TD_white or 0) + (night_det.PGD or 0)

            d += timedelta(days=1)

        # Quy đổi công theo trọng số
        required_credits_total = 0.0
        for k in SHIFT_LIST:
            required_credits_by_shift[k] = round(req_by_shift[k] * CREDIT[k], 2)
            required_credits_total += required_credits_by_shift[k]
        required_credits_total = round(required_credits_total, 2)

        # Nguồn cung: tổng quota tháng theo nhân sự hiện có
        staff = s.query(Staff).all()
        supply_total = 0.0
        for r in staff:
            # base_quota là tổng công quy đổi/ tháng
            q = float(r.base_quota or 0.0)
            supply_by_staff[r.id] = q
            supply_total += q
        supply_total = round(supply_total, 2)

        # Delta theo nhân sự: (quota - 0 hiện dùng cho estimate tĩnh)
        for r in staff:
            delta_by_staff[r.id] = round((float(r.base_quota or 0.0) - 0.0), 2)

        return {
            "ok": True,
            "year": year, "month": month,
            "days_in_month": month_last_day(year, month),
            "required_shifts_total": sum(req_by_shift.values()),
            "required_shifts_by_code": req_by_shift,                 # số lượng người/slot theo mã
            "required_credits_total": required_credits_total,        # tổng công quy đổi
            "required_credits_by_shift": required_credits_by_shift,  # công quy đổi theo mã
            "supply_total": supply_total,                            # tổng cung công (quota)
            "supply_by_staff": supply_by_staff,                      # quota theo staff
            "delta_total": round(supply_total - required_credits_total, 2),
            "delta_by_staff": delta_by_staff,
        }