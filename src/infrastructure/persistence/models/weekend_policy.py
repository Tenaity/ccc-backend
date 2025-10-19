"""WeekendPolicy enum."""

from enum import Enum as PyEnum


class WeekendPolicy(str, PyEnum):
    SAT_OFF = "sat_off"
    SAT_WORK_AM = "sat_work_am"
    SAT_WORK = "sat_work"

    __all__ = ["WeekendPolicy"]
