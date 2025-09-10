# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Set
from datetime import date, timedelta

from rules.types import ShiftCode
from .core import Context
from scheduler.utils import day_kind
from .utils_rank import ChoiceCtx, fill_ranked_slots


def _log(_: Context, msg: str):
    print(f"[DAY ] {msg}")


def run_phase_day(ctx: Context, first: date, last: date):
    d = first
    while d <= last:
        locked_today: Set[int] = ctx.locked.get(d, set())

        # used = mọi người đã được đặt TRONG NGÀY d (vd. Đêm đã đặt trước đó)
        pre_used = {p.staff_id for p in ctx._planned if p.day == d}
        used: Set[int] = set(pre_used)

        detail = ctx.profile.day_detail(kind=day_kind(d, ctx.holidays))

        # ============ 1) fixed trước (nếu có) ============
        for r in ctx.fixed.get(d, []):
            if r.staff_id in used or r.staff_id in locked_today:
                continue
            if not ctx.can_take(r.staff_id, r.shift_code):
                continue
            # fixed luôn tại TD (yêu cầu cũ), nếu cần có PGD thì backend sẽ seed
            ctx.do_place(d, r.staff_id, r.shift_code, "TD")
            used.add(r.staff_id)
            _log(ctx, f"{d.isoformat()} FIXED {r.shift_code}@TD -> #{r.staff_id}")

        # Đếm số lượng đã được phân ca trước khi dispatch thêm
        td_k_filled = pgd_k_filled = pgd_ca2_filled = td_ca1_filled = td_ca2_filled = 0
        for p in ctx._planned:
            if p.day != d:
                continue
            if p.position == "TD" and p.shift_code == ShiftCode.K:
                td_k_filled += 1
            elif p.position == "PGD" and p.shift_code == ShiftCode.K:
                pgd_k_filled += 1
            elif p.position == "PGD" and p.shift_code == ShiftCode.CA2:
                pgd_ca2_filled += 1
            elif p.position == "TD" and p.shift_code == ShiftCode.CA1:
                td_ca1_filled += 1
            elif p.position == "TD" and p.shift_code == ShiftCode.CA2:
                td_ca2_filled += 1

        k_td_need = max(int(detail.TD.get(ShiftCode.K, 0)) - td_k_filled, 0)
        pgd_k_need = max(int(detail.PGD.get(ShiftCode.K, 0)) - pgd_k_filled, 0)
        pgd_ca2_need = max(int(detail.PGD.get(ShiftCode.CA2, 0)) - pgd_ca2_filled, 0)
        td_ca1_need = max(int(detail.TD.get(ShiftCode.CA1, 0)) - td_ca1_filled, 0)
        td_ca2_need = max(int(detail.TD.get(ShiftCode.CA2, 0)) - td_ca2_filled, 0)

        # ============ 2) TD · K (leader) = từ TC ============
        if k_td_need > 0:
            # Pool TC hợp lệ trong ngày d
            pool_ids_before = [x.id for x in ctx.q_tc_day]
            pool_tc = [x for x in list(ctx.q_tc_day)
                       if x.id not in used and x.id not in locked_today]

            _log(ctx, f"{d.isoformat()} TD.K need={k_td_need} | TC pool(before)={pool_ids_before} | usable={[x.id for x in pool_tc]}")

            placed_leader = False
            tried = set()

            # đi theo thứ tự trong deque; ai không đạt quota thì thử người tiếp theo
            # khi chọn được, đẩy người đó xuống cuối deque để fair vòng sau
            for cand in list(ctx.q_tc_day):
                if cand.id in tried:
                    continue
                tried.add(cand.id)
                if cand.id in used or cand.id in locked_today:
                    continue
                if ctx.can_take(cand.id, "K"):
                    ctx.do_place(d, cand.id, "K", "TD")
                    used.add(cand.id)
                    placed_leader = True

                    # --- xoay deque: đưa cand xuống cuối để không bị “ăn” liên tục
                    while len(ctx.q_tc_day) and ctx.q_tc_day[0].id != cand.id:
                        ctx.q_tc_day.rotate(-1)
                    if len(ctx.q_tc_day) and ctx.q_tc_day[0].id == cand.id:
                        ctx.q_tc_day.rotate(-1)

                    _log(ctx, f"{d.isoformat()} TD.K leader -> TC#{cand.id} | TC queue(after)={[x.id for x in ctx.q_tc_day]}")
                    break

            if placed_leader:
                k_td_need = max(k_td_need - 1, 0)
            else:
                _log(ctx, f"{d.isoformat()} TD.K leader MISS (usable={ [x.id for x in pool_tc] })")

        # ============ 3) PGD · K (đỏ) ============
        if pgd_k_need > 0:
            cc = ChoiceCtx(d=d, code="K", locked_today=locked_today, used=used, ctx=ctx)
            ids = fill_ranked_slots(need=pgd_k_need,
                                    pool_top1=ctx.q_gdv1,
                                    pool_top2=ctx.q_gdv2,
                                    cc=cc)
            for sid in ids:
                ctx.do_place(d, sid, "K", "PGD")
                _log(ctx, f"{d.isoformat()} PGD.K -> #{sid}")

        # ============ 4) PGD · CA2 ============
        if pgd_ca2_need > 0:
            cc = ChoiceCtx(d=d, code="CA2", locked_today=locked_today, used=used, ctx=ctx)
            ids = fill_ranked_slots(need=pgd_ca2_need,
                                    pool_top1=ctx.q_gdv1,
                                    pool_top2=ctx.q_gdv2,
                                    cc=cc)
            for sid in ids:
                ctx.do_place(d, sid, "CA2", "PGD")
                _log(ctx, f"{d.isoformat()} PGD.CA2 -> #{sid}")

        # ============ 5) TD · CA1 ============
        if td_ca1_need > 0:
            cc = ChoiceCtx(d=d, code="CA1", locked_today=locked_today, used=used, ctx=ctx)
            ids = fill_ranked_slots(need=td_ca1_need,
                                    pool_top1=ctx.q_gdv1,
                                    pool_top2=ctx.q_gdv2,
                                    cc=cc)
            for sid in ids:
                ctx.do_place(d, sid, "CA1", "TD")
                _log(ctx, f"{d.isoformat()} TD.CA1 -> #{sid}")

        # ============ 6) TD · CA2 ============
        if td_ca2_need > 0:
            cc = ChoiceCtx(d=d, code="CA2", locked_today=locked_today, used=used, ctx=ctx)
            ids = fill_ranked_slots(need=td_ca2_need,
                                    pool_top1=ctx.q_gdv1,
                                    pool_top2=ctx.q_gdv2,
                                    cc=cc)
            for sid in ids:
                ctx.do_place(d, sid, "CA2", "TD")
                _log(ctx, f"{d.isoformat()} TD.CA2 -> #{sid}")

        if ctx.save:
            ctx.session.commit()

        # Summary ngắn cho ngày d (dễ đối chiếu UI)
        td_k = int(detail.TD.get(ShiftCode.K, 0))
        td_ca1 = int(detail.TD.get(ShiftCode.CA1, 0))
        td_ca2 = int(detail.TD.get(ShiftCode.CA2, 0))
        pgd_k = int(detail.PGD.get(ShiftCode.K, 0))
        pgd_ca2 = int(detail.PGD.get(ShiftCode.CA2, 0))
        _log(ctx, f"summary {d.isoformat()} | TD: K={td_k} CA1={td_ca1} CA2={td_ca2} | PGD: K={pgd_k} CA2={pgd_ca2}")

        d += timedelta(days=1)

