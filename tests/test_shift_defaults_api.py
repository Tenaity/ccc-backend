import importlib
from types import SimpleNamespace

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "shift_defaults.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")

    # Reset database engine cache to pick up new DB_URL
    from src.infrastructure.persistence import database as db_module
    db_module.reset_engine()

    import models
    import app as app_module

    importlib.reload(models)
    models.init_db()
    importlib.reload(app_module)

    return SimpleNamespace(
        client=app_module.app.test_client(),
        models=models,
    )


def test_get_shift_defaults_returns_zero_when_absent(client):
    app = client.client

    res = app.get("/api/shift-defaults?year=2025&month=10")
    assert res.status_code == 200
    payload = res.get_json()

    assert payload == {
        "year": 2025,
        "month": 10,
        "day_shifts": 0,
        "night_shifts": 0,
        "leader_shifts": 0,
        "pgd_shifts": 0,
    }


def test_put_and_get_shift_defaults(client):
    app = client.client

    res = app.put(
        "/api/shift-defaults",
        json={
            "year": 2025,
            "month": 10,
            "day_shifts": 40,
            "night_shifts": 20,
            "leader_shifts": 8,
            "pgd_shifts": 4,
        },
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload == {
        "year": 2025,
        "month": 10,
        "day_shifts": 40,
        "night_shifts": 20,
        "leader_shifts": 8,
        "pgd_shifts": 4,
    }

    res = app.get("/api/shift-defaults?year=2025&month=10")
    assert res.status_code == 200
    fetched = res.get_json()
    assert fetched == payload


def test_shift_defaults_validation_errors(client):
    app = client.client

    res = app.put(
        "/api/shift-defaults",
        json={
            "year": 2025,
            "month": 10,
            "day_shifts": 10,
            "night_shifts": 5,
            "leader_shifts": 2,
        },
    )
    assert res.status_code == 400
    assert "Missing fields" in res.get_json()["error"]

    res = app.put(
        "/api/shift-defaults",
        json={
            "year": 2025,
            "month": 10,
            "day_shifts": 10,
            "night_shifts": -1,
            "leader_shifts": 2,
            "pgd_shifts": 1,
        },
    )
    assert res.status_code == 400
    assert "night_shifts" in res.get_json()["error"]

    res = app.put(
        "/api/shift-defaults",
        json={
            "year": 2025,
            "month": 10,
            "day_shifts": 10,
            "night_shifts": "5",
            "leader_shifts": 2,
            "pgd_shifts": 1,
        },
    )
    assert res.status_code == 400
    assert "night_shifts" in res.get_json()["error"]

    res = app.get("/api/shift-defaults?year=2025&month=13")
    assert res.status_code == 400
    assert "month" in res.get_json()["error"]
