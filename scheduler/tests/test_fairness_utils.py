from datetime import date, timedelta
from types import SimpleNamespace

from scheduler.engine.utils_rank import ChoiceCtx, FairnessWindow, budget_for_day, fill_ranked_slots


class DummyStaff:
    def __init__(self, sid, rank):
        self.id = sid
        self.rank = rank


class DummyCtx(SimpleNamespace):
    pass


def test_budget_for_day_rounds():
    assert budget_for_day(date(2025, 1, 1), "TD.CA1", 5) == {1: 3, 2: 2}


def test_fairness_window_sliding_and_pref():
    rank_map = {1: 1, 2: 2}
    fair = FairnessWindow(rank_map=rank_map)
    d0 = date(2025, 1, 1)
    # seed previous 6 days with rank1 placements
    for i in range(6):
        fair.new_day(d0 + timedelta(days=i))
        fair.bump(1, "CA1", "TD")
    # day 7, rank2 should be preferred
    day7 = d0 + timedelta(days=6)
    fair.new_day(day7)
    import random

    ctx = DummyCtx(can_take=lambda sid, code: True, rng=random.Random(0))
    cc = ChoiceCtx(d=day7, code="CA1", locked_today=set(), ctx=ctx)
    ids = fill_ranked_slots(
        need=2,
        pool_top1=[DummyStaff(1, 1)],
        pool_top2=[DummyStaff(2, 2)],
        cc=cc,
        fairness=fair,
        position="TD",
    )
    # first placement should favor rank2 due to deficit
    assert ids[0] == 2
