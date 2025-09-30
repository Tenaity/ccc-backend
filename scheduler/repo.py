# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from collections import defaultdict
from typing import List, Optional

from sqlalchemy import select

from models import FixedAssignment, Holiday, OffDay, Staff


# ---------- helpers ----------
def _parse_rank(notes: Optional[str]) -> Optional[int]:
    if not notes:
        return None
    m = re.search(r"\[RANK:(\d+)\]", notes)
    try:
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _is_maternity(notes: Optional[str]) -> bool:
    return bool(notes and "nghỉ sinh" in notes.lower())


# ---------- loaders ----------
def load_staff(session):
    """
    Trả về 4 lists: (TC, GDV1, GDV2, HC)
    - GDV1: rank == 1
    - GDV2: rank != 1 (mặc định 2)
    - Bỏ GDV "nghỉ sinh"
    """
    staff = session.execute(select(Staff)).scalars().all()

    TC: List[Staff] = []
    GDV1: List[Staff] = []
    GDV2: List[Staff] = []
    HC: List[Staff] = []

    for s in staff:
        # gắn thuộc tính tạm (không persist DB)
        s.rank = _parse_rank(s.notes) or 2

        if s.role == "TC":
            TC.append(s)
        elif s.role == "GDV" and not _is_maternity(s.notes):
            (GDV1 if s.rank == 1 else GDV2).append(s)
        elif s.role == "HC":
            HC.append(s)

    # ổn định thứ tự
    TC.sort(key=lambda x: x.id)
    GDV1.sort(key=lambda x: x.id)
    GDV2.sort(key=lambda x: x.id)
    HC.sort(key=lambda x: x.id)

    return TC, GDV1, GDV2, HC


def load_locked(session):
    mp = defaultdict(set)  # day -> set(staff_id)
    for r in session.query(OffDay).all():
        mp[r.day].add(r.staff_id)
    return mp


def load_fixed(session):
    mp = defaultdict(list)  # day -> list[FixedAssignment]
    for r in session.query(FixedAssignment).all():
        mp[r.day].append(r)
    return mp


def load_holidays(session) -> set:
    return {r.day for r in session.query(Holiday).all()}


def write_assignments(session, items):
    for it in items:
        session.add(it)
    session.commit()
