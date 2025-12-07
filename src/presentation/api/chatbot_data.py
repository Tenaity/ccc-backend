"""Chatbot data HTTP routes."""

from __future__ import annotations

import logging
from http import HTTPStatus

from flask import Blueprint, jsonify, request

from src.application.chatbot_data_service import ChatbotDataService
from src.domain.exceptions import NotFoundError, ValidationError


logger = logging.getLogger(__name__)

chatbot_data_bp = Blueprint("chatbot_data", __name__, url_prefix="/api/chatbot-data")
service = ChatbotDataService()

_FIELD_SERIALIZATION = {
    "id": "id",
    "rawText": "rawText",
    "majorSection": "majorSection",
    "fullSectionId": "fullSectionId",
    "sourceTable": "sourceTable",
    "title": "title",
    "site": "site",
    "anotherPrice": "anotherPrice",
    "shipmentDirection": "shipmentDirection",
    "containerStatus": "containerStatus",
    "containerType": "containerType",
    "containerSize": "containerSize",
    "serviceType": "serviceType",
    "operationType": "operationType",
    "location": "location",
    "from_": "from",
    "to": "to",
    "unit": "unit",
    "price": "price",
    "priceType": "priceType",
    "basePriceRef": "basePriceRef",
    "calculationFormula": "calculationFormula",
    "context": "context",
    "scopeAndConditions": "scopeAndConditions",
    "pointNote": "pointNote",
    "keywords": "keywords",
    "embeddingText": "embeddingText",
    "year": "year",
    "status": "status",
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
        logger.info(
            "Fetched chatbot data list: page=%s page_size=%s returned=%s total=%s",
            page,
            page_size,
            len(page_data.items),
            page_data.total,
        )
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
        logger.warning("Invalid chatbot data pagination params: %s", exc)
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@chatbot_data_bp.get("/<string:record_id>")
def get_record(record_id: str):
    try:
        dto = service.get_record(record_id)
        logger.info("Fetched chatbot data record id=%s", record_id)
        return jsonify(_serialize(dto))
    except NotFoundError:
        logger.warning("Chatbot data record id=%s not found", record_id)
        return {"error": "Chatbot data not found"}, HTTPStatus.NOT_FOUND


@chatbot_data_bp.post("")
def create_record():
    payload = request.get_json(silent=True) or {}
    try:
        dto = service.create_record(payload)
        logger.info("Created chatbot data record id=%s", dto.id)
        return jsonify(_serialize(dto)), HTTPStatus.CREATED
    except ValidationError as exc:
        logger.warning("Invalid chatbot data create payload: %s", exc)
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST


@chatbot_data_bp.put("/<string:record_id>")
def update_record(record_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        dto = service.update_record(record_id, payload)
        logger.info("Updated chatbot data record id=%s", record_id)
        return jsonify(_serialize(dto))
    except ValidationError as exc:
        logger.warning("Invalid chatbot data update payload for id=%s: %s", record_id, exc)
        return {"error": str(exc)}, HTTPStatus.BAD_REQUEST
    except NotFoundError:
        logger.warning("Chatbot data record id=%s not found for update", record_id)
        return {"error": "Chatbot data not found"}, HTTPStatus.NOT_FOUND


@chatbot_data_bp.delete("/<string:record_id>")
def delete_record(record_id: str):
    try:
        service.delete_record(record_id)
        logger.info("Deleted chatbot data record id=%s", record_id)
        return {"ok": True}
    except NotFoundError:
        logger.warning("Chatbot data record id=%s not found for delete", record_id)
        return {"error": "Chatbot data not found"}, HTTPStatus.NOT_FOUND


__all__ = ["chatbot_data_bp"]
