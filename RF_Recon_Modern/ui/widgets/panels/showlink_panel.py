"""
showlink_panel.py - 2.4 GHz ShowLink & Wireless DMX / CRMX Coexistence Panel.
Monitors 16 ShowLink Zigbee channels (11-26), Wi-Fi 1/6/11 channel overlap,
and CRMX / Wireless DMX frequency-hopping density.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QDoubleSpinBox, QTableWidget, QHeaderView, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal

class ShowLinkPanel(QWidget):
    """
    2.4 GHz ShowLink and Wireless DMX / CRMX coordination panel.
    """
    monitorToggled = pyqtSignal(bool)
    thresholdChanged = pyqtSignal(float)
    showThresholdToggled = pyqtSignal(bool)
    tuneSweepClicked = pyqtSignal()
    openMapClicked = pyqtSignal()
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
        
        # Primary Action Button: Enable Coexistence Monitor
        self.enable_btn = QPushButton("Enable Coexistence Monitor")
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
        cfg_card = self._create_card("2.4 GHz SHOWLINK & CRMX MONITOR", layout)
        
        thresh_layout = QHBoxLayout()
        thresh_layout.setContentsMargins(0, 2, 0, 2)
        thresh_layout.setSpacing(8)
        thresh_lbl = QLabel("Threshold:")
        thresh_lbl.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 500;")
        
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(-150.0, 0.0)
        self.thresh_spin.setValue(-80.0)
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
        
        self.tune_btn = QPushButton("Tune Sweep to 2.4 GHz Band")
        self.tune_btn.setObjectName("primaryActionBtn")
        self.tune_btn.clicked.connect(self.tuneSweepClicked.emit)
        cfg_card.layout().addWidget(self.tune_btn)
        
        # --- 2. SHOWLINK CHANNELS TABLE CARD ---
        table_card = self._create_card("SHOWLINK CHANNELS (11 - 26)", layout)
        
        self.showlink_table = QTableWidget(0, 4)
        self.showlink_table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1117;
                gridline-color: #21262d;
                border: 1px solid #21262d;
                border-radius: 4px;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 1px 2px;
            }
        """)
        self.showlink_table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                border: none;
                border-bottom: 1px solid #21262d;
                padding: 3px 2px;
                font-size: 10px;
                font-weight: 700;
            }
        """)
        self.showlink_table.setHorizontalHeaderLabels(["CH", "FREQ", "RSSI", "STATE"])
        self.showlink_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.showlink_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.showlink_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.showlink_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.showlink_table.setColumnWidth(0, 28)
        self.showlink_table.setColumnWidth(1, 42)
        self.showlink_table.setColumnWidth(2, 68)
        self.showlink_table.verticalHeader().setVisible(False)
        self.showlink_table.setMinimumHeight(190)
        self.showlink_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.showlink_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table_card.layout().addWidget(self.showlink_table)
        
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 2, 0, 0)
        action_layout.setSpacing(6)
        
        self.map_btn = QPushButton("Spectrum Map...")
        self.map_btn.clicked.connect(self.openMapClicked.emit)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(54)
        self.clear_btn.clicked.connect(self.clearClicked.emit)
        
        action_layout.addWidget(self.map_btn, 1)
        action_layout.addWidget(self.clear_btn, 0)
        table_card.layout().addLayout(action_layout)
        
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

    def _update_enable_btn_style(self):
        if self.enable_btn.isChecked():
            self.enable_btn.setText("Pause Coexistence Monitor")
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
            self.enable_btn.setText("Enable Coexistence Monitor")
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
