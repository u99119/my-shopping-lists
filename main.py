"""Entry point (Buildozer and desktop): ``python main.py``."""

import datetime
import os
import sys
import traceback


def _crash_paths() -> list[str]:
    """Writable locations for startup markers and crash dumps.

    First match wins; the extras are fallbacks for phones that block /sdcard.
    """
    paths = [
        "/sdcard/Download/msl-crash.txt",
        "/storage/emulated/0/Download/msl-crash.txt",
    ]
    try:
        from jnius import autoclass  # type: ignore[import-not-found]

        ctx = autoclass("org.kivy.android.PythonActivity").mActivity
        ext = ctx.getExternalFilesDir(None)
        if ext is not None:
            paths.append(os.path.join(ext.getAbsolutePath(), "msl-crash.txt"))
    except Exception:
        pass
    paths.append(os.path.expanduser("~/msl-crash.txt"))
    return paths


def _write(line: str) -> None:
    for path in _crash_paths():
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as fh:
                fh.write(line)
            return
        except Exception:
            continue


def _excepthook(exc_type, exc_val, exc_tb) -> None:
    tb = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
    _write(f"\n=== CRASH {datetime.datetime.now().isoformat()} ===\n{tb}\n")
    sys.__excepthook__(exc_type, exc_val, exc_tb)


_write(f"\n--- STARTUP {datetime.datetime.now().isoformat()} py={sys.version.split()[0]} ---\n")
sys.excepthook = _excepthook

try:
    from msl.app import ShoppingListsApp
except Exception:
    _excepthook(*sys.exc_info())
    raise

if __name__ == "__main__":
    try:
        ShoppingListsApp().run()
    except Exception:
        _excepthook(*sys.exc_info())
        raise
