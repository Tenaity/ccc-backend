"""Application services for fixed assignments."""

from __future__ import annotations

import calendar
from datetime import date
from typing import List

from src.utils.logging import instrument_service
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import (
    FixedAssignment,
    Staff,
)


@instrument_service
class FixedAssignmentService:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def list_assignments(self, *, year: int, month: int) -> List[dict]:
        if month < 1 or month > 12:
            raise ValidationError("month must be 1..12")
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)

        with self._session() as session:
            rows = (
                session.query(FixedAssignment, Staff)
                .join(Staff, FixedAssignment.staff_id == Staff.id)
                .filter(FixedAssignment.day.between(start, end))
                .all()
            )
            return [
                {
                    "id": fa.id,
                    "staff_id": fa.staff_id,
                    "staff_name": staff.full_name,
                    "day": fa.day.isoformat(),
                    "shift_code": fa.shift_code,
                    "position": fa.position,
                }
                for fa, staff in rows
            ]

    def create_assignment(self, data: dict) -> dict:
        staff_id = data.get("staff_id")
        day_raw = data.get("day")
        shift_code = data.get("shift_code")
        position = data.get("position")

        if staff_id is None or day_raw is None or shift_code is None:
            raise ValidationError("staff_id, day, shift_code required")

        try:
            staff_id = int(staff_id)
        except (TypeError, ValueError):
            raise ValidationError("staff_id must be int")

        try:
            day_value = date.fromisoformat(day_raw)
        except Exception:
            raise ValidationError("day must be YYYY-MM-DD")

        with self._session() as session:
            staff = session.get(Staff, staff_id)
            if not staff:
                raise NotFoundError("Staff not found")

            row = FixedAssignment(
                staff_id=staff_id,
                day=day_value,
                shift_code=shift_code,
                position=position,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "staff_id": row.staff_id,
                "staff_name": staff.full_name,
                "day": row.day.isoformat(),
                "shift_code": row.shift_code,
                "position": row.position,
            }

    def update_assignment(self, assignment_id: int, data: dict) -> dict:
        with self._session() as session:
            row = session.get(FixedAssignment, assignment_id)
            if not row:
                raise NotFoundError("Not found")

            staff = row.staff
            if "staff_id" in data and data["staff_id"] is not None:
                try:
                    staff_id = int(data["staff_id"])
                except (TypeError, ValueError):
                    raise ValidationError("staff_id must be int")
                staff = session.get(Staff, staff_id)
                if not staff:
                    raise NotFoundError("Staff not found")
                row.staff_id = staff_id

            if "day" in data and data["day"] is not None:
                try:
                    row.day = date.fromisoformat(data["day"])
                except Exception:
                    raise ValidationError("day must be YYYY-MM-DD")

            if "shift_code" in data and data["shift_code"] is not None:
                row.shift_code = data["shift_code"]
            if "position" in data:
                row.position = data["position"]

            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "staff_id": row.staff_id,
                "staff_name": staff.full_name if staff else None,
                "day": row.day.isoformat(),
                "shift_code": row.shift_code,
                "position": row.position,
            }

    def delete_assignment(self, assignment_id: int) -> None:
        with self._session() as session:
            row = session.get(FixedAssignment, assignment_id)
            if not row:
                raise NotFoundError("Not found")
            session.delete(row)
            session.commit()


__all__ = ["FixedAssignmentService"]
