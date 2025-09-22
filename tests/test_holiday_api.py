import importlib
from datetime import date

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "holiday.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")
    import app as app_module
    import models

    importlib.reload(models)
    models.init_db()
    importlib.reload(app_module)
    return app_module.app.test_client(), models


def test_holiday_crud(client):
    app, models = client

    with models.SessionLocal() as session:
        session.add(models.Holiday(day=date(2025, 1, 1), name="New Year"))
        session.commit()

    res = app.get("/api/holidays?year=2025&month=1")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 1
    assert rows[0]["name"] == "New Year"

    res = app.post("/api/holidays", json={"day": "2025-01-02", "name": "Second"})
    assert res.status_code == 201
    payload = res.get_json()
    assert payload["item"]["name"] == "Second"
    hid = payload["item"]["id"]

    # duplicate day is idempotent
    res = app.post("/api/holidays", json={"day": "2025-01-02", "name": "Duplicate"})
    assert res.status_code == 200
    again = res.get_json()
    assert again["item"]["id"] == hid

    res = app.delete(f"/api/holidays/{hid}")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    res = app.get("/api/holidays?year=2025&month=1")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 1  # only the seeded holiday remains


def test_create_holiday_validation(client):
    app, _ = client

    res = app.post("/api/holidays", json={"name": "Missing"})
    assert res.status_code == 400
    assert res.get_json()["error"] == "day required"

    res = app.post("/api/holidays", json={"day": "bad"})
    assert res.status_code == 400
    assert res.get_json()["error"] == "day must be YYYY-MM-DD"


def test_delete_holiday_not_found(client):
    app, _ = client
    res = app.delete("/api/holidays/999")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Not found"
