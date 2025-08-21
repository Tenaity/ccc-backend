# backend/scheduler/estimate.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import calendar
from datetime import date, timedelta

from models import SessionLocal, Staff, Holiday
from rules import get_profile

# Mã ca chuẩn (string) dùng cho estimate/credits
SHIFT_LIST = ["CA1", "CA2", "K", "HC", "Đ", "P"]
CREDIT = {"CA1": 1.0, "CA2": 1.0, "HC": 1.0, "K": 1.25, "Đ": 1.5, "P": 0.0}


def month_last_day(y: int, m: int) -> int:
    return calendar.monthrange(y, m)[1]


def day_kind(d: date, holidays: set[date]) -> str:
    """Xác định loại ngày cho RULE (WEEKDAY/SAT/SUN/HOLIDAY)."""
    if d in holidays:
        return "HOLIDAY"
    wd = d.weekday()  # 0=Mon..6=Sun
    if wd == 5:
        return "SAT"
    if wd == 6:
        return "SUN"
    return "WEEKDAY"


def estimate_month(year: int, month: int):
    """
    Tính nhu cầu (required) dựa trên RULE (enum-based, đã chuẩn hoá key string):

    - Day:  profile.expected_day_counts(kind) ->
        {
          "TD":  {"K": x, "CA1": y, "CA2": z},
          "PGD": {"K": u, "CA2": v}
        }

    - Night: profile.expected_night_counts(kind) ->
        {
          "TD":  {"Đ": a},    # tổng Đ tại Tổng đài (leader + white)
          "PGD": {"Đ": b}     # tổng Đ tại PGD
        }

    Tổng nhu cầu theo mã:
      K   = TD.K + PGD.K
      CA1 = TD.CA1
      CA2 = TD.CA2 + PGD.CA2
      Đ   = Night.TD.Đ + Night.PGD.Đ
      HC, P: không nằm trong rule (để 0 trong estimate tĩnh)
    """
    first = date(year, month, 1)
    last = date(year, month, month_last_day(year, month))

    # ----- REQUIRED (số slot theo mã ca) -----
    req_by_shift = {k: 0 for k in SHIFT_LIST}
    required_credits_by_shift = {k: 0.0 for k in SHIFT_LIST}

    with SessionLocal() as s:
        # Lấy rows Holiday object, đảm bảo .day là instance datetime.date
        holiday_rows = s.query(Holiday).all()

        # Chỉ lấy các ngày nằm trong khoảng tháng (r.day là date, không phải Column)
        holidays: set[date] = {
            r.day for r in holiday_rows
            if isinstance(r.day, date) and (first <= r.day <= last)
        }

        profile = get_profile()

        d = first
        while d <= last:
            kind = day_kind(d, holidays)

            # Nhu cầu theo rule (đã chuẩn hoá sang string-key)
            day_det = profile.expected_day_counts(kind)     # {"TD": {...}, "PGD": {...}}
            night_det = profile.expected_night_counts(kind) # {"TD": {"Đ": a}, "PGD": {"Đ": b}}

            td = day_det.get("TD", {}) or {}
            pgd = day_det.get("PGD", {}) or {}
            n_td = night_det.get("TD", {}) or {}
            n_pgd = night_det.get("PGD", {}) or {}

            # --- Cộng nhu cầu theo mã ---
            # Daytime
            req_by_shift["K"] += int(td.get("K", 0)) + int(pgd.get("K", 0))
            req_by_shift["CA1"] += int(td.get("CA1", 0))
            req_by_shift["CA2"] += int(td.get("CA2", 0)) + int(pgd.get("CA2", 0))

            # Night (gộp leader/white/PGD thành mã "Đ")
            req_by_shift["Đ"] += int(n_td.get("Đ", 0)) + int(n_pgd.get("Đ", 0))

            # HC/P không nằm trong rule (để 0)
            d += timedelta(days=1)

        # ----- CREDITS REQUIRED -----
        required_credits_total = 0.0
        for k in SHIFT_LIST:
            required_credits_by_shift[k] = round(req_by_shift[k] * CREDIT[k], 2)
            required_credits_total += required_credits_by_shift[k]
        required_credits_total = round(required_credits_total, 2)

        # ----- SUPPLY (quota theo staff hiện có) -----
        staff = s.query(Staff).all()
        supply_total = 0.0
        supply_by_staff: dict[int, float] = {}
        delta_by_staff: dict[int, float] = {}

        for r in staff:
            q = float(r.base_quota or 0.0)  # tổng công quy đổi / tháng
            supply_by_staff[r.id] = q
            supply_total += q
        supply_total = round(supply_total, 2)

        # Tạm thời delta_by_staff = quota - 0 (chưa phân phối)
        for r in staff:
            delta_by_staff[r.id] = round((float(r.base_quota or 0.0) - 0.0), 2)

        # ----- KẾT QUẢ -----
        return {
            "ok": True,
            "year": year,
            "month": month,
            "days_in_month": month_last_day(year, month),

            # Nhu cầu theo mã (slot người-ca)
            "required_shifts_total": sum(req_by_shift.values()),
            "required_shifts_by_code": req_by_shift,

            # Nhu cầu công quy đổi
            "required_credits_total": required_credits_total,
            "required_credits_by_shift": required_credits_by_shift,

            # Nguồn cung (quota)
            "supply_total": supply_total,
            "supply_by_staff": supply_by_staff,

            # Chênh lệch
            "delta_total": round(supply_total - required_credits_total, 2),
            "delta_by_staff": delta_by_staff,
        }