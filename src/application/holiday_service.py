"""Application services for managing holidays."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.utils.logging import instrument_service
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.holiday import HolidayDTO
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import Holiday
from src.infrastructure.providers.holiday_provider import HolidayProviderError


@instrument_service
class HolidayService:
    """Encapsulates holiday use-cases."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def _provider(self):
        from importlib import import_module

        module = import_module("app")
        return getattr(module, "_fetch_nager_holidays")

    # -------------------------- Queries --------------------------
    def list_holidays(self, year: int, month: Optional[int] = None) -> List[HolidayDTO]:
        start, end = self._resolve_range(year, month)
        with self._session() as session:
            rows = (
                session.execute(
                    select(Holiday).where(Holiday.day.between(start, end)).order_by(Holiday.day.asc())
                )
                .scalars()
                .all()
            )
            return [self._to_dto(row) for row in rows]

    # -------------------------- Commands --------------------------
    def create_holiday(
        self,
        *,
        day: date,
        name: Optional[str],
        kind: Optional[str],
        official: bool,
        source: Optional[str],
    ) -> Tuple[HolidayDTO, bool]:
        with self._session() as session:
            existing = session.execute(
                select(Holiday).where(Holiday.day == day)
            ).scalar_one_or_none()
            if existing:
                return self._to_dto(existing), False

            row = Holiday(
                day=day,
                name=name,
                kind=kind,
                official=official,
                source=source,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_dto(row), True

    def update_holiday(self, holiday_id: int, **changes) -> HolidayDTO:
        with self._session() as session:
            row = session.get(Holiday, holiday_id)
            if not row:
                raise NotFoundError("Holiday not found")

            if "day" in changes and changes["day"] is not None:
                new_day = changes["day"]
                conflict = session.execute(
                    select(Holiday).where(Holiday.day == new_day, Holiday.id != holiday_id)
                ).scalar_one_or_none()
                if conflict:
                    raise ConflictError("day already exists")
                row.day = new_day

            if "name" in changes:
                row.name = changes["name"]
            if "kind" in changes:
                row.kind = changes["kind"]
            if "official" in changes:
                row.official = bool(changes["official"])
            if "source" in changes:
                row.source = changes["source"]

            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ConflictError("day already exists") from exc
            except Exception as exc:
                session.rollback()
                raise ConflictError("day already exists") from exc
            session.refresh(row)
            return self._to_dto(row)

    def delete_holiday(self, holiday_id: int) -> None:
        with self._session() as session:
            row = session.get(Holiday, holiday_id)
            if not row:
                raise NotFoundError("Holiday not found")
            session.delete(row)
            session.commit()

    def import_holidays(self, *, year: int, provider: str) -> Tuple[List[HolidayDTO], int, int]:
        if provider.lower() != "nager":
            raise ValidationError("unsupported source")

        provider = self._provider()
        try:
            incoming = provider(year)
        except HolidayProviderError as exc:  # pragma: no cover - network failure branch
            raise ValidationError(f"Import failed: {exc}") from exc

        with self._session() as session:
            days = [item["day"] for item in incoming]
            existing_rows = (
                session.execute(select(Holiday).where(Holiday.day.in_(days)))
                .scalars()
                .all()
                if days
                else []
            )
            existing_by_day = {row.day: row for row in existing_rows}

            inserted = 0
            updated = 0

            for item in incoming:
                existing = existing_by_day.get(item["day"])
                if existing:
                    existing.name = item["name"]
                    existing.kind = item["kind"]
                    existing.official = item["official"]
                    existing.source = item["source"]
                    updated += 1
                else:
                    row = Holiday(
                        day=item["day"],
                        name=item["name"],
                        kind=item["kind"],
                        official=item["official"],
                        source=item["source"],
                    )
                    session.add(row)
                    inserted += 1

            session.commit()

            year_rows = (
                session.execute(
                    select(Holiday)
                    .where(
                        Holiday.day.between(
                            date(year, 1, 1),
                            date(year, 12, 31),
                        )
                    )
                    .order_by(Holiday.day.asc())
                )
                .scalars()
                .all()
            )

            return [self._to_dto(row) for row in year_rows], inserted, updated

    # -------------------------- Helpers --------------------------
    @staticmethod
    def _resolve_range(year: int, month: Optional[int]) -> Tuple[date, date]:
        if month is not None and (month < 1 or month > 12):
            raise ValidationError("month must be 1..12")
        if month is None:
            return date(year, 1, 1), date(year, 12, 31)
        import calendar
        start = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        return start, date(year, month, last_day)

    @staticmethod
    def _to_dto(row: Holiday) -> HolidayDTO:
        return HolidayDTO(
            id=row.id,
            day=row.day,
            name=row.name,
            kind=row.kind,
            official=bool(row.official),
            source=row.source,
        )


__all__ = ["HolidayService"]
