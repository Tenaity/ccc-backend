"""Department model for multi-department support."""

from typing import List

from sqlalchemy import Boolean, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class Department(Base):
    """Department model for multi-department support."""
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # Short code like "CC", "IT"
    color: Mapped[str] = mapped_column(String, default="#3b82f6")  # Hex color for UI
    icon: Mapped[str] = mapped_column(String, default="Building2")  # Lucide icon name
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Settings stored as JSON
    settings: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {
            "working_hours": {"start": "08:00", "end": "17:00"},
            "weekend_policy": "sat_off",
            "max_hours_per_month": 208,
            "min_staff_per_shift": 2,
        },
        server_default='{"working_hours": {"start": "08:00", "end": "17:00"}, "weekend_policy": "sat_off", "max_hours_per_month": 208, "min_staff_per_shift": 2}'
    )

    # Relationships
    staff: Mapped[List["Staff"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )
    shifts: Mapped[List["ShiftConfig"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )

    __all__ = ["Department"]
