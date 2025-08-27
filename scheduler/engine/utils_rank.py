# backend/scheduler/utils_rank.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, List, Optional, Tuple, Set
from dataclasses import dataclass, field      # 👈 thêm field
from datetime import date                     # 👈 thêm date
from models import Staff                      # 👈 dùng model thật
from scheduler.randomize import choose, choose_relaxed
from datetime import date             # cần cho type
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

def fill_ranked_slots(*, need: int, pool_top1: Iterable[Staff], pool_top2: Iterable[Staff], cc: ChoiceCtx) -> List[int]:
    want1, want2 = split_need(need)
    ids: List[int] = []

    def _take_from(src: List[Staff], k: int) -> int:
        taken = 0
        for _ in range(k):
            c = _pick_one(src, cc) or _pick_one(src, cc, relaxed=True)
            if not c:
                break
            ids.append(c.id)
            cc.used.add(c.id)                    # 👈 mark used
            src[:] = [x for x in src if x.id != c.id]
            taken += 1
        return taken

    p1 = [x for x in list(pool_top1) if x.id not in cc.used and x.id not in cc.locked_today]
    p2 = [x for x in list(pool_top2) if x.id not in cc.used and x.id not in cc.locked_today]

    t1 = _take_from(p1, want1)
    t2 = _take_from(p2, want2)

    remain = need - (t1 + t2)
    if remain > 0:
        p = [x for x in (p1 + p2) if x.id not in cc.used and x.id not in cc.locked_today]
        for _ in range(remain):
            c = _pick_one(p, cc) or _pick_one(p, cc, relaxed=True)
            if not c:
                break
            ids.append(c.id)
            cc.used.add(c.id)                    # 👈 mark used
            p = [x for x in p if x.id != c.id]

    return ids