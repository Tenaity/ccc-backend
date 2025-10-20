"""Staff model - Employee records."""

from typing import List, Optional
from datetime import date

from sqlalchemy import Boolean, Numeric, ForeignKey, Integer, String, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class Staff(Base):
    """Employee staff member."""

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id", ondelete="CASCADE"),
        nullable=False
    )
    team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("team.id", ondelete="SET NULL"),
        nullable=True
    )
    rank_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rank.id", ondelete="SET NULL"),
        nullable=True
    )
    title_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("title.id", ondelete="SET NULL"),
        nullable=True
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    employee_code: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, nullable=True
    )
    role: Mapped[str] = mapped_column(String(50), default="GDV")  # Legacy field
    base_quota: Mapped[float] = mapped_column(Numeric(6, 2), default=26.0)
    can_night: Mapped[bool] = mapped_column(Boolean, default=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_on_leave: Mapped[bool] = mapped_column(Boolean, default=False)
    leave_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    leave_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    department: Mapped["Department"] = relationship(back_populates="staff")
    team: Mapped[Optional["Team"]] = relationship(back_populates="staff")
    rank: Mapped[Optional["Rank"]] = relationship(back_populates="staff")
    title: Mapped[Optional["Title"]] = relationship(back_populates="staff")
    preferences: Mapped[Optional["StaffPreferences"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan", uselist=False
    )
    fixed_assignments: Mapped[List["FixedAssignment"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    off_days: Mapped[List["OffDay"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["Assignment"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    quota_tracking: Mapped[List["StaffQuotaTracking"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    assignment_history: Mapped[List["AssignmentHistory"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Staff id={self.id} code={self.employee_code} name={self.full_name}>"
