"""Domain DTOs for chatbot data records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ChatbotDataDTO:
    id: str
    rawText: Optional[str]
    majorSection: Optional[str]
    fullSectionId: Optional[str]
    sourceTable: Optional[str]
    title: Optional[str]
    site: Optional[str]
    anotherPrice: Optional[str]
    shipmentDirection: Optional[str]
    containerStatus: Optional[str]
    containerType: Optional[str]
    containerSize: Optional[str]
    serviceType: Optional[str]
    operationType: Optional[str]
    location: Optional[str]
    from_: Optional[str]
    to: Optional[str]
    unit: Optional[str]
    price: Optional[float]
    priceType: Optional[str]
    basePriceRef: Optional[str]
    calculationFormula: Optional[str]
    context: Optional[str]
    scopeAndConditions: Optional[str]
    pointNote: Optional[str]
    keywords: Optional[str]
    embeddingText: Optional[str]
    year: Optional[int]
    status: Optional[str]


@dataclass
class ChatbotDataPage:
    items: List[ChatbotDataDTO]
    page: int
    page_size: int
    total: int


__all__ = ["ChatbotDataDTO", "ChatbotDataPage"]
