"""HTTP routes for schedule queries."""

from __future__ import annotations

from http import HTTPStatus
from datetime import date

from flask import Blueprint, jsonify, request

from sqlalchemy import select

from src.application.schedule_service import ScheduleService
from src.application.utils import parse_year_month
from src.domain.exceptions import NotFoundError

schedule_bp = Blueprint("schedule", __name__, url_prefix="/api")
service = ScheduleService()


@schedule_bp.get("/schedule")
def get_schedule():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST

    dept_id = request.args.get("department_id", type=int)

    try:
        payload = service.get_schedule(year=year, month=month, department_id=dept_id)
        return jsonify(payload)
    except NotFoundError as exc:
        return {"error": str(exc)}, HTTPStatus.NOT_FOUND


@schedule_bp.get("/schedule/overview")
def schedule_overview():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST

    payload = service.get_overview(year=year, month=month)
    return jsonify(payload)

@schedule_bp.get("/schedule/validate")
def schedule_validate():
    try:
        year, month = parse_year_month(
            request.args.get("year"), request.args.get("month")
        )
    except ValueError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST

    from scheduler.validate import validate_month

    body = validate_month(year, month)
    return jsonify(body)
@schedule_bp.post("/schedule/generate")
def schedule_generate():
    payload = request.get_json(silent=True) or {}
    from datetime import date as _date

    today = _date.today()
    year = int(payload.get("year", today.year))
    month = int(payload.get("month", today.month))
    if month < 1 or month > 12:
        return {"ok": False, "error": "month must be 1..12"}, HTTPStatus.BAD_REQUEST

    shuffle = bool(payload.get("shuffle", False))
    seed = payload.get("seed")
    try:
        seed = int(seed) if seed is not None else None
    except Exception:
        seed = None
    save_flag = bool(payload.get("save", False))
    fill_hc = bool(payload.get("fill_hc", False))

    from models import MonthConfig, SessionLocal, ShiftPlanDefaults
    # Import from app module to allow test monkeypatching
    import app as app_module
    generate_schedule = app_module.generate_schedule
    from src.application.month_config_service import MonthConfigService

    try:
        with SessionLocal() as session:
            month_config = session.execute(
                select(MonthConfig).where(
                    MonthConfig.year == year, MonthConfig.month == month
                )
            ).scalar_one_or_none()
            shift_defaults = session.execute(
                select(ShiftPlanDefaults).where(
                    ShiftPlanDefaults.year == year,
                    ShiftPlanDefaults.month == month,
                )
            ).scalar_one_or_none()

            missing = {}
            if month_config is None:
                missing["month_config"] = f"No month config found for {year}-{month:02d}"
            if shift_defaults is None:
                missing["shift_plan_defaults"] = (
                    f"No shift plan defaults found for {year}-{month:02d}"
                )
            if missing:
                return {"ok": False, "error": "Missing configuration", "missing": missing}, HTTPStatus.BAD_REQUEST

            config_payload = MonthConfigService().get_month_config(year=year, month=month)
            effective_working_days = float(config_payload.effective_working_days)
            shift_plan_defaults = {
                "day_shifts": shift_defaults.day_shifts,
                "night_shifts": shift_defaults.night_shifts,
                "leader_shifts": shift_defaults.leader_shifts,
                "pgd_shifts": shift_defaults.pgd_shifts,
            }
    except Exception as exc:
        return {"ok": False, "error": f"Internal error: {exc.__class__.__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR

    try:
        res = generate_schedule(
            year,
            month,
            shuffle=shuffle,
            seed=seed,
            save=save_flag,
            fill_hc=fill_hc,
            effective_working_days=effective_working_days,
            shift_plan_defaults=shift_plan_defaults,
        )
        if isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], dict):
            body, status = res
            return jsonify(body), int(status)
        if isinstance(res, dict):
            return jsonify(res)
        return {"ok": False, "error": "Internal error: bad return type"}, HTTPStatus.INTERNAL_SERVER_ERROR
    except Exception as exc:
        return {"ok": False, "error": f"Internal error: {exc.__class__.__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR


@schedule_bp.get("/schedule/estimate")
def schedule_estimate():
    from scheduler.estimator import estimate_month

    today = date.today()
    year = request.args.get("year", type=int) or today.year
    month = request.args.get("month", type=int) or today.month
    return jsonify(estimate_month(year, month))

