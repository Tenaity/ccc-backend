# -*- coding: utf-8 -*-
from __future__ import annotations
import random
from collections import deque
from datetime import timedelta
from models import SessionLocal
from rules import get_profile
from .utils import ymd, month_last_day, day_kind
from .repo import load_staff, load_locked, load_fixed, load_holidays
from .placements import Planned, place, after_place, reset_trackers, exp_planned
from .randomize import choose, choose_relaxed, CFG as RAND_CFG
from .validators import validate_one_day_leader

def schedule_month(year: int, month: int, *, shuffle: bool = False, seed: int | None = None, save: bool = False):
    """
    Nếu save=False => preview (không ghi DB), trả planned[].
    Nếu save=True  => ghi DB theo tham số, vẫn trả planned[].
    """
    first = ymd(year, month, 1)
    last  = ymd(year, month, month_last_day(year, month))

    reset_trackers()
    planned: list[Planned] = []

    with SessionLocal() as s:
        TC, GDV, HC = load_staff(s)
        if not TC:
            return {"ok": False, "error": "Không có Trưởng ca (TC)."}, 400

        q_tc_day   = deque(TC)
        q_tc_night = deque(TC)
        q_gdv      = deque(GDV)
        rng = random.Random(seed) if shuffle else random.Random()

        locked   = load_locked(s)
        fixed    = load_fixed(s)
        holidays = load_holidays(s)
        profile  = get_profile()  # mặc định CSKH_2025 (có thể đổi qua ENV)

        # ===== HC ngày thường (T2–T6, trừ Lễ) =====
        d = first
        while d <= last:
            if d.weekday() < 5 and d not in holidays:
                for h in HC:
                    if h.id not in locked.get(d, set()):
                        place(s, planned, day=d, staff_id=h.id, code="HC", position="TD", save=save)
                        after_place(h.id, d, "HC")
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

            # leader Đ (Đ@TD) — nếu không có ứng viên, KHÔNG break; tiếp tục các slot khác
            if detail.leader:
                pool = [x for x in list(q_tc_night) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                if not cand:
                    cand = choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                if cand:
                    place(s, planned, day=d, staff_id=cand.id, code="Đ", position="TD", save=save)
                    used.add(cand.id); after_place(cand.id, d, "Đ")
                    locked[d + timedelta(days=1)].add(cand.id)

            # Đ trắng @ Tổng đài (D_WHITE)
            need = detail.TD_white
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_night) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                if not cand:
                    cand = choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="Đ", position="D_WHITE", save=save)
                used.add(cand.id); after_place(cand.id, d, "Đ")
                locked[d + timedelta(days=1)].add(cand.id)
                need -= 1

            # Đ @ PGD (Đ nền đỏ)
            need = detail.PGD
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_night) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                if not cand:
                    cand = choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="Đ", position="PGD", save=save)
                used.add(cand.id); after_place(cand.id, d, "Đ")
                locked[d + timedelta(days=1)].add(cand.id)
                need -= 1

            if save: s.commit()
            d += timedelta(days=1)

        # ===== PHA 2: NGÀY =====
        d = first
        while d <= last:
            used = set()
            locked_today = locked.get(d, set())
            detail = profile.day_detail(kind=day_kind(d, holidays))

            # jitter hàng đợi
            if RAND_CFG["daily_jitter"]:
                if len(q_tc_day): q_tc_day.rotate(rng.randrange(len(q_tc_day)))
                if len(q_gdv):    q_gdv.rotate(rng.randrange(len(q_gdv)))

            # fixed trước (đăng ký cố định)
            for r in fixed.get(d, []):
                if r.staff_id not in used and r.staff_id not in locked_today:
                    place(s, planned, day=d, staff_id=r.staff_id, code=r.shift_code, position="TD", save=save)
                    used.add(r.staff_id); after_place(r.staff_id, d, r.shift_code)

            # leader K @ TD
            if detail.TD.get("K_leader", 0) > 0:
                pool = [x for x in list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if not cand:
                    cand = choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if cand:
                    place(s, planned, day=d, staff_id=cand.id, code="K", position="TD", save=save)
                    used.add(cand.id); after_place(cand.id, d, "K")

            # K_WHITE (T7) — 1 người trực tại Tổng đài (thứ 7)
            kw = detail.K_WHITE
            while kw > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if not cand:
                    # Fallback "relaxed" để không bị hụt slot K trắng (vẫn tôn trọng OffDay)
                    cand = choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if not cand:
                    # Không còn ai hợp lệ -> thoát vòng; các slot khác vẫn tiếp tục
                    break
                place(s, planned, day=d, staff_id=cand.id, code="K", position="K_WHITE", save=save)
                used.add(cand.id)
                after_place(cand.id, d, "K")
                kw -= 1

            # PGD: K
            need = detail.PGD.get("K", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if not cand:
                    cand = choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="K", position="PGD", save=save)
                used.add(cand.id); after_place(cand.id, d, "K"); need -= 1

            # PGD: CA2
            need = detail.PGD.get("CA2", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="CA2", locked_today=locked_today, rng=rng)
                if not cand:
                    cand = choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="CA2", position="PGD", save=save)
                used.add(cand.id); after_place(cand.id, d, "CA2"); need -= 1

            # TD: CA1
            need = detail.TD.get("CA1", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="CA1", locked_today=locked_today, rng=rng)
                if not cand:
                    cand = choose_relaxed(pool, d=d, code="CA1", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="CA1", position="TD", save=save)
                used.add(cand.id); after_place(cand.id, d, "CA1"); need -= 1

            # TD: CA2
            need = detail.TD.get("CA2", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="CA2", locked_today=locked_today, rng=rng)
                if not cand:
                    cand = choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="CA2", position="TD", save=save)
                used.add(cand.id); after_place(cand.id, d, "CA2"); need -= 1

            if save: s.commit()
            d += timedelta(days=1)

        # Validate: đúng 1 Trưởng ca ngày / ngày
        bad = validate_one_day_leader(planned, first, last)
        if bad:
            return {
                "ok": False,
                "error": "Sai số lượng Trưởng ca ngày (K@TD)",
                "details": [{"day": d.isoformat(), "leaders": c} for d, c in bad],
                "planned": exp_planned(planned),
            }, 400

        return {"ok": True, "planned": exp_planned(planned)}