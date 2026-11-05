"""Platform-aware config directory.

- Desktop (CLI, tests): ~/.msl-cal (override via MSL_CAL_HOME env).
- Kivy app (desktop or Android): App.user_data_dir / 'cal' when an MDApp is running.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

CONFIG_DIR_ENV = "MSL_CAL_HOME"


def _app_dir() -> Optional[Path]:
    try:
        from kivymd.app import MDApp  # imported lazily so CLI doesn't need kivymd
        app = MDApp.get_running_app()
        if app is None:
            return None
        return Path(app.user_data_dir) / "cal"
    except Exception:
        return None


def get_config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    app_dir = _app_dir()
    if app_dir is not None:
        return app_dir
    return Path.home() / ".msl-cal"


def get_config_path() -> Path:
    return get_config_dir() / "config.json"
