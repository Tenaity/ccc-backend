from __future__ import annotations

import csv
import io
import os
from datetime import date
from typing import Iterable

from flask import Response, stream_with_context
from sqlalchemy import select

from models import Holiday, MonthConfig, ShiftPlanDefaults, WeekendPolicy
from scheduler.utils import month_last_day


def parse_year_month(year_raw, month_raw) -> tuple[int, int]:
    """Validate and convert year/month inputs."""

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
    last_day = month_last_day(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    return start, end


def get_cost_per_hour() -> float:
    raw = os.getenv("LABOR_COST_PER_HOUR", "0").strip()
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def build_csv_response(
    filename: str, header: Iterable[object], rows: Iterable[Iterable[object]]
) -> Response:
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


def coerce_extra_dates(
    values: object, year: int, month: int, field_name: str
) -> set[date] | None:
    """Validate optional list of YYYY-MM-DD strings limited to the target month."""

    if values is None:
        return None
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of dates")

    parsed: set[date] = set()
    for item in values:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain YYYY-MM-DD strings")
        try:
            dt = date.fromisoformat(item)
        except ValueError as exc:
            raise ValueError(f"{field_name} has invalid date '{item}'") from exc
        if dt.year != year or dt.month != month:
            raise ValueError(
                f"{field_name} must stay within {year}-{month:02d}"
            )
        parsed.add(dt)
    return parsed


def build_month_config_payload(session, year: int, month: int) -> dict:
    """Construct payload for month config, including derived working days."""

    config = session.execute(
        select(MonthConfig).where(
            MonthConfig.year == year, MonthConfig.month == month
        )
    ).scalar_one_or_none()

    weekend_policy = config.weekend_policy if config else WeekendPolicy.SAT_OFF
    stored_workdays = config.extra_workdays if config else []
    stored_offdays = config.extra_offdays if config else []
    working_days_override = config.working_days_override if config else None

    last_day = month_last_day(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)

    official_holidays = {
        row.day
        for row in session.scalars(
            select(Holiday).where(
                Holiday.day >= start,
                Holiday.day <= end,
                Holiday.official.is_(True),
            )
        )
    }

    auto_working_days = sum(
        1
        for day in range(1, last_day + 1)
        if (dt := date(year, month, day)).weekday() < 5
        and dt not in official_holidays
    )

    day_values: dict[date, float] = {}
    for day in range(1, last_day + 1):
        current = date(year, month, day)
        weekday = current.weekday()
        if weekday < 5:
            base = 1.0
        elif weekday == 5:
            if weekend_policy == WeekendPolicy.SAT_WORK:
                base = 1.0
            elif weekend_policy == WeekendPolicy.SAT_WORK_AM:
                base = 0.5
            else:
                base = 0.0
        else:
            base = 0.0
        if current in official_holidays:
            base = 0.0
        day_values[current] = base

    workday_dates = set()
    for raw in stored_workdays:
        try:
            dt = date.fromisoformat(raw)
        except ValueError:
            continue
        if dt.year == year and dt.month == month:
            workday_dates.add(dt)
    offday_dates = set()
    for raw in stored_offdays:
        try:
            dt = date.fromisoformat(raw)
        except ValueError:
            continue
        if dt.year == year and dt.month == month:
            offday_dates.add(dt)

    for extra in workday_dates:
        if start <= extra <= end:
            day_values[extra] = max(day_values.get(extra, 0.0), 1.0)

    for extra in offday_dates:
        if start <= extra <= end:
            day_values[extra] = 0.0

    policy_working_days = sum(day_values.values())
    effective_working_days = (
        working_days_override if working_days_override is not None else policy_working_days
    )

    return {
        "year": year,
        "month": month,
        "auto_working_days": auto_working_days,
        "policy_working_days": policy_working_days,
        "effective_working_days": effective_working_days,
        "config": {
            "weekend_policy": weekend_policy.value,
            "extra_workdays": sorted(dt.isoformat() for dt in workday_dates),
            "extra_offdays": sorted(dt.isoformat() for dt in offday_dates),
            "working_days_override": working_days_override,
        },
    }


def serialize_shift_defaults(
    defaults: ShiftPlanDefaults | None, year: int, month: int
) -> dict:
    """Return API payload describing stored shift plan defaults for a month."""

    return {
        "year": year,
        "month": month,
        "day_shifts": defaults.day_shifts if defaults else 0,
        "night_shifts": defaults.night_shifts if defaults else 0,
        "leader_shifts": defaults.leader_shifts if defaults else 0,
        "pgd_shifts": defaults.pgd_shifts if defaults else 0,
    }
