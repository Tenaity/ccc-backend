# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, timedelta


def ymd(y: int, m: int, d: int) -> date:
    return date(y, m, d)


def month_last_day(y: int, m: int) -> int:
    if m == 12:
        return (date(y + 1, 1, 1) - timedelta(days=1)).day
    return (date(y, m + 1, 1) - timedelta(days=1)).day


def day_kind(d: date, holidays: set[date]) -> str:
    if d in holidays:
        return "HOLIDAY"
    wd = d.weekday()  # 0 Mon .. 6 Sun
    if wd == 5:
        return "SAT"
    if wd == 6:
        return "SUN"
    return "WEEKDAY"
