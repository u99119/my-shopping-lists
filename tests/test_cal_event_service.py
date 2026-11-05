"""Tests for msl.cal.event_service orchestrator (no network)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from msl.cal import config as cfgmod
from msl.cal import event_service as svc


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv(cfgmod.CONFIG_DIR_ENV, str(tmp_path))
    return tmp_path


@pytest.fixture
def seeded_cfg(tmp_home):
    cfg = cfgmod.Config(calendar_id="cal@group.calendar.google.com",
                        client_secret_path="/tmp/secret.json")
    cfgmod.add_phrase(cfg, "Walk the dog", 8, 0)
    cfgmod.save(cfg)
    return cfg


def test_is_configured_false_when_missing(tmp_home):
    assert svc.is_configured() is False


def test_is_configured_true_when_both_set(seeded_cfg):
    assert svc.is_configured() is True


def test_resolve_when_now(seeded_cfg):
    now = datetime(2026, 1, 1, 10, 0).astimezone()
    assert svc.resolve_when("now", now=now).minute == 5


def test_resolve_when_default_requires_phrase(seeded_cfg):
    with pytest.raises(ValueError, match="default"):
        svc.resolve_when("default", now=datetime.now().astimezone())


def test_resolve_when_unknown_option(seeded_cfg):
    with pytest.raises(ValueError, match="Unknown"):
        svc.resolve_when("bogus", now=datetime.now().astimezone())


def test_push_requires_configured_calendar(tmp_home):
    with pytest.raises(svc.ConfigError):
        svc.push(phrase_index=None, text="x", option="now")


def test_push_out_of_range_phrase(seeded_cfg):
    with pytest.raises(ValueError, match="out of range"):
        svc.push(phrase_index=99, text=None, option="now")


def test_push_requires_text_or_phrase(seeded_cfg):
    with pytest.raises(ValueError, match="required"):
        svc.push(phrase_index=None, text=None, option="now")


def test_push_calls_create_event_with_phrase(seeded_cfg):
    fake_creds = object()
    fake_event = {"id": "evt-123"}
    with patch.object(svc.auth, "ensure_credentials", return_value=fake_creds), \
         patch.object(svc.cc, "create_event", return_value=fake_event) as create:
        res = svc.push(phrase_index=0, text=None, option="now")
    assert res.event_id == "evt-123"
    assert res.text == "Walk the dog"
    create.assert_called_once()
    _, kwargs = create.call_args
    # positional args: creds, calendar_id, summary, when
    args = create.call_args.args
    assert args[1] == "cal@group.calendar.google.com"
    assert args[2] == "Walk the dog"


def test_push_x_hours_persists_last_value(seeded_cfg):
    with patch.object(svc.auth, "ensure_credentials", return_value=object()), \
         patch.object(svc.cc, "create_event", return_value={"id": "e"}):
        svc.push(phrase_index=0, text=None, option="x_hours", x_hours=7)
    assert cfgmod.load().last_x_hours == 7


def test_push_auth_error_raises_auth_required(seeded_cfg):
    with patch.object(svc.auth, "ensure_credentials",
                      side_effect=RuntimeError("no token")):
        with pytest.raises(svc.AuthRequiredError):
            svc.push(phrase_index=0, text=None, option="now")


def test_undo_calls_delete(seeded_cfg):
    with patch.object(svc.auth, "ensure_credentials", return_value=object()), \
         patch.object(svc.cc, "delete_event") as delete:
        svc.undo("evt-xyz")
    delete.assert_called_once()
    assert delete.call_args.args[2] == "evt-xyz"
