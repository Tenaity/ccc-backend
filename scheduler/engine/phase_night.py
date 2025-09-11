# backend/scheduler/engine/phase_night.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Set
from datetime import date, timedelta

from .core import Context
from .utils_rank import ChoiceCtx, fill_ranked_slots, budget_for_day, FairnessWindow  # dùng bản trong engine/
from scheduler.utils import day_kind
from scheduler.randomize import CFG as RAND_CFG
from .logging import night_log

# Cho phép “cứu cháy” leader đêm: bỏ rào trần công nếu cần thiết
ALLOW_OVERCAP_NIGHT_LEADER = True


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


def run_phase_night(ctx: Context, first: date, last: date, fair: FairnessWindow) -> List[date]:
    """
    Phase NIGHT (cân bằng rank cho GDV):
      1) Leader Đ @ TD: chỉ chọn từ TC (ưu tiên can_take, cuối cùng có thể overcap).
      2) Đ @ TD còn lại: chia ~50/50 giữa GDV rank1 & rank2 (thiếu bù chéo), thiếu log "short" (không dùng TC).
      3) Đ @ PGD: tương tự (2) nhưng thiếu có thể fallback TC.
    Trả về: danh sách ngày thiếu leader đêm.
    """
    night_miss: List[date] = []
    tc_ids = {getattr(st, "id") for st in getattr(ctx, "TC", [])}
    if not tc_ids:
        tc_ids = {st.id for st in ctx.q_tc_night}

    d = first
    while d <= last:
        fair.new_day(d)
        used: Set[int] = {p.staff_id for p in ctx._planned if p.day == d}
        locked_today = ctx.locked.get(d, set())
        for sid in sorted(locked_today):
            night_log(ctx, f"{d.isoformat()} SKIP (locked) #{sid}")
        detail = ctx.profile.expected_night_counts(kind=day_kind(d, ctx.holidays))

        # Tổng nhu cầu Đ theo rule
        td_total = _get_total(detail, "TD")
        pgd_total = _get_total(detail, "PGD")

        placed_leader = False
        leader_id = None

        # Fixed assignments for night
        for r in ctx.fixed.get(d, []):
            if r.shift_code != "Đ":
                continue
            pos = getattr(r, "position", "TD") or "TD"
            if r.staff_id in locked_today:
                night_log(ctx, f"{d.isoformat()} SKIP (locked) #{r.staff_id}")
                continue
            if r.staff_id in used:
                continue
            if not ctx.can_take(r.staff_id, "Đ"):
                continue
            if pos == "TD" and getattr(r, "role", "") == "TC" and placed_leader:
                night_log(ctx, f"{d.isoformat()} SKIP extra TC leader #{r.staff_id}")
                continue
            ctx.do_place(d, r.staff_id, "Đ", pos)
            used.add(r.staff_id)
            if pos == "TD":
                td_total = max(td_total - 1, 0)
                if getattr(r, "role", "") == "TC" and not placed_leader:
                    placed_leader = True
                    leader_id = r.staff_id
            elif pos == "PGD":
                pgd_total = max(pgd_total - 1, 0)
            night_log(ctx, f"{d.isoformat()} FIXED Đ@{pos} -> #{r.staff_id}")

        # jitter hàng đợi mỗi ngày (nếu bật)
        if RAND_CFG.get("daily_jitter"):
            if len(ctx.q_tc_night):
                ctx.q_tc_night.rotate(ctx.rng.randrange(len(ctx.q_tc_night)))
            if len(ctx.q_gdv1):
                ctx.q_gdv1.rotate(ctx.rng.randrange(len(ctx.q_gdv1)))
            if len(ctx.q_gdv2):
                ctx.q_gdv2.rotate(ctx.rng.randrange(len(ctx.q_gdv2)))

        night_log(ctx, f"{d.isoformat()} | need TD.D={td_total} PGD.D={pgd_total} | locked={sorted(locked_today)}")

        # ===== 1) Leader Đ @ TD (từ TC) =====
        if not placed_leader and td_total > 0:
            pool0 = [
                x
                for x in list(ctx.q_tc_night)
                if x.id not in used and x.id not in locked_today and getattr(x, "can_night", True)
            ]
            night_log(ctx, f"  leader pool0={[x.id for x in pool0]}")

            existing_leader = next(
                (
                    p.staff_id
                    for p in ctx._planned
                    if p.day == d
                    and p.shift_code == "Đ"
                    and p.position == "TD"
                    and p.staff_id in tc_ids
                ),
                None,
            )

            # Tầng 1: strict can_take
            tried: Set[int] = set()
            pool = list(pool0)
            while pool:
                idx = ctx.rng.randrange(len(pool))
                cand = pool.pop(idx)
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if existing_leader is not None:
                    night_log(
                        ctx,
                        f"LEADER_DUP {d.isoformat()} existing=#{existing_leader} try=#{cand.id}",
                    )
                    placed_leader = True
                    leader_id = existing_leader
                    break
                if ctx.can_take(cand.id, "Đ"):
                    ctx.do_place(d, cand.id, "Đ", "TD")
                    used.add(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed_leader = True
                    leader_id = cand.id
                    night_log(ctx, f"  leader placed=TC#{cand.id} (strict)")
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
                    if existing_leader is not None:
                        night_log(
                            ctx,
                            f"LEADER_DUP {d.isoformat()} existing=#{existing_leader} try=#{cand.id}",
                        )
                        placed_leader = True
                        leader_id = existing_leader
                        break
                    # không check can_take
                    ctx.do_place(d, cand.id, "Đ", "TD")
                    used.add(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed_leader = True
                    leader_id = cand.id
                    night_log(ctx, f"  leader OVERCAP=TC#{cand.id}")
                    break

            if not placed_leader:
                night_log(ctx, "  MISS leader (không đặt được TC cho Đ@TD)")
                night_miss.append(d)

        # ===== 2) Đ @ TD (non‑leader) =====
        td_remain = max(td_total - (1 if placed_leader else 0), 0)
        if td_remain > 0:
            night_log(ctx, f"  TD.D remaining={td_remain} (after leader)")
            budget = budget_for_day(d, "TD.Đ", td_remain)
            cc = ChoiceCtx(d=d, code="Đ", locked_today=locked_today, ctx=ctx, used=used)

            pool_top1 = [
                x
                for x in list(ctx.q_gdv1)
                if x.id not in used
                and getattr(x, "can_night", True)
                and getattr(x, "role", "GDV") != "TC"
            ]
            pool_top2 = [
                x
                for x in list(ctx.q_gdv2)
                if x.id not in used
                and getattr(x, "can_night", True)
                and getattr(x, "role", "GDV") != "TC"
            ]

            ids = fill_ranked_slots(need=td_remain, pool_top1=pool_top1, pool_top2=pool_top2, cc=cc, fairness=fair, position="TD", want=budget)

            placed = 0
            for sid in ids:
                if ctx.can_take(sid, "Đ"):
                    ctx.do_place(d, sid, "Đ", "TD")
                    used.add(sid)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(sid)
                    placed += 1

            remain = td_remain - placed
            if remain > 0:
                night_log(ctx, f"  TD.D short={remain}")

            got1, got2 = fair.today_for("Đ", "TD")
            win1, win2 = fair.summary("Đ", "TD")
            print(f"[FAIR] {d.isoformat()} TD.Đ want r1={budget[1]} r2={budget[2]} | got r1={got1} r2={got2} | window7 r1={win1} r2={win2}")

        # ===== 3) Đ @ PGD =====
        if pgd_total > 0:
            night_log(ctx, f"  PGD.D need={pgd_total}")
            budget = budget_for_day(d, "PGD.Đ", pgd_total)
            cc = ChoiceCtx(d=d, code="Đ", locked_today=locked_today, ctx=ctx, used=used)
            pool_top1 = [
                x
                for x in list(ctx.q_gdv1)
                if x.id not in used
                and getattr(x, "can_night", True)
                and getattr(x, "role", "GDV") != "TC"
            ]
            pool_top2 = [
                x
                for x in list(ctx.q_gdv2)
                if x.id not in used
                and getattr(x, "can_night", True)
                and getattr(x, "role", "GDV") != "TC"
            ]
            ids = fill_ranked_slots(need=pgd_total, pool_top1=pool_top1, pool_top2=pool_top2, cc=cc, fairness=fair, position="PGD", want=budget)

            placed = 0
            for sid in ids:
                if ctx.can_take(sid, "Đ"):
                    ctx.do_place(d, sid, "Đ", "PGD")
                    used.add(sid)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(sid)
                    placed += 1

            remain = pgd_total - placed
            if remain > 0:
                night_log(ctx, f"  PGD.D fallback TC remain={remain}")
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
                    night_log(ctx, f"  PGD.D short={remain}")

            got1, got2 = fair.today_for("Đ", "PGD")
            win1, win2 = fair.summary("Đ", "PGD")
            print(f"[FAIR] {d.isoformat()} PGD.Đ want r1={budget[1]} r2={budget[2]} | got r1={got1} r2={got2} | window7 r1={win1} r2={win2}")

        # ===== summary ngày
        night_log(ctx, f"summary {d.isoformat()} | leader={leader_id if placed_leader else '-'} | TD.D={td_total} | PGD.D={pgd_total}")

        if ctx.save:
            ctx.session.commit()
        d += timedelta(days=1)

    return night_miss
