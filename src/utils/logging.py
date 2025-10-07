"""Central logging helpers for the project."""

from __future__ import annotations

import logging
import os
import sys
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(*, force: bool = False) -> None:
    """Initialise the root logger with sane defaults.

    The configuration is idempotent unless ``force`` is set. Environment
    variables ``LOG_LEVEL`` and ``LOG_FORMAT`` can override the defaults.
    """

    if logging.getLogger().handlers and not force:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.getenv("LOG_FORMAT", _DEFAULT_FORMAT)

    logging.basicConfig(level=level, format=fmt, stream=sys.stdout, force=force)

    # Keep SQLAlchemy noise under control unless explicitly requested.
    sa_level_name = os.getenv("SQL_LOG_LEVEL", "WARNING").upper()
    sa_level = getattr(logging, sa_level_name, logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(sa_level)


def _shorten(value: Any, *, limit: int = 120) -> str:
    try:
        text = repr(value)
    except Exception:
        text = object.__repr__(value)
    if len(text) > limit:
        return f"{text[:limit]}…"
    return text


def log_call(logger: logging.Logger, *, level: int = logging.INFO) -> Callable[[F], F]:
    """Decorator logging duration and success/failure for callables."""

    def decorator(func: F) -> F:
        if getattr(func, "__log_wrapped__", False):
            return func

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):  # type: ignore[misc]
            start = time.perf_counter()
            arg_preview = ", ".join([
                ", ".join(_shorten(a) for a in args[:3]),
                ", ".join(f"{k}={_shorten(v)}" for k, v in list(kwargs.items())[:3]),
            ]).strip(", ")
            logger.log(level, "? %s(%s)", func.__qualname__, arg_preview)
            try:
                result = func(*args, **kwargs)
            except Exception:
                duration = time.perf_counter() - start
                logger.exception("? %s failed after %.3fs", func.__qualname__, duration)
                raise
            duration = time.perf_counter() - start
            logger.log(
                level,
                "? %s completed in %.3fs%s",
                func.__qualname__,
                duration,
                f" -> {_shorten(result)}" if result is not None else "",
            )
            return result

        setattr(wrapper, "__log_wrapped__", True)
        return cast(F, wrapper)

    return decorator


def instrument_service(cls=None, *, logger: Optional[logging.Logger] = None):
    """Class decorator instrumenting public methods with ``log_call``."""

    def wrap(target_cls):
        service_logger = logger or logging.getLogger(
            f"{target_cls.__module__}.{target_cls.__name__}"
        )
        for name, attr in list(target_cls.__dict__.items()):
            if name.startswith("_"):
                continue
            if isinstance(attr, staticmethod):
                func = getattr(attr, "__func__")
                wrapped = staticmethod(log_call(service_logger)(func))
                setattr(target_cls, name, wrapped)
            elif isinstance(attr, classmethod):
                func = getattr(attr, "__func__")
                wrapped = classmethod(log_call(service_logger)(func))
                setattr(target_cls, name, wrapped)
            elif callable(attr):
                setattr(target_cls, name, log_call(service_logger)(attr))
        setattr(target_cls, "_logger", service_logger)
        return target_cls

    if cls is None:
        return wrap
    return wrap(cls)



def instrument_flask_routes(app, *, exclude_prefixes: tuple[str, ...] = ("static",)) -> None:
    """Wrap Flask view functions with timing logs."""

    for endpoint, func in list(app.view_functions.items()):
        if any(endpoint.startswith(prefix) for prefix in exclude_prefixes):
            continue
        app.view_functions[endpoint] = log_call(
            logging.getLogger(f"http.route.{endpoint}")
        )(func)


def register_http_logging(app) -> None:
    """Attach Flask request/response logging handlers."""

    import uuid
    from flask import g, request

    http_logger = logging.getLogger("http")

    @app.before_request
    def _start_timer():  # pragma: no cover - thin adapter
        g._request_start = time.perf_counter()
        g._request_id = uuid.uuid4().hex

    @app.after_request
    def _log_response(response):  # pragma: no cover - thin adapter
        start = getattr(g, "_request_start", time.perf_counter())
        duration = time.perf_counter() - start
        http_logger.info(
            "%s %s %s %s %.3fs",
            request.method,
            request.path,
            response.status_code,
            request.remote_addr,
            duration,
        )
        response.headers.setdefault("X-Request-ID", getattr(g, "_request_id", ""))
        return response

    @app.teardown_request
    def _log_exception(exc):  # pragma: no cover - thin adapter
        if exc is not None:
            http_logger.exception("Unhandled exception for %s %s", request.method, request.path)


__all__ = [
    "configure_logging",
    "log_call",
    "instrument_service",
    "register_http_logging",
    "instrument_flask_routes",
]
