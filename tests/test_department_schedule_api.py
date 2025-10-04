from __future__ import annotations

import importlib
from datetime import date

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")

    # Reset database engine cache to pick up new DB_URL
    from src.infrastructure.persistence import database as db_module
    db_module.reset_engine()

    import models

    importlib.reload(models)
    models.init_db()

    import app as app_module

    importlib.reload(app_module)
    return app_module.app.test_client(), models


@pytest.fixture()
def seeded(client):
    app, models = client
    with models.SessionLocal() as session:
        dept_active = models.Department(
            name="Support",
            code="SUP",
            color="#123456",
            icon="Headphones",
            settings={"min_staff_per_shift": 3},
            is_active=True,
        )
        dept_inactive = models.Department(
            name="Legacy",
            code="LEG",
            color="#654321",
            icon="Archive",
            is_active=False,
        )
        session.add_all([dept_active, dept_inactive])
        session.flush()

        alice = models.Staff(
            full_name="Alice Leader",
            role="TC",
            department_id=dept_active.id,
        )
        bob = models.Staff(
            full_name="Bob Worker",
            role="GDV",
            department_id=dept_active.id,
        )
        claire = models.Staff(
            full_name="Claire Support",
            role="GDV",
            department_id=dept_active.id,
        )
        ian = models.Staff(
            full_name="Ian Inactive",
            role="TC",
            department_id=dept_inactive.id,
        )
        session.add_all([alice, bob, claire, ian])
        session.flush()

        assignments = [
            models.Assignment(
                staff_id=alice.id,
                day=date(2024, 9, 1),
                shift_code="K",
                position="TD",
            ),
            models.Assignment(
                staff_id=bob.id,
                day=date(2024, 9, 1),
                shift_code="CA1",
            ),
            models.Assignment(
                staff_id=alice.id,
                day=date(2024, 9, 2),
                shift_code="Đ",
                position="TD",
            ),
            models.Assignment(
                staff_id=bob.id,
                day=date(2024, 9, 3),
                shift_code="Đ",
            ),
            models.Assignment(
                staff_id=claire.id,
                day=date(2024, 9, 4),
                shift_code="K",
            ),
            models.Assignment(
                staff_id=ian.id,
                day=date(2024, 9, 1),
                shift_code="K",
                position="TD",
            ),
        ]
        session.add_all(assignments)
        session.commit()

    return app, models, {
        "active_dept": dept_active.id,
        "inactive_dept": dept_inactive.id,
    }


def test_list_departments_active_filter(seeded):
    app, _models, meta = seeded

    res = app.get("/api/departments?active=1")
    assert res.status_code == 200
    body = res.get_json()
    assert len(body) == 1
    assert body[0]["id"] == meta["active_dept"]
    assert set(body[0].keys()) == {"id", "name", "code", "color", "icon", "settings"}

    res = app.get("/api/departments?active=maybe")
    assert res.status_code == 400


def test_staff_filters_by_department_role_and_query(seeded):
    app, _models, meta = seeded

    res = app.get(
        f"/api/staff?department_id={meta['active_dept']}&role=tc&q=alice"
    )
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) == 1
    assert data[0]["full_name"] == "Alice Leader"
    assert data[0]["role"] == "TC"

    res = app.get(f"/api/staff?department_id={meta['active_dept']}&role=gdv")
    assert res.status_code == 200
    names = [row["full_name"] for row in res.get_json()]
    assert names == sorted(names)
    assert names == ["Bob Worker", "Claire Support"]

    res = app.get("/api/staff?q=ian")
    assert res.status_code == 200
    assert [row["full_name"] for row in res.get_json()] == ["Ian Inactive"]


def test_get_schedule_filters_and_counts(seeded):
    app, _models, meta = seeded

    res = app.get(
        f"/api/schedule?year=2024&month=9&department_id={meta['active_dept']}"
    )
    assert res.status_code == 200
    payload = res.get_json()

    items = payload["items"]
    assert all(item["department_id"] == meta["active_dept"] for item in items)
    assert {item["staff_name"] for item in items} == {
        "Alice Leader",
        "Bob Worker",
        "Claire Support",
    }

    counts = payload["counts"]
    assert counts["total"] == 5
    assert counts["by_shift"] == {"K": 2, "CA1": 1, "Đ": 2}
    assert counts["leaders"] == {"day": 1, "night": 1}


def test_schedule_rejects_inactive_department(seeded):
    app, _models, meta = seeded

    res = app.get(
        f"/api/schedule?year=2024&month=9&department_id={meta['inactive_dept']}"
    )
    assert res.status_code == 404


def test_schedule_overview(seeded):
    app, _models, meta = seeded

    res = app.get("/api/schedule/overview?year=2024&month=9")
    assert res.status_code == 200
    body = res.get_json()

    assert len(body) == 1
    row = body[0]
    assert row["department_id"] == meta["active_dept"]
    assert row["shifts"] == 5
    assert row["missing_leaders"] == 2
    assert row["coverage_rate"] == pytest.approx(4 / 30, abs=1e-4)
