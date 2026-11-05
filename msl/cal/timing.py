"""Time calculations for push options. Pure functions, no I/O."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional


def push_now(now: datetime, buffer_minutes: int = 5) -> datetime:
    return (now + timedelta(minutes=buffer_minutes)).replace(second=0, microsecond=0)


def next_half(now: datetime) -> datetime:
    """Strictly next :30. At HH:30 returns (HH+1):30. At HH:00 returns HH:30."""
    base = now.replace(second=0, microsecond=0)
    if base.minute < 30:
        return base.replace(minute=30)
    return (base.replace(minute=0) + timedelta(hours=1)).replace(minute=30)


def next_oclock(now: datetime) -> datetime:
    """Strictly next :00. At HH:00 returns (HH+1):00."""
    base = now.replace(second=0, microsecond=0)
    return (base.replace(minute=0) + timedelta(hours=1))


def x_hours_from_now(now: datetime, n: int) -> datetime:
    """N-th upcoming hour mark (inclusive of current hour if exactly at :00).

    Examples (n=3):
      3:00  -> 5:00  (marks: 3,4,5)
      3:16  -> 6:00  (marks: 4,5,6)
      4:16  -> 7:00
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    base = now.replace(second=0, microsecond=0)
    if base.minute == 0:
        first = base
    else:
        first = (base.replace(minute=0) + timedelta(hours=1))
    return first + timedelta(hours=n - 1)


def fixed_time(now: datetime, hh: int, mm: int = 0) -> datetime:
    """Today at HH:MM; if already past, roll to tomorrow."""
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return target


def default_time(now: datetime, hh: int, mm: int) -> datetime:
    """Phrase's default HH:MM today; if past, roll to tomorrow."""
    return fixed_time(now, hh, mm)


def parse_hhmm(s: str) -> tuple[int, int]:
    """Parse 'HH:MM' (24h) into (hour, minute). Raises ValueError on bad input."""
    parts = s.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Expected HH:MM, got {s!r}")
    hh, mm = int(parts[0]), int(parts[1])
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"Out of range: {s!r}")
    return hh, mm


def format_hhmm(hh: int, mm: int) -> str:
    return f"{hh:02d}:{mm:02d}"
