"""
locate_panel.py - Sensor network: where the sensors are, what they see, and
where each carrier is estimated to be.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from ... import combo_popups
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QDoubleSpinBox, QComboBox, QFormLayout, QFrame, QAbstractItemView,
)


class LocatePanel(QWidget):
    sensorPositionEdited = pyqtSignal(str, dict)    # slot_id, {source, lat, lon, x_m, y_m}
    settingsChanged = pyqtSignal(dict)              # path_loss_exp, margin_db
    carrierSelected = pyqtSignal(float)             # freq_hz
    tdoaRequested = pyqtSignal(float)               # freq_hz (Phase 2)
    openConnections = pyqtSignal()
    restartAverages = pyqtSignal()                  # forget the GNSS fixes averaged so far, on every sensor

    SENSOR_COLS = ("Sensor", "Position", "Lat / X (m)", "Lon / Y (m)", "Lock")
    SENSOR_ROW_H = 30
    CARRIER_COLS = ("MHz", "Device", "Conf", "Seen by", "Strongest", "Position", "±m")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        intro = QLabel("Several analyzers on the same span, each at a known place. Levels seen at each "
                       "sensor give a coarse position (power multilateration); the fingerprints from all "
                       "sensors are combined into one device guess.")
        intro.setWordWrap(True); intro.setStyleSheet("color: #8b949e; font-size: 11px;")
        root.addWidget(intro)

        hdr = QHBoxLayout()
        lbl = QLabel("SENSORS"); lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        hdr.addWidget(lbl); hdr.addStretch()
        self.conn_btn = QPushButton("Analyzers…"); self.conn_btn.setFixedHeight(22)
        self.conn_btn.setToolTip("Add analyzers and choose the Sensor Network topology in the Connection dialog")
        self.conn_btn.clicked.connect(self.openConnections.emit)
        self.restart_btn = QPushButton("Restart averaging"); self.restart_btn.setFixedHeight(22)
        self.restart_btn.setToolTip("Each sensor's GNSS position is the mean of its fixes. Start those means again:\n"
                                    "after moving an antenna, or once a weak signal has become a good one.")
        self.restart_btn.clicked.connect(self.restartAverages.emit)
        hdr.addWidget(self.restart_btn)
        hdr.addWidget(self.conn_btn)
        root.addLayout(hdr)

        self.sensor_table = QTableWidget(0, len(self.SENSOR_COLS))
        self.sensor_table.setHorizontalHeaderLabels(self.SENSOR_COLS)
        # The whole table fits the panel: the coordinates share what the fixed columns leave
        sh = self.sensor_table.horizontalHeader()
        sh.setMinimumSectionSize(30)
        Mode = QHeaderView.ResizeMode
        for col, mode in enumerate((Mode.ResizeToContents, Mode.Fixed, Mode.Stretch, Mode.Stretch, Mode.ResizeToContents)):
            sh.setSectionResizeMode(col, mode)
        self.sensor_table.setColumnWidth(1, 76)             # the GNSS / Manual selector
        self.sensor_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sensor_table.setStyleSheet("QTableWidget { font-size: 11px; } QTableWidget::item { padding: 2px 3px; } "
                                        "QHeaderView::section { padding: 3px 3px; font-size: 10px; }")
        self.sensor_table.setMinimumHeight(40 + 2 * self.SENSOR_ROW_H)       # the header and two analyzers, always (no scroll bar)
        self.sensor_table.horizontalHeaderItem(4).setToolTip(
            "Locked: the analyzer has a GNSS fix. Searching: GNSS is running without a fix yet.\n"
            "Height, satellites and signal are listed for each analyzer under the table.")
        self._last_sensor_rows = None
        self.sensor_table.verticalHeader().setVisible(False)
        self.sensor_table.verticalHeader().setDefaultSectionSize(self.SENSOR_ROW_H)
        self.sensor_table.setMaximumHeight(170)
        self.sensor_table.cellChanged.connect(self._on_sensor_cell_changed)
        root.addWidget(self.sensor_table)
        self.gnss_lbl = QLabel("")
        self.gnss_lbl.setWordWrap(True)
        self.gnss_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.gnss_lbl.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        self.gnss_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.gnss_lbl.setVisible(False)
        root.addWidget(self.gnss_lbl)
        hint = QLabel("Position: GNSS uses the analyzer's own fix (outdoors). Manual: type latitude/longitude, "
                      "or east/north metres measured on a venue drawing (then every sensor must use metres).")
        hint.setWordWrap(True); hint.setStyleSheet("color: #6e7681; font-size: 10px;")
        root.addWidget(hint)

        form = QFormLayout(); form.setContentsMargins(0, 4, 0, 4)
        self.exp_spin = QDoubleSpinBox(); self.exp_spin.setRange(1.5, 5.0); self.exp_spin.setSingleStep(0.1); self.exp_spin.setValue(3.0)
        exp_tip = ("How quickly a signal is taken to weaken with distance. Locate turns the difference in level\n"
                   "between two sensors into a difference in distance, and this is the conversion rate.\n\n"
                   "    2.0    free space, clear line of sight (6 dB weaker per doubling of distance)\n"
                   "    2.5    open air outdoors\n"
                   "    3.0 to 3.5    inside a venue: walls, people, scenery (9 to 10.5 dB per doubling)\n\n"
                   "Too low pushes estimates towards the loudest sensor; too high pulls them towards the middle.\n"
                   "To set it for a room, key a transmitter at a known spot and adjust until Locate puts it there.\n"
                   "Used by the power-based position only, not by Locate precisely (TDOA).")
        self.exp_spin.setToolTip(exp_tip)
        self.exp_spin.valueChanged.connect(self._emit_settings)
        form.addRow("Path-loss exponent:", self.exp_spin)
        self.margin_spin = QDoubleSpinBox(); self.margin_spin.setRange(6, 40); self.margin_spin.setValue(12); self.margin_spin.setSuffix(" dB")
        margin_tip = ("How far above a sensor's noise floor something must be to be listed as a carrier.\n"
                      "The floor is taken from an average of that sensor's last sweeps.\n\n"
                      "Lower: weaker carriers are listed, and more false ones with them.\n"
                      "Higher: only strong, unmistakable carriers.\n\n"
                      "A listed carrier is given a device name only once it is 20 dB over the floor at its\n"
                      "best sensor; below that it reads \"Too weak to identify\".")
        self.margin_spin.setToolTip(margin_tip)
        self.margin_spin.valueChanged.connect(self._emit_settings)
        form.addRow("Detection margin:", self.margin_spin)
        # The same explanation on the words as on the fields
        form.labelForField(self.exp_spin).setToolTip(exp_tip)
        form.labelForField(self.margin_spin).setToolTip(margin_tip)
        root.addLayout(form)

        lbl2 = QLabel("CARRIERS"); lbl2.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        root.addWidget(lbl2)
        self.carrier_table = QTableWidget(0, len(self.CARRIER_COLS))
        self.carrier_table.setHorizontalHeaderLabels(self.CARRIER_COLS)
        self.carrier_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.carrier_table.horizontalHeader().setStretchLastSection(True)
        self.carrier_table.verticalHeader().setVisible(False)
        self.carrier_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.carrier_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.carrier_table.itemSelectionChanged.connect(self._on_carrier_selected)
        root.addWidget(self.carrier_table, 1)

        self.tdoa_btn = QPushButton("Locate precisely (TDOA)")
        self.tdoa_btn.setEnabled(False)
        self.tdoa_btn.setToolTip("Every sensor captures the selected carrier starting on the same GPS second, for several "
                                 "seconds; the differences in arrival time give its position. Needs a GNSS fix on every "
                                 "sensor (three or more sensors for a point). Sweeping resumes by itself.")
        self.tdoa_btn.clicked.connect(self._on_tdoa)
        root.addWidget(self.tdoa_btn)
        self.status_lbl = QLabel(""); self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        root.addWidget(self.status_lbl)

    # --- sensors ---
    def show_sensors(self, sensors):
        """
        sensors: [{"id", "name", "source" ("gnss" / "manual"), "lat", "lon", "x_m", "y_m",
        "connected", "height", "sats", "lock", "has_fix"}]
        """
        if sensors == self._last_sensor_rows:
            return
        # The selectors are only replaced when the list of sensors or a source changes
        # (replacing one closes its open list and makes the row flicker); a new fix only
        # rewrites the text
        shape = lambda rows: [(d["id"], d["source"]) for d in rows or []]
        rebuild = shape(sensors) != shape(self._last_sensor_rows)
        self._last_sensor_rows = [dict(d) for d in sensors]
        self._loading = True
        t = self.sensor_table
        t.setRowCount(len(sensors))
        for r, d in enumerate(sensors):
            sid, name, source, connected = d["id"], d["name"], d["source"], d["connected"]
            lat, lon, x_m, y_m = d["lat"], d["lon"], d["x_m"], d["y_m"]
            it = QTableWidgetItem(name); it.setData(Qt.ItemDataRole.UserRole, sid)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it.setForeground(QColor("#c9d1d9" if connected else "#6e7681"))
            t.setItem(r, 0, it)
            if rebuild or t.cellWidget(r, 1) is None:
                cb = QComboBox(); cb.addItems(["GNSS", "Manual"]); cb.setCurrentIndex(0 if source == "gnss" else 1)
                cb.setStyleSheet("QComboBox { padding: 1px 4px; min-height: 20px; font-size: 11px; }")
                cb.currentIndexChanged.connect(lambda i, s=sid: self._on_source_changed(s, i))
                combo_popups.fit_list(cb)       # the cell is narrower than "Manual" with its tick
                t.setCellWidget(r, 1, cb)
            t.setRowHeight(r, self.SENSOR_ROW_H)
            if source == "manual" and x_m is not None:
                a, b = f"{x_m:g}", f"{y_m:g}"
            else:
                # A GNSS position to the metre here (the readout below has it in full); one typed
                # in is shown as typed
                digits = 5 if source == "gnss" else 6
                a = "" if lat is None else f"{lat:.{digits}f}"
                b = "" if lon is None else f"{lon:.{digits}f}"
            for c, v in ((2, a), (3, b)):
                it = QTableWidgetItem(v)
                it.setToolTip(v)                # in full, should the column ever be too narrow
                font = it.font(); font.setPixelSize(10); it.setFont(font)      # ten characters of longitude fit
                if source != "manual":
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable); it.setForeground(QColor("#8b949e"))
                t.setItem(r, c, it)
            lock_color = {"Locked": "#10b981", "Searching": "#f59e0b", "Weak fix": "#f59e0b", "Manual": "#c9d1d9",
                          "Disconnected": "#f43f5e"}.get(d["lock"], "#6e7681")
            it = QTableWidgetItem(d["lock"]); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it.setForeground(QColor(lock_color if connected or d["lock"] == "Disconnected" else "#6e7681"))
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if d.get("weak"):
                it.setToolTip(f"Locked, but on a weak fix ({d['weak']}): this position can be tens of metres out.\n"
                              "A better sky view for its GNSS antenna, then Restart averaging.")
            t.setItem(r, 4, it)
        self._loading = False

    def show_gnss(self, lines):
        """
        lines: [(sensor name, GNSS readout)], shown under the sensor table. A readout is a
        sentence, or [(label, value)] rows laid out as a small table per sensor.
        """
        blocks = []
        for name, readout in lines:
            if isinstance(readout, str):
                blocks.append(f"<b>{name}</b>: {readout}")
                continue
            rows = "".join(f"<tr><td style='color:#8b949e; padding-right:10px;'>{label}</td><td>{value}</td></tr>"
                           for label, value in readout)
            blocks.append(f"<b>{name}</b><table cellspacing='0' cellpadding='1'>{rows}</table>")
        text = "".join(f"<div style='margin-bottom:4px;'>{b}</div>" for b in blocks)
        if text != self.gnss_lbl.text():
            self.gnss_lbl.setText(text)
        self.gnss_lbl.setVisible(bool(lines))

    def _on_source_changed(self, slot_id, idx):
        if not self._loading:
            self.sensorPositionEdited.emit(slot_id, {"source": "gnss" if idx == 0 else "manual"})

    def _on_sensor_cell_changed(self, row, col):
        if self._loading or col not in (2, 3):
            return
        sid = self.sensor_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        a = self.sensor_table.item(row, 2).text().strip(); b = self.sensor_table.item(row, 3).text().strip()
        try:
            va, vb = float(a), float(b)
        except ValueError:
            return
        # lat/lon look like degrees; anything else is metres on a drawing
        if abs(va) <= 90 and abs(vb) <= 180 and ("." in a and "." in b) and (abs(va) > 0.5 or abs(vb) > 0.5):
            self.sensorPositionEdited.emit(sid, {"source": "manual", "lat": va, "lon": vb, "x_m": None, "y_m": None})
        else:
            self.sensorPositionEdited.emit(sid, {"source": "manual", "x_m": va, "y_m": vb, "lat": None, "lon": None})

    def _emit_settings(self, *_):
        self.settingsChanged.emit({"path_loss_exp": self.exp_spin.value(), "margin_db": self.margin_spin.value()})

    # --- carriers ---
    def show_carriers(self, estimates, selected_hz=None):
        t = self.carrier_table
        t.blockSignals(True)
        rows = sorted(estimates, key=lambda e: -(e.strongest[1] if e.strongest[1] is not None else -999))
        t.setRowCount(len(rows))
        sel_row = None
        for r, e in enumerate(rows):
            sid, lvl = e.strongest
            seen = ", ".join(sorted(k.split("_")[-1].upper() for k in e.levels))
            if e.fix is not None:
                pos = f"{e.fix.x:.0f}, {e.fix.y:.0f} m" if e.latlon is None else f"{e.latlon[0]:.5f}, {e.latlon[1]:.5f}"
                rad = f"{e.fix.radius_m:.0f}" if e.fix.radius_m < 1e4 else "—"
            else:
                pos, rad = "need 2+ positioned sensors", ""
            vals = (f"{e.freq_hz / 1e6:.3f}", e.device, f"{e.confidence}%", seen,
                    f"{(sid or '').split('_')[-1].upper()} {lvl:.0f} dBm" if sid else "", pos, rad)
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, e.freq_hz)
                t.setItem(r, c, it)
            if selected_hz is not None and abs(e.freq_hz - selected_hz) < 1e3:
                sel_row = r
        if sel_row is not None:
            t.selectRow(sel_row)
        t.blockSignals(False)

    def set_tdoa_state(self, busy: bool, text: str = None):
        self._tdoa_busy = busy
        self.tdoa_btn.setText(text or ("Locating…" if busy else "Locate precisely (TDOA)"))
        self.tdoa_btn.setEnabled(not busy and bool(self.carrier_table.selectionModel().selectedRows()))

    def _on_carrier_selected(self):
        rows = self.carrier_table.selectionModel().selectedRows()
        self.tdoa_btn.setEnabled(bool(rows) and not getattr(self, "_tdoa_busy", False))
        if rows:
            it = self.carrier_table.item(rows[0].row(), 0)
            if it is not None:
                self.carrierSelected.emit(float(it.data(Qt.ItemDataRole.UserRole)))

    def _on_tdoa(self):
        rows = self.carrier_table.selectionModel().selectedRows()
        if rows:
            self.tdoaRequested.emit(float(self.carrier_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)))

    def set_status(self, text: str):
        self.status_lbl.setText(text)
