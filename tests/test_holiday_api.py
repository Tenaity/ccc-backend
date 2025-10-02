import importlib
import json
from datetime import date
from types import SimpleNamespace

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
    return SimpleNamespace(
        client=app_module.app.test_client(),
        models=models,
        module=app_module,
    )


def test_holiday_crud(client):
    app = client.client
    models = client.models

    with models.SessionLocal() as session:
        session.add(models.Holiday(day=date(2025, 1, 1), name="New Year"))
        session.commit()

    res = app.get("/api/holidays?year=2025")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 1
    assert rows[0]["name"] == "New Year"

    res = app.post(
        "/api/holidays",
        json={
            "day": "2025-01-02",
            "name": "Second",
            "kind": "company",
            "official": False,
            "source": "internal",
        },
    )
    assert res.status_code == 201
    payload = res.get_json()
    assert payload["item"]["name"] == "Second"
    assert payload["item"]["kind"] == "company"
    assert payload["item"]["source"] == "internal"
    hid = payload["item"]["id"]

    # duplicate day is idempotent
    res = app.post(
        "/api/holidays",
        json={"day": "2025-01-02", "name": "Duplicate", "official": True},
    )
    assert res.status_code == 200
    again = res.get_json()
    assert again["item"]["id"] == hid

    res = app.put(
        f"/api/holidays/{hid}",
        json={"name": "Renamed", "official": True, "kind": None},
    )
    assert res.status_code == 200
    updated = res.get_json()["item"]
    assert updated["name"] == "Renamed"
    assert updated["official"] is True
    assert updated["kind"] is None

    res = app.delete(f"/api/holidays/{hid}")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    res = app.get("/api/holidays?year=2025")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == 1  # only the seeded holiday remains


def test_create_holiday_validation(client):
    app = client.client

    res = app.post("/api/holidays", json={"name": "Missing"})
    assert res.status_code == 400
    assert res.get_json()["error"] == "day required"

    res = app.post("/api/holidays", json={"day": "bad"})
    assert res.status_code == 400
    assert res.get_json()["error"] == "day must be YYYY-MM-DD"


def test_delete_holiday_not_found(client):
    app = client.client
    res = app.delete("/api/holidays/999")
    assert res.status_code == 404
    assert res.get_json()["error"] == "Not found"


def test_update_holiday_conflict(client):
    app = client.client
    models = client.models

    with models.SessionLocal() as session:
        session.add_all(
            [
                models.Holiday(day=date(2025, 1, 1), name="One"),
                models.Holiday(day=date(2025, 1, 2), name="Two"),
            ]
        )
        session.commit()

    res = app.put("/api/holidays/1", json={"day": "2025-01-02"})
    assert res.status_code == 409
    assert res.get_json()["error"] == "day already exists"


def test_import_holidays_from_nager(client, monkeypatch):
    app = client.client
    models = client.models
    module = client.module

    incoming = [
        {
            "day": date(2026, 1, 1),
            "name": "Tết Dương lịch",
            "kind": "Public",
            "official": True,
            "source": "nager",
        },
        {
            "day": date(2026, 4, 30),
            "name": "Ngày Giải phóng",
            "kind": "Public",
            "official": True,
            "source": "nager",
        },
    ]

    monkeypatch.setattr(module, "_fetch_nager_holidays", lambda year: incoming)

    res = app.post("/api/holidays/import?year=2026&source=nager")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["inserted"] == 2
    assert payload["updated"] == 0
    assert len(payload["items"]) == 2

    # import again should update existing rows only
    res = app.post("/api/holidays/import?year=2026&source=nager")
    assert res.status_code == 200
    again = res.get_json()
    assert again["inserted"] == 0
    assert again["updated"] == 2

    # manual holiday remains after import
    with models.SessionLocal() as session:
        session.add(models.Holiday(day=date(2026, 5, 1), name="Company Off", source="internal"))
        session.commit()

    res = app.get("/api/holidays?year=2026")
    rows = res.get_json()
    assert len(rows) == 3


def test_import_year_holidays_matches_count(client, monkeypatch):
    app = client.client
    module = client.module

    incoming = [
        {
            "day": date(2027, 1, 1),
            "name": "New Year",
            "kind": "Public",
            "official": True,
            "source": "nager",
        },
        {
            "day": date(2027, 4, 30),
            "name": "Liberation Day",
            "kind": "Public",
            "official": True,
            "source": "nager",
        },
        {
            "day": date(2027, 5, 1),
            "name": "Labour Day",
            "kind": "Public",
            "official": True,
            "source": "nager",
        },
    ]

    monkeypatch.setattr(module, "_fetch_nager_holidays", lambda year: incoming)

    res = app.post("/api/holidays/import?year=2027&source=nager")
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["inserted"] == len(incoming)

    res = app.get("/api/holidays?year=2027")
    assert res.status_code == 200
    rows = res.get_json()
    assert len(rows) == len(incoming)
    assert {row["day"] for row in rows} == {item["day"].isoformat() for item in incoming}


def test_fetch_nager_holidays(monkeypatch):
    import app as app_module

    sample = [
        {
            "date": "2026-01-01",
            "localName": "Tết Dương lịch",
            "types": ["Public"],
            "global": True,
        }
    ]

    payload = json.dumps(sample).encode()

    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return payload

        def getcode(self):
            return 200

    monkeypatch.setattr(
        app_module.urllib.request,
        "urlopen",
        lambda url, timeout=15: DummyResponse(),
    )

    result = app_module._fetch_nager_holidays(2026)
    assert result[0]["day"].isoformat() == "2026-01-01"
    assert result[0]["name"] == "Tết Dương lịch"
    assert result[0]["official"] is True
