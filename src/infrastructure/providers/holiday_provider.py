"""External holiday provider integrations."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from typing import Iterable


class HolidayProviderError(RuntimeError):
    """Raised when fetching external holidays fails."""


def fetch_nager_holidays(year: int, country_code: str = "VN") -> list[dict]:
    """Fetch holidays from the Nager.Date API."""

    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}".strip()
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            status = getattr(response, "status", None) or response.getcode()
            if status >= 400:
                raise HolidayProviderError(f"Provider returned HTTP {status}")
            payload = response.read()
    except urllib.error.URLError as exc:
        raise HolidayProviderError(str(exc)) from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HolidayProviderError("Invalid JSON payload") from exc

    if not isinstance(data, list):
        raise HolidayProviderError("Unexpected response schema")

    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        day = item.get("date")
        try:
            day_value = date.fromisoformat(day)
        except Exception:
            continue
        name = item.get("localName") or item.get("name") or "(unnamed)"
        types = item.get("types") or []
        kind = ",".join(t for t in types if isinstance(t, str)) or None
        official = "Public" in types or bool(item.get("global"))
        out.append(
            {
                "day": day_value,
                "name": name,
                "kind": kind,
                "official": official,
                "source": "nager",
            }
        )
    return out


__all__ = ["HolidayProviderError", "fetch_nager_holidays"]
