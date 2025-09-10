"""Utilities to validate pre-booked shifts and off days for a month."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List

from models import SessionLocal, FixedAssignment, OffDay
from scheduler.repo import load_holidays
from scheduler.utils import ymd, month_last_day, day_kind
from rules import get_profile


def validate_month(year: int, month: int) -> Dict[str, object]:
    """Validate fixed assignments against off days and rule capacity.

    Returns a dict with ``ok`` flag and a list of ``conflicts`` describing
    issues. Each conflict is a mapping containing ``day`` (YYYY-MM-DD) and
    extra details depending on the type.
    """
    first = ymd(year, month, 1)
    last = ymd(year, month, month_last_day(year, month))
    conflicts: List[Dict[str, object]] = []

    with SessionLocal() as s:
        fixed_rows = (
            s.query(FixedAssignment)
            .filter(FixedAssignment.day.between(first, last))
            .all()
        )
        off_rows = (
            s.query(OffDay)
            .filter(OffDay.day.between(first, last))
            .all()
        )
        holidays = load_holidays(s)

    off_by_day_staff = {(r.day, r.staff_id) for r in off_rows}
    fixed_by_day: Dict[date, List[FixedAssignment]] = defaultdict(list)
    for r in fixed_rows:
        fixed_by_day[r.day].append(r)
        if (r.day, r.staff_id) in off_by_day_staff:
            conflicts.append(
                {
                    "day": r.day.isoformat(),
                    "type": "OFFDAY_VS_FIXED",
                    "staff_id": r.staff_id,
                    "shift_code": r.shift_code,
                    "position": getattr(r, "position", None),
                }
            )

    for day, items in fixed_by_day.items():
        by_staff: Dict[int, List[FixedAssignment]] = defaultdict(list)
        for r in items:
            by_staff[r.staff_id].append(r)
        for sid, lst in by_staff.items():
            if len(lst) > 1:
                conflicts.append(
                    {
                        "day": day.isoformat(),
                        "type": "DOUBLE_FIXED",
                        "staff_id": sid,
                        "shift_codes": [x.shift_code for x in lst],
                    }
                )

    prof = get_profile()
    d = first
    while d <= last:
        kind = day_kind(d, holidays)
        exp_day = prof.expected_day_counts(kind)
        exp_night = prof.expected_night_counts(kind)
        bucket: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in fixed_by_day.get(d, []):
            pos = getattr(r, "position", "TD") or "TD"
            code = r.shift_code
            bucket[pos][code] += 1
            expected_map = exp_day if code != "Đ" else exp_night
            if int(expected_map.get(pos, {}).get(code, 0)) == 0:
                conflicts.append(
                    {
                        "day": d.isoformat(),
                        "type": "INVALID_POSITION",
                        "staff_id": r.staff_id,
                        "shift_code": code,
                        "position": pos,
                    }
                )
        for pos, codes in bucket.items():
            for code, cnt in codes.items():
                expected_map = exp_day if code != "Đ" else exp_night
                exp = int(expected_map.get(pos, {}).get(code, 0))
                if cnt > exp:
                    conflicts.append(
                        {
                            "day": d.isoformat(),
                            "type": "OVER_CAPACITY",
                            "position": pos,
                            "shift_code": code,
                            "fixed": cnt,
                            "expected": exp,
                        }
                    )
        d += timedelta(days=1)

    return {"ok": not conflicts, "conflicts": conflicts}
