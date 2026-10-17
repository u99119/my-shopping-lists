# RUNBOOK

## 1. One-time setup (macOS)
```bash
brew install openjdk@17 autoconf automake libtool pkgconf
export PYENV_ROOT=~/c/pyenv PATH=~/c/pyenv/bin:$PATH
pyenv install -s 3.11.17
~/c/pyenv/versions/3.11.17/bin/python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. Daily commands
| Task | Command |
|---|---|
| Run on desktop | `.venv/bin/python main.py` |
| Tests | `.venv/bin/python -m pytest -q` |
| Reset desktop data | delete `~/.kivy/` app data dir shown in the startup log (`user_data_dir`) |

## 3. Build the APK
```bash
.venv/bin/pip install buildozer cython
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
.venv/bin/buildozer android debug     # first run downloads SDK/NDK (several GB, 20+ min)
```
Output: `bin/myshoppinglists-1.0.0-arm64-v8a-debug.apk`.

## 4. Install on the phone (side-load)
1. Enable Developer options and USB debugging, connect the phone.
2. `adb install -r bin/*.apk` (or copy the APK to the phone and open it).
3. Data lives in the app's private storage. Uninstalling deletes it, so export first.

## 5. Real-device checklist
- [ ] App opens; create a list, add categories, sub-categories, items.
- [ ] Share list text to WhatsApp and email.
- [ ] Export data, send to another phone, import: lists merge, nothing is deleted.
- [ ] Settings: turn on app lock; reopen and resume the app; device lock prompt appears.
- [ ] Back button navigates up; leaving the app and returning re-locks.

## 6. Troubleshooting
| Symptom | Fix |
|---|---|
| `Unable to locate a Java Runtime` | Set `JAVA_HOME` to JDK 17 as above. |
| Buildozer fails on API 36 | Upgrade: `.venv/bin/pip install -U buildozer python-for-android` and retry; `buildozer android clean` if stale. |
| App crashes at start on phone | `adb logcat -s python` and look for the traceback. |
| `ModuleNotFoundError` on phone only | Add the package to `requirements` in `buildozer.spec`. |
| KivyMD "version 1.2.0 is deprecated" warning | Expected; pinned deliberately. |

## 7. Release steps
1. Bump `__version__` in `msl/__init__.py` and `version` in `buildozer.spec`.
2. Run tests, build, verify on device.
3. Commit, push to `u99119/my-shopping-lists`, tag `vX.Y.Z`.
