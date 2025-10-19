"""ChatbotData model - for chatbot training data."""

from typing import Optional
import uuid

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.models.base import Base


class ChatbotData(Base):
    """Structured record for chatbot data."""

    __tablename__ = "chatbot_data"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    major_section: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    full_section_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_table: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    another_price: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    site: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    shipment_direction: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    container_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    container_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    container_size: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    service_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    operation_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    from_location: Mapped[Optional[str]] = mapped_column("from", String, nullable=True)
    to_location: Mapped[Optional[str]] = mapped_column("to", String, nullable=True)

    unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    base_price_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    calculation_formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_and_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    point_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    process: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    intent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cauhoi: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    maily: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    __all__ = ["ChatbotData"]
