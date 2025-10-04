from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from models import SessionLocal, ShiftPlanDefaults
from .utils import parse_year_month, serialize_shift_defaults

bp = Blueprint("shift_defaults", __name__)


@bp.get("/api/shift-defaults")
def get_shift_defaults():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400
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
        with SessionLocal() as session:
            defaults = session.execute(
                select(ShiftPlanDefaults).where(
                    ShiftPlanDefaults.year == year,
                    ShiftPlanDefaults.month == month,
                )
            ).scalar_one_or_none()
            return jsonify(serialize_shift_defaults(defaults, year, month))
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


@bp.put("/api/shift-defaults")
def upsert_shift_defaults():
    data = request.get_json(silent=True) or {}
    try:
        year, month = parse_year_month(data.get("year"), data.get("month"))
    except ValueError as exc:
        return {"error": str(exc)}, 400
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

    fields = ["day_shifts", "night_shifts", "leader_shifts", "pgd_shifts"]
    missing = [field for field in fields if field not in data]
    if missing:
        return {"error": f"Missing fields: {', '.join(missing)}"}, 400

    validated: dict[str, int] = {}
    for field in fields:
        value = data.get(field)
        if not isinstance(value, int):
            return {"error": f"{field} must be an integer"}, 400
        if value < 0:
            return {"error": f"{field} must be >= 0"}, 400
        validated[field] = value

    try:
        with SessionLocal() as session:
            defaults = session.execute(
                select(ShiftPlanDefaults).where(
                    ShiftPlanDefaults.year == year,
                    ShiftPlanDefaults.month == month,
                )
            ).scalar_one_or_none()

            if defaults is None:
                defaults = ShiftPlanDefaults(
                    year=year,
                    month=month,
                    day_shifts=validated["day_shifts"],
                    night_shifts=validated["night_shifts"],
                    leader_shifts=validated["leader_shifts"],
                    pgd_shifts=validated["pgd_shifts"],
                )
                session.add(defaults)
            else:
                for field, value in validated.items():
                    setattr(defaults, field, value)

            session.commit()
            session.refresh(defaults)
            return jsonify(serialize_shift_defaults(defaults, year, month))
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
