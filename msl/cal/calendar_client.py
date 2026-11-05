"""Thin Google Calendar wrapper: create / delete / list events.

Hits the REST API directly via ``requests``. We intentionally avoid
``google-api-python-client`` so we don't pull in ``protobuf`` on Android,
which has no prebuilt wheels there.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote

import requests

from ._credentials import Credentials

_BASE = "https://www.googleapis.com/calendar/v3"
_TIMEOUT = 30  # seconds


def _local_tz_name() -> str:
    """IANA tz name for the local system, with safe fallback."""
    try:
        return datetime.now().astimezone().tzinfo.key  # type: ignore[attr-defined]
    except Exception:
        return "UTC"


def _headers(creds: Credentials) -> dict:
    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json; charset=utf-8",
    }


def _cal_url(calendar_id: str, suffix: str = "") -> str:
    return f"{_BASE}/calendars/{quote(calendar_id, safe='')}{suffix}"


def create_event(
    creds: Credentials,
    calendar_id: str,
    summary: str,
    start: datetime,
    duration_min: int = 0,
    popup_offset_min: int = 0,
    tz: Optional[str] = None,
) -> dict:
    """Create an event. 0 duration + popup at 0 min = reminder-style."""
    tzname = tz or _local_tz_name()
    end = start + timedelta(minutes=max(0, duration_min))
    body = {
        "summary": summary,
        "start": {"dateTime": start.isoformat(), "timeZone": tzname},
        "end": {"dateTime": end.isoformat(), "timeZone": tzname},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": popup_offset_min}],
        },
    }
    r = requests.post(_cal_url(calendar_id, "/events"),
                      headers=_headers(creds), json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def delete_event(creds: Credentials, calendar_id: str, event_id: str) -> None:
    r = requests.delete(_cal_url(calendar_id, f"/events/{quote(event_id, safe='')}"),
                        headers=_headers(creds), timeout=_TIMEOUT)
    # 410 Gone is fine for undo (already deleted).
    if r.status_code not in (200, 204, 410):
        r.raise_for_status()


def list_today(creds: Credentials, calendar_id: str, now: datetime) -> list[dict]:
    """Events overlapping today (local midnight to next midnight)."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone()
    end = start + timedelta(days=1)
    params = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "50",
    }
    r = requests.get(_cal_url(calendar_id, "/events"),
                     headers=_headers(creds), params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json().get("items", [])
