"""
dtv_panel.py - Broadcast Television Coordination & Station Database Panel.
Provides FCC & OFCOM broadcast station lookups by postal code,
threshold line placement, occupied channel auto-detection, T-Band scanning, and zone mapping.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QDoubleSpinBox, QCheckBox, QTableWidget, QHeaderView, QFrame, QScrollArea, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal

class DTVPanel(QWidget):
    """
    Broadcast television coordination and live station analysis panel.
    """
    lookupRequested = pyqtSignal(str)
    thresholdChanged = pyqtSignal(float)
    showThresholdToggled = pyqtSignal(bool)
    dtvDetectToggled = pyqtSignal(bool)
    tbandScanToggled = pyqtSignal(bool)
    stationSelected = pyqtSignal(int, int) # row, column
    zoneSelected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        scroll.setWidget(container)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        
        # --- 1. POSTAL CODE LOOKUP CARD ---
        lookup_card = self._create_card("BROADCAST STATION LOOKUP", layout)
        
        zip_layout = QHBoxLayout()
        self.zip_input = QLineEdit()
        self.zip_input.setPlaceholderText("Enter ZIP / Postal Code")
        self.zip_input.setMaxLength(8)
        self.zip_input.returnPressed.connect(self._on_lookup)
        
        self.lookup_btn = QPushButton("Lookup")
        self.lookup_btn.setObjectName("primaryActionBtn")
        self.lookup_btn.clicked.connect(self._on_lookup)
        
        zip_layout.addWidget(self.zip_input)
        zip_layout.addWidget(self.lookup_btn)
        lookup_card.layout().addLayout(zip_layout)
        
        # --- 2. DETECTION & THRESHOLDS CARD ---
        thresh_card = self._create_card("OCCUPIED CHANNEL DETECTOR", layout)
        t_form = QFormLayout()
        t_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-150.0, 0.0)
        self.threshold_spin.setValue(-70.0)
        self.threshold_spin.setSuffix(" dBm")
        self.threshold_spin.valueChanged.connect(self.thresholdChanged.emit)
        t_form.addRow("DTV Threshold:", self.threshold_spin)
        
        self.show_thresh_cb = QCheckBox("Display Threshold Line on Spectrum")
        self.show_thresh_cb.toggled.connect(self.showThresholdToggled.emit)
        t_form.addRow(self.show_thresh_cb)
        thresh_card.layout().addLayout(t_form)
        
        btn_layout = QHBoxLayout()
        self.dtv_detect_btn = QPushButton("Auto DTV Detect")
        self.dtv_detect_btn.setCheckable(True)
        self.dtv_detect_btn.toggled.connect(self.dtvDetectToggled.emit)
        
        self.tband_scan_btn = QPushButton("Scan T-Band")
        self.tband_scan_btn.setCheckable(True)
        self.tband_scan_btn.toggled.connect(self.tbandScanToggled.emit)
        
        btn_layout.addWidget(self.dtv_detect_btn)
        btn_layout.addWidget(self.tband_scan_btn)
        thresh_card.layout().addLayout(btn_layout)
        
        self.detect_status_lbl = QLabel("Auto DTV: Idle (Disabled)")
        self.detect_status_lbl.setStyleSheet("color: #8b949e; font-size: 11px; padding-top: 4px;")
        thresh_card.layout().addWidget(self.detect_status_lbl)
        
        # --- 3. NEARBY STATIONS TABLE CARD ---
        stations_card = self._create_card("NEARBY BROADCAST TRANSMITTERS", layout)
        
        self.stations_table = QTableWidget(0, 5)
        self.stations_table.setHorizontalHeaderLabels(["Ch", "Call Sign / Band", "ERP / Range", "Dist", "Live RF (dBm)"])
        self.stations_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.stations_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.stations_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.stations_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.stations_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.stations_table.verticalHeader().setVisible(False)
        self.stations_table.setMinimumHeight(180)
        self.stations_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.stations_table.cellClicked.connect(self.stationSelected.emit)
        stations_card.layout().addWidget(self.stations_table)
        
        # --- 4. DTV COORDINATION ZONES CARD ---
        zones_card = self._create_card("COORDINATION ZONES", layout)
        self.zones_table = QTableWidget(0, 2)
        self.zones_table.setHorizontalHeaderLabels(["Select", "Zone Name"])
        self.zones_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.zones_table.horizontalHeader().setStretchLastSection(True)
        self.zones_table.verticalHeader().setVisible(False)
        self.zones_table.setMaximumHeight(160)
        self.zones_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        zones_card.layout().addWidget(self.zones_table)
        
        self.zone_btn_group = QButtonGroup(self)
        self.zone_btn_group.idClicked.connect(self.zoneSelected.emit)
        
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

    def _on_lookup(self):
        code = self.zip_input.text().strip()
        if code:
            self.lookupRequested.emit(code)

    def update_detect_status(self, active_count: int, total_count: int, thresh: float, is_active: bool):
        if not is_active:
            self.detect_status_lbl.setText("Auto DTV: Idle (Disabled)")
            self.detect_status_lbl.setStyleSheet("color: #8b949e; font-size: 11px; padding-top: 4px;")
        else:
            self.detect_status_lbl.setText(f"Auto DTV: {active_count} Occupied | {total_count - active_count} Clear (Thresh: {thresh:.1f} dBm)")
            self.detect_status_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600; padding-top: 4px;")
