"""Application services for month configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import select

from src.utils.logging import instrument_service
from src.application.utils import parse_year_month
from src.domain.exceptions import ValidationError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import (
    Holiday,
    MonthConfig,
    WeekendPolicy,
)
from scheduler.utils import month_last_day


@dataclass
class MonthConfigPayload:
    year: int
    month: int
    auto_working_days: float
    policy_working_days: float
    effective_working_days: float
    config: dict


@instrument_service
class MonthConfigService:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def get_month_config(self, *, year: int, month: int) -> MonthConfigPayload:
        with self._session() as session:
            return self._build_payload(session, year, month)

    def update_month_config(self, data: dict) -> MonthConfigPayload:
        try:
            year, month = parse_year_month(data.get("year"), data.get("month"))
        except ValueError as exc:
            raise ValidationError(str(exc))

        weekend_policy_raw = data.get("weekend_policy")
        if weekend_policy_raw is not None:
            try:
                weekend_policy = WeekendPolicy(weekend_policy_raw)
            except ValueError:
                raise ValidationError("weekend_policy must be one of sat_off, sat_work, sat_work_am")
        else:
            weekend_policy = None

        extra_workdays = self._coerce_extra_dates(
            data.get("extra_workdays"), year, month, "extra_workdays"
        )
        extra_offdays = self._coerce_extra_dates(
            data.get("extra_offdays"), year, month, "extra_offdays"
        )

        working_days_override = data.get("working_days_override")
        if working_days_override is not None:
            try:
                working_days_override = float(working_days_override)
                if working_days_override < 0:
                    raise ValidationError("working_days_override must be >= 0")
            except (TypeError, ValueError):
                raise ValidationError("working_days_override must be a number")

        with self._session() as session:
            config = session.execute(
                select(MonthConfig).where(
                    MonthConfig.year == year,
                    MonthConfig.month == month,
                )
            ).scalar_one_or_none()

            if config is None:
                config = MonthConfig(year=year, month=month)
                session.add(config)

            if weekend_policy is not None:
                config.weekend_policy = weekend_policy
            if extra_workdays is not None:
                config.extra_workdays = sorted(dt.isoformat() for dt in extra_workdays)
            if extra_offdays is not None:
                config.extra_offdays = sorted(dt.isoformat() for dt in extra_offdays)
            if working_days_override is not None or working_days_override == 0:
                config.working_days_override = working_days_override

            session.commit()
            session.refresh(config)

            return self._build_payload(session, year, month)

    # -------------------------- Helpers --------------------------
    @staticmethod
    def _coerce_extra_dates(values, year: int, month: int, field_name: str):
        if values is None:
            return None
        if not isinstance(values, list):
            raise ValidationError(f"{field_name} must be a list of dates")
        parsed = set()
        for item in values:
            if not isinstance(item, str):
                raise ValidationError(f"{field_name} must contain YYYY-MM-DD strings")
            try:
                dt = date.fromisoformat(item)
            except ValueError as exc:
                raise ValidationError(f"{field_name} has invalid date '{item}'") from exc
            if dt.year != year or dt.month != month:
                raise ValidationError(
                    f"{field_name} must stay within {year}-{month:02d}"
                )
            parsed.add(dt)
        return parsed

    def _build_payload(self, session, year: int, month: int) -> MonthConfigPayload:
        config = session.execute(
            select(MonthConfig).where(
                MonthConfig.year == year,
                MonthConfig.month == month,
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
            if (dt := date(year, month, day)).weekday() < 5 and dt not in official_holidays
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

        workday_dates = {
            date.fromisoformat(raw)
            for raw in stored_workdays
            if _safe_same_month(raw, year, month)
        }
        offday_dates = {
            date.fromisoformat(raw)
            for raw in stored_offdays
            if _safe_same_month(raw, year, month)
        }

        for extra in workday_dates:
            if start <= extra <= end:
                day_values[extra] = max(day_values.get(extra, 0.0), 1.0)

        for extra in offday_dates:
            if start <= extra <= end:
                day_values[extra] = 0.0

        policy_working_days = sum(day_values.values())
        effective_working_days = (
            working_days_override
            if working_days_override is not None
            else policy_working_days
        )

        return MonthConfigPayload(
            year=year,
            month=month,
            auto_working_days=auto_working_days,
            policy_working_days=policy_working_days,
            effective_working_days=effective_working_days,
            config={
                "weekend_policy": weekend_policy.value,
                "extra_workdays": sorted(dt.isoformat() for dt in workday_dates),
                "extra_offdays": sorted(dt.isoformat() for dt in offday_dates),
                "working_days_override": working_days_override,
            },
        )


def _safe_same_month(raw: str, year: int, month: int) -> bool:
    try:
        dt = date.fromisoformat(raw)
    except ValueError:
        return False
    return dt.year == year and dt.month == month


__all__ = ["MonthConfigService", "MonthConfigPayload"]

def build_month_config_payload(session, year: int, month: int) -> dict:
    """Compatibility helper returning a dict payload."""

    service = MonthConfigService()
    payload = service._build_payload(session, year, month)
    return {
        "year": payload.year,
        "month": payload.month,
        "auto_working_days": payload.auto_working_days,
        "policy_working_days": payload.policy_working_days,
        "effective_working_days": payload.effective_working_days,
        "config": payload.config,
    }


__all__.append('build_month_config_payload')

