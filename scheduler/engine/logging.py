"""Minimal logging helpers for scheduler phases."""

from __future__ import annotations

import logging

from .core import Context

_day_logger = logging.getLogger("scheduler.day")
_night_logger = logging.getLogger("scheduler.night")
_engine_logger = logging.getLogger("scheduler.engine")
_balancer_logger = logging.getLogger("scheduler.balancer")


def day_log(_: Context, msg: str) -> None:
    _day_logger.info(msg)
    print(f"[DAY ] {msg}")


def night_log(_: Context, msg: str) -> None:
    _night_logger.info(msg)
    print(f"[NIGHT] {msg}")


def engine_log(msg: str) -> None:
    _engine_logger.info(msg)
    print(f"[ENGINE] {msg}")


def balancer_log(msg: str) -> None:
    _balancer_logger.info(msg)
    print(f"[BALANCER] {msg}")
