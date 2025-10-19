"""Staff model."""

from typing import List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="GDV")  # GDV | TC
    can_night: Mapped[bool] = mapped_column(Boolean, default=True)
    base_quota: Mapped[float] = mapped_column(Float, default=26.0)  # công chuẩn/tháng
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Department FK (nullable for backward compatibility)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    department: Mapped[Optional["Department"]] = relationship(back_populates="staff")
    fixed_assignments: Mapped[List["FixedAssignment"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    off_days: Mapped[List["OffDay"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    preferences: Mapped[Optional["StaffPreferences"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan", uselist=False
    )

    __all__ = ["Staff"]
