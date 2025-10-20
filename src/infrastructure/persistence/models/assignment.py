"""Assignment model - Daily shift assignments (partitioned by year/month)."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class Assignment(Base):
    """Daily shift assignment for staff."""

    __tablename__ = "assignment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id", ondelete="CASCADE"), nullable=False
    )
    shift_config_id: Mapped[int] = mapped_column(
        ForeignKey("shift_config.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("team.id", ondelete="SET NULL"), nullable=True
    )
    rank_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rank.id", ondelete="SET NULL"), nullable=True
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)

    shift_code: Mapped[str] = mapped_column(String(50), nullable=False)
    position: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="assignments")
    department: Mapped["Department"] = relationship()
    shift_config: Mapped["ShiftConfig"] = relationship()
    team: Mapped[Optional["Team"]] = relationship()
    rank: Mapped[Optional["Rank"]] = relationship()

    def __repr__(self) -> str:
        return f"<Assignment staff={self.staff_id} day={self.day} shift={self.shift_code}>"
