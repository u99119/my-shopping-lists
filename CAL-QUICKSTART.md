# MY CAL — Quick Start

Branch: `feature/sl-plus-cal`. Phase 1 = CLI only.

## 1. One-time setup

### On B's side
1. Open https://calendar.google.com (signed in as B)
2. Create a new calendar (e.g. "Shared with A")
3. Settings → **Share with specific people** → add A's Gmail → permission = **Make changes to events**
4. Settings → **Integrate calendar** → copy the **Calendar ID** → send to A

### On A's Mac
```bash
cd /Users/maysingh/c/github/my-shopping-lists
source .venv/bin/activate
pip install -r requirements-cal.txt    # already done; safe to re-run

# Point the CLI at your downloaded client_secret file + the calendar ID B sent you
./gcal-push config set-client-secret /Users/maysingh/Downloads/client_secret_989058260277-59b736u3k2q8ccqp6nsd10jadv5k024k.apps.googleusercontent.com.json
./gcal-push config set-calendar '<the calendar ID B sent you>'

# Authenticate (opens a browser; sign in as A, grant Calendar access)
./gcal-push auth --email <your-A-gmail>

# Validate: creates then deletes a dummy event
./gcal-push test
```

Expected: `Deleted. Sharing + auth OK.`

## 2. Daily usage

### Add phrases (max 12)
```bash
./gcal-push config add-phrase "Take medication" --at 22:00
./gcal-push config add-phrase "Walk the dog"    --at 07:30
./gcal-push config list-phrases
```

### Push an event
```bash
# Instant reminder (now + 5 min)
./gcal-push push --phrase 0 --now

# At the phrase's default time (rolls to tomorrow if past)
./gcal-push push --phrase 0 --default

# Strictly next :30 / :00
./gcal-push push --phrase 1 --next-half
./gcal-push push --phrase 1 --next-oclock

# 3 upcoming hour marks from now
./gcal-push push --phrase 0 --in-hours 3

# Fixed time today (rolls to tomorrow if past)
./gcal-push push --phrase 0 --at 15:00

# Ad-hoc text (no stored phrase)
./gcal-push push --text "Call mum" --at 18:30
```

### See today's events on the shared calendar
```bash
./gcal-push today
```

### Clear token (forces re-auth next time)
```bash
./gcal-push logout
```

## 3. Phrase management

```bash
./gcal-push config add-phrase "New one" --at 12:00    # errors if 12 phrases exist
./gcal-push config remove-phrase 3                    # delete by index
./gcal-push config list-phrases
./gcal-push config show                               # dump full config
```

## 4. Where things live

| File | Purpose |
|---|---|
| `~/.msl-cal/config.json` | Calendar ID, phrases, defaults (plaintext) |
| OS Keychain (service `msl-cal`) | OAuth refresh token (encrypted by OS) |
| `/Users/maysingh/Downloads/client_secret_*.json` | OAuth client file from Google Cloud Console |

Override config location in tests: `export MSL_CAL_HOME=/some/dir`.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `No client_secret path configured` | `./gcal-push config set-client-secret <path>` then `./gcal-push auth` |
| `calendar_id not set` | `./gcal-push config set-calendar <id-from-B>` |
| Browser opens but "Access blocked: ... has not completed verification" | Add your A-Gmail to **Test Users** in Google Cloud Console → OAuth consent screen |
| `invalid_grant` or "token expired" on push | `./gcal-push auth` to re-authorise (happens ~weekly in Testing mode) |
| `insufficientPermissions` or `Calendar usage limits exceeded` | B's sharing permission is "See all event details" (read-only). Change to "Make changes to events". |
| Event created but B doesn't see it | On B's phone: Google Calendar → menu → Settings → tap shared calendar → toggle **Sync** ON |
| B sees event but no notification | On B's phone: shared calendar settings → set default notification; or verify popup override was sent (the CLI sets one at 0 min) |
| Push lands at wrong time | Check `./gcal-push config show` — system tz drives Calendar tz; confirm Mac tz matches intent |
| `keyring.errors.NoKeyringError` on Linux | Install `gnome-keyring` or `kwallet`; macOS works out of the box |

## 6. Verify your Google Cloud project is free

- https://console.cloud.google.com → hamburger → **Billing**
- Should say: "This project has no billing account" ✅
- If a billing account is linked, you can unlink it; Calendar API keeps working.

## 7. Run tests

```bash
source .venv/bin/activate
python -m pytest tests/test_cal_timing.py tests/test_cal_config.py -v
# or everything:
python -m pytest
```

## 8. Reset everything (clean slate)

```bash
./gcal-push logout
rm -rf ~/.msl-cal
```
