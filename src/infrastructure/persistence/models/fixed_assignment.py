"""FixedAssignment model."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class FixedAssignment(Base):
    __tablename__ = "fixed_assignment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date, nullable=False)
    shift_code: Mapped[str] = mapped_column(String, nullable=False)  # CA1 | CA2 | K | HC | Đ
    position: Mapped[str | None] = mapped_column(String, nullable=True)  # TD | PGD
    staff: Mapped["Staff"] = relationship(back_populates="fixed_assignments")

    __all__ = ["FixedAssignment"]
