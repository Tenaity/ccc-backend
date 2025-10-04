"""HTTP routes for CSV export/report endpoints."""

from __future__ import annotations

import csv
import io
from http import HTTPStatus

from flask import Blueprint, Response, request, stream_with_context

from src.application.metrics_service import (
    load_department_comparison,
    load_staff_workload,
)

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _build_csv_response(filename: str, header: list[str], rows: list[list[object]]):
    """Build streaming CSV response."""

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    response = Response(
        stream_with_context(generate()),
        content_type="text/csv; charset=utf-8",
    )
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@reports_bp.get("/staff-workload.csv")
def export_staff_workload_csv():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return {"error": "year and month must be provided"}, HTTPStatus.BAD_REQUEST

    data, totals = load_staff_workload(year, month)
    rows = [
        [row.staff_id, row.name, f"{row.hours:.2f}", f"{row.night_hours:.2f}"]
        for row in data
    ]
    if data:
        rows.append(["TOTAL", "", f"{totals['hours']:.2f}", f"{totals['night_hours']:.2f}"])
    return _build_csv_response(
        f"staff-workload-{year:04d}-{month:02d}.csv",
        ["staff_id", "name", "hours", "night_hours"],
        rows,
    )


@reports_bp.get("/department-compare.csv")
def export_department_compare_csv():
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return {"error": "year and month must be provided"}, HTTPStatus.BAD_REQUEST

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
    return _build_csv_response(
        f"department-compare-{year:04d}-{month:02d}.csv",
        ["department", "staff_count", "hours", "overtime_hours"],
        csv_rows,
    )


@reports_bp.get("/schedule-month.csv")
def export_schedule_month_csv():
    """Export monthly schedule as CSV."""
    try:
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return {"error": "year and month must be provided"}, HTTPStatus.BAD_REQUEST

    from src.application.export_service import export_month_csv

    # The function returns a Flask Response object directly
    return export_month_csv(year, month)
