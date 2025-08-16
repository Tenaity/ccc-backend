# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
from typing import Optional, Dict
from models import Assignment
from rules import CREDIT

@dataclass
class Planned:
    day: date
    staff_id: int
    shift_code: str
    position: Optional[str]  # "TD" | "PGD" | "K_WHITE" | "D_WHITE" | None

# trackers (state theo lần generate)
_last_night: Dict[int, date] = {}
_last_day:   Dict[int, date] = {}
_credit:     Dict[int, float] = {}
_weekend:    Dict[int, Dict[str, int]] = {}  # {"sat": n, "sun": n}

def reset_trackers():
    _last_night.clear(); _last_day.clear(); _credit.clear(); _weekend.clear()

def credit_of(code: str) -> float:
    return CREDIT.get(code, 0.0)

def place(session, planned: list[Planned], *, day, staff_id, code, position, save: bool):
    planned.append(Planned(day=day, staff_id=staff_id, shift_code=code, position=position))
    if save:
        session.add(Assignment(day=day, staff_id=staff_id, shift_code=code, position=position))

def after_place(staff_id: int, d: date, code: str):
    _credit[staff_id] = _credit.get(staff_id, 0.0) + credit_of(code)
    if code == "Đ":
        _last_night[staff_id] = d
    else:
        _last_day[staff_id] = d
        wd = d.weekday()
        if staff_id not in _weekend:
            _weekend[staff_id] = {"sat": 0, "sun": 0}
        if wd == 5:
            _weekend[staff_id]["sat"] += 1
        if wd == 6:
            _weekend[staff_id]["sun"] += 1

def exp_planned(planned: list[Planned]):
    return [asdict(p) | {"day": p.day.isoformat()} for p in planned]

# expose trackers cho randomize
def trackers():
    return _last_night, _last_day, _credit, _weekend