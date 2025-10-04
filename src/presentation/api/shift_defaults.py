"""HTTP routes for shift defaults."""

from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.shift_defaults_service import ShiftDefaultsService
from src.domain.exceptions import ValidationError

shift_defaults_bp = Blueprint("shift_defaults", __name__, url_prefix="/api/shift-defaults")
service = ShiftDefaultsService()


@shift_defaults_bp.get("")
def get_shift_defaults():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if year is None or month is None:
        return {"error": "year and month required"}, HTTPStatus.BAD_REQUEST
    try:
        payload = service.get_defaults(year=year, month=month)
        return jsonify(payload)
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@shift_defaults_bp.put("")
def upsert_shift_defaults():
    data = request.get_json(force=True) or {}
    try:
        payload = service.upsert_defaults(data)
        return jsonify(payload)
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
