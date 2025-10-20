"""Rank model - Catalog of employee ranks."""

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Rank(Base):
    """Employee rank/level catalog."""

    __tablename__ = "rank"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    level: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    staff = relationship("Staff", back_populates="rank")
    assignments = relationship("Assignment", back_populates="rank")
    shift_rank_requirements = relationship(
        "ShiftRankRequirement", back_populates="rank", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Rank id={self.id} name={self.name} level={self.level}>"
