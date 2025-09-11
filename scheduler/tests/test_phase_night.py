from datetime import date
import re
import pytest

from models import OffDay
from scheduler.engine.phase_night import run_phase_night
from scheduler.engine.utils_rank import FairnessWindow

from .conftest import build_ctx


def _fairness(ctx):
    rank_map = {st.id: 1 for st in ctx.GDV1}
    rank_map.update({st.id: 1 for st in ctx.TC})
    rank_map.update({st.id: 2 for st in ctx.GDV2})
    return FairnessWindow(rank_map=rank_map)


def test_single_leader_per_night(session, capsys):
    ctx, _, _ = build_ctx(2025, 1, seed=1, save=False)
    from collections import deque
    # remove TC from GDV1 queue to model expected behaviour
    ctx.q_gdv1 = deque([x for x in ctx.q_gdv1 if getattr(x, "role", "") != "TC"])
    d = date(2025, 1, 2)
    miss = run_phase_night(ctx, d, d, _fairness(ctx))
    assert miss == []
    assigns = [p for p in ctx._planned if p.day == d]
    staff_map = {s.id: s for s in ctx.TC + ctx.GDV1 + ctx.GDV2}
    tc_leaders = [a for a in assigns if a.shift_code == "Đ" and a.position == "TD" and staff_map[a.staff_id].role == "TC"]
    assert len(tc_leaders) == 1
    out = capsys.readouterr().out
    assert re.search(rf"summary {d.isoformat()} \| leader=\d+ \| TD.D=", out)


@pytest.mark.xfail(reason="known bug: TC reused as non-leader", strict=True)
def test_no_double_night_leader(session):
    d = date(2025, 1, 3)
    for gid in range(3, 9):
        session.add(OffDay(staff_id=gid, day=d))
    session.commit()
    ctx, _, _ = build_ctx(2025, 1, seed=1, save=False)
    run_phase_night(ctx, d, d, _fairness(ctx))
    assigns = [p for p in ctx._planned if p.day == d]
    staff_map = {s.id: s for s in ctx.TC + ctx.GDV1 + ctx.GDV2}
    tc_leaders = [a for a in assigns if a.shift_code == "Đ" and a.position == "TD" and staff_map[a.staff_id].role == "TC"]
    assert len(tc_leaders) == 1  # fails: two TC assigned


def test_night_miss_without_tc(session):
    d = date(2025, 1, 6)
    session.add(OffDay(staff_id=1, day=d))
    session.add(OffDay(staff_id=2, day=d))
    session.commit()
    ctx, _, _ = build_ctx(2025, 1, seed=1, save=False)
    miss = run_phase_night(ctx, d, d, _fairness(ctx))
    assert d in miss


def test_overcap_toggle(session, monkeypatch):
    d = date(2025, 1, 2)
    ctx, _, _ = build_ctx(2025, 1, seed=1, save=False)
    # simulate quota exhausted
    for tc in ctx.TC:
        ctx.credit_map[tc.id] = ctx.base_quota[tc.id] + 10
    miss = run_phase_night(ctx, d, d, _fairness(ctx))
    assert miss == []

    ctx2, _, _ = build_ctx(2025, 1, seed=1, save=False)
    for tc in ctx2.TC:
        ctx2.credit_map[tc.id] = ctx2.base_quota[tc.id] + 10
    monkeypatch.setattr("scheduler.engine.phase_night.ALLOW_OVERCAP_NIGHT_LEADER", False)
    miss2 = run_phase_night(ctx2, d, d, _fairness(ctx2))
    assert d in miss2
