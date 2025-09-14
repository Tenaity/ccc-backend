# backend/scheduler/placements.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple, cast

# Chỉ dùng Session làm type hint (không phụ thuộc model riêng nào)
from sqlalchemy.orm import Session

from models import Assignment
from rules import CREDIT as RULE_CREDIT


# ====== Kiểu dữ liệu tạm trong một lần generate ======
@dataclass
class Planned:
    day: date
    staff_id: int
    shift_code: str  # "CA1" | "CA2" | "K" | "HC" | "Đ" | "P"
    position: Optional[str]  # "TD" | "PGD" | "K_WHITE" | "D_WHITE" | None


# ====== Trackers runtime (chỉ sống trong 1 phiên generate) ======
_last_night: Dict[int, date] = {}
_last_day: Dict[int, date] = {}
_credit: Dict[int, float] = {}
_weekend: Dict[int, Dict[str, int]] = {}  # {"sat": n, "sun": n}

# optional hook for fairness window
_fair_hook = None

# Ép kiểu rõ ràng để Pylance không báo lỗi khi .get(...)
CREDIT: Dict[str, float] = cast(Dict[str, float], RULE_CREDIT)


def reset_trackers() -> None:
    """Xoá trạng thái phiên trước khi bắt đầu generate mới."""
    _last_night.clear()
    _last_day.clear()
    _credit.clear()
    _weekend.clear()


def credit_of(code: str) -> float:
    """Trả về trọng số công của mã ca."""
    return float(CREDIT.get(code, 0.0))


def set_fairness_hook(hook) -> None:
    """Set callback invoked on every placement."""
    global _fair_hook
    _fair_hook = hook


def place(
    session: Optional[Session],
    planned: List[Planned],
    *,
    day: date,
    staff_id: int,
    code: str,
    position: Optional[str],
    save: bool,
) -> None:
    """
    Ghi 1 ô phân ca vào bộ nhớ (và DB nếu save=True).
      - session: SQLAlchemy Session hiện tại (Context.session)
      - planned: danh sách Planned tạm để trả về/đối chiếu
    """
    rec = Planned(day=day, staff_id=staff_id, shift_code=code, position=position)
    planned.append(rec)

    if _fair_hook is not None:
        try:
            _fair_hook(staff_id, code, position)
        except Exception:
            pass

    if save and session is not None:
        session.add(Assignment(day=day, staff_id=staff_id, shift_code=code, position=position))


def after_place(staff_id: int, d: date, code: str) -> None:
    """
    Cập nhật trackers sau khi place:
      - tổng công quy đổi (_credit)
      - lần gần nhất làm đêm/ngày
      - đếm số thứ 7/CN đã làm (cho các rule phân phối nếu cần)
    """
    _credit[staff_id] = _credit.get(staff_id, 0.0) + credit_of(code)

    if code == "Đ":
        _last_night[staff_id] = d
        return

    _last_day[staff_id] = d
    wd = d.weekday()  # 0=Mon..6=Sun
    if staff_id not in _weekend:
        _weekend[staff_id] = {"sat": 0, "sun": 0}
    if wd == 5:
        _weekend[staff_id]["sat"] += 1
    elif wd == 6:
        _weekend[staff_id]["sun"] += 1


def exp_planned(planned: List[Planned]) -> List[dict]:
    """Xuất planned ra list[dict] (day -> ISO) cho API/debug."""
    return [asdict(p) | {"day": p.day.isoformat()} for p in planned]


def trackers() -> (
    Tuple[Dict[int, date], Dict[int, date], Dict[int, float], Dict[int, Dict[str, int]]]
):
    """
    Cho randomize/engine mượn các tracker nội bộ khi cần:
      - _last_night: id -> ngày gần nhất làm Đ
      - _last_day:   id -> ngày gần nhất làm ngày
      - _credit:     id -> tổng công quy đổi đã đặt
      - _weekend:    id -> {"sat": n, "sun": n}
    """
    return _last_night, _last_day, _credit, _weekend
