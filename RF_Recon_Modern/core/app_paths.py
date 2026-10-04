"""
app_paths.py - Per-user, writable locations for Freqon data (cross-platform).

The application folder may be read-only (a macOS .app bundle, a system install)
and the working directory is arbitrary (`/` when launched from Finder), so
anything Freqon writes lives in the platform's per-user data directory:

  macOS    ~/Library/Application Support/Freqon
  Linux    $XDG_DATA_HOME/Freqon (default ~/.local/share/Freqon)
  Windows  %APPDATA%\\Freqon
"""

import os
import shutil
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent  # RF_Recon_Modern/


def user_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = base / "Freqon"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_database(name: str) -> str:
    """
    Path of a writable database in the user data directory. On first use it is
    seeded from the copy bundled with the application, if there is one.
    """
    target = user_data_dir() / name
    if not target.exists():
        bundled = APP_DIR / name
        if bundled.exists():
            shutil.copy2(bundled, target)
    return str(target)
