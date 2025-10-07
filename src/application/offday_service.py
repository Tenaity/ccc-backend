"""Application services for managing off days."""

from __future__ import annotations

import calendar
from datetime import date
from typing import List

from src.utils.logging import instrument_service
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import OffDay, Staff


@instrument_service
class OffDayService:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def list_off_days(self, *, year: int, month: int) -> List[dict]:
        if month < 1 or month > 12:
            raise ValidationError("month must be 1..12")

        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)

        with self._session() as session:
            rows = (
                session.query(OffDay, Staff)
                .join(Staff, OffDay.staff_id == Staff.id)
                .filter(OffDay.day.between(start, end))
                .all()
            )
            return [
                {
                    "id": off.id,
                    "staff_id": off.staff_id,
                    "staff_name": staff.full_name,
                    "day": off.day.isoformat(),
                    "reason": off.reason,
                }
                for off, staff in rows
            ]

    def create_off_day(self, data: dict) -> dict:
        staff_id = data.get("staff_id")
        day_raw = data.get("day")
        reason = data.get("reason")

        if staff_id is None or day_raw is None:
            raise ValidationError("staff_id and day required")

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

            existing = (
                session.query(OffDay)
                .filter(OffDay.staff_id == staff_id, OffDay.day == day_value)
                .first()
            )
            if existing:
                return {"id": existing.id, "ok": True}

            off = OffDay(staff_id=staff_id, day=day_value, reason=reason)
            session.add(off)
            session.commit()
            return {"id": off.id, "ok": True}

    def delete_off_day(self, off_id: int) -> None:
        with self._session() as session:
            row = session.get(OffDay, off_id)
            if not row:
                raise NotFoundError("Not found")
            session.delete(row)
            session.commit()


__all__ = ["OffDayService"]
