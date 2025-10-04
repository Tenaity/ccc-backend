"""Application services for schedule queries."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, List

from sqlalchemy import select

from src.application.utils import month_range
from src.domain.exceptions import NotFoundError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import (
    Assignment,
    Department,
    Staff,
)


class ScheduleService:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def get_schedule(self, *, year: int, month: int, department_id: int | None) -> dict:
        with self._session() as session:
            if department_id is not None:
                dept = session.get(Department, department_id)
                if not dept or not dept.is_active:
                    raise NotFoundError("Department not found or inactive")

            start, end = month_range(year, month)

            query = (
                select(
                    Assignment.day,
                    Assignment.shift_code,
                    Assignment.position,
                    Assignment.staff_id,
                    Staff.full_name,
                    Staff.role,
                    Staff.department_id,
                    Department.name,
                )
                .join(Staff, Assignment.staff_id == Staff.id, isouter=True)
                .join(Department, Staff.department_id == Department.id, isouter=True)
                .where(Assignment.day.between(start, end))
                .order_by(Assignment.day, Assignment.shift_code, Assignment.id)
            )

            if department_id is not None:
                query = query.where(Staff.department_id == department_id)

            rows = session.execute(query).all()

        items: list[dict] = []
        counts: dict[str, object] = {
            "total": 0,
            "by_shift": defaultdict(int),
            "leaders": {"day": 0, "night": 0},
        }

        for day, shift_code, position, staff_id, full_name, role, row_dept_id, dept_name in rows:
            items.append(
                {
                    "day": day.isoformat(),
                    "shift_code": shift_code,
                    "position": position,
                    "staff_id": staff_id,
                    "staff_name": full_name,
                    "role": role,
                    "department_id": row_dept_id,
                    "department_name": dept_name,
                }
            )
            counts["total"] += 1
            counts["by_shift"][shift_code] += 1
            if shift_code == "K" and (position or "").upper() == "TD":
                counts["leaders"]["day"] += 1
            if shift_code == "Đ" and (position or "").upper() == "TD":
                counts["leaders"]["night"] += 1

        counts["by_shift"] = dict(counts["by_shift"])
        return {"items": items, "counts": counts}

    def get_overview(self, *, year: int, month: int) -> List[dict]:
        start, end = month_range(year, month)
        days_in_month = (end - start).days + 1

        with self._session() as session:
            departments = session.execute(
                select(Department).order_by(Department.name)
            ).scalars().all()
            rows = session.execute(
                select(
                    Assignment.day,
                    Assignment.shift_code,
                    Assignment.position,
                    Staff.department_id,
                    Department.name,
                    Department.is_active,
                )
                .join(Staff, Assignment.staff_id == Staff.id, isouter=True)
                .join(Department, Staff.department_id == Department.id, isouter=True)
                .where(Assignment.day.between(start, end))
            ).all()

        overview: dict[int, dict[str, object]] = {}
        day_presence: Dict[int, set[date]] = defaultdict(set)
        day_shifts: Dict[int, dict[str, set[date]]] = defaultdict(
            lambda: {"day": set(), "night": set()}
        )
        leader_flags: Dict[int, dict[str, set[date]]] = defaultdict(
            lambda: {"day": set(), "night": set()}
        )

        for dept in departments:
            if not dept.is_active:
                continue
            overview[dept.id] = {
                "department_id": dept.id,
                "name": dept.name,
                "shifts": 0,
                "missing_leaders": 0,
                "coverage_rate": 0.0,
            }

        for day, shift_code, position, dept_id, dept_name, is_active in rows:
            if dept_id is None or dept_id not in overview:
                continue
            info = overview[dept_id]
            info["shifts"] += 1
            day_presence[dept_id].add(day)
            if shift_code == "K":
                day_shifts[dept_id]["day"].add(day)
                if (position or "").upper() == "TD":
                    leader_flags[dept_id]["day"].add(day)
            elif shift_code == "Đ":
                day_shifts[dept_id]["night"].add(day)
                if (position or "").upper() == "TD":
                    leader_flags[dept_id]["night"].add(day)

        for dept_id, info in overview.items():
            covered_days = len(day_presence.get(dept_id, set()))
            info["coverage_rate"] = round(
                covered_days / days_in_month if days_in_month else 0.0,
                4,
            )

            missing = 0
            for bucket in ("day", "night"):
                shift_days = day_shifts[dept_id][bucket]
                leaders = leader_flags[dept_id][bucket]
                for day in shift_days:
                    if day not in leaders:
                        missing += 1
            info["missing_leaders"] = missing

        return sorted(overview.values(), key=lambda item: item["name"])


__all__ = ["ScheduleService"]
