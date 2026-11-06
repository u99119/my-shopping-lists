# MY CAL — Design, Decisions, Progress

Branch: `feature/sl-plus-cal` (do not merge to `main` until Phase 2 is complete).

## 1. Goal

From mobile A, push an event/reminder to mobile B's Google Calendar with minimum taps.
No app install on B. Starts as a CLI; Phase 2 adds a button in the shopping-list app.

## 2. Chosen Approach

- **Shared Google Calendar with write access** (Option A).
- B shares a calendar with A granting "Make changes to events".
- A authenticates with A's own Google account via OAuth; A's refresh token is the only token involved.
- Events appear on B's Google Calendar app natively (no app on B).

## 3. Scope (Confirmed)

| Area | Decision |
|---|---|
| Auth | OAuth, weekly re-auth via in-app prompt (Google Testing-mode 7-day token lifetime) |
| Event shape | 0-duration event + popup notification at 0 min before = reminder-style |
| Max phrases | 12 |
| Row quick actions | ⚡ Push NOW (now + 5 min), 🕐 Push at default HH:MM |
| Full Push Options | NOW, default, next :30, next :00, X hrs (ceiling-next-hour +N−1), 10am/3pm/6pm/9pm |
| Fixed-time past | Auto-roll to tomorrow |
| Long-press phrase | Edit text + default HH:MM |
| Cost | $0 (Calendar API free tier, no billing needed) |

## 4. Architecture

```
msl/cal/
├── __init__.py
├── timing.py         # pure time math (fully unit-tested)
├── config.py         # ~/.msl-cal/config.json (plain JSON, non-secret)
├── auth.py           # OAuth flow + token in OS keyring
├── calendar_client.py# Google Calendar API wrapper
├── commands.py       # CLI command handlers
└── cli.py            # argparse entry point

gcal-push             # shell wrapper (repo root), activates venv + runs CLI
requirements-cal.txt  # extra deps for CLI (not in main requirements.txt)
tests/
├── test_cal_timing.py
└── test_cal_config.py
```

### Storage

| What | Where | Why |
|---|---|---|
| OAuth refresh token | OS keyring (`msl-cal` / `google-oauth-token`) | Secret → OS-encrypted store |
| calendar_id, phrases, defaults | `~/.msl-cal/config.json` plaintext | Non-secret user data |
| client_secret_*.json | Wherever user keeps it; path recorded in config | Desktop/CLI only, during OAuth. Android uses the built-in Android client (no secret) |

Overridable via env var `MSL_CAL_HOME` (used in tests).

## 5. Time Rules (verified by tests)

| Option | Rule | Example (now = 15:16) |
|---|---|---|
| NOW | now + 5 min | 15:21 |
| Default | phrase's HH:MM today; past → tomorrow | — |
| Next :30 | strictly next :30 | 15:30 |
| Next :00 | strictly next :00 | 16:00 |
| X hrs (N=3) | ceil to next hour, +(N−1) | 18:00 |
| 10 AM | today 10:00; past → tomorrow 10:00 | tomorrow 10:00 |

Edge: at exactly 15:00, X hrs N=3 → 17:00 (current hour counts as 1st mark).

## 6. CLI Surface

```
gcal-push auth [--client-secret PATH] [--email a@gmail.com]
gcal-push test
gcal-push push (--phrase N | --text "...")
               (--now | --default | --at HH:MM |
                --next-half | --next-oclock | --in-hours N)
gcal-push today
gcal-push config show
gcal-push config set-calendar <id>
gcal-push config set-client-secret <path>
gcal-push config add-phrase "text" [--at HH:MM]
gcal-push config remove-phrase <index>
gcal-push config list-phrases
gcal-push logout
```

## 7. Dependencies

Added via `requirements-cal.txt` (keeps main `requirements.txt` untouched so
Android build is not affected yet):
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client` — Google APIs
- `keyring` — OS secret store (macOS Keychain; Linux Secret Service)

Phase 2 (Android) will require adding these to `buildozer.spec` and switching the
OAuth flow from local-server redirect to an Android-friendly custom-tab flow.

## 8. Cost

- Calendar API: Always Free tier, 1M requests/day/project. Expected usage ~20/day.
- OAuth Testing mode: free, no verification needed, up to 100 Test Users.
- No billing account linked to the Google Cloud project. Confirmed by user.
- Trade-off: refresh tokens expire every 7 days → weekly in-app re-auth on A.

## 9. Security Notes

- Refresh token never logged, never printed, never put in argv/env.
- `client_secret.json` stays on disk where downloaded; only its path is in config.
- Calendar ID is treated as user data (plaintext config is fine).
- Scope is minimum needed: `calendar.events` only (no `calendar` or profile).
- B can revoke A's access anytime via Google Calendar sharing settings.

## 10. Phase Plan

### Phase 1 — CLI ✅ (this iteration)
- [x] `msl/cal/` module built
- [x] Timing + config tests (20 tests, all green; full suite 75/75 green)
- [x] `gcal-push` wrapper
- [x] Docs (this file + CAL-QUICKSTART.md)
- [ ] **User validation**: run `gcal-push auth` → `gcal-push test` → confirm event appears on B's phone
- [ ] **User validation**: push a real phrase and confirm notification on B

### Phase 2a — Desktop Kivy UI ✅ (this iteration)
- [x] `msl/cal/storage.py` — platform-aware config dir (env on desktop, `App.user_data_dir` on Android)
- [x] `msl/cal/event_service.py` — thin orchestrator used by UI (hides auth/HTTP, typed errors)
- [x] `msl/ui/widgets.py::toast_action` — snackbar with Undo button (5-sec window)
- [x] `msl/ui/cal_screen.py` — MY CAL grid, ⚡ + 🕐 per row, dots menu for Edit/Delete, long-press → Edit, today thumbnail
- [x] `msl/ui/cal_pushoptions.py` — "MY CAL (push options)" with 4 time-rule rows + −/+ X-hrs row + 4 fixed hours
- [x] `msl/ui/cal_settings.py` — Calendar ID / client_secret path / popup offset / test / re-auth / sign-out
- [x] Calendar FAB wired on `homescreen.py` (above + FAB); opens MY CAL if configured, else Settings
- [x] All screens registered in `app.py`; Android back-key routing for cal screens
- [x] Tests: 90/90 passing (3 new storage + 12 new event_service tests)

### Phase 2b — Android ✅
- [x] Hand-rolled PKCE code grant + refresh via `requests` (google-auth dropped: it needs `cryptography`)
- [x] Android Keystore via `pyjnius` for refresh-token storage
- [x] Android sign-in: Android OAuth client (package + debug-key SHA-1, "custom URI scheme" enabled, no secret).
  Google redirects to `org.u99119.myshoppinglists:/oauth2redirect`; `android_intent_filters.xml` routes it to
  the running app (`services.listen_for_uri`). A 127.0.0.1 server cannot work on Android: background apps
  get their incoming traffic dropped while the browser is in front.
- [x] APK build + on-device validation
- Release builds signed with another key need a second Android client with that key's SHA-1

### Phase 3 — Polish (deferred)
- Offline queue (retry on reconnect)
- Per-phrase duration override UI

## 11. Open / Deferred

- Should we move to Published OAuth to avoid 7-day token expiry? Deferred (verification is heavy for personal app)
- Per-phrase duration override UI (CLI supports via config; UI pending Phase 2)

## 12. Test Coverage

- `tests/test_cal_timing.py` — 12 tests; covers all 6 time functions + parse/format + edge rolls
- `tests/test_cal_config.py` — 8 tests; roundtrip, max-12 limit, empty-text rejection, update, remove
- `tests/test_cal_storage.py` — 3 tests; env override, `~` expansion, default fallback
- `tests/test_cal_event_service.py` — 16 tests; is_configured (incl. Android without secret), resolve_when branches, push validation + mocked create/undo, x_hours persistence, AuthRequired propagation, Android sign-in (redirect scheme, no secret, state check), refresh without secret
- Real network paths (`calendar_client.py`, token endpoint) not unit-tested; validated by `gcal-push test` and on-device sign-in.
