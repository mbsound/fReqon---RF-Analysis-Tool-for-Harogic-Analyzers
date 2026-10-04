"""
threats_panel.py - Intruder Alerts, Soundbase JSON & Marker Hierarchy Panel.
Manages automated threat detection against unknown RF transmitters,
Soundbase frequency coordination JSON imports, and active channel markers.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QDoubleSpinBox, QTableWidget, QHeaderView, QTreeWidget, QTreeWidgetItem, QFrame,
    QScrollArea, QTableWidgetItem, QMenu, QColorDialog, QComboBox
)
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import Qt, pyqtSignal, QPoint

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
    Intruder alert monitoring, Soundbase / WWB coordination file import, and marker management panel.
    """
    intruderAlertToggled = pyqtSignal(bool)
    intruderThresholdChanged = pyqtSignal(float)
    showThresholdToggled = pyqtSignal(bool)
    carrierMaskChanged = pyqtSignal()                 # mask shape or margin around coordinated carriers
    clearIntrudersClicked = pyqtSignal()
    addIntruderToMarkersClicked = pyqtSignal()
    fingerprintRequested = pyqtSignal()               # one MSCAN fingerprint pass
    intermodSettingsChanged = pyqtSignal()            # sources/orders/overlay changed
    intermodCheckRequested = pyqtSignal()             # check coordination for intermod hits
    intermodVerifyRequested = pyqtSignal()            # attenuation test on the selected carrier
    backgroundFingerprintToggled = pyqtSignal(bool)   # continuous pass on a second analyzer
    loadCoordinationClicked = pyqtSignal()
    loadSoundbaseClicked = loadCoordinationClicked # Backwards compatible alias
    markerItemChanged = pyqtSignal(object, int)
    carrierSelected = pyqtSignal(float)
    carrierColorChanged = pyqtSignal(str, str) # carrier_id, color_hex

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
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(6)
        
        t_lbl = QLabel("Threshold:")
        t_lbl.setStyleSheet("font-size: 11px;")
        
        self.show_thresh_cb = QCheckBox()
        self.show_thresh_cb.setChecked(True)
        self.show_thresh_cb.setToolTip("Display Threshold Line on Spectrum")
        self.show_thresh_cb.toggled.connect(self.showThresholdToggled.emit)
        
        self.intruder_thresh_spin = QDoubleSpinBox()
        self.intruder_thresh_spin.setRange(-150.0, 20.0)
        self.intruder_thresh_spin.setValue(-80.0)
        self.intruder_thresh_spin.setSuffix(" dBm")
        self.intruder_thresh_spin.valueChanged.connect(self.intruderThresholdChanged.emit)
        
        t_layout.addWidget(t_lbl)
        t_layout.addWidget(self.show_thresh_cb)
        t_layout.addWidget(self.intruder_thresh_spin, 1)
        intr_card.layout().addLayout(t_layout)

        # What a coordinated carrier accounts for: only its channel, or its channel plus
        # the skirts an ETSI EN 300 422-1 transmit mask allows it (core/emission_mask.py)
        m_layout = QHBoxLayout()
        m_layout.setContentsMargins(0, 0, 0, 0)
        m_layout.setSpacing(6)
        m_lbl = QLabel("Mask:")
        m_lbl.setStyleSheet("font-size: 11px;")
        self.carrier_mask_combo = QComboBox()
        # (kept narrow: this row must not make the panel wider than it is shown)
        self.carrier_mask_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.carrier_mask_combo.setMinimumContentsLength(11)
        self.carrier_mask_combo.addItem("ETSI auto", "auto")
        self.carrier_mask_combo.addItem("Channel only", "channel")
        self.carrier_mask_combo.addItem("ETSI digital", "digital")
        self.carrier_mask_combo.addItem("ETSI analogue", "analogue")
        self.carrier_mask_combo.setToolTip(
            "Channel only: whatever is inside a coordinated carrier's channel is that carrier; outside it the threshold applies.\n"
            "ETSI: the transmit mask of EN 300 422-1 is drawn around each coordinated carrier at the level it is received. "
            "Its own skirts stay under it; a hotter signal a little off its centre breaks through a skirt and is listed.\n"
            "ETSI auto picks the mask by device: FM systems (in-ear monitors, UHF-R, EW G3/G4 …) get the analogue mask, WMAS its own, the rest the digital one.")
        self.carrier_mask_combo.currentIndexChanged.connect(lambda _i: self.carrierMaskChanged.emit())
        self.carrier_mask_margin_spin = QDoubleSpinBox()
        self.carrier_mask_margin_spin.setRange(0.0, 30.0)
        self.carrier_mask_margin_spin.setDecimals(0)
        self.carrier_mask_margin_spin.setValue(6.0)
        self.carrier_mask_margin_spin.setPrefix("+")
        self.carrier_mask_margin_spin.setSuffix(" dB")
        margin_tip = (
            "Mask margin: how far above each carrier's received level its ETSI mask is drawn.\n\n"
            "The mask hangs on the carrier's own level, so with no margin the carrier would touch its own mask "
            "whenever it fades up or its modulation peaks. The margin is the headroom that keeps those from being listed.\n\n"
            "Lower (about +3 dB): tighter around the carrier, catches weaker signals beside it, more false alarms.\n"
            "Higher (about +10 dB): tolerates more level movement, misses weaker signals near the carrier.\n\n"
            "Used by the ETSI masks only; it has no effect with Mask set to Channel only.")
        self.carrier_mask_margin_spin.setToolTip(margin_tip)
        self.carrier_mask_margin_lbl = QLabel("Margin:")
        self.carrier_mask_margin_lbl.setStyleSheet("font-size: 11px;")
        self.carrier_mask_margin_lbl.setToolTip(margin_tip)
        self.carrier_mask_margin_spin.valueChanged.connect(lambda _v: self.carrierMaskChanged.emit())
        self.carrier_mask_margin_spin.setFixedWidth(100)
        m_layout.addWidget(m_lbl)
        m_layout.addWidget(self.carrier_mask_combo, 1)
        m_layout.addWidget(self.carrier_mask_margin_lbl)
        m_layout.addWidget(self.carrier_mask_margin_spin)
        # The margin belongs to the ETSI masks: greyed out with "Channel only"
        self.carrier_mask_combo.currentIndexChanged.connect(self._sync_mask_margin_enabled)
        self._sync_mask_margin_enabled()
        intr_card.layout().addLayout(m_layout)
        
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

        # Carrier fingerprinting: identify systems from their spectra. The main
        # sweep gives a first guess; an MSCAN pass (~1 kHz resolution) firms it up.
        fp_layout = QHBoxLayout()
        self.fingerprint_btn = QPushButton("Fingerprint Carriers")
        self.fingerprint_btn.setToolTip(
            "Dwell on each detected carrier with MSCAN (~1 kHz resolution) for a few seconds "
            "to identify it. The sweep pauses briefly; waterfall history is kept.")
        self.fingerprint_btn.clicked.connect(self.fingerprintRequested.emit)
        self.bg_fingerprint_cb = QCheckBox("Use Analyzer B")
        self.bg_fingerprint_cb.setToolTip(
            "With two analyzers connected, Analyzer B fingerprints carriers continuously "
            "while Analyzer A keeps sweeping (Analyzer B stops its own sweep).")
        self.bg_fingerprint_cb.toggled.connect(self.backgroundFingerprintToggled.emit)
        fp_layout.addWidget(self.fingerprint_btn)
        fp_layout.addWidget(self.bg_fingerprint_cb)
        intr_card.layout().addLayout(fp_layout)
        self.fingerprint_status_lbl = QLabel("Identification from the sweep; MSCAN fingerprinting gives more detail.")
        self.fingerprint_status_lbl.setWordWrap(True)
        self.fingerprint_status_lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
        intr_card.layout().addWidget(self.fingerprint_status_lbl)
        
        # --- 2. MARKERS & CHANNELS CARD (the coordination import sits in its header) ---
        markers_card = self._create_card("MARKERS & CHANNEL MASKS", layout)
        title_lbl = markers_card.layout().itemAt(0).widget()
        markers_card.layout().removeWidget(title_lbl)
        markers_hdr = QHBoxLayout()
        markers_hdr.setContentsMargins(0, 0, 0, 0)
        markers_hdr.addWidget(title_lbl)
        markers_hdr.addStretch()
        self.btn_soundbase_json = QPushButton("SB / WWB Import")
        self.btn_soundbase_json.setObjectName("pillBtn")
        self.btn_soundbase_json.setFixedHeight(22)
        self.btn_soundbase_json.setToolTip("Import Soundbase (.sbcoordsite, .json) or Wireless Workbench (.csv) coordination")
        self.btn_soundbase_json.clicked.connect(self.loadCoordinationClicked.emit)
        markers_hdr.addWidget(self.btn_soundbase_json)
        markers_card.layout().insertLayout(0, markers_hdr)

        self.soundbase_status_lbl = QLabel("No coordination file active")
        self.soundbase_status_lbl.setWordWrap(True)
        self.soundbase_status_lbl.setStyleSheet("color: #6e7681; font-size: 10px;")
        markers_card.layout().addWidget(self.soundbase_status_lbl)

        self.markers_tree = QTreeWidget()
        self.markers_tree.setColumnCount(2)
        self.markers_tree.setHeaderLabels(["Item / Channel", "Freq (MHz)"])
        self.markers_tree.setHeaderHidden(False)
        # Both columns can be dragged (a stretched column cannot); the last one takes the rest
        self.markers_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.markers_tree.header().setStretchLastSection(True)
        self.markers_tree.header().setMinimumSectionSize(40)
        self.markers_tree.setColumnWidth(0, 190)
        self.markers_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.markers_tree.setIndentation(14)
        self.markers_tree.setMinimumHeight(240)
        self.markers_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.markers_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self.markers_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 11px;
                color: #c9d1d9;
            }
            QTreeWidget::item {
                padding: 2px 2px;
            }
            QTreeWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QTreeWidget::item:hover {
                background-color: #161b22;
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
        self.markers_tree.itemChanged.connect(self._on_tree_item_changed)
        self.markers_tree.itemClicked.connect(self._on_tree_item_clicked)
        markers_card.layout().addWidget(self.markers_tree)
        
        # --- 2b. INTERMODULATION CARD ---
        im_card = self._create_card("INTERMODULATION", layout)
        im_form = QHBoxLayout()
        self.im_source_combo = QComboBox()
        self.im_source_combo.addItem("On-air coordinated carriers", "on_air")
        self.im_source_combo.addItem("All coordinated carriers", "all")
        self.im_source_combo.setToolTip(
            "Which transmitters create products. 'On air' uses coordinated carriers currently "
            "seen in the sweep; 'All' assumes every coordinated (non-spare) carrier is on.")
        self.im_source_combo.currentIndexChanged.connect(self.intermodSettingsChanged.emit)
        im_form.addWidget(self.im_source_combo)
        im_card.layout().addLayout(im_form)
        im_opts = QHBoxLayout()
        self.im3_cb = QCheckBox("IM3"); self.im3_cb.setChecked(True)
        self.im5_cb = QCheckBox("IM5"); self.im5_cb.setChecked(True)
        self.im3t_cb = QCheckBox("3-tone"); self.im3t_cb.setChecked(True)
        self.im_detected_cb = QCheckBox("+ detected")
        self.im_detected_cb.setToolTip(
            "Also mix in carriers detected by threat detection (front-end intermod in your "
            "receivers: everything reaching the antenna mixes, regardless of zone).")
        # The orders in the colours they are drawn in on the spectrum
        for cb, color in ((self.im3_cb, "#f97316"), (self.im5_cb, "#22d3ee"), (self.im3t_cb, "#e879f9")):
            cb.setStyleSheet(f"QCheckBox {{ color: {color}; font-weight: 600; }}")
        for cb in (self.im3_cb, self.im5_cb, self.im3t_cb, self.im_detected_cb):
            cb.toggled.connect(self.intermodSettingsChanged.emit)
            im_opts.addWidget(cb)
        im_card.layout().addLayout(im_opts)
        im_lvl = QHBoxLayout()
        im_lvl_lbl = QLabel("IM3 below carriers:")
        im_lvl_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.im_dbc_spin = QDoubleSpinBox()
        self.im_dbc_spin.setRange(0.0, 80.0)
        self.im_dbc_spin.setDecimals(0)
        self.im_dbc_spin.setValue(30.0)
        self.im_dbc_spin.setSuffix(" dB")
        self.im_dbc_spin.setToolTip(
            "How far below the carriers a 2-tone 3rd-order product is drawn: 20-25 dB for packs "
            "touching, 35-40 dB a metre apart. IM5 is taken 15 dB lower, 3-tone 6 dB higher. "
            "Carrier levels come from the sweep; a coordinated carrier that is not on air is "
            "assumed to be as strong as the on-air ones.")
        self.im_dbc_spin.valueChanged.connect(self.intermodSettingsChanged.emit)
        im_lvl.addWidget(im_lvl_lbl)
        im_lvl.addWidget(self.im_dbc_spin)
        im_lvl.addStretch()
        im_card.layout().addLayout(im_lvl)
        self.im_overlay_cb = QCheckBox("Show products on spectrum")
        self.im_overlay_cb.toggled.connect(self.intermodSettingsChanged.emit)
        im_card.layout().addWidget(self.im_overlay_cb)
        im_btns = QHBoxLayout()
        self.im_check_btn = QPushButton("Check Coordination")
        self.im_check_btn.setToolTip("List coordinated and spare frequencies that intermod products land on")
        self.im_check_btn.clicked.connect(self.intermodCheckRequested.emit)
        self.im_verify_btn = QPushButton("Verify Selected")
        self.im_verify_btn.setToolTip(
            "Attenuation test on the selected threat: adds 10 dB of input attenuation for a moment. "
            "A real signal drops 10 dB; intermod made inside the analyzer drops ~30 dB.")
        self.im_verify_btn.clicked.connect(self.intermodVerifyRequested.emit)
        im_btns.addWidget(self.im_check_btn)
        im_btns.addWidget(self.im_verify_btn)
        im_card.layout().addLayout(im_btns)
        self.im_table = QTableWidget(0, 3)
        self.im_table.setHorizontalHeaderLabels(["Carrier", "MHz", "Products on it"])
        # Columns can be dragged; the last one takes the rest
        self.im_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.im_table.horizontalHeader().setStretchLastSection(True)
        self.im_table.setColumnWidth(0, 96)
        self.im_table.setColumnWidth(1, 64)
        self.im_table.setToolTip("Coordinated and spare carriers that intermod products land on")
        self.im_table.verticalHeader().setVisible(False)
        self.im_table.setMinimumHeight(120)
        self.im_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        im_card.layout().addWidget(self.im_table)
        self.im_status_lbl = QLabel("Import a Soundbase or Wireless Workbench coordination to analyse intermod.")
        self.im_status_lbl.setWordWrap(True)
        self.im_status_lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
        im_card.layout().addWidget(self.im_status_lbl)

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

    def intermod_settings(self) -> dict:
        orders = tuple(o for o, cb in ((3, self.im3_cb), (5, self.im5_cb), (33, self.im3t_cb)) if cb.isChecked())
        return {"source": self.im_source_combo.currentData(), "orders": orders,
                "include_detected": self.im_detected_cb.isChecked(),
                "overlay": self.im_overlay_cb.isChecked(), "im3_dbc": self.im_dbc_spin.value()}

    def show_intermod_results(self, rows: list):
        """rows: [(carrier name, freq MHz, text, is_spare, n_hits)]"""
        self.im_table.setRowCount(len(rows))
        for r, (name, f_mhz, text, is_spare, n) in enumerate(rows):
            items = [QTableWidgetItem(name + (" (spare)" if is_spare else "")),
                     QTableWidgetItem(f"{f_mhz:.3f}"), QTableWidgetItem(text)]
            color = QColor("#f85149") if n and not is_spare else QColor("#d29922") if n else QColor("#3fb950")
            items[2].setForeground(color)
            items[2].setToolTip(text)
            for c, it in enumerate(items):
                self.im_table.setItem(r, c, it)

    def _sync_mask_margin_enabled(self, *_):
        etsi = self.carrier_mask_combo.currentData() != "channel"
        self.carrier_mask_margin_spin.setEnabled(etsi)
        self.carrier_mask_margin_lbl.setEnabled(etsi)

    def set_soundbase_active(self, filename: str, count: int):
        # The import button stays an import button (another file can be loaded over this one);
        # a green outline says a coordination is in use
        self.btn_soundbase_json.setStyleSheet("QPushButton { border: 1px solid #2ea043; color: #3fb950; }")
        self.btn_soundbase_json.setToolTip("A coordination is loaded. Click to import another "
                                           "(Soundbase .sbcoordsite / .json, or Wireless Workbench .csv)")
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

    def populate_soundbase_tree(self, soundbase_data: dict):
        """
        Populates the markers_tree with hierarchical Sites, Zones, Groups, and Carriers.
        """
        self.markers_tree.blockSignals(True)
        self.markers_tree.clear()
        
        sites = soundbase_data.get("sites", [])
        for site in sites:
            total_site_ch = sum(len(g['carriers']) for z in site.get('zones', []) for g in z.get('groups', []))
            s_item = QTreeWidgetItem([site["name"], f"{total_site_ch} ch"])
            s_item.setCheckState(0, Qt.CheckState.Checked)
            font = s_item.font(0)
            font.setBold(True)
            s_item.setFont(0, font)
            s_item.setForeground(0, QBrush(QColor("#f0f6fc")))
            s_item.setForeground(1, QBrush(QColor("#8b949e")))
            self.markers_tree.addTopLevelItem(s_item)
            
            for zone in site.get("zones", []):
                z_ch_count = sum(len(g['carriers']) for g in zone.get('groups', []))
                z_item = QTreeWidgetItem([zone["name"], f"{z_ch_count} ch"])
                z_item.setCheckState(0, Qt.CheckState.Checked)
                z_font = z_item.font(0)
                z_font.setBold(True)
                z_item.setFont(0, z_font)
                z_item.setForeground(0, QBrush(QColor("#c9d1d9")))
                z_item.setForeground(1, QBrush(QColor("#8b949e")))
                s_item.addChild(z_item)
                
                for group in zone.get("groups", []):
                    g_color = group.get("color", "#38bdf8")
                    g_item = QTreeWidgetItem([group["name"], f"{len(group['carriers'])} ch"])
                    g_item.setCheckState(0, Qt.CheckState.Checked)
                    g_item.setForeground(0, QBrush(QColor(g_color)))
                    g_item.setForeground(1, QBrush(QColor("#8b949e")))
                    z_item.addChild(g_item)
                    
                    for carrier in group.get("carriers", []):
                        c_freq = carrier["freq_mhz"]
                        c_name = carrier["name"]
                        c_bw = carrier["bandwidth_mhz"] * 1000
                        c_model = carrier.get("model", "")
                        c_color = carrier.get("color", g_color)
                        
                        c_item = QTreeWidgetItem([c_name, f"{c_freq:.3f}"])
                        c_item.setCheckState(0, Qt.CheckState.Checked)
                        c_item.setData(0, Qt.ItemDataRole.UserRole, c_freq)
                        c_item.setData(0, Qt.ItemDataRole.UserRole + 1, str(carrier["id"]))
                        c_item.setForeground(0, QBrush(QColor(c_color)))
                        c_item.setForeground(1, QBrush(QColor("#f0f6fc")))
                        
                        tooltip = (
                            f"Channel: {c_name}\n"
                            f"Frequency: {c_freq:.3f} MHz\n"
                            f"Bandwidth: {c_bw:.0f} kHz\n"
                            f"Model: {c_model}\n"
                            f"Group: {group['name']}\n"
                            f"Zone: {zone['name']}"
                        )
                        c_item.setToolTip(0, tooltip)
                        c_item.setToolTip(1, tooltip)
                        g_item.addChild(c_item)
                        
            s_item.setExpanded(True)
            for i in range(s_item.childCount()):
                s_item.child(i).setExpanded(True)
                
        self.markers_tree.blockSignals(False)

    def _on_tree_item_changed(self, item, col):
        if col != 0:
            return
        state = item.checkState(0)
        self.markers_tree.blockSignals(True)
        try:
            def apply_to_children(parent, s):
                for i in range(parent.childCount()):
                    ch = parent.child(i)
                    ch.setCheckState(0, s)
                    apply_to_children(ch, s)
            apply_to_children(item, state)
        finally:
            self.markers_tree.blockSignals(False)
            
        self.markerItemChanged.emit(item, col)

    def _on_tree_item_clicked(self, item, col):
        freq = item.data(0, Qt.ItemDataRole.UserRole)
        if freq is not None:
            self.carrierSelected.emit(float(freq))

    def _on_tree_context_menu(self, pos: QPoint):
        item = self.markers_tree.itemAt(pos)
        if not item:
            return
        c_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if c_id is None:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        ch_name = item.text(0)
        action_color = menu.addAction(f"Change Color for '{ch_name}'...")
        chosen = menu.exec(self.markers_tree.viewport().mapToGlobal(pos))
        if chosen == action_color:
            current_brush = item.foreground(0)
            initial_color = current_brush.color() if current_brush.color().isValid() else QColor("#38bdf8")
            selected_color = QColorDialog.getColor(initial_color, self, f"Select Color for {ch_name}")
            if selected_color.isValid():
                hex_col = selected_color.name()
                item.setForeground(0, QBrush(selected_color))
                self.carrierColorChanged.emit(str(c_id), hex_col)

    def update_carrier_color(self, carrier_id: str, new_color_hex: str):
        c_id = str(carrier_id)
        qcol = QColor(new_color_hex)
        if not qcol.isValid():
            return
        def search_tree(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if str(child.data(0, Qt.ItemDataRole.UserRole + 1)) == c_id:
                    child.setForeground(0, QBrush(qcol))
                    return True
                if search_tree(child):
                    return True
            return False

        for idx in range(self.markers_tree.topLevelItemCount()):
            top = self.markers_tree.topLevelItem(idx)
            if search_tree(top):
                break
