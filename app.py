"""Application entrypoint with Clean Architecture wiring."""

from __future__ import annotations

import urllib
import urllib.request

from scheduler import schedule_month as generate_schedule

from src.application.month_config_service import build_month_config_payload
from src.infrastructure.providers.holiday_provider import (
    HolidayProviderError as HolidayImportError,
    fetch_nager_holidays as _fetch_nager_holidays,
)
from src.presentation.app import create_app

app = create_app()


def _build_month_config_payload(session, year: int, month: int) -> dict:
    """Expose legacy helper for compatibility with existing tests."""

    return build_month_config_payload(session, year, month)


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=int(8000), debug=True)
