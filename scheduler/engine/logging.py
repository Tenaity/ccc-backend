"""Minimal logging helpers for scheduler phases."""

from __future__ import annotations

from .core import Context


def day_log(_: Context, msg: str) -> None:
    print(f"[DAY ] {msg}")


def night_log(_: Context, msg: str) -> None:
    print(f"[NIGHT] {msg}")
