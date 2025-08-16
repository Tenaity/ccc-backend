# -*- coding: utf-8 -*-
from __future__ import annotations
from collections import defaultdict
from sqlalchemy import select
from models import SessionLocal, Staff, FixedAssignment, OffDay, Holiday, Assignment

def load_staff(session):
    staff = session.execute(select(Staff)).scalars().all()
    TC  = [s for s in staff if s.role == "TC"]
    GDV = [s for s in staff if s.role == "GDV" and (s.notes or "").lower() != "nghỉ sinh"]
    HC  = [s for s in staff if s.role == "HC"]
    return TC, GDV, HC

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