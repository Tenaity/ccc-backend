# backend/scheduler/core.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, DefaultDict, Dict, List, Set, Tuple, Deque
import random
from collections import deque, defaultdict
from datetime import date
from sqlalchemy.orm import Session

from models import SessionLocal
from rules import get_profile
from rules.base import RuleProfile
from scheduler.utils import ymd, month_last_day
from scheduler.repo import load_staff, load_locked, load_fixed, load_holidays
from scheduler.placements import place, after_place, Planned

ShiftCode = str
Position = str | None

TOLERANCE = 0.9  # lệch công cho phép


@dataclass
class Context:
    # ===== dữ liệu “quy tắc”
    profile: RuleProfile
    credits: Dict[str, float]

    # ===== nhân sự & hàng đợi
    TC: list
    GDV: list
    HC: list
    q_tc_day: Deque[Any]
    q_tc_night: Deque[Any]
    q_gdv: Deque[Any]

    # ===== ràng buộc theo ngày
    locked: Dict[date, Set[int]]     # Off/lock
    fixed: Dict[date, list]          # đăng ký cố định (FixedAssignment)
    holidays: Set[date]              # ngày lễ

    # ===== quota & credit hiện tại trong phiên phát lịch
    base_quota: Dict[int, float]

    # ===== runtime (KHÔNG default -> phải đứng TRƯỚC các field có default)
    rng: random.Random
    save: bool
    session: Session

    # ===== fields có default (đặt sau)
    credit_map: DefaultDict[int, float] = field(default_factory=lambda: defaultdict(float))
    _planned: List[Planned] = field(default_factory=list)

    def can_take(self, staff_id: int, code: str) -> bool:
        """Không để vượt trần base_quota + TOLERANCE."""
        return (self.credit_map[staff_id] + self.credits.get(code, 0.0)) <= \
               (self.base_quota.get(staff_id, 0.0) + TOLERANCE + 1e-9)

    def do_place(self, day: date, staff_id: int, code: str, position: Position):
        """place + cập nhật credit_map + trackers."""
        place(self.session, self._planned, day=day, staff_id=staff_id, code=code, position=position, save=self.save)
        self.credit_map[staff_id] += self.credits.get(code, 0.0)
        after_place(staff_id, day, code)


def build_context(*, year: int, month: int, shuffle: bool, seed: int | None, save: bool) -> Tuple[Context, date, date]:
    """Tạo ngữ cảnh chạy cho cả tháng + trả về (first, last)."""
    first = ymd(year, month, 1)
    last  = ymd(year, month, month_last_day(year, month))

    s = SessionLocal()

    # load nhân sự
    TC, GDV, HC = load_staff(s)
    profile: RuleProfile = get_profile()
    credits = profile.credit()

    rng = random.Random(seed) if shuffle else random.Random()

    locked   = load_locked(s)
    fixed    = load_fixed(s)
    holidays = load_holidays(s)

    base_quota = {st.id: float(getattr(st, "base_quota", 0.0)) for st in (TC + GDV + HC)}

    ctx = Context(
        profile=profile,
        credits=credits,
        TC=TC, GDV=GDV, HC=HC,
        q_tc_day=deque(TC),
        q_tc_night=deque(TC),
        q_gdv=deque(GDV),
        locked=locked,
        fixed=fixed,
        holidays=holidays,
        base_quota=base_quota,
        rng=rng,
        save=save,
        session=s,
    )
    return ctx, first, last


def close_context(ctx: Context):
    try:
        ctx.session.close()
    except Exception:
        pass