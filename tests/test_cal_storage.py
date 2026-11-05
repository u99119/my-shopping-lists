"""Tests for msl.cal.storage platform-aware path resolution."""

from pathlib import Path

from msl.cal import storage


def test_env_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv(storage.CONFIG_DIR_ENV, str(tmp_path))
    assert storage.get_config_dir() == tmp_path
    assert storage.get_config_path() == tmp_path / "config.json"


def test_env_override_expands_user(monkeypatch):
    monkeypatch.setenv(storage.CONFIG_DIR_ENV, "~/custom-cal-dir")
    assert storage.get_config_dir() == Path.home() / "custom-cal-dir"


def test_default_without_env_and_without_app(monkeypatch):
    monkeypatch.delenv(storage.CONFIG_DIR_ENV, raising=False)
    # No MDApp running in pytest -> _app_dir() returns None -> fall back to ~/.msl-cal
    assert storage.get_config_dir() == Path.home() / ".msl-cal"
