"""Application configuration primitives.

This module centralises configuration access so the rest of the codebase avoids
reading environment variables directly. It is intentionally lightweight to keep
bootstrap costs small while retaining enough structure to express the project
policies (e.g. database URL discovery).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DB_URL = "sqlite:///instance/app.sqlite"


@dataclass(frozen=True)
class DatabaseSettings:
    """Database connection configuration."""

    url: str


def _build_url_from_components() -> Optional[str]:
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    values = [host, port, name, user, password]
    if not any(values):
        return None

    missing = [
        key
        for key, value in {
            "DB_HOST": host,
            "DB_PORT": port,
            "DB_NAME": name,
            "DB_USER": user,
            "DB_PASSWORD": password,
        }.items()
        if not value
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing database configuration for: {joined}")

    tz = os.getenv("DB_TIMEZONE")
    opts = os.getenv("DB_OPTIONS")

    safe_user = quote_plus(user)
    safe_password = quote_plus(password)

    base = f"postgresql+psycopg://{safe_user}:{safe_password}@{host}:{port}/{name}"

    query_parts: list[str] = []
    if opts:
        payload = opts.lstrip("?")
        if payload:
            query_parts.append(payload)
    if tz:
        query_parts.append(f"options={quote_plus(f'-c TimeZone={tz}')}")

    if query_parts:
        return f"{base}?{'&'.join(query_parts)}"
    return base


def get_database_settings() -> DatabaseSettings:
    """Load database settings from environment (with caching)."""

    url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if not url:
        url = _build_url_from_components() or DEFAULT_DB_URL
    return DatabaseSettings(url=url)
