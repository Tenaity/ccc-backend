"""Schedule Metrics model - Quality metrics for schedules."""

from datetime import datetime
from sqlalchemy import Integer, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ScheduleMetrics(Base):
    """Quality and coverage metrics for a schedule."""

    __tablename__ = "schedule_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Coverage metrics
    total_shifts_required: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_shifts_assigned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coverage_percentage: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Quality metrics
    preference_match_rate: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    avg_consecutive_days: Mapped[float | None] = mapped_column(
        Numeric(4, 2), nullable=True
    )
    quota_balance_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Constraint violations
    hard_constraint_violations: Mapped[int] = mapped_column(Integer, default=0)
    soft_constraint_violations: Mapped[int] = mapped_column(Integer, default=0)

    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    department: Mapped["Department"] = relationship(
        back_populates="schedule_metrics"
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduleMetrics dept={self.department_id} {self.year}-{self.month:02d} "
            f"coverage={self.coverage_percentage}%>"
        )
