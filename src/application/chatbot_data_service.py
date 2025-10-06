"""Application service for chatbot data records."""

from __future__ import annotations

from typing import Dict

from sqlalchemy import func, select

from src.domain.chatbot_data import ChatbotDataDTO, ChatbotDataPage
from src.domain.exceptions import NotFoundError, ValidationError
from src.infrastructure.persistence import database as persistence_db
from src.infrastructure.persistence.models import ChatbotData


def _normalise_float(value):
    """Convert price inputs to float or None."""

    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("price must be numeric") from exc


class ChatbotDataService:
    """Encapsulate CRUD operations with pagination."""

    _FIELD_MAP: Dict[str, str] = {
        "raw_text": "raw_text",
        "major_section": "major_section",
        "full_section_id": "full_section_id",
        "source_table": "source_table",
        "anotherPrice": "another_price",
        "another_price": "another_price",
        "title": "title",
        "site": "site",
        "shipmentDirection": "shipment_direction",
        "shipment_direction": "shipment_direction",
        "containerStatus": "container_status",
        "container_status": "container_status",
        "containerType": "container_type",
        "container_type": "container_type",
        "containerSize": "container_size",
        "container_size": "container_size",
        "serviceType": "service_type",
        "service_type": "service_type",
        "operationType": "operation_type",
        "operation_type": "operation_type",
        "location": "location",
        "from": "from_location",
        "from_location": "from_location",
        "to": "to_location",
        "to_location": "to_location",
        "unit": "unit",
        "price": "price",
        "price_type": "price_type",
        "base_price_ref": "base_price_ref",
        "calculation_formula": "calculation_formula",
        "context": "context",
        "scope_and_conditions": "scope_and_conditions",
        "keywords": "keywords",
        "embedding_text": "embedding_text",
        "status": "status",
        "process": "process",
        "intent": "intent",
        "cauhoi": "cauhoi",
        "MAILY": "maily",
        "maily": "maily",
    }

    _MODEL_FIELDS = set(_FIELD_MAP.values())

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def _session(self):
        factory = self._session_factory or persistence_db.get_session_factory()
        return factory()

    def list_records(self, *, page: int = 1, page_size: int = 20) -> ChatbotDataPage:
        if page < 1:
            raise ValidationError("page must be >= 1")
        if page_size < 1 or page_size > 200:
            raise ValidationError("page_size must be between 1 and 200")

        with self._session() as session:
            total = session.execute(select(func.count(ChatbotData.id))).scalar() or 0
            offset = (page - 1) * page_size
            rows = (
                session.execute(
                    select(ChatbotData)
                    .order_by(ChatbotData.title.is_(None), ChatbotData.title.asc(), ChatbotData.id.asc())
                    .offset(offset)
                    .limit(page_size)
                )
                .scalars()
                .all()
            )
            return ChatbotDataPage(
                items=[self._to_dto(row) for row in rows],
                page=page,
                page_size=page_size,
                total=int(total),
            )

    def get_record(self, record_id: str) -> ChatbotDataDTO:
        with self._session() as session:
            row = session.get(ChatbotData, record_id)
            if not row:
                raise NotFoundError("Chatbot data not found")
            return self._to_dto(row)

    def create_record(self, payload: Dict[str, object]) -> ChatbotDataDTO:
        data = self._normalise_payload(payload, for_update=False)
        if not data.get("raw_text") and not data.get("title"):
            raise ValidationError("raw_text or title is required")

        with self._session() as session:
            row = ChatbotData(**data)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_dto(row)

    def update_record(self, record_id: str, payload: Dict[str, object]) -> ChatbotDataDTO:
        updates = self._normalise_payload(payload, for_update=True)
        if not updates:
            raise ValidationError("No valid fields provided")

        with self._session() as session:
            row = session.get(ChatbotData, record_id)
            if not row:
                raise NotFoundError("Chatbot data not found")

            for key, value in updates.items():
                setattr(row, key, value)

            session.commit()
            session.refresh(row)
            return self._to_dto(row)

    def delete_record(self, record_id: str) -> None:
        with self._session() as session:
            row = session.get(ChatbotData, record_id)
            if not row:
                raise NotFoundError("Chatbot data not found")
            session.delete(row)
            session.commit()

    def _normalise_payload(self, payload: Dict[str, object], *, for_update: bool) -> Dict[str, object]:
        result: Dict[str, object] = {}
        for incoming_key, value in payload.items():
            if incoming_key == "id":
                continue
            mapped = self._FIELD_MAP.get(incoming_key)
            if not mapped or mapped not in self._MODEL_FIELDS:
                continue
            if mapped == "price":
                result[mapped] = _normalise_float(value)
            else:
                result[mapped] = value
        return result

    def _to_dto(self, row: ChatbotData) -> ChatbotDataDTO:
        return ChatbotDataDTO(
            id=row.id,
            raw_text=row.raw_text,
            major_section=row.major_section,
            full_section_id=row.full_section_id,
            source_table=row.source_table,
            another_price=row.another_price,
            title=row.title,
            site=row.site,
            shipment_direction=row.shipment_direction,
            container_status=row.container_status,
            container_type=row.container_type,
            container_size=row.container_size,
            service_type=row.service_type,
            operation_type=row.operation_type,
            location=row.location,
            from_location=row.from_location,
            to_location=row.to_location,
            unit=row.unit,
            price=row.price,
            price_type=row.price_type,
            base_price_ref=row.base_price_ref,
            calculation_formula=row.calculation_formula,
            context=row.context,
            scope_and_conditions=row.scope_and_conditions,
            keywords=row.keywords,
            embedding_text=row.embedding_text,
            status=row.status,
            process=row.process,
            intent=row.intent,
            cauhoi=row.cauhoi,
            maily=row.maily,
        )


__all__ = ["ChatbotDataService"]
