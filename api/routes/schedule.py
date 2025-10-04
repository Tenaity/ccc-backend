from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from models import (
    Assignment,
    Department,
    MonthConfig,
    SessionLocal,
    ShiftPlanDefaults,
    Staff,
)
from rules import get_profile
from scheduler import schedule_month as generate_schedule
from scheduler.estimator import estimate_month
from scheduler.repo import load_holidays
from scheduler.utils import day_kind, month_last_day, ymd
from scheduler.validate import validate_month

from .utils import build_month_config_payload, month_range, parse_year_month

bp = Blueprint("schedule", __name__)


@bp.get("/api/schedule")
def get_schedule():
    """Return assignments for a month with optional department filtering."""

    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400

    dept_id = request.args.get("department_id", type=int)
    start, end = month_range(year, month)

    with SessionLocal() as session:
        if dept_id is not None:
            dept = session.get(Department, dept_id)
            if not dept or not dept.is_active:
                return {"error": "Department not found or inactive"}, 404

        query = (
            select(
                Assignment.day,
                Assignment.shift_code,
                Assignment.position,
                Assignment.staff_id,
                Staff.full_name,
                Staff.role,
                Staff.department_id,
                Department.name,
            )
            .join(Staff, Assignment.staff_id == Staff.id, isouter=True)
            .join(Department, Staff.department_id == Department.id, isouter=True)
            .where(Assignment.day.between(start, end))
            .order_by(Assignment.day, Assignment.shift_code, Assignment.id)
        )

        if dept_id is not None:
            query = query.where(Staff.department_id == dept_id)

        rows = session.execute(query).all()

    items: list[dict] = []
    counts: dict[str, object] = {
        "total": 0,
        "by_shift": defaultdict(int),
        "leaders": {"day": 0, "night": 0},
    }

    for day, shift_code, position, staff_id, full_name, role, row_dept_id, dept_name in rows:
        items.append(
            {
                "day": day.isoformat(),
                "shift_code": shift_code,
                "position": position,
                "staff_id": staff_id,
                "staff_name": full_name,
                "role": role,
                "department_id": row_dept_id,
                "department_name": dept_name,
            }
        )
        counts["total"] += 1
        counts["by_shift"][shift_code] += 1
        if shift_code == "K" and (position or "").upper() == "TD":
            counts["leaders"]["day"] += 1
        if shift_code == "Đ" and (position or "").upper() == "TD":
            counts["leaders"]["night"] += 1

    return jsonify({"items": items, "counts": counts})


@bp.get("/api/schedule/overview")
def schedule_overview():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400

    start, end = month_range(year, month)
    days_in_month = (end - start).days + 1

    with SessionLocal() as session:
        departments = session.execute(
            select(Department).where(Department.is_active.is_(True))
        ).scalars().all()

        rows = session.execute(
            select(
                Assignment.day,
                Assignment.shift_code,
                Assignment.position,
                Department.id,
                Department.name,
                Department.is_active,
            )
            .join(Staff, Assignment.staff_id == Staff.id, isouter=True)
            .join(Department, Staff.department_id == Department.id, isouter=True)
            .where(Assignment.day.between(start, end))
        ).all()

    overview: dict[int, dict[str, object]] = {}
    day_presence: dict[int, set[date]] = defaultdict(set)
    day_shifts: dict[int, dict[str, set[date]]] = defaultdict(lambda: {"day": set(), "night": set()})
    leader_flags: dict[int, dict[str, set[date]]] = defaultdict(lambda: {"day": set(), "night": set()})

    for dept in departments:
        overview[dept.id] = {
            "department_id": dept.id,
            "name": dept.name,
            "shifts": 0,
            "missing_leaders": 0,
            "coverage_rate": 0.0,
        }

    for day, shift_code, position, dept_id, dept_name, is_active in rows:
        if dept_id is None or dept_id not in overview or not is_active:
            continue
        info = overview[dept_id]
        info["shifts"] += 1
        day_presence[dept_id].add(day)
        bucket = "day" if shift_code == "K" else "night" if shift_code == "Đ" else None
        if bucket:
            day_shifts[dept_id][bucket].add(day)
            if (position or "").upper() == "TD":
                leader_flags[dept_id][bucket].add(day)

    for dept_id, info in overview.items():
        covered_days = len(day_presence.get(dept_id, set()))
        info["coverage_rate"] = round(
            covered_days / days_in_month if days_in_month else 0.0,
            4,
        )

        missing = 0
        for bucket in ("day", "night"):
            shift_days = day_shifts[dept_id][bucket]
            leaders = leader_flags[dept_id][bucket]
            for day_value in shift_days:
                if day_value not in leaders:
                    missing += 1
        info["missing_leaders"] = missing

    return jsonify(sorted(overview.values(), key=lambda item: item["name"]))


@bp.get("/api/rules/expected")
def rule_expected():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    profile = get_profile()

    first = ymd(year, month, 1)
    last = ymd(year, month, month_last_day(year, month))

    out: dict[int, dict[str, dict[str, int]]] = {}
    current = first
    holidays = load_holidays(SessionLocal())
    while current <= last:
        kind = day_kind(current, holidays)

        day_counts = profile.expected_day_counts(kind)
        night_counts = profile.expected_night_counts(kind)

        td = day_counts.get("TD", {})
        pgd = day_counts.get("PGD", {})
        n_td = night_counts.get("TD", {}) or {}
        n_pgd = night_counts.get("PGD", {}) or {}

        out[current.day] = {
            "expectedTD": {
                "K": int(td.get("K", 0)),
                "CA1": int(td.get("CA1", 0)),
                "CA2": int(td.get("CA2", 0)),
                "D": int(n_td.get("Đ", 0)),
            },
            "expectedPGD": {
                "K": int(pgd.get("K", 0)),
                "CA2": int(pgd.get("CA2", 0)),
                "D": int(n_pgd.get("Đ", 0)),
            },
        }
        current = current + timedelta(days=1)

    return jsonify({"ok": True, "perDayExpected": out})


@bp.get("/api/schedule/validate")
def schedule_validate():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    if month < 1 or month > 12:
        return jsonify({"ok": False, "error": "month must be 1..12"}), 400
    body = validate_month(year, month)
    return jsonify(body)


@bp.post("/api/schedule/generate")
def schedule_generate():
    payload = request.get_json(silent=True) or {}
    today = date.today()
    year = int(payload.get("year", today.year))
    month = int(payload.get("month", today.month))
    if month < 1 or month > 12:
        return jsonify({"ok": False, "error": "month must be 1..12"}), 400

    shuffle = bool(payload.get("shuffle", False))
    seed = payload.get("seed")
    try:
        seed = int(seed) if seed is not None else None
    except Exception:
        seed = None
    save_flag = bool(payload.get("save", False))
    fill_hc = bool(payload.get("fill_hc", False))

    try:
        with SessionLocal() as session:
            month_config = session.execute(
                select(MonthConfig).where(
                    MonthConfig.year == year, MonthConfig.month == month
                )
            ).scalar_one_or_none()
            shift_defaults = session.execute(
                select(ShiftPlanDefaults).where(
                    ShiftPlanDefaults.year == year,
                    ShiftPlanDefaults.month == month,
                )
            ).scalar_one_or_none()

            missing: dict[str, str] = {}
            if month_config is None:
                missing["month_config"] = (
                    f"No month config found for {year}-{month:02d}"
                )
            if shift_defaults is None:
                missing["shift_plan_defaults"] = (
                    f"No shift plan defaults found for {year}-{month:02d}"
                )
            if missing:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": "Missing configuration",
                            "missing": missing,
                        }
                    ),
                    400,
                )

            config_payload = build_month_config_payload(session, year, month)
            effective_working_days = float(
                config_payload.get("effective_working_days", 0.0)
            )
            shift_plan_defaults_payload = {
                "day_shifts": shift_defaults.day_shifts,
                "night_shifts": shift_defaults.night_shifts,
                "leader_shifts": shift_defaults.leader_shifts,
                "pgd_shifts": shift_defaults.pgd_shifts,
            }
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"Internal error: {exc.__class__.__name__}: {exc}",
                }
            ),
            500,
        )

    try:
        result = generate_schedule(
            year,
            month,
            shuffle=shuffle,
            seed=seed,
            save=save_flag,
            fill_hc=fill_hc,
            effective_working_days=effective_working_days,
            shift_plan_defaults=shift_plan_defaults_payload,
        )
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict):
            body, status = result
            return jsonify(body), int(status)
        if isinstance(result, dict):
            return jsonify(result)
        return jsonify({"ok": False, "error": "Internal error: bad return type"}), 500
    except Exception as exc:  # pragma: no cover - engine failure guard
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"Internal error: {exc.__class__.__name__}: {exc}",
                }
            ),
            500,
        )


@bp.get("/api/schedule/estimate")
def schedule_estimate():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    return jsonify(estimate_month(year, month))
