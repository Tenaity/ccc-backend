"""HTTP routes for off day resources."""

from __future__ import annotations

from datetime import date
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.offday_service import OffDayService
from src.domain.exceptions import NotFoundError, ValidationError

offday_bp = Blueprint("off", __name__, url_prefix="/api/off")
service = OffDayService()


@offday_bp.get("")
def list_off_days():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    try:
        rows = service.list_off_days(year=year, month=month)
        return jsonify(rows)
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@offday_bp.post("")
def create_off_day():
    data = request.get_json(force=True) or {}
    try:
        payload = service.create_off_day(data)
        status = HTTPStatus.CREATED if payload.get("id") else HTTPStatus.OK
        return payload, status
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND


@offday_bp.delete("/<int:off_id>")
def delete_off_day(off_id: int):
    try:
        service.delete_off_day(off_id)
        return {"ok": True}
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND
