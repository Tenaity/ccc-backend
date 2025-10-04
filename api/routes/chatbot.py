from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

bp = Blueprint("chatbot", __name__)


@bp.post("/api/chatbot/upload")
def chatbot_upload():
    """Proxy file uploads to the configured webhook."""
    import requests

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        files = {"file": (file.filename, file.stream, file.content_type)}
        data = {key: request.form[key] for key in request.form}
        webhook_url = os.getenv(
            "WEBHOOK_UPLOAD_URL",
            "https://iconic-host.lapage.vn/webhook/upload-file",
        )
        response = requests.post(webhook_url, files=files, data=data, timeout=30)
        return (
            jsonify({"status": response.status_code, "response": response.text}),
            response.status_code,
        )
    except Exception as exc:  # pragma: no cover - network failure guard
        return jsonify({"error": str(exc)}), 500


@bp.post("/api/chatbot/chunking")
def chatbot_chunking():
    """Proxy chunking requests to the configured webhook."""
    import requests

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        webhook_url = os.getenv(
            "WEBHOOK_CHUNKING_URL",
            "https://iconic-host.lapage.vn/webhook/chunking",
        )
        response = requests.post(webhook_url, json=data, timeout=30)
        if response.headers.get("content-type") == "application/json":
            payload = response.json()
        else:
            payload = response.text
        return (
            jsonify({"status": response.status_code, "response": payload}),
            response.status_code,
        )
    except Exception as exc:  # pragma: no cover - network failure guard
        return jsonify({"error": str(exc)}), 500
