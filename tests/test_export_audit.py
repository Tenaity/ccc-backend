import csv
import io
import importlib
from datetime import date
import json

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


def test_export_audit_quotes_json(client):
    client_app, models = client
    with models.SessionLocal() as s:
        s.add(models.Staff(id=1, full_name="A"))
        s.add(models.Assignment(staff_id=1, day=date(2024, 1, 1), shift_code="CA1"))
        s.commit()
    res = client_app.get("/api/export_audit?year=2024&month=1")
    assert res.status_code == 200
    rows = list(csv.reader(io.StringIO(res.data.decode())))
    assert rows[0] == ["day", "shift_code", "staff_id", "meta"]
    meta = json.loads(rows[1][3])
    assert meta == {"info": "CA1,1", "extra": "value"}
