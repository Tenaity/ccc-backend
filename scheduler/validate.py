"""Utilities to validate pre-booked shifts and off days for a month."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import DefaultDict, Dict, List

from models import SessionLocal, FixedAssignment, OffDay, Assignment, Staff
from scheduler.repo import load_holidays
from scheduler.utils import ymd, month_last_day, day_kind
from rules import get_profile


def validate_month(year: int, month: int) -> Dict[str, object]:
    """Validate fixed assignments against off days and rule capacity.

    Returns a dict with ``ok`` flag and grouped ``conflicts`` describing
    issues. Keys in ``conflicts`` denote conflict type.
    """
    first = ymd(year, month, 1)
    last = ymd(year, month, month_last_day(year, month))
    conflicts: DefaultDict[str, List[Dict[str, object]]] = defaultdict(list)

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
        assign_rows = (
            s.query(
                Assignment.day,
                Assignment.staff_id,
                Assignment.shift_code,
                Assignment.position,
                Staff.role,
            )
            .join(Staff, Assignment.staff_id == Staff.id, isouter=True)
            .filter(Assignment.day.between(first, last))
            .all()
        )
        holidays = load_holidays(s)

    off_by_day_staff = {(r.day, r.staff_id) for r in off_rows}
    fixed_by_day: Dict[date, List[FixedAssignment]] = defaultdict(list)
    for r in fixed_rows:
        fixed_by_day[r.day].append(r)
        if (r.day, r.staff_id) in off_by_day_staff:
            conflicts["offday_vs_fixed"].append(
                {
                    "day": r.day.isoformat(),
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
                conflicts["double_fixed"].append(
                    {
                        "day": day.isoformat(),
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
                conflicts["invalid_position"].append(
                    {
                        "day": d.isoformat(),
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
                    conflicts["over_capacity"].append(
                        {
                            "day": d.isoformat(),
                            "position": pos,
                            "shift_code": code,
                            "fixed": cnt,
                            "expected": exp,
                        }
                    )
        d += timedelta(days=1)

    # ---- leader duplicates in assignments ----
    leader_day: Dict[date, List[int]] = defaultdict(list)
    leader_night: Dict[date, List[int]] = defaultdict(list)
    for day, staff_id, code, pos, role in assign_rows:
        if code == "K" and (pos or "") == "TD":
            leader_day[day].append(staff_id)
        if code == "Đ" and (pos or "") == "TD" and role == "TC":
            leader_night[day].append(staff_id)
    for day, ids in leader_day.items():
        if len(ids) > 1:
            conflicts["leader_day_dup"].append({"day": day.isoformat(), "ids": ids})
    for day, ids in leader_night.items():
        if len(ids) > 1:
            conflicts["leader_night_dup"].append({"day": day.isoformat(), "ids": ids})

    assign_set = {
        (day, staff_id, code, (pos or "TD"))
        for day, staff_id, code, pos, _ in assign_rows
    }
    for r in fixed_rows:
        pos = getattr(r, "position", "TD") or "TD"
        key = (r.day, r.staff_id, r.shift_code, pos)
        if key not in assign_set:
            conflicts["unfulfilled_fixed"].append(
                {
                    "day": r.day.isoformat(),
                    "staff_id": r.staff_id,
                    "shift_code": r.shift_code,
                    "position": pos,
                }
            )

    for key in (
        "offday_vs_fixed",
        "double_fixed",
        "invalid_position",
        "over_capacity",
        "leader_day_dup",
        "leader_night_dup",
        "unfulfilled_fixed",
    ):
        conflicts.setdefault(key, [])

    ok = not any(conflicts.values())
    return {"ok": ok, "conflicts": dict(conflicts)}
