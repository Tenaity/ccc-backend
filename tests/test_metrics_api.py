import csv
import importlib
from datetime import date
from io import StringIO

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LABOR_COST_PER_HOUR", "50")
    import models
    import api.metrics as metrics_module

    importlib.reload(models)
    models.init_db()
    importlib.reload(metrics_module)

    import app as app_module

    importlib.reload(app_module)
    return app_module.app.test_client(), models


@pytest.fixture()
def sample_data(client):
    app, models = client
    with models.SessionLocal() as session:
        dept_a = models.Department(
            name="Support",
            code="SUP",
            color="#fff",
            icon="Headphones",
            settings={"max_hours_per_month": 14},
        )
        dept_b = models.Department(
            name="Sales",
            code="SAL",
            color="#000",
            icon="Briefcase",
        )
        session.add_all([dept_a, dept_b])
        session.flush()

        staff_1 = models.Staff(
            full_name="Alice",
            role="TC",
            department_id=dept_a.id,
        )
        staff_2 = models.Staff(
            full_name="Bob",
            role="TC",
            department_id=dept_a.id,
        )
        staff_3 = models.Staff(
            full_name="Carol",
            role="GDV",
            department_id=dept_b.id,
        )
        session.add_all([staff_1, staff_2, staff_3])
        session.flush()

        assignments = [
            models.Assignment(
                staff_id=staff_1.id,
                day=date(2024, 9, 1),
                shift_code="CA1",
                position="TD",
            ),
            models.Assignment(
                staff_id=staff_1.id,
                day=date(2024, 9, 2),
                shift_code="Đ",
                position="TD",
            ),
            models.Assignment(
                staff_id=staff_2.id,
                day=date(2024, 9, 1),
                shift_code="K",
                position="TD",
            ),
            models.Assignment(
                staff_id=staff_3.id,
                day=date(2024, 9, 3),
                shift_code="CA2",
                position="PGD",
            ),
            models.Assignment(
                staff_id=staff_3.id,
                day=date(2024, 8, 30),
                shift_code="CA2",
                position="PGD",
            ),
        ]
        session.add_all(assignments)
        session.commit()
    return app, models


def _decode_csv(response):
    text = response.data.decode("utf-8")
    reader = csv.reader(StringIO(text))
    return list(reader)


def test_metrics_staff_workload(client, sample_data):
    app, _ = sample_data
    res = app.get("/api/metrics/staff-workload?year=2024&month=9")
    assert res.status_code == 200
    body = res.get_json()
    assert body["totals"] == {"hours": pytest.approx(38.0), "night_hours": pytest.approx(12.0)}
    assert body["by_staff"][0]["name"] == "Alice"
    assert body["by_staff"][0]["hours"] == pytest.approx(20.0)
    assert body["by_staff"][0]["night_hours"] == pytest.approx(12.0)
    assert len(body["by_staff"]) == 3


def test_metrics_staff_workload_missing_params(client, sample_data):
    app, _ = sample_data
    res = app.get("/api/metrics/staff-workload?year=2024")
    assert res.status_code == 400
    assert res.get_json()["error"]


def test_metrics_department_compare(client, sample_data):
    app, _ = sample_data
    res = app.get("/api/metrics/department-compare?year=2024&month=9")
    assert res.status_code == 200
    body = res.get_json()
    departments = {item["dept"]: item for item in body["by_department"]}
    assert departments["Support"]["staff_count"] == 2
    assert departments["Support"]["hours"] == pytest.approx(30.0)
    assert departments["Support"]["overtime_hours"] == pytest.approx(2.0)
    assert departments["Sales"]["hours"] == pytest.approx(8.0)


def test_metrics_attendance_validation(client, sample_data):
    app, _ = sample_data
    res = app.get("/api/metrics/attendance")
    assert res.status_code == 400
    res = app.get("/api/metrics/attendance?from=2024-09-05&to=bad")
    assert res.status_code == 400
    res = app.get("/api/metrics/attendance?from=2024-09-05&to=2024-09-04")
    assert res.status_code == 400
    res = app.get("/api/metrics/attendance?from=2024-09-01&to=2024-09-30")
    assert res.status_code == 200
    assert res.get_json() == {"rate": 0, "absences": [], "late": []}


def test_metrics_cost_uses_env(client, sample_data, monkeypatch):
    app, _ = sample_data
    monkeypatch.setenv("LABOR_COST_PER_HOUR", "100")
    res = app.get("/api/metrics/cost?year=2024&month=9")
    assert res.status_code == 200
    assert res.get_json()["labor_cost"] == pytest.approx(3800.0)


def test_reports_staff_workload_csv(client, sample_data):
    app, _ = sample_data
    res = app.get("/api/reports/staff-workload.csv?year=2024&month=9")
    assert res.status_code == 200
    rows = _decode_csv(res)
    assert rows[0] == ["staff_id", "name", "hours", "night_hours"]
    assert any(row[1] == "Alice" for row in rows[1:])
    assert "staff-workload-2024-09" in res.headers["Content-Disposition"]


def test_reports_department_compare_csv(client, sample_data):
    app, _ = sample_data
    res = app.get("/api/reports/department-compare.csv?year=2024&month=9")
    assert res.status_code == 200
    rows = _decode_csv(res)
    assert rows[0] == ["department", "staff_count", "hours", "overtime_hours"]
    assert len(rows) >= 2
    assert "department-compare-2024-09" in res.headers["Content-Disposition"]


def test_reports_schedule_month_csv_wrapper(client, sample_data):
    app, _ = sample_data
    res = app.get("/api/reports/schedule-month.csv?year=2024&month=9")
    assert res.status_code == 200
    rows = _decode_csv(res)
    assert rows[0] == ["Ngày", "Staff", "Role", "Rank", "Shift", "Position", "Công"]
    assert len(rows) > 1
    assert "schedule-month-2024-09" in res.headers["Content-Disposition"]
