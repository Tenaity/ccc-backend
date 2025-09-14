import os

os.environ.setdefault("DB_URL", "sqlite:///:memory:")

from datetime import date

import pytest

from models import Base, FixedAssignment, Holiday, OffDay, SessionLocal, Staff, engine, init_db


def seed_small(session):
    staff = [
        Staff(id=1, full_name="TC1", role="TC", base_quota=2),
        Staff(id=2, full_name="TC2", role="TC", base_quota=2),
        Staff(id=3, full_name="G1A", role="GDV", notes="[RANK:1]"),
        Staff(id=4, full_name="G1B", role="GDV", notes="[RANK:1]"),
        Staff(id=5, full_name="G1C", role="GDV", notes="[RANK:1]"),
        Staff(id=6, full_name="G2A", role="GDV", notes="[RANK:2]"),
        Staff(id=7, full_name="G2B", role="GDV", notes="[RANK:2]"),
        Staff(id=8, full_name="G2C", role="GDV", notes="[RANK:2]"),
    ]
    session.add_all(staff)
    # fixed assignment & off day sample for 2025-01-04 (Saturday)
    session.add(FixedAssignment(staff_id=3, day=date(2025, 1, 4), shift_code="CA1", position="TD"))
    session.add(OffDay(staff_id=6, day=date(2025, 1, 4)))
    session.add(Holiday(day=date(2025, 1, 1), name="NewYear"))
    session.commit()


@pytest.fixture()
def session():
    Base.metadata.drop_all(bind=engine)
    init_db()
    s = SessionLocal()
    seed_small(s)
    yield s
    s.close()


def build_ctx(year, month, seed=0, save=False):
    from scheduler.engine.core import build_context

    ctx, first, last = build_context(year=year, month=month, shuffle=False, seed=seed, save=save)
    return ctx, first, last
