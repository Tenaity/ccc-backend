# backend/scheduler/utils_rank.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from collections import deque, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import date

from models import Staff
from scheduler.randomize import choose, choose_relaxed
from .core import Context

@dataclass
class ChoiceCtx:
    d: date
    code: str
    locked_today: Set[int]
    ctx: Context
    used: Set[int] = field(default_factory=set)    # 👈 thêm used (mặc định set rỗng)

def _rank_of(staff_obj: Staff) -> int:
    r = getattr(staff_obj, "rank", None)
    try:
        return int(r) if r is not None else 2
    except Exception:
        return 2

def split_need(need: int) -> Tuple[int, int]:
    if need <= 0:
        return (0, 0)
    a = need // 2
    b = need - a
    return (b, a) if need % 2 == 1 else (a, b)


def budget_for_day(_d: date, _kind: str, want_total: int) -> Dict[int, int]:
    """Return target allocation of slots per rank for a day.

    The current policy splits ``want_total`` as evenly as possible between
    rank 1 and rank 2, giving any remainder to rank 1.
    """
    r1, r2 = split_need(want_total)
    return {1: r1, 2: r2}

def _pick_one(pool: List[Staff], cc: ChoiceCtx, *, relaxed=False) -> Optional[Staff]:
    if not pool:
        return None
    picker = choose_relaxed if relaxed else choose
    tried: Set[int] = set()
    # lọc trước theo used/locked
    pool = [x for x in pool if x.id not in cc.used and x.id not in cc.locked_today]
    while pool:
        cand = picker(pool, d=cc.d, code=cc.code, locked_today=cc.locked_today, rng=cc.ctx.rng)
        if not cand:
            break
        if cand.id in tried:
            break
        tried.add(cand.id)
        if cc.ctx.can_take(cand.id, cc.code):
            return cand
        pool = [x for x in pool if x.id != cand.id]
    return None


@dataclass
class FairnessWindow:
    """Track rank distribution in a 7-day sliding window."""

    rank_map: Dict[int, int]
    size: int = 7
    _data: Dict[Tuple[str, str, int], deque[int]] = field(default_factory=lambda: defaultdict(deque))
    _today: Optional[date] = None
    _today_counts: Dict[Tuple[str, str, int], int] = field(default_factory=dict)

    def new_day(self, d: date) -> None:
        if self._today != d:
            if self._today is not None:
                for key, cnt in self._today_counts.items():
                    dq = self._data.setdefault(key, deque(maxlen=self.size))
                    dq.append(cnt)
            self._today_counts.clear()
            self._today = d

    def bump(self, staff_id: int, code: str, position: str | None) -> None:
        rank = self.rank_map.get(staff_id, 2)
        key = (code, position or "", rank)
        self._today_counts[key] = self._today_counts.get(key, 0) + 1

    def today_for(self, code: str, position: str | None) -> Tuple[int, int]:
        k1 = (code, position or "", 1)
        k2 = (code, position or "", 2)
        return self._today_counts.get(k1, 0), self._today_counts.get(k2, 0)

    def summary(self, code: str, position: str | None) -> Tuple[int, int]:
        k1 = (code, position or "", 1)
        k2 = (code, position or "", 2)
        r1 = sum(self._data.get(k1, [])) + self._today_counts.get(k1, 0)
        r2 = sum(self._data.get(k2, [])) + self._today_counts.get(k2, 0)
        return r1, r2


def fill_ranked_slots(
    *,
    need: int,
    pool_top1: Iterable[Staff],
    pool_top2: Iterable[Staff],
    cc: ChoiceCtx,
    fairness: Optional[FairnessWindow] = None,
    position: str | None = None,
    want: Optional[Dict[int, int]] = None,
) -> List[int]:
    # Determine targets per rank
    if want is None:
        want1, want2 = split_need(need)
    else:
        want1, want2 = want.get(1, 0), want.get(2, 0)
    ids: List[int] = []

    p1 = [x for x in list(pool_top1) if x.id not in cc.used and x.id not in cc.locked_today]
    p2 = [x for x in list(pool_top2) if x.id not in cc.used and x.id not in cc.locked_today]

    want_map = {1: want1, 2: want2}
    pools = {1: p1, 2: p2}

    while want_map[1] > 0 or want_map[2] > 0:
        prefer: Optional[int] = None
        if fairness is not None:
            r1, r2 = fairness.summary(cc.code, position)
            if r1 < r2:
                prefer = 1
            elif r2 < r1:
                prefer = 2
        order = [r for r in (prefer, 1, 2) if r is not None]

        placed = False
        for rk in order:
            if want_map[rk] <= 0:
                continue
            pool = pools[rk]
            c = _pick_one(pool, cc) or _pick_one(pool, cc, relaxed=True)
            if not c:
                continue
            ids.append(c.id)
            cc.used.add(c.id)
            pools[rk] = [x for x in pool if x.id != c.id]
            want_map[rk] -= 1
            if fairness is not None:
                fairness.bump(c.id, cc.code, position)
            placed = True
            break
        if not placed:
            break

    remain = want_map[1] + want_map[2]
    if remain > 0:
        p = [x for x in (p1 + p2) if x.id not in cc.used and x.id not in cc.locked_today]
        for _ in range(remain):
            c = _pick_one(p, cc) or _pick_one(p, cc, relaxed=True)
            if not c:
                break
            ids.append(c.id)
            cc.used.add(c.id)
            if fairness is not None:
                fairness.bump(c.id, cc.code, position)
            p = [x for x in p if x.id != c.id]

    return ids
