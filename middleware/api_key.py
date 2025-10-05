from __future__ import annotations

from typing import Optional

from flask import Flask, jsonify, request


def register_api_key_middleware(app: Flask, *, api_key: Optional[str]) -> None:
    """Attach middleware enforcing x-api-key header when configured."""

    if not api_key:
        return

    @app.before_request
    def _enforce_api_key():  # pragma: no cover - simple guard
        if request.method == "OPTIONS":
            return
        if not request.path.startswith("/api"):
            return

        header_key = request.headers.get("x-api-key")
        if header_key != api_key:
            return jsonify({"isSuccess": False, "error": "invalid_api_key"}), 401
