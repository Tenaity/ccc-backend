# backend/models.py
import os
from datetime import date
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import (
    Mapped,
    declarative_base,
    mapped_column,
    relationship,
    sessionmaker,
)

DB_URL = os.getenv("DB_URL", "sqlite:///./cskh.db")
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="GDV")  # GDV | TC
    can_night: Mapped[bool] = mapped_column(Boolean, default=True)
    base_quota: Mapped[float] = mapped_column(Float, default=26.0)  # công chuẩn/tháng
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    fixed_assignments: Mapped[List["FixedAssignment"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    off_days: Mapped[List["OffDay"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )


class FixedAssignment(Base):
    __tablename__ = "fixed_assignment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date, nullable=False)
    shift_code: Mapped[str] = mapped_column(String, nullable=False)  # CA1 | CA2 | K | HC | Đ
    position: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # TD | PGD
    staff: Mapped[Staff] = relationship(back_populates="fixed_assignments")


class OffDay(Base):
    __tablename__ = "off_day"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String)
    staff: Mapped[Staff] = relationship(back_populates="off_days")


class Assignment(Base):
    __tablename__ = "assignment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    day: Mapped[date] = mapped_column(Date, nullable=False)
    shift_code: Mapped[str] = mapped_column(String, nullable=False)
    position = Column(String, nullable=True)  # 'PGD' | 'TD' | 'K_WHITE' | None
    staff: Mapped[Optional[Staff]] = relationship()


class Holiday(Base):
    __tablename__ = "holidays"
    id = Column(Integer, primary_key=True)
    day = Column(Date, unique=True, nullable=False)
    name = Column(String, nullable=True)


def init_db():
    """Create tables and migrate legacy databases.

    SQLite does not support ``ALTER TABLE`` in ``create_all``. Existing
    deployments may therefore miss newly added columns. This helper creates
    tables for fresh databases and, for pre-existing ones, ensures the
    ``fixed_assignment`` table contains the ``position`` column.
    """
    Base.metadata.create_all(engine)

    # --- Migration: add ``position`` column if missing ---
    with engine.connect() as conn:
        res = conn.exec_driver_sql("PRAGMA table_info('fixed_assignment')").fetchall()
        cols = {row[1] for row in res}
        if "position" not in cols:
            conn.exec_driver_sql("ALTER TABLE fixed_assignment ADD COLUMN position VARCHAR NULL")
        conn.commit()
