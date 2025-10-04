"""HTTP routes for metrics endpoints."""

from __future__ import annotations

import os
from datetime import date
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.metrics_service import (
    load_department_comparison,
    load_staff_workload,
)

metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


def _get_cost_per_hour() -> float:
    """Get labor cost per hour from environment variable."""
    raw = os.getenv("LABOR_COST_PER_HOUR", "0").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.0


@metrics_bp.get("/staff-workload")
def staff_workload():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return {"error": "year and month must be provided"}, HTTPStatus.BAD_REQUEST

    rows, totals = load_staff_workload(year, month)
    payload = [row.__dict__ for row in rows]
    return jsonify({"by_staff": payload, "totals": totals})


@metrics_bp.get("/department-compare")
def department_comparison():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return {"error": "year and month must be provided"}, HTTPStatus.BAD_REQUEST

    rows = load_department_comparison(year, month)
    return jsonify({"by_department": [row.__dict__ for row in rows]})


@metrics_bp.get("/attendance")
def metrics_attendance():
    start_raw = request.args.get("from")
    end_raw = request.args.get("to")
    if not start_raw or not end_raw:
        return {"error": "from and to required"}, HTTPStatus.BAD_REQUEST

    try:
        start = date.fromisoformat(start_raw)
        end = date.fromisoformat(end_raw)
    except ValueError:
        return {"error": "from/to must be YYYY-MM-DD"}, HTTPStatus.BAD_REQUEST

    if end < start:
        return {"error": "to must be on or after from"}, HTTPStatus.BAD_REQUEST

    return jsonify({"rate": 0, "absences": [], "late": []})


@metrics_bp.get("/cost")
def metrics_cost():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return {"error": "year and month must be provided"}, HTTPStatus.BAD_REQUEST

    _, totals = load_staff_workload(year, month)
    cost = totals["hours"] * _get_cost_per_hour()
    return jsonify({"labor_cost": cost})
