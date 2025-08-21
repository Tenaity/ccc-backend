# -*- coding: utf-8 -*-
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta, date  # ⬅️ thêm date
from typing import Dict, List, Tuple

from .core import build_context, close_context, TOLERANCE
from .phase_night import run_phase_night
from .phase_day import run_phase_day
from ..balancer import balance_hc
from ..placements import reset_trackers, exp_planned, place
from ..validators import validate_one_day_leader
from rules import get_profile  # ⬅️ để lấy expected nếu cần đối chiếu nhanh
from scheduler.utils import day_kind  # ⬅️ dùng khi đối chiếu expected từng ngày

def schedule_month(
    year: int,
    month: int,
    *,
    shuffle: bool = False,
    seed: int | None = None,
    save: bool = False,
    fill_hc: bool = False,
):
    print(f"[ENGINE] start y={year} m={month} shuffle={shuffle} seed={seed} save={save} fill_hc={fill_hc}")
    reset_trackers()

    ctx, first, last = build_context(year=year, month=month, shuffle=shuffle, seed=seed, save=save)

    try:
        # (0) Scatter HC mặc định
        print("[ENGINE] phase0: scatter default HC (weekdays, non-holiday)")
        placed_p0 = 0
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
                    placed_p0 += 1
            d += timedelta(days=1)
        if ctx.save:
            ctx.session.commit()
        print(f"[ENGINE] phase0 done: placed={placed_p0}")

        # (1) NIGHT
        print("[ENGINE] phase1: NIGHT")
        night_miss: List[date] = run_phase_night(ctx, first, last) or []   # ⬅️ rõ type
        if night_miss:
            print("[ENGINE] NIGHT_MISS (no night leader):", [x.isoformat() for x in night_miss[:10]], "…")

        # (2) DAY
        print("[ENGINE] phase2: DAY")
        before_day = len(ctx._planned)
        run_phase_day(ctx, first, last)
        after_day = len(ctx._planned)
        print(f"[ENGINE] phase2 done: placed={after_day - before_day}, total={after_day}")

        # (3) BALANCER (optional)
        if fill_hc:
            print("[ENGINE] phase3: BALANCER HC")
            normalized = [(p.day, p.staff_id, p.shift_code, p.position) for p in ctx._planned]
            everyone = ctx.TC + ctx.GDV + ctx.HC

            proposals = balance_hc(
                planned=normalized,
                staff=everyone,
                holidays=ctx.holidays,
                year=year,
                month=month,
                credits=ctx.credits,
                tolerance=TOLERANCE,
                locked_by_day=ctx.locked,
            )
            if proposals:
                hc_credit = ctx.credits.get("HC", 1.0)
                final_credit: Dict[int, float] = defaultdict(float, ctx.credit_map)
                for d0, sid0, _code0, _pos0 in proposals:
                    final_credit[sid0] += hc_credit
                leftovers = []
                for sid, base in ctx.base_quota.items():
                    df = base - final_credit.get(sid, 0.0)
                    if df > TOLERANCE + 1e-9:
                        leftovers.append((sid, round(df, 2)))
                if leftovers:
                    print("[BALANCER] Không thể bù hết do thiếu ngày hợp lệ:", leftovers[:10], "…")

            applied = 0
            for d0, sid0, code0, pos0 in (proposals or []):
                place(ctx.session, ctx._planned, day=d0, staff_id=sid0, code=code0, position=pos0, save=ctx.save)
                applied += 1
            if ctx.save:
                ctx.session.commit()
            print(f"[ENGINE] phase3 done: applied={applied}, total={len(ctx._planned)}")

        # (4) Validate 1 trưởng ca NGÀY
        print("[ENGINE] phase4: VALIDATE day leaders")
        bad = validate_one_day_leader(ctx._planned, first, last)
        if bad:
            body = {
                "ok": False,
                "error": "Sai số lượng Trưởng ca ngày (K@TD)",
                "details": [{"day": d.isoformat(), "leaders": c} for d, c in bad],
                "planned": exp_planned(ctx._planned),
            }
            print("[ENGINE] done: error -> 400")
            return body, 400

        # (optional) đối chiếu nhanh expected vs actual để debug (in console)
        try:
            prof = get_profile()
            d = first
            while d <= last:
                kind = day_kind(d, ctx.holidays)
                exp_day = prof.expected_day_counts(kind)         # {"TD":{"K":...},"PGD":{"K":...,"CA2":...}}
                exp_night = prof.expected_night_counts(kind)     # {"TD":{"Đ":...}, "PGD":{"Đ":...}}
                # Bạn có thể thêm bộ đếm thực tế theo ngày ở đây (nếu cần)
                d += timedelta(days=1)
        except Exception:
            pass

        body = {"ok": True, "planned": exp_planned(ctx._planned)}
        print(f"[ENGINE] done: ok, planned={len(ctx._planned)} rows")
        return body

    finally:
        close_context(ctx)