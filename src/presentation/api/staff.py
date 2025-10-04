"""HTTP routes for staff resources."""

from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.staff_service import StaffService
from src.domain.exceptions import NotFoundError, ValidationError

staff_bp = Blueprint("staff", __name__, url_prefix="/api/staff")
service = StaffService()


@staff_bp.get("")
def list_staff():
    dept_id = request.args.get("department_id", type=int)
    role_filter = request.args.get("role")
    query = request.args.get("q", "").strip()

    rows = service.list_staff(
        department_id=dept_id,
        role_filter=role_filter,
        query=query,
    )
    return jsonify(rows)


@staff_bp.post("")
def create_staff():
    data = request.get_json(force=True) or {}
    try:
        row = service.create_staff(data)
        return jsonify(row), HTTPStatus.CREATED
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@staff_bp.put("/<int:staff_id>")
def update_staff(staff_id: int):
    data = request.get_json(force=True) or {}
    try:
        row = service.update_staff(staff_id, data)
        return jsonify(row)
    except NotFoundError:
        return {"error": "Staff not found"}, HTTPStatus.NOT_FOUND


@staff_bp.delete("/<int:staff_id>")
def delete_staff(staff_id: int):
    try:
        service.delete_staff(staff_id)
        return {"ok": True}
    except NotFoundError:
        return {"error": "Not found"}, HTTPStatus.NOT_FOUND


@staff_bp.get("/<int:staff_id>/preferences")
def get_preferences(staff_id: int):
    try:
        payload = service.get_preferences(staff_id)
        return jsonify(payload)
    except NotFoundError:
        return {"error": "Staff not found"}, HTTPStatus.NOT_FOUND


@staff_bp.put("/<int:staff_id>/preferences")
def update_preferences(staff_id: int):
    data = request.get_json(force=True) or {}
    try:
        payload = service.update_preferences(staff_id, data)
        return jsonify(payload)
    except NotFoundError:
        return {"error": "Staff not found"}, HTTPStatus.NOT_FOUND
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
