"""
dtv_panel.py - Broadcast Television Coordination & Station Database Panel.
Provides FCC & OFCOM broadcast station lookups by postal code,
threshold line placement, occupied channel auto-detection, T-Band scanning, and zone mapping.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QDoubleSpinBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QScrollArea,
    QButtonGroup, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

class DTVPanel(QWidget):
    """
    Broadcast television coordination and live station analysis panel.
    """
    lookupRequested = pyqtSignal(str)
    updateUkDataRequested = pyqtSignal()
    thresholdChanged = pyqtSignal(float)
    showThresholdToggled = pyqtSignal(bool)
    dtvDetectToggled = pyqtSignal(bool)
    tbandScanToggled = pyqtSignal(bool)
    stationSelected = pyqtSignal(int, int) # row, column
    zoneSelected = pyqtSignal(int)
    detectSettingsChanged = pyqtSignal()        # automatic/fixed, margin or threshold
    stationMaskToggled = pyqtSignal(object, bool)   # channel, mask on
    allMasksRequested = pyqtSignal(bool)        # every listed channel's mask on / off

    def set_lookup_busy(self, busy: bool):
        self.lookup_btn.setEnabled(not busy)
        self.lookup_btn.setText("Looking up…" if busy else "Lookup")

    def set_region(self, region: str):
        """Offer what the region's transmitter lookup needs: Ofcom's data import is the UK's."""
        self.update_uk_btn.setVisible(region == "UK")
        # A change of region clears the lookup's results, so its status line goes back to the hint
        changed = region != getattr(self, "_region", None)
        self._region = region
        if changed or self.lookup_status_lbl.text() in self.REGION_HINTS.values() or not self.lookup_status_lbl.text():
            self.lookup_status_lbl.setText(self.REGION_HINTS.get(region, self.REGION_HINTS[None]))
            self.lookup_status_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")

    REGION_HINTS = {"North America": "Live FCC lookup by ZIP code", "UK": "Imported Ofcom data, by postcode",
                    "Spain": "National plan: the channels of the postcode's area (código postal)",
                    "Portugal": "Transmitter list by postcode (código postal, e.g. 1000-001)",
                    None: "No station database for this region"}

    def set_lookup_status(self, text: str, warn: bool = False):
        self.lookup_status_lbl.setText(text)
        self.lookup_status_lbl.setStyleSheet(
            f"color: {'#d29922' if warn else '#8b949e'}; font-size: 11px;")

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

        # Where the results came from (live FCC, cached, bundled, Ofcom import)
        self.lookup_status_lbl = QLabel("")
        self.lookup_status_lbl.setWordWrap(True)
        self.lookup_status_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        lookup_card.layout().addWidget(self.lookup_status_lbl)

        self.update_uk_btn = QPushButton("Update UK Data…")
        self.update_uk_btn.setToolTip("Import Ofcom's television transmitter spreadsheet")
        self.update_uk_btn.clicked.connect(self.updateUkDataRequested.emit)
        lookup_card.layout().addWidget(self.update_uk_btn)
        self.update_uk_btn.setVisible(False)        # shown for the UK region only (set_region)
        
        # --- 2. DETECTION & THRESHOLDS CARD ---
        thresh_card = self._create_card("OCCUPIED CHANNEL DETECTOR", layout)
        t_form = QFormLayout()
        t_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        
        # A TV signal fills its channel well above the noise floor. Automatic
        # finds the floor in the sweep itself; Fixed compares with a set level.
        self.detect_mode_combo = QComboBox()
        self.detect_mode_combo.addItem("Automatic", "auto")
        self.detect_mode_combo.addItem("Fixed threshold", "fixed")
        self.detect_mode_combo.setToolTip(
            "Automatic: a channel is occupied when a signal fills it at least the margin above the\n"
            "noise floor found in the sweep. Works at any RBW, gain or antenna; needs a sweep at\n"
            "least three channels wide.\n"
            "Fixed threshold: the same test against a level you set.")
        self.detect_mode_combo.currentIndexChanged.connect(self._on_detect_mode_changed)
        t_form.addRow("Detection:", self.detect_mode_combo)

        self.margin_spin = QDoubleSpinBox()
        self.margin_spin.setRange(3.0, 40.0)
        self.margin_spin.setValue(6.0)
        self.margin_spin.setSingleStep(1.0)
        self.margin_spin.setDecimals(0)
        self.margin_spin.setSuffix(" dB")
        self.margin_spin.setToolTip("Automatic detection: how far above the noise floor a channel must be to count\n"
                                    "as occupied. Changing it selects Automatic. Dragging the line on the spectrum\n"
                                    "in Automatic mode sets this.")
        self.margin_spin.valueChanged.connect(lambda _v: self._on_value_edited("auto"))
        t_form.addRow("Margin:", self.margin_spin)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-150.0, 0.0)
        self.threshold_spin.setValue(-70.0)
        self.threshold_spin.setSuffix(" dBm")
        self.threshold_spin.setToolTip("Fixed threshold: the level a channel must reach. Changing it selects\n"
                                       "Fixed threshold. Dragging the line on the spectrum in that mode sets this.")
        self.threshold_spin.valueChanged.connect(self.thresholdChanged.emit)
        self.threshold_spin.valueChanged.connect(lambda _v: self._on_value_edited("fixed"))
        t_form.addRow("DTV Threshold:", self.threshold_spin)
        
        self.show_thresh_cb = QCheckBox("Display Threshold Line on Spectrum")
        self.show_thresh_cb.setToolTip("Fixed threshold: the level you set.\n"
                                       "Automatic: the detector's level, the noise floor plus the margin.\n"
                                       "Drag the line to change the threshold or the margin.")
        self.show_thresh_cb.toggled.connect(self.showThresholdToggled.emit)
        t_form.addRow(self.show_thresh_cb)
        thresh_card.layout().addLayout(t_form)
        self._on_detect_mode_changed()
        
        btn_layout = QHBoxLayout()
        self.dtv_detect_btn = QPushButton("Auto DTV Detect")
        self.dtv_detect_btn.setCheckable(True)
        self.dtv_detect_btn.toggled.connect(self.dtvDetectToggled.emit)
        
        self.tband_scan_btn = QPushButton("Scan T-Band")
        self.tband_scan_btn.setCheckable(True)
        self.tband_scan_btn.setToolTip("Watch TV channels 14-20 (470-512 MHz) and work out what is in each: a TV\n"
                                       "station fills the channel; land mobile radio is narrow carriers that key on\n"
                                       "and off. Channels with land mobile radio are masked red.")
        self.tband_scan_btn.toggled.connect(self.tbandScanToggled.emit)
        
        btn_layout.addWidget(self.dtv_detect_btn)
        btn_layout.addWidget(self.tband_scan_btn)
        thresh_card.layout().addLayout(btn_layout)
        
        self.detect_status_lbl = QLabel("Auto DTV: Idle (Disabled)")
        self.detect_status_lbl.setStyleSheet("color: #8b949e; font-size: 11px; padding-top: 4px;")
        thresh_card.layout().addWidget(self.detect_status_lbl)
        self.tband_status_lbl = QLabel("")
        self.tband_status_lbl.setWordWrap(True)
        self.tband_status_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.tband_status_lbl.hide()
        thresh_card.layout().addWidget(self.tband_status_lbl)
        
        # --- 3. NEARBY STATIONS TABLE CARD ---
        stations_card = self._create_card("NEARBY BROADCAST TRANSMITTERS", layout)

        # Masks: the tick beside each channel, or all of them at once
        mask_row = QHBoxLayout()
        mask_lbl = QLabel("Masks:")
        mask_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.masks_on_btn = QPushButton("All On")
        self.masks_off_btn = QPushButton("All Off")
        for btn, on in ((self.masks_on_btn, True), (self.masks_off_btn, False)):
            btn.setObjectName("pillBtn")
            btn.setFixedHeight(20)
            btn.setToolTip("Show the channel mask of every listed transmitter" if on
                           else "Hide the channel masks of the listed transmitters")
            btn.clicked.connect(lambda _c=False, on=on: self.allMasksRequested.emit(on))
        mask_row.addWidget(mask_lbl)
        mask_row.addWidget(self.masks_on_btn)
        mask_row.addWidget(self.masks_off_btn)
        mask_row.addStretch()
        stations_card.layout().addLayout(mask_row)
        
        self._rows_by_channel = {}      # channel -> table rows showing it
        self._mask_boxes = {}           # channel -> the Mask checkboxes of those rows
        self.stations_table = QTableWidget(0, len(self.STATION_COLUMNS))
        self.stations_table.setHorizontalHeaderLabels([name for name, _w, _tip in self.STATION_COLUMNS])
        for col, (_name, width, tip) in enumerate(self.STATION_COLUMNS):
            self.stations_table.horizontalHeaderItem(col).setToolTip(tip)
            self.stations_table.setColumnWidth(col, width)
        self.stations_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._user_sized_columns(self.stations_table)
        self.stations_table.verticalHeader().setVisible(False)
        self.stations_table.setMinimumHeight(180)
        self.stations_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.stations_table.cellClicked.connect(self.stationSelected.emit)
        stations_card.layout().addWidget(self.stations_table)
        
        # --- 4. DTV COORDINATION ZONES CARD ---
        zones_card = self._create_card("COORDINATION ZONES", layout)
        self.zones_table = QTableWidget(0, 2)
        self.zones_table.setHorizontalHeaderLabels(["Select", "Zone Name"])
        self.zones_table.setColumnWidth(0, 60)
        self._user_sized_columns(self.zones_table)
        self.zones_table.verticalHeader().setVisible(False)
        self.zones_table.setMaximumHeight(160)
        self.zones_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        zones_card.layout().addWidget(self.zones_table)
        
        self.zone_btn_group = QButtonGroup(self)
        self.zone_btn_group.idClicked.connect(self.zoneSelected.emit)
        
        layout.addStretch()

    # Transmitter table columns: (header, default width, tooltip). The first four
    # fit the panel; the rest are reached by scrolling or by resizing columns.
    COL_MASK, COL_CH, COL_STATION, COL_LIVE, COL_DIST, COL_ERP = range(6)
    STATION_COLUMNS = (
        ("Mask", 46, "Show this channel's mask on the spectrum and waterfall"),
        ("Ch", 48, "RF channel"),
        ("Station", 88, "Call sign (US) or transmitter site"),
        ("Live", 68, "Measured by Auto DTV Detect: dB above the noise floor, or clear"),
        ("Dist", 60, "Distance from the looked-up location"),
        ("ERP", 66, "Effective radiated power"),
    )

    @staticmethod
    def _user_sized_columns(table: QTableWidget):
        """Columns the user can drag to resize and reorder; the table scrolls sideways when they are wider than it."""
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsMovable(True)
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(44)     # two digits plus the cell padding
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)

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

    # --- Detection settings ---
    @property
    def auto_threshold(self) -> bool:
        return self.detect_mode_combo.currentData() == "auto"

    @property
    def margin_db(self) -> float:
        return float(self.margin_spin.value())

    def _on_detect_mode_changed(self, *_):
        # Both values stay editable; the one not in use is dimmed. Editing either
        # selects the mode it belongs to (see _on_value_edited).
        auto = self.auto_threshold
        dim = "QDoubleSpinBox { color: #6e7681; }"
        self.margin_spin.setStyleSheet("" if auto else dim)
        self.threshold_spin.setStyleSheet(dim if auto else "")
        self.detectSettingsChanged.emit()

    def _on_value_edited(self, mode: str):
        """The margin belongs to Automatic and the threshold to Fixed: changing one selects its mode."""
        idx = self.detect_mode_combo.findData(mode)
        if idx >= 0 and self.detect_mode_combo.currentIndex() != idx:
            self.detect_mode_combo.setCurrentIndex(idx)     # emits detectSettingsChanged
        else:
            self.detectSettingsChanged.emit()

    def set_tband_status(self, text: str, state: str = "idle"):
        color = {"ok": "#f87171", "warn": "#d29922"}.get(state, "#8b949e")
        self.tband_status_lbl.setText(text)
        self.tband_status_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.tband_status_lbl.setVisible(bool(text))

    def set_detect_status(self, text: str, state: str = "idle"):
        """state: idle (grey), ok (blue) or warn (amber)."""
        color, weight = {"ok": ("#38bdf8", 600), "warn": ("#d29922", 600)}.get(state, ("#8b949e", 400))
        self.detect_status_lbl.setWordWrap(True)
        self.detect_status_lbl.setText(text)
        self.detect_status_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: {weight}; padding-top: 4px;")

    # --- Transmitter table ---
    def show_stations(self, rows: list):
        """
        Fill the table. rows: (channel, name, ERP text, distance text, mask on, is LMR).
        The checkbox in the Mask column shows and hides the channel's mask.
        """
        table = self.stations_table
        table.setRowCount(0)            # drops the previous rows' checkboxes
        table.setRowCount(len(rows))
        self._rows_by_channel, self._mask_boxes = {}, {}
        for r, (ch, name, erp, dist, mask_on, is_lmr) in enumerate(rows):
            box = QCheckBox()
            box.setChecked(bool(mask_on))
            box.setToolTip(f"Show the mask of channel {ch} on the spectrum and waterfall")
            box.toggled.connect(lambda checked, ch=ch: self._on_mask_box_toggled(ch, checked))
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            holder_layout.addWidget(box)
            table.setCellWidget(r, self.COL_MASK, holder)
            self._mask_boxes.setdefault(ch, []).append(box)

            ch_item = QTableWidgetItem(str(ch))
            ch_item.setData(Qt.ItemDataRole.UserRole, ch)
            name_item = QTableWidgetItem(name)
            name_item.setToolTip(f"{name}\nChannel {ch} · {erp} · {dist}")
            if is_lmr:
                name_item.setForeground(QColor("#f87171"))
            cells = {self.COL_CH: ch_item, self.COL_STATION: name_item, self.COL_LIVE: QTableWidgetItem("--"),
                     self.COL_DIST: QTableWidgetItem(dist), self.COL_ERP: QTableWidgetItem(erp)}
            for c, item in cells.items():
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r, c, item)
            self._rows_by_channel.setdefault(ch, []).append(r)

    def listed_channels(self) -> list:
        return list(self._rows_by_channel)

    def channel_at_row(self, row: int):
        item = self.stations_table.item(row, self.COL_CH)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def mask_checkbox(self, row: int) -> QCheckBox:
        """The Mask checkbox of a table row."""
        ch = self.channel_at_row(row)
        return self._mask_boxes[ch][self._rows_by_channel[ch].index(row)]

    def set_mask_checked(self, channel, checked: bool):
        """Reflect a mask turned on or off elsewhere (detection, the channel bar, a row sharing the channel)."""
        for box in self._mask_boxes.get(channel, ()):
            if box.isChecked() != bool(checked):
                box.blockSignals(True)
                box.setChecked(bool(checked))
                box.blockSignals(False)

    def set_live_rf(self, channel, text: str, occupied=None, detail: str = ""):
        """Measured state of a channel: occupied True (red), False (green) or None (unknown)."""
        color = {True: "#f87171", False: "#4ade80"}.get(occupied, "#8b949e")
        for r in self._rows_by_channel.get(channel, ()):
            item = self.stations_table.item(r, self.COL_LIVE)
            if item is not None and (item.text() != text or item.toolTip() != detail):
                item.setText(text)
                item.setToolTip(detail)
                item.setForeground(QColor(color))

    def _on_mask_box_toggled(self, channel, checked: bool):
        # Transmitters sharing the channel share its mask
        self.set_mask_checked(channel, checked)
        self.stationMaskToggled.emit(channel, checked)
