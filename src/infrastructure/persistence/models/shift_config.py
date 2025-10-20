"""ShiftConfig model - Shift configuration per department."""

from typing import List
from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class ShiftConfig(Base):
    """Custom shift configuration per department."""

    __tablename__ = "shift_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    start_time: Mapped[str] = mapped_column(String(50), nullable=False)
    end_time: Mapped[str] = mapped_column(String(50), nullable=False)

    color: Mapped[str] = mapped_column(String(50), default="#60a5fa")
    icon: Mapped[str] = mapped_column(String(50), default="Sun")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    is_night_shift: Mapped[bool] = mapped_column(Boolean, default=False)
    credit_value: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0)

    # Rules stored as JSON (legacy)
    rules: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {},
        server_default='{}'
    )

    # Relationships
    department: Mapped["Department"] = relationship(back_populates="shift_configs")
    rank_requirements: Mapped[List["ShiftRankRequirement"]] = relationship(
        back_populates="shift_config", cascade="all, delete-orphan"
    )
    team_requirements: Mapped[List["ShiftTeamRequirement"]] = relationship(
        back_populates="shift_config", cascade="all, delete-orphan"
    )
    shift_plan_defaults: Mapped[List["ShiftPlanDefaults"]] = relationship(
        back_populates="shift_config", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("department_id", "code", name="uq_shift_config_dept_code"),
    )

    def __repr__(self) -> str:
        return f"<ShiftConfig id={self.id} code={self.code} dept={self.department_id}>"
