"""
dect_panel.py - DECT & Riedel Bolero Intercom Capacity & TDMA Analysis Panel.
Monitors temporal duty cycle, base station beacons, beltpack transceivers,
and channel congestion across standard DECT bands.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QDoubleSpinBox, QTableWidget, QHeaderView, QFrame,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from core.dect_analyzer import DECT_BANDS

class DECTPanel(QWidget):
    """
    DECT and wireless intercom coordination panel.
    """
    bandChanged = pyqtSignal(str)
    monitorToggled = pyqtSignal(bool)
    thresholdChanged = pyqtSignal(float)
    showThresholdToggled = pyqtSignal(bool)
    tuneSweepClicked = pyqtSignal()
    openMatrixClicked = pyqtSignal()
    clearClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)
        scroll.setWidget(container)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        
        # Primary Action Button: Enable DECT Monitor
        self.enable_btn = QPushButton("Enable DECT Monitor")
        self.enable_btn.setObjectName("triggerBtn")
        self.enable_btn.setFixedHeight(34)
        self.enable_btn.setCheckable(True)
        self.enable_btn.setChecked(False)
        self._update_enable_btn_style()
        self.enable_btn.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_btn)
        
        # Backward-compatible alias for any code checking .enable_cb
        self.enable_cb = self.enable_btn
        
        # --- 1. CONFIGURATION CARD ---
        cfg_card = self._create_card("DECT INTERCOM MONITOR", layout)
        
        # Band Selection: Title stacked above Combo for full width & no label collision
        band_lbl = QLabel("DECT Region / Band:")
        band_lbl.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 600;")
        cfg_card.layout().addWidget(band_lbl)
        
        self.band_combo = QComboBox()
        self.band_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.band_combo.addItems(list(DECT_BANDS.keys()))
        self.band_combo.currentTextChanged.connect(self.bandChanged.emit)
        cfg_card.layout().addWidget(self.band_combo)
        
        # Threshold Row (Horizontal alignment with flex spinbox)
        thresh_layout = QHBoxLayout()
        thresh_layout.setContentsMargins(0, 2, 0, 2)
        thresh_layout.setSpacing(8)
        thresh_lbl = QLabel("Threshold:")
        thresh_lbl.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 500;")
        
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(-150.0, 0.0)
        self.thresh_spin.setValue(-85.0)
        self.thresh_spin.setSuffix(" dBm")
        self.thresh_spin.setDecimals(1)
        self.thresh_spin.valueChanged.connect(self.thresholdChanged.emit)
        
        thresh_layout.addWidget(thresh_lbl)
        thresh_layout.addWidget(self.thresh_spin, 1)
        cfg_card.layout().addLayout(thresh_layout)
        
        # Display Threshold Line on Spectrum Checkbox
        self.show_thresh_cb = QCheckBox("Display Threshold Line on Spectrum")
        self.show_thresh_cb.setChecked(True)
        self.show_thresh_cb.toggled.connect(self.showThresholdToggled.emit)
        cfg_card.layout().addWidget(self.show_thresh_cb)
        
        # Tune Sweep Button
        self.tune_btn = QPushButton("Tune Sweep to DECT Band")
        self.tune_btn.setObjectName("primaryActionBtn")
        self.tune_btn.clicked.connect(self.tuneSweepClicked.emit)
        cfg_card.layout().addWidget(self.tune_btn)
        
        # --- 2. CARRIERS & OCCUPANCY CARD ---
        carriers_card = self._create_card("DISCOVERED CARRIERS & LOAD", layout)
        
        # Telemetry HUD Summary (Structured 2-row micro card)
        hud_frame = QFrame()
        hud_frame.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #21262d;
                border-radius: 4px;
                padding: 4px 6px;
            }
        """)
        hud_layout = QGridLayout(hud_frame)
        hud_layout.setContentsMargins(4, 4, 4, 4)
        hud_layout.setSpacing(4)
        
        # Row 1: Band Load
        load_title = QLabel("BAND LOAD:")
        load_title.setStyleSheet("color: #8b949e; font-size: 10px; font-weight: 700;")
        self.load_val_lbl = QLabel("0% (CLEAN)")
        self.load_val_lbl.setStyleSheet("color: #10b981; font-weight: 700; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
        hud_layout.addWidget(load_title, 0, 0)
        hud_layout.addWidget(self.load_val_lbl, 0, 1, Qt.AlignmentFlag.AlignRight)
        
        # Row 2: Antennas & Beltpacks
        units_title = QLabel("ACTIVE UNITS:")
        units_title.setStyleSheet("color: #8b949e; font-size: 10px; font-weight: 700;")
        self.units_val_lbl = QLabel("0 Ant | 0 Packs")
        self.units_val_lbl.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
        hud_layout.addWidget(units_title, 1, 0)
        hud_layout.addWidget(self.units_val_lbl, 1, 1, Qt.AlignmentFlag.AlignRight)
        
        carriers_card.layout().addWidget(hud_frame)
        
        # Carriers Table with strict column budget
        self.carriers_table = QTableWidget(0, 4)
        self.carriers_table.setStyleSheet("font-size: 11px;")
        self.carriers_table.setHorizontalHeaderLabels(["CH", "RSSI", "DUTY", "STATUS"])
        self.carriers_table.horizontalHeader().setStyleSheet("font-size: 10px; font-weight: 700;")
        self.carriers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.carriers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.carriers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.carriers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.carriers_table.setColumnWidth(0, 20)
        self.carriers_table.setColumnWidth(1, 72)
        self.carriers_table.setColumnWidth(2, 44)
        self.carriers_table.verticalHeader().setVisible(False)
        self.carriers_table.setMinimumHeight(150)
        self.carriers_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.carriers_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        carriers_card.layout().addWidget(self.carriers_table)
        
        # Action Buttons (Proportionally constrained)
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 2, 0, 0)
        action_layout.setSpacing(6)
        
        self.matrix_btn = QPushButton("TDMA Matrix...")
        self.matrix_btn.setToolTip("Open Full Time-Slot Matrix Inspector")
        self.matrix_btn.clicked.connect(self.openMatrixClicked.emit)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(54)
        self.clear_btn.setToolTip("Reset discovered carrier telemetry")
        self.clear_btn.clicked.connect(self.clearClicked.emit)
        
        action_layout.addWidget(self.matrix_btn, 1)
        action_layout.addWidget(self.clear_btn, 0)
        carriers_card.layout().addLayout(action_layout)
        
        layout.addStretch()

    def _create_card(self, title: str, parent_layout: QVBoxLayout) -> QFrame:
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        card_layout.addWidget(title_lbl)
        
        parent_layout.addWidget(card)
        return card

    def update_summary(self, load_pct: float, antennas: int, beltpacks: int, status_str: str):
        if load_pct < 25.0:
            color = "#10b981" # Green
        elif load_pct < 60.0:
            color = "#f59e0b" # Amber
        else:
            color = "#f43f5e" # Red
            
        self.load_val_lbl.setText(f"{load_pct:.0f}% ({status_str})")
        self.load_val_lbl.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
        self.units_val_lbl.setText(f"{antennas} Ant | {beltpacks} Packs")

    def _update_enable_btn_style(self):
        if self.enable_btn.isChecked():
            self.enable_btn.setText("Pause DECT Monitor")
            self.enable_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0969da;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    border-radius: 6px;
                    border: 1px solid #218bff;
                }
                QPushButton:hover {
                    background-color: #1f7bf2;
                }
                QPushButton:pressed {
                    background-color: #054da7;
                }
            """)
        else:
            self.enable_btn.setText("Enable DECT Monitor")
            self.enable_btn.setStyleSheet("""
                QPushButton {
                    background-color: #238636;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    border-radius: 6px;
                    border: 1px solid #2ea043;
                }
                QPushButton:hover {
                    background-color: #2ea043;
                }
                QPushButton:pressed {
                    background-color: #1a7f37;
                }
            """)

    def _on_enable_toggled(self, checked: bool):
        self._update_enable_btn_style()
        self.monitorToggled.emit(checked)

    def set_monitor_active(self, active: bool):
        self.enable_btn.setChecked(active)
