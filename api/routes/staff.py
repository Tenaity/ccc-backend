from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from models import SessionLocal, ShiftConfig, Staff, StaffPreferences

bp = Blueprint("staff", __name__)


@bp.get("/api/staff")
def list_staff():
    """Get all staff, optionally filtered by department."""
    dept_id = request.args.get("department_id", type=int)
    role_filter_raw = request.args.get("role")
    query_raw = request.args.get("q", "").strip()

    with SessionLocal() as session:
        query = select(Staff).options(selectinload(Staff.department))

        if dept_id is not None:
            query = query.where(Staff.department_id == dept_id)

        if role_filter_raw:
            roles = {item.strip().upper() for item in role_filter_raw.split(",") if item.strip()}
            if roles:
                query = query.where(func.upper(Staff.role).in_(sorted(roles)))

        if query_raw:
            pattern = f"%{query_raw.lower()}%"
            query = query.where(func.lower(Staff.full_name).like(pattern))

        query = query.order_by(func.lower(Staff.full_name))

        rows = session.execute(query).scalars().all()
        return jsonify(
            [
                {
                    "id": row.id,
                    "full_name": row.full_name,
                    "role": row.role,
                    "can_night": row.can_night,
                    "base_quota": row.base_quota,
                    "notes": row.notes,
                    "department_id": row.department_id,
                    "department_name": row.department.name if row.department else None,
                }
                for row in rows
            ]
        )


@bp.post("/api/staff")
def add_staff():
    data = request.get_json(force=True)
    with SessionLocal() as session:
        staff = Staff(
            full_name=data["full_name"],
            role=data.get("role", "GDV"),
            can_night=bool(data.get("can_night", True)),
            base_quota=float(data.get("base_quota", 26.0)),
            notes=data.get("notes"),
            department_id=data.get("department_id"),
        )
        session.add(staff)
        session.commit()
        session.refresh(staff)
        return {
            "id": staff.id,
            "full_name": staff.full_name,
            "department_id": staff.department_id,
        }


@bp.put("/api/staff/<int:staff_id>")
def update_staff(staff_id: int):
    """Update an existing staff member."""
    data = request.get_json(force=True)
    with SessionLocal() as session:
        staff = session.get(Staff, staff_id)
        if not staff:
            return {"error": "Staff not found"}, 404

        if "full_name" in data:
            staff.full_name = data["full_name"]
        if "role" in data:
            staff.role = data["role"]
        if "can_night" in data:
            staff.can_night = bool(data["can_night"])
        if "base_quota" in data:
            staff.base_quota = float(data["base_quota"])
        if "notes" in data:
            staff.notes = data["notes"]
        if "department_id" in data:
            staff.department_id = data["department_id"]

        session.commit()
        session.refresh(staff)
        return {
            "id": staff.id,
            "full_name": staff.full_name,
            "role": staff.role,
            "can_night": staff.can_night,
            "base_quota": staff.base_quota,
            "notes": staff.notes,
            "department_id": staff.department_id,
            "department_name": staff.department.name if staff.department else None,
        }


@bp.delete("/api/staff/<int:staff_id>")
def delete_staff(staff_id: int):
    with SessionLocal() as session:
        staff = session.get(Staff, staff_id)
        if not staff:
            return {"error": "Not found"}, 404
        session.delete(staff)
        session.commit()
        return {"ok": True}


@bp.get("/api/staff/<int:staff_id>/preferences")
def get_staff_preferences(staff_id: int):
    """Get scheduling preferences for a staff member."""
    with SessionLocal() as session:
        staff = session.get(Staff, staff_id)
        if not staff:
            return {"error": "Staff not found"}, 404

        prefs = staff.preferences
        if not prefs:
            return {
                "staff_id": staff_id,
                "preferred_shifts": [],
                "unavailable_days": [],
                "max_consecutive_days": 6,
                "preferred_days_off": [],
                "notes": None,
            }

        return {
            "staff_id": prefs.staff_id,
            "preferred_shifts": prefs.preferred_shifts or [],
            "unavailable_days": prefs.unavailable_days or [],
            "max_consecutive_days": prefs.max_consecutive_days,
            "preferred_days_off": prefs.preferred_days_off or [],
            "notes": prefs.notes,
        }


@bp.put("/api/staff/<int:staff_id>/preferences")
def update_staff_preferences(staff_id: int):
    """Upsert scheduling preferences for a staff member."""
    data = request.get_json(force=True)

    preferred_shifts = data.get("preferred_shifts", [])
    unavailable_days = data.get("unavailable_days", [])
    max_consecutive_days = data.get("max_consecutive_days")
    preferred_days_off = data.get("preferred_days_off", [])
    notes = data.get("notes")

    if max_consecutive_days is not None:
        try:
            max_consecutive_days = int(max_consecutive_days)
            if max_consecutive_days < 0:
                return {"error": "max_consecutive_days must be >= 0"}, 400
        except (ValueError, TypeError):
            return {"error": "max_consecutive_days must be a number"}, 400

    for day_str in unavailable_days:
        try:
            datetime.fromisoformat(day_str)
        except (ValueError, TypeError):
            return {"error": f"Invalid date format: {day_str}. Use YYYY-MM-DD"}, 400

    for day_num in preferred_days_off:
        if not isinstance(day_num, int) or day_num < 0 or day_num > 6:
            return {"error": f"Invalid day number: {day_num}. Must be 0-6 (Mon-Sun)"}, 400

    with SessionLocal() as session:
        staff = session.get(Staff, staff_id)
        if not staff:
            return {"error": "Staff not found"}, 404

        if staff.department_id and preferred_shifts:
            valid_shift_codes = set(
                session.execute(
                    select(ShiftConfig.code)
                    .where(ShiftConfig.department_id == staff.department_id)
                    .where(ShiftConfig.is_active == True)
                ).scalars().all()
            )

            for shift_code in preferred_shifts:
                if shift_code not in valid_shift_codes:
                    return {
                        "error": (
                            f"Invalid shift code '{shift_code}' for department. "
                            f"Valid codes: {sorted(valid_shift_codes)}"
                        )
                    }, 400

        prefs = staff.preferences
        if not prefs:
            prefs = StaffPreferences(staff_id=staff_id)
            session.add(prefs)

        prefs.preferred_shifts = preferred_shifts
        prefs.unavailable_days = unavailable_days
        prefs.max_consecutive_days = max_consecutive_days
        prefs.preferred_days_off = preferred_days_off
        prefs.notes = notes

        session.commit()
        session.refresh(prefs)

        return {
            "staff_id": prefs.staff_id,
            "preferred_shifts": prefs.preferred_shifts or [],
            "unavailable_days": prefs.unavailable_days or [],
            "max_consecutive_days": prefs.max_consecutive_days,
            "preferred_days_off": prefs.preferred_days_off or [],
            "notes": prefs.notes,
        }
