"""ShiftPlanDefaults model."""

from sqlalchemy import Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class ShiftPlanDefaults(Base):
    __tablename__ = "shift_plan_defaults"
    __table_args__ = (
        UniqueConstraint(
            "year",
            "month",
            name="uq_shift_plan_defaults_year_month",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day_shifts: Mapped[int] = mapped_column(Integer, nullable=False)
    night_shifts: Mapped[int] = mapped_column(Integer, nullable=False)
    leader_shifts: Mapped[int] = mapped_column(Integer, nullable=False)
    pgd_shifts: Mapped[int] = mapped_column(Integer, nullable=False)

    __all__ = ["ShiftPlanDefaults"]
