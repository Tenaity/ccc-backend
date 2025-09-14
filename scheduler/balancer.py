# backend/scheduler/balancer.py
from __future__ import annotations

import calendar
import heapq
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Set, Tuple

Placement = Tuple[date, int, str, str]  # (day, staff_id, shift_code, position)


class StaffLike(Protocol):
    id: int
    base_quota: float


@dataclass(frozen=True)
class HCPlacement:
    day: date
    staff_id: int


def _days_in_month(year: int, month: int) -> List[date]:
    last = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, last + 1)]


def balance_hc(
    *,
    planned: Optional[Iterable[Tuple[date, int, str, Optional[str]]]] = None,
    staff: Sequence[StaffLike],
    holidays: Set[date],
    year: int,
    month: int,
    credits: Dict[str, float],
    tolerance: float,
    locked_by_day: Dict[date, Set[int]],
) -> List[Placement]:
    """
    Cân bằng HC sau khi đã có planned:
      - planned: các ca đã xếp (day, staff_id, code, position|None)
      - staff: danh sách nhân sự có .id, .base_quota
      - locked_by_day: ngày -> set(staff_id) bị khoá/không được gán thêm
      - credits: bảng điểm công theo mã ca, dùng "HC": 1.0
      - tolerance: cho phép thiếu/dư trong [-tolerance, +tolerance]
    Kết quả: danh sách đề xuất (day, staff_id, "HC", "TD")
    """
    EPS = 1e-9
    credit_hc = credits.get("HC", 1.0)
    days = _days_in_month(year, month)

    # 1) base_quota & current_credit
    base_quota: Dict[int, float] = {int(s.id): float(getattr(s, "base_quota", 0.0)) for s in staff}
    current_credit: Dict[int, float] = {sid: 0.0 for sid in base_quota.keys()}

    # ai đã có ca trong ngày (để tránh xếp thêm HC)
    taken_today: Dict[date, Set[int]] = {d: set() for d in days}

    # clone locked map để có thể bơm thêm constraint
    locked2: Dict[date, Set[int]] = {d: set(v) for d, v in locked_by_day.items()}

    if planned:
        for d, sid, code, _pos in planned:
            if d.year == year and d.month == month:
                # cộng công đã xếp
                current_credit[sid] = current_credit.get(sid, 0.0) + float(credits.get(code, 0.0))
                taken_today.setdefault(d, set()).add(sid)
                # tự khóa ngày kế sau ca Đ (an toàn, nếu engine chưa làm)
                if code == "Đ":
                    locked2.setdefault(d + timedelta(days=1), set()).add(sid)

    # 2) can_work: ngày -> những ai đủ điều kiện nhận thêm 1 HC (không locked, chưa có ca)
    can_work: Dict[date, Set[int]] = {}
    for d in days:
        locked = locked2.get(d, set())
        can_work[d] = {
            sid
            for sid in base_quota.keys()
            if sid not in locked and sid not in taken_today.get(d, set())
        }

    # 3) heap theo deficit (max-heap bằng cách đẩy âm vào heapq)
    def deficit_of(sid: int) -> float:
        return base_quota.get(sid, 0.0) - current_credit.get(sid, 0.0)

    heap: List[Tuple[float, int]] = []
    for sid in base_quota.keys():
        d0 = deficit_of(sid)
        if d0 > tolerance + EPS:
            heapq.heappush(heap, (-d0, sid))

    out: List[Placement] = []

    # 4) duyệt từng ngày T2–T6, tránh ngày Lễ, bơm 1 HC cho những người thiếu nhiều nhất
    for d in days:
        if d.weekday() >= 5:
            continue
        if d in holidays:
            continue
        if not heap:
            break

        avail = set(can_work.get(d, set()))
        if not avail:
            continue

        used_today: Set[int] = set()
        postpone: List[Tuple[float, int]] = []

        while heap and len(used_today) < len(avail):
            neg_def, sid = heapq.heappop(heap)
            def_before = -neg_def

            if sid not in avail or sid in used_today:
                postpone.append((-def_before, sid))
                continue

            # sau khi cộng 1 HC, deficit' = def_before - 1; phải giữ >= -tolerance
            if (def_before - credit_hc) < -tolerance - EPS:
                # đã chạm biên dưới -> không push lại (đã đủ/khá đủ)
                continue

            # gán 1 HC
            out.append((d, sid, "HC", "TD"))
            current_credit[sid] = current_credit.get(sid, 0.0) + credit_hc
            used_today.add(sid)
            taken_today.setdefault(d, set()).add(sid)  # cập nhật ngay để ngày này không trùng ca

            new_def = deficit_of(sid)
            if new_def > tolerance + EPS:
                heapq.heappush(heap, (-new_def, sid))

        # đẩy lại các phần tử hoãn
        for item in postpone:
            heapq.heappush(heap, item)

    return out
