"""OAuth flow (InstalledAppFlow) + refresh-token storage in OS keyring.

Phase 1 (CLI/desktop): uses google_auth_oauthlib's local-server redirect.
Phase 2 (Android): will be swapped for a custom-tab / system-browser flow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
KEYRING_SERVICE = "msl-cal"
KEYRING_USERNAME = "google-oauth-token"


def _creds_to_json(creds: Credentials) -> str:
    return creds.to_json()


def _creds_from_json(s: str) -> Credentials:
    data = json.loads(s)
    return Credentials.from_authorized_user_info(data, SCOPES)


def load_credentials() -> Optional[Credentials]:
    s = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    if not s:
        return None
    try:
        return _creds_from_json(s)
    except Exception:
        return None


def save_credentials(creds: Credentials) -> None:
    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, _creds_to_json(creds))


def clear_credentials() -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass


def run_oauth_flow(client_secret_path: str) -> Credentials:
    """Open a local browser for consent. Blocks until user approves. Saves creds."""
    p = Path(client_secret_path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"client_secret file not found: {p}")
    flow = InstalledAppFlow.from_client_secrets_file(str(p), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    save_credentials(creds)
    return creds


def ensure_credentials(client_secret_path: Optional[str]) -> Credentials:
    """Return valid creds, refreshing or re-prompting as needed."""
    creds = load_credentials()
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_credentials(creds)
            return creds
        except Exception:
            pass  # refresh failed (e.g. 7-day testing-mode expiry); fall through to re-auth
    if not client_secret_path:
        raise RuntimeError(
            "Need to re-authenticate but client_secret_path is not configured. "
            "Run: gcal-push config set-client-secret <path>"
        )
    return run_oauth_flow(client_secret_path)
