from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from models import Department, SessionLocal

bp = Blueprint("departments", __name__)


@bp.get("/api/departments")
def list_departments():
    """Get all departments."""

    active_raw = request.args.get("active")
    active_filter: bool | None = None
    if active_raw is not None:
        raw = active_raw.strip().lower()
        if raw in {"1", "true", "yes"}:
            active_filter = True
        elif raw in {"0", "false", "no"}:
            active_filter = False
        else:
            return (
                jsonify({"error": "active must be truthy (1/true) or falsy (0/false)"}),
                400,
            )

    with SessionLocal() as session:
        query = select(Department).order_by(Department.name)
        if active_filter is not None:
            query = query.where(Department.is_active.is_(active_filter))
        rows = session.execute(query).scalars().all()

        if active_filter is not None:
            payload = [
                {
                    "id": row.id,
                    "name": row.name,
                    "code": row.code,
                    "color": row.color,
                    "icon": row.icon,
                    "settings": row.settings,
                }
                for row in rows
            ]
        else:
            payload = [
                {
                    "id": row.id,
                    "name": row.name,
                    "code": row.code,
                    "color": row.color,
                    "icon": row.icon,
                    "description": row.description,
                    "is_active": row.is_active,
                    "settings": row.settings,
                    "staff_count": len(row.staff) if row.staff else 0,
                    "shift_count": len(row.shifts) if row.shifts else 0,
                }
                for row in rows
            ]

        return jsonify(payload)


@bp.post("/api/departments")
def create_department():
    """Create a new department."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    code = data.get("code", "").strip().upper()

    if not name:
        return jsonify({"error": "Department name is required"}), 400
    if not code:
        return jsonify({"error": "Department code is required"}), 400

    with SessionLocal() as session:
        existing = session.execute(
            select(Department).where(
                (Department.name == name) | (Department.code == code)
            )
        ).scalar_one_or_none()

        if existing:
            return jsonify({"error": "Department name or code already exists"}), 400

        department = Department(
            name=name,
            code=code,
            color=data.get("color", "#3b82f6"),
            icon=data.get("icon", "Building2"),
            description=data.get("description"),
            is_active=data.get("is_active", True),
            settings=data.get(
                "settings",
                {
                    "working_hours": {"start": "08:00", "end": "17:00"},
                    "weekend_policy": "sat_off",
                    "max_hours_per_month": 208,
                    "min_staff_per_shift": 2,
                },
            ),
        )
        session.add(department)
        session.commit()
        session.refresh(department)

        return (
            jsonify(
                {
                    "id": department.id,
                    "name": department.name,
                    "code": department.code,
                    "color": department.color,
                    "icon": department.icon,
                    "description": department.description,
                    "is_active": department.is_active,
                    "settings": department.settings,
                }
            ),
            201,
        )


@bp.put("/api/departments/<int:dept_id>")
def update_department(dept_id: int):
    """Update a department."""
    data = request.get_json() or {}

    with SessionLocal() as session:
        department = session.get(Department, dept_id)
        if not department:
            return jsonify({"error": "Department not found"}), 404

        if "name" in data:
            name = data["name"].strip()
            if not name:
                return jsonify({"error": "Department name cannot be empty"}), 400
            department.name = name

        if "code" in data:
            code = data["code"].strip().upper()
            if not code:
                return jsonify({"error": "Department code cannot be empty"}), 400
            department.code = code

        if "color" in data:
            department.color = data["color"]
        if "icon" in data:
            department.icon = data["icon"]
        if "description" in data:
            department.description = data["description"]
        if "is_active" in data:
            department.is_active = data["is_active"]
        if "settings" in data:
            department.settings = data["settings"]

        session.commit()
        session.refresh(department)

        return jsonify(
            {
                "id": department.id,
                "name": department.name,
                "code": department.code,
                "color": department.color,
                "icon": department.icon,
                "description": department.description,
                "is_active": department.is_active,
                "settings": department.settings,
            }
        )


@bp.delete("/api/departments/<int:dept_id>")
def delete_department(dept_id: int):
    """Delete a department."""
    with SessionLocal() as session:
        department = session.get(Department, dept_id)
        if not department:
            return jsonify({"error": "Department not found"}), 404

        if department.staff and len(department.staff) > 0:
            return (
                jsonify(
                    {
                        "error": (
                            "Cannot delete department with "
                            f"{len(department.staff)} staff members. Please reassign or remove staff first."
                        )
                    }
                ),
                400,
            )

        session.delete(department)
        session.commit()
        return jsonify({"ok": True})
