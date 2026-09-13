"""
theme.py - Obsidian Slate Industrial Design System for RF Recon Modern.
Provides professional dark-mode stylesheets, color palettes, and styling constants.
Zero emojis, clean vector aesthetics, crisp typography, and high-contrast precision readouts.
"""

import os
from pathlib import Path
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt

# Vector Asset Path Resolution & Auto-Generation
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

SVG_ASSETS = {
    "plus.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
  <line x1="8" y1="3" x2="8" y2="13" stroke="#f0f6fc" stroke-width="2.2" stroke-linecap="round"/>
  <line x1="3" y1="8" x2="13" y2="8" stroke="#f0f6fc" stroke-width="2.2" stroke-linecap="round"/>
</svg>""",
    "plus_hover.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
  <line x1="8" y1="3" x2="8" y2="13" stroke="#0d1117" stroke-width="2.2" stroke-linecap="round"/>
  <line x1="3" y1="8" x2="13" y2="8" stroke="#0d1117" stroke-width="2.2" stroke-linecap="round"/>
</svg>""",
    "minus.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
  <line x1="3" y1="8" x2="13" y2="8" stroke="#f0f6fc" stroke-width="2.2" stroke-linecap="round"/>
</svg>""",
    "minus_hover.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
  <line x1="3" y1="8" x2="13" y2="8" stroke="#0d1117" stroke-width="2.2" stroke-linecap="round"/>
</svg>""",
    "check.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="20 6 9 17 4 12"></polyline>
</svg>""",
    "chevron_down.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
  <polyline points="4 6 8 10 12 6" fill="none" stroke="#8b949e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
    "chevron_up.svg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16">
  <polyline points="4 10 8 6 12 10" fill="none" stroke="#8b949e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",
}

for _svg_name, _svg_content in SVG_ASSETS.items():
    _svg_file = ASSETS_DIR / _svg_name
    if not _svg_file.exists():
        _svg_file.write_text(_svg_content.strip(), encoding="utf-8")

PLUS_SVG_PATH = (ASSETS_DIR / "plus.svg").as_posix()
PLUS_HOVER_SVG_PATH = (ASSETS_DIR / "plus_hover.svg").as_posix()
MINUS_SVG_PATH = (ASSETS_DIR / "minus.svg").as_posix()
MINUS_HOVER_SVG_PATH = (ASSETS_DIR / "minus_hover.svg").as_posix()
CHECK_SVG_PATH = (ASSETS_DIR / "check.svg").as_posix()
CHEVRON_DOWN_SVG_PATH = (ASSETS_DIR / "chevron_down.svg").as_posix()

# Color Palette Constants
BG_DARK = "#0d1117"        # Darkest workspace background
BG_PANEL = "#161b22"       # Primary container & card background
BG_SURFACE = "#21262d"     # Input fields, table rows, button surface
BG_HOVER = "#30363d"       # Hover highlight state
BG_ACTIVE = "#388bfd33"    # Active selected highlight

BORDER_SUBTLE = "#30363d"   # 1px border for containers
BORDER_FOCUS = "#58a6ff"    # Input focus highlight
BORDER_MUTED = "#21262d"    # Very subtle separator

TEXT_PRIMARY = "#f0f6fc"    # High-contrast white/silver text
TEXT_SECONDARY = "#8b949e"  # Muted metadata & label text
TEXT_MUTED = "#6e7681"      # Disabled / placeholder text

ACCENT_BLUE = "#38bdf8"     # Electric cyan / primary accent
ACCENT_GREEN = "#10b981"    # Signal active / connected emerald
ACCENT_AMBER = "#f59e0b"    # Warning / alert amber
ACCENT_RED = "#f43f5e"      # Disconnected / critical red
ACCENT_MAGENTA = "#d946ef"  # Marker / intruder threshold
ACCENT_PURPLE = "#a855f7"   # Secondary telemetry

FONT_FAMILY = "Segoe UI, Inter, -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
FONT_MONO = "'JetBrains Mono', 'SF Mono', Consolas, 'Courier New', monospace"

MODERN_STYLE_SHEET = f"""
QMainWindow, QDialog {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
}}

QWidget {{
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    font-size: 12px;
}}

QLabel {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
}}

/* Top Bar & Containers */
#topBar {{
    background-color: {BG_PANEL};
    border-bottom: 1px solid {BORDER_SUBTLE};
    padding: 4px 8px;
}}

#panelContainer {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
}}

#cardFrame {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 8px;
}}

#cardFrame QLabel {{
    background-color: transparent;
}}

/* Scroll Areas */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: {BG_DARK};
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background-color: {BG_HOVER};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {BG_DARK};
    height: 8px;
    margin: 0px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background-color: {BG_HOVER};
    min-width: 20px;
    border-radius: 4px;
}}

/* Push Buttons */
QPushButton {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 5px;
    padding: 5px 12px;
    font-weight: 500;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER_FOCUS};
}}

QPushButton:pressed {{
    background-color: #282e33;
    border-color: {ACCENT_BLUE};
}}

QPushButton:checked {{
    background-color: #1f3a5f;
    color: #79c0ff;
    border-color: {ACCENT_BLUE};
    font-weight: 600;
}}

QPushButton:disabled {{
    background-color: {BG_PANEL};
    color: {TEXT_MUTED};
    border-color: {BORDER_MUTED};
}}

/* Action Button Variants */
QPushButton#primaryActionBtn {{
    background-color: #0969da;
    color: #ffffff;
    border: 1px solid #218bff;
    font-weight: 600;
}}

QPushButton#primaryActionBtn:hover {{
    background-color: #1f7bf2;
    border-color: #54aeff;
}}

QPushButton#successBtn {{
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    font-weight: 600;
}}

QPushButton#successBtn:hover {{
    background-color: #2ea043;
}}

QPushButton#dangerBtn {{
    background-color: #da3633;
    color: #ffffff;
    border: 1px solid #f85149;
    font-weight: 600;
}}

QPushButton#dangerBtn:hover {{
    background-color: #f85149;
}}

QPushButton#iconBtn {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px;
    min-width: 24px;
    min-height: 24px;
}}

QPushButton#iconBtn:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER_SUBTLE};
}}

QPushButton#pillBtn {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
}}

QPushButton#pillBtn:checked {{
    background-color: #1f3a5f;
    color: #79c0ff;
    border-color: {ACCENT_BLUE};
}}

/* Line Edits */
QLineEdit {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 4px 8px;
    font-family: {FONT_MONO};
    font-size: 12px;
    selection-background-color: #1f6feb;
}}

QLineEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
    background-color: #1c2128;
}}

/* Numeric Spin Boxes with High-Contrast Stepper Controls */
QDoubleSpinBox, QSpinBox {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 3px 24px 3px 8px;
    font-family: {FONT_MONO};
    font-size: 12px;
    selection-background-color: #1f6feb;
}}

QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 1px solid {BORDER_FOCUS};
    background-color: #1c2128;
}}

QDoubleSpinBox::up-button, QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    height: 12px;
    background-color: #2b323c;
    border-left: 1px solid {BORDER_SUBTLE};
    border-bottom: 1px solid {BORDER_SUBTLE};
    border-top-right-radius: 3px;
}}

QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover {{
    background-color: {ACCENT_BLUE};
    border-color: {ACCENT_BLUE};
}}

QDoubleSpinBox::up-button:pressed, QSpinBox::up-button:pressed {{
    background-color: #0284c7;
}}

QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {{
    image: url({PLUS_SVG_PATH});
    width: 9px;
    height: 9px;
}}

QDoubleSpinBox::up-button:hover QDoubleSpinBox::up-arrow,
QSpinBox::up-button:hover QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow:hover, QSpinBox::up-arrow:hover {{
    image: url({PLUS_HOVER_SVG_PATH});
}}

QDoubleSpinBox::down-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    height: 12px;
    background-color: #2b323c;
    border-left: 1px solid {BORDER_SUBTLE};
    border-bottom-right-radius: 3px;
}}

QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {{
    background-color: {ACCENT_BLUE};
    border-color: {ACCENT_BLUE};
}}

QDoubleSpinBox::down-button:pressed, QSpinBox::down-button:pressed {{
    background-color: #0284c7;
}}

QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {{
    image: url({MINUS_SVG_PATH});
    width: 9px;
    height: 9px;
}}

QDoubleSpinBox::down-button:hover QDoubleSpinBox::down-arrow,
QSpinBox::down-button:hover QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow:hover, QSpinBox::down-arrow:hover {{
    image: url({MINUS_HOVER_SVG_PATH});
}}

/* Combo Box */
QComboBox {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {BORDER_FOCUS};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid {BORDER_SUBTLE};
    background-color: {BG_PANEL};
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
    outline: none;
    padding: 4px;
}}

/* Check Boxes & Radio Buttons */
QCheckBox, QRadioButton {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    spacing: 6px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 3px;
    background-color: {BG_SURFACE};
}}

QRadioButton::indicator {{
    border-radius: 8px;
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {BORDER_FOCUS};
}}

QCheckBox::indicator:checked {{
    background-color: #1f6feb;
    border-color: #58a6ff;
    image: url({CHECK_SVG_PATH});
}}

QRadioButton::indicator:checked {{
    background-color: #1f6feb;
    border-color: #58a6ff;
}}

/* Group Boxes */
QGroupBox {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    background-color: transparent;
    color: {ACCENT_BLUE};
    font-weight: 700;
}}

/* Tables */
QTableWidget {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    gridline-color: {BORDER_MUTED};
    selection-background-color: {BG_ACTIVE};
    selection-color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY};
    outline: none;
}}

QTableWidget::item {{
    padding: 4px 6px;
    border-bottom: 1px solid {BORDER_MUTED};
}}

QTableWidget::item:selected {{
    background-color: #1f3a5f;
    color: #79c0ff;
}}

QTableWidget::item:hover {{
    background-color: {BG_SURFACE};
}}

QHeaderView::section {{
    background-color: {BG_DARK};
    color: {TEXT_SECONDARY};
    padding: 4px 6px;
    border: none;
    border-bottom: 1px solid {BORDER_SUBTLE};
    border-right: 1px solid {BORDER_MUTED};
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
}}

/* Tree Widget */
QTreeWidget {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    outline: none;
}}

QTreeWidget::item {{
    padding: 4px;
    border-radius: 3px;
}}

QTreeWidget::item:hover {{
    background-color: {BG_SURFACE};
}}

QTreeWidget::item:selected {{
    background-color: #1f3a5f;
    color: #79c0ff;
}}

/* Menu Bar & Menus */
QMenuBar {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER_SUBTLE};
    padding: 2px 6px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 4px 8px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {BG_HOVER};
}}

QMenu {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 5px 24px 5px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: #1f6feb;
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER_SUBTLE};
    margin: 4px 6px;
}}

/* Labels & Badges */
QLabel {{
    color: {TEXT_PRIMARY};
}}

QLabel#sectionTitle {{
    font-size: 11px;
    font-weight: 700;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QLabel#hudValue {{
    font-family: {FONT_MONO};
    font-weight: 600;
    color: {ACCENT_BLUE};
}}

QLabel#badgeWarning {{
    background-color: rgba(245, 158, 11, 0.15);
    color: {ACCENT_AMBER};
    border: 1px solid {ACCENT_AMBER};
    border-radius: 4px;
    padding: 2px 6px;
    font-weight: 600;
    font-size: 11px;
}}

QLabel#badgeSuccess {{
    background-color: rgba(16, 185, 129, 0.15);
    color: {ACCENT_GREEN};
    border: 1px solid {ACCENT_GREEN};
    border-radius: 4px;
    padding: 2px 6px;
    font-weight: 600;
    font-size: 11px;
}}

QLabel#badgeDanger {{
    background-color: rgba(244, 63, 94, 0.15);
    color: {ACCENT_RED};
    border: 1px solid {ACCENT_RED};
    border-radius: 4px;
    padding: 2px 6px;
    font-weight: 600;
    font-size: 11px;
}}

/* Tooltips */
QToolTip {{
    background-color: #24292f;
    color: #f0f6fc;
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* Splitters */
QSplitter::handle {{
    background-color: {BORDER_MUTED};
}}

QSplitter::handle:hover {{
    background-color: {BORDER_FOCUS};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* Dialogs */
QDialog {{
    background-color: {BG_PANEL};
    color: {TEXT_PRIMARY};
}}

QGroupBox {{
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}}
"""
