# backend/scheduler/engine/phase_night.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Set
from datetime import date, timedelta

from .core import Context
from .utils_rank import ChoiceCtx, fill_ranked_slots  # dùng bản trong engine/
from scheduler.utils import day_kind
from scheduler.randomize import CFG as RAND_CFG

# Cho phép “cứu cháy” leader đêm: bỏ rào trần công nếu cần thiết
ALLOW_OVERCAP_NIGHT_LEADER = True


def _log(_: Context, msg: str):
    print(f"[NIGHT] {msg}")


def _get_total(night_detail: dict, place_key: str) -> int:
    """
    night_detail: {"TD": {<key D>: x}, "PGD": {<key D>: y}}
    key D có thể là enum ShiftCode.D hoặc string "Đ".
    """
    box = (night_detail.get(place_key, {}) or {})
    # cố lấy theo enum nếu có, fallback sang string
    try:
        from rules.types import ShiftCode  # lazy import để tránh lỗi vòng
        return int(box.get(ShiftCode.D, box.get("Đ", 0)) or 0)
    except Exception:
        return int(box.get("Đ", 0) or 0)


def run_phase_night(ctx: Context, first: date, last: date) -> List[date]:
    """
    Phase NIGHT (cân bằng rank cho GDV):
      1) Leader Đ @ TD: chỉ chọn từ TC (ưu tiên can_take, cuối cùng có thể overcap).
      2) Đ @ TD còn lại: chia ~50/50 giữa GDV rank1 & rank2 (thiếu bù chéo), thiếu nữa fallback TC.
      3) Đ @ PGD: tương tự (2).
    Trả về: danh sách ngày thiếu leader đêm.
    """
    night_miss: List[date] = []

    d = first
    while d <= last:
        used: Set[int] = set()
        locked_today = ctx.locked.get(d, set())
        detail = ctx.profile.expected_night_counts(kind=day_kind(d, ctx.holidays))

        # Tổng nhu cầu Đ theo rule
        td_total = _get_total(detail, "TD")
        pgd_total = _get_total(detail, "PGD")

        # jitter hàng đợi mỗi ngày (nếu bật)
        if RAND_CFG.get("daily_jitter"):
            if len(ctx.q_tc_night):
                ctx.q_tc_night.rotate(ctx.rng.randrange(len(ctx.q_tc_night)))
            if len(ctx.q_gdv1):
                ctx.q_gdv1.rotate(ctx.rng.randrange(len(ctx.q_gdv1)))
            if len(ctx.q_gdv2):
                ctx.q_gdv2.rotate(ctx.rng.randrange(len(ctx.q_gdv2)))

        _log(ctx, f"{d.isoformat()} | need TD.D={td_total} PGD.D={pgd_total} | locked={sorted(locked_today)}")

        # ===== 1) Leader Đ @ TD (từ TC) =====
        placed_leader = False
        leader_id = None
        if td_total > 0:
            pool0 = [
                x for x in list(ctx.q_tc_night)
                if x.id not in used and x.id not in locked_today and getattr(x, "can_night", True)
            ]
            _log(ctx, f"  leader pool0={[x.id for x in pool0]}")

            # Tầng 1: strict can_take
            tried: Set[int] = set()
            pool = list(pool0)
            while pool:
                idx = ctx.rng.randrange(len(pool))
                cand = pool.pop(idx)
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "Đ"):
                    ctx.do_place(d, cand.id, "Đ", "TD")
                    used.add(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed_leader = True
                    leader_id = cand.id
                    _log(ctx, f"  leader placed=TC#{cand.id} (strict)")
                    break

            # Tầng 2: last resort (bỏ quota)
            if not placed_leader and ALLOW_OVERCAP_NIGHT_LEADER and pool0:
                tried = set()
                pool = list(pool0)
                while pool:
                    idx = ctx.rng.randrange(len(pool))
                    cand = pool.pop(idx)
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    # không check can_take
                    ctx.do_place(d, cand.id, "Đ", "TD")
                    used.add(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed_leader = True
                    leader_id = cand.id
                    _log(ctx, f"  leader OVERCAP=TC#{cand.id}")
                    break

            if not placed_leader:
                _log(ctx, "  MISS leader (không đặt được TC cho Đ@TD)")
                night_miss.append(d)

        # ===== 2) Đ @ TD (non‑leader) =====
        td_remain = max(td_total - (1 if placed_leader else 0), 0)
        if td_remain > 0:
            _log(ctx, f"  TD.D remaining={td_remain} (after leader)")
            cc = ChoiceCtx(d=d, code="Đ", locked_today=locked_today, ctx=ctx, used=used)

            pool_top1 = [x for x in list(ctx.q_gdv1) if x.id not in used and getattr(x, "can_night", True)]
            pool_top2 = [x for x in list(ctx.q_gdv2) if x.id not in used and getattr(x, "can_night", True)]

            ids = fill_ranked_slots(need=td_remain, pool_top1=pool_top1, pool_top2=pool_top2, cc=cc)

            placed = 0
            for sid in ids:
                if ctx.can_take(sid, "Đ"):
                    ctx.do_place(d, sid, "Đ", "TD")
                    used.add(sid)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(sid)
                    placed += 1

            # fallback TC nếu còn thiếu
            remain = td_remain - placed
            if remain > 0:
                _log(ctx, f"  TD.D fallback TC remain={remain}")
                pool_tc = [
                    x for x in list(ctx.q_tc_night)
                    if x.id not in used and x.id not in locked_today and getattr(x, "can_night", True)
                ]
                while remain > 0 and pool_tc:
                    idx = ctx.rng.randrange(len(pool_tc))
                    cand = pool_tc.pop(idx)
                    if ctx.can_take(cand.id, "Đ"):
                        ctx.do_place(d, cand.id, "Đ", "TD")
                        used.add(cand.id)
                        ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                        placed += 1
                        remain -= 1
                if remain > 0:
                    _log(ctx, f"  TD.D short={remain}")

        # ===== 3) Đ @ PGD =====
        if pgd_total > 0:
            _log(ctx, f"  PGD.D need={pgd_total}")
            cc = ChoiceCtx(d=d, code="Đ", locked_today=locked_today, ctx=ctx, used=used)
            pool_top1 = [x for x in list(ctx.q_gdv1) if x.id not in used and getattr(x, "can_night", True)]
            pool_top2 = [x for x in list(ctx.q_gdv2) if x.id not in used and getattr(x, "can_night", True)]
            ids = fill_ranked_slots(need=pgd_total, pool_top1=pool_top1, pool_top2=pool_top2, cc=cc)

            placed = 0
            for sid in ids:
                if ctx.can_take(sid, "Đ"):
                    ctx.do_place(d, sid, "Đ", "PGD")
                    used.add(sid)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(sid)
                    placed += 1

            remain = pgd_total - placed
            if remain > 0:
                _log(ctx, f"  PGD.D fallback TC remain={remain}")
                pool_tc = [
                    x for x in list(ctx.q_tc_night)
                    if x.id not in used and x.id not in locked_today and getattr(x, "can_night", True)
                ]
                while remain > 0 and pool_tc:
                    idx = ctx.rng.randrange(len(pool_tc))
                    cand = pool_tc.pop(idx)
                    if ctx.can_take(cand.id, "Đ"):
                        ctx.do_place(d, cand.id, "Đ", "PGD")
                        used.add(cand.id)
                        ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                        placed += 1
                        remain -= 1
                if remain > 0:
                    _log(ctx, f"  PGD.D short={remain}")

        # ===== summary ngày
        _log(ctx, f"summary {d.isoformat()} | leader={leader_id if placed_leader else '-'} | TD.D={td_total} | PGD.D={pgd_total}")

        if ctx.save:
            ctx.session.commit()
        d += timedelta(days=1)

    return night_miss