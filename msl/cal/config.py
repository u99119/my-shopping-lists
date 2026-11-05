"""Local config for MY CAL. Plain JSON at ~/.msl-cal/config.json.

Not a secret: calendar ID, phrases, defaults, client_secret.json path.
OAuth tokens live in the OS keyring (see auth.py).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

MAX_PHRASES = 12
DEFAULT_DURATION_MIN = 0      # 0-duration event (reminder-like)
DEFAULT_POPUP_OFFSET_MIN = 0  # notification at event time
DEFAULT_X_HOURS = 3

CONFIG_DIR_ENV = "MSL_CAL_HOME"


@dataclass
class Phrase:
    text: str
    default_hh: int = 9
    default_mm: int = 0
    duration_min: int = DEFAULT_DURATION_MIN


@dataclass
class Config:
    calendar_id: Optional[str] = None
    client_secret_path: Optional[str] = None
    account_email: Optional[str] = None
    phrases: list[Phrase] = field(default_factory=list)
    last_x_hours: int = DEFAULT_X_HOURS
    popup_offset_min: int = DEFAULT_POPUP_OFFSET_MIN

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "Config":
        d = json.loads(s)
        phrases = [Phrase(**p) for p in d.pop("phrases", [])]
        return cls(phrases=phrases, **d)


def config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".msl-cal"


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> Config:
    p = config_path()
    if not p.exists():
        return Config()
    return Config.from_json(p.read_text())


def save(cfg: Config) -> None:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    config_path().write_text(cfg.to_json())


def add_phrase(cfg: Config, text: str, hh: int = 9, mm: int = 0) -> Phrase:
    if len(cfg.phrases) >= MAX_PHRASES:
        raise ValueError(f"Phrase limit reached ({MAX_PHRASES}). Delete one first.")
    text = text.strip()
    if not text:
        raise ValueError("Phrase text cannot be empty.")
    p = Phrase(text=text, default_hh=hh, default_mm=mm)
    cfg.phrases.append(p)
    return p


def remove_phrase(cfg: Config, index: int) -> Phrase:
    if not (0 <= index < len(cfg.phrases)):
        raise IndexError(f"Phrase index {index} out of range (0..{len(cfg.phrases) - 1}).")
    return cfg.phrases.pop(index)


def update_phrase(
    cfg: Config,
    index: int,
    text: Optional[str] = None,
    hh: Optional[int] = None,
    mm: Optional[int] = None,
) -> Phrase:
    if not (0 <= index < len(cfg.phrases)):
        raise IndexError(f"Phrase index {index} out of range.")
    p = cfg.phrases[index]
    if text is not None:
        text = text.strip()
        if not text:
            raise ValueError("Phrase text cannot be empty.")
        p.text = text
    if hh is not None:
        p.default_hh = hh
    if mm is not None:
        p.default_mm = mm
    return p
