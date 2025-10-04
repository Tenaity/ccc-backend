from __future__ import annotations

from flask import Flask

from .admin import bp as admin_bp
from .assignments import bp as assignments_bp
from .chatbot import bp as chatbot_bp
from .departments import bp as departments_bp
from .fixed_assignments import bp as fixed_assignments_bp
from .holidays import bp as holidays_bp
from .metrics_routes import bp as metrics_bp
from .month_config import bp as month_config_bp
from .off_days import bp as off_days_bp
from .root import bp as root_bp
from .schedule import bp as schedule_bp
from .shift_configs import bp as shift_configs_bp
from .shift_defaults import bp as shift_defaults_bp
from .staff import bp as staff_bp


def register_routes(app: Flask) -> None:
    """Register all API blueprints on the provided Flask app."""

    for blueprint in (
        departments_bp,
        shift_configs_bp,
        staff_bp,
        fixed_assignments_bp,
        off_days_bp,
        holidays_bp,
        shift_defaults_bp,
        month_config_bp,
        assignments_bp,
        metrics_bp,
        schedule_bp,
        admin_bp,
        chatbot_bp,
        root_bp,
    ):
        app.register_blueprint(blueprint)
