# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta  # ⬅️ thêm date
from typing import Dict, List, Optional

import logging

from rules import get_profile  # ⬅️ để lấy expected nếu cần đối chiếu nhanh
from scheduler.utils import day_kind  # ⬅️ dùng khi đối chiếu expected từng ngày

from ..balancer import balance_hc
from ..placements import exp_planned, place, reset_trackers, set_fairness_hook
from ..validators import validate_one_day_leader
from .core import TOLERANCE, build_context, close_context
from .phase_day import run_phase_day
from .phase_night import run_phase_night
from .utils_rank import FairnessWindow
from .logging import engine_log, balancer_log
from src.utils.logging import log_call

logger = logging.getLogger(__name__)

@log_call(logger)
def schedule_month(
    year: int,
    month: int,
    *,
    shuffle: bool = False,
    seed: Optional[int] = None,
    save: bool = False,
    fill_hc: bool = False,
    effective_working_days: float | None = None,
    shift_plan_defaults: dict[str, int] | None = None,
):
    engine_log(
        f"start y={year} m={month} shuffle={shuffle} seed={seed} save={save} fill_hc={fill_hc}"
    )
    reset_trackers()

    ctx, first, last = build_context(
        year=year,
        month=month,
        shuffle=shuffle,
        seed=seed,
        save=save,
        working_day_target=effective_working_days,
        shift_plan_defaults=shift_plan_defaults,
    )
    # build rank map for fairness
    rank_map = {st.id: 1 for st in ctx.GDV1}
    rank_map.update({st.id: 1 for st in ctx.TC})
    rank_map.update({st.id: 2 for st in ctx.GDV2})
    fair = FairnessWindow(rank_map=rank_map)
    set_fairness_hook(fair.bump)

    try:
        # (0) Scatter HC mặc định
        engine_log("phase0: scatter default HC (weekdays, non-holiday)")
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
        engine_log(f"phase0 done: placed={placed_p0}")

        # (1) NIGHT
        engine_log("phase1: NIGHT")
        night_miss: List[date] = run_phase_night(ctx, first, last, fair) or []  # ⬅️ rõ type
        if night_miss:
            engine_log(
                f"NIGHT_MISS (no night leader): {[x.isoformat() for x in night_miss[:10]]} …"
            )

        # (2) DAY
        engine_log("phase2: DAY")
        before_day = len(ctx._planned)
        run_phase_day(ctx, first, last, fair)
        after_day = len(ctx._planned)
        engine_log(f"phase2 done: placed={after_day - before_day}, total={after_day}")

        # (3) BALANCER (optional)
        if fill_hc:
            engine_log("phase3: BALANCER HC")
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
                    balancer_log(f"Không thể bù hết do thiếu ngày hợp lệ: {leftovers[:10]} …")

            applied = 0
            for d0, sid0, code0, pos0 in proposals or []:
                place(
                    ctx.session,
                    ctx._planned,
                    day=d0,
                    staff_id=sid0,
                    code=code0,
                    position=pos0,
                    save=ctx.save,
                )
                applied += 1
            if ctx.save:
                ctx.session.commit()
            engine_log(f"phase3 done: applied={applied}, total={len(ctx._planned)}")

        # (4) Validate 1 trưởng ca NGÀY
        engine_log("phase4: VALIDATE day leaders")
        bad = validate_one_day_leader(ctx._planned, first, last)
        if bad:
            body = {
                "ok": False,
                "error": "Sai số lượng Trưởng ca ngày (K@TD)",
                "details": [{"day": d.isoformat(), "leaders": c} for d, c in bad],
                "planned": exp_planned(ctx._planned),
            }
            engine_log("done: error -> 400")
            return body, 400

        # (optional) đối chiếu nhanh expected vs actual để debug (in console)
        try:
            prof = get_profile()
            d = first
            while d <= last:
                kind = day_kind(d, ctx.holidays)
                prof.expected_day_counts(kind)  # {"TD":{"K":...},"PGD":{"K":...,"CA2":...}}
                prof.expected_night_counts(kind)  # {"TD":{"Đ":...}, "PGD":{"Đ":...}}
                # Bạn có thể thêm bộ đếm thực tế theo ngày ở đây (nếu cần)
                d += timedelta(days=1)
        except Exception:
            pass

        body = {"ok": True, "planned": exp_planned(ctx._planned)}
        engine_log(f"done: ok, planned={len(ctx._planned)} rows")
        return body

    finally:
        set_fairness_hook(None)
        close_context(ctx)
