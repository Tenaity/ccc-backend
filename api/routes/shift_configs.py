from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from models import Department, SessionLocal, ShiftConfig
from rules import SHIFT_DEFS

bp = Blueprint("shift_configs", __name__)


@bp.get("/api/shift-configs")
def list_shift_configs():
    """Get all shift configurations, optionally filtered by department."""
    dept_id = request.args.get("department_id", type=int)

    with SessionLocal() as session:
        query = select(ShiftConfig).order_by(
            ShiftConfig.department_id,
            ShiftConfig.display_order,
            ShiftConfig.name,
        )

        if dept_id:
            query = query.where(ShiftConfig.department_id == dept_id)

        rows = session.execute(query).scalars().all()
        return jsonify(
            [
                {
                    "id": row.id,
                    "department_id": row.department_id,
                    "department_name": row.department.name if row.department else None,
                    "name": row.name,
                    "code": row.code,
                    "start_time": row.start_time,
                    "end_time": row.end_time,
                    "color": row.color,
                    "icon": row.icon,
                    "is_active": row.is_active,
                    "display_order": row.display_order,
                    "rules": row.rules,
                }
                for row in rows
            ]
        )


@bp.post("/api/shift-configs")
def create_shift_config():
    """Create a new shift configuration."""
    data = request.get_json() or {}
    dept_id = data.get("department_id")
    name = data.get("name", "").strip()
    code = data.get("code", "").strip().upper()

    if not dept_id:
        return jsonify({"error": "department_id is required"}), 400
    if not name:
        return jsonify({"error": "Shift name is required"}), 400
    if not code:
        return jsonify({"error": "Shift code is required"}), 400

    with SessionLocal() as session:
        department = session.get(Department, dept_id)
        if not department:
            return jsonify({"error": "Department not found"}), 404

        existing = session.execute(
            select(ShiftConfig).where(
                (ShiftConfig.department_id == dept_id)
                & (ShiftConfig.code == code)
            )
        ).scalar_one_or_none()

        if existing:
            return (
                jsonify(
                    {"error": f"Shift code '{code}' already exists in this department"}
                ),
                400,
            )

        shift = ShiftConfig(
            department_id=dept_id,
            name=name,
            code=code,
            start_time=data.get("start_time", "08:00"),
            end_time=data.get("end_time", "17:00"),
            color=data.get("color", "#60a5fa"),
            icon=data.get("icon", "Sun"),
            is_active=data.get("is_active", True),
            display_order=data.get("display_order", 0),
            rules=data.get("rules", {}),
        )
        session.add(shift)
        session.commit()
        session.refresh(shift)

        return (
            jsonify(
                {
                    "id": shift.id,
                    "department_id": shift.department_id,
                    "name": shift.name,
                    "code": shift.code,
                    "start_time": shift.start_time,
                    "end_time": shift.end_time,
                    "color": shift.color,
                    "icon": shift.icon,
                    "is_active": shift.is_active,
                    "display_order": shift.display_order,
                    "rules": shift.rules,
                }
            ),
            201,
        )


@bp.put("/api/shift-configs/<int:shift_id>")
def update_shift_config(shift_id: int):
    """Update a shift configuration."""
    data = request.get_json() or {}

    with SessionLocal() as session:
        shift = session.get(ShiftConfig, shift_id)
        if not shift:
            return jsonify({"error": "Shift configuration not found"}), 404

        if "name" in data:
            shift.name = data["name"].strip()
        if "code" in data:
            shift.code = data["code"].strip().upper()
        if "start_time" in data:
            shift.start_time = data["start_time"]
        if "end_time" in data:
            shift.end_time = data["end_time"]
        if "color" in data:
            shift.color = data["color"]
        if "icon" in data:
            shift.icon = data["icon"]
        if "is_active" in data:
            shift.is_active = data["is_active"]
        if "display_order" in data:
            shift.display_order = data["display_order"]
        if "rules" in data:
            shift.rules = data["rules"]

        session.commit()
        session.refresh(shift)

        return jsonify(
            {
                "id": shift.id,
                "department_id": shift.department_id,
                "name": shift.name,
                "code": shift.code,
                "start_time": shift.start_time,
                "end_time": shift.end_time,
                "color": shift.color,
                "icon": shift.icon,
                "is_active": shift.is_active,
                "display_order": shift.display_order,
                "rules": shift.rules,
            }
        )


@bp.delete("/api/shift-configs/<int:shift_id>")
def delete_shift_config(shift_id: int):
    """Delete a shift configuration."""
    with SessionLocal() as session:
        shift = session.get(ShiftConfig, shift_id)
        if not shift:
            return jsonify({"error": "Shift configuration not found"}), 404

        session.delete(shift)
        session.commit()
        return jsonify({"ok": True})


@bp.get("/api/shifts")
def shifts():
    return jsonify(SHIFT_DEFS)
