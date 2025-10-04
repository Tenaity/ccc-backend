"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Create a test client with isolated database.

    This fixture:
    1. Creates a temporary SQLite database for test isolation
    2. Sets the DB_URL environment variable
    3. Resets the database engine cache to pick up the new URL
    4. Initializes the database schema
    5. Creates a fresh Flask app instance
    6. Returns a namespace with the test client and modules
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_URL", f"sqlite:///{db_path}")

    # Reset database engine cache to pick up new DB_URL
    from src.infrastructure.persistence import database as db_module
    db_module.reset_engine()

    # Reload models to get fresh engine/session
    import models
    importlib.reload(models)
    models.init_db()

    # Reload app module to create fresh Flask app
    import app as app_module
    importlib.reload(app_module)

    return SimpleNamespace(
        client=app_module.app.test_client(),
        models=models,
        module=app_module,
    )
