"""Shift Rank Requirement model - Define rank requirements for shifts."""

from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ShiftRankRequirement(Base):
    """Define minimum staff required by rank for a shift."""

    __tablename__ = "shift_rank_requirement"

    id: Mapped[int] = mapped_column(primary_key=True)
    shift_config_id: Mapped[int] = mapped_column(
        ForeignKey("shift_config.id", ondelete="CASCADE"), nullable=False
    )
    rank_id: Mapped[int] = mapped_column(
        ForeignKey("rank.id", ondelete="CASCADE"), nullable=False
    )
    min_staff: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    shift_config: Mapped["ShiftConfig"] = relationship(
        back_populates="rank_requirements"
    )
    rank: Mapped["Rank"] = relationship(back_populates="shift_rank_requirements")

    def __repr__(self) -> str:
        return f"<ShiftRankRequirement shift={self.shift_config_id} rank={self.rank_id} min={self.min_staff}>"
