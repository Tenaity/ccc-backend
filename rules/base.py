# backend/rules/base.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from .types import ShiftCode, Position, DayKind, CREDITS

# UI/REST vẫn dùng các mã ca dạng string
SHIFT_DEFS = [
    ShiftCode.CA1.value,
    ShiftCode.CA2.value,
    ShiftCode.K.value,
    ShiftCode.HC.value,
    ShiftCode.D.value,
    ShiftCode.P.value,
]

# ---- Kiểu cho phần ngày ----
DayTD  = Dict[str, int]            # keys: "K_leader", "CA1", "CA2"
DayPGD = Dict[ShiftCode, int]      # keys: ShiftCode.K, ShiftCode.CA2

@dataclass(frozen=True)
class DayDetail:
    TD: DayTD
    PGD: DayPGD
    K_WHITE: int = 0               # chỉ có ở Thứ 7

    def to_engine_dict(self) -> Dict[str, Any]:
        """Chuẩn hoá sang dict dùng trong engine/UI (PGD đổi key sang string)."""
        return {
            "TD": self.TD,
            "PGD": {k.value: v for k, v in self.PGD.items()},
            "K_WHITE": self.K_WHITE,   # lưu ý: đây là int, nên return type cần Any
        }

@dataclass(frozen=True)
class NightDetail:
    leader: int      # Đ @ TD (trưởng ca đêm)
    TD_white: int    # Đ trắng @ TD
    PGD: int         # Đ @ PGD

class RuleProfile:
    """Interface chung; mỗi phòng ban triển khai 1 profile."""
    name: str = "BASE"

    def day_detail(self, kind: DayKind | str) -> DayDetail:
        raise NotImplementedError

    def night_detail(self, kind: DayKind | str) -> NightDetail:
        raise NotImplementedError

    def credit(self) -> Dict[str, float]:
        # Trả map string->float để các phần còn lại không cần biết enum
        return {k.value: v for k, v in CREDITS.items()}

    # ===== Helpers cho TotalsRows/estimate (optional) =====
    def expected_day_counts(self, kind: DayKind | str) -> Dict[str, Any]:
        """Trả cấu trúc giống perDayByPlace của UI (TD/PGD/K_WHITE)."""
        return self.day_detail(kind).to_engine_dict()

    def expected_night_counts(self, kind: DayKind | str) -> Dict[str, int]:
        n = self.night_detail(kind)
        return {"leader": n.leader, "TD_WHITE": n.TD_white, "PGD": n.PGD}