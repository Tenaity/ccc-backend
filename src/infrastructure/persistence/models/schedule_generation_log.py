"""Schedule Generation Log model - Track schedule generation events."""

from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ScheduleGenerationLog(Base):
    """Log entry for each schedule generation event."""

    __tablename__ = "schedule_generation_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'success', 'failed', 'partial'
    assignments_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    department: Mapped["Department"] = relationship(
        back_populates="schedule_generation_logs"
    )

    def __repr__(self) -> str:
        return f"<ScheduleGenerationLog dept={self.department_id} {self.year}-{self.month:02d} status={self.status}>"
