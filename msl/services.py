"""Platform layer: Android intents through pyjnius, with desktop fallbacks for development.

Nothing here needs storage permissions or a FileProvider: files are written and read through
Android's system file picker (Storage Access Framework), and sharing uses the standard chooser.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from kivy.utils import platform

IS_ANDROID = platform == "android"
HAS_FILE_PICKER = IS_ANDROID  # on desktop the UI asks for a path instead

_REQ_SAVE, _REQ_OPEN, _REQ_LOCK = 7101, 7102, 7103
_RESULT_OK = -1
_pending: dict[int, Callable] = {}
_bound = False


def _activity():
    from jnius import autoclass

    return autoclass("org.kivy.android.PythonActivity").mActivity


def _on_result(request: int, result: int, intent) -> None:
    callback = _pending.pop(request, None)
    if callback:
        callback(result == _RESULT_OK, intent)


def _start_for_result(intent, request: int, callback: Callable) -> None:
    global _bound
    if not _bound:
        from android import activity  # type: ignore[import-not-found]

        activity.bind(on_activity_result=_on_result)
        _bound = True
    _pending[request] = callback
    _activity().startActivityForResult(intent, request)


# --- sharing -------------------------------------------------------------------------------


def share_text(text: str, subject: str = "") -> str:
    """Open the Android share sheet (WhatsApp, email, ...). Desktop: copy to clipboard."""
    if IS_ANDROID:
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        intent = Intent(Intent.ACTION_SEND)
        intent.setType("text/plain")
        intent.putExtra(Intent.EXTRA_SUBJECT, subject)
        intent.putExtra(Intent.EXTRA_TEXT, text)
        _activity().startActivity(Intent.createChooser(intent, "Share list"))
        return ""
    from kivy.core.clipboard import Clipboard

    Clipboard.copy(text)
    return "Copied to clipboard"


# --- export / import files -----------------------------------------------------------------


def save_text_file(filename: str, text: str, on_done: Callable[[str], None]) -> None:
    """Let the user choose where to save ``text``; ``on_done(message)`` reports the outcome."""
    if not IS_ANDROID:
        downloads = Path.home() / "Downloads"
        target = (downloads if downloads.is_dir() else Path.home()) / filename
        target.write_text(text, encoding="utf-8")
        on_done(f"Saved to {target}")
        return

    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("application/json")
    intent.putExtra(Intent.EXTRA_TITLE, filename)

    def finished(ok: bool, data) -> None:
        if not ok or data is None:
            on_done("Export cancelled")
            return
        try:
            out = _activity().getContentResolver().openOutputStream(data.getData())
            writer = autoclass("java.io.OutputStreamWriter")(out, "UTF-8")
            writer.write(text)
            writer.flush()
            writer.close()
            on_done("Export saved")
        except Exception as exc:  # noqa: BLE001 - surface any Java error to the user
            on_done(f"Export failed: {exc}")

    _start_for_result(intent, _REQ_SAVE, finished)


def read_path(path: str) -> str:
    return Path(path).expanduser().read_text(encoding="utf-8")


def pick_text_file(on_text: Callable[[Optional[str], str], None]) -> None:
    """Android file picker. ``on_text(text, error)``: text is None on cancel/failure."""
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("*/*")

    def finished(ok: bool, data) -> None:
        if not ok or data is None:
            on_text(None, "")
            return
        try:
            stream = _activity().getContentResolver().openInputStream(data.getData())
            reader = autoclass("java.io.BufferedReader")(
                autoclass("java.io.InputStreamReader")(stream, "UTF-8")
            )
            lines = []
            while (line := reader.readLine()) is not None:
                lines.append(line)
            reader.close()
            on_text("\n".join(lines), "")
        except Exception as exc:  # noqa: BLE001
            on_text(None, f"Could not read file: {exc}")

    _start_for_result(intent, _REQ_OPEN, finished)


# --- device lock ---------------------------------------------------------------------------


def _keyguard():
    from jnius import autoclass

    return _activity().getSystemService(autoclass("android.content.Context").KEYGUARD_SERVICE)


def device_is_secure() -> bool:
    """True when the phone has a PIN / pattern / password / biometric lock set."""
    return bool(IS_ANDROID and _keyguard().isDeviceSecure())


def authenticate(on_result: Callable[[bool], None]) -> None:
    """Ask for the phone's own lock screen credential. No lock configured => allowed."""
    if not IS_ANDROID or not device_is_secure():
        on_result(True)
        return
    intent = _keyguard().createConfirmDeviceCredentialIntent("My Shopping Lists", "Unlock to continue")
    if intent is None:
        on_result(True)
        return
    _start_for_result(intent, _REQ_LOCK, lambda ok, _data: on_result(ok))
