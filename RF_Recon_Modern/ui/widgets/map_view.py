"""
map_view.py - Sensors and located transmitters on a local map (metres, east/north).
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtGui import QColor

from .plot_grid import install_grid


class MapView(QWidget):
    carrierClicked = pyqtSignal(float)   # freq_hz

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        hdr = QHBoxLayout()
        self.title_label = QLabel("SENSOR MAP")
        self.title_label.setStyleSheet("font-weight: 700; font-size: 11px; color: #8b949e; letter-spacing: 0.5px;")
        hdr.addWidget(self.title_label)
        hdr.addStretch()
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        hdr.addWidget(self.info_label)
        layout.addLayout(hdr)

        self.plot = pg.PlotWidget()
        self.plot.setBackground('#0d1117')
        self.plot.setAspectLocked(True)
        self.plot.setLabel('bottom', 'East (m)')
        self.plot.setLabel('left', 'North (m)')
        install_grid(self.plot, x=True, y=True, alpha=0.2)
        self.plot.hideButtons()
        layout.addWidget(self.plot, 1)

        self.sensor_scatter = pg.ScatterPlotItem(size=14, symbol='t1', pen=pg.mkPen('#38bdf8'), brush=pg.mkBrush('#38bdf8'))
        self.plot.addItem(self.sensor_scatter)
        self.sensor_labels = []
        self.carrier_scatter = pg.ScatterPlotItem(size=9, symbol='o', pen=pg.mkPen('#f97316'), brush=pg.mkBrush(249, 115, 22, 160))
        self.carrier_scatter.sigClicked.connect(self._on_carrier_clicked)
        self.plot.addItem(self.carrier_scatter)
        self.selected_marker = pg.ScatterPlotItem(size=18, symbol='x', pen=pg.mkPen('#f43f5e', width=2))
        self.plot.addItem(self.selected_marker)
        self.ellipse = self.plot.plot(pen=pg.mkPen(QColor(244, 63, 94, 180), width=1.0, style=Qt.PenStyle.DashLine))
        self.ellipse2 = self.plot.plot(pen=pg.mkPen(QColor(244, 63, 94, 70), width=1.0, style=Qt.PenStyle.DotLine))
        self.selected_label = pg.TextItem(anchor=(0, 1), color='#f43f5e')
        self.plot.addItem(self.selected_label)
        self._carrier_keys = []

    def set_sensors(self, sensors):
        """sensors: [(name, x, y, status)]"""
        for t in self.sensor_labels:
            self.plot.removeItem(t)
        self.sensor_labels = []
        if not sensors:
            self.sensor_scatter.setData([], [])
            return
        xs = [s[1] for s in sensors]; ys = [s[2] for s in sensors]
        self.sensor_scatter.setData(xs, ys)
        for name, x, y, status in sensors:
            t = pg.TextItem(f"{name}\n{status}", anchor=(0.5, -0.3), color='#38bdf8')
            t.setPos(x, y)
            self.plot.addItem(t)
            self.sensor_labels.append(t)
        pad = max(20.0, 0.25 * max(np.ptp(xs) if len(xs) > 1 else 0, np.ptp(ys) if len(ys) > 1 else 0, 40))
        self.plot.setXRange(min(xs) - pad, max(xs) + pad, padding=0)
        self.plot.setYRange(min(ys) - pad, max(ys) + pad, padding=0)

    def set_carriers(self, estimates, selected_hz=None):
        """estimates: iterable of CarrierEstimate with a fix."""
        pts, keys = [], []
        sel = None
        for e in estimates:
            if e.fix is None:
                continue
            pts.append((e.fix.x, e.fix.y)); keys.append(e.freq_hz)
            if selected_hz is not None and abs(e.freq_hz - selected_hz) < 1e3:
                sel = e
        self._carrier_keys = keys
        self.carrier_scatter.setData([p[0] for p in pts], [p[1] for p in pts])
        if sel is None:
            self.selected_marker.setData([], []); self.ellipse.setData([], []); self.ellipse2.setData([], [])
            self.selected_label.setText("")
            return
        f = sel.fix
        self.selected_marker.setData([f.x], [f.y])
        if np.all(np.isfinite(f.cov)) and f.radius_m < 1e4:
            ex, ey = f.ellipse(1.0); self.ellipse.setData(ex, ey)
            ex, ey = f.ellipse(2.0); self.ellipse2.setData(ex, ey)
        else:
            self.ellipse.setData([], []); self.ellipse2.setData([], [])
        where = f"±{f.radius_m:.0f} m ({f.method}, {f.n_sensors} sensors)"
        self.selected_label.setText(f"{sel.freq_hz / 1e6:.3f} MHz  {sel.device}\n{where}")
        self.selected_label.setPos(f.x, f.y)

    def _on_carrier_clicked(self, plot, points):
        if points is not None and len(points):
            i = points[0].index()
            if 0 <= i < len(self._carrier_keys):
                self.carrierClicked.emit(self._carrier_keys[i])
