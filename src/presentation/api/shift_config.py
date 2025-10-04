"""HTTP routes for shift configuration resources."""

from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.shift_config_service import ShiftConfigService
from src.domain.exceptions import NotFoundError, ValidationError

shift_config_bp = Blueprint("shift_config", __name__, url_prefix="/api/shift-configs")
service = ShiftConfigService()


@shift_config_bp.get("")
def list_shift_configs():
    dept_id = request.args.get("department_id", type=int)
    rows = service.list_shift_configs(department_id=dept_id)
    return jsonify(rows)


@shift_config_bp.post("")
def create_shift_config():
    data = request.get_json(force=True) or {}
    try:
        row = service.create_shift_config(data)
        return jsonify(row), HTTPStatus.CREATED
    except ValidationError as exc:
        status = HTTPStatus.BAD_REQUEST
        if "already exists" in str(exc):
            status = HTTPStatus.BAD_REQUEST
        return {"error": str(exc)}, status
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND


@shift_config_bp.put("/<int:shift_id>")
def update_shift_config(shift_id: int):
    data = request.get_json(force=True) or {}
    try:
        row = service.update_shift_config(shift_id, data)
        return jsonify(row)
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND


@shift_config_bp.delete("/<int:shift_id>")
def delete_shift_config(shift_id: int):
    try:
        service.delete_shift_config(shift_id)
        return {"ok": True}
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND
