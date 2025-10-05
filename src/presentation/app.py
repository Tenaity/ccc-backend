"""Flask application factory."""

from __future__ import annotations

import os
import pathlib

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from middleware.api_key import register_api_key_middleware
from models import init_db

from src.presentation.api.admin import admin_bp
from src.presentation.api.department import department_bp
from src.presentation.api.export import export_bp
from src.presentation.api.fixed_assignment import fixed_bp
from src.presentation.api.holiday import holiday_bp
from src.presentation.api.lookup import lookup_bp
from src.presentation.api.metrics import metrics_bp
from src.presentation.api.month_config import month_config_bp
from src.presentation.api.offday import offday_bp, create_off_day, delete_off_day, list_off_days
from src.presentation.api.reports import reports_bp
from src.presentation.api.schedule import schedule_bp
from src.presentation.api.shift_config import shift_config_bp
from src.presentation.api.shift_defaults import shift_defaults_bp
from src.presentation.api.staff import staff_bp

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
frontend_override = os.getenv("FRONTEND_DIST")
if frontend_override:
    frontend_path = pathlib.Path(frontend_override).expanduser()
else:
    frontend_path = DEFAULT_FRONTEND_DIST
frontend_static = str(frontend_path.resolve()) if frontend_path.exists() else None

load_dotenv()


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=frontend_static,
        static_url_path="/",
    )
    cors_raw = os.getenv("CORS_ORIGINS", "*")
    cors_origins = [item.strip() for item in cors_raw.split(",") if item.strip()]
    CORS(app, origins=cors_origins or ["*"], supports_credentials=True)

    register_api_key_middleware(app, api_key=os.getenv("API_KEY"))

    # ensure database schema exists
    init_db()

    # Register blueprints
    app.register_blueprint(lookup_bp)
    app.register_blueprint(holiday_bp)
    app.register_blueprint(department_bp)
    app.register_blueprint(shift_config_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(fixed_bp)
    app.register_blueprint(offday_bp)
    app.register_blueprint(month_config_bp)
    app.register_blueprint(shift_defaults_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(admin_bp)

    # keep ORM helpers in sync with the active engine
    import models as _models
    from src.infrastructure.persistence import database as _database

    _models.engine = _database.get_engine()
    _models.SessionLocal = _database.get_session_factory()

    # Compatibility aliases for legacy routes
    app.add_url_rule("/api/offdays", view_func=list_off_days, methods=["GET"])
    app.add_url_rule("/api/offdays", view_func=create_off_day, methods=["POST"])
    app.add_url_rule("/api/offdays/<int:off_id>", view_func=delete_off_day, methods=["DELETE"])

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/")
    def root():
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
        if app.static_folder:
            full = os.path.join(app.static_folder, path)
            if os.path.isfile(full):
                return send_from_directory(app.static_folder, path)
            index_html = os.path.join(app.static_folder, "index.html")
            if os.path.isfile(index_html):
                return send_from_directory(app.static_folder, "index.html")
        return {"error": "Not Found"}, 404

    return app
