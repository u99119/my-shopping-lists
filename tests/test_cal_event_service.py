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


# ------------------------------------------------- Android sign-in (custom URI scheme)
@pytest.fixture
def android(monkeypatch):
    monkeypatch.setattr(svc.auth.token_store, "_is_android", lambda: True)


class _FakeServices:
    """Stands in for msl.services: 'opening' the URL immediately delivers a redirect."""

    def __init__(self, redirect_for):
        self.redirect_for = redirect_for  # (prefix, state) -> uri or None
        self.listeners = {}

    def listen_for_uri(self, prefix, callback):
        self.listeners[prefix] = callback
        return lambda: self.listeners.pop(prefix, None)

    def open_url(self, url):
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(url).query)
        self.opened = q
        uri = self.redirect_for(q["redirect_uri"][0], q["state"][0])
        if uri:
            self.listeners[q["redirect_uri"][0]](uri)
        return True


def _run_android_flow(monkeypatch, redirect_for):
    import msl
    fake = _FakeServices(redirect_for)
    monkeypatch.setitem(__import__("sys").modules, "msl.services", fake)
    monkeypatch.setattr(msl, "services", fake, raising=False)
    monkeypatch.setattr(svc.auth, "load_credentials", lambda: None)
    monkeypatch.setattr(svc.auth, "save_credentials", lambda _c: None)
    resp = MagicMock()
    resp.json.return_value = {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}
    with patch.object(svc.auth._requests, "post", return_value=resp) as post:
        creds = svc.auth.ensure_credentials(None)
    return fake, post, creds


def test_is_configured_on_android_without_client_secret(tmp_home, android):
    cfgmod.save(cfgmod.Config(calendar_id="cal@group.calendar.google.com"))
    assert svc.is_configured() is True


def test_android_sign_in_uses_redirect_scheme_and_no_secret(monkeypatch, android):
    fake, post, creds = _run_android_flow(
        monkeypatch, lambda prefix, state: f"{prefix}?state={state}&code=CODE123&scope=x")
    assert fake.opened["client_id"] == [svc.auth.ANDROID_CLIENT_ID]
    assert fake.opened["code_challenge_method"] == ["S256"]
    data = post.call_args.kwargs["data"]
    assert data["code"] == "CODE123"
    assert data["redirect_uri"] == svc.auth.ANDROID_REDIRECT_URI
    assert data["code_verifier"]
    assert "client_secret" not in data
    assert creds.token == "at" and creds.refresh_token == "rt" and creds.client_secret is None
    assert fake.listeners == {}  # stopped listening


def test_android_sign_in_rejects_wrong_state(monkeypatch, android):
    with pytest.raises(RuntimeError, match="state mismatch"):
        _run_android_flow(monkeypatch, lambda prefix, _s: f"{prefix}?state=forged&code=X")


def test_refresh_without_client_secret_omits_it():
    creds = svc.auth.Credentials(token="old", refresh_token="rt", client_id="cid")
    resp = MagicMock()
    resp.json.return_value = {"access_token": "new", "expires_in": 3600}
    with patch.object(svc.auth._requests, "post", return_value=resp) as post:
        svc.auth._refresh(creds)
    assert "client_secret" not in post.call_args.kwargs["data"]
    assert creds.token == "new"
