from collections import deque
from dataclasses import dataclass
from types import SimpleNamespace
from datetime import date
import random

from scheduler.engine.phase_day import run_phase_day
from rules.types import ShiftCode


@dataclass
class DummyStaff:
    id: int
    rank: int = 1


class DummyProfile:
    def day_detail(self, kind):
        class Detail:
            TD = {ShiftCode.K: 1, ShiftCode.CA1: 1, ShiftCode.CA2: 1}
            PGD = {ShiftCode.K: 1, ShiftCode.CA2: 1}

        return Detail()


def test_fixed_assignments_do_not_duplicate():
    d = date(2025, 1, 1)
    planned = []

    def can_take(sid, code):
        return True

    def do_place(day, staff_id, code, position):
        planned.append(SimpleNamespace(day=day, staff_id=staff_id, shift_code=code, position=position))

    ctx = SimpleNamespace(
        locked={},
        fixed={
            d: [
                SimpleNamespace(staff_id=1, shift_code="K"),
                SimpleNamespace(staff_id=2, shift_code="CA1"),
                SimpleNamespace(staff_id=3, shift_code="CA2"),
            ]
        },
        _planned=planned,
        profile=DummyProfile(),
        holidays=set(),
        can_take=can_take,
        do_place=do_place,
        q_tc_day=deque([DummyStaff(id=6)]),
        q_gdv1=deque([DummyStaff(id=7, rank=1)]),
        q_gdv2=deque([DummyStaff(id=8, rank=2)]),
        save=False,
        session=None,
        rng=random.Random(0),
    )

    # Pre-existing PGD assignments (simulate fixed at PGD)
    do_place(d, 4, "K", "PGD")
    do_place(d, 5, "CA2", "PGD")

    run_phase_day(ctx, d, d)

    assert len(planned) == 5

    by_code = {}
    for p in planned:
        if p.day != d:
            continue
        key = (p.position, p.shift_code)
        by_code[key] = by_code.get(key, 0) + 1

    assert by_code.get(("TD", "K")) == 1
    assert by_code.get(("TD", "CA1")) == 1
    assert by_code.get(("TD", "CA2")) == 1
    assert by_code.get(("PGD", "K")) == 1
    assert by_code.get(("PGD", "CA2")) == 1

    # không có staff mới nào được thêm ngoài danh sách cố định
    assert {p.staff_id for p in planned} == {1, 2, 3, 4, 5}

