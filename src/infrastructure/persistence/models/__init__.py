"""SQLAlchemy models for database entities.

Clean separation of concerns - each model in its own file.
PostgreSQL-only configuration (SQLite removed).
"""

from src.infrastructure.persistence.models.base import Base
from src.infrastructure.persistence.models.department import Department
from src.infrastructure.persistence.models.shift_config import ShiftConfig
from src.infrastructure.persistence.models.staff import Staff
from src.infrastructure.persistence.models.fixed_assignment import FixedAssignment
from src.infrastructure.persistence.models.off_day import OffDay
from src.infrastructure.persistence.models.staff_preferences import StaffPreferences
from src.infrastructure.persistence.models.assignment import Assignment
from src.infrastructure.persistence.models.holiday import Holiday
from src.infrastructure.persistence.models.month_config import MonthConfig
from src.infrastructure.persistence.models.shift_plan_defaults import ShiftPlanDefaults
from src.infrastructure.persistence.models.chatbot_data import ChatbotData
from src.infrastructure.persistence.models.weekend_policy import WeekendPolicy

__all__ = [
    "Base",
    "Department",
    "ShiftConfig",
    "Staff",
    "FixedAssignment",
    "OffDay",
    "StaffPreferences",
    "Assignment",
    "Holiday",
    "MonthConfig",
    "ShiftPlanDefaults",
    "ChatbotData",
    "WeekendPolicy",
]
