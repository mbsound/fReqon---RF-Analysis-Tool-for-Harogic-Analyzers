"""
det_view.py - Zero-Span / Power vs. Time (DET) High-Speed Oscilloscope Viewport.
Visualizes high-rate time-domain power envelopes ($t$ vs. $P_{dBm}$), provides
interactive dual delta time cursors, TDMA framing grids (DECT, Bolero, Bluetooth),
and real-time burst metrics.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox, QPushButton, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

class PowerAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{v:.0f}" for v in values]

class TimeAxisItem(pg.AxisItem):
    """
    Format time axis with microsecond / millisecond units.
    """
    def tickStrings(self, values, scale, spacing):
        strings = []
        for val in values:
            if val < 1000.0:
                strings.append(f"{val:.0f} ns")
            elif val < 1000000.0:
                strings.append(f"{val/1000.0:.1f} us")
            else:
                strings.append(f"{val/1000000.0:.2f} ms")
        return strings


class DETView(QWidget):
    """
    Zero-Span Power vs. Time (DET) Oscilloscope Viewport.
    """
    fitWindowRequested = pyqtSignal(float)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detView")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header Toolbar / HUD
        hud_bar = QFrame()
        hud_bar.setFixedHeight(28)
        hud_bar.setStyleSheet("background-color: #161b22; border-bottom: 1px solid #30363d; padding: 2px 6px;")
        hud_layout = QHBoxLayout(hud_bar)
        hud_layout.setContentsMargins(6, 2, 6, 2)
        hud_layout.setSpacing(10)
        
        mode_tag = QLabel("ZERO-SPAN (DET) POWER VS TIME")
        mode_tag.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 700; color: #10b981; letter-spacing: 0.5px;")
        hud_layout.addWidget(mode_tag)
        
        hud_layout.addStretch()
        
        # TDMA Grid Overlay Controls
        self.grid_enable_check = QCheckBox("TDMA Grid:")
        self.grid_enable_check.setStyleSheet("""
            QCheckBox {
                color: #8b949e;
                font-size: 10px;
                font-weight: 700;
            }
            QCheckBox:checked {
                color: #38bdf8;
            }
            QCheckBox::indicator {
                width: 12px;
                height: 12px;
                border: 1px solid #30363d;
                border-radius: 2px;
                background: #161b22;
            }
            QCheckBox::indicator:checked {
                background-color: #38bdf8;
                border-color: #0284c7;
            }
        """)
        self.grid_enable_check.toggled.connect(self._on_grid_enable_toggled)
        hud_layout.addWidget(self.grid_enable_check)
        
        self.grid_combo = QComboBox()
        self.grid_combo.addItems([
            "DECT Full-Slot (416.7 us)",
            "DECT Half-Slot (208.3 us)",
            "Bolero Slot (1.0 ms)",
            "Bolero Slot (833.3 us)",
            "Bluetooth (625.0 us)"
        ])
        self.grid_combo.setFixedHeight(20)
        self.grid_combo.setEnabled(False)
        self.grid_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.grid_combo.wheelEvent = lambda event: None
        self.grid_combo.setStyleSheet("""
            QComboBox {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 3px;
                color: #c9d1d9;
                font-size: 10px;
                font-weight: 600;
                padding: 1px 6px;
            }
            QComboBox:disabled {
                color: #484f58;
                border-color: #21262d;
            }
            QComboBox:hover:!disabled {
                border-color: #38bdf8;
            }
        """)
        self.grid_combo.currentTextChanged.connect(self._on_grid_changed)
        hud_layout.addWidget(self.grid_combo)
        
        self.align_t1_check = QCheckBox("Lock to T1")
        self.align_t1_check.setEnabled(False)
        self.align_t1_check.setToolTip("Anchor Slot 0 boundary directly to Cursor T1")
        self.align_t1_check.setStyleSheet("""
            QCheckBox {
                color: #8b949e;
                font-size: 10px;
                font-weight: 600;
            }
            QCheckBox:checked {
                color: #facc15;
            }
            QCheckBox:disabled {
                color: #484f58;
            }
            QCheckBox::indicator {
                width: 12px;
                height: 12px;
                border: 1px solid #30363d;
                border-radius: 2px;
                background: #161b22;
            }
            QCheckBox::indicator:checked {
                background-color: #facc15;
                border-color: #eab308;
            }
        """)
        self.align_t1_check.toggled.connect(lambda: self._update_tdma_grid())
        hud_layout.addWidget(self.align_t1_check)
        
        self.fit_window_btn = QPushButton("Fit Window")
        self.fit_window_btn.setFixedHeight(20)
        self.fit_window_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.15);
                color: #f59e0b;
                border: 1px solid #f59e0b;
                border-radius: 3px;
                padding: 1px 6px;
                font-weight: 600;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: rgba(245, 158, 11, 0.3);
            }
        """)
        self.fit_window_btn.hide()
        self.fit_window_btn.clicked.connect(self._on_auto_fit_clicked)
        hud_layout.addWidget(self.fit_window_btn)
        
        self.telemetry_hud = QLabel("PEAK: ---.- dBm | AVG: ---.- dBm | BURST: ---.- us | DUTY: --%")
        self.telemetry_hud.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600; color: #c9d1d9; background-color: #0d1117; padding: 2px 6px; border-radius: 3px; border: 1px solid #30363d;")
        hud_layout.addWidget(self.telemetry_hud)
        
        layout.addWidget(hud_bar)
        
        # Plot Layout
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground('#0d1117')
        layout.addWidget(self.glw)
        
        self.x_axis = TimeAxisItem(orientation='bottom')
        self.y_axis = PowerAxisItem(orientation='left')
        
        self.plot_item = self.glw.addPlot(axisItems={'bottom': self.x_axis, 'left': self.y_axis})
        self.plot_item.showGrid(x=True, y=True, alpha=0.15)
        self.plot_item.setMenuEnabled(False)
        self.plot_item.getViewBox().disableAutoRange()
        
        self.ref_level = 0.0
        self.bottom_level = -110.0
        self.plot_item.setYRange(self.bottom_level, self.ref_level + 5.0, padding=0)
        
        # Oscilloscope Waveform Curve (Emerald Green / Cyan)
        self.power_curve = self.plot_item.plot(pen=pg.mkPen(color='#10b981', width=1.6), name="Power vs Time")
        self.power_curve.setDownsampling(auto=True, method='peak')
        self.power_curve.setClipToView(True)
        
        # Delta Cursors (T1 and T2)
        self.cursor_t1 = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen(color='#facc15', width=1.5, style=Qt.PenStyle.SolidLine), label="T1: 500.0 us")
        self.cursor_t2 = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen(color='#38bdf8', width=1.5, style=Qt.PenStyle.SolidLine), label="T2: 1500.0 us")
        self.cursor_t1.setPos(500000.0) # 500 us
        self.cursor_t2.setPos(1500000.0) # 1.5 ms
        
        self.plot_item.addItem(self.cursor_t1)
        self.plot_item.addItem(self.cursor_t2)
        
        self.cursor_t1.sigPositionChanged.connect(self._on_cursor_moved)
        self.cursor_t2.sigPositionChanged.connect(self._on_cursor_moved)
        self._on_cursor_moved()
        
        # TDMA Grid Line Items
        self.tdma_grid_lines = []
        
        # Mouse Crosshairs
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color='#6e7681', width=1, style=Qt.PenStyle.DashLine))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(color='#6e7681', width=1, style=Qt.PenStyle.DashLine))
        self.v_line.hide()
        self.h_line.hide()
        self.plot_item.addItem(self.v_line)
        self.plot_item.addItem(self.h_line)
        
        self.plot_item.scene().sigMouseMoved.connect(self._on_mouse_moved)
        
        self.current_time_ns = None
        self.current_power_dbm = None
        self._last_max_time_ns = 0.0

    def _on_grid_enable_toggled(self, checked: bool):
        self.grid_combo.setEnabled(checked)
        self.align_t1_check.setEnabled(checked)
        self._update_tdma_grid()

    def _on_grid_changed(self, grid_mode: str):
        self._update_tdma_grid()

    def _get_active_interval_ns(self) -> float:
        txt = self.grid_combo.currentText()
        if "DECT Full-Slot" in txt:
            return 416666.67
        elif "DECT Half-Slot" in txt:
            return 208333.33
        elif "Bolero Slot (1.0 ms)" in txt:
            return 1000000.0
        elif "Bolero Slot (833.3 us)" in txt:
            return 833333.33
        elif "Bluetooth" in txt:
            return 625000.0
        return 0.0

    def _on_auto_fit_clicked(self):
        interval_ns = self._get_active_interval_ns()
        if interval_ns > 0:
            min_duration_ns = max(interval_ns * 12.0, 5000000.0)
            self.fitWindowRequested.emit(min_duration_ns)

    def _update_tdma_grid(self):
        # Clear existing grid lines
        for line in self.tdma_grid_lines:
            self.plot_item.removeItem(line)
        self.tdma_grid_lines.clear()
        
        if not self.grid_enable_check.isChecked():
            self.fit_window_btn.hide()
            return
            
        interval_ns = self._get_active_interval_ns()
        if interval_ns <= 0:
            self.fit_window_btn.hide()
            return
            
        max_time_ns = self.current_time_ns[-1] if (self.current_time_ns is not None and len(self.current_time_ns) > 0) else 0.0
        self._last_max_time_ns = max_time_ns
        
        if max_time_ns > 0 and max_time_ns < interval_ns:
            self.fit_window_btn.setText(f"Fit Window to {interval_ns/1000.0:.0f} us")
            self.fit_window_btn.show()
        else:
            self.fit_window_btn.hide()
            
        if max_time_ns <= 0:
            return
            
        anchor_ns = 0.0
        if self.align_t1_check.isChecked():
            anchor_ns = self.cursor_t1.value()
            
        is_dect = "DECT" in self.grid_combo.currentText()
        
        # 1. Forward from anchor
        cur_t = anchor_ns
        slot_idx = 0
        while cur_t <= max_time_ns:
            if cur_t >= 0:
                if is_dect and (slot_idx % 12 == 0):
                    pen = pg.mkPen(color='#f59e0b', width=1.8, style=Qt.PenStyle.SolidLine)
                    label_txt = f"S{slot_idx % 24} (Frame)" if slot_idx % 24 == 0 else f"S{slot_idx % 24} (UL/DL)"
                    label_col = '#f59e0b'
                else:
                    pen = pg.mkPen(color='#38bdf8', width=1.2, style=Qt.PenStyle.DashLine)
                    label_txt = f"S{slot_idx % 24}" if is_dect else f"S{slot_idx}"
                    label_col = '#38bdf8'
                    
                gl = pg.InfiniteLine(
                    pos=cur_t,
                    angle=90,
                    movable=False,
                    pen=pen,
                    label=label_txt,
                    labelOpts={'position': 0.94, 'color': label_col, 'fill': (13, 17, 23, 180), 'movable': False}
                )
                self.plot_item.addItem(gl)
                self.tdma_grid_lines.append(gl)
            cur_t += interval_ns
            slot_idx += 1
            
        # 2. Backward from anchor if anchor > 0
        if anchor_ns > 0:
            cur_t = anchor_ns - interval_ns
            slot_idx = -1
            while cur_t >= 0:
                pen = pg.mkPen(color='#38bdf8', width=1.2, style=Qt.PenStyle.DashLine)
                label_txt = f"S{slot_idx}"
                gl = pg.InfiniteLine(
                    pos=cur_t,
                    angle=90,
                    movable=False,
                    pen=pen,
                    label=label_txt,
                    labelOpts={'position': 0.94, 'color': '#38bdf8', 'fill': (13, 17, 23, 180), 'movable': False}
                )
                self.plot_item.addItem(gl)
                self.tdma_grid_lines.append(gl)
                cur_t -= interval_ns
                slot_idx -= 1

    def update_det_data(self, time_ns: np.ndarray, power_dbm: np.ndarray, info: dict):
        if len(time_ns) == 0 or len(power_dbm) == 0:
            return
            
        self.current_time_ns = time_ns
        self.current_power_dbm = power_dbm
        ref_lvl = info.get("ref_level", 0.0)
        self.ref_level = ref_lvl
        
        # Update Axis only when bounds change to avoid per-frame layout recalculations
        max_t = time_ns[-1]
        if abs(max_t - getattr(self, '_last_axis_max_t', 0.0)) > 1.0:
            self.plot_item.setXRange(0, max_t, padding=0.01)
            self._last_axis_max_t = max_t
        if abs(ref_lvl - getattr(self, '_last_axis_ref_lvl', 999.0)) > 0.5:
            self.plot_item.setYRange(self.bottom_level, ref_lvl + 5.0, padding=0)
            self._last_axis_ref_lvl = ref_lvl
        
        # Update curve
        self.power_curve.setData(time_ns, power_dbm)
        
        # Compute burst metrics
        peak_pwr = np.max(power_dbm)
        avg_pwr = 10.0 * np.log10(np.mean(10.0 ** (power_dbm / 10.0)) + 1e-15)
        
        # Active burst threshold: Peak - 10 dB
        active_thresh = max(self.bottom_level + 10.0, peak_pwr - 10.0)
        active_mask = power_dbm > active_thresh
        active_pts = np.count_nonzero(active_mask)
        duty_pct = (active_pts / max(1, len(power_dbm))) * 100.0
        
        sample_interval_ns = info.get("sample_interval_ns", 16.0)
        burst_duration_us = (active_pts * sample_interval_ns) / 1000.0
        
        # Format Telemetry HUD
        self.telemetry_hud.setText(f"PEAK: {peak_pwr:05.1f} dBm | AVG: {avg_pwr:05.1f} dBm | BURST: {burst_duration_us:05.1f} us | DUTY: {duty_pct:04.1f}%")
        
        # Refresh TDMA grid only if enabled and window max time changed
        if self.grid_enable_check.isChecked():
            if abs(max_t - getattr(self, '_last_max_time_ns', 0.0)) > 1.0:
                self._update_tdma_grid()

    def set_tdma_grid_standard(self, standard_keyword: str):
        """Programmatically switch TDMA Grid standard and activate grid."""
        for idx in range(self.grid_combo.count()):
            if standard_keyword.lower() in self.grid_combo.itemText(idx).lower():
                self.grid_combo.setCurrentIndex(idx)
                self.grid_enable_check.setChecked(True)
                break

    def _on_cursor_moved(self):
        t1 = self.cursor_t1.value()
        t2 = self.cursor_t2.value()
        dt_ns = abs(t2 - t1)
        
        if dt_ns > 0:
            dt_us = dt_ns / 1000.0
            freq_hz = 1e9 / dt_ns
            if freq_hz >= 1e6:
                f_str = f"{freq_hz/1e6:.3f} MHz"
            elif freq_hz >= 1e3:
                f_str = f"{freq_hz/1e3:.2f} kHz"
            else:
                f_str = f"{freq_hz:.1f} Hz"
            self.cursor_t1.label.setText(f"T1: {t1/1000.0:.1f} us (dT: {dt_us:.1f} us | 1/dT: {f_str})")
            self.cursor_t1.label.setText(f"T1: {t1/1000.0:.1f} us")
        self.cursor_t2.label.setText(f"T2: {t2/1000.0:.1f} us")
        
        if self.grid_enable_check.isChecked() and self.align_t1_check.isChecked():
            self._update_tdma_grid()

    def _on_mouse_moved(self, pos):
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_pt = self.plot_item.getViewBox().mapSceneToView(pos)
            t_ns = mouse_pt.x()
            p_dbm = mouse_pt.y()
            
            if self.current_time_ns is not None and 0 <= t_ns <= self.current_time_ns[-1] and self.bottom_level <= p_dbm <= self.ref_level + 5.0:
                self.v_line.setPos(t_ns)
                self.h_line.setPos(p_dbm)
                self.v_line.show()
                self.h_line.show()
                return
        self.v_line.hide()
        self.h_line.hide()
