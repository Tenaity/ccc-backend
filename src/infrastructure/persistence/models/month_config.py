"""MonthConfig model."""

from typing import List

from sqlalchemy import JSON, Enum as SAEnum, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base
from src.infrastructure.persistence.models.weekend_policy import WeekendPolicy


class MonthConfig(Base):
    __tablename__ = "month_config"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_month_config_year_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    working_days_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekend_policy: Mapped[WeekendPolicy] = mapped_column(
        SAEnum(
            WeekendPolicy,
            name="weekend_policy",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=WeekendPolicy.SAT_OFF,
        server_default=WeekendPolicy.SAT_OFF.value,
    )
    extra_workdays: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    extra_offdays: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )

    __all__ = ["MonthConfig"]
