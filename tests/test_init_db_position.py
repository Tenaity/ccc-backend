import importlib
from datetime import date


def test_init_db_adds_position_column(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")

    # Reset database engine cache to pick up new DB_URL
    from src.infrastructure.persistence import database as db_module
    db_module.reset_engine()

    # Reload database module to clear any cached state
    importlib.reload(db_module)

    import models
    importlib.reload(models)

    # Calling twice should be idempotent
    models.init_db()
    models.init_db()

    # Ensure the column exists
    with models.engine.connect() as conn:
        info = conn.exec_driver_sql("PRAGMA table_info('fixed_assignment')").fetchall()
        assert any(row[1] == "position" for row in info)

    with models.SessionLocal() as s:
        s.add(models.Staff(id=1, full_name="A"))
        s.add(
            models.FixedAssignment(
                staff_id=1,
                day=date(2025, 1, 1),
                shift_code="CA1",
                position="PGD",
            )
        )
        s.commit()
        r = s.query(models.FixedAssignment).first()
        assert r.position == "PGD"
