# backend/app.py
import calendar
import csv
import io
import json
import os
import pathlib
import urllib.error
import urllib.request
from datetime import date, timedelta

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from flask_cors import CORS
from sqlalchemy import select, text

from dotenv import load_dotenv

load_dotenv()

from api.export_month_csv import export_month_csv as _export_month_csv
from models import (
    Assignment,
    FixedAssignment,
    Holiday,
    MonthConfig,
    OffDay,
    ShiftPlanDefaults,
    SessionLocal,
    Staff,
    WeekendPolicy,
    engine,
    init_db,
)
from rules import SHIFT_DEFS, get_profile
from scheduler import schedule_month as generate_schedule
from scheduler.estimator import estimate_month
from scheduler.repo import load_holidays
from scheduler.utils import day_kind, month_last_day, ymd
from scheduler.validate import validate_month

# Trỏ tới thư mục build của frontend (Vite) nếu đã build
BASE_DIR = pathlib.Path(__file__).parent
DEFAULT_FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
frontend_override = os.getenv("FRONTEND_DIST")
frontend_path = pathlib.Path(frontend_override).expanduser() if frontend_override else DEFAULT_FRONTEND_DIST
frontend_static = str(frontend_path.resolve()) if frontend_path.exists() else None

db_path = pathlib.Path(engine.url.database).expanduser() if engine.url.database else None
if db_path and not db_path.is_absolute():
    db_path = (pathlib.Path.cwd() / db_path).resolve()
DB_FILE = db_path

app = Flask(
    __name__,
    static_folder=frontend_static,
    static_url_path="/",
)
cors_raw = os.getenv("CORS_ORIGINS", "*")
cors_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]
CORS(app, origins=cors_origins or ["*"], supports_credentials=True)

APP_HOST = os.getenv("HOST", "0.0.0.0")
APP_PORT = int(os.getenv("PORT", "8000"))
APP_DEBUG = os.getenv("APP_ENV", "local").lower() != "production"

# Khởi tạo DB (tạo bảng nếu chưa có)
init_db()


class HolidayImportError(RuntimeError):
    """Raised when an external holiday provider cannot be fetched."""


def _serialize_holiday(row: Holiday) -> dict:
    """Convert a Holiday row to JSON-serialisable dict."""

    return {
        "id": row.id,
        "day": row.day.isoformat(),
        "name": row.name,
        "kind": row.kind,
        "official": bool(row.official),
        "source": row.source,
    }


def _fetch_nager_holidays(year: int, country_code: str = "VN") -> list[dict]:
    """Fetch holidays from Nager.Date API for a year."""

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


def _parse_year_month(year_raw, month_raw) -> tuple[int, int]:
    """Validate and convert year/month inputs."""

    if year_raw is None or month_raw is None:
        raise ValueError("year and month required")
    try:
        year = int(year_raw)
        month = int(month_raw)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive guard
        raise ValueError("year and month must be integers") from exc
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    if year < 1900 or year > 2100:
        raise ValueError("year must be between 1900 and 2100")
    return year, month


def _coerce_extra_dates(
    values: object, year: int, month: int, field_name: str
) -> set[date] | None:
    """Validate optional list of YYYY-MM-DD strings limited to the target month."""

    if values is None:
        return None
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list of dates")

    parsed: set[date] = set()
    for item in values:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain YYYY-MM-DD strings")
        try:
            dt = date.fromisoformat(item)
        except ValueError as exc:
            raise ValueError(f"{field_name} has invalid date '{item}'") from exc
        if dt.year != year or dt.month != month:
            raise ValueError(
                f"{field_name} must stay within {year}-{month:02d}"
            )
        parsed.add(dt)
    return parsed


def _build_month_config_payload(session, year: int, month: int) -> dict:
    """Construct payload for month config, including derived working days."""

    config = session.execute(
        select(MonthConfig).where(
            MonthConfig.year == year, MonthConfig.month == month
        )
    ).scalar_one_or_none()

    weekend_policy = (
        config.weekend_policy if config else WeekendPolicy.SAT_OFF
    )
    stored_workdays = config.extra_workdays if config else []
    stored_offdays = config.extra_offdays if config else []
    working_days_override = (
        config.working_days_override if config else None
    )

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
        if (dt := date(year, month, day)).weekday() < 5
        and dt not in official_holidays
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

    workday_dates = set()
    for raw in stored_workdays:
        try:
            dt = date.fromisoformat(raw)
        except ValueError:
            continue
        if dt.year == year and dt.month == month:
            workday_dates.add(dt)
    offday_dates = set()
    for raw in stored_offdays:
        try:
            dt = date.fromisoformat(raw)
        except ValueError:
            continue
        if dt.year == year and dt.month == month:
            offday_dates.add(dt)

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

    payload = {
        "year": year,
        "month": month,
        "auto_working_days": auto_working_days,
        "policy_working_days": policy_working_days,
        "effective_working_days": effective_working_days,
        "config": {
            "weekend_policy": weekend_policy.value,
            "extra_workdays": sorted(dt.isoformat() for dt in workday_dates),
            "extra_offdays": sorted(dt.isoformat() for dt in offday_dates),
            "working_days_override": working_days_override,
        },
    }
    return payload


def _serialize_shift_defaults(
    defaults: ShiftPlanDefaults | None, year: int, month: int
) -> dict:
    """Return API payload describing stored shift plan defaults for a month."""

    return {
        "year": year,
        "month": month,
        "day_shifts": defaults.day_shifts if defaults else 0,
        "night_shifts": defaults.night_shifts if defaults else 0,
        "leader_shifts": defaults.leader_shifts if defaults else 0,
        "pgd_shifts": defaults.pgd_shifts if defaults else 0,
    }


# ---------- Root / SPA ----------
@app.get("/")
def root():
    """Nếu đã build frontend thì trả index.html, còn không trả JSON giới thiệu API."""
    if app.static_folder and os.path.isfile(os.path.join(app.static_folder, "index.html")):
        return send_from_directory(app.static_folder, "index.html")
    return jsonify(
        service="customer-care-center API",
        ok=True,
        docs=[
            "/api/ping",
            "/api/shifts",
            "/api/staff",
            "/api/assignments?year=YYYY&month=MM",
            "/api/schedule/generate (POST)",
            "/api/admin/reset?mode=soft (POST)",
        ],
    )


@app.route("/<path:path>")
def spa_assets(path: str):
    """Phục vụ static assets và fallback cho route SPA."""
    if app.static_folder:
        p = os.path.join(app.static_folder, path)
        if os.path.isfile(p):
            return send_from_directory(app.static_folder, path)
        index_html = os.path.join(app.static_folder, "index.html")
        if os.path.isfile(index_html):
            return send_from_directory(app.static_folder, "index.html")
    return {"error": "Not Found"}, 404


# ---------- API ----------
@app.get("/api/ping")
def ping():
    return {"ok": True}


@app.get("/api/shifts")
def shifts():
    return jsonify(SHIFT_DEFS)


@app.get("/api/staff")
def list_staff():
    with SessionLocal() as s:
        rows = s.execute(select(Staff)).scalars().all()
        return jsonify(
            [
                {
                    "id": r.id,
                    "full_name": r.full_name,
                    "role": r.role,
                    "can_night": r.can_night,
                    "base_quota": r.base_quota,
                    "notes": r.notes,
                }
                for r in rows
            ]
        )


@app.post("/api/staff")
def add_staff():
    data = request.get_json(force=True)
    with SessionLocal() as s:
        r = Staff(
            full_name=data["full_name"],
            role=data.get("role", "GDV"),
            can_night=bool(data.get("can_night", True)),
            base_quota=float(data.get("base_quota", 26.0)),
            notes=data.get("notes"),
        )
        s.add(r)
        s.commit()
        return {"id": r.id}


@app.delete("/api/staff/<int:staff_id>")
def del_staff(staff_id: int):
    with SessionLocal() as s:
        r = s.get(Staff, staff_id)
        if not r:
            return {"error": "Not found"}, 404
        s.delete(r)
        s.commit()
        return {"ok": True}


@app.get("/api/fixed")
def list_fixed_assignments():
    """List fixed assignments for a given month."""
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month

    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last_day)

    try:
        with SessionLocal() as s:
            rows = (
                s.query(FixedAssignment, Staff)
                .join(Staff, FixedAssignment.staff_id == Staff.id)
                .filter(FixedAssignment.day.between(start, end))
                .all()
            )
            out = [
                {
                    "id": fa.id,
                    "staff_id": fa.staff_id,
                    "staff_name": st.full_name,
                    "day": fa.day.isoformat(),
                    "shift_code": fa.shift_code,
                    "position": fa.position,
                }
                for fa, st in rows
            ]
            return jsonify(out)
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.post("/api/fixed")
def create_fixed_assignment():
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    shift_code = data.get("shift_code")
    position = data.get("position")

    if staff_id is None or day_str is None or shift_code is None:
        return {"error": "staff_id, day, shift_code required"}, 400

    try:
        staff_id = int(staff_id)
    except Exception:
        return {"error": "staff_id must be int"}, 400

    try:
        d = date.fromisoformat(day_str)
    except Exception:
        return {"error": "day must be YYYY-MM-DD"}, 400

    try:
        with SessionLocal() as s:
            staff = s.get(Staff, staff_id)
            if not staff:
                return {"error": "Staff not found"}, 404

            fa = FixedAssignment(
                staff_id=staff_id,
                day=d,
                shift_code=shift_code,
                position=position,
            )
            s.add(fa)
            s.commit()
            item = {
                "id": fa.id,
                "staff_id": fa.staff_id,
                "staff_name": staff.full_name,
                "day": fa.day.isoformat(),
                "shift_code": fa.shift_code,
                "position": fa.position,
            }
            return {"ok": True, "item": item}, 201
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.put("/api/fixed/<int:fix_id>")
def update_fixed_assignment(fix_id: int):
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    shift_code = data.get("shift_code")
    position = data.get("position")

    try:
        with SessionLocal() as s:
            fa = s.get(FixedAssignment, fix_id)
            if not fa:
                return {"error": "Not found"}, 404

            if staff_id is not None:
                try:
                    staff_id = int(staff_id)
                except Exception:
                    return {"error": "staff_id must be int"}, 400
                staff = s.get(Staff, staff_id)
                if not staff:
                    return {"error": "Staff not found"}, 404
                fa.staff_id = staff_id
            else:
                staff = fa.staff

            if day_str is not None:
                try:
                    fa.day = date.fromisoformat(day_str)
                except Exception:
                    return {"error": "day must be YYYY-MM-DD"}, 400

            if shift_code is not None:
                fa.shift_code = shift_code
            if position is not None:
                fa.position = position

            s.commit()
            item = {
                "id": fa.id,
                "staff_id": fa.staff_id,
                "staff_name": staff.full_name if staff else None,
                "day": fa.day.isoformat(),
                "shift_code": fa.shift_code,
                "position": fa.position,
            }
            return {"ok": True, "item": item}
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.delete("/api/fixed/<int:fix_id>")
def delete_fixed_assignment(fix_id: int):
    try:
        with SessionLocal() as s:
            fa = s.get(FixedAssignment, fix_id)
            if not fa:
                return {"error": "Not found"}, 404
            s.delete(fa)
            s.commit()
            return {"ok": True}
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.get("/api/off")
def list_off_days():
    """List off days for a given month (defaults to current)."""
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month

    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last_day)
    print(f"[API] off GET {y}-{m}", flush=True)

    try:
        with SessionLocal() as s:
            rows = (
                s.query(OffDay, Staff)
                .join(Staff, OffDay.staff_id == Staff.id)
                .filter(OffDay.day.between(start, end))
                .all()
            )
            out = [
                {
                    "id": od.id,
                    "staff_id": od.staff_id,
                    "staff_name": st.full_name,
                    "day": od.day.isoformat(),
                    "reason": od.reason,
                }
                for od, st in rows
            ]
            return jsonify(out)
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.post("/api/off")
def create_off_day():
    data = request.get_json(force=True) or {}
    staff_id = data.get("staff_id")
    day_str = data.get("day")
    reason = data.get("reason")

    if staff_id is None or day_str is None:
        return {"error": "staff_id and day required"}, 400

    try:
        staff_id = int(staff_id)
    except Exception:
        return {"error": "staff_id must be int"}, 400

    try:
        d = date.fromisoformat(day_str)
    except Exception:
        return {"error": "day must be YYYY-MM-DD"}, 400

    print(f"[API] off POST {staff_id} {day_str}", flush=True)

    try:
        with SessionLocal() as s:
            staff = s.get(Staff, staff_id)
            if not staff:
                return {"error": "Staff not found"}, 404

            existing = s.query(OffDay).filter(OffDay.staff_id == staff_id, OffDay.day == d).first()
            if existing:
                return {"id": existing.id, "ok": True}

            off = OffDay(staff_id=staff_id, day=d, reason=reason)
            s.add(off)
            s.commit()
            return {"id": off.id, "ok": True}, 201
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.delete("/api/off/<int:off_id>")
def delete_off_day(off_id: int):
    print(f"[API] off DELETE {off_id}", flush=True)
    try:
        with SessionLocal() as s:
            r = s.get(OffDay, off_id)
            if not r:
                return {"error": "Not found"}, 404
            s.delete(r)
            s.commit()
            return {"ok": True}
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


# ---------- Holidays ----------
@app.get("/api/holidays")
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
        with SessionLocal() as s:
            rows = (
                s.query(Holiday)
                .filter(Holiday.day.between(start, end))
                .order_by(Holiday.day.asc())
                .all()
            )
            return jsonify([_serialize_holiday(row) for row in rows])
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.post("/api/holidays")
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
        with SessionLocal() as s:
            existing = s.query(Holiday).filter(Holiday.day == holiday_day).first()
            if existing:
                return {"ok": True, "item": _serialize_holiday(existing)}

            holiday = Holiday(
                day=holiday_day,
                name=name,
                kind=kind,
                official=official,
                source=source,
            )
            s.add(holiday)
            s.commit()
            s.refresh(holiday)
            return {"ok": True, "item": _serialize_holiday(holiday)}, 201
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.put("/api/holidays/<int:holiday_id>")
def update_holiday(holiday_id: int):
    data = request.get_json(force=True) or {}

    try:
        with SessionLocal() as s:
            row = s.get(Holiday, holiday_id)
            if not row:
                return {"error": "Not found"}, 404

            if "day" in data:
                day_str = data.get("day")
                try:
                    new_day = date.fromisoformat(day_str)
                except Exception:
                    return {"error": "day must be YYYY-MM-DD"}, 400

                conflict = (
                    s.query(Holiday)
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

            s.commit()
            s.refresh(row)
            return {"ok": True, "item": _serialize_holiday(row)}
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.delete("/api/holidays/<int:holiday_id>")
def delete_holiday(holiday_id: int):
    try:
        with SessionLocal() as s:
            row = s.get(Holiday, holiday_id)
            if not row:
                return {"error": "Not found"}, 404
            s.delete(row)
            s.commit()
            return {"ok": True}
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


@app.post("/api/holidays/import")
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
        with SessionLocal() as s:
            existing_rows = (
                s.query(Holiday)
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
                    s.add(holiday)
                    inserted += 1

            s.commit()

            year_rows = (
                s.query(Holiday)
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
    except Exception as e:
        return (
            jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}),
            500,
        )


# ---------- Shift plan defaults ----------
@app.get("/api/shift-defaults")
def get_shift_defaults():
    try:
        year, month = _parse_year_month(
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
            defaults = session.execute(
                select(ShiftPlanDefaults).where(
                    ShiftPlanDefaults.year == year,
                    ShiftPlanDefaults.month == month,
                )
            ).scalar_one_or_none()
            return jsonify(_serialize_shift_defaults(defaults, year, month))
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


@app.put("/api/shift-defaults")
def upsert_shift_defaults():
    data = request.get_json(silent=True) or {}
    try:
        year, month = _parse_year_month(data.get("year"), data.get("month"))
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

    fields = ["day_shifts", "night_shifts", "leader_shifts", "pgd_shifts"]
    missing = [field for field in fields if field not in data]
    if missing:
        return {"error": f"Missing fields: {', '.join(missing)}"}, 400

    validated: dict[str, int] = {}
    for field in fields:
        value = data.get(field)
        if not isinstance(value, int):
            return {"error": f"{field} must be an integer"}, 400
        if value < 0:
            return {"error": f"{field} must be >= 0"}, 400
        validated[field] = value

    try:
        with SessionLocal() as session:
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
                for field, value in validated.items():
                    setattr(defaults, field, value)

            session.commit()
            session.refresh(defaults)
            return jsonify(_serialize_shift_defaults(defaults, year, month))
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


# ---------- Month config ----------
@app.get("/api/month-config")
def get_month_config():
    try:
        year, month = _parse_year_month(
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
            payload = _build_month_config_payload(session, year, month)
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


@app.put("/api/month-config")
def upsert_month_config():
    data = request.get_json(silent=True) or {}
    try:
        year, month = _parse_year_month(data.get("year"), data.get("month"))
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
        weekend_policy = None
        working_days_override = None

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

            workdays = _coerce_extra_dates(
                data.get("extra_workdays"), year, month, "extra_workdays"
            )
            offdays = _coerce_extra_dates(
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

            payload = _build_month_config_payload(session, year, month)
            return jsonify(payload)
    except ValueError as exc:
        return {"error": str(exc)}, 400


# Backwards‑compat aliases for old /api/offdays routes
@app.get("/api/offdays")
def list_off_days_alias():
    return list_off_days()


@app.post("/api/offdays")
def create_off_day_alias():
    return create_off_day()


@app.delete("/api/offdays/<int:off_id>")
def delete_off_day_alias(off_id: int):
    return delete_off_day(off_id)


@app.get("/api/assignments")
def list_assignments():
    """Trả danh sách phân ca theo tháng (mặc định tháng hiện tại nếu thiếu params)."""
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month

    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last_day)

    with SessionLocal() as s:
        rows = s.query(Assignment).filter(Assignment.day.between(start, end)).all()
        return jsonify(
            [
                {
                    "day": r.day.isoformat(),
                    "shift_code": r.shift_code,
                    "staff_id": r.staff_id,
                    "position": r.position,  # PGD | TD | None
                }
                for r in rows
            ]
        )


@app.get("/api/export_audit")
def export_audit():
    """Xuất danh sách phân ca kèm JSON metadata ra CSV để audit.

    Sử dụng ``csv.writer`` để đảm bảo trích dẫn đúng các ký tự đặc biệt
    trong cột JSON. Dữ liệu được stream từng hàng thông qua ``io.StringIO``
    nhằm tránh giữ toàn bộ nội dung trong bộ nhớ.
    """
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month

    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400

    last_day = calendar.monthrange(y, m)[1]
    start = date(y, m, 1)
    end = date(y, m, last_day)

    with SessionLocal() as s:
        rows = s.query(Assignment).filter(Assignment.day.between(start, end)).all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["day", "shift_code", "staff_id", "meta"])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for r in rows:
            # JSON chứa nhiều key, bao gồm chuỗi có dấu phẩy để kiểm tra quoting
            meta = {
                "info": f"{r.shift_code},{r.staff_id}",
                "extra": "value",
            }
            writer.writerow(
                [
                    r.day.isoformat(),
                    r.shift_code,
                    r.staff_id,
                    json.dumps(meta, ensure_ascii=False),
                ]
            )
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    headers = {"Content-Disposition": f"attachment; filename=audit-{y:04d}-{m:02d}.csv"}
    return Response(
        stream_with_context(generate()),
        content_type="text/csv; charset=utf-8",
        headers=headers,
    )


@app.get("/api/export/month.csv")
def export_month_csv_endpoint():
    """Xuất lịch phân ca dạng CSV cho một tháng."""
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month
    if m < 1 or m > 12:
        return {"error": "month must be 1..12"}, 400
    return _export_month_csv(y, m)


@app.get("/api/rules/expected")
def rule_expected():
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month
    prof = get_profile()

    first = ymd(y, m, 1)
    last = ymd(y, m, month_last_day(y, m))

    out = {}
    d = first
    # nạp holiday 1 lần
    holidays = load_holidays(SessionLocal())
    while d <= last:
        kind = day_kind(d, holidays)

        day = prof.expected_day_counts(
            kind
        )  # {"TD": {"K":..,"CA1":..,"CA2":..}, "PGD": {"K":..,"CA2":..}}
        night = prof.expected_night_counts(
            kind
        )  # {"TD": {"Đ": x}, "PGD": {"Đ": y}}  (từ NightDetail.to_engine_dict)

        td = day.get("TD", {})
        pgd = day.get("PGD", {})
        n_td = night.get("TD", {}) or {}
        n_pgd = night.get("PGD", {}) or {}

        out[d.day] = {
            "expectedTD": {
                "K": int(td.get("K", 0)),
                "CA1": int(td.get("CA1", 0)),
                "CA2": int(td.get("CA2", 0)),
                "D": int(n_td.get("Đ", 0)),  # gộp Đ (đêm @ TD)
            },
            "expectedPGD": {
                "K": int(pgd.get("K", 0)),
                "CA2": int(pgd.get("CA2", 0)),
                "D": int(n_pgd.get("Đ", 0)),  # gộp Đ (đêm @ PGD)
            },
        }
        d = d + timedelta(days=1)

    return jsonify({"ok": True, "perDayExpected": out})


@app.get("/api/schedule/validate")
def schedule_validate():
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month
    if m < 1 or m > 12:
        return jsonify({"ok": False, "error": "month must be 1..12"}), 400
    body = validate_month(y, m)
    return jsonify(body)


@app.post("/api/schedule/generate")
def gen():
    payload = request.get_json(silent=True) or {}
    from datetime import date as _date

    today = _date.today()
    year = int(payload.get("year", today.year))
    month = int(payload.get("month", today.month))
    if month < 1 or month > 12:
        return jsonify({"ok": False, "error": "month must be 1..12"}), 400

    shuffle = bool(payload.get("shuffle", False))
    seed = payload.get("seed")
    try:
        seed = int(seed) if seed is not None else None
    except Exception:
        seed = None
    save_flag = bool(payload.get("save", False))
    fill_hc = bool(payload.get("fill_hc", False))

    print("[API] generate begin", year, month, shuffle, seed, save_flag, fill_hc, flush=True)

    try:
        res = generate_schedule(
            year, month, shuffle=shuffle, seed=seed, save=save_flag, fill_hc=fill_hc
        )
        print("[API] generate end", type(res), flush=True)
        # engine may return a dict or (dict, status)
        if isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], dict):
            body, status = res
            return jsonify(body), int(status)
        elif isinstance(res, dict):
            return jsonify(res)
        else:
            return jsonify({"ok": False, "error": "Internal error: bad return type"}), 500
    except Exception as e:
        # never bubble raw HTML traceback to the frontend
        return jsonify({"ok": False, "error": f"Internal error: {e.__class__.__name__}: {e}"}), 500


# ====== Reset DB ======
@app.post("/api/admin/reset")
def admin_reset():
    """
    mode=soft: xoá Assignment (giữ Staff/Off/Fix/Holiday)
    mode=hard: xoá file sqlite và tạo lại schema
    """
    mode = (request.args.get("mode") or "soft").lower()
    if mode not in ("soft", "hard"):
        return {"error": "mode must be soft|hard"}, 400

    if mode == "hard":
        try:
            if DB_FILE and DB_FILE.exists():
                DB_FILE.unlink()
            init_db()  # tạo lại schema rỗng
            return {"ok": True, "mode": "hard"}
        except Exception as e:
            return {"error": str(e)}, 500

    # soft reset
    with SessionLocal() as s:
        try:
            s.execute(text("DELETE FROM assignment"))
            s.commit()
            return {"ok": True, "mode": "soft"}
        except Exception as e:
            s.rollback()
            return {"error": str(e)}, 500


@app.get("/api/schedule/estimate")
def api_estimate():
    today = date.today()
    y = request.args.get("year", type=int) or today.year
    m = request.args.get("month", type=int) or today.month
    return jsonify(estimate_month(y, m))


@app.post("/api/chatbot/upload")
def api_chatbot_upload():
    """Proxy endpoint to forward file uploads to the webhook"""
    import requests

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    try:
        # Forward the file to the webhook
        files = {'file': (file.filename, file.stream, file.content_type)}

        # Include any additional form data
        data = {}
        for key in request.form:
            data[key] = request.form[key]

        webhook_url = os.getenv("WEBHOOK_UPLOAD_URL", "https://iconic-host.lapage.vn/webhook/upload-file")
        response = requests.post(webhook_url, files=files, data=data, timeout=30)

        return jsonify({
            "status": response.status_code,
            "response": response.text
        }), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/chatbot/chunking")
def api_chatbot_chunking():
    """Proxy endpoint to forward chunking request to the webhook"""
    import requests

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        webhook_url = os.getenv("WEBHOOK_CHUNKING_URL", "https://iconic-host.lapage.vn/webhook/chunking")
        response = requests.post(webhook_url, json=data, timeout=30)

        return jsonify({
            "status": response.status_code,
            "response": response.json() if response.headers.get('content-type') == 'application/json' else response.text
        }), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host=APP_HOST, port=APP_PORT, debug=APP_DEBUG)
