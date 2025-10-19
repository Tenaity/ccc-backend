"""Assignment model."""

from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class Assignment(Base):
    __tablename__ = "assignment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    day: Mapped[date] = mapped_column(Date, nullable=False)
    shift_code: Mapped[str] = mapped_column(String, nullable=False)
    position = Column(String, nullable=True)  # 'PGD' | 'TD' | 'K_WHITE' | None
    staff: Mapped[Optional["Staff"]] = relationship()

    __all__ = ["Assignment"]
