# backend/models.py
import os
from datetime import date
from typing import List, Optional
from urllib.parse import quote_plus

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    inspect,
)
from sqlalchemy.orm import (
    Mapped,
    declarative_base,
    mapped_column,
    relationship,
    sessionmaker,
)

from dotenv import load_dotenv

load_dotenv()

DB_URL_ENV = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

if DB_URL_ENV:
    DB_URL = DB_URL_ENV
else:
    cfg = {
        "DB_HOST": os.getenv("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_USER": os.getenv("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD"),
    }
    missing = [key for key, value in cfg.items() if not value]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            "Missing database configuration for: " + joined
        )

    tz = os.getenv("DB_TIMEZONE")
    opts = os.getenv("DB_OPTIONS")

    user = quote_plus(cfg["DB_USER"])
    password = quote_plus(cfg["DB_PASSWORD"])
    base = (
        f"postgresql+psycopg://{user}:{password}"
        f"@{cfg['DB_HOST']}:{cfg['DB_PORT']}/{cfg['DB_NAME']}"
    )

    query_parts = []
    if opts:
        opt_payload = opts.lstrip("?")
        if opt_payload:
            query_parts.append(opt_payload)
    if tz:
        query_parts.append(f"options={quote_plus(f'-c TimeZone={tz}')}")

    if query_parts:
        DB_URL = f"{base}?{'&'.join(query_parts)}"
    else:
        DB_URL = base

if DB_URL.startswith("sqlite:///"):
    db_file = DB_URL.replace("sqlite:///", "", 1)
    if db_file and db_file != ":memory:":
        abs_path = os.path.abspath(db_file)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

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
    """Create tables and run lightweight migrations.

    Ensures the ``fixed_assignment`` table always has the ``position`` column,
    even for databases created before the column was introduced.
    """
    Base.metadata.create_all(engine)

    # --- Migration: add ``position`` column if missing ---
    insp = inspect(engine)
    try:
        tables = set(insp.get_table_names())
    except Exception:
        return

    if "fixed_assignment" not in tables:
        return

    cols = {col["name"] for col in insp.get_columns("fixed_assignment")}
    if "position" not in cols:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "ALTER TABLE fixed_assignment ADD COLUMN position VARCHAR NULL"
            )
