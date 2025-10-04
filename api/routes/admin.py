from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from models import SessionLocal, engine, init_db

bp = Blueprint("admin", __name__)

_db_path = engine.url.database or ""
if _db_path and _db_path != ":memory:":
    if not os.path.isabs(_db_path):
        DB_FILE = (Path.cwd() / _db_path).resolve()
    else:
        DB_FILE = Path(_db_path)
else:
    DB_FILE = None


@bp.post("/api/admin/reset")
def admin_reset():
    """Reset assignments or rebuild the SQLite database based on mode."""
    mode = (request.args.get("mode") or "soft").lower()
    if mode not in ("soft", "hard"):
        return {"error": "mode must be soft|hard"}, 400

    if mode == "hard":
        try:
            if DB_FILE and DB_FILE.exists():
                DB_FILE.unlink()
            init_db()
            return {"ok": True, "mode": "hard"}
        except Exception as exc:  # pragma: no cover - defensive guard
            return {"error": str(exc)}, 500

    with SessionLocal() as session:
        try:
            session.execute(text("DELETE FROM assignment"))
            session.commit()
            return {"ok": True, "mode": "soft"}
        except Exception as exc:  # pragma: no cover - defensive guard
            session.rollback()
            return {"error": str(exc)}, 500
