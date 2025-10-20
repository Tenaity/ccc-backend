"""Staff Quota Tracking model - Track staff quotas per month."""

from datetime import datetime
from sqlalchemy import Integer, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class StaffQuotaTracking(Base):
    """Track staff work quota progress for each month."""

    __tablename__ = "staff_quota_tracking"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    base_quota: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    current_credit: Mapped[float] = mapped_column(
        Numeric(6, 2), default=0, nullable=False
    )

    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    staff: Mapped["Staff"] = relationship(back_populates="quota_tracking")

    @property
    def remaining_quota(self) -> float:
        """Calculate remaining quota."""
        return float(self.base_quota - self.current_credit)

    def __repr__(self) -> str:
        return (
            f"<StaffQuotaTracking staff={self.staff_id} {self.year}-{self.month:02d} "
            f"base={self.base_quota} current={self.current_credit}>"
        )
