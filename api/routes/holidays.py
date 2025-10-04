from __future__ import annotations

import calendar
import json
import urllib.error
import urllib.request
from datetime import date

from flask import Blueprint, jsonify, request

from models import Holiday, SessionLocal

bp = Blueprint("holidays", __name__)


class HolidayImportError(RuntimeError):
    """Raised when an external holiday provider cannot be fetched."""


def _serialize_holiday(row: Holiday) -> dict:
    return {
        "id": row.id,
        "day": row.day.isoformat(),
        "name": row.name,
        "kind": row.kind,
        "official": bool(row.official),
        "source": row.source,
    }


def _fetch_nager_holidays(year: int, country_code: str = "VN") -> list[dict]:
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}".strip()
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status >= 400:
                raise HolidayImportError(f"Provider returned HTTP {status}")
            payload = response.read()
    except urllib.error.URLError as exc:  # pragma: no cover - network failure branch
        raise HolidayImportError(str(exc)) from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - provider bug branch
        raise HolidayImportError("Invalid JSON payload") from exc

    if not isinstance(data, list):
        raise HolidayImportError("Unexpected response schema")

    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        day = item.get("date")
        try:
            day_value = date.fromisoformat(day)
        except Exception:
            continue
        name = item.get("localName") or item.get("name") or "(unnamed)"
        types = item.get("types") or []
        kind = ",".join(t for t in types if isinstance(t, str)) or None
        official = "Public" in types or bool(item.get("global"))
        out.append(
            {
                "day": day_value,
                "name": name,
                "kind": kind,
                "official": official,
                "source": "nager",
            }
        )
    return out


@bp.get("/api/holidays")
def list_holidays():
    """List holidays for a given year, optionally filtering by month."""

    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int)

    if month is not None and (month < 1 or month > 12):
        return {"error": "month must be 1..12"}, 400

    if month is None:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
    else:
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last_day)

    try:
        with SessionLocal() as session:
            rows = (
                session.query(Holiday)
                .filter(Holiday.day.between(start, end))
                .order_by(Holiday.day.asc())
                .all()
            )
            return jsonify([_serialize_holiday(row) for row in rows])
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


@bp.post("/api/holidays")
def create_holiday():
    data = request.get_json(force=True) or {}
    day_str = data.get("day")
    name = data.get("name")
    kind = data.get("kind") or None
    official = bool(data.get("official", False))
    source = data.get("source") or None

    if not day_str:
        return {"error": "day required"}, 400

    try:
        holiday_day = date.fromisoformat(day_str)
    except Exception:
        return {"error": "day must be YYYY-MM-DD"}, 400

    try:
        with SessionLocal() as session:
            existing = session.query(Holiday).filter(Holiday.day == holiday_day).first()
            if existing:
                return {"ok": True, "item": _serialize_holiday(existing)}

            holiday = Holiday(
                day=holiday_day,
                name=name,
                kind=kind,
                official=official,
                source=source,
            )
            session.add(holiday)
            session.commit()
            session.refresh(holiday)
            return {"ok": True, "item": _serialize_holiday(holiday)}, 201
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


@bp.put("/api/holidays/<int:holiday_id>")
def update_holiday(holiday_id: int):
    data = request.get_json(force=True) or {}

    try:
        with SessionLocal() as session:
            row = session.get(Holiday, holiday_id)
            if not row:
                return {"error": "Not found"}, 404

            if "day" in data:
                day_str = data.get("day")
                try:
                    new_day = date.fromisoformat(day_str)
                except Exception:
                    return {"error": "day must be YYYY-MM-DD"}, 400

                conflict = (
                    session.query(Holiday)
                    .filter(Holiday.day == new_day, Holiday.id != holiday_id)
                    .first()
                )
                if conflict:
                    return {"error": "day already exists"}, 409
                row.day = new_day

            if "name" in data:
                row.name = data.get("name")
            if "kind" in data:
                row.kind = data.get("kind") or None
            if "official" in data:
                row.official = bool(data.get("official"))
            if "source" in data:
                row.source = data.get("source") or None

            session.commit()
            session.refresh(row)
            return {"ok": True, "item": _serialize_holiday(row)}
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


@bp.delete("/api/holidays/<int:holiday_id>")
def delete_holiday(holiday_id: int):
    try:
        with SessionLocal() as session:
            row = session.get(Holiday, holiday_id)
            if not row:
                return {"error": "Not found"}, 404
            session.delete(row)
            session.commit()
            return {"ok": True}
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


@bp.post("/api/holidays/import")
def import_holidays():
    """Import holidays from external providers."""

    year = request.args.get("year", type=int)
    source = (request.args.get("source") or "").lower()

    if not year:
        return {"error": "year required"}, 400
    if source != "nager":
        return {"error": "unsupported source"}, 400

    try:
        incoming = _fetch_nager_holidays(year)
    except HolidayImportError as exc:
        return {"error": f"Import failed: {exc}"}, 502

    days = [item["day"] for item in incoming]

    try:
        with SessionLocal() as session:
            existing_rows = (
                session.query(Holiday)
                .filter(Holiday.day.in_(days))
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
                    holiday = Holiday(
                        day=item["day"],
                        name=item["name"],
                        kind=item["kind"],
                        official=item["official"],
                        source=item["source"],
                    )
                    session.add(holiday)
                    inserted += 1

            session.commit()

            year_rows = (
                session.query(Holiday)
                .filter(
                    Holiday.day.between(
                        date(year, 1, 1),
                        date(year, 12, 31),
                    )
                )
                .order_by(Holiday.day.asc())
                .all()
            )

            return {
                "ok": True,
                "inserted": inserted,
                "updated": updated,
                "items": [_serialize_holiday(row) for row in year_rows],
            }
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
