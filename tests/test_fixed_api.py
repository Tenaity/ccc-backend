import importlib

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")

    # Reset database engine cache to pick up new DB_URL
    from src.infrastructure.persistence import database as db_module
    db_module.reset_engine()

    import app as app_module
    import models

    importlib.reload(models)
    models.init_db()
    importlib.reload(app_module)
    return app_module.app.test_client(), models


def test_fixed_crud(client):
    app, models = client
    with models.SessionLocal() as s:
        s.add(models.Staff(id=1, full_name="A"))
        s.commit()
    res = app.post(
        "/api/fixed",
        json={
            "staff_id": 1,
            "day": "2024-01-02",
            "shift_code": "CA1",
            "position": "TD",
        },
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["ok"] is True
    fid = body["item"]["id"]

    res = app.get("/api/fixed?year=2024&month=1")
    assert res.status_code == 200
    items = res.get_json()
    assert items[0]["shift_code"] == "CA1"

    res = app.put(f"/api/fixed/{fid}", json={"shift_code": "CA2"})
    assert res.status_code == 200
    assert res.get_json()["item"]["shift_code"] == "CA2"

    res = app.delete(f"/api/fixed/{fid}")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True
