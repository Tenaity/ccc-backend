# -*- coding: utf-8 -*-
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from .placements import Planned

def validate_one_day_leader(planned: list[Planned], first: date, last: date):
    by = defaultdict(int)
    for p in planned:
        if p.shift_code == "K" and p.position == "TD":
            by[p.day] += 1
    bad = []
    d = first
    while d <= last:
        if by.get(d, 0) != 1:
            bad.append((d, by.get(d, 0)))
        d += timedelta(days=1)
    return bad