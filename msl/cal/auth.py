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

import datetime
import hashlib
import json
import secrets
import socketserver
import threading
import urllib.parse
import wsgiref.simple_server
from pathlib import Path
from typing import Callable, Optional

import requests as _requests

from . import token_store
from ._credentials import Credentials

# NOTE: google-auth / google-auth-oauthlib are deliberately NOT imported here.
# They transitively pull google.auth.crypt.es → cryptography, whose native
# extensions don't build cleanly for Android. OAuth2 is simple enough to do by
# hand against the public token endpoint using just `requests`.
_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_SUCCESS_HTML = (b"<html><head><meta charset=utf-8></head><body style='font-family:"
                 b"sans-serif;padding:24px'><h3>Authentication complete.</h3>"
                 b"<p>You can close this tab and return to the app.</p></body></html>")


class _CallbackApp:
    """Minimal WSGI app that captures the OAuth redirect URL.

    Only a request carrying ``code`` or ``error`` counts as the callback; other
    requests (favicon, browser probes) get a 404 and are ignored.
    """

    def __init__(self) -> None:
        self.last_uri: Optional[str] = None
        self.done = threading.Event()

    def __call__(self, environ, start_response):
        host = environ.get("HTTP_HOST", "127.0.0.1")
        path = environ.get("PATH_INFO", "/")
        qs = environ.get("QUERY_STRING", "")
        params = urllib.parse.parse_qs(qs)
        is_callback = "code" in params or "error" in params
        print(f"[auth] http request path={path} callback={is_callback}", flush=True)
        if not is_callback:
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b""]
        self.last_uri = f"http://{host}{path}?{qs}"
        self.done.set()
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [_SUCCESS_HTML]


class _ThreadingWSGIServer(socketserver.ThreadingMixIn, wsgiref.simple_server.WSGIServer):
    daemon_threads = True


class _QuietHandler(wsgiref.simple_server.WSGIRequestHandler):
    timeout = 10  # per-connection socket timeout; idle pre-connects can't stall the server

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass  # default access log would print the query string (auth code)


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
def _load_client_config(path: Path) -> tuple[str, str]:
    """Return (client_id, client_secret) from a Google client_secret JSON file.

    Accepts both ``installed`` (desktop app) and ``web`` (web app) shapes.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    block = data.get("installed") or data.get("web")
    if not block:
        raise RuntimeError("client_secret JSON missing 'installed' / 'web' section")
    return block["client_id"], block["client_secret"]


def _pkce_pair() -> tuple[str, str]:
    """Generate (code_verifier, code_challenge) per RFC 7636."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    import base64
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _extract_code(redirect_uri: str) -> str:
    qs = urllib.parse.urlparse(redirect_uri).query
    params = urllib.parse.parse_qs(qs)
    if "error" in params:
        raise RuntimeError(f"OAuth error: {params['error'][0]}")
    codes = params.get("code") or []
    if not codes:
        raise RuntimeError("OAuth callback had no 'code' parameter")
    return codes[0]


def _loopback_flow(client_secret_path: str) -> Credentials:
    """Run the full OAuth code grant through a local 127.0.0.1 HTTP server.

    Called from both the sync (CLI) and async (UI) paths. Blocks the calling
    thread until the user completes consent in the system browser. Uses PKCE
    so the client_secret never touches the browser redirect.
    """
    from .. import services  # lazy: services imports kivy which pytest should avoid

    p = Path(client_secret_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"client_secret file not found: {p}")
    client_id, client_secret = _load_client_config(p)

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    cb = _CallbackApp()
    server = wsgiref.simple_server.make_server(
        "127.0.0.1", 0, cb,
        server_class=_ThreadingWSGIServer, handler_class=_QuietHandler)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.5},
                     daemon=True).start()
    try:
        redirect_uri = f"http://127.0.0.1:{server.server_port}/"
        auth_url = _AUTH_URI + "?" + urllib.parse.urlencode({
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        print(f"[auth] loopback server bound at {redirect_uri}", flush=True)
        if not services.open_url(auth_url):
            raise RuntimeError("Could not launch system browser for sign-in.")
        print("[auth] waiting for OAuth redirect (timeout 300s)...", flush=True)
        cb.done.wait(300)
        print(f"[auth] wait finished; last_uri={bool(cb.last_uri)}", flush=True)
    finally:
        server.shutdown()
        server.server_close()

    if not cb.last_uri:
        raise RuntimeError(
            "Sign-in timed out — the browser did not redirect back to the app. "
            "This usually means Chrome blocked the 127.0.0.1 redirect."
        )
    code = _extract_code(cb.last_uri)
    resp = _requests.post(_TOKEN_URI, data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }, timeout=20)
    resp.raise_for_status()
    body = resp.json()
    expires_in = int(body.get("expires_in", 3600))
    creds = Credentials(
        token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        token_uri=_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(SCOPES),
        expiry=datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in),
    )
    save_credentials(creds)
    return creds


def run_oauth_flow(client_secret_path: str) -> Credentials:
    """Backwards-compatible name used by the CLI; synchronous."""
    return _loopback_flow(client_secret_path)


# -------------------------------------------------- sync entry (CLI / tests)
def _refresh(creds: Credentials) -> None:
    """Refresh an expired access token in place, without google.auth.transport.

    Google's OAuth2 refresh is a single POST to the token endpoint; doing it by
    hand lets us skip the Request() import that drags in cryptography.
    """
    resp = _requests.post(
        creds.token_uri or "https://oauth2.googleapis.com/token",
        data={
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "refresh_token": creds.refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    creds.token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    creds.expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)


def ensure_credentials(client_secret_path: Optional[str]) -> Credentials:
    """Return valid creds, refreshing or re-prompting as needed. Blocks."""
    creds = load_credentials()
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            _refresh(creds)
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
        print("[auth.worker] thread started", flush=True)
        try:
            creds = ensure_credentials(client_secret_path)
            print("[auth.worker] ensure_credentials returned OK", flush=True)
            deliver(creds, None)
        except BaseException as exc:  # noqa: BLE001 - surface all to UI
            import traceback
            print(f"[auth.worker] exception: {exc!r}", flush=True)
            traceback.print_exc()
            deliver(None, exc)

    print("[auth] spawning worker thread", flush=True)
    threading.Thread(target=worker, daemon=True).start()
