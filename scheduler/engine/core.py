# backend/scheduler/core.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from typing import Any, DefaultDict, Deque, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy.orm import Session

from models import SessionLocal
from rules import get_profile
from rules.base import RuleProfile
from scheduler.placements import Planned, after_place, place
from scheduler.repo import load_fixed, load_holidays, load_locked, load_staff
from scheduler.utils import month_last_day, ymd

ShiftCode = str
Position = Optional[str]

TOLERANCE = 0.9  # lệch công cho phép


@dataclass
class Context:
    # ===== dữ liệu “quy tắc”
    profile: RuleProfile
    credits: Dict[str, float]

    # ===== nhân sự & hàng đợi
    TC: list
    GDV1: list
    GDV2: list
    HC: list

    q_tc_day: Deque[Any]
    q_tc_night: Deque[Any]
    q_gdv1: Deque[Any]
    q_gdv2: Deque[Any]
    # legacy queue (gộp) cho chỗ code cũ còn tham chiếu
    q_gdv: Deque[Any]

    # ===== ràng buộc theo ngày
    locked: Dict[date, Set[int]]  # Off/lock
    fixed: Dict[date, list]  # đăng ký cố định
    holidays: Set[date]  # ngày lễ

    # ===== quota & credit hiện tại
    base_quota: Dict[int, float]

    # ===== runtime
    rng: random.Random
    save: bool
    session: Session

    # ===== cấu hình tháng
    working_day_target: float | None = None
    shift_plan_defaults: Dict[str, int] = field(default_factory=dict)

    # ===== accumulators
    credit_map: DefaultDict[int, float] = field(default_factory=lambda: defaultdict(float))
    _planned: List[Planned] = field(default_factory=list)

    def can_take(self, staff_id: int, code: str) -> bool:
        """Không để vượt trần base_quota + TOLERANCE."""
        return (self.credit_map[staff_id] + self.credits.get(code, 0.0)) <= (
            self.base_quota.get(staff_id, 0.0) + TOLERANCE + 1e-9
        )

    def do_place(self, day: date, staff_id: int, code: str, position: Position):
        """place + cập nhật credit_map + trackers."""
        place(
            self.session,
            self._planned,
            day=day,
            staff_id=staff_id,
            code=code,
            position=position,
            save=self.save,
        )
        self.credit_map[staff_id] += self.credits.get(code, 0.0)
        after_place(staff_id, day, code)


def build_context(
    *,
    year: int,
    month: int,
    shuffle: bool,
    seed: Optional[int],
    save: bool,
    working_day_target: float | None = None,
    shift_plan_defaults: dict[str, int] | None = None,
) -> Tuple[Context, date, date]:
    """Tạo ngữ cảnh chạy cho cả tháng + trả về (first, last)."""
    first = ymd(year, month, 1)
    last = ymd(year, month, month_last_day(year, month))

    s = SessionLocal()
    profile: RuleProfile = get_profile()
    credits = profile.credit()

    # ---- load staff (4-tuple). Có fallback nếu ở đâu đó còn version 3-tuple.
    try:
        TC, GDV1, GDV2, HC = load_staff(s)  # new: đã parse rank cho GDV; TC vẫn là TC
    except ValueError:
        # Bản cũ: (TC, GDV, HC) -> suy diễn rank: thiếu thì mặc định rank=2
        TC, GDV, HC = load_staff(s)  # type: ignore[misc]
        for st in GDV:
            st.rank = getattr(st, "rank", None) or 2
        GDV1 = [st for st in GDV if int(getattr(st, "rank", 2)) == 1]
        GDV2 = [st for st in GDV if int(getattr(st, "rank", 2)) != 1]

    # Cho TC tham gia hàng đợi GDV rank-1 (để có thể bù ca như GDV khi cần)
    # Lưu ý: vai trò leader vẫn lấy từ TC queue chuyên biệt.
    gdv1_with_tc = list(GDV1) + list(TC)

    rng = random.Random(seed) if shuffle else random.Random()

    locked = load_locked(s)
    fixed = load_fixed(s)
    holidays = load_holidays(s)

    base_quota = {st.id: float(getattr(st, "base_quota", 0.0)) for st in (TC + GDV1 + GDV2 + HC)}

    ctx = Context(
        profile=profile,
        credits=credits,
        TC=TC,
        GDV1=GDV1,
        GDV2=GDV2,
        HC=HC,
        q_tc_day=deque(TC),
        q_tc_night=deque(TC),
        q_gdv1=deque(gdv1_with_tc),  # 👈 rank-1 gồm cả TC để có thể xếp như GDV khi cần
        q_gdv2=deque(GDV2),
        q_gdv=deque(GDV1 + GDV2),  # legacy (không gồm TC, chỉ để code cũ dùng tạm)
        locked=locked,
        fixed=fixed,
        holidays=holidays,
        base_quota=base_quota,
        working_day_target=working_day_target,
        shift_plan_defaults=dict(shift_plan_defaults or {}),
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
