"""ShiftConfig model for custom shift configuration per department."""

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.models.base import Base


class ShiftConfig(Base):
    """Custom shift configuration per department."""
    __tablename__ = "shift_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String, nullable=False)  # "Ca Sáng"
    code: Mapped[str] = mapped_column(String, nullable=False)  # "CS" (for display on matrix)
    start_time: Mapped[str] = mapped_column(String, nullable=False)  # "08:00"
    end_time: Mapped[str] = mapped_column(String, nullable=False)  # "17:00"
    color: Mapped[str] = mapped_column(String, default="#60a5fa")  # Pastel color
    icon: Mapped[str] = mapped_column(String, default="Sun")  # Lucide icon
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)  # For sorting

    # Rules stored as JSON
    rules: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {},
        server_default='{}'
    )

    # Relationship
    department: Mapped["Department"] = relationship(back_populates="shifts")

    __table_args__ = (
        ("uq_shift_config_dept_code", {"unique": True, "columns": ["department_id", "code"]}),
    )

    __all__ = ["ShiftConfig"]
