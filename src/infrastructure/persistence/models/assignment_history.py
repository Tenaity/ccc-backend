"""Assignment History model - Audit trail for assignment changes."""

from datetime import datetime, date
from sqlalchemy import Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AssignmentHistory(Base):
    """Audit trail for assignment modifications."""

    __tablename__ = "assignment_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)

    action: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'created', 'updated', 'deleted'
    old_shift_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_shift_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    changed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AssignmentHistory staff={self.staff_id} day={self.day} action={self.action}>"
