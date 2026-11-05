"""Thin Google Calendar wrapper: create / delete / list events."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def _service(creds: Credentials):
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _local_tz_name() -> str:
    """IANA tz name for the local system, with safe fallback."""
    try:
        return datetime.now().astimezone().tzinfo.key  # type: ignore[attr-defined]
    except Exception:
        return "UTC"


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
    return _service(creds).events().insert(calendarId=calendar_id, body=body).execute()


def delete_event(creds: Credentials, calendar_id: str, event_id: str) -> None:
    _service(creds).events().delete(calendarId=calendar_id, eventId=event_id).execute()


def list_today(creds: Credentials, calendar_id: str, now: datetime) -> list[dict]:
    """Events overlapping today (local midnight to next midnight)."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone()
    end = start + timedelta(days=1)
    resp = (
        _service(creds)
        .events()
        .list(
            calendarId=calendar_id,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        )
        .execute()
    )
    return resp.get("items", [])
