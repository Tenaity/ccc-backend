from datetime import date
import re

from scheduler.engine.phase_day import run_phase_day
from scheduler.engine.utils_rank import FairnessWindow

from .conftest import build_ctx


def _fairness(ctx):
    rank_map = {st.id: 1 for st in ctx.GDV1}
    rank_map.update({st.id: 1 for st in ctx.TC})
    rank_map.update({st.id: 2 for st in ctx.GDV2})
    return FairnessWindow(rank_map=rank_map)


def _staff_map(ctx):
    return {s.id: s for s in ctx.TC + ctx.GDV1 + ctx.GDV2 + ctx.HC}


def test_day_leader_single_tc(session, capsys):
    ctx, _, _ = build_ctx(2025, 1, seed=1, save=False)
    d = date(2025, 1, 2)
    run_phase_day(ctx, d, d, _fairness(ctx))
    assigns = [p for p in ctx._planned if p.day == d]
    smap = _staff_map(ctx)
    tc_leaders = [a for a in assigns if a.shift_code == "K" and a.position == "TD" and smap[a.staff_id].role == "TC"]
    assert len(tc_leaders) == 1
    out = capsys.readouterr().out
    assert re.search(rf"summary {d.isoformat()} \| TD: K=", out)


def test_rank_and_fixed_off(session):
    ctx, _, _ = build_ctx(2025, 1, seed=1, save=False)
    d = date(2025, 1, 4)
    run_phase_day(ctx, d, d, _fairness(ctx))
    assigns = [p for p in ctx._planned if p.day == d]
    smap = _staff_map(ctx)
    assert any(a.staff_id == 3 and a.shift_code == "CA1" and a.position == "TD" for a in assigns)
    assert all(a.staff_id != 6 for a in assigns)
    td_ca2 = [a for a in assigns if a.shift_code == "CA2" and a.position == "TD"]
    ranks = {1: 0, 2: 0}
    for a in td_ca2:
        rk = getattr(smap[a.staff_id], "rank", 2)
        if smap[a.staff_id].role == "TC":
            rk = 1
        ranks[rk] += 1
    assert abs(ranks[1] - ranks[2]) <= 1
    pgd_k = [a for a in assigns if a.shift_code == "K" and a.position == "PGD"]
    ranks = {1: 0, 2: 0}
    for a in pgd_k:
        rk = getattr(smap[a.staff_id], "rank", 2)
        if smap[a.staff_id].role == "TC":
            rk = 1
        ranks[rk] += 1
    assert abs(ranks[1] - ranks[2]) <= 1
