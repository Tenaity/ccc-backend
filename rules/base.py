# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .types import CREDITS, DayKind, ShiftCode

# UI/REST vẫn dùng các mã ca dạng string
SHIFT_DEFS = [
    ShiftCode.CA1.value,
    ShiftCode.CA2.value,
    ShiftCode.K.value,
    ShiftCode.HC.value,
    ShiftCode.D.value,
    ShiftCode.P.value,
]

# ---- Kiểu cho phần NGÀY ----
DayTD = Dict[ShiftCode, int]  # ví dụ: {ShiftCode.K:1, ShiftCode.CA1:2, ShiftCode.CA2:4}
DayPGD = Dict[ShiftCode, int]  # ví dụ: {ShiftCode.K:1, ShiftCode.CA2:1}


@dataclass(frozen=True)
class DayDetail:
    TD: DayTD
    PGD: DayPGD

    def to_engine_dict(self) -> Dict[str, Dict[str, int]]:
        """
        Chuẩn hoá sang dict cho engine/UI:
        - key là string (".value" của enum)
        - KHÔNG còn 'K_leader' hay 'K_WHITE' ở đây; 'leader/K_white' do POSITION quyết định ở engine.
        """
        return {
            "TD": {k.value: v for k, v in self.TD.items()},
            "PGD": {k.value: v for k, v in self.PGD.items()},
        }


# ---- Kiểu cho phần ĐÊM ----
NightTD = Dict[ShiftCode, int]  # ví dụ: {ShiftCode.K:1, ShiftCode.CA1:2, ShiftCode.CA2:4}
NightPGD = Dict[ShiftCode, int]  # ví dụ: {ShiftCode.K:1, ShiftCode.CA2:1}


@dataclass(frozen=True)
class NightDetail:
    TD: NightTD
    PGD: NightPGD

    def to_engine_dict(self) -> Dict[str, Dict[str, int]]:
        """
        Chuẩn hoá sang dict cho engine/UI:
        - key là string (".value" của enum)
        - KHÔNG còn 'K_leader' hay 'K_WHITE' ở đây; 'leader/K_white' do POSITION quyết định ở engine.
        """
        return {
            "TD": {k.value: v for k, v in self.TD.items()},
            "PGD": {k.value: v for k, v in self.PGD.items()},
        }


class RuleProfile:
    """Interface chung; mỗi phòng ban triển khai 1 profile."""

    name: str = "BASE"

    def day_detail(self, kind: DayKind | str) -> DayDetail:
        raise NotImplementedError

    def night_detail(self, kind: DayKind | str) -> NightDetail:
        raise NotImplementedError

    def credit(self) -> Dict[str, float]:
        """
        Trả map string->float để các phần còn lại (engine/DB/UI) không cần biết enum.
        Ví dụ: {"CA1":1, "CA2":1, "K":1.25, "HC":1, "Đ":1.5, "P":0}
        """
        return {k.value: v for k, v in CREDITS.items()}

    # ===== Helpers cho TotalsRows/estimate (tùy dùng) =====
    def expected_day_counts(self, kind: DayKind | str) -> Dict[str, Dict[str, int]]:
        """
        Trả cấu trúc cùng shape với perDayByPlace (phần NGÀY):
        {
          "TD":  {"K":1,"CA1":2,"CA2":4},
          "PGD": {"K":1,"CA2":1}
        }
        Lưu ý: KHÔNG có "K_WHITE" ở đây (K trắng sẽ do engine quyết định theo POSITION).
        """
        return self.day_detail(kind).to_engine_dict()

    def expected_night_counts(self, kind: DayKind | str) -> Dict[str, Dict[str, int]]:
        """
        Trả cấu trúc cùng shape với perDayByPlace (phần NGÀY):
        {
          "TD":  {"K":1,"Đ":2,},
          "PGD": {"Đ":2}
        }
        Lưu ý: KHÔNG có "K_WHITE" ở đây (K trắng sẽ do engine quyết định theo POSITION).
        Đ cũng sẽ quyết định theo position.
        """
        return self.night_detail(kind).to_engine_dict()
