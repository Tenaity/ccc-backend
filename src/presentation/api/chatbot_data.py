"""Chatbot data HTTP routes."""

from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.chatbot_data_service import ChatbotDataService
from src.domain.exceptions import NotFoundError, ValidationError


chatbot_data_bp = Blueprint("chatbot_data", __name__, url_prefix="/api/chatbot-data")
service = ChatbotDataService()

_FIELD_SERIALIZATION = {
    "id": "id",
    "raw_text": "raw_text",
    "major_section": "major_section",
    "full_section_id": "full_section_id",
    "source_table": "source_table",
    "another_price": "anotherPrice",
    "title": "title",
    "site": "site",
    "shipment_direction": "shipmentDirection",
    "container_status": "containerStatus",
    "container_type": "containerType",
    "container_size": "containerSize",
    "service_type": "serviceType",
    "operation_type": "operationType",
    "location": "location",
    "from_location": "from",
    "to_location": "to",
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
    "maily": "MAILY",
}


def _serialize(dto):
    return {api_key: getattr(dto, attr) for attr, api_key in _FIELD_SERIALIZATION.items()}


def _parse_pagination(args):
    def _parse(name, default):
        raw = args.get(name, default)
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{name} must be an integer") from exc

    return _parse("page", 1), _parse("page_size", 20)


@chatbot_data_bp.get("")
def list_records():
    try:
        page, page_size = _parse_pagination(request.args)
        page_data = service.list_records(page=page, page_size=page_size)
        return (
            jsonify(
                {
                    "items": [_serialize(item) for item in page_data.items],
                    "page": page_data.page,
                    "page_size": page_data.page_size,
                    "total": page_data.total,
                }
            ),
            HTTPStatus.OK,
        )
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@chatbot_data_bp.get("/<string:record_id>")
def get_record(record_id: str):
    try:
        dto = service.get_record(record_id)
        return jsonify(_serialize(dto))
    except NotFoundError:
        return {"error": "Chatbot data not found"}, HTTPStatus.NOT_FOUND


@chatbot_data_bp.post("")
def create_record():
    payload = request.get_json(silent=True) or {}
    try:
        dto = service.create_record(payload)
        return jsonify(_serialize(dto)), HTTPStatus.CREATED
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@chatbot_data_bp.put("/<string:record_id>")
def update_record(record_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        dto = service.update_record(record_id, payload)
        return jsonify(_serialize(dto))
    except ValidationError as exc:
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except NotFoundError:
        return {"error": "Chatbot data not found"}, HTTPStatus.NOT_FOUND


@chatbot_data_bp.delete("/<string:record_id>")
def delete_record(record_id: str):
    try:
        service.delete_record(record_id)
        return {"ok": True}
    except NotFoundError:
        return {"error": "Chatbot data not found"}, HTTPStatus.NOT_FOUND


__all__ = ["chatbot_data_bp"]
