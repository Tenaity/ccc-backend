"""Application services for staff management."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select

from src.utils.logging import instrument_service
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import (
    ShiftConfig,
    Staff,
    StaffPreferences,
)


@instrument_service
class StaffService:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def list_staff(
        self,
        *,
        department_id: Optional[int] = None,
        role_filter: Optional[str] = None,
        query: str = "",
    ) -> List[dict]:
        with self._session() as session:
            query_stmt = select(Staff)
            if department_id is not None:
                query_stmt = query_stmt.where(Staff.department_id == department_id)

            if role_filter:
                roles = {
                    item.strip().upper()
                    for item in role_filter.split(",")
                    if item.strip()
                }
                if roles:
                    query_stmt = query_stmt.where(func.upper(Staff.role).in_(sorted(roles)))

            if query:
                pattern = f"%{query.lower()}%"
                query_stmt = query_stmt.where(func.lower(Staff.full_name).like(pattern))

            query_stmt = query_stmt.order_by(func.lower(Staff.full_name))

            rows = session.execute(query_stmt).scalars().all()
            return [
                {
                    "id": row.id,
                    "full_name": row.full_name,
                    "role": row.role,
                    "can_night": row.can_night,
                    "base_quota": row.base_quota,
                    "notes": row.notes,
                    "department_id": row.department_id,
                    "department_name": row.department.name if row.department else None,
                }
                for row in rows
            ]

    def create_staff(self, data: dict) -> dict:
        required = data.get("full_name")
        if not required:
            raise ValidationError("full_name is required")
        with self._session() as session:
            row = Staff(
                full_name=data["full_name"],
                role=data.get("role", "GDV"),
                can_night=bool(data.get("can_night", True)),
                base_quota=float(data.get("base_quota", 26.0)),
                notes=data.get("notes"),
                department_id=data.get("department_id"),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "full_name": row.full_name,
                "department_id": row.department_id,
            }

    def update_staff(self, staff_id: int, data: dict) -> dict:
        with self._session() as session:
            row = session.get(Staff, staff_id)
            if not row:
                raise NotFoundError("Staff not found")

            if "full_name" in data:
                row.full_name = data["full_name"]
            if "role" in data:
                row.role = data["role"]
            if "can_night" in data:
                row.can_night = bool(data["can_night"])
            if "base_quota" in data:
                row.base_quota = float(data["base_quota"])
            if "notes" in data:
                row.notes = data["notes"]
            if "department_id" in data:
                row.department_id = data["department_id"]

            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "full_name": row.full_name,
                "role": row.role,
                "can_night": row.can_night,
                "base_quota": row.base_quota,
                "notes": row.notes,
                "department_id": row.department_id,
                "department_name": row.department.name if row.department else None,
            }

    def delete_staff(self, staff_id: int) -> None:
        with self._session() as session:
            row = session.get(Staff, staff_id)
            if not row:
                raise NotFoundError("Staff not found")
            session.delete(row)
            session.commit()

    def get_preferences(self, staff_id: int) -> dict:
        with self._session() as session:
            staff = session.get(Staff, staff_id)
            if not staff:
                raise NotFoundError("Staff not found")

            prefs = staff.preferences
            if not prefs:
                return {
                    "staff_id": staff_id,
                    "preferred_shifts": [],
                    "unavailable_days": [],
                    "max_consecutive_days": 6,
                    "preferred_days_off": [],
                    "notes": None,
                }

            return {
                "staff_id": prefs.staff_id,
                "preferred_shifts": prefs.preferred_shifts or [],
                "unavailable_days": prefs.unavailable_days or [],
                "max_consecutive_days": prefs.max_consecutive_days,
                "preferred_days_off": prefs.preferred_days_off or [],
                "notes": prefs.notes,
            }

    def update_preferences(self, staff_id: int, data: dict) -> dict:
        preferred_shifts = data.get("preferred_shifts", [])
        unavailable_days = data.get("unavailable_days", [])
        max_consecutive_days = data.get("max_consecutive_days")
        preferred_days_off = data.get("preferred_days_off", [])
        notes = data.get("notes")

        if max_consecutive_days is not None:
            try:
                max_consecutive_days = int(max_consecutive_days)
            except (ValueError, TypeError):
                raise ValidationError("max_consecutive_days must be a number")
            if max_consecutive_days < 0:
                raise ValidationError("max_consecutive_days must be >= 0")

        for day_str in unavailable_days:
            try:
                datetime.fromisoformat(day_str)
            except (ValueError, TypeError):
                raise ValidationError(
                    f"Invalid date format: {day_str}. Use YYYY-MM-DD"
                )

        for day_num in preferred_days_off:
            if not isinstance(day_num, int) or day_num < 0 or day_num > 6:
                raise ValidationError(
                    f"Invalid day number: {day_num}. Must be 0-6 (Mon-Sun)"
                )

        with self._session() as session:
            staff = session.get(Staff, staff_id)
            if not staff:
                raise NotFoundError("Staff not found")

            if staff.department_id and preferred_shifts:
                valid_shift_codes = set(
                    session.execute(
                        select(ShiftConfig.code)
                        .where(ShiftConfig.department_id == staff.department_id)
                        .where(ShiftConfig.is_active == True)  # noqa: E712 - SQLAlchemy truthy check
                    )
                    .scalars()
                    .all()
                )
                for shift_code in preferred_shifts:
                    if shift_code not in valid_shift_codes:
                        raise ValidationError(
                            f"Invalid shift code '{shift_code}' for department. "
                            f"Valid codes: {sorted(valid_shift_codes)}"
                        )

            prefs = staff.preferences
            if not prefs:
                prefs = StaffPreferences(staff_id=staff_id)
                session.add(prefs)

            prefs.preferred_shifts = preferred_shifts
            prefs.unavailable_days = unavailable_days
            prefs.max_consecutive_days = max_consecutive_days
            prefs.preferred_days_off = preferred_days_off
            prefs.notes = notes

            session.commit()
            session.refresh(prefs)

            return {
                "staff_id": prefs.staff_id,
                "preferred_shifts": prefs.preferred_shifts or [],
                "unavailable_days": prefs.unavailable_days or [],
                "max_consecutive_days": prefs.max_consecutive_days,
                "preferred_days_off": prefs.preferred_days_off or [],
                "notes": prefs.notes,
            }


__all__ = ["StaffService"]
