"""Team model - Organizational teams within departments."""

from typing import List
from sqlalchemy import String, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Team(Base):
    """Team/sub-group within a department."""

    __tablename__ = "team"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    department: Mapped["Department"] = relationship(back_populates="teams")
    staff: Mapped[List["Staff"]] = relationship(back_populates="team")
    shift_team_requirements: Mapped[List["ShiftTeamRequirement"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["Assignment"]] = relationship(back_populates="team")

    def __repr__(self) -> str:
        return f"<Team id={self.id} code={self.code} name={self.name}>"
