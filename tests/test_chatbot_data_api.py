from __future__ import annotations

from http import HTTPStatus

API_HEADERS = {"x-api-key": "123456"}


def _sample_payload(index: int = 0):
    return {
        "raw_text": f"Sample text {index}",
        "title": f"Rate {index}",
        "major_section": "pricing",
        "full_section_id": f"section-{index}",
        "shipmentDirection": "import",
        "containerType": "GP",
        "containerSize": "40HQ",
        "unit": "container",
        "price": 123.45 + index,
        "status": "active",
        "MAILY": "yes",
    }


def test_chatbot_data_crud(client):
    resp = client.client.post("/api/chatbot-data", json=_sample_payload(1), headers=API_HEADERS)
    assert resp.status_code == HTTPStatus.CREATED
    created = resp.get_json()
    record_id = created["id"]
    assert created["title"] == "Rate 1"

    list_resp = client.client.get("/api/chatbot-data?page=1&page_size=1", headers=API_HEADERS)
    assert list_resp.status_code == HTTPStatus.OK
    listing = list_resp.get_json()
    assert listing["total"] == 1
    assert len(listing["items"]) == 1
    assert listing["items"][0]["id"] == record_id

    update_resp = client.client.put(
        f"/api/chatbot-data/{record_id}",
        json={"status": "archived", "price": 222.5},
        headers=API_HEADERS,
    )
    assert update_resp.status_code == HTTPStatus.OK
    updated = update_resp.get_json()
    assert updated["status"] == "archived"
    assert updated["price"] == 222.5

    get_resp = client.client.get(f"/api/chatbot-data/{record_id}", headers=API_HEADERS)
    assert get_resp.status_code == HTTPStatus.OK
    fetched = get_resp.get_json()
    assert fetched["status"] == "archived"

    delete_resp = client.client.delete(f"/api/chatbot-data/{record_id}", headers=API_HEADERS)
    assert delete_resp.status_code == HTTPStatus.OK
    assert delete_resp.get_json()["ok"] is True

    missing = client.client.get(f"/api/chatbot-data/{record_id}", headers=API_HEADERS)
    assert missing.status_code == HTTPStatus.NOT_FOUND


def test_chatbot_data_invalid_pagination(client):
    resp = client.client.get("/api/chatbot-data?page=0", headers=API_HEADERS)
    assert resp.status_code == HTTPStatus.BAD_REQUEST
