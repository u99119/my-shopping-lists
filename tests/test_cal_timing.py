"""Tests for msl.cal.timing (pure, no network)."""

from datetime import datetime

import pytest

from msl.cal import timing


def D(h, m=0):  # helper
    return datetime(2026, 1, 15, h, m, 0)


def test_push_now_adds_buffer():
    now = D(10, 30)
    assert timing.push_now(now) == D(10, 35)
    assert timing.push_now(now, buffer_minutes=1) == D(10, 31)


def test_next_half_before_half():
    assert timing.next_half(D(5, 0)) == D(5, 30)
    assert timing.next_half(D(5, 15)) == D(5, 30)
    assert timing.next_half(D(5, 29)) == D(5, 30)


def test_next_half_at_or_after_half_rolls_to_next_hour():
    assert timing.next_half(D(5, 30)) == D(6, 30)
    assert timing.next_half(D(5, 45)) == D(6, 30)
    assert timing.next_half(D(5, 59)) == D(6, 30)


def test_next_oclock_strictly_next():
    assert timing.next_oclock(D(5, 0)) == D(6, 0)
    assert timing.next_oclock(D(5, 30)) == D(6, 0)
    assert timing.next_oclock(D(5, 59)) == D(6, 0)


def test_x_hours_from_now_user_examples():
    # At 3:00 with N=3 -> 5pm (3 is the first mark since we're at :00)
    assert timing.x_hours_from_now(D(15, 0), 3) == D(17, 0)
    # At 3:01..3:59 with N=3 -> 6pm
    assert timing.x_hours_from_now(D(15, 1), 3) == D(18, 0)
    assert timing.x_hours_from_now(D(15, 15), 3) == D(18, 0)
    assert timing.x_hours_from_now(D(15, 16), 3) == D(18, 0)
    # At 4:16 with N=3 -> 7pm
    assert timing.x_hours_from_now(D(16, 16), 3) == D(19, 0)


def test_x_hours_from_now_rejects_bad_n():
    with pytest.raises(ValueError):
        timing.x_hours_from_now(D(10, 0), 0)


def test_fixed_time_today_when_future():
    now = D(9, 0)
    assert timing.fixed_time(now, 15, 0) == D(15, 0)


def test_fixed_time_rolls_to_tomorrow_when_past():
    now = D(16, 0)
    expected = datetime(2026, 1, 16, 10, 0, 0)
    assert timing.fixed_time(now, 10, 0) == expected


def test_fixed_time_rolls_when_exactly_now():
    now = D(10, 0)
    # equal -> treated as past -> tomorrow
    assert timing.fixed_time(now, 10, 0) == datetime(2026, 1, 16, 10, 0, 0)


def test_default_time_matches_fixed_time():
    now = D(9, 0)
    assert timing.default_time(now, 15, 0) == timing.fixed_time(now, 15, 0)


def test_parse_and_format_hhmm():
    assert timing.parse_hhmm("09:00") == (9, 0)
    assert timing.parse_hhmm("23:59") == (23, 59)
    assert timing.format_hhmm(9, 5) == "09:05"


def test_parse_hhmm_rejects_bad_input():
    with pytest.raises(ValueError):
        timing.parse_hhmm("9am")
    with pytest.raises(ValueError):
        timing.parse_hhmm("24:00")
    with pytest.raises(ValueError):
        timing.parse_hhmm("10:60")
