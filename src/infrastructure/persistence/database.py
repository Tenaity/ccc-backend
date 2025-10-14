"""Database bootstrap helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.settings.config import get_database_settings

logger = logging.getLogger(__name__)

Base = declarative_base()
_engine = None
_SessionLocal = None
_active_url = None


def _normalise_url(raw: str) -> str:
    if raw.startswith("sqlite:///"):
        db_file = raw.replace("sqlite:///", "", 1)
        if db_file and db_file != ":memory:":
            path = Path(db_file).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{path}"
    return raw


def get_engine():
    global _engine, _SessionLocal, _active_url
    settings = get_database_settings()
    url = _normalise_url(settings.url)

    if _engine is None or url != _active_url:
        engine_kwargs = {"echo": False, "future": True}

        if url.startswith("sqlite"):
            # Allow connections to be shared across threads which helps with
            # background tasks and test fixtures.
            engine_kwargs["connect_args"] = {"check_same_thread": False}

            normalized = url.split("?", 1)[0]
            is_memory = (
                normalized in {"sqlite://", "sqlite:///:memory:"}
                or normalized.endswith(":memory:")
                or ":memory:" in normalized
            )

            if is_memory:
                # Ensure all sessions share the same in-memory database. Without
                # a static pool each new connection would see a fresh schema,
                # causing "no such table" errors in tests that rely on
                # init_db() to create the schema once per fixture.
                engine_kwargs["poolclass"] = StaticPool

        if _engine is not None:
            try:
                _engine.dispose()
            except Exception:  # pragma: no cover - defensive
                pass
        engine_kwargs = {
            "echo": False,
            "future": True,
        }
        normalized = url.split("?")[0]
        if normalized in {"sqlite://", "sqlite:///:memory:"} or normalized.endswith(":memory:"):
            engine_kwargs.update({
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            })
        _engine = create_engine(url, **engine_kwargs)
        _SessionLocal = None
        _active_url = url
    logger.info("Using database engine with URL: %s", url)
    return _engine


def get_session_factory():
    global _SessionLocal
    engine = get_engine()
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables if they don't exist."""

    Base.metadata.create_all(get_engine())


def reset_engine() -> None:
    """Reset cached engine and session factory (useful for test reinitialisation)."""

    global _engine, _SessionLocal, _active_url
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:  # pragma: no cover - defensive
            pass
    _engine = None
    _SessionLocal = None
    _active_url = None
