import importlib
from types import SimpleNamespace

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "generate.db"
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
        module=app_module,
    )


def test_generate_requires_month_and_shift_config(client, monkeypatch):
    app = client.client
    module = client.module

    def fail(*args, **kwargs):  # pragma: no cover - defensive guard
        raise AssertionError("engine should not be invoked when config missing")

    monkeypatch.setattr(module, "generate_schedule", fail)

    res = app.post("/api/schedule/generate", json={"year": 2025, "month": 5})
    assert res.status_code == 400
    payload = res.get_json()
    assert payload["error"] == "Missing configuration"
    assert "month_config" in payload["missing"]
    assert "shift_plan_defaults" in payload["missing"]



def test_generate_requires_shift_defaults_only(client):
    app = client.client
    models = client.models

    with models.SessionLocal() as session:
        session.add(models.MonthConfig(year=2025, month=5))
        session.commit()

    res = app.post("/api/schedule/generate", json={"year": 2025, "month": 5})
    assert res.status_code == 400
    payload = res.get_json()
    assert "shift_plan_defaults" in payload["missing"]
    assert "month_config" not in payload["missing"]



def test_generate_passes_config_to_engine(client, monkeypatch):
    app = client.client
    models = client.models
    module = client.module

    with models.SessionLocal() as session:
        session.add(
            models.MonthConfig(
                year=2025,
                month=6,
                weekend_policy=models.WeekendPolicy.SAT_WORK_AM,
                extra_workdays=["2025-06-22"],
                extra_offdays=["2025-06-29"],
            )
        )
        session.add(
            models.ShiftPlanDefaults(
                year=2025,
                month=6,
                day_shifts=40,
                night_shifts=20,
                leader_shifts=10,
                pgd_shifts=5,
            )
        )
        session.commit()

    with models.SessionLocal() as session:
        config_payload = module._build_month_config_payload(session, 2025, 6)
    expected_working_days = float(config_payload["effective_working_days"])

    captured = {}

    def fake_schedule(year, month, **kwargs):
        captured["args"] = (year, month)
        captured["kwargs"] = kwargs
        return {"ok": True, "planned": []}

    monkeypatch.setattr(module, "generate_schedule", fake_schedule)

    res = app.post(
        "/api/schedule/generate",
        json={"year": 2025, "month": 6, "shuffle": True, "seed": 123},
    )
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    assert captured["args"] == (2025, 6)
    kwargs = captured["kwargs"]
    assert kwargs["shuffle"] is True
    assert kwargs["seed"] == 123
    assert kwargs["save"] is False
    assert kwargs["fill_hc"] is False

    expected_defaults = {
        "day_shifts": 40,
        "night_shifts": 20,
        "leader_shifts": 10,
        "pgd_shifts": 5,
    }
    assert kwargs["shift_plan_defaults"] == expected_defaults
    assert kwargs["effective_working_days"] == pytest.approx(expected_working_days)
