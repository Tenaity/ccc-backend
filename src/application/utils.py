"""Shared application-level helpers."""

from __future__ import annotations

import calendar
from datetime import date


def parse_year_month(year_raw, month_raw) -> tuple[int, int]:
    if year_raw is None or month_raw is None:
        raise ValueError("year and month required")
    try:
        year = int(year_raw)
        month = int(month_raw)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
        raise ValueError("year and month must be integers") from exc
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    if year < 1900 or year > 2100:
        raise ValueError("year must be between 1900 and 2100")
    return year, month


def month_range(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    return start, end


__all__ = ["parse_year_month", "month_range"]
