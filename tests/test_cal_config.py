"""Tests for msl.cal.config (local JSON, no network)."""

import pytest

from msl.cal import config as cfgmod


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv(cfgmod.CONFIG_DIR_ENV, str(tmp_path))
    return tmp_path


def test_load_returns_empty_when_missing(tmp_home):
    cfg = cfgmod.load()
    assert cfg.calendar_id is None
    assert cfg.phrases == []


def test_save_and_load_roundtrip(tmp_home):
    cfg = cfgmod.Config(calendar_id="abc@group.calendar.google.com",
                        client_secret_path="/tmp/secret.json",
                        account_email="a@example.com")
    cfgmod.add_phrase(cfg, "Walk the dog", 7, 30)
    cfgmod.add_phrase(cfg, "Take meds", 22, 0)
    cfgmod.save(cfg)

    loaded = cfgmod.load()
    assert loaded.calendar_id == cfg.calendar_id
    assert loaded.account_email == "a@example.com"
    assert [p.text for p in loaded.phrases] == ["Walk the dog", "Take meds"]
    assert loaded.phrases[0].default_hh == 7


def test_add_phrase_limit(tmp_home):
    cfg = cfgmod.Config()
    for i in range(cfgmod.MAX_PHRASES):
        cfgmod.add_phrase(cfg, f"p{i}")
    with pytest.raises(ValueError, match="limit"):
        cfgmod.add_phrase(cfg, "one too many")


def test_add_phrase_rejects_empty(tmp_home):
    cfg = cfgmod.Config()
    with pytest.raises(ValueError):
        cfgmod.add_phrase(cfg, "   ")


def test_remove_phrase(tmp_home):
    cfg = cfgmod.Config()
    cfgmod.add_phrase(cfg, "a")
    cfgmod.add_phrase(cfg, "b")
    removed = cfgmod.remove_phrase(cfg, 0)
    assert removed.text == "a"
    assert [p.text for p in cfg.phrases] == ["b"]


def test_remove_phrase_out_of_range(tmp_home):
    cfg = cfgmod.Config()
    with pytest.raises(IndexError):
        cfgmod.remove_phrase(cfg, 0)


def test_update_phrase(tmp_home):
    cfg = cfgmod.Config()
    cfgmod.add_phrase(cfg, "orig", 9, 0)
    cfgmod.update_phrase(cfg, 0, text="new", hh=18, mm=45)
    p = cfg.phrases[0]
    assert (p.text, p.default_hh, p.default_mm) == ("new", 18, 45)


def test_update_phrase_rejects_empty_text(tmp_home):
    cfg = cfgmod.Config()
    cfgmod.add_phrase(cfg, "orig")
    with pytest.raises(ValueError):
        cfgmod.update_phrase(cfg, 0, text="  ")
