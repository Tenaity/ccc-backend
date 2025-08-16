# -*- coding: utf-8 -*-
from __future__ import annotations
import random
from collections import deque, defaultdict  # 👈 thêm defaultdict
from datetime import timedelta
from models import SessionLocal
from rules import get_profile
from .utils import ymd, month_last_day, day_kind
from .repo import load_staff, load_locked, load_fixed, load_holidays
from .placements import Planned, place, after_place, reset_trackers, exp_planned
from .randomize import choose, choose_relaxed, CFG as RAND_CFG
from .validators import validate_one_day_leader

def schedule_month(
    year: int,
    month: int,
    *,
    shuffle: bool = False,
    seed: int | None = None,
    save: bool = False,
    fill_hc: bool = False,   # 👈 NEW: bật/tắt tự bù HC
):
    """
    Nếu save=False => preview (không ghi DB), trả planned[].
    Nếu save=True  => ghi DB theo tham số, vẫn trả planned[].
    fill_hc=True  => sau khi xếp ca chính, tự bù ca HC các ngày T2–T6 (trừ ngày Lễ)
                     cho những nhân sự còn thiếu so với base_quota.
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

            # leader Đ (Đ@TD) — thiếu ứng viên thì bỏ qua, không break toàn ngày
            if detail.leader:
                pool = [x for x in list(q_tc_night) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
                if cand:
                    place(s, planned, day=d, staff_id=cand.id, code="Đ", position="TD", save=save)
                    used.add(cand.id); after_place(cand.id, d, "Đ")
                    locked[d + timedelta(days=1)].add(cand.id)

            # Đ trắng @ Tổng đài (D_WHITE)
            need = detail.TD_white
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_night) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
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
                cand = choose(pool, d=d, code="Đ", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="Đ", locked_today=locked_today, rng=rng)
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
                cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if cand:
                    place(s, planned, day=d, staff_id=cand.id, code="K", position="TD", save=save)
                    used.add(cand.id); after_place(cand.id, d, "K")

            # K_WHITE (T7) — trực tại Tổng đài (1 người nếu rule yêu cầu)
            kw = getattr(detail, "K_WHITE", 0)
            while kw > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="K", position="K_WHITE", save=save)
                used.add(cand.id); after_place(cand.id, d, "K")
                kw -= 1

            # PGD: K
            need = detail.PGD.get("K", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="K", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="K", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="K", position="PGD", save=save)
                used.add(cand.id); after_place(cand.id, d, "K")
                need -= 1

            # PGD: CA2
            need = detail.PGD.get("CA2", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="CA2", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="CA2", position="PGD", save=save)
                used.add(cand.id); after_place(cand.id, d, "CA2")
                need -= 1

            # TD: CA1
            need = detail.TD.get("CA1", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="CA1", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="CA1", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="CA1", position="TD", save=save)
                used.add(cand.id); after_place(cand.id, d, "CA1")
                need -= 1

            # TD: CA2
            need = detail.TD.get("CA2", 0)
            while need > 0:
                pool = [x for x in list(q_gdv) + list(q_tc_day) if x.id not in used and x.id not in locked_today]
                cand = choose(pool, d=d, code="CA2", locked_today=locked_today, rng=rng) or \
                       choose_relaxed(pool, d=d, code="CA2", locked_today=locked_today, rng=rng)
                if not cand:
                    break
                place(s, planned, day=d, staff_id=cand.id, code="CA2", position="TD", save=save)
                used.add(cand.id); after_place(cand.id, d, "CA2")
                need -= 1

            if save: s.commit()
            d += timedelta(days=1)

        # ====== (TÙY CHỌN) PHA 3: FILL HC CHO NGƯỜI THIẾU CÔNG ======
        if fill_hc:
            _fill_hc_makeup(s, planned, year, month, holidays, locked, save, profile)

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


# --------- helper: FILL HC ---------
def _fill_hc_makeup(s, planned, year, month, holidays, locked, save, profile):
    """
    Bù ca HC (TD) cho các nhân sự còn thiếu công so với base_quota.
    - Chỉ xếp vào T2–T6, không Lễ.
    - Không đụng vào ngày đã có ca.
    - Tôn trọng OffDay.
    - Ưu tiên người thiếu nhiều công trước.
    """
    from .repo import load_staff  # dùng lại để lấy danh sách staff mới nhất

    # 1) Tính credits hiện có theo tháng
    credit_map = defaultdict(float)
    credits = profile.credit()  # {"CA1":1, "CA2":1, "HC":1, "K":1.25, "Đ":1.5, "P":0}

    # assignments trong vòng đời generate (preview & save đều tích lũy vào planned)
    by_day_staff = defaultdict(set)  # day -> set(staff_id) đã có ca
    for p in planned:
        credit_map[p.staff_id] += credits.get(p.shift_code, 0.0)
        by_day_staff[p.day].add(p.staff_id)

    # 2) Lấy danh sách staff & quota
    TC, GDV, HC_staff = load_staff(s)
    everyone = TC + GDV + HC_staff

    # 3) Lập danh sách “deficit”
    def remaining(st):  # thiếu bao nhiêu công (>=0)
        return max(0.0, float(getattr(st, "base_quota", 0)) - credit_map.get(st.id, 0.0))

    candidates = [(st, remaining(st)) for st in everyone]
    candidates = [(st, r) for (st, r) in candidates if r > 0]  # bỏ ai quota=0 hoặc đã đủ
    # Sort: người thiếu nhiều công trước
    candidates.sort(key=lambda x: x[1], reverse=True)

    # 4) Duyệt ngày T2–T6 (không Lễ) và gán HC cho người chưa có ca & còn thiếu
    first = ymd(year, month, 1)
    last  = ymd(year, month, month_last_day(year, month))
    d = first
    while d <= last and candidates:
        if d.weekday() < 5 and d not in holidays:
            locked_today = locked.get(d, set())
            for i, (st, deficit) in enumerate(list(candidates)):
                if deficit <= 0:
                    candidates.pop(i)
                    continue
                if st.id in locked_today:
                    continue
                if st.id in by_day_staff.get(d, set()):
                    continue
                # Gán HC (TD)
                place(s, planned, day=d, staff_id=st.id, code="HC", position="TD", save=save)
                after_place(st.id, d, "HC")
                by_day_staff[d].add(st.id)
                credit_map[st.id] += credits.get("HC", 1.0)
                # cập nhật deficit
                new_def = max(0.0, float(getattr(st, "base_quota", 0)) - credit_map[st.id])
                candidates[i] = (st, new_def)
            # lọc lại ai đã đủ
            candidates = [(st, r) for (st, r) in candidates if r > 1e-9]
            if save:
                s.commit()
        d += timedelta(days=1)