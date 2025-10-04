"""Metrics business logic for dashboard and reporting."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from sqlalchemy import case, func

import models

# Constants (from legacy api/constants.py)
BASE_HOURS_PER_CREDIT = 8.0
SHIFT_CREDIT = {
    "CA1": 1,
    "CA2": 1,
    "K": 1.25,
    "Đ": 1.5,
    "HC": 1,
    "P": 0,
}
SHIFT_HOURS = {code: credit * BASE_HOURS_PER_CREDIT for code, credit in SHIFT_CREDIT.items()}
NIGHT_SHIFT_CODES = {"Đ"}
DEFAULT_MAX_HOURS_PER_STAFF = 208.0


@dataclass(frozen=True)
class StaffWorkloadRow:
    """Per-staff workload metrics."""
    staff_id: int
    name: str
    hours: float
    night_hours: float


@dataclass(frozen=True)
class DepartmentWorkloadRow:
    """Per-department workload metrics."""
    department_id: int
    dept: str
    staff_count: int
    hours: float
    overtime_hours: float


def _month_range(year: int, month: int) -> tuple[date, date]:
    """Get first and last day of month."""
    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    return start, end


def _hours_case():
    """SQLAlchemy CASE expression for shift hours."""
    whens: Sequence[tuple[object, float]] = [
        (models.Assignment.shift_code == code, hours)
        for code, hours in SHIFT_HOURS.items()
    ]
    return case(*whens, else_=0.0)


def _night_hours_case():
    """SQLAlchemy CASE expression for night shift hours."""
    whens: Sequence[tuple[object, float]] = [
        (models.Assignment.shift_code == code, SHIFT_HOURS[code])
        for code in NIGHT_SHIFT_CODES
    ]
    return case(*whens, else_=0.0)


def load_staff_workload(year: int, month: int) -> tuple[list[StaffWorkloadRow], dict[str, float]]:
    """Return per-staff workload with totals for a month."""
    start, end = _month_range(year, month)
    hour_case = _hours_case()
    night_case = _night_hours_case()

    with models.SessionLocal() as session:
        rows = (
            session.query(
                models.Assignment.staff_id,
                models.Staff.full_name,
                func.sum(hour_case).label("hours"),
                func.sum(night_case).label("night_hours"),
            )
            .join(models.Staff, models.Assignment.staff_id == models.Staff.id)
            .filter(models.Assignment.day.between(start, end))
            .group_by(models.Assignment.staff_id, models.Staff.full_name)
            .order_by(func.sum(hour_case).desc(), models.Staff.full_name)
            .all()
        )

    data = [
        StaffWorkloadRow(
            staff_id=row[0],
            name=row[1],
            hours=float(row[2] or 0.0),
            night_hours=float(row[3] or 0.0),
        )
        for row in rows
    ]
    totals = {
        "hours": sum(item.hours for item in data),
        "night_hours": sum(item.night_hours for item in data),
    }
    return data, totals


def load_department_comparison(year: int, month: int) -> list[DepartmentWorkloadRow]:
    """Return workload aggregated per department for a month."""
    start, end = _month_range(year, month)
    hour_case = _hours_case()

    with models.SessionLocal() as session:
        departments = session.query(models.Department).order_by(models.Department.name).all()
        staff_counts = {
            dept_id: count
            for dept_id, count in (
                session.query(
                    models.Department.id,
                    func.count(models.Staff.id).label("staff_count"),
                )
                .outerjoin(models.Staff, models.Staff.department_id == models.Department.id)
                .group_by(models.Department.id)
                .all()
            )
        }
        hour_map = {
            dept_id: float(hours or 0.0)
            for dept_id, hours in (
                session.query(
                    models.Department.id,
                    func.sum(hour_case).label("hours"),
                )
                .join(models.Staff, models.Staff.department_id == models.Department.id)
                .join(models.Assignment, models.Assignment.staff_id == models.Staff.id)
                .filter(models.Assignment.day.between(start, end))
                .group_by(models.Department.id)
                .all()
            )
        }

    result: list[DepartmentWorkloadRow] = []
    for dept in departments:
        staff_count = int(staff_counts.get(dept.id, 0) or 0)
        hours = hour_map.get(dept.id, 0.0)
        settings = dept.settings or {}
        max_hours_per_staff = settings.get("max_hours_per_month") if isinstance(settings, dict) else None
        if not isinstance(max_hours_per_staff, (int, float)):
            max_hours_per_staff = DEFAULT_MAX_HOURS_PER_STAFF
        overtime_limit = staff_count * float(max_hours_per_staff)
        overtime_hours = max(hours - overtime_limit, 0.0)
        result.append(
            DepartmentWorkloadRow(
                department_id=dept.id,
                dept=dept.name,
                staff_count=staff_count,
                hours=hours,
                overtime_hours=overtime_hours,
            )
        )

    return result


__all__ = [
    "StaffWorkloadRow",
    "DepartmentWorkloadRow",
    "load_staff_workload",
    "load_department_comparison",
]
