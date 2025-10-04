"""HTTP routes for department resources."""

from __future__ import annotations

from dataclasses import asdict
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.department_service import DepartmentService
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError


def _serialize(dto):
    payload = asdict(dto)
    if payload.get("staff_count") is None:
        payload.pop("staff_count", None)
    if payload.get("shift_count") is None:
        payload.pop("shift_count", None)
    return payload


department_bp = Blueprint("department", __name__, url_prefix="/api/departments")
service = DepartmentService()


@department_bp.get("")
def list_departments():
    active_raw = request.args.get("active")
    active_filter = None
    if active_raw is not None:
        raw = active_raw.strip().lower()
        if raw in {"1", "true", "yes"}:
            active_filter = True
        elif raw in {"0", "false", "no"}:
            active_filter = False
        else:
            return {"error": "active must be truthy (1/true) or falsy (0/false)"}, HTTPStatus.BAD_REQUEST

    rows = service.list_departments(active=active_filter)
    if active_filter is not None:
        return jsonify([
            {
                "id": row.id,
                "name": row.name,
                "code": row.code,
                "color": row.color,
                "icon": row.icon,
                "settings": row.settings,
            }
            for row in rows
        ])
    return jsonify([_serialize(row) for row in rows])


@department_bp.post("")
def create_department():
    data = request.get_json(force=True) or {}
    try:
        dto = service.create_department(
            name=data.get("name", ""),
            code=data.get("code", ""),
            color=data.get("color"),
            icon=data.get("icon"),
            description=data.get("description"),
            is_active=data.get("is_active", True),
            settings=data.get("settings") or {},
        )
        return jsonify(_serialize(dto)), HTTPStatus.CREATED
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except ConflictError as exc:
        return {"error": str(exc)}, HTTPStatus.CONFLICT


@department_bp.put("/<int:dept_id>")
def update_department(dept_id: int):
    data = request.get_json(force=True) or {}
    try:
        dto = service.update_department(dept_id, **data)
        return jsonify(_serialize(dto))
    except NotFoundError:
        return {"error": "Department not found"}, HTTPStatus.NOT_FOUND


@department_bp.delete("/<int:dept_id>")
def delete_department(dept_id: int):
    try:
        service.delete_department(dept_id)
        return {"ok": True}
    except NotFoundError:
        return {"error": "Department not found"}, HTTPStatus.NOT_FOUND
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
