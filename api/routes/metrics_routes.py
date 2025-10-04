from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request

from api.export_month_csv import export_month_csv as export_staff_month_csv
from api.metrics import load_department_comparison, load_staff_workload
from .utils import build_csv_response, get_cost_per_hour, parse_year_month

bp = Blueprint("metrics_routes", __name__)


@bp.get("/api/metrics/staff-workload")
def metrics_staff_workload():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400

    data, totals = load_staff_workload(year, month)
    return jsonify(
        {
            "by_staff": [
                {
                    "staff_id": row.staff_id,
                    "name": row.name,
                    "hours": row.hours,
                    "night_hours": row.night_hours,
                }
                for row in data
            ],
            "totals": totals,
        }
    )


@bp.get("/api/metrics/department-compare")
def metrics_department_compare():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400

    rows = load_department_comparison(year, month)
    return jsonify(
        {
            "by_department": [
                {
                    "dept": row.dept,
                    "staff_count": row.staff_count,
                    "hours": row.hours,
                    "overtime_hours": row.overtime_hours,
                }
                for row in rows
            ]
        }
    )


@bp.get("/api/metrics/attendance")
def metrics_attendance():
    start_raw = request.args.get("from")
    end_raw = request.args.get("to")
    if not start_raw or not end_raw:
        return {"error": "from and to required"}, 400

    try:
        start = date.fromisoformat(start_raw)
        end = date.fromisoformat(end_raw)
    except ValueError:
        return {"error": "from/to must be YYYY-MM-DD"}, 400

    if end < start:
        return {"error": "to must be on or after from"}, 400

    return jsonify({"rate": 0, "absences": [], "late": []})


@bp.get("/api/metrics/cost")
def metrics_cost():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400

    _, totals = load_staff_workload(year, month)
    cost = totals["hours"] * get_cost_per_hour()
    return jsonify({"labor_cost": cost})


@bp.get("/api/reports/staff-workload.csv")
def export_staff_workload_csv():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400

    data, totals = load_staff_workload(year, month)
    rows = [
        [row.staff_id, row.name, f"{row.hours:.2f}", f"{row.night_hours:.2f}"]
        for row in data
    ]
    if data:
        rows.append(["TOTAL", "", f"{totals['hours']:.2f}", f"{totals['night_hours']:.2f}"])
    return build_csv_response(
        f"staff-workload-{year:04d}-{month:02d}.csv",
        ["staff_id", "name", "hours", "night_hours"],
        rows,
    )


@bp.get("/api/reports/department-compare.csv")
def export_department_compare_csv():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400

    rows = load_department_comparison(year, month)
    csv_rows = [
        [
            row.dept,
            row.staff_count,
            f"{row.hours:.2f}",
            f"{row.overtime_hours:.2f}",
        ]
        for row in rows
    ]
    return build_csv_response(
        f"department-compare-{year:04d}-{month:02d}.csv",
        ["department", "staff_count", "hours", "overtime_hours"],
        csv_rows,
    )


@bp.get("/api/reports/schedule-month.csv")
def export_schedule_month_csv():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400

    response = export_staff_month_csv(year, month)
    response.headers["Content-Disposition"] = (
        f"attachment; filename=schedule-month-{year:04d}-{month:02d}.csv"
    )
    return response
