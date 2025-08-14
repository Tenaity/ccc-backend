# -*- coding: utf-8 -*-
"""
Scheduler — TTCSKH (preview/save)
- Xếp Trưởng ca NGÀY trước (1 người/ngày, position="TD")
- CN/Lễ: luôn có 1 Trưởng ca NGÀY
- Ca đêm: CN/Lễ KHÔNG có trưởng ca đêm; ngày thường/T7 có 1 TC đêm
- 2 Đ nền đỏ (PGD) cho ca đêm (nếu đủ người)
- Tránh đêm liên tiếp; nghỉ bù sau đêm (lock d+1)
- Phân đều T7/CN, tránh T7→CN liên tiếp
- Tôn trọng can_night khi xếp Đ
- K_WHITE chỉ thứ 7
- Validator: mỗi ngày phải có đúng 1 Trưởng ca NGÀY (K, position="TD")
- Preview: không lưu DB, chỉ trả danh sách planned[]
"""
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import date, timedelta
import random
from typing import Optional, List, Tuple

from sqlalchemy import select

from models import SessionLocal, Staff, Assignment, OffDay, FixedAssignment, Holiday
from rules import CREDIT, ALLOWED_DELTA

# -------------------- Data structures --------------------

@dataclass
class Planned:
    day: date
    staff_id: int
    shift_code: str
    position: str | None

# -------------------- Date helpers --------------------

def ymd(y: int, m: int, d: int) -> date:
    return date(y, m, d)

def month_last_day(y: int, m: int) -> int:
    if m == 12:
        return (date(y + 1, 1, 1) - timedelta(days=1)).day
    return (date(y, m + 1, 1) - timedelta(days=1)).day

def is_sat(d: date) -> bool: return d.weekday() == 5
def is_sun(d: date) -> bool: return d.weekday() == 6

# -------------------- Loaders --------------------

def load_people(session):
    staff = session.execute(select(Staff)).scalars().all()
    TC  = [s for s in staff if s.role == "TC"]
    GDV = [s for s in staff if s.role == "GDV" and (s.notes or "").lower() != "nghỉ sinh"]
    HC  = [s for s in staff if s.role == "HC"]
    return TC, GDV, HC

def off_locks(session):
    mp = defaultdict(set)
    for r in session.query(OffDay).all():
        mp[r.day].add(r.staff_id)
    return mp

def fixed_by_day(session):
    mp = defaultdict(list)
    for r in session.query(FixedAssignment).all():
        mp[r.day].append(r)
    return mp

def holidays_set(session):
    return {r.day for r in session.query(Holiday).all()}

# -------------------- Placement --------------------

def place(session, d: date, staff_id: int, code: str, position: Optional[str],
          *, planned: list[Planned], save: bool):
    """Ghi vào planned[] luôn; nếu save=True thì thêm vào DB."""
    planned.append(Planned(day=d, staff_id=staff_id, shift_code=code, position=position))
    if save:
        session.add(Assignment(day=d, staff_id=staff_id, shift_code=code, position=position))

def rotate_randomly(q: deque, rng: random.Random):
    if len(q):
        q.rotate(rng.randrange(len(q)))

def pick_rr(qs: List[deque], used_today: set, locked_today: set, skip_fn=None):
    for q in qs:
        for _ in range(len(q)):
            cand = q[0]; q.rotate(-1)
            if cand.id in used_today or cand.id in locked_today:
                continue
            if skip_fn and skip_fn(cand):
                continue
            return cand, q
    return None, None

def pick_fair_weekend(qs: List[deque], used_today: set, locked_today: set, weekend_load, d: date, skip_fn=None):
    key = "sat" if is_sat(d) else ("sun" if is_sun(d) else None)
    if key is None:
        return pick_rr(qs, used_today, locked_today, skip_fn=skip_fn)

    best = None; bestq = None; best_load = None
    for q in qs:
        for _ in range(len(q)):
            cand = q[0]; q.rotate(-1)
            if cand.id in used_today or cand.id in locked_today:
                continue
            if skip_fn and skip_fn(cand):
                continue
            load = weekend_load[cand.id][key]
            if best is None or load < best_load:
                best, bestq, best_load = cand, q, load
    if best is None:
        return None, None
    while bestq and bestq[0].id != best.id:
        bestq.rotate(-1)
    return best, bestq

# -------------------- Validators --------------------

def validate_day_leader_from_planned(planned: list[Planned], first: date, last: date):
    by_day = defaultdict(int)
    for p in planned:
        if p.shift_code == "K" and p.position == "TD":
            by_day[p.day] += 1
    bad = []
    d = first
    while d <= last:
        if by_day.get(d, 0) != 1:
            bad.append((d, by_day.get(d, 0)))
        d += timedelta(days=1)
    return bad

# -------------------- Core --------------------

def schedule_month(year: int, month: int, *,
                   shuffle: bool = False,
                   seed: Optional[int] = None,
                   save: bool = False):
    """Nếu save=False => preview (không ghi DB), trả planned[]. Nếu save=True => ghi DB."""
    first = ymd(year, month, 1)
    last  = ymd(year, month, month_last_day(year, month))

    planned: list[Planned] = []

    with SessionLocal() as s:
        TC, GDV, HC = load_people(s)
        if not TC:
            return {"ok": False, "error": "Không có Trưởng ca (TC)."}, 400

        # Queues
        rng = random.Random(seed) if shuffle else None
        q_tc_day   = deque(TC)
        q_tc_night = deque(TC)
        q_gdv      = deque(GDV)
        if rng:
            rotate_randomly(q_tc_day, rng)
            rotate_randomly(q_tc_night, rng)
            rotate_randomly(q_gdv, rng)

        locked     = off_locks(s)           # nghỉ phép / nghỉ bù
        holidays   = holidays_set(s)
        fixed      = fixed_by_day(s)
        last_night = {}                     # staff_id -> date
        weekend_load = defaultdict(lambda: {"sat": 0, "sun": 0})

        # ====== HC FULL (T2–T6, trừ Lễ) ======
        d = first
        while d <= last:
            if (not is_sat(d)) and (not is_sun(d)) and (d not in holidays):
                for h in HC:
                    if h.id not in locked.get(d, set()):
                        place(s, d, h.id, "HC", position="TD", planned=planned, save=save)
            d += timedelta(days=1)
        if save: s.commit()

        # ====== PHA 1: ĐÊM ======
        d = first
        while d <= last:
            used = set()
            is_holiday = d in holidays
            locked_today = locked.get(d, set())

            # Nhu cầu ca đêm
            if is_sat(d):
                need_leader = 1
                need_rest   = 3
                pgd_red     = 2
            elif is_sun(d) or is_holiday:
                need_leader = 0
                need_rest   = 2
                pgd_red     = 2
            else:
                need_leader = 1
                need_rest   = 4
                pgd_red     = 2

            def avoid_sat_sun_consecutive(cand):
                if is_sun(d):
                    yday = d - timedelta(days=1)
                    return weekend_load[cand.id]["sat"] > 0 and (yday.weekday() == 5)
                return False

            def skip_night(cand):
                return (not getattr(cand, "can_night", True)) or avoid_sat_sun_consecutive(cand) \
                       or (last_night.get(cand.id) == d - timedelta(days=1))

            # Trưởng ca đêm
            cand, _ = (None, None)
            if need_leader:
                cand, _ = pick_fair_weekend([q_tc_night], used, locked_today, weekend_load, d, skip_fn=skip_night)
            if cand:
                place(s, d, cand.id, "Đ", position="TD", planned=planned, save=save)
                used.add(cand.id)
                last_night[cand.id] = d
                locked[d + timedelta(days=1)].add(cand.id)
                if is_sat(d): weekend_load[cand.id]["sat"] += 1
                if is_sun(d): weekend_load[cand.id]["sun"] += 1

            # NV đêm còn lại
            need = need_rest
            pgd_taken = 0
            while need > 0 and (len(q_gdv) + len(q_tc_night)) > 0:
                cand, _ = pick_fair_weekend([q_gdv, q_tc_night], used, locked_today, weekend_load, d, skip_fn=skip_night)
                if not cand:
                    break
                pos = "PGD" if pgd_taken < pgd_red else "TD"
                place(s, d, cand.id, "Đ", position=pos, planned=planned, save=save)
                used.add(cand.id)
                last_night[cand.id] = d
                locked[d + timedelta(days=1)].add(cand.id)
                if is_sat(d): weekend_load[cand.id]["sat"] += 1
                if is_sun(d): weekend_load[cand.id]["sun"] += 1
                if pos == "PGD": pgd_taken += 1
                need -= 1

            if save: s.commit()
            d += timedelta(days=1)

        # ====== PHA 2: NGÀY ======
        d = first
        while d <= last:
            used = set()
            locked_today = locked.get(d, set())
            is_holiday = d in holidays

            # fixed trước
            for r in fixed.get(d, []):
                if r.staff_id not in used and r.staff_id not in locked_today:
                    place(s, d, r.staff_id, r.shift_code, position="TD", planned=planned, save=save)
                    used.add(r.staff_id)

            def avoid_sat_sun_consecutive(cand):
                if is_sun(d):
                    yday = d - timedelta(days=1)
                    return weekend_load[cand.id]["sat"] > 0 and (yday.weekday() == 5)
                return False

            need_ca1, need_ca2 = (1, 1) if (is_holiday or is_sun(d)) else ((2, 2) if is_sat(d) else (2, 3))
            need_k_white = 1 if is_sat(d) else 0

            # Trưởng ca NGÀY (leader Tổng đài) — LUÔN CÓ
            leader, _ = pick_fair_weekend([q_tc_day], used, locked_today, weekend_load, d, skip_fn=avoid_sat_sun_consecutive)
            if not leader:
                leader, _ = pick_rr([q_tc_day], used, locked_today)
            if leader:
                place(s, d, leader.id, "K", position="TD", planned=planned, save=save)
                used.add(leader.id)
                if is_sat(d): weekend_load[leader.id]["sat"] += 1
                if is_sun(d): weekend_load[leader.id]["sun"] += 1

            # PGD ban ngày (trừ CN/Lễ): 1 K(PGD) + 1 CA2(PGD) + (thứ 7) 1 K_WHITE
            if not (is_sun(d) or is_holiday):
                cand_k_pgd, _ = pick_rr([q_gdv, q_tc_day], used, locked_today, skip_fn=avoid_sat_sun_consecutive)
                if cand_k_pgd:
                    place(s, d, cand_k_pgd.id, "K", position="PGD", planned=planned, save=save); used.add(cand_k_pgd.id)

                cand_ca2_pgd, _ = pick_rr([q_gdv, q_tc_day], used, locked_today, skip_fn=avoid_sat_sun_consecutive)
                if cand_ca2_pgd:
                    place(s, d, cand_ca2_pgd.id, "CA2", position="PGD", planned=planned, save=save); used.add(cand_ca2_pgd.id)

                if need_k_white:
                    cand_kw, _ = pick_fair_weekend([q_gdv, q_tc_day], used, locked_today, weekend_load, d, skip_fn=avoid_sat_sun_consecutive)
                    if cand_kw:
                        place(s, d, cand_kw.id, "K", position="K_WHITE", planned=planned, save=save); used.add(cand_kw.id)
                        weekend_load[cand_kw.id]["sat"] += 1

            # Tổng đài CA1/CA2
            pools = [q_gdv, q_tc_day]
            while need_ca1 > 0:
                cand, _ = pick_fair_weekend(pools, used, locked_today, weekend_load, d, skip_fn=avoid_sat_sun_consecutive)
                if not cand: break
                place(s, d, cand.id, "CA1", position="TD", planned=planned, save=save); used.add(cand.id); need_ca1 -= 1
                if is_sat(d): weekend_load[cand.id]["sat"] += 1
                if is_sun(d): weekend_load[cand.id]["sun"] += 1

            while need_ca2 > 0:
                cand, _ = pick_fair_weekend(pools, used, locked_today, weekend_load, d, skip_fn=avoid_sat_sun_consecutive)
                if not cand: break
                place(s, d, cand.id, "CA2", position="TD", planned=planned, save=save); used.add(cand.id); need_ca2 -= 1
                if is_sat(d): weekend_load[cand.id]["sat"] += 1
                if is_sun(d): weekend_load[cand.id]["sun"] += 1

            if save: s.commit()
            d += timedelta(days=1)

        # ====== VALIDATE trên planned ======
        bad_days = validate_day_leader_from_planned(planned, first, last)
        if bad_days:
            return {
                "ok": False,
                "error": "Sai số lượng Trưởng ca ngày",
                "details": [{"day": d.isoformat(), "leaders": c} for (d, c) in bad_days],
                "planned": [asdict(p) | {"day": p.day.isoformat()} for p in planned],
            }, 400

        return {
            "ok": True,
            "planned": [asdict(p) | {"day": p.day.isoformat()} for p in planned]
        }

# Adapter giữ API cũ (app.py gọi generate_schedule)
def generate_schedule(year: int, month: int, *, shuffle: bool = False, seed: int | None = None, save: bool = False):
    return schedule_month(year, month, shuffle=shuffle, seed=seed, save=save)
