"""
nav_rail.py - Segmented Navigation Rail for Workflow Modes.
Provides quick switching between RF & Sweep, Broadcast/DTV, DECT/Intercom,
2.4G/ShowLink, and Threats & Markers, with instant panel collapsing.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QButtonGroup, QLabel, QFrame, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from ..icons import get_chevron_icon

class NavRail(QWidget):
    """
    Vertical workflow mode navigation switcher with expand/collapse toggle.
    """
    modeChanged = pyqtSignal(int)
    collapseToggled = pyqtSignal(bool)

    MODES = [
        ("RF & Sweep", "RF hardware parameters, wide sweep ranges, and multi-row waterfall"),
        ("Threats & Markers", "Intruder alerts, Soundbase JSON and custom markers"),
        ("Rapid Channel Monitoring", "Ultra-fast discrete channel hopping across Soundbase coordinated carriers"),
        ("Real-Time (RTSA)", "Real-Time Spectrum Analysis with 2D persistence density heatmap and 100% POI"),
        ("Zero-Span (DET)", "High-rate time-domain Power vs. Time oscilloscope and TDMA burst analysis"),
        ("Demodulation", "Digital signal demodulation (ASK, FSK, PSK, QAM), constellation, eye diagram, bit table"),
        ("Broadcast / DTV", "FCC/OFCOM broadcast television station lookups"),
        ("DECT / Intercom", "DECT & Riedel Bolero capacity and TDMA time slots"),
        ("2.4G / ShowLink", "ShowLink, Wireless DMX / CRMX and Wi-Fi coexistence"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(160)
        self.is_collapsed = False
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(4)
        
        # Header with Collapse button
        header = QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 4)
        
        lbl = QLabel("MODES")
        lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        header.addWidget(lbl)
        header.addStretch()
        
        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("iconBtn")
        self.toggle_btn.setIcon(get_chevron_icon("left", "#8b949e", 14))
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setToolTip("Collapse / Expand Panel")
        self.toggle_btn.clicked.connect(self._toggle_collapse)
        header.addWidget(self.toggle_btn)
        layout.addLayout(header)
        
        self.btn_group = QButtonGroup(self)
        self.buttons = []
        
        for idx, (title, tooltip) in enumerate(self.MODES):
            btn = QPushButton(title.replace("&", "&&"))
            btn.setObjectName("pillBtn")
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #8b949e;
                    border: 1px solid transparent;
                    text-align: left;
                    padding-left: 10px;
                    font-size: 11px;
                    font-weight: 600;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #161b22;
                    color: #f0f6fc;
                    border-color: #30363d;
                }
                QPushButton:checked {
                    background-color: #21262d;
                    color: #38bdf8;
                    border: 1px solid #38bdf8;
                }
            """)
            if idx == 0:
                btn.setChecked(True)
                
            self.btn_group.addButton(btn, idx)
            self.buttons.append(btn)
            layout.addWidget(btn)
            
        self.btn_group.idClicked.connect(self.modeChanged.emit)
        layout.addStretch()

    def _toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.toggle_btn.setIcon(get_chevron_icon("right", "#8b949e", 14))
        else:
            self.toggle_btn.setIcon(get_chevron_icon("left", "#8b949e", 14))
        self.collapseToggled.emit(self.is_collapsed)

    def set_active_mode(self, mode_idx: int):
        if 0 <= mode_idx < len(self.buttons):
            self.buttons[mode_idx].setChecked(True)
            self.modeChanged.emit(mode_idx)
