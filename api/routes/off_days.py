from __future__ import annotations

import calendar
from datetime import date

from flask import Blueprint, jsonify, request

from models import OffDay, SessionLocal, Staff

bp = Blueprint("off_days", __name__)


@bp.get("/api/off")
def list_off_days():
    """List off days for a given month (defaults to current)."""
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    if month < 1 or month > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    print(f"[API] off GET {year}-{month}", flush=True)

    try:
        with SessionLocal() as session:
            rows = (
                session.query(OffDay, Staff)
                .join(Staff, OffDay.staff_id == Staff.id)
                .filter(OffDay.day.between(start, end))
                .all()
            )
            payload = [
                {
                    "id": row.id,
                    "staff_id": row.staff_id,
                    "staff_name": staff.full_name,
                    "day": row.day.isoformat(),
                    "reason": row.reason,
                }
                for row, staff in rows
            ]
            return jsonify(payload)
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


@bp.post("/api/off")
def create_off_day():
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    reason = data.get("reason")

    if staff_id is None or day_str is None:
        return {"error": "staff_id and day required"}, 400

    try:
        staff_id = int(staff_id)
    except Exception:
        return {"error": "staff_id must be int"}, 400

    try:
        day_value = date.fromisoformat(day_str)
    except Exception:
        return {"error": "day must be YYYY-MM-DD"}, 400

    print(f"[API] off POST {staff_id} {day_str}", flush=True)

    try:
        with SessionLocal() as session:
            staff = session.get(Staff, staff_id)
            if not staff:
                return {"error": "Staff not found"}, 404

            existing = (
                session.query(OffDay)
                .filter(OffDay.staff_id == staff_id, OffDay.day == day_value)
                .first()
            )
            if existing:
                return {"id": existing.id, "ok": True}

            record = OffDay(staff_id=staff_id, day=day_value, reason=reason)
            session.add(record)
            session.commit()
            return {"id": record.id, "ok": True}, 201
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


@bp.delete("/api/off/<int:off_id>")
def delete_off_day(off_id: int):
    print(f"[API] off DELETE {off_id}", flush=True)
    try:
        with SessionLocal() as session:
            record = session.get(OffDay, off_id)
            if not record:
                return {"error": "Not found"}, 404
            session.delete(record)
            session.commit()
            return {"ok": True}
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




@bp.get("/api/offdays")
def list_off_days_alias():
    return list_off_days()


@bp.post("/api/offdays")
def create_off_day_alias():
    return create_off_day()


@bp.delete("/api/offdays/<int:off_id>")
def delete_off_day_alias(off_id: int):
    return delete_off_day(off_id)


