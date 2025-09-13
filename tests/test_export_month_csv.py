import csv
import io
import importlib
from datetime import date

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")
    import models
    import app as app_module
    importlib.reload(models)
    models.init_db()
    importlib.reload(app_module)
    return app_module.app.test_client(), models


def test_export_month_csv_streams(client):
    client_app, models = client
    with models.SessionLocal() as s:
        s.add_all([
            models.Staff(id=1, full_name="Alice, Jr", role="GDV"),
            models.Staff(id=2, full_name="Bob\nSmith", role="TC"),
        ])
        s.add_all([
            models.Assignment(staff_id=1, day=date(2025, 9, 1), shift_code="CA1"),
            models.Assignment(staff_id=2, day=date(2025, 9, 2), shift_code="CA2", position="TD"),
        ])
        s.commit()
    res = client_app.get("/api/export/month.csv?year=2025&month=9")
    assert res.status_code == 200
    assert res.headers["Content-Type"] == "text/csv; charset=utf-8"
    rows = list(csv.reader(io.StringIO(res.data.decode())))
    assert rows[0] == ["day", "staff_id", "full_name", "role", "shift_code", "position"]
    assert rows[1] == ["2025-09-01", "1", "Alice, Jr", "GDV", "CA1", ""]
    assert rows[2] == ["2025-09-02", "2", "Bob\nSmith", "TC", "CA2", "TD"]
    assert len(rows) == 3
