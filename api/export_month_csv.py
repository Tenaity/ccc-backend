import calendar
import csv
import io
import re
from datetime import date
from typing import Optional

from flask import Response, stream_with_context

import models

from .constants import SHIFT_CREDIT

_RANK_RE = re.compile(r"\[RANK:(1|2)\]")


def _extract_rank(notes: Optional[str]) -> str:
    """Extract rank from staff notes."""
    if not notes:
        return ""
    m = _RANK_RE.search(notes)
    return m.group(1) if m else ""


def export_month_csv(year: int, month: int) -> Response:
    """Stream assignment data of a month as CSV.

    Columns: Ngày, Staff, Role, Rank, Shift, Position, Công.
    """
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    with models.SessionLocal() as s:
        rows = (
            s.query(
                models.Assignment.day,
                models.Staff.full_name,
                models.Staff.role,
                models.Staff.notes,
                models.Assignment.shift_code,
                models.Assignment.position,
            )
            .join(models.Staff, models.Assignment.staff_id == models.Staff.id)
            .filter(models.Assignment.day.between(start, end))
            .order_by(models.Assignment.day, models.Assignment.staff_id)
            .all()
        )

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Ngày", "Staff", "Role", "Rank", "Shift", "Position", "Công"])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for d, name, role, notes, shift, pos in rows:
            rank = _extract_rank(notes)
            credit = SHIFT_CREDIT.get(shift, 0)
            writer.writerow([d.isoformat(), name, role, rank, shift, pos or "", credit])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    headers = {"Content-Disposition": f"attachment; filename=schedule-{year:04d}-{month:02d}.csv"}
    return Response(
        stream_with_context(generate()),
        content_type="text/csv; charset=utf-8",
        headers=headers,
    )
