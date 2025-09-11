from __future__ import annotations

"""Minimal logging helpers for scheduler phases."""
from .core import Context


def day_log(_: Context, msg: str) -> None:
    print(f"[DAY ] {msg}")


def night_log(_: Context, msg: str) -> None:
    print(f"[NIGHT] {msg}")
