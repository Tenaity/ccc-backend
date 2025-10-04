from __future__ import annotations

import calendar
from datetime import date

from flask import Blueprint, jsonify, request

from models import FixedAssignment, SessionLocal, Staff

bp = Blueprint("fixed_assignments", __name__)


@bp.get("/api/fixed")
def list_fixed_assignments():
    """List fixed assignments for a given month."""
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    if month < 1 or month > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    try:
        with SessionLocal() as session:
            rows = (
                session.query(FixedAssignment, Staff)
                .join(Staff, FixedAssignment.staff_id == Staff.id)
                .filter(FixedAssignment.day.between(start, end))
                .all()
            )
            payload = [
                {
                    "id": record.id,
                    "staff_id": record.staff_id,
                    "staff_name": staff.full_name,
                    "day": record.day.isoformat(),
                    "shift_code": record.shift_code,
                    "position": record.position,
                }
                for record, staff in rows
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


@bp.post("/api/fixed")
def create_fixed_assignment():
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    shift_code = data.get("shift_code")
    position = data.get("position")

    if staff_id is None or day_str is None or shift_code is None:
        return {"error": "staff_id, day, shift_code required"}, 400

    try:
        staff_id = int(staff_id)
    except Exception:
        return {"error": "staff_id must be int"}, 400

    try:
        day_value = date.fromisoformat(day_str)
    except Exception:
        return {"error": "day must be YYYY-MM-DD"}, 400

    try:
        with SessionLocal() as session:
            staff = session.get(Staff, staff_id)
            if not staff:
                return {"error": "Staff not found"}, 404

            record = FixedAssignment(
                staff_id=staff_id,
                day=day_value,
                shift_code=shift_code,
                position=position,
            )
            session.add(record)
            session.commit()
            item = {
                "id": record.id,
                "staff_id": record.staff_id,
                "staff_name": staff.full_name,
                "day": record.day.isoformat(),
                "shift_code": record.shift_code,
                "position": record.position,
            }
            return {"ok": True, "item": item}, 201
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


@bp.put("/api/fixed/<int:fix_id>")
def update_fixed_assignment(fix_id: int):
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    shift_code = data.get("shift_code")
    position = data.get("position")

    try:
        with SessionLocal() as session:
            record = session.get(FixedAssignment, fix_id)
            if not record:
                return {"error": "Not found"}, 404

            if staff_id is not None:
                try:
                    staff_id = int(staff_id)
                except Exception:
                    return {"error": "staff_id must be int"}, 400
                staff = session.get(Staff, staff_id)
                if not staff:
                    return {"error": "Staff not found"}, 404
                record.staff_id = staff_id
            else:
                staff = record.staff

            if day_str is not None:
                try:
                    record.day = date.fromisoformat(day_str)
                except Exception:
                    return {"error": "day must be YYYY-MM-DD"}, 400

            if shift_code is not None:
                record.shift_code = shift_code
            if position is not None:
                record.position = position

            session.commit()
            item = {
                "id": record.id,
                "staff_id": record.staff_id,
                "staff_name": staff.full_name if staff else None,
                "day": record.day.isoformat(),
                "shift_code": record.shift_code,
                "position": record.position,
            }
            return {"ok": True, "item": item}
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


@bp.delete("/api/fixed/<int:fix_id>")
def delete_fixed_assignment(fix_id: int):
    try:
        with SessionLocal() as session:
            record = session.get(FixedAssignment, fix_id)
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
