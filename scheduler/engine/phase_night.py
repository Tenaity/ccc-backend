# engine/phase_night.py
from __future__ import annotations
from typing import List, Set
from datetime import date, timedelta
from .core import Context
from scheduler.utils import day_kind
from scheduler.randomize import choose, choose_relaxed, CFG as RAND_CFG
from rules.types import ShiftCode  # dùng ShiftCode.D

# Cho phép “cứu cháy” leader đêm (bỏ quota nếu bắt buộc)
ALLOW_OVERCAP_NIGHT_LEADER = True

def _log(_: Context, msg: str):
    print(f"[NIGHT] {msg}")

def run_phase_night(ctx: Context, first: date, last: date) -> List[date]:
    """
    Input:
      - ctx: Context (hàng đợi TC/GDV đêm, lock-by-day, RNG, credits/quota, session…)
      - first, last: khoảng ngày của tháng

    Profile (enum-based) cung cấp:
      detail = ctx.profile.night_detail(kind)
        TD:  {ShiftCode.D: X}   # tổng Đ @ Tổng đài (gồm 1 leader + (X-1) Đ thường)
        PGD: {ShiftCode.D: Y}   # tổng Đ @ PGD

    Chính sách:
      - Leader Đ @ TD: chọn từ hàng đợi TC đêm (q_tc_night), tôn trọng lock/quota. Nếu bí có thể “overcap”.
      - Đ @ TD (còn lại): chọn từ GDV + TC đêm (q_gdv + q_tc_night), tôn trọng lock/quota.
      - Đ @ PGD: tương tự, chọn từ GDV + TC đêm.

    Output:
      - night_miss: List[date] các ngày KHÔNG gán được leader đêm (khi TD.D > 0 nhưng không chọn được TC).
    """
    night_miss: List[date] = []

    d = first
    while d <= last:
        used: Set[int] = set()
        locked_today = ctx.locked.get(d, set())
        detail = ctx.profile.night_detail(kind=day_kind(d, ctx.holidays))

        # Tổng Đ theo rule (enum)
        td_total  = int(detail.TD.get(ShiftCode.D, 0))
        pgd_total = int(detail.PGD.get(ShiftCode.D, 0))

        _log(ctx, f"{d.isoformat()} | need TD.D={td_total} PGD.D={pgd_total} | locked={sorted(list(locked_today))}")

        # Jitter hàng đợi (nếu bật)
        if RAND_CFG["daily_jitter"]:
            if len(ctx.q_tc_night):
                ctx.q_tc_night.rotate(ctx.rng.randrange(len(ctx.q_tc_night)))
            if len(ctx.q_gdv):
                ctx.q_gdv.rotate(ctx.rng.randrange(len(ctx.q_gdv)))

        # ===== 1) Leader Đ @ TD (từ TC) =====
        placed_leader = False
        leader_needed = 1 if td_total > 0 else 0
        leader_id = None

        if leader_needed:
            pool0 = [x for x in list(ctx.q_tc_night)
                     if x.id not in used
                     and x.id not in locked_today
                     and getattr(x, "can_night", True)]
            _log(ctx, f"  leader pool0={ [x.id for x in pool0] }")

            # Tầng 1: chọn “chuẩn”
            tried: Set[int] = set()
            pool = list(pool0)
            while pool:
                cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "Đ"):
                    ctx.do_place(d, cand.id, "Đ", "TD")
                    used.add(cand.id)
                    leader_id = cand.id
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed_leader = True
                    _log(ctx, f"  leader placed=TC#{cand.id} (strict)")
                    break
                _log(ctx, f"  leader skip=TC#{cand.id} (blocked by quota/rules)")
                pool = [x for x in pool if x.id != cand.id]

            # Tầng 2: relaxed
            if not placed_leader and pool0:
                tried = set()
                pool = list(pool0)
                while pool:
                    cand = choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                    if not cand: break
                    if cand.id in tried: break
                    tried.add(cand.id)
                    if ctx.can_take(cand.id, "Đ"):
                        ctx.do_place(d, cand.id, "Đ", "TD")
                        used.add(cand.id)
                        leader_id = cand.id
                        ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                        placed_leader = True
                        _log(ctx, f"  leader placed=TC#{cand.id} (relaxed)")
                        break
                    _log(ctx, f"  leader skip(relaxed)=TC#{cand.id} (blocked)")
                    pool = [x for x in pool if x.id != cand.id]

            # Tầng 3: last resort (overcap)
            if not placed_leader and ALLOW_OVERCAP_NIGHT_LEADER and pool0:
                tried = set()
                pool = list(pool0)
                while pool:
                    cand = choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                    if not cand: break
                    if cand.id in tried: break
                    tried.add(cand.id)
                    # ép xếp, không check can_take
                    ctx.do_place(d, cand.id, "Đ", "TD")
                    used.add(cand.id)
                    leader_id = cand.id
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed_leader = True
                    _log(ctx, f"  leader placed=TC#{cand.id} (OVERCAP)")
                    break

            if not placed_leader:
                reasons = []
                if not pool0:
                    reasons.append("pool0=∅ (TC không ai can_night hoặc bị lock)")
                else:
                    overcap_ids = [x.id for x in pool0 if not ctx.can_take(x.id, 'Đ')]
                    if overcap_ids and len(overcap_ids) == len(pool0):
                        reasons.append("tất cả ứng viên vượt trần/quy tắc")
                _log(ctx, f"  leader MISS | reasons={'; '.join(reasons) or 'unknown'}")
                night_miss.append(d)

        # ===== 2) Đ @ TD (phần còn lại) =====
        white_needed = max(td_total - (1 if placed_leader else 0), 0)
        _log(ctx, f"  TD.D remaining={white_needed} (after leader)")
        td_ids = [leader_id] if leader_id else []
        while white_needed > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_night)
                    if x.id not in used and x.id not in locked_today and getattr(x, "can_night", True)]
            if not pool:
                _log(ctx, f"  TD.D short (pool empty)")
                break
            placed = False
            tried: Set[int] = set()
            while pool:
                cand = (choose(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng))
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "Đ"):
                    ctx.do_place(d, cand.id, "Đ", "TD")  # không còn "D_WHITE"
                    used.add(cand.id)
                    td_ids.append(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed = True
                    _log(ctx, f"  TD.D placed=#{cand.id}")
                    break
                _log(ctx, f"  TD.D skip=#{cand.id} (blocked)")
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, f"  TD.D short (blocked)")
                break
            white_needed -= 1

        # ===== 3) Đ @ PGD =====
        need_pgd = pgd_total
        _log(ctx, f"  PGD.D need={need_pgd}")
        pgd_ids: List[int] = []
        while need_pgd > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_night)
                    if x.id not in used and x.id not in locked_today and getattr(x, "can_night", True)]
            if not pool:
                _log(ctx, f"  PGD.D short (pool empty)")
                break
            placed = False
            tried = set()
            while pool:
                cand = (choose(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng))
                if not cand: break
                if cand.id in tried: break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "Đ"):
                    ctx.do_place(d, cand.id, "Đ", "PGD")
                    used.add(cand.id)
                    pgd_ids.append(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed = True
                    _log(ctx, f"  PGD.D placed=#{cand.id}")
                    break
                _log(ctx, f"  PGD.D skip=#{cand.id} (blocked)")
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, f"  PGD.D short (blocked)")
                break
            need_pgd -= 1

        # ===== Tóm tắt ngày =====
        _log(ctx, f"summary {d.isoformat()} | leader={leader_id or '-'} | TD.D={len([x for x in td_ids if x])} | PGD.D={len(pgd_ids)}")

        if ctx.save:
            ctx.session.commit()
        d += timedelta(days=1)

    return night_miss