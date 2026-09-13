"""
trace_controls.py - Multi-Trace Management & Color Picker.
Provides quick trace activation pills, freeze toggles, and custom color swatch selectors.
"""

from PyQt6.QtWidgets import QPushButton, QMenu, QColorDialog, QWidget, QHBoxLayout, QLabel, QCheckBox, QSpinBox
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen
from PyQt6.QtCore import Qt, pyqtSignal

class SimpleColorPicker(QPushButton):
    """
    Compact modern circular color picker button.
    """
    colorChanged = pyqtSignal(QColor)
    
    PALETTE_COLORS = [
        ('Yellow', '#eab308'),
        ('Cyan', '#06b6d4'),
        ('Magenta', '#d946ef'),
        ('Emerald', '#10b981'),
        ('Orange', '#f97316'),
        ('Sky Blue', '#38bdf8'),
        ('Red', '#ef4444'),
        ('White', '#f8fafc')
    ]
    
    def __init__(self, default_color_name='yellow', parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.current_color = QColor(default_color_name)
        self._update_style()
        
        self.menu = QMenu(self)
        for name, col_hex in self.PALETTE_COLORS:
            action = self.menu.addAction(name)
            action.triggered.connect(lambda checked, h=col_hex: self.set_color_from_hex(h))
            
        self.menu.addSeparator()
        custom_action = self.menu.addAction("Custom Color...")
        custom_action.triggered.connect(self.choose_custom_color)
        self.setMenu(self.menu)

    def _update_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color.name()};
                border: 2px solid #30363d;
                border-radius: 11px;
            }}
            QPushButton:hover {{
                border-color: #58a6ff;
            }}
            QPushButton::menu-indicator {{
                image: none;
            }}
        """)

    def set_color_from_hex(self, hex_val):
        self.set_color(QColor(hex_val))

    def set_color(self, color):
        if color.isValid():
            self.current_color = color
            self._update_style()
            self.colorChanged.emit(color)

    def choose_custom_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Select Trace Color")
        if color.isValid():
            self.set_color(color)
            
    def color(self):
        return self.current_color
