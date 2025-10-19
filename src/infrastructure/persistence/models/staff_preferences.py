"""StaffPreferences model."""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class StaffPreferences(Base):
    """Staff scheduling preferences for better work-life balance."""
    __tablename__ = "staff_preferences"

    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Preferred shift codes (e.g., ["K", "CA1"] - prefer day shifts)
    preferred_shifts: Mapped[Optional[str]] = mapped_column(
        JSON,
        nullable=True,
        server_default='[]'
    )

    # Unavailable dates (e.g., ["2025-10-15", "2025-10-20"])
    unavailable_days: Mapped[Optional[str]] = mapped_column(
        JSON,
        nullable=True,
        server_default='[]'
    )

    # Maximum consecutive working days before needing a break
    max_consecutive_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=6
    )

    # Preferred days off (0=Monday, 6=Sunday) - e.g., [5, 6] for weekends
    preferred_days_off: Mapped[Optional[str]] = mapped_column(
        JSON,
        nullable=True,
        server_default='[]'
    )

    # Additional notes about preferences
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationship
    staff: Mapped["Staff"] = relationship(back_populates="preferences")

    __all__ = ["StaffPreferences"]
