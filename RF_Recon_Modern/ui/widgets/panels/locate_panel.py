"""
locate_panel.py - Sensor network: where the sensors are, what they see, and
where each carrier is estimated to be.
"""

from PyQt6.QtCore import Qt, pyqtSignal
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

    SENSOR_COLS = ("Sensor", "Position", "Lat / X (m)", "Lon / Y (m)", "Status")
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
        hdr.addWidget(self.conn_btn)
        root.addLayout(hdr)

        self.sensor_table = QTableWidget(0, len(self.SENSOR_COLS))
        self.sensor_table.setHorizontalHeaderLabels(self.SENSOR_COLS)
        self.sensor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.sensor_table.horizontalHeader().setStretchLastSection(True)
        self._last_sensor_rows = None
        self.sensor_table.verticalHeader().setVisible(False)
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
        self.exp_spin.setToolTip("Path-loss exponent: 2.0 free space, ~2.5 open air, 3–3.5 inside a venue")
        self.exp_spin.valueChanged.connect(self._emit_settings)
        form.addRow("Path-loss exponent:", self.exp_spin)
        self.margin_spin = QDoubleSpinBox(); self.margin_spin.setRange(6, 40); self.margin_spin.setValue(12); self.margin_spin.setSuffix(" dB")
        self.margin_spin.setToolTip("A carrier counts when it is this far above a sensor's noise floor")
        self.margin_spin.valueChanged.connect(self._emit_settings)
        form.addRow("Detection margin:", self.margin_spin)
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
        """sensors: [(slot_id, name, source, lat, lon, x_m, y_m, status, connected)]"""
        if sensors == self._last_sensor_rows:
            return          # rebuilding replaces the cell widgets; only do it on a change
        self._last_sensor_rows = list(sensors)
        self._loading = True
        t = self.sensor_table
        t.setRowCount(len(sensors))
        for r, (sid, name, source, lat, lon, x_m, y_m, status, connected) in enumerate(sensors):
            it = QTableWidgetItem(name); it.setData(Qt.ItemDataRole.UserRole, sid)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            it.setForeground(QColor("#c9d1d9" if connected else "#6e7681"))
            t.setItem(r, 0, it)
            cb = QComboBox(); cb.addItems(["GNSS", "Manual"]); cb.setCurrentIndex(0 if source == "gnss" else 1)
            cb.currentIndexChanged.connect(lambda i, s=sid: self._on_source_changed(s, i))
            t.setCellWidget(r, 1, cb)
            if source == "manual" and x_m is not None:
                a, b = f"{x_m:g}", f"{y_m:g}"
            else:
                a = "" if lat is None else f"{lat:.6f}"
                b = "" if lon is None else f"{lon:.6f}"
            for c, v in ((2, a), (3, b)):
                it = QTableWidgetItem(v)
                if source != "manual":
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable); it.setForeground(QColor("#8b949e"))
                t.setItem(r, c, it)
            it = QTableWidgetItem(status); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            t.setItem(r, 4, it)
        self._loading = False

    def show_gnss(self, lines):
        """lines: [(sensor name, one-line GNSS summary)], shown under the sensor table."""
        text = "<br>".join(f"<b>{name}</b>: {summary}" for name, summary in lines)
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
