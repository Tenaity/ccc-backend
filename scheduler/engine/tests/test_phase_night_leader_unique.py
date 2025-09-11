# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import date
from collections import deque
import random
import types

import pytest

from scheduler.engine.phase_night import run_phase_night
from scheduler.engine.utils_rank import FairnessWindow


class _Planned:
    def __init__(self, day, staff_id, code, position):
        self.day = day
        self.staff_id = staff_id
        self.shift_code = code
        self.position = position


class FakeCtx:
    """Lightweight Context double for phase_night tests."""

    def __init__(self, *, tc_ids, gdv1_ids, gdv2_ids, holidays=None, locked=None):
        self.q_tc_night = deque([types.SimpleNamespace(id=i, can_night=True, role="TC") for i in tc_ids])
        self.q_gdv1 = deque([types.SimpleNamespace(id=i, can_night=True, role="GDV", rank=1) for i in gdv1_ids])
        self.q_gdv2 = deque([types.SimpleNamespace(id=i, can_night=True, role="GDV", rank=2) for i in gdv2_ids])
        self.q_gdv = deque(list(self.q_gdv1) + list(self.q_gdv2))

        self.locked = locked or {}
        self.fixed = {}
        self.holidays = set(holidays or [])
        self.base_quota = {i: 999 for i in (tc_ids + gdv1_ids + gdv2_ids)}
        self.credit_map = {}
        self._planned = []
        self.rng = random.Random(0)
        self.save = False
        self.session = None

        class Prof:
            def expected_night_counts(self, kind: str):
                return {"TD": {"Đ": 3}, "PGD": {"Đ": 2}}

        self.profile = Prof()

    def can_take(self, staff_id: int, code: str) -> bool:  # pragma: no cover - simple stub
        return True

    def do_place(self, d: date, staff_id: int, code: str, position: str | None):
        self._planned.append(_Planned(d, staff_id, code, position))

    def session_commit(self):  # pragma: no cover - not used
        pass


def _fairness(ctx: FakeCtx) -> FairnessWindow:
    rank_map = {st.id: 1 for st in ctx.q_gdv1}
    rank_map.update({st.id: 1 for st in ctx.q_tc_night})
    rank_map.update({st.id: 2 for st in ctx.q_gdv2})
    return FairnessWindow(rank_map=rank_map)


@pytest.fixture
def the_day():
    return date(2025, 9, 1)


def _count_leaders(ctx: FakeCtx, the_day: date, tc_set: set[int]):
    leaders = [
        p
        for p in ctx._planned
        if p.day == the_day and p.shift_code == "Đ" and p.position == "TD" and p.staff_id in tc_set
    ]
    return leaders


def _count_code_pos(ctx: FakeCtx, the_day: date, code: str, pos: str):
    return sum(1 for p in ctx._planned if p.day == the_day and p.shift_code == code and p.position == pos)


def test_night_has_single_tc_leader_and_gdv_fill_rest(the_day):
    tc_ids = [101, 102, 103]
    gdv1_ids = [201, 202, 203, 204]
    gdv2_ids = [301, 302, 303, 304]
    ctx = FakeCtx(tc_ids=tc_ids, gdv1_ids=gdv1_ids, gdv2_ids=gdv2_ids)

    miss = run_phase_night(ctx, the_day, the_day, _fairness(ctx))
    assert miss == [], "Should not miss leader when TC available"

    tc_set = set(tc_ids)
    leaders = _count_leaders(ctx, the_day, tc_set)
    assert len(leaders) == 1, f"Expected exactly 1 TC leader at Đ@TD, got {len(leaders)}"

    td_d = _count_code_pos(ctx, the_day, "Đ", "TD")
    pgd_d = _count_code_pos(ctx, the_day, "Đ", "PGD")
    assert td_d == 3 and pgd_d == 2, f"Expected TD.D=3, PGD.D=2; got TD.D={td_d}, PGD.D={pgd_d}"

    non_leader_td = [
        p
        for p in ctx._planned
        if p.day == the_day and p.shift_code == "Đ" and p.position == "TD" and p.staff_id not in tc_set
    ]
    assert len(non_leader_td) == 2, "Two remaining TD.D should be GDV (not TC)"


def test_night_miss_when_no_tc_available(the_day):
    tc_ids = [111, 112]
    gdv1_ids = [211, 212, 213, 214]
    gdv2_ids = [311, 312, 313, 314]
    locked = {the_day: set(tc_ids)}
    ctx = FakeCtx(tc_ids=tc_ids, gdv1_ids=gdv1_ids, gdv2_ids=gdv2_ids, locked=locked)

    miss = run_phase_night(ctx, the_day, the_day, _fairness(ctx))
    assert miss == [the_day], "Should record leader-miss when all TC are locked"

    tc_set = set(tc_ids)
    leaders = _count_leaders(ctx, the_day, tc_set)
    assert len(leaders) == 0, "No TC leader should be placed when TC are locked"
