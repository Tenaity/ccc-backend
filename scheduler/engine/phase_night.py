# engine/phase_night.py
from __future__ import annotations
from typing import List, Set
from datetime import date, timedelta
from .core import Context
from scheduler.utils import day_kind
from scheduler.randomize import choose, choose_relaxed, CFG as RAND_CFG

# Cho phép “cứu cháy” leader đêm: bỏ rào trần công nếu cần thiết
ALLOW_OVERCAP_NIGHT_LEADER = True

def _log(ctx: Context, msg: str):
    print(f"[NIGHT] {msg}")

def run_phase_night(ctx: Context, first: date, last: date) -> List[date]:
    """
    Trả về danh sách ngày KHÔNG gán được trưởng ca đêm (Đ@TD)
    (chỉ những ngày profile.night_detail(...).leader > 0)
    """
    night_miss: List[date] = []

    d = first
    while d <= last:
        used: Set[int] = set()
        locked_today = ctx.locked.get(d, set())
        detail = ctx.profile.night_detail(kind=day_kind(d, ctx.holidays))

        # jitter hàng đợi
        if RAND_CFG["daily_jitter"]:
            if len(ctx.q_tc_night):
                ctx.q_tc_night.rotate(ctx.rng.randrange(len(ctx.q_tc_night)))
            if len(ctx.q_gdv):
                ctx.q_gdv.rotate(ctx.rng.randrange(len(ctx.q_gdv)))

        # ==== 1) Trưởng ca đêm (Đ@TD) ====
        placed_leader = False
        if detail.leader:  # chỉ ngày cần leader
            # POOL ban đầu: chỉ TC có thể trực đêm, không bị lock hôm nay, chưa dùng
            pool0 = [x for x in list(ctx.q_tc_night)
                     if x.id not in used
                     and x.id not in locked_today
                     and getattr(x, "can_night", True)]

            # --- Tầng 1: chọn “chuẩn”
            tried: Set[int] = set()
            pool = list(pool0)
            while pool:
                cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "Đ"):
                    ctx.do_place(d, cand.id, "Đ", "TD")
                    used.add(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)  # khóa ngày kế
                    placed_leader = True
                    break
                # loại ứng viên vượt trần rồi thử tiếp
                pool = [x for x in pool if x.id != cand.id]

            # --- Tầng 2: relaxed (nới khoảng cách đêm)
            if not placed_leader and pool0:
                tried = set()
                pool = list(pool0)
                while pool:
                    cand = choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                    if not cand:
                        break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if ctx.can_take(cand.id, "Đ"):
                        ctx.do_place(d, cand.id, "Đ", "TD")
                        used.add(cand.id)
                        ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                        placed_leader = True
                        break
                    pool = [x for x in pool if x.id != cand.id]

            # --- Tầng 3: last resort (nếu bật) — bỏ rào trần công
            if not placed_leader and ALLOW_OVERCAP_NIGHT_LEADER and pool0:
                # vẫn tôn trọng lock/can_night; KHÔNG check can_take
                tried = set()
                pool = list(pool0)
                while pool:
                    # chọn ai “ít tệ” nhất theo relaxed
                    cand = choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                    if not cand:
                        break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)

                    ctx.do_place(d, cand.id, "Đ", "TD")
                    used.add(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed_leader = True
                    _log(ctx, f"OVERCAP leader at {d.isoformat()} -> TC#{cand.id} (forced to avoid miss)")
                    break

            # Nếu vẫn không xếp được leader, log đầy đủ rồi đánh dấu miss
            if not placed_leader:
                # phân tích lý do
                reasons = []
                if not pool0:
                    reasons.append("pool0=∅ (TC không ai can_night hoặc tất cả bị lock/dùng)")
                else:
                    # có pool nhưng toàn bị rào trần?
                    overcap_ids = [x.id for x in pool0 if not ctx.can_take(x.id, 'Đ')]
                    if overcap_ids and len(overcap_ids) == len(pool0):
                        reasons.append("tất cả ứng viên vượt trần công")
                _log(ctx, f"MISS leader at {d.isoformat()} | pool0={ [x.id for x in pool0] } | reasons={'; '.join(reasons) or 'unknown'}")
                night_miss.append(d)

        # ==== 2) Đ trắng @ Tổng đài (D_WHITE) ====
        need = detail.TD_white
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_night)
                    if x.id not in used and x.id not in locked_today and getattr(x, "can_night", True)]
            if not pool:
                _log(ctx, f"D_WHITE short at {d.isoformat()} (pool empty)")
                break
            placed = False
            tried = set()
            while pool:
                cand = (choose(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng))
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "Đ"):
                    ctx.do_place(d, cand.id, "Đ", "D_WHITE")
                    used.add(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed = True
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, f"D_WHITE short at {d.isoformat()} (can_take blocked)")
                break
            need -= 1

        # ==== 3) Đ @ PGD ====
        need = detail.PGD
        while need > 0:
            pool = [x for x in list(ctx.q_gdv) + list(ctx.q_tc_night)
                    if x.id not in used and x.id not in locked_today and getattr(x, "can_night", True)]
            if not pool:
                _log(ctx, f"NIGHT PGD short at {d.isoformat()} (pool empty)")
                break
            placed = False
            tried = set()
            while pool:
                cand = (choose(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng)
                        or choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=ctx.rng))
                if not cand:
                    break
                if cand.id in tried:
                    break
                tried.add(cand.id)
                if ctx.can_take(cand.id, "Đ"):
                    ctx.do_place(d, cand.id, "Đ", "PGD")
                    used.add(cand.id)
                    ctx.locked.setdefault(d + timedelta(days=1), set()).add(cand.id)
                    placed = True
                    break
                pool = [x for x in pool if x.id != cand.id]
            if not placed:
                _log(ctx, f"NIGHT PGD short at {d.isoformat()} (can_take blocked)")
                break
            need -= 1

        if ctx.save:
            ctx.session.commit()
        d = d + timedelta(days=1)

    return night_miss