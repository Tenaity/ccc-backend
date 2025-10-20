"""Title model - Catalog of employee titles/positions."""

from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Title(Base):
    """Employee title/position catalog."""

    __tablename__ = "title"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    staff = relationship("Staff", back_populates="title")

    def __repr__(self) -> str:
        return f"<Title id={self.id} code={self.code} name={self.name}>"
