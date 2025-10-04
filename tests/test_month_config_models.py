import importlib
import sqlite3
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError


@pytest.fixture()
def models(tmp_path, monkeypatch):
    db_path = tmp_path / "config.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")

    # Reset database engine cache to pick up new DB_URL
    from src.infrastructure.persistence import database as db_module
    db_module.reset_engine()

    import models as models_module
    importlib.reload(models_module)
    models_module.init_db()
    return models_module


def test_month_config_unique_constraint(models):
    with models.SessionLocal() as session:
        cfg = models.MonthConfig(year=2025, month=1)
        session.add(cfg)
        session.commit()

        assert cfg.extra_workdays == []
        assert cfg.extra_offdays == []
        assert cfg.weekend_policy == models.WeekendPolicy.SAT_OFF

        session.add(models.MonthConfig(year=2025, month=1))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_shift_plan_defaults_unique_constraint(models):
    with models.SessionLocal() as session:
        defaults = models.ShiftPlanDefaults(
            year=2025,
            month=1,
            day_shifts=10,
            night_shifts=5,
            leader_shifts=2,
            pgd_shifts=1,
        )
        session.add(defaults)
        session.commit()

        session.add(
            models.ShiftPlanDefaults(
                year=2025,
                month=1,
                day_shifts=8,
                night_shifts=4,
                leader_shifts=1,
                pgd_shifts=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_init_db_migrates_legacy_holidays(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE holidays (id INTEGER PRIMARY KEY, day DATE NOT NULL, name VARCHAR)"
    )
    conn.execute(
        "INSERT INTO holidays (id, day, name) VALUES (1, '2024-01-01', 'New Year')"
    )
    conn.commit()
    conn.close()

    # Reset database engine cache to pick up new DB_URL
    from src.infrastructure.persistence import database as db_module
    db_module.reset_engine()

    import models
    importlib.reload(models)
    models.init_db()

    models_module = models

    # Use get_engine() to ensure we get the correct engine for this test
    test_engine = db_module.get_engine()
    with test_engine.connect() as raw_conn:
        tables = {
            row[0]
            for row in raw_conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "holiday" in tables
        assert "holidays" not in tables

        columns = {
            row[1]
            for row in raw_conn.exec_driver_sql("PRAGMA table_info('holiday')").fetchall()
        }
        assert {"id", "date", "name", "kind", "official", "source"}.issubset(columns)

        indexes = raw_conn.exec_driver_sql("PRAGMA index_list('holiday')").fetchall()
        unique_index_names = [row[1] for row in indexes if row[2] == 1]
        assert unique_index_names, "Expected a unique index on holiday(date)"
        date_index_verified = False
        for name in unique_index_names:
            cols = raw_conn.exec_driver_sql(
                f"PRAGMA index_info('{name}')"
            ).fetchall()
            if len(cols) == 1 and cols[0][2] == "date":
                date_index_verified = True
                break
        assert date_index_verified, "holiday(date) should be unique"

    # Use get_session_factory() to ensure we get the correct session for this test
    test_session_factory = db_module.get_session_factory()
    with test_session_factory() as session:
        rows = session.query(models_module.Holiday).all()
        assert len(rows) == 1
        assert rows[0].day == date(2024, 1, 1)
        assert rows[0].name == "New Year"
        assert rows[0].official is False
