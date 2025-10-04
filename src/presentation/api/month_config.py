"""HTTP routes for month configuration."""

from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.month_config_service import MonthConfigService
from src.domain.exceptions import ValidationError

month_config_bp = Blueprint("month_config", __name__, url_prefix="/api/month-config")
service = MonthConfigService()


def _serialize(payload):
    return {
        "year": payload.year,
        "month": payload.month,
        "auto_working_days": payload.auto_working_days,
        "policy_working_days": payload.policy_working_days,
        "effective_working_days": payload.effective_working_days,
        "config": payload.config,
    }


@month_config_bp.get("")
def get_month_config():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if year is None or month is None:
        return {"error": "year and month required"}, HTTPStatus.BAD_REQUEST

    try:
        payload = service.get_month_config(year=year, month=month)
        return jsonify(_serialize(payload))
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@month_config_bp.put("")
def update_month_config():
    data = request.get_json(force=True) or {}
    try:
        payload = service.update_month_config(data)
        return jsonify(_serialize(payload))
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
