"""Shift Team Requirement model - Define team requirements for shifts."""

from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ShiftTeamRequirement(Base):
    """Define minimum staff required by team for a shift."""

    __tablename__ = "shift_team_requirement"

    id: Mapped[int] = mapped_column(primary_key=True)
    shift_config_id: Mapped[int] = mapped_column(
        ForeignKey("shift_config.id", ondelete="CASCADE"), nullable=False
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("team.id", ondelete="CASCADE"), nullable=False
    )
    min_staff: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    shift_config: Mapped["ShiftConfig"] = relationship(
        back_populates="team_requirements"
    )
    team: Mapped["Team"] = relationship(back_populates="shift_team_requirements")

    def __repr__(self) -> str:
        return f"<ShiftTeamRequirement shift={self.shift_config_id} team={self.team_id} min={self.min_staff}>"
