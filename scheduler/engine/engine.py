# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Tuple
from collections import defaultdict
from datetime import date, timedelta

from .core import build_context, close_context, TOLERANCE
from .phase_night import run_phase_night
from .phase_day import run_phase_day
from ..balancer import balance_hc
from ..placements import reset_trackers, exp_planned, place
from ..validators import validate_one_day_leader

def schedule_month(
    year: int,
    month: int,
    *,
    shuffle: bool = False,
    seed: int | None = None,
    save: bool = False,
    fill_hc: bool = False,
):
    """
    Orchestrator:
      0) Rải HC mặc định cho nhóm HC (T2–T6, trừ Lễ)
      1) Pha NIGHT (lock ngày kế cho người trực đêm)
      2) Pha DAY (tôn trọng lock)
      3) (option) BALANCER – bơm HC để mọi người vào vùng ±0.9
      4) Validate: đúng 1 trưởng ca ngày (K@TD) / ngày
    """
    print(f"[ENGINE] start y={year} m={month} shuffle={shuffle} seed={seed} save={save} fill_hc={fill_hc}")
    reset_trackers()

    ctx, first, last = build_context(year=year, month=month, shuffle=shuffle, seed=seed, save=save)

    try:
        # ---------------- (0) Rải HC mặc định cho nhóm HC ----------------
        print("[ENGINE] phase0: scatter default HC (weekdays, non-holiday)")
        d = first
        while d <= last:
            if d.weekday() < 5 and d not in ctx.holidays:
                lock = ctx.locked.get(d, set())
                for h in ctx.HC:
                    if h.id in lock:
                        continue
                    if not ctx.can_take(h.id, "HC"):
                        continue
                    ctx.do_place(d, h.id, "HC", "TD")
            d += timedelta(days=1)
        if ctx.save:
            ctx.session.commit()

        # ---------------- (1) NIGHT trước DAY ----------------
        print("[ENGINE] phase1: NIGHT")
        night_miss = run_phase_night(ctx, first, last)  # -> List[date]
        if night_miss and len(night_miss) > 0:
            print("[ENGINE] NIGHT_MISS (no night leader):", [x.isoformat() for x in night_miss[:10]], "…")

        # ---------------- (2) DAY ----------------
        print("[ENGINE] phase2: DAY")
        run_phase_day(ctx, first, last)

        # ---------------- (3) BALANCER (optional) ----------------
        if fill_hc:
            print("[ENGINE] phase3: BALANCER HC")
            normalized = [(p.day, p.staff_id, p.shift_code, p.position) for p in ctx._planned]
            everyone = ctx.TC + ctx.GDV + ctx.HC

            proposals = balance_hc(
                planned=normalized,
                staff=everyone,
                holidays=ctx.holidays,
                year=year, month=month,
                credits=ctx.credits,
                tolerance=TOLERANCE,
                locked_by_day=ctx.locked,
            )

            if proposals:
                # quick check “leftovers”
                hc_credit = ctx.credits.get("HC", 1.0)
                final_credit = defaultdict(float, ctx.credit_map)
                for d0, sid0, _code0, _pos0 in proposals:
                    final_credit[sid0] += hc_credit
                leftovers = []
                for sid, base in ctx.base_quota.items():
                    df = base - final_credit.get(sid, 0.0)
                    if df > TOLERANCE + 1e-9:
                        leftovers.append((sid, round(df, 2)))
                if leftovers:
                    print("[BALANCER] Không thể bù hết do thiếu ngày hợp lệ:", leftovers[:10], "…")

            for d0, sid0, code0, pos0 in proposals:
                # Không cần after_place() vì đây là bước cuối
                place(ctx.session, ctx._planned, day=d0, staff_id=sid0, code=code0, position=pos0, save=ctx.save)
            if ctx.save:
                ctx.session.commit()

        # ---------------- (4) Validate ----------------
        print("[ENGINE] phase4: VALIDATE day leaders")
        bad = validate_one_day_leader(ctx._planned, first, last)
        if bad:
            body = {
                "ok": False,
                "error": "Sai số lượng Trưởng ca ngày (K@TD)",
                "details": [{"day": d.isoformat(), "leaders": c} for d, c in bad],
                "planned": exp_planned(ctx._planned),
            }
            return body, 400

        body = {"ok": True, "planned": exp_planned(ctx._planned)}
        print("[ENGINE] done: ok")
        return body

    finally:
        close_context(ctx)