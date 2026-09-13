"""
main.py - Entry point for Freqon (RF Recon Modern).
"""

import sys
import signal
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.theme import MODERN_STYLE_SHEET
from ui.main_window import MainWindow

def main():
    # Enable High-DPI support
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    app.setApplicationName("Freqon")
    app.setOrganizationName("Harogic")
    
    # Configure PyQtGraph Dark Industrial Profile
    pg.setConfigOption('background', '#0d1117')
    pg.setConfigOption('foreground', '#c9d1d9')
    pg.setConfigOption('antialias', True)
    
    # Apply Modern Obsidian Stylesheet
    app.setStyleSheet(MODERN_STYLE_SHEET)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
