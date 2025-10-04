"""Lookup/constant endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify

from rules import SHIFT_DEFS

lookup_bp = Blueprint("lookup", __name__, url_prefix="/api")


@lookup_bp.get("/shifts")
def get_shifts():
    return jsonify(SHIFT_DEFS)
