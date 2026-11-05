"""OAuth flow + token storage.

Desktop (CLI, tests): ``ensure_credentials`` is synchronous, uses blocking
``InstalledAppFlow``.  Kivy (desktop or Android): ``ensure_credentials_async``
runs the loopback flow on a background thread and delivers credentials back on
Kivy's main thread via ``Clock.schedule_once``.

On both platforms the browser is launched via ``services.open_url`` so the
same code path works everywhere (webbrowser on desktop, Intent on Android).
Token blobs are persisted through :mod:`.token_store` (OS keyring on desktop,
Keystore-encrypted file on Android).
"""

from __future__ import annotations

import json
import threading
import wsgiref.simple_server
from pathlib import Path
from typing import Callable, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import token_store

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_SUCCESS_HTML = (b"<html><head><meta charset=utf-8></head><body style='font-family:"
                 b"sans-serif;padding:24px'><h3>Authentication complete.</h3>"
                 b"<p>You can close this tab and return to the app.</p></body></html>")


class _CallbackApp:
    """Minimal WSGI app that captures the OAuth redirect URL."""

    def __init__(self) -> None:
        self.last_uri: Optional[str] = None

    def __call__(self, environ, start_response):
        host = environ.get("HTTP_HOST", "127.0.0.1")
        path = environ.get("PATH_INFO", "/")
        qs = environ.get("QUERY_STRING", "")
        self.last_uri = f"http://{host}{path}" + (f"?{qs}" if qs else "")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [_SUCCESS_HTML]


# ----------------------------------------------------------------- token I/O
def load_credentials() -> Optional[Credentials]:
    s = token_store.load()
    if not s:
        return None
    try:
        return Credentials.from_authorized_user_info(json.loads(s), SCOPES)
    except Exception:
        return None


def save_credentials(creds: Credentials) -> None:
    token_store.save(creds.to_json())


def clear_credentials() -> None:
    token_store.clear()


# ---------------------------------------------------------- shared loopback
def _loopback_flow(client_secret_path: str) -> Credentials:
    """Run the full OAuth code grant through a local 127.0.0.1 HTTP server.

    Called from both the sync (CLI) and async (UI) paths. Blocks the calling
    thread until the user completes consent in the system browser.
    """
    from .. import services  # lazy: services imports kivy which pytest should avoid

    p = Path(client_secret_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"client_secret file not found: {p}")

    flow = InstalledAppFlow.from_client_secrets_file(str(p), SCOPES)
    app = _CallbackApp()
    server = wsgiref.simple_server.make_server("127.0.0.1", 0, app)
    try:
        flow.redirect_uri = f"http://127.0.0.1:{server.server_port}/"
        auth_url, _state = flow.authorization_url(
            prompt="consent", access_type="offline")
        services.open_url(auth_url)
        server.handle_request()  # blocks until first request (the redirect)
    finally:
        server.server_close()

    if not app.last_uri:
        raise RuntimeError("OAuth callback never reached the local server.")
    # fetch_token requires https-scheme redirect_uri internally
    flow.fetch_token(authorization_response=app.last_uri.replace("http://", "https://", 1))
    creds = flow.credentials
    save_credentials(creds)
    return creds


def run_oauth_flow(client_secret_path: str) -> Credentials:
    """Backwards-compatible name used by the CLI; synchronous."""
    return _loopback_flow(client_secret_path)


# -------------------------------------------------- sync entry (CLI / tests)
def ensure_credentials(client_secret_path: Optional[str]) -> Credentials:
    """Return valid creds, refreshing or re-prompting as needed. Blocks."""
    creds = load_credentials()
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return creds
        except Exception:
            pass  # refresh failed → fall through to re-auth
    if not client_secret_path:
        raise RuntimeError(
            "Need to re-authenticate but client_secret_path is not configured. "
            "Run: gcal-push config set-client-secret <path>"
        )
    return _loopback_flow(client_secret_path)


# --------------------------------------------------------- async entry (UI)
def ensure_credentials_async(
    client_secret_path: Optional[str],
    on_done: Callable[[Optional[Credentials], Optional[BaseException]], None],
) -> None:
    """Call ``on_done(creds, None)`` on success, ``on_done(None, exc)`` on error.

    Always delivers on Kivy's main thread via ``Clock.schedule_once``. Returns
    immediately; the browser launch and server wait run on a background thread.
    """
    from kivy.clock import Clock

    def deliver(creds: Optional[Credentials], exc: Optional[BaseException]) -> None:
        Clock.schedule_once(lambda _dt: on_done(creds, exc), 0)

    def worker() -> None:
        try:
            deliver(ensure_credentials(client_secret_path), None)
        except BaseException as exc:  # noqa: BLE001 - surface all to UI
            deliver(None, exc)

    threading.Thread(target=worker, daemon=True).start()
