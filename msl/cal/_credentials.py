"""Minimal OAuth2 user credentials holder.

Replaces ``google.oauth2.credentials.Credentials`` so Android builds don't
need the ``cryptography`` native extension (pulled in transitively by
``google-auth`` through ``google.auth.crypt.es``).

JSON shape is kept compatible with ``google.oauth2.credentials.Credentials.to_json``
so existing stored tokens continue to load.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from typing import List, Optional

_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
# Refresh a few seconds before expiry to avoid racing a 401.
_EXPIRY_SKEW_SEC = 60


def _parse_expiry(value) -> Optional[_dt.datetime]:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        # google-auth writes "YYYY-MM-DDTHH:MM:SS.ffffff" (naive UTC) or ISO with Z.
        s = value.rstrip("Z")
        try:
            return _dt.datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


@dataclass
class Credentials:
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_uri: str = _DEFAULT_TOKEN_URI
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scopes: List[str] = field(default_factory=list)
    expiry: Optional[_dt.datetime] = None  # naive UTC, matching google-auth

    @property
    def expired(self) -> bool:
        if self.expiry is None:
            return False
        now = _dt.datetime.utcnow()
        return now >= (self.expiry - _dt.timedelta(seconds=_EXPIRY_SKEW_SEC))

    @property
    def valid(self) -> bool:
        return bool(self.token) and not self.expired

    # --------------------------------------------------------------- (de)serialize
    @classmethod
    def from_authorized_user_info(cls, info: dict, scopes: Optional[List[str]] = None) -> "Credentials":
        return cls(
            token=info.get("token") or info.get("access_token"),
            refresh_token=info.get("refresh_token"),
            token_uri=info.get("token_uri") or _DEFAULT_TOKEN_URI,
            client_id=info.get("client_id"),
            client_secret=info.get("client_secret"),
            scopes=list(info.get("scopes") or scopes or []),
            expiry=_parse_expiry(info.get("expiry")),
        )

    def to_json(self) -> str:
        return json.dumps({
            "token": self.token,
            "refresh_token": self.refresh_token,
            "token_uri": self.token_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scopes": list(self.scopes),
            "expiry": self.expiry.isoformat() if self.expiry else None,
        })
