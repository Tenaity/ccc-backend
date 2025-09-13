import os
import importlib
from datetime import date

import pytest


def setup_module(module):
    pass

@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")
    import models
    importlib.reload(models)
    models.init_db()
    import scheduler.validate as validate
    importlib.reload(validate)
    return models, validate


def test_offday_vs_fixed_conflict(fresh_db):
    models, validate = fresh_db
    with models.SessionLocal() as s:
        s.add(models.Staff(id=1, full_name="A"))
        s.add(models.FixedAssignment(staff_id=1, day=date(2025, 9, 4), shift_code="CA1", position="TD"))
        s.add(models.OffDay(staff_id=1, day=date(2025, 9, 4)))
        s.commit()
    res = validate.validate_month(2025, 9)
    assert not res["ok"]
    assert res["conflicts"].get("offday_vs_fixed")


def test_double_fixed_conflict(fresh_db):
    models, validate = fresh_db
    with models.SessionLocal() as s:
        s.add(models.Staff(id=1, full_name="A"))
        s.add(models.FixedAssignment(staff_id=1, day=date(2025, 9, 5), shift_code="CA1", position="TD"))
        s.add(models.FixedAssignment(staff_id=1, day=date(2025, 9, 5), shift_code="K", position="PGD"))
        s.commit()
    res = validate.validate_month(2025, 9)
    assert res["conflicts"].get("double_fixed")


def test_over_capacity_conflict(fresh_db):
    models, validate = fresh_db
    day = date(2025, 9, 1)  # weekday: PGD K expected 1
    with models.SessionLocal() as s:
        for i in range(1, 4):
            s.add(models.Staff(id=i, full_name=f"S{i}"))
            s.add(models.FixedAssignment(staff_id=i, day=day, shift_code="K", position="PGD"))
        s.commit()
    res = validate.validate_month(2025, 9)
    conflict = res["conflicts"].get("over_capacity")
    assert conflict and conflict[0]["position"] == "PGD"
    assert conflict[0]["shift_code"] == "K"
    assert conflict[0]["fixed"] == 3
    assert conflict[0]["expected"] < 3


def test_unfulfilled_fixed_conflict(fresh_db):
    models, validate = fresh_db
    day = date(2025, 9, 2)
    with models.SessionLocal() as s:
        s.add(models.Staff(id=1, full_name="A"))
        s.add(models.FixedAssignment(staff_id=1, day=day, shift_code="CA1", position="TD"))
        s.commit()
    res = validate.validate_month(2025, 9)
    assert res["conflicts"].get("unfulfilled_fixed")
