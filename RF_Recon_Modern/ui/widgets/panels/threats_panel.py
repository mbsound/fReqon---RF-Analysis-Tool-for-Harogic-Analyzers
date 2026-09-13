"""
threats_panel.py - Intruder Alerts, Soundbase JSON & Marker Hierarchy Panel.
Manages automated threat detection against unknown RF transmitters,
Soundbase frequency coordination JSON imports, and active channel markers.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QCheckBox, QDoubleSpinBox, QTableWidget, QHeaderView, QTreeWidget, QFrame, QScrollArea,
    QTableWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal

class NumericTableWidgetItem(QTableWidgetItem):
    """
    QTableWidgetItem subclass that sorts numerically based on UserRole data.
    """
    def __init__(self, text: str, sort_value: float):
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, float(sort_value))

    def __lt__(self, other):
        if other is not None:
            v1 = self.data(Qt.ItemDataRole.UserRole)
            v2 = other.data(Qt.ItemDataRole.UserRole)
            if v1 is not None and v2 is not None:
                try:
                    return float(v1) < float(v2)
                except (ValueError, TypeError):
                    pass
        return super().__lt__(other)

class ThreatsPanel(QWidget):
    """
    Intruder alert monitoring, Soundbase coordination file import, and marker management panel.
    """
    intruderAlertToggled = pyqtSignal(bool)
    intruderThresholdChanged = pyqtSignal(float)
    showThresholdToggled = pyqtSignal(bool)
    clearIntrudersClicked = pyqtSignal()
    addIntruderToMarkersClicked = pyqtSignal()
    loadSoundbaseClicked = pyqtSignal()
    markerItemChanged = pyqtSignal(object, int)

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
        
        # Primary Action Button: Enable Intruder Detection
        self.enable_btn = QPushButton("Enable Intruder Detection")
        self.enable_btn.setObjectName("triggerBtn")
        self.enable_btn.setFixedHeight(34)
        self.enable_btn.setCheckable(True)
        self.enable_btn.setChecked(False)
        self._update_enable_btn_style()
        self.enable_btn.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_btn)
        
        # Backward-compatible alias for any code checking .intruder_enable_cb
        self.intruder_enable_cb = self.enable_btn
        
        # --- 1. INTRUDER ALERT & THREATS CARD ---
        intr_card = self._create_card("INTRUDER THREAT DETECTION", layout)
        
        t_layout = QHBoxLayout()
        t_lbl = QLabel("Threshold:")
        t_lbl.setStyleSheet("font-size: 11px;")
        self.intruder_thresh_spin = QDoubleSpinBox()
        self.intruder_thresh_spin.setRange(-150.0, 20.0)
        self.intruder_thresh_spin.setValue(-80.0)
        self.intruder_thresh_spin.setSuffix(" dBm")
        self.intruder_thresh_spin.valueChanged.connect(self.intruderThresholdChanged.emit)
        t_layout.addWidget(t_lbl)
        t_layout.addWidget(self.intruder_thresh_spin)
        intr_card.layout().addLayout(t_layout)
        
        # Display Threshold Line on Spectrum Checkbox
        self.show_thresh_cb = QCheckBox("Display Threshold Line on Spectrum")
        self.show_thresh_cb.setChecked(True)
        self.show_thresh_cb.toggled.connect(self.showThresholdToggled.emit)
        intr_card.layout().addWidget(self.show_thresh_cb)
        
        self.intruder_table = QTableWidget(0, 3)
        self.intruder_table.setHorizontalHeaderLabels(["Freq (MHz)", "Power", "Signature"])
        self.intruder_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.intruder_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.intruder_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.intruder_table.setColumnWidth(0, 78)
        self.intruder_table.setColumnWidth(1, 78)
        self.intruder_table.verticalHeader().setVisible(False)
        self.intruder_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.intruder_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.intruder_table.setSortingEnabled(True)
        self.intruder_table.horizontalHeader().setSortIndicatorShown(True)
        self.intruder_table.horizontalHeader().setSortIndicator(1, Qt.SortOrder.DescendingOrder)
        self.intruder_table.setMinimumHeight(200)
        self.intruder_table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                gridline-color: #21262d;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                font-weight: 700;
                font-size: 10px;
                border: none;
                border-bottom: 1px solid #30363d;
                padding: 3px 2px;
            }
            QHeaderView::section:hover {
                background-color: #21262d;
                color: #f0f6fc;
            }
            QTableWidget::item {
                padding: 2px 3px;
            }
            QTableWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        intr_card.layout().addWidget(self.intruder_table)
        
        btn_layout = QHBoxLayout()
        self.clear_intr_btn = QPushButton("Clear Threats")
        self.clear_intr_btn.clicked.connect(self.clearIntrudersClicked.emit)
        
        self.add_marker_btn = QPushButton("Add to Markers...")
        self.add_marker_btn.clicked.connect(self.addIntruderToMarkersClicked.emit)
        
        btn_layout.addWidget(self.clear_intr_btn)
        btn_layout.addWidget(self.add_marker_btn)
        intr_card.layout().addLayout(btn_layout)
        
        # --- 2. SOUNDBASE JSON IMPORTS CARD ---
        json_card = self._create_card("FREQUENCY COORDINATION IMPORT", layout)
        
        self.btn_soundbase_json = QPushButton("Import Soundbase Site JSON")
        self.btn_soundbase_json.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                font-weight: 600;
                padding: 6px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #f0f6fc;
            }
        """)
        self.btn_soundbase_json.clicked.connect(self.loadSoundbaseClicked.emit)
        json_card.layout().addWidget(self.btn_soundbase_json)
        
        self.soundbase_status_lbl = QLabel("No coordination file active")
        self.soundbase_status_lbl.setStyleSheet("color: #6e7681; font-size: 10px; margin-top: 2px;")
        json_card.layout().addWidget(self.soundbase_status_lbl)
        
        # --- 3. MARKERS & CHANNELS CARD ---
        markers_card = self._create_card("MARKERS & CHANNEL MASKS", layout)
        
        self.markers_tree = QTreeWidget()
        self.markers_tree.setHeaderHidden(True)
        self.markers_tree.setMinimumHeight(180)
        self.markers_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.markers_tree.itemChanged.connect(self.markerItemChanged.emit)
        markers_card.layout().addWidget(self.markers_tree)
        
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

    def set_soundbase_active(self, filename: str, count: int):
        self.btn_soundbase_json.setText("Soundbase JSON Loaded")
        self.btn_soundbase_json.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #2ea043;
                border-radius: 4px;
            }
        """)
        self.soundbase_status_lbl.setText(f"{filename} ({count} channels active)")
        self.soundbase_status_lbl.setStyleSheet("color: #10b981; font-size: 10px;")

    def _update_enable_btn_style(self):
        if self.enable_btn.isChecked():
            self.enable_btn.setText("Pause Intruder Detection")
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
            self.enable_btn.setText("Enable Intruder Detection")
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
        self.intruderAlertToggled.emit(checked)

    def set_detection_active(self, active: bool):
        self.enable_btn.setChecked(active)

