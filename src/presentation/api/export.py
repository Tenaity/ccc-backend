"""HTTP routes for export endpoints."""

from __future__ import annotations

import calendar
import csv
import io
import json
from datetime import date

from flask import Blueprint, Response, request, stream_with_context

import models

from src.application.export_service import export_month_csv

export_bp = Blueprint("export", __name__, url_prefix="/api")


@export_bp.get("/export/month.csv")
def export_month_csv_endpoint():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    if month < 1 or month > 12:
        return {"error": "month must be 1..12"}, 400
    return export_month_csv(year, month)


@export_bp.get("/export_audit")
def export_audit():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month

    if month < 1 or month > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    with models.SessionLocal() as session:
        rows = (
            session.query(models.Assignment)
            .filter(models.Assignment.day.between(start, end))
            .all()
        )

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["day", "shift_code", "staff_id", "meta"])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            meta = {
                "info": f"{row.shift_code},{row.staff_id}",
                "extra": "value",
            }
            writer.writerow(
                [
                    row.day.isoformat(),
                    row.shift_code,
                    row.staff_id,
                    json.dumps(meta, ensure_ascii=False),
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    headers = {
        "Content-Disposition": f"attachment; filename=audit-{year:04d}-{month:02d}.csv"
    }
    return Response(
        stream_with_context(generate()),
        content_type="text/csv; charset=utf-8",
        headers=headers,
    )
