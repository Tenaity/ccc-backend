"""Holiday model."""

from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from src.infrastructure.persistence.models.base import Base


class Holiday(Base):
    __tablename__ = "holiday"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(
        "date", Date, unique=True, nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    official: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=expression.false(),
    )
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    __all__ = ["Holiday"]
