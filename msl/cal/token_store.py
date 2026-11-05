"""Platform-aware OAuth-token storage.

Desktop: OS keyring (macOS Keychain, Linux Secret Service, Windows Credential Manager).
Android: AES-GCM via AndroidKeyStore; ciphertext stored in app-private config dir.

Public API:
    load() -> Optional[str]
    save(blob: str) -> None
    clear() -> None
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import storage

KEYRING_SERVICE = "msl-cal"
KEYRING_USERNAME = "google-oauth-token"

# Length-prefixed on-disk layout:  [1 byte IV length][IV][ciphertext]
_IV_LEN_BYTES = 1


def _is_android() -> bool:
    # Lazy import so the CLI (and pytest on desktop) never touches kivy.utils.
    try:
        from kivy.utils import platform
    except Exception:
        return False
    return platform == "android"


def _android_path() -> Path:
    return storage.get_config_dir() / "token.enc"


# ------------------------------------------------------------------- desktop
def _desktop_load() -> Optional[str]:
    import keyring

    return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)


def _desktop_save(blob: str) -> None:
    import keyring

    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, blob)


def _desktop_clear() -> None:
    import keyring
    import keyring.errors

    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass


# ------------------------------------------------------------------- android
def _android_load() -> Optional[str]:
    p = _android_path()
    if not p.exists():
        return None
    data = p.read_bytes()
    if len(data) < _IV_LEN_BYTES + 1:
        return None
    iv_len = data[0]
    iv = data[1:1 + iv_len]
    ct = data[1 + iv_len:]
    from . import android_keystore

    try:
        return android_keystore.decrypt(iv, ct).decode("utf-8")
    except Exception:
        return None


def _android_save(blob: str) -> None:
    from . import android_keystore

    iv, ct = android_keystore.encrypt(blob.encode("utf-8"))
    if len(iv) > 255:
        raise RuntimeError("IV too long to length-prefix in 1 byte")
    p = _android_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(bytes([len(iv)]) + iv + ct)


def _android_clear() -> None:
    p = _android_path()
    if p.exists():
        p.unlink()
    try:
        from . import android_keystore

        android_keystore.delete_key()
    except Exception:
        pass


# ------------------------------------------------------------------- dispatch
def load() -> Optional[str]:
    return _android_load() if _is_android() else _desktop_load()


def save(blob: str) -> None:
    (_android_save if _is_android() else _desktop_save)(blob)


def clear() -> None:
    (_android_clear if _is_android() else _desktop_clear)()
