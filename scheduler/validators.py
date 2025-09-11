# -*- coding: utf-8 -*-
"""Lightweight helpers for validating planned assignments."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Iterable, List, Tuple

from .placements import Planned


def validate_one_day_leader(planned: List[Planned], first: date, last: date) -> List[Tuple[date, int]]:
    """Return days where count of K@TD is not exactly one."""
    by = defaultdict(int)
    for p in planned:
        if p.shift_code == "K" and p.position == "TD":
            by[p.day] += 1
    bad: List[Tuple[date, int]] = []
    d = first
    while d <= last:
        c = by.get(d, 0)
        if c != 1:
            bad.append((d, c))
        d += timedelta(days=1)
    return bad


def find_leader_duplicates(planned: Iterable[Planned], tc_ids: Iterable[int]) -> Tuple[Dict[date, List[int]], Dict[date, List[int]]]:
    """Detect duplicate leaders for day (K@TD) and night (Đ@TD from TC).

    Returns two dicts mapping day -> list of staff ids for offending days.
    """
    tc_set = set(tc_ids)
    day_map: Dict[date, List[int]] = defaultdict(list)
    night_map: Dict[date, List[int]] = defaultdict(list)
    for p in planned:
        if p.shift_code == "K" and p.position == "TD":
            day_map[p.day].append(p.staff_id)
        if p.shift_code == "Đ" and p.position == "TD" and p.staff_id in tc_set:
            night_map[p.day].append(p.staff_id)
    dup_day = {d: ids for d, ids in day_map.items() if len(ids) > 1}
    dup_night = {d: ids for d, ids in night_map.items() if len(ids) > 1}
    return dup_day, dup_night
