"""HTTP routes for holiday resources."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from http import HTTPStatus
from typing import Optional

from flask import Blueprint, jsonify, request

from src.application.holiday_service import HolidayService
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.holiday import HolidayDTO

holiday_bp = Blueprint("holiday", __name__, url_prefix="/api/holidays")
service = HolidayService()


def _serialize(dto: HolidayDTO) -> dict:
    payload = asdict(dto)
    payload["day"] = dto.day.isoformat()
    return payload


@holiday_bp.get("")
def list_holidays():
    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int)

    try:
        rows = service.list_holidays(year=year, month=month)
        return jsonify([_serialize(row) for row in rows])
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify({"ok": False, "error": f"Internal error: {exc.__class__.__name__}: {exc}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@holiday_bp.post("")
def create_holiday():
    data = request.get_json(force=True) or {}
    day_raw = data.get("day")

    if not day_raw:
        return {"error": "day required"}, HTTPStatus.BAD_REQUEST

    try:
        day = date.fromisoformat(day_raw)
    except Exception:
        return {"error": "day must be YYYY-MM-DD"}, HTTPStatus.BAD_REQUEST

    try:
        dto, created = service.create_holiday(
            day=day,
            name=data.get("name"),
            kind=data.get("kind") or None,
            official=bool(data.get("official", False)),
            source=data.get("source") or None,
        )
        status = HTTPStatus.CREATED if created else HTTPStatus.OK
        return {"ok": True, "item": _serialize(dto)}, status
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify({"ok": False, "error": f"Internal error: {exc.__class__.__name__}: {exc}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@holiday_bp.put("/<int:holiday_id>")
def update_holiday(holiday_id: int):
    data = request.get_json(force=True) or {}

    changes = {}
    if "day" in data and data["day"] is not None:
        try:
            changes["day"] = date.fromisoformat(data["day"])
        except Exception:
            return {"error": "day must be YYYY-MM-DD"}, HTTPStatus.BAD_REQUEST
    if "name" in data:
        changes["name"] = data.get("name")
    if "kind" in data:
        changes["kind"] = data.get("kind") or None
    if "official" in data:
        changes["official"] = bool(data.get("official"))
    if "source" in data:
        changes["source"] = data.get("source") or None

    try:
        dto = service.update_holiday(holiday_id, **changes)
        return {"ok": True, "item": _serialize(dto)}
    except NotFoundError:
        return {"error": "Not found"}, HTTPStatus.NOT_FOUND
    except ConflictError as exc:
        return {"error": str(exc)}, HTTPStatus.CONFLICT
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify({"ok": False, "error": f"Internal error: {exc.__class__.__name__}: {exc}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@holiday_bp.delete("/<int:holiday_id>")
def delete_holiday(holiday_id: int):
    try:
        service.delete_holiday(holiday_id)
        return {"ok": True}
    except NotFoundError:
        return {"error": "Not found"}, HTTPStatus.NOT_FOUND
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify({"ok": False, "error": f"Internal error: {exc.__class__.__name__}: {exc}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )


@holiday_bp.post("/import")
def import_holidays():
    year = request.args.get("year", type=int)
    source = (request.args.get("source") or "")

    if not year:
        return {"error": "year required"}, HTTPStatus.BAD_REQUEST

    try:
        rows, inserted, updated = service.import_holidays(year=year, provider=source)
        return {
            "ok": True,
            "inserted": inserted,
            "updated": updated,
            "items": [_serialize(row) for row in rows],
        }
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except Exception as exc:  # pragma: no cover - defensive guard
        return (
            jsonify({"ok": False, "error": f"Internal error: {exc.__class__.__name__}: {exc}"}),
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
