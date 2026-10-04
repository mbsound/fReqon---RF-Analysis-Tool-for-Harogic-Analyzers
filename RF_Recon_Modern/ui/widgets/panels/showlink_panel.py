"""
showlink_panel.py - 2.4 GHz ShowLink & Wireless DMX / CRMX Coexistence Panel.
Monitors 16 ShowLink Zigbee channels (11-26), Wi-Fi 1/6/11 channel overlap,
and CRMX / Wireless DMX frequency-hopping density.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QDoubleSpinBox, QTableWidget, QHeaderView, QFrame, QScrollArea, QComboBox
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
    myChannelChanged = pyqtSignal(int)          # the ShowLink channel in use
    airtimeClicked = pyqtSignal()               # measure the channel's airtime in zero span
    copySurveyClicked = pyqtSignal()            # put the survey summary on the clipboard

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

        # --- 1b. FEASIBILITY: can ShowLink run here, and what would the venue have to switch off ---
        feas_card = self._create_card("SHOWLINK FEASIBILITY", layout)
        self.feas_lbl = QLabel("Enable the monitor and tune to the band. Survey with the venue's Wi-Fi in use.")
        self.feas_lbl.setWordWrap(True)
        self.feas_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.feas_lbl.setStyleSheet("font-size: 11px; color: #c9d1d9;")
        feas_card.layout().addWidget(self.feas_lbl)
        self.copy_survey_btn = QPushButton("Copy Survey Summary")
        self.copy_survey_btn.setToolTip("Put a plain-text summary (verdict, clear channels, Wi-Fi in use, what to switch off) on the clipboard")
        self.copy_survey_btn.clicked.connect(self.copySurveyClicked.emit)
        feas_card.layout().addWidget(self.copy_survey_btn)

        # --- 1c. THE CHANNEL SHOWLINK IS ON ---
        my_card = self._create_card("SHOWLINK CHANNEL", layout)
        my_row = QHBoxLayout()
        my_lbl = QLabel("Judge:")
        my_lbl.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 500;")
        # The AD610 picks its channel itself (and moves it when interfered with, unless
        # channel agility is turned off in Wireless Workbench), so the channel is read off
        # the air; a fixed choice is for checking a channel it might move to
        self.my_channel_combo = QComboBox()
        self.my_channel_combo.addItem("the channel ShowLink is seen on", 0)
        for ch in range(11, 27):
            self.my_channel_combo.addItem(f"Ch {ch}  ({2405 + 5 * (ch - 11)} MHz)", ch)
        self.my_channel_combo.setToolTip("The AD610 chooses its channel itself and moves when interfered with "
                                         "(channel agility; it cannot be set by hand). Judge the channel ShowLink is "
                                         "seen on, or pick one to see how it would fare there.")
        self.my_channel_combo.currentIndexChanged.connect(lambda _i: self.myChannelChanged.emit(self.my_channel_combo.currentData()))
        my_row.addWidget(my_lbl)
        my_row.addWidget(self.my_channel_combo, 1)
        my_card.layout().addLayout(my_row)
        self.verdict_lbl = QLabel("Enable the monitor and tune to the band.")
        self.verdict_lbl.setWordWrap(True)
        self.verdict_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.verdict_lbl.setStyleSheet("font-size: 11px; color: #c9d1d9;")
        my_card.layout().addWidget(self.verdict_lbl)
        self.airtime_btn = QPushButton("Measure Airtime (Zero-Span)")
        self.airtime_btn.setToolTip("Capture the judged channel in zero span for a moment and measure the share of time "
                                    "anything is transmitting on it, and how long the bursts are. The sweep resumes afterwards.")
        self.airtime_btn.clicked.connect(self.airtimeClicked.emit)
        my_card.layout().addWidget(self.airtime_btn)
        self.airtime_lbl = QLabel("")
        self.airtime_lbl.setWordWrap(True)
        self.airtime_lbl.setStyleSheet("font-size: 10px; color: #8b949e;")
        my_card.layout().addWidget(self.airtime_lbl)
        
        # --- 2. SHOWLINK CHANNELS TABLE CARD ---
        table_card = self._create_card("SHOWLINK CHANNELS (11 - 26)", layout)
        
        self.showlink_table = QTableWidget(0, 5)
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
        self.showlink_table.setHorizontalHeaderLabels(["CH", "FREQ", "BUSY", "RSSI", "STATE"])
        hdr = self.showlink_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(True)
        hdr.setMinimumSectionSize(28)
        self.showlink_table.setColumnWidth(0, 28)
        self.showlink_table.setColumnWidth(1, 42)
        self.showlink_table.setColumnWidth(2, 44)
        self.showlink_table.setColumnWidth(3, 60)
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

        # --- 3. WHAT IS ON THE BAND ---
        band_card = self._create_card("WHAT IS ON THE BAND", layout)
        self.mix_lbl = QLabel("")
        self.mix_lbl.setWordWrap(True)
        self.mix_lbl.setStyleSheet("font-size: 10px; color: #8b949e;")
        band_card.layout().addWidget(self.mix_lbl)
        self.wifi_table = QTableWidget(0, 4)
        self.wifi_table.setStyleSheet(self.showlink_table.styleSheet())
        self.wifi_table.horizontalHeader().setStyleSheet(self.showlink_table.horizontalHeader().styleSheet())
        self.wifi_table.setHorizontalHeaderLabels(["WI-FI", "MHz", "BUSY", "PEAK"])
        whdr = self.wifi_table.horizontalHeader()
        whdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        whdr.setStretchLastSection(True)
        whdr.setMinimumSectionSize(28)
        self.wifi_table.setColumnWidth(0, 44)
        self.wifi_table.setColumnWidth(1, 44)
        self.wifi_table.setColumnWidth(2, 44)
        self.wifi_table.verticalHeader().setVisible(False)
        self.wifi_table.setMinimumHeight(150)
        self.wifi_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.wifi_table.setToolTip("All 13 Wi-Fi channels. Busy: share of recent sweeps with a 20 MHz-wide signal centred on the channel.")
        band_card.layout().addWidget(self.wifi_table)
        
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
