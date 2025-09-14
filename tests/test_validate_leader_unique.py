import importlib
from datetime import date

import pytest

from rules.types import ShiftCode
from scheduler.engine.utils_rank import FairnessWindow


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


def test_validate_leader_duplicate(fresh_db):
    models, validate = fresh_db
    d = date(2025, 9, 1)
    with models.SessionLocal() as s:
        s.add_all(
            [
                models.Staff(id=1, full_name="TC1", role="TC"),
                models.Staff(id=2, full_name="TC2", role="TC"),
                models.Staff(id=3, full_name="TC3", role="TC"),
            ]
        )
        s.add(models.Assignment(staff_id=1, day=d, shift_code="K", position="TD"))
        s.add(models.Assignment(staff_id=2, day=d, shift_code="Đ", position="TD"))
        s.commit()

    res = validate.validate_month(2025, 9)
    assert res["conflicts"]["leader_day_dup"] == []
    assert res["conflicts"]["leader_night_dup"] == []

    with models.SessionLocal() as s:
        s.add(models.Assignment(staff_id=3, day=d, shift_code="K", position="TD"))
        s.commit()

    res = validate.validate_month(2025, 9)
    dup = res["conflicts"]["leader_day_dup"]
    assert len(dup) == 1
    assert dup[0]["day"] == d.isoformat()
    assert set(dup[0]["ids"]) == {1, 3}


def test_engine_guard_day_logs_dup(fresh_db, capsys, monkeypatch):
    models, _ = fresh_db
    with models.SessionLocal() as s:
        for i in range(1, 3):
            s.add(
                models.Staff(id=i, full_name=f"TC{i}", role="TC", can_night=True, base_quota=26.0)
            )
        s.commit()
    from scheduler.engine.core import build_context, close_context
    from scheduler.engine.phase_day import run_phase_day

    ctx, first, _ = build_context(year=2025, month=9, shuffle=False, seed=1, save=False)
    d = first
    leader1 = ctx.TC[0].id
    ctx.do_place(d, leader1, "K", "TD")
    ctx.q_tc_day.rotate(-1)

    orig_day_detail = ctx.profile.day_detail

    def fake_day_detail(kind):
        detail = orig_day_detail(kind)
        detail.TD[ShiftCode.K] = 2
        return detail

    monkeypatch.setattr(ctx.profile, "day_detail", fake_day_detail)
    fair = FairnessWindow(rank_map={})
    run_phase_day(ctx, d, d, fair)
    out = capsys.readouterr().out
    assert f"LEADER_DUP {d.isoformat()}" in out
    ids = [
        p.staff_id
        for p in ctx._planned
        if p.day == d and p.shift_code == "K" and p.position == "TD"
    ]
    assert ids == [leader1]
    close_context(ctx)
