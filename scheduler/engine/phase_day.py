# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Set
from datetime import date, timedelta

from rules.types import ShiftCode
from .core import Context
from scheduler.utils import day_kind
from scheduler.randomize import choose, choose_relaxed, CFG as RAND_CFG


def _log(_: Context, msg: str):
    print(f"[DAY] {msg}")


def run_phase_day(ctx: Context, first: date, last: date):
    """
    Phase DAY – chỉ xếp ca ngày (K/CA1/CA2 ở TD, K/CA2 ở PGD).

    NGUYÊN TẮC QUAN TRỌNG:
    - Không đụng/ghi đè ca Đ (đêm) đã xếp ở phase_night:
      + Trước khi xếp, lấy toàn bộ staff_id đã có assignment trong ngày d
        -> đưa vào 'used' để day-phase không chọn họ nữa.
    - Tôn trọng 'locked_today' và 'can_take'.
    - K @ TD: luôn xếp 1 TC làm leader (nếu rule có nhu cầu K ở TD),
      phần K còn lại (nếu có) mới xếp tiếp từ TC/GDV.
    """
    d = first
    while d <= last:
        locked_today = ctx.locked.get(d, set())

        # === (0) Lấy nhu cầu theo rule cho ngày d ===
        detail = ctx.profile.day_detail(kind=day_kind(d, ctx.holidays))
        k_td_need   = int(detail.TD.get(ShiftCode.K, 0))     # K @ TD (ít nhất 1 là leader)
        ca1_td_need = int(detail.TD.get(ShiftCode.CA1, 0))   # CA1 @ TD
        ca2_td_need = int(detail.TD.get(ShiftCode.CA2, 0))   # CA2 @ TD
        k_pgd_need  = int(detail.PGD.get(ShiftCode.K, 0))    # K @ PGD
        ca2_pgd_need= int(detail.PGD.get(ShiftCode.CA2, 0))  # CA2 @ PGD

        # === (1) Những người đã có assignment trong ngày d (ví dụ Đ ở phase_night) ===
        already_used_today: Set[int] = {p.staff_id for p in ctx._planned if p.day == d}
        used: Set[int] = set(already_used_today)

        _log(ctx, f"{d.isoformat()} | need TD: K={k_td_need}, CA1={ca1_td_need}, CA2={ca2_td_need} | "
                   f"PGD: K={k_pgd_need}, CA2={ca2_pgd_need} | locked={sorted(locked_today)} | "
                   f"already_used={sorted(already_used_today)}")

        # === (2) jitter hàng đợi (tăng độ ngẫu nhiên) ===
        if RAND_CFG["daily_jitter"]:
            if len(ctx.q_tc_day):
                ctx.q_tc_day.rotate(ctx.rng.randrange(len(ctx.q_tc_day)))
            if len(ctx.q_gdv):
                ctx.q_gdv.rotate(ctx.rng.randrange(len(ctx.q_gdv)))

        # === (3) Xếp fixed trước (nếu có), vẫn tôn trọng used/lock/can_take ===
        for r in ctx.fixed.get(d, []):
            if r.staff_id in used or r.staff_id in locked_today:
                continue
            if not ctx.can_take(r.staff_id, r.shift_code):
                continue
            # NOTE: nếu FixedAssignment có position, nên dùng r.position thay "TD".
            ctx.do_place(d, r.staff_id, r.shift_code, "TD")
            used.add(r.staff_id)
            _log(ctx, f"  fixed placed staff#{r.staff_id} {r.shift_code}@TD")

        # === (4) TD · K (leader từ TC trước) ===
        if k_td_need > 0:
            pool = [x for x in list(ctx.q_tc_day) if x.id not in used and x.id not in locked_today]
            tried = set()
            placed_leader = False
            while pool:
                cand = (choose(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng))
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "K"):
                    ctx.do_place(d, cand.id, "K", "TD")  # leader ngày
                    used.add(cand.id)
                    placed_leader = True
                    k_td_need -= 1
                    _log(ctx, f"  TD.K leader placed=TC#{cand.id}")
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed_leader:
                _log(ctx, "  TD.K leader MISS (no eligible TC)")

        # (4.2) Nếu rule còn yêu cầu K @ TD (hiện tại thường = 0), xếp tiếp từ TC/GDV
        while k_td_need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng))
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "K"):
                    ctx.do_place(d, cand.id, "K", "TD")
                    used.add(cand.id)
                    placed = True
                    _log(ctx, f"  TD.K placed=#{cand.id}")
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, "  TD.K short (can_take blocked or pool empty)")
                break
            k_td_need -= 1

        # === (5) PGD: K ===
        need = k_pgd_need
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=ctx.rng))
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "K"):
                    ctx.do_place(d, cand.id, "K", "PGD")
                    used.add(cand.id)
                    placed = True
                    _log(ctx, f"  PGD.K placed=#{cand.id}")
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, "  PGD.K short (can_take blocked or pool empty)")
                break
            need -= 1

        # === (6) PGD: CA2 ===
        need = ca2_pgd_need
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="CA2", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=ctx.rng))
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "CA2"):
                    ctx.do_place(d, cand.id, "CA2", "PGD")
                    used.add(cand.id)
                    placed = True
                    _log(ctx, f"  PGD.CA2 placed=#{cand.id}")
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, "  PGD.CA2 short (can_take blocked or pool empty)")
                break
            need -= 1

        # === (7) TD: CA1 ===
        need = ca1_td_need
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="CA1", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="CA1", locked_today=locked_today, rng=ctx.rng))
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "CA1"):
                    ctx.do_place(d, cand.id, "CA1", "TD")
                    used.add(cand.id)
                    placed = True
                    _log(ctx, f"  TD.CA1 placed=#{cand.id}")
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, "  TD.CA1 short (can_take blocked or pool empty)")
                break
            need -= 1

        # === (8) TD: CA2 ===
        need = ca2_td_need
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_day)
                    if x.id not in used and x.id not in locked_today]
            tried = set()
            placed = False
            while pool:
                cand = (choose(pool, d=d, code="CA2", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=ctx.rng))
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "CA2"):
                    ctx.do_place(d, cand.id, "CA2", "TD")
                    used.add(cand.id)
                    placed = True
                    _log(ctx, f"  TD.CA2 placed=#{cand.id}")
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, "  TD.CA2 short (can_take blocked or pool empty)")
                break
            need -= 1

        # === (9) commit + summary cho ngày d ===
        if ctx.save:
            ctx.session.commit()

        # Summary nhanh (chỉ ca ngày, không tính Đ)
        td_k  = sum(1 for p in ctx._planned if p.day == d and p.shift_code == "K"  and p.position == "TD")
        td_c1 = sum(1 for p in ctx._planned if p.day == d and p.shift_code == "CA1" and p.position == "TD")
        td_c2 = sum(1 for p in ctx._planned if p.day == d and p.shift_code == "CA2" and p.position == "TD")
        pgd_k = sum(1 for p in ctx._planned if p.day == d and p.shift_code == "K"  and p.position == "PGD")
        pgd_c2= sum(1 for p in ctx._planned if p.day == d and p.shift_code == "CA2" and p.position == "PGD")

        _log(ctx, f"summary {d.isoformat()} | TD: K={td_k}, CA1={td_c1}, CA2={td_c2} | PGD: K={pgd_k}, CA2={pgd_c2}")

        d = d + timedelta(days=1)