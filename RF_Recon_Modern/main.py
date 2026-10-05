"""
main.py - Entry point for Freqon (RF Recon Modern).
"""

import sys
import signal
import multiprocessing
import traceback
from datetime import datetime
from pathlib import Path

import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QStandardPaths

from ui.theme import MODERN_STYLE_SHEET
from ui.main_window import MainWindow


def install_exception_hook():
    """
    PyQt6 aborts the whole process when an exception escapes a Qt slot. Log it
    instead (stderr + <app data>/freqon.log) so one faulty handler cannot take
    down the application. Repeats of the same error are rate-limited, since slot
    errors in streaming handlers would otherwise recur every frame.
    """
    log_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    log_file = log_dir / "freqon.log"
    counts = {}

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        n = counts.get(text, 0) + 1
        counts[text] = n
        if n > 1 and n % 100:
            return
        header = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Unhandled exception"
        if n > 1:
            header += f" (repeated {n} times)"
        sys.stderr.write(f"{header}\n{text}")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{header}\n{text}\n")
        except OSError:
            pass

    sys.excepthook = hook


def main():
    # Start hardware processes with "spawn" on every OS (macOS's default). Linux
    # defaults to "fork", which copies the GUI process -- including SDK threads
    # and locks from network scans -- into the child and can deadlock it.
    multiprocessing.set_start_method("spawn", force=True)

    # Enable High-DPI support
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("Freqon")
    app.setOrganizationName("Harogic")
    install_exception_hook()

    # Configure PyQtGraph Dark Industrial Profile
    pg.setConfigOption('background', '#0d1117')
    pg.setConfigOption('foreground', '#c9d1d9')
    pg.setConfigOption('antialias', True)

    # Apply Modern Obsidian Stylesheet
    app.setStyleSheet(MODERN_STYLE_SHEET)
    from ui import combo_popups
    combo_popups.install(app)           # drop-down lists as wide as their entries, everywhere

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
