"""SQLAlchemy models and schema bootstrap utilities."""

from __future__ import annotations

from datetime import date
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    inspect,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.sql import expression

from src.infrastructure.persistence import database as _database
from src.infrastructure.persistence.database import Base, session_scope

engine = _database.get_engine()
SessionLocal = _database.get_session_factory()


class Department(Base):
    """Department model for multi-department support."""
    __tablename__ = "department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # Short code like "CC", "IT"
    color: Mapped[str] = mapped_column(String, default="#3b82f6")  # Hex color for UI
    icon: Mapped[str] = mapped_column(String, default="Building2")  # Lucide icon name
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Settings stored as JSON
    settings: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {
            "working_hours": {"start": "08:00", "end": "17:00"},
            "weekend_policy": "sat_off",
            "max_hours_per_month": 208,
            "min_staff_per_shift": 2,
        },
        server_default='{"working_hours": {"start": "08:00", "end": "17:00"}, "weekend_policy": "sat_off", "max_hours_per_month": 208, "min_staff_per_shift": 2}'
    )

    # Relationships
    staff: Mapped[List["Staff"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )
    shifts: Mapped[List["ShiftConfig"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )


class ShiftConfig(Base):
    """Custom shift configuration per department."""
    __tablename__ = "shift_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("department.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String, nullable=False)  # "Ca Sáng"
    code: Mapped[str] = mapped_column(String, nullable=False)  # "CS" (for display on matrix)
    start_time: Mapped[str] = mapped_column(String, nullable=False)  # "08:00"
    end_time: Mapped[str] = mapped_column(String, nullable=False)  # "17:00"
    color: Mapped[str] = mapped_column(String, default="#60a5fa")  # Pastel color
    icon: Mapped[str] = mapped_column(String, default="Sun")  # Lucide icon
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)  # For sorting

    # Rules stored as JSON
    rules: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {},
        server_default='{}'
    )

    # Relationship
    department: Mapped[Department] = relationship(back_populates="shifts")

    __table_args__ = (
        UniqueConstraint("department_id", "code", name="uq_shift_config_dept_code"),
    )


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="GDV")  # GDV | TC
    can_night: Mapped[bool] = mapped_column(Boolean, default=True)
    base_quota: Mapped[float] = mapped_column(Float, default=26.0)  # công chuẩn/tháng
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Department FK (nullable for backward compatibility)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    department: Mapped[Optional[Department]] = relationship(back_populates="staff")
    fixed_assignments: Mapped[List["FixedAssignment"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    off_days: Mapped[List["OffDay"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan"
    )
    preferences: Mapped[Optional["StaffPreferences"]] = relationship(
        back_populates="staff", cascade="all, delete-orphan", uselist=False
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


class StaffPreferences(Base):
    """Staff scheduling preferences for better work-life balance."""
    __tablename__ = "staff_preferences"

    staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Preferred shift codes (e.g., ["K", "CA1"] - prefer day shifts)
    preferred_shifts: Mapped[Optional[str]] = mapped_column(
        JSON,
        nullable=True,
        server_default='[]'
    )

    # Unavailable dates (e.g., ["2025-10-15", "2025-10-20"])
    unavailable_days: Mapped[Optional[str]] = mapped_column(
        JSON,
        nullable=True,
        server_default='[]'
    )

    # Maximum consecutive working days before needing a break
    max_consecutive_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=6
    )

    # Preferred days off (0=Monday, 6=Sunday) - e.g., [5, 6] for weekends
    preferred_days_off: Mapped[Optional[str]] = mapped_column(
        JSON,
        nullable=True,
        server_default='[]'
    )

    # Additional notes about preferences
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationship
    staff: Mapped[Staff] = relationship(back_populates="preferences")


class Assignment(Base):
    __tablename__ = "assignment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    day: Mapped[date] = mapped_column(Date, nullable=False)
    shift_code: Mapped[str] = mapped_column(String, nullable=False)
    position = Column(String, nullable=True)  # 'PGD' | 'TD' | 'K_WHITE' | None
    staff: Mapped[Optional[Staff]] = relationship()



class WeekendPolicy(str, PyEnum):
    SAT_OFF = "sat_off"
    SAT_WORK_AM = "sat_work_am"
    SAT_WORK = "sat_work"


class Holiday(Base):
    __tablename__ = "holiday"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(
        "date", Date, unique=True, nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    official: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=expression.false(),
    )
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class MonthConfig(Base):
    __tablename__ = "month_config"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_month_config_year_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    working_days_override: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weekend_policy: Mapped[WeekendPolicy] = mapped_column(
        SAEnum(WeekendPolicy, name="weekend_policy"),
        nullable=False,
        default=WeekendPolicy.SAT_OFF,
        server_default=WeekendPolicy.SAT_OFF.value,
    )
    extra_workdays: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    extra_offdays: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )


class ShiftPlanDefaults(Base):
    __tablename__ = "shift_plan_defaults"
    __table_args__ = (
        UniqueConstraint(
            "year",
            "month",
            name="uq_shift_plan_defaults_year_month",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day_shifts: Mapped[int] = mapped_column(Integer, nullable=False)
    night_shifts: Mapped[int] = mapped_column(Integer, nullable=False)
    leader_shifts: Mapped[int] = mapped_column(Integer, nullable=False)
    pgd_shifts: Mapped[int] = mapped_column(Integer, nullable=False)


def init_db():
    """Create tables and run lightweight migrations.

    Ensures schema changes introduced over time are reflected when running in
    environments without Alembic migrations.
    """

    global engine, SessionLocal
    engine = _database.get_engine()
    SessionLocal = _database.get_session_factory()

    insp = inspect(engine)
    try:
        existing_tables = set(insp.get_table_names())
    except Exception:
        existing_tables = set()

    if "holidays" in existing_tables and "holiday" not in existing_tables:
        with engine.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE holidays RENAME TO holiday")
        existing_tables.remove("holidays")
        existing_tables.add("holiday")

    Base.metadata.create_all(engine)

    insp = inspect(engine)
    try:
        tables = set(insp.get_table_names())
    except Exception:
        return

    # --- Migration: holiday table enhancements ---
    if "holiday" in tables:
        holiday_cols = {col["name"] for col in insp.get_columns("holiday")}

        if "day" in holiday_cols and "date" not in holiday_cols:
            with engine.begin() as conn:
                conn.exec_driver_sql("ALTER TABLE holiday RENAME COLUMN day TO date")
            insp = inspect(engine)
            holiday_cols = {col["name"] for col in insp.get_columns("holiday")}

        if "kind" not in holiday_cols:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE holiday ADD COLUMN kind VARCHAR NULL"
                )
            insp = inspect(engine)
            holiday_cols = {col["name"] for col in insp.get_columns("holiday")}

        if "official" not in holiday_cols:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE holiday ADD COLUMN official BOOLEAN NOT NULL DEFAULT false"
                )
            insp = inspect(engine)
            holiday_cols = {col["name"] for col in insp.get_columns("holiday")}

        if "source" not in holiday_cols:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE holiday ADD COLUMN source VARCHAR NULL"
                )

        uniques = insp.get_unique_constraints("holiday")
        has_date_unique = any(
            "date" in constraint.get("column_names", []) for constraint in uniques
        )
        if not has_date_unique:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_holiday_date ON holiday(date)"
                )

    # --- Migration: add ``position`` column if missing ---
    if "fixed_assignment" in tables:
        cols = {col["name"] for col in insp.get_columns("fixed_assignment")}
        if "position" not in cols:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE fixed_assignment ADD COLUMN position VARCHAR NULL"
                )

    # --- Migration: add department_id to staff table ---
    if "staff" in tables:
        staff_cols = {col["name"] for col in insp.get_columns("staff")}
        if "department_id" not in staff_cols:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    "ALTER TABLE staff ADD COLUMN department_id INTEGER NULL"
                )

__all__ = [
    'Base',
    'SessionLocal',
    'engine',
    'session_scope',
    'Department',
    'ShiftConfig',
    'Staff',
    'FixedAssignment',
    'OffDay',
    'StaffPreferences',
    'Assignment',
    'WeekendPolicy',
    'Holiday',
    'MonthConfig',
    'ShiftPlanDefaults',
    'init_db',
]

