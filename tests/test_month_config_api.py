import calendar
import importlib
from datetime import date
from types import SimpleNamespace

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "month_config.db"
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


def _count_weekdays(year: int, month: int) -> int:
    _, days = calendar.monthrange(year, month)
    return sum(
        1 for day in range(1, days + 1) if date(year, month, day).weekday() < 5
    )


def test_month_config_get_defaults(client):
    app = client.client
    models = client.models

    with models.SessionLocal() as session:
        session.add(
            models.Holiday(
                day=date(2025, 10, 1),
                name="Holiday",
                official=True,
            )
        )
        session.commit()

    res = app.get("/api/month-config?year=2025&month=10")
    assert res.status_code == 200
    payload = res.get_json()

    assert payload["year"] == 2025
    assert payload["month"] == 10

    base_weekdays = _count_weekdays(2025, 10)
    assert payload["auto_working_days"] == base_weekdays - 1  # minus official holiday
    assert payload["policy_working_days"] == payload["auto_working_days"]
    assert payload["effective_working_days"] == payload["policy_working_days"]

    config = payload["config"]
    assert config["weekend_policy"] == "sat_off"
    assert config["extra_workdays"] == []
    assert config["extra_offdays"] == []
    assert config["working_days_override"] is None


def test_month_config_update_with_weekend_policy_and_extras(client):
    app = client.client
    models = client.models

    with models.SessionLocal() as session:
        session.add(
            models.Holiday(
                day=date(2025, 10, 1),
                name="Holiday",
                official=True,
            )
        )
        session.commit()

    res = app.put(
        "/api/month-config",
        json={
            "year": 2025,
            "month": 10,
            "weekend_policy": "sat_work",
            "extra_workdays": ["2025-10-12"],
            "extra_offdays": ["2025-10-18"],
        },
    )
    assert res.status_code == 200
    payload = res.get_json()

    assert payload["auto_working_days"] == _count_weekdays(2025, 10) - 1
    assert payload["policy_working_days"] == 26
    assert payload["effective_working_days"] == 26

    config = payload["config"]
    assert config["weekend_policy"] == "sat_work"
    assert config["extra_workdays"] == ["2025-10-12"]
    assert config["extra_offdays"] == ["2025-10-18"]

    # persisted state should be returned by GET as well
    res = app.get("/api/month-config?year=2025&month=10")
    fetched = res.get_json()
    assert fetched["policy_working_days"] == 26
    assert fetched["config"] == config


def test_month_config_half_day_policy_and_override(client):
    app = client.client

    res = app.put(
        "/api/month-config",
        json={
            "year": 2025,
            "month": 11,
            "weekend_policy": "sat_work_am",
        },
    )
    assert res.status_code == 200
    payload = res.get_json()

    assert payload["auto_working_days"] == _count_weekdays(2025, 11)
    assert payload["policy_working_days"] == 22.5
    assert payload["effective_working_days"] == 22.5
    assert payload["config"]["weekend_policy"] == "sat_work_am"

    res = app.put(
        "/api/month-config",
        json={
            "year": 2025,
            "month": 11,
            "working_days_override": 25,
        },
    )
    assert res.status_code == 200
    updated = res.get_json()
    assert updated["policy_working_days"] == 22.5
    assert updated["effective_working_days"] == 25
    assert updated["config"]["weekend_policy"] == "sat_work_am"
    assert updated["config"]["working_days_override"] == 25


def test_month_config_validation_errors(client):
    app = client.client

    res = app.put(
        "/api/month-config",
        json={
            "year": 2025,
            "month": 10,
            "weekend_policy": "invalid",
        },
    )
    assert res.status_code == 400
    assert "weekend_policy" in res.get_json()["error"]

    res = app.put(
        "/api/month-config",
        json={
            "year": 2025,
            "month": 10,
            "extra_workdays": ["2025-11-01"],
        },
    )
    assert res.status_code == 400
    assert "extra_workdays" in res.get_json()["error"]
