"""Database bootstrap helpers - PostgreSQL only."""

from __future__ import annotations

import logging
from typing import Iterator

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.settings.config import get_database_settings

logger = logging.getLogger(__name__)

Base = declarative_base()
_engine = None
_SessionLocal = None
_active_url = None


def get_engine():
    """Get or create database engine for PostgreSQL.

    PostgreSQL only - SQLite removed for production deployment.
    """
    global _engine, _SessionLocal, _active_url
    settings = get_database_settings()
    url = settings.url

    if _engine is None or url != _active_url:
        engine_kwargs = {
            "echo": False,
            "future": True,
        }

        if _engine is not None:
            try:
                _engine.dispose()
            except Exception:  # pragma: no cover - defensive
                pass

        _engine = create_engine(url, **engine_kwargs)
        _SessionLocal = None
        _active_url = url

    logger.info("Connected to database: %s", url.split("@")[1] if "@" in url else url)
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
