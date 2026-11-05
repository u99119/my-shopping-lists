"""Orchestrator used by UI. Hides credentials/HTTP; returns simple types.

UI layer (msl/ui/cal_*) never imports auth/calendar_client/Google libs directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from . import auth, calendar_client as cc, config as cfgmod, timing


class ConfigError(Exception):
    """Config is incomplete (missing calendar_id or client_secret)."""


class AuthRequiredError(Exception):
    """User must re-auth (no token, or refresh failed)."""


@dataclass
class PushResult:
    event_id: str
    when: datetime
    text: str


OPTIONS = ("now", "default", "next_half", "next_oclock", "x_hours", "fixed")


def _require_cfg(require_cal: bool = True) -> cfgmod.Config:
    cfg = cfgmod.load()
    if require_cal and not cfg.calendar_id:
        raise ConfigError("calendar_id not set")
    return cfg


def _creds(cfg: cfgmod.Config):
    try:
        return auth.ensure_credentials(cfg.client_secret_path)
    except Exception as exc:  # noqa: BLE001 - surface anything auth-related as AuthRequired
        raise AuthRequiredError(str(exc)) from exc


def resolve_when(option: str, now: Optional[datetime] = None,
                 phrase: Optional[cfgmod.Phrase] = None,
                 x_hours: int = cfgmod.DEFAULT_X_HOURS,
                 fixed_hh: int = 10, fixed_mm: int = 0) -> datetime:
    now = now or datetime.now().astimezone()
    if option == "now":
        return timing.push_now(now)
    if option == "default":
        if not phrase:
            raise ValueError("'default' needs a phrase")
        return timing.default_time(now, phrase.default_hh, phrase.default_mm)
    if option == "next_half":
        return timing.next_half(now)
    if option == "next_oclock":
        return timing.next_oclock(now)
    if option == "x_hours":
        return timing.x_hours_from_now(now, x_hours)
    if option == "fixed":
        return timing.fixed_time(now, fixed_hh, fixed_mm)
    raise ValueError(f"Unknown option: {option}")


def push(phrase_index: Optional[int], text: Optional[str], option: str, **kwargs) -> PushResult:
    cfg = _require_cfg()
    phrase: Optional[cfgmod.Phrase] = None
    if phrase_index is not None:
        if not (0 <= phrase_index < len(cfg.phrases)):
            raise ValueError(f"Phrase index {phrase_index} out of range")
        phrase = cfg.phrases[phrase_index]
        text = phrase.text
    if not text:
        raise ValueError("Either phrase_index or text is required")
    when = resolve_when(option, phrase=phrase, **kwargs)
    duration = phrase.duration_min if phrase else cfgmod.DEFAULT_DURATION_MIN
    if option == "x_hours":
        cfg.last_x_hours = int(kwargs.get("x_hours", cfg.last_x_hours))
        cfgmod.save(cfg)
    creds = _creds(cfg)
    ev = cc.create_event(creds, cfg.calendar_id, text, when,
                         duration_min=duration, popup_offset_min=cfg.popup_offset_min)
    return PushResult(event_id=ev["id"], when=when, text=text)


def undo(event_id: str) -> None:
    cfg = _require_cfg()
    creds = _creds(cfg)
    cc.delete_event(creds, cfg.calendar_id, event_id)


def test_connection() -> None:
    """Create + delete a dummy event. Raises on any failure."""
    cfg = _require_cfg()
    creds = _creds(cfg)
    now = datetime.now().astimezone()
    ev = cc.create_event(creds, cfg.calendar_id, "MY CAL test — safe to ignore",
                         timing.push_now(now, buffer_minutes=1),
                         duration_min=0, popup_offset_min=cfg.popup_offset_min)
    cc.delete_event(creds, cfg.calendar_id, ev["id"])


def today_events() -> list[dict]:
    cfg = _require_cfg()
    creds = _creds(cfg)
    return cc.list_today(creds, cfg.calendar_id, datetime.now().astimezone())


def is_configured() -> bool:
    cfg = cfgmod.load()
    return bool(cfg.calendar_id and cfg.client_secret_path)
