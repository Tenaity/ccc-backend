# -*- coding: utf-8 -*-
from __future__ import annotations
import random
from collections import deque, defaultdict
from datetime import timedelta
from models import SessionLocal
from rules import get_profile
from .utils import ymd, month_last_day, day_kind
from .repo import load_staff, load_locked, load_fixed, load_holidays
from .placements import Planned, place, after_place, reset_trackers, exp_planned
from .randomize import choose, choose_relaxed, CFG as RAND_CFG
from .validators import validate_one_day_leader
from .balancer import balance_hc  # 👈 NEW

# DUNG SAI công cho mỗi người: cho phép thiếu/dư tối đa 0.9 công
TOLERANCE = 0.9

def schedule_month(year: int, month: int, *, shuffle: bool = False, seed: int | None = None, save: bool = False, fill_hc: bool = False):

    first = ymd(year, month, 1)
    last  = ymd(year, month, month_last_day(year, month))

    reset_trackers()
    planned: list[Planned] = []

    with SessionLocal() as s:
        TC, GDV, HC = load_staff(s)
        if not TC:
            return {"ok": False, "error": "Không có Trưởng ca (TC)."}, 400

        # === NEW: bản đồ quota & credit hiện tại (tính trong vòng generate) ===
        profile  = get_profile()
        CREDITS = profile.credit()  # {"CA1":1, "CA2":1, "HC":1, "K":1.25, "Đ":1.5, "P":0}
        base_quota = {st.id: float(getattr(st, "base_quota", 0.0)) for st in (TC + GDV + HC)}
        credit_map = defaultdict(float)   # staff_id -> credits đã xếp trong planned

        def can_take(staff_id: int, code: str) -> bool:
            """Không để vượt trần base_quota + TOLERANCE."""
            return (credit_map[staff_id] + CREDITS.get(code, 0.0)) <= (base_quota.get(staff_id, 0.0) + TOLERANCE + 1e-9)

        def do_place(day, staff_id: int, code: str, position: str | None):
            """place + cập nhật credit_map + trackers."""
            place(s, planned, day=day, staff_id=staff_id, code=code, position=position, save=save)
            credit_map[staff_id] += CREDITS.get(code, 0.0)
            after_place(staff_id, day, code)

        # === hàng đợi chọn ngẫu nhiên ===
        q_tc_day   = deque(TC)
        q_tc_night = deque(TC)
        q_gdv      = deque(GDV)
        rng = random.Random(seed) if shuffle else random.Random()

        locked   = load_locked(s)
        fixed    = load_fixed(s)
        holidays = load_holidays(s)

        # ===== HC ngày thường (T2–T6, trừ Lễ) =====
        d = first
        while d <= last:
            if d.weekday() < 5 and d not in holidays:
                for h in HC:
                    if h.id in locked.get(d, set()):
                        continue
                    # NEW: chặn trần khi rải HC mặc định
                    if not can_take(h.id, "HC"):
                        continue
                    do_place(d, h.id, "HC", "TD")
            d += timedelta(days=1)
        if save: s.commit()

        # ===== PHA 1: ĐÊM =====
        d = first
        while d <= last:
            used = set()
            locked_today = locked.get(d, set())
            detail = profile.night_detail(kind=day_kind(d, holidays))

            # jitter hàng đợi
            if RAND_CFG["daily_jitter"]:
                if len(q_tc_night): q_tc_night.rotate(rng.randrange(len(q_tc_night)))
                if len(q_gdv):      q_gdv.rotate(rng.randrange(len(q_gdv)))

            # leader Đ (Đ@TD)
            if detail.leader:
                pool = [x for x in list(q_tc_night) if x.id not in used and x.id not in locked_today]
                # thử chọn đến khi gặp người không vượt trần
                tried = set()
                while pool:
                    cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "Đ"):
                        do_place(d, cand.id, "Đ", "TD")
                        used.add(cand.id)
                        locked[d + timedelta(days=1)].add(cand.id)
                        break
                    # bỏ ứng viên vượt trần khỏi pool và thử lại
                    pool = [x for x in pool if x.id != cand.id]

            # Đ trắng @ Tổng đài (D_WHITE)
            need = detail.TD_white
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_night) if x.id not in used and x.id not in locked_today]
                tried = set()
                placed = False
                while pool:
                    cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "Đ"):
                        do_place(d, cand.id, "Đ", "D_WHITE")
                        used.add(cand.id)
                        locked[d + timedelta(days=1)].add(cand.id)
                        placed = True
                        break
                    pool = [x for x in pool if x.id != cand.id]
                if not placed:
                    break
                need -= 1

            # Đ @ PGD
            need = detail.PGD
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_night) if x.id not in used and x.id not in locked_today]
                tried = set()
                placed = False
                while pool:
                    cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "Đ"):
                        do_place(d, cand.id, "Đ", "PGD")
                        used.add(cand.id)
                        locked[d + timedelta(days=1)].add(cand.id)
                        placed = True
                        break
                    pool = [x for x in pool if x.id != cand.id]
                if not placed:
                    break
                need -= 1

            if save: s.commit()
            d += timedelta(days=1)

        # ===== PHA 2: NGÀY =====
        d = first
        while d <= last:
            used = set()
            locked_today = locked.get(d, set())
            detail = profile.day_detail(kind=day_kind(d, holidays))

            if RAND_CFG["daily_jitter"]:
                if len(q_tc_day): q_tc_day.rotate(rng.randrange(len(q_tc_day)))
                if len(q_gdv):    q_gdv.rotate(rng.randrange(len(q_gdv)))

            # fixed trước (đăng ký cố định)
            for r in fixed.get(d, []):
                if r.staff_id in used or r.staff_id in locked_today:
                    continue
                if not can_take(r.staff_id, r.shift_code):
                    continue
                do_place(d, r.staff_id, r.shift_code, "TD")
                used.add(r.staff_id)

            # leader K @ TD
            if detail.TD.get("K_leader", 0) > 0:
                pool = [x for x in list(q_tc_day) if x.id not in used and x.id not in locked_today]
                tried = set()
                while pool:
                    cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "K"):
                        do_place(d, cand.id, "K", "TD")
                        used.add(cand.id)
                        break
                    pool = [x for x in pool if x.id != cand.id]

            # K_WHITE (T7)
            kw = getattr(detail, "K_WHITE", 0)
            while kw > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                tried = set()
                placed = False
                while pool:
                    cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "K"):
                        do_place(d, cand.id, "K", "K_WHITE")
                        used.add(cand.id)
                        placed = True
                        break
                    pool = [x for x in pool if x.id != cand.id]
                if not placed:
                    break
                kw -= 1

            # PGD: K
            need = detail.PGD.get("K", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                tried = set()
                placed = False
                while pool:
                    cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "K"):
                        do_place(d, cand.id, "K", "PGD")
                        used.add(cand.id)
                        placed = True
                        break
                    pool = [x for x in pool if x.id != cand.id]
                if not placed:
                    break
                need -= 1

            # PGD: CA2
            need = detail.PGD.get("CA2", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                tried = set()
                placed = False
                while pool:
                    cand = choose(pool, d=d, code="CA2", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "CA2"):
                        do_place(d, cand.id, "CA2", "PGD")
                        used.add(cand.id)
                        placed = True
                        break
                    pool = [x for x in pool if x.id != cand.id]
                if not placed:
                    break
                need -= 1

            # TD: CA1
            need = detail.TD.get("CA1", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                tried = set()
                placed = False
                while pool:
                    cand = choose(pool, d=d, code="CA1", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="CA1", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "CA1"):
                        do_place(d, cand.id, "CA1", "TD")
                        used.add(cand.id)
                        placed = True
                        break
                    pool = [x for x in pool if x.id != cand.id]
                if not placed:
                    break
                need -= 1

            # TD: CA2
            need = detail.TD.get("CA2", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                tried = set()
                placed = False
                while pool:
                    cand = choose(pool, d=d, code="CA2", locked_today=locked_today, rng=rng) or \
                           choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=rng)
                    if not cand: break
                    if cand.id in tried:
                        break
                    tried.add(cand.id)
                    if can_take(cand.id, "CA2"):
                        do_place(d, cand.id, "CA2", "TD")
                        used.add(cand.id)
                        placed = True
                        break
                    pool = [x for x in pool if x.id != cand.id]
                if not placed:
                    break
                need -= 1

            if save: s.commit()
            d += timedelta(days=1)

        # ====== (TÙY CHỌN) PHA 3: FILL HC CHO NGƯỜI THIẾU CÔNG ======
        if fill_hc:
            # Prepare normalized 'planned' for balancer (day, staff_id, code, position)
            normalized_planned = [(p.day, p.staff_id, p.shift_code, p.position) for p in planned]

            # Rebuild 'everyone' and locked map (already loaded above)
            TC, GDV, HC_staff = load_staff(s)
            everyone = TC + GDV + HC_staff

            proposals = balance_hc(
                planned=normalized_planned,
                staff=everyone,
                holidays=holidays,
                year=year,
                month=month,
                credits=profile.credit(),
                tolerance=TOLERANCE,        # 0.9
                locked_by_day=locked,
            )
            # Test check
            if proposals:
                # tính tổng công mới sau khi bơm
                hc_credit = CREDITS.get("HC", 1.0)
                final_credit = defaultdict(float, credit_map)
                for d, sid, code, _pos in proposals:
                    final_credit[sid] += hc_credit

                # ai còn > tolerance?
                leftovers = [
                    (sid, base_quota.get(sid, 0.0) - final_credit.get(sid, 0.0))
                    for sid in base_quota.keys()
                ]
                still_high = [(sid, round(defc, 2)) for sid, defc in leftovers if defc > TOLERANCE + 1e-9]
                if still_high:
                    print("[BALANCER] Không thể bù hết do thiếu ngày hợp lệ:", still_high[:10], "…")

            # Apply proposals
            for d, staff_id, shift_code, position in proposals:
                place(s, planned, day=d, staff_id=staff_id, code=shift_code, position=position, save=save)
                # intentionally no after_place() — this is the final pass

            if save:
                s.commit()

        # Validate…
        bad = validate_one_day_leader(planned, first, last)
        if bad:
            return {
                "ok": False,
                "error": "Sai số lượng Trưởng ca ngày (K@TD)",
                "details": [{"day": d.isoformat(), "leaders": c} for d, c in bad],
                "planned": exp_planned(planned),
            }, 400

        return {"ok": True, "planned": exp_planned(planned)}