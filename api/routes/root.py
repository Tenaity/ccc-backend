from __future__ import annotations

import os

from flask import Blueprint, current_app, jsonify, send_from_directory

bp = Blueprint("root", __name__)


@bp.get("/")
def root():
    """Serve SPA entrypoint or fallback API info."""
    static_folder = current_app.static_folder
    if static_folder:
        index_html = os.path.join(static_folder, "index.html")
        if os.path.isfile(index_html):
            return send_from_directory(static_folder, "index.html")

    return jsonify(
        service="customer-care-center API",
        ok=True,
        docs=[
            "/api/ping",
            "/api/shifts",
            "/api/staff",
            "/api/assignments?year=YYYY&month=MM",
            "/api/schedule/generate (POST)",
            "/api/admin/reset?mode=soft (POST)",
        ],
    )


@bp.route("/<path:path>")
def spa_assets(path: str):
    """Serve static assets and fallback to index.html for SPA routes."""
    static_folder = current_app.static_folder
    if static_folder:
        asset_path = os.path.join(static_folder, path)
        if os.path.isfile(asset_path):
            return send_from_directory(static_folder, path)

        index_html = os.path.join(static_folder, "index.html")
        if os.path.isfile(index_html):
            return send_from_directory(static_folder, "index.html")

    return {"error": "Not Found"}, 404


@bp.get("/api/ping")
def ping():
    return {"ok": True}
