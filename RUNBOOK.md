# RUNBOOK

## 1. One-time setup (macOS)
```bash
brew install openjdk@17 autoconf automake libtool pkgconf cmake
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

### 3.1 Environment required
| Item | Requirement |
|---|---|
| OS | macOS (Apple silicon); Homebrew installed |
| Python | 3.11 in `.venv` (section 1) |
| Python packages in `.venv` | `buildozer` (1.6.0 tested), `cython` (0.29.x tested) |
| Java | JDK 17 (`brew install openjdk@17`) |
| Build tools | `autoconf automake libtool pkgconf cmake` (Homebrew), `git` |
| Disk / network | about 10 GB free; first run downloads SDK, NDK and python-for-android |
| Target device | Android 15 or newer installs; built against Android 16 (`android.api = 36`, `android.minapi = 35` in `buildozer.spec`) |

### 3.2 Environment variables (set in the same terminal, every new session)
| Variable | Value | Why |
|---|---|---|
| `JAVA_HOME` | `/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home` | Homebrew's JDK is not registered with macOS, so `/usr/libexec/java_home` cannot find it. |
| `VIRTUAL_ENV` | `$PWD/.venv` | Buildozer uses it to skip `pip install --user`, which fails inside a venv. |
| `PATH` | `$PWD/.venv/bin:$JAVA_HOME/bin:$PATH` | Buildozer finds `cython`, `javac` and `keytool` on `PATH`. |

### 3.3 Commands (run from the repo root)
```bash
# one-time (skip if already installed)
brew install openjdk@17 autoconf automake libtool pkgconf cmake
.venv/bin/pip install buildozer cython

# every new terminal session
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export VIRTUAL_ENV="$PWD/.venv"
export PATH="$PWD/.venv/bin:$JAVA_HOME/bin:$PATH"
java -version                         # must print 17.x
buildozer --version                   # must print Buildozer 1.6.x

# build
buildozer android debug               # first run: 20+ min; later runs: a few minutes
```
- Output: `bin/myshoppinglists-1.0.0-arm64-v8a-debug.apk`.
- Re-run the same `buildozer android debug` after a failure; it resumes. Use `buildozer android clean` only if the build state looks stale.
- Full log: add `-v` (`buildozer -v android debug`).

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
| `Unable to locate a Java Runtime` (also from `java_home -v 17`) | Set `JAVA_HOME` to the Homebrew path in section 3. Alternative: `sudo ln -sfn $(brew --prefix openjdk@17)/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-17.jdk`. |
| `Cython (cython) not found, please install it.` | Buildozer searches `PATH`. Run `export PATH="$PWD/.venv/bin:$PATH"` (and `pip install cython` in the venv if missing). |
| `Can not perform a '--user' install. User site-packages are not visible in this virtualenv.` | Buildozer 1.6.0 checks `VIRTUAL_ENV` to avoid `pip --user`. Activate the venv (`source .venv/bin/activate`) or set `export VIRTUAL_ENV="$PWD/.venv"`, then retry the build. |
| Build sits forever at `python -m pythonforandroid.toolchain aab -h ...` with ~0% CPU | Python-for-Android is waiting at a hidden prompt (`Do you want automatically install prerequisite cmake? [y/N]`). Press Ctrl+C, run `brew install cmake`, then re-run the build. To see the cause, run that command by hand from `.buildozer/android/platform/python-for-android`. |
| FreeType `configure: error: C compiler cannot create executables`; `config.log` shows `ld.lld: error: cannot open crtbegin_dynamic.o` | `android.minapi` is higher than the NDK supports (r28c has libraries for API 21-35 only). Set `android.minapi = 35`, then `buildozer android clean` and rebuild. |
| Buildozer fails on API 36 | Upgrade: `.venv/bin/pip install -U buildozer python-for-android` and retry; `buildozer android clean` if stale. |
| App crashes at start on phone | `adb logcat -s python` and look for the traceback. |
| `ModuleNotFoundError` on phone only | Add the package to `requirements` in `buildozer.spec`. |
| KivyMD "version 1.2.0 is deprecated" warning | Expected; pinned deliberately. |

## 7. Release steps
1. Bump `__version__` in `msl/__init__.py` and `version` in `buildozer.spec`.
2. Run tests, build, verify on device.
3. Commit, push to `u99119/my-shopping-lists`, tag `vX.Y.Z`.
