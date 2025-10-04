"""Administrative endpoints."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, request
from sqlalchemy import text

import models

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _db_file() -> Path | None:
    db_path = models.engine.url.database
    if not db_path:
        return None
    path = Path(db_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


@admin_bp.post("/reset")
def admin_reset():
    mode = (request.args.get("mode") or "soft").lower()
    if mode not in ("soft", "hard"):
        return {"error": "mode must be soft|hard"}, 400

    if mode == "hard":
        db_file = _db_file()
        try:
            if db_file and db_file.exists():
                db_file.unlink()
            models.init_db()
            return {"ok": True, "mode": "hard"}
        except Exception as exc:
            return {"error": str(exc)}, 500

    with models.SessionLocal() as session:
        try:
            session.execute(text("DELETE FROM assignment"))
            session.commit()
            return {"ok": True, "mode": "soft"}
        except Exception as exc:
            session.rollback()
            return {"error": str(exc)}, 500
