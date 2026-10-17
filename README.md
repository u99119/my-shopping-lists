# my-shopping-lists

Free, offline Android shopping-list app written in Python (Kivy + KivyMD). Side-loaded APK, no Google Play, no cloud.

## Features
- Multiple shopping lists; each has categories and sub-categories (preloaded catalog: Stationary, Alcohol, Clothes, Souvenirs, Kitchen, Makeup, Food, ...; editable in the Catalog screen).
- Items with priority, cost and status (pending / bought / not available).
- Edit mode and a collapsed view mode (top-priority pending items only), with totals.
- Currency: base INR; other currencies convert using stored, editable rates (works offline).
- Share a list as readable text (WhatsApp, email, ...).
- Export all data to a JSON file, share it to another phone, and import it there. Import merges: newer change wins, nothing is deleted. Importing a duplicate list resets item statuses to pending.
- Optional app lock using the Android device lock (PIN / pattern / biometric).
- All data is stored locally in SQLite.

## Requirements
- Android 16 (API 36) or newer.
- Dev machine: Python 3.11, JDK 17 (only for building the APK).

## Quick start (desktop)
```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py          # run the app in a window
.venv/bin/python -m pytest -q     # run the tests
```

## Layout
| Path | Purpose |
|---|---|
| `msl/core/` | Models, SQLite, repository, view-models, currency, share text, export/import. No UI code. |
| `msl/ui/` | KivyMD screens: home, list, catalog, settings, lock. |
| `msl/services.py` | Android bridge (share, file save/pick, device lock) with desktop fallbacks. |
| `msl/app.py`, `main.py` | App class and entry point. |
| `tests/` | pytest suite for `msl/core`. |
| `buildozer.spec` | Android build settings. |

See [RUNBOOK.md](RUNBOOK.md) for build, install and troubleshooting.

## Status
- Core logic: 55 unit tests passing.
- UI: headless smoke test passes on desktop.
- Device lock, share sheet, file picker: need verification on a real Android 16 device.
