"""Domain DTOs for chatbot data records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ChatbotDataDTO:
    id: str
    raw_text: Optional[str]
    major_section: Optional[str]
    full_section_id: Optional[str]
    source_table: Optional[str]
    another_price: Optional[str]
    title: Optional[str]
    site: Optional[str]
    shipment_direction: Optional[str]
    container_status: Optional[str]
    container_type: Optional[str]
    container_size: Optional[str]
    service_type: Optional[str]
    operation_type: Optional[str]
    location: Optional[str]
    from_location: Optional[str]
    to_location: Optional[str]
    unit: Optional[str]
    price: Optional[float]
    price_type: Optional[str]
    base_price_ref: Optional[str]
    calculation_formula: Optional[str]
    context: Optional[str]
    scope_and_conditions: Optional[str]
    keywords: Optional[str]
    embedding_text: Optional[str]
    status: Optional[str]
    process: Optional[str]
    intent: Optional[str]
    cauhoi: Optional[str]
    maily: Optional[str]


@dataclass
class ChatbotDataPage:
    items: List[ChatbotDataDTO]
    page: int
    page_size: int
    total: int


__all__ = ["ChatbotDataDTO", "ChatbotDataPage"]
