"""
mscan_panel.py - Discrete Channel Scanning (MSCAN) Control Panel.
Coordinates ultra-fast hardware list-scanning across Soundbase production channels,
dwell timing, RF dropout alarms, and Zone/Group channel filtering.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QCheckBox, QDoubleSpinBox, QComboBox, QTreeWidget, QTreeWidgetItem,
    QFrame, QScrollArea, QHeaderView, QTableWidget, QTableWidgetItem
)
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtCore import Qt, pyqtSignal

class MSCANPanel(QWidget):
    """
    Control sidebar for Hardware Discrete Channel Scanning (MSCAN).
    """
    scanToggled = pyqtSignal(bool)
    paramsChanged = pyqtSignal(dict)
    loadSoundbaseClicked = pyqtSignal()
    channelsSelectionChanged = pyqtSignal(list) # list of selected carrier dicts
    tuneAudioDemodRequested = pyqtSignal(float)
    inspectRtsaRequested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.carriers = []
        self.selected_carriers = []
        self.is_scanning = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        scroll.setWidget(container)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        # --- 1. PRIMARY SCAN ACTION & TELEMETRY ---
        self.scan_btn = QPushButton("Start Rapid Channel Monitoring")
        self.scan_btn.setObjectName("triggerBtn")
        self.scan_btn.setFixedHeight(36)
        self.scan_btn.setCheckable(True)
        self.scan_btn.setChecked(False)
        self._update_scan_btn_style()
        self.scan_btn.clicked.connect(self._on_scan_btn_clicked)
        layout.addWidget(self.scan_btn)

        self.telemetry_card = QFrame()
        self.telemetry_card.setStyleSheet("""
            QFrame {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        telem_layout = QVBoxLayout(self.telemetry_card)
        telem_layout.setContentsMargins(6, 6, 6, 6)
        telem_layout.setSpacing(4)

        self.lbl_telem_status = QLabel("Status: Standby")
        self.lbl_telem_status.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        telem_layout.addWidget(self.lbl_telem_status)

        self.lbl_telem_metrics = QLabel("0 channels @ 0.0 hops/s (Cycle: -- ms)")
        self.lbl_telem_metrics.setStyleSheet("color: #38bdf8; font-size: 11px; font-family: monospace;")
        telem_layout.addWidget(self.lbl_telem_metrics)
        layout.addWidget(self.telemetry_card)

        # --- 2. SCAN PARAMETERS CARD ---
        param_card = self._create_card("SCAN TIMING & HARDWARE")
        param_layout = QFormLayout(param_card)
        param_layout.setContentsMargins(8, 8, 8, 8)
        param_layout.setSpacing(6)

        # Dwell Time
        self.dwell_combo = QComboBox()
        self.dwell_combo.addItem("200 µs (Ultra-fast)", 0.0002)
        self.dwell_combo.addItem("500 µs (High-speed)", 0.0005)
        self.dwell_combo.addItem("1.0 ms (Recommended)", 0.001)
        self.dwell_combo.addItem("2.0 ms (High Sensitivity)", 0.002)
        self.dwell_combo.addItem("5.0 ms", 0.005)
        self.dwell_combo.addItem("10.0 ms", 0.010)
        self.dwell_combo.setCurrentIndex(2) # 1.0 ms default
        self.dwell_combo.currentIndexChanged.connect(self._emit_params_changed)
        param_layout.addRow("Dwell Time:", self.dwell_combo)

        # Detector
        self.detector_combo = QComboBox()
        self.detector_combo.addItem("Max Peak (PosPeak)", 1)
        self.detector_combo.addItem("Average", 2)
        self.detector_combo.addItem("RMS", 6)
        self.detector_combo.setCurrentIndex(0)
        self.detector_combo.currentIndexChanged.connect(self._emit_params_changed)
        param_layout.addRow("Detector:", self.detector_combo)

        # Hardware Channel Filter / Decimation
        self.channel_filter_combo = QComboBox()
        self.channel_filter_combo.addItem("400 kHz (High Density 375k Grid)", 256)
        self.channel_filter_combo.addItem("200 kHz (Ultra Narrow 200k Grid)", 512)
        self.channel_filter_combo.addItem("800 kHz (Standard 500k+ Grid)", 128)
        self.channel_filter_combo.addItem("1.6 MHz (Wideband Overview)", 64)
        self.channel_filter_combo.setCurrentIndex(0) # Default to 400 kHz / Decimate 256
        self.channel_filter_combo.currentIndexChanged.connect(self._emit_params_changed)
        param_layout.addRow("IF Filter:", self.channel_filter_combo)

        # Reference Level
        self.ref_level_spin = QDoubleSpinBox()
        self.ref_level_spin.setRange(-100.0, 30.0)
        self.ref_level_spin.setValue(-10.0)
        self.ref_level_spin.setSuffix(" dBm")
        self.ref_level_spin.valueChanged.connect(self._emit_params_changed)
        param_layout.addRow("Ref Level:", self.ref_level_spin)

        # Hardware Preamp
        self.preamp_cb = QCheckBox("RF Preamplifier (+20 dB)")
        self.preamp_cb.setChecked(False)
        self.preamp_cb.toggled.connect(self._emit_params_changed)
        param_layout.addRow(self.preamp_cb)

        layout.addWidget(param_card)

        # --- 3. SOUNDBASE COORDINATION CARD ---
        sb_card = self._create_card("COORDINATION & CHANNELS")
        sb_layout = QVBoxLayout(sb_card)
        sb_layout.setContentsMargins(8, 8, 8, 8)
        sb_layout.setSpacing(6)

        self.btn_load_sb = QPushButton("Import Soundbase File")
        self.btn_load_sb.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #f0f6fc;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 5px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #8b949e;
            }
        """)
        self.btn_load_sb.clicked.connect(self.loadSoundbaseClicked.emit)
        sb_layout.addWidget(self.btn_load_sb)

        self.sb_file_lbl = QLabel("No coordination file loaded")
        self.sb_file_lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
        sb_layout.addWidget(self.sb_file_lbl)

        # Channel Filter Tree (Site -> Zone -> Group -> Channel)
        self.channel_tree = QTreeWidget()
        self.channel_tree.setColumnCount(2)
        self.channel_tree.setHeaderLabels(["Item / Channel", "Freq (MHz)"])
        self.channel_tree.setHeaderHidden(False)
        self.channel_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.channel_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.channel_tree.setColumnWidth(1, 80)
        self.channel_tree.setIndentation(14)
        self.channel_tree.setFixedHeight(220)
        self.channel_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #c9d1d9;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 2px 2px;
            }
            QTreeWidget::item:hover {
                background-color: #161b22;
            }
            QTreeWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                font-weight: 700;
                font-size: 10px;
                border: none;
                border-bottom: 1px solid #30363d;
                padding: 3px 4px;
            }
        """)
        self.channel_tree.itemChanged.connect(self._on_tree_item_changed)
        sb_layout.addWidget(self.channel_tree)

        # Quick selection buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setFixedHeight(22)
        self.btn_select_all.setStyleSheet("font-size: 10px; background: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 3px;")
        self.btn_select_all.clicked.connect(self.select_all_channels)
        btn_row.addWidget(self.btn_select_all)

        self.btn_clear_all = QPushButton("Clear All")
        self.btn_clear_all.setFixedHeight(22)
        self.btn_clear_all.setStyleSheet("font-size: 10px; background: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 3px;")
        self.btn_clear_all.clicked.connect(self.clear_all_channels)
        btn_row.addWidget(self.btn_clear_all)

        sb_layout.addLayout(btn_row)

        self.channel_summary_lbl = QLabel("0 / 0 Channels Selected for Monitoring")
        self.channel_summary_lbl.setStyleSheet("color: #10b981; font-size: 10px; font-weight: 600;")
        sb_layout.addWidget(self.channel_summary_lbl)

        layout.addWidget(sb_card)

        # --- 4. RF HEALTH & DROPOUT ALERTS CARD ---
        alert_card = self._create_card("RF ALERTS & DROPOUT THRESHOLDS")
        alert_layout = QFormLayout(alert_card)
        alert_layout.setContentsMargins(8, 8, 8, 8)
        alert_layout.setSpacing(6)

        # Dropout Warning Threshold
        self.dropout_spin = QDoubleSpinBox()
        self.dropout_spin.setRange(-120.0, -20.0)
        self.dropout_spin.setValue(-75.0)
        self.dropout_spin.setSuffix(" dBm")
        self.dropout_spin.setToolTip("Trigger warning if an active production mic drops below this RF level")
        self.dropout_spin.valueChanged.connect(self._emit_params_changed)
        alert_layout.addRow("Dropout Floor:", self.dropout_spin)

        # Rogue / Stray Threshold
        self.rogue_spin = QDoubleSpinBox()
        self.rogue_spin.setRange(-120.0, -20.0)
        self.rogue_spin.setValue(-85.0)
        self.rogue_spin.setSuffix(" dBm")
        self.rogue_spin.setToolTip("Trigger alert if an inactive / backup channel receives unexpected RF energy")
        self.rogue_spin.valueChanged.connect(self._emit_params_changed)
        alert_layout.addRow("Rogue Floor:", self.rogue_spin)

        self.visual_alert_cb = QCheckBox("Visual Flash on RF Dropout")
        self.visual_alert_cb.setChecked(True)
        alert_layout.addRow(self.visual_alert_cb)

        layout.addWidget(alert_card)
        layout.addStretch()

    def _create_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
            }
        """)
        return card

    def _update_scan_btn_style(self):
        if self.scan_btn.isChecked():
            self.scan_btn.setText("Monitoring Active (Stop)")
            self.scan_btn.setStyleSheet("""
                QPushButton {
                    background-color: #238636;
                    color: #ffffff;
                    font-weight: 700;
                    border: 1px solid #2ea043;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #2ea043;
                }
            """)
        else:
            self.scan_btn.setText("Start Rapid Channel Monitoring")
            self.scan_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1f6feb;
                    color: #ffffff;
                    font-weight: 700;
                    border: 1px solid #388bfd;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #388bfd;
                }
            """)

    def stop_scan(self):
        if self.is_scanning or self.scan_btn.isChecked():
            self.is_scanning = False
            self.scan_btn.setChecked(False)
            self._update_scan_btn_style()
            self.lbl_telem_status.setText("Status: Standby")
            self.lbl_telem_status.setStyleSheet("color: #8b949e; font-weight: 600;")
            self.scanToggled.emit(False)

    def _on_scan_btn_clicked(self):
        self.is_scanning = self.scan_btn.isChecked()
        self._update_scan_btn_style()
        self.lbl_telem_status.setText("Status: Scanning" if self.is_scanning else "Status: Paused")
        self.lbl_telem_status.setStyleSheet("color: #10b981; font-weight: 600;" if self.is_scanning else "color: #8b949e; font-weight: 600;")
        self.scanToggled.emit(self.is_scanning)

    def _emit_params_changed(self):
        self.paramsChanged.emit(self.get_params())

    def get_params(self) -> dict:
        return {
            "dwell_time": float(self.dwell_combo.currentData() or 0.001),
            "detector": int(self.detector_combo.currentData() or 1),
            "decimate": int(self.channel_filter_combo.currentData() or 256),
            "ref_level": float(self.ref_level_spin.value()),
            "preamp": 0x01 if self.preamp_cb.isChecked() else 0x00,
            "atten": 0,
            "dropout_thresh_dbm": float(self.dropout_spin.value()),
            "rogue_thresh_dbm": float(self.rogue_spin.value()),
            "visual_alert": self.visual_alert_cb.isChecked(),
            "channels": self.selected_carriers
        }

    def set_soundbase_data(self, parsed_data: dict):
        """Populates the channel selection tree from parsed Soundbase coordination data."""
        self.carriers = parsed_data.get("all_carriers", parsed_data.get("carriers", []))
        self.sb_file_lbl.setText(f"{len(self.carriers)} carriers loaded")
        self.sb_file_lbl.setStyleSheet("color: #10b981; font-size: 10px; font-weight: 600;")

        self.channel_tree.blockSignals(True)
        self.channel_tree.clear()

        sites = parsed_data.get("sites", [])
        for site in sites:
            total_site_ch = sum(len(g.get('carriers', [])) for z in site.get('zones', []) for g in z.get('groups', []))
            site_item = QTreeWidgetItem([site.get("name", "Site"), f"{total_site_ch} ch"])
            site_item.setFlags(site_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            site_item.setCheckState(0, Qt.CheckState.Checked)
            s_font = site_item.font(0)
            s_font.setBold(True)
            site_item.setFont(0, s_font)
            site_item.setForeground(0, QBrush(QColor("#f0f6fc")))
            site_item.setForeground(1, QBrush(QColor("#8b949e")))
            self.channel_tree.addTopLevelItem(site_item)

            for zone in site.get("zones", []):
                z_ch_count = sum(len(g.get('carriers', [])) for g in zone.get('groups', []))
                zone_item = QTreeWidgetItem([zone.get("name", "Zone"), f"{z_ch_count} ch"])
                zone_item.setFlags(zone_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                zone_item.setCheckState(0, Qt.CheckState.Checked)
                z_font = zone_item.font(0)
                z_font.setBold(True)
                zone_item.setFont(0, z_font)
                zone_item.setForeground(0, QBrush(QColor("#c9d1d9")))
                zone_item.setForeground(1, QBrush(QColor("#8b949e")))
                site_item.addChild(zone_item)

                for group in zone.get("groups", []):
                    g_color = group.get("color", "#38bdf8")
                    g_name = group.get("name", "Group")
                    g_carriers = group.get("carriers", [])
                    group_item = QTreeWidgetItem([g_name, f"{len(g_carriers)} ch"])
                    group_item.setFlags(group_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    group_item.setCheckState(0, Qt.CheckState.Checked)
                    group_item.setForeground(0, QBrush(QColor(g_color)))
                    group_item.setForeground(1, QBrush(QColor("#8b949e")))
                    zone_item.addChild(group_item)

                    for carrier in g_carriers:
                        ch_name = carrier.get("name", "Mic")
                        f_mhz = carrier.get("freq_mhz", 0.0)
                        c_bw = carrier.get("bandwidth_mhz", 0.2) * 1000.0
                        c_model = carrier.get("model", "")
                        c_color = carrier.get("color", g_color)

                        ch_item = QTreeWidgetItem([ch_name, f"{f_mhz:.3f}"])
                        ch_item.setFlags(ch_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        ch_item.setCheckState(0, Qt.CheckState.Checked)
                        ch_item.setData(0, Qt.ItemDataRole.UserRole, carrier)
                        ch_item.setForeground(0, QBrush(QColor(c_color)))
                        ch_item.setForeground(1, QBrush(QColor("#f0f6fc")))

                        tooltip = (
                            f"Channel: {ch_name}\n"
                            f"Frequency: {f_mhz:.3f} MHz\n"
                            f"Bandwidth: {c_bw:.0f} kHz\n"
                            f"Model: {c_model}\n"
                            f"Group: {g_name}\n"
                            f"Zone: {zone.get('name', 'Zone')}"
                        )
                        ch_item.setToolTip(0, tooltip)
                        ch_item.setToolTip(1, tooltip)
                        group_item.addChild(ch_item)

        self.channel_tree.expandAll()
        self.channel_tree.blockSignals(False)
        self._update_selected_carriers()

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int):
        if column != 0:
            return
        state = item.checkState(0)
        def cascade(parent_item, st):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                child.setCheckState(0, st)
                cascade(child, st)

        self.channel_tree.blockSignals(True)
        cascade(item, state)
        self.channel_tree.blockSignals(False)
        self._update_selected_carriers()

    def _update_selected_carriers(self):
        selected = []
        def gather(item):
            for i in range(item.childCount()):
                child = item.child(i)
                data = child.data(0, Qt.ItemDataRole.UserRole)
                if data is not None and child.checkState(0) == Qt.CheckState.Checked:
                    selected.append(data)
                gather(child)

        for idx in range(self.channel_tree.topLevelItemCount()):
            gather(self.channel_tree.topLevelItem(idx))

        self.selected_carriers = selected
        total = len(self.carriers)
        count = len(selected)
        self.channel_summary_lbl.setText(f"{count} / {total} Channels Selected for Monitoring")
        self.channelsSelectionChanged.emit(self.selected_carriers)
        if self.is_scanning:
            self._emit_params_changed()

    def select_all_channels(self):
        def set_state(item, st):
            item.setCheckState(0, st)
            for i in range(item.childCount()):
                set_state(item.child(i), st)

        self.channel_tree.blockSignals(True)
        for i in range(self.channel_tree.topLevelItemCount()):
            set_state(self.channel_tree.topLevelItem(i), Qt.CheckState.Checked)
        self.channel_tree.blockSignals(False)
        self._update_selected_carriers()

    def clear_all_channels(self):
        def set_state(item, st):
            item.setCheckState(0, st)
            for i in range(item.childCount()):
                set_state(item.child(i), st)

        self.channel_tree.blockSignals(True)
        for i in range(self.channel_tree.topLevelItemCount()):
            set_state(self.channel_tree.topLevelItem(i), Qt.CheckState.Unchecked)
        self.channel_tree.blockSignals(False)
        self._update_selected_carriers()

    def update_telemetry(self, num_channels: int, hop_rate_hz: float, cycle_ms: float):
        self.lbl_telem_metrics.setText(f"{num_channels} channels @ {hop_rate_hz:.1f} hops/s (Cycle: {cycle_ms:.1f} ms)")
