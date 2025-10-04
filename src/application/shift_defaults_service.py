"""Application services for shift defaults management."""

from __future__ import annotations

from sqlalchemy import select

from src.application.utils import parse_year_month
from src.domain.exceptions import ValidationError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import ShiftPlanDefaults


class ShiftDefaultsService:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def get_defaults(self, *, year: int, month: int) -> dict:
        try:
            year, month = parse_year_month(year, month)
        except ValueError as exc:
            raise ValidationError(str(exc))

        with self._session() as session:
            defaults = session.execute(
                select(ShiftPlanDefaults).where(
                    ShiftPlanDefaults.year == year,
                    ShiftPlanDefaults.month == month,
                )
            ).scalar_one_or_none()
            return self._serialize(defaults, year, month)

    def upsert_defaults(self, data: dict) -> dict:
        try:
            year, month = parse_year_month(data.get("year"), data.get("month"))
        except ValueError as exc:
            raise ValidationError(str(exc))

        fields = ["day_shifts", "night_shifts", "leader_shifts", "pgd_shifts"]
        missing = [field for field in fields if field not in data]
        if missing:
            raise ValidationError(f"Missing fields: {', '.join(missing)}")

        validated: dict[str, int] = {}
        for field in fields:
            value = data.get(field)
            if not isinstance(value, int):
                raise ValidationError(f"{field} must be an integer")
            if value < 0:
                raise ValidationError(f"{field} must be >= 0")
            validated[field] = value

        with self._session() as session:
            defaults = session.execute(
                select(ShiftPlanDefaults).where(
                    ShiftPlanDefaults.year == year,
                    ShiftPlanDefaults.month == month,
                )
            ).scalar_one_or_none()

            if defaults is None:
                defaults = ShiftPlanDefaults(
                    year=year,
                    month=month,
                    day_shifts=validated["day_shifts"],
                    night_shifts=validated["night_shifts"],
                    leader_shifts=validated["leader_shifts"],
                    pgd_shifts=validated["pgd_shifts"],
                )
                session.add(defaults)
            else:
                defaults.day_shifts = validated["day_shifts"]
                defaults.night_shifts = validated["night_shifts"]
                defaults.leader_shifts = validated["leader_shifts"]
                defaults.pgd_shifts = validated["pgd_shifts"]

            session.commit()
            session.refresh(defaults)
            return self._serialize(defaults, year, month)

    @staticmethod
    def _serialize(defaults, year: int, month: int) -> dict:
        return {
            "year": year,
            "month": month,
            "day_shifts": defaults.day_shifts if defaults else 0,
            "night_shifts": defaults.night_shifts if defaults else 0,
            "leader_shifts": defaults.leader_shifts if defaults else 0,
            "pgd_shifts": defaults.pgd_shifts if defaults else 0,
        }


__all__ = ["ShiftDefaultsService"]
