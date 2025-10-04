"""HTTP routes for fixed assignment resources."""

from __future__ import annotations

from datetime import date
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.fixed_assignment_service import FixedAssignmentService
from src.domain.exceptions import NotFoundError, ValidationError

fixed_bp = Blueprint("fixed", __name__, url_prefix="/api/fixed")
service = FixedAssignmentService()


@fixed_bp.get("")
def list_fixed_assignments():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    try:
        rows = service.list_assignments(year=year, month=month)
        return jsonify(rows)
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@fixed_bp.post("")
def create_fixed_assignment():
    data = request.get_json(force=True) or {}
    try:
        item = service.create_assignment(data)
        return {"ok": True, "item": item}, HTTPStatus.CREATED
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND


@fixed_bp.put("/<int:assignment_id>")
def update_fixed_assignment(assignment_id: int):
    data = request.get_json(force=True) or {}
    try:
        item = service.update_assignment(assignment_id, data)
        return {"ok": True, "item": item}
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND


@fixed_bp.delete("/<int:assignment_id>")
def delete_fixed_assignment(assignment_id: int):
    try:
        service.delete_assignment(assignment_id)
        return {"ok": True}
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND
