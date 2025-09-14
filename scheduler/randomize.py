# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import random
from datetime import date

from .placements import trackers

CFG = {
    "daily_jitter": True,
    "epsilon": 0.08,
    "top_k": 3,
    "temperature": 0.7,
    "w_last_night_gap": 2.0,
    "w_weekend_balance": 1.2,
    "w_credit_balance": 1.0,
    "w_recent_day_gap": 0.6,
    "night_lock_penalty": 1e6,
}


def _days_gap(prev: date | None, cur: date) -> int:
    return 999 if prev is None else (cur - prev).days


def _score(cand, *, d: date, code: str, is_weekend: bool, locked_today: set[int]):
    _last_night, _last_day, _credit, _weekend = trackers()

    # hard locks
    if cand.id in locked_today:
        return CFG["night_lock_penalty"]

    if code == "Đ":
        if not getattr(cand, "can_night", True):
            return CFG["night_lock_penalty"]
        # cấm 2 đêm liên tiếp trong chế độ "chuẩn"
        if _days_gap(_last_night.get(cand.id), d) <= 1:
            return CFG["night_lock_penalty"]

    gap_n = _days_gap(_last_night.get(cand.id), d) if code == "Đ" else 0

    # ⚠️ tách biến để type checker không phàn nàn
    prev_day = _last_day.get(cand.id)
    gap_d = _days_gap(prev_day, d) if code != "Đ" else 0

    credit = _credit.get(cand.id, 0.0)

    wk_term = 0
    if is_weekend:
        wk = _weekend.get(cand.id) or {}
        wk_term = wk.get("sat" if d.weekday() == 5 else "sun", 0)

    # nhỏ tốt
    return (
        -CFG["w_last_night_gap"] * gap_n
        - CFG["w_recent_day_gap"] * gap_d
        + CFG["w_credit_balance"] * credit
        + CFG["w_weekend_balance"] * wk_term
    )


# ---- softmax ổn định số học (subtract-the-max) ----
def _softmax_choice(scored, rng: random.Random):
    if not scored:
        return None
    scored.sort(key=lambda x: x[1])  # score nhỏ tốt
    pool = scored[: max(1, CFG["top_k"])]

    # ε-greedy trong top-k
    if rng.random() < CFG["epsilon"] and len(pool) > 1:
        return rng.choice(pool)[0]

    # Softmax ổn định: exp(z - zmax), với z = -score/T
    T = max(1e-6, CFG["temperature"])
    zs = [(-s) / T for _, s in pool]
    zmax = max(zs)
    weights = [math.exp(z - zmax) for z in zs]
    ssum = sum(weights)

    if not math.isfinite(ssum) or ssum <= 0.0:
        return pool[0][0]  # fallback: chọn tốt nhất

    r = rng.random() * ssum
    cum = 0.0
    for (cand, _), w in zip(pool, weights):
        cum += w
        if r <= cum:
            return cand
    return pool[-1][0]


def choose(cands, *, d: date, code: str, locked_today: set[int], rng: random.Random):
    is_weekend = d.weekday() >= 5
    scored = [
        (c, _score(c, d=d, code=code, is_weekend=is_weekend, locked_today=locked_today))
        for c in cands
    ]
    # loại các ứng viên bị phạt "vô cực" (lock)
    scored = [(c, s) for (c, s) in scored if s < CFG["night_lock_penalty"]]
    return _softmax_choice(scored, rng) if scored else None


def choose_relaxed(cands, *, d: date, code: str, locked_today: set[int], rng: random.Random):
    """
    Fallback: khi pool chuẩn rỗng.
    - Vẫn tôn trọng: locked_today (OffDay) & can_night (nếu code == "Đ")
    - Thư giãn: cho phép 2 đêm liên tiếp nếu bắt buộc để đủ slot
    """
    _last_night, _last_day, _credit, _weekend = trackers()

    # lọc tối thiểu
    pool = []
    for x in cands:
        if x.id in locked_today:
            continue
        if code == "Đ" and not getattr(x, "can_night", True):
            continue
        pool.append(x)

    if not pool:
        return None

    # chấm điểm "thư giãn": KHÔNG phạt consecutive night
    def relaxed_score(cand):
        prev_day = _last_day.get(cand.id)
        gap_d = _days_gap(prev_day, d)  # an toàn kiểu
        credit = _credit.get(cand.id, 0.0)
        wk_term = 0
        if d.weekday() >= 5:
            wk = _weekend.get(cand.id) or {}
            wk_term = wk.get("sat" if d.weekday() == 5 else "sun", 0)
        return (
            -CFG["w_recent_day_gap"] * gap_d
            + CFG["w_credit_balance"] * credit
            + CFG["w_weekend_balance"] * wk_term
        )

    scored = [(c, relaxed_score(c)) for c in pool]
    return _softmax_choice(scored, rng) if scored else None
