"""Tests for the desktop (keyring) backend of msl.cal.token_store."""

from unittest.mock import patch

from msl.cal import token_store


def _force_desktop(monkeypatch):
    monkeypatch.setattr(token_store, "_is_android", lambda: False)


def test_desktop_round_trip(monkeypatch):
    _force_desktop(monkeypatch)
    store: dict[tuple[str, str], str] = {}

    def set_password(service, user, value):
        store[(service, user)] = value

    def get_password(service, user):
        return store.get((service, user))

    def delete_password(service, user):
        if (service, user) in store:
            del store[(service, user)]
        else:
            import keyring.errors

            raise keyring.errors.PasswordDeleteError

    with patch("keyring.set_password", side_effect=set_password), \
         patch("keyring.get_password", side_effect=get_password), \
         patch("keyring.delete_password", side_effect=delete_password):
        assert token_store.load() is None
        token_store.save('{"refresh_token": "abc"}')
        assert token_store.load() == '{"refresh_token": "abc"}'
        token_store.clear()
        assert token_store.load() is None


def test_desktop_clear_is_idempotent(monkeypatch):
    _force_desktop(monkeypatch)

    def delete_password(_service, _user):
        import keyring.errors

        raise keyring.errors.PasswordDeleteError

    with patch("keyring.delete_password", side_effect=delete_password):
        token_store.clear()  # must not raise
