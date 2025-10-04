from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from models import MonthConfig, SessionLocal, WeekendPolicy
from .utils import (
    build_month_config_payload,
    coerce_extra_dates,
    parse_year_month,
)

bp = Blueprint("month_config", __name__)


@bp.get("/api/month-config")
def get_month_config():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, 400
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"Internal error: {exc.__class__.__name__}: {exc}",
                }
            ),
            500,
        )

    try:
        with SessionLocal() as session:
            payload = build_month_config_payload(session, year, month)
            return jsonify(payload)
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"Internal error: {exc.__class__.__name__}: {exc}",
                }
            ),
            500,
        )


@bp.put("/api/month-config")
def upsert_month_config():
    data = request.get_json(silent=True) or {}
    try:
        year, month = parse_year_month(data.get("year"), data.get("month"))
    except ValueError as exc:
        return {"error": str(exc)}, 400
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"Internal error: {exc.__class__.__name__}: {exc}",
                }
            ),
            500,
        )

    try:
        weekend_policy: WeekendPolicy | None = None
        working_days_override: int | None = None

        def _existing_dates(values: list[str] | None) -> set[date]:
            dates: set[date] = set()
            for raw in values or []:
                if not isinstance(raw, str):
                    continue
                try:
                    dt = date.fromisoformat(raw)
                except ValueError:
                    continue
                if dt.year == year and dt.month == month:
                    dates.add(dt)
            return dates

        with SessionLocal() as session:
            config = session.execute(
                select(MonthConfig).where(
                    MonthConfig.year == year, MonthConfig.month == month
                )
            ).scalar_one_or_none()

            if config is None:
                config = MonthConfig(year=year, month=month)
                session.add(config)

            if "weekend_policy" in data:
                policy_raw = data.get("weekend_policy")
                if policy_raw is None:
                    weekend_policy = WeekendPolicy.SAT_OFF
                else:
                    try:
                        weekend_policy = WeekendPolicy(policy_raw)
                    except ValueError as exc:  # pragma: no cover - enum guard
                        raise ValueError("weekend_policy invalid") from exc
            else:
                weekend_policy = config.weekend_policy or WeekendPolicy.SAT_OFF

            override_sentinel = object()
            override_raw = data.get("working_days_override", override_sentinel)
            if override_raw is override_sentinel:
                working_days_override = config.working_days_override
            elif override_raw is None:
                working_days_override = None
            else:
                try:
                    working_days_override = int(override_raw)
                except (TypeError, ValueError) as exc:  # pragma: no cover - guard
                    raise ValueError("working_days_override must be an integer") from exc
                if working_days_override < 0:
                    raise ValueError("working_days_override must be >= 0")

            existing_workdays = _existing_dates(config.extra_workdays)
            existing_offdays = _existing_dates(config.extra_offdays)

            workdays = coerce_extra_dates(
                data.get("extra_workdays"), year, month, "extra_workdays"
            )
            offdays = coerce_extra_dates(
                data.get("extra_offdays"), year, month, "extra_offdays"
            )

            if workdays is None:
                workdays = set(existing_workdays)
            else:
                workdays = set(workdays)
            if offdays is None:
                offdays = set(existing_offdays)
            else:
                offdays = set(offdays)

            workdays -= offdays

            config.year = year
            config.month = month
            config.weekend_policy = weekend_policy
            config.extra_workdays = sorted(dt.isoformat() for dt in workdays)
            config.extra_offdays = sorted(dt.isoformat() for dt in offdays)
            config.working_days_override = working_days_override

            session.commit()

            payload = build_month_config_payload(session, year, month)
            return jsonify(payload)
    except ValueError as exc:
        return {"error": str(exc)}, 400
