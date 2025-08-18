# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Set
from datetime import date, timedelta  # ✅ cần timedelta
from .core import Context
from scheduler.utils import day_kind
from scheduler.randomize import choose, choose_relaxed, CFG as RAND_CFG

def run_phase_day(ctx: Context, first: date, last: date):
    d = first
    while d <= last:
        used: Set[int] = set()
        locked_today = ctx.locked.get(d, set())
        detail = ctx.profile.day_detail(kind=day_kind(d, ctx.holidays))

        # jitter hàng đợi
        if RAND_CFG["daily_jitter"]:
            if len(ctx.q_tc_day):
                ctx.q_tc_day.rotate(ctx.rng.randrange(len(ctx.q_tc_day)))
            if len(ctx.q_gdv):
                ctx.q_gdv.rotate(ctx.rng.randrange(len(ctx.q_gdv)))

        # 1) fixed trước
        for r in ctx.fixed.get(d, []):
            if r.staff_id in used or r.staff_id in locked_today:
                continue
            if not ctx.can_take(r.staff_id, r.shift_code):
                continue
            ctx.do_place(d, r.staff_id, r.shift_code, "TD")
            used.add(r.staff_id)

        # 2) leader K @ TD (từ TC)
        if detail.TD.get("K_leader", 0) > 0:
            pool = [x for x in list(ctx.q_tc_day) if x.id not in used and x.id not in locked_today]
            tried = set()
            while pool:
                cand = (choose(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng))
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "K"):
                    ctx.do_place(d, cand.id, "K", "TD")
                    used.add(cand.id)
                    break
                pool = [x for x in pool if x.id != cand.id]

        # 3) K_WHITE (T7)
        kw = getattr(detail, "K_WHITE", 0)
        while kw > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng))
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "K"):
                    ctx.do_place(d, cand.id, "K", "K_WHITE")
                    used.add(cand.id)
                    placed = True
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed: break
            kw -= 1

        # 4) PGD: K
        need = detail.PGD.get("K", 0)
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng))
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "K"):
                    ctx.do_place(d, cand.id, "K", "PGD")
                    used.add(cand.id)
                    placed = True
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed: break
            need -= 1

        # 5) PGD: CA2
        need = detail.PGD.get("CA2", 0)
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="CA2", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=ctx.rng))
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "CA2"):
                    ctx.do_place(d, cand.id, "CA2", "PGD")
                    used.add(cand.id)
                    placed = True
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed: break
            need -= 1

        # 6) TD: CA1
        need = detail.TD.get("CA1", 0)
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="CA1", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="CA1", locked_today=locked_today, rng=ctx.rng))
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "CA1"):
                    ctx.do_place(d, cand.id, "CA1", "TD")
                    used.add(cand.id)
                    placed = True
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed: break
            need -= 1

        # 7) TD: CA2
        need = detail.TD.get("CA2", 0)
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="CA2", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=ctx.rng))
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "CA2"):
                    ctx.do_place(d, cand.id, "CA2", "TD")
                    used.add(cand.id)
                    placed = True
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed: break
            need -= 1

        if ctx.save:
            ctx.session.commit()
        d = d + timedelta(days=1)  # ✅ date + 1 day