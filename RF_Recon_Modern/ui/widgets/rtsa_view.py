"""
rtsa_view.py - Real-Time Spectrum Analysis (RTSA) Viewport.
Features a 2D Persistence Density Heatmap (DPX) with adjustable color palettes,
persistence decay time, and real-time instantaneous/max/min hold curve overlays.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QFont, QFontMetrics
from .channel_marker_bar import MHzAxisItem, ChannelMarkerBar

class PowerAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{v:.0f}" for v in values]

COLOR_PALETTES = {
    "Viridis": [
        (0.0, (68, 1, 84, 0)),
        (0.1, (72, 40, 120, 160)),
        (0.3, (49, 104, 142, 220)),
        (0.6, (53, 183, 121, 255)),
        (0.85, (253, 231, 37, 255)),
        (1.0, (255, 255, 255, 255))
    ],
    "Inferno": [
        (0.0, (0, 0, 4, 0)),
        (0.15, (40, 11, 84, 160)),
        (0.4, (101, 21, 110, 220)),
        (0.7, (221, 73, 24, 255)),
        (0.9, (252, 165, 10, 255)),
        (1.0, (252, 255, 164, 255))
    ],
    "Turbo": [
        (0.0, (48, 18, 59, 0)),
        (0.2, (70, 134, 251, 180)),
        (0.4, (27, 229, 181, 220)),
        (0.7, (251, 185, 56, 255)),
        (0.9, (220, 52, 19, 255)),
        (1.0, (122, 4, 3, 255))
    ],
    "Electric Cyan": [
        (0.0, (13, 17, 23, 0)),
        (0.15, (14, 52, 90, 160)),
        (0.45, (2, 132, 199, 220)),
        (0.75, (56, 189, 248, 255)),
        (1.0, (240, 249, 255, 255))
    ]
}

def get_lookup_table(palette_name: str, n_pts: int = 256) -> np.ndarray:
    stops = COLOR_PALETTES.get(palette_name, COLOR_PALETTES["Viridis"])
    pos = [s[0] for s in stops]
    colors = [s[1] for s in stops]
    
    cm = pg.ColorMap(pos, colors)
    return cm.getLookupTable(0.0, 1.0, n_pts, alpha=True)


class RTSAView(QWidget):
    """
    2D Persistence Density Heatmap and Real-Time Spectrum Analysis Viewport.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rtsaView")
        
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
        
        mode_tag = QLabel("RTSA DENSITY PERSISTENCE (100% POI)")
        mode_tag.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;")
        hud_layout.addWidget(mode_tag)
        
        hud_layout.addStretch()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Viridis", "Inferno", "Turbo", "Electric Cyan"])
        self.theme_combo.setFixedHeight(20)
        self.theme_combo.setStyleSheet("""
            QComboBox {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 3px;
                color: #c9d1d9;
                font-size: 10px;
                font-weight: 600;
                padding: 1px 6px;
            }
        """)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        hud_layout.addWidget(QLabel("Theme:"))
        hud_layout.addWidget(self.theme_combo)
        
        self.cursor_hud = QLabel("FREQ: ---.--- MHz | PWR: ---.- dBm | HITS: --%")
        self.cursor_hud.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600; color: #c9d1d9; background-color: #0d1117; padding: 2px 6px; border-radius: 3px; border: 1px solid #30363d;")
        hud_layout.addWidget(self.cursor_hud)
        
        layout.addWidget(hud_bar)
        
        # Plot Graphics Layout
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground('#0d1117')
        layout.addWidget(self.glw)
        
        self.x_axis = MHzAxisItem(orientation='bottom')
        self.y_axis = PowerAxisItem(orientation='left')
        
        self.plot_item = self.glw.addPlot(axisItems={'bottom': self.x_axis, 'left': self.y_axis})
        self.plot_item.showGrid(x=True, y=True, alpha=0.15)
        self.plot_item.setMenuEnabled(False)
        self.plot_item.setMouseEnabled(x=True, y=False)
        # Fixed Axis Widths for Pixel-Perfect Multi-Plot Alignment
        self.plot_item.getAxis('left').setWidth(58)
        self.plot_item.showAxis('right')
        r_axis = self.plot_item.getAxis('right')
        r_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        r_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        r_axis.setWidth(15)

        # Channel Marker Bar Under RTSA View
        self.channel_bar = ChannelMarkerBar()
        self.channel_bar.getAxis('left').setWidth(58)
        self.channel_bar.showAxis('right')
        cb_r_axis = self.channel_bar.getAxis('right')
        cb_r_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        cb_r_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        cb_r_axis.setWidth(15)
        self.channel_bar.setXLink(self.plot_item)
        layout.addWidget(self.channel_bar)
        
        # Bottom Frequency Label
        self.freq_axis_label = QLabel("Frequency (MHz)")
        self.freq_axis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_axis_label.setStyleSheet("color: #6e7681; font-weight: 600; font-size: 10px; margin-top: 2px;")
        layout.addWidget(self.freq_axis_label)
        
        self.ref_level = 0.0
        self.bottom_level = -120.0
        self.plot_item.setYRange(self.bottom_level, self.ref_level + 5.0, padding=0)
        
        # 1. 2D Density Image Item
        self.img_item = pg.ImageItem()
        self.img_item.setZValue(-10)
        self.img_item.setOpacity(0.92)
        self.plot_item.addItem(self.img_item)
        
        # Set initial LUT
        self.current_lut = get_lookup_table("Viridis")
        self.img_item.setLookupTable(self.current_lut)
        
        # 2. Trace Overlays
        self.rt_curve = self.plot_item.plot(pen=pg.mkPen(color='#facc15', width=1.5), name="Real-Time")
        self.max_curve = self.plot_item.plot(pen=pg.mkPen(color='#38bdf8', width=1.2), name="Max Hold")
        self.min_curve = self.plot_item.plot(pen=pg.mkPen(color='#e879f9', width=1.0), name="Min Hold")
        self.max_curve.hide()
        self.min_curve.hide()
        
        # Crosshair lines
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color='#38bdf8', width=1, style=Qt.PenStyle.DashLine))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(color='#38bdf8', width=1, style=Qt.PenStyle.DashLine))
        self.v_line.hide()
        self.h_line.hide()
        self.plot_item.addItem(self.v_line)
        self.plot_item.addItem(self.h_line)
        
        self.plot_item.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # 6 MHz Channel Exclusion Masks & Station Badges
        self.channel_masks = {}
        self.channel_text_items = {}
        self.channel_text_meta = {}
        self._channel_names = {}
        self._last_active_dict = {}
        self._last_standard = None
        self._last_ps_dict = {}

        # Signals
        self.plot_item.getViewBox().sigRangeChanged.connect(self._on_plot_range_changed)
        self.plot_item.getViewBox().sigXRangeChanged.connect(self.channel_bar.update_visibility)
        
        # Internal State
        self.accumulated_density = None
        self.decay_factor = 0.90 # Persistence decay
        self.current_freqs = None
        self.start_freq_hz = 470e6
        self.stop_freq_hz = 608e6

    def _on_theme_changed(self, theme_name: str):
        self.current_lut = get_lookup_table(theme_name)
        self.img_item.setLookupTable(self.current_lut)

    def set_persistence_decay(self, decay: float):
        self.decay_factor = max(0.5, min(0.99, float(decay)))

    def update_rta_data(self, freq_hz: np.ndarray, power_trace: np.ndarray, bitmap_2d: np.ndarray, info: dict):
        if len(freq_hz) == 0:
            return
            
        self.current_freqs = freq_hz
        start_f = info.get("start_freq", freq_hz[0])
        stop_f = info.get("stop_freq", freq_hz[-1])
        ref_lvl = info.get("ref_level", 0.0)
        
        self.start_freq_hz = start_f
        self.stop_freq_hz = stop_f
        self.ref_level = ref_lvl
        
        # Update Axis ranges
        self.plot_item.setXRange(start_f / 1e6, stop_f / 1e6, padding=0)
        self.plot_item.setYRange(self.bottom_level, ref_lvl + 5.0, padding=0)
        
        # Update instantaneous trace
        self.rt_curve.setData(freq_hz / 1e6, power_trace)
        
        # Update 2D Persistence Heatmap Matrix
        h, w = bitmap_2d.shape
        raw_norm = bitmap_2d.astype(np.float32)
        max_hit = np.max(raw_norm)
        if max_hit > 0:
            raw_norm = raw_norm / max_hit
            
        if self.accumulated_density is None or self.accumulated_density.shape != (h, w):
            self.accumulated_density = raw_norm
        else:
            self.accumulated_density = self.accumulated_density * self.decay_factor + raw_norm * (1.0 - self.decay_factor)
            
        # Display image mapped to exact frequency (X) and Power dBm (Y) bounds
        # Transpose to align with (X=Frequency, Y=Power) in PyQtGraph
        disp_matrix = np.transpose(np.clip(self.accumulated_density * 255.0, 0, 255).astype(np.uint8))
        
        x_min = start_f / 1e6
        x_scale = (stop_f - start_f) / (1e6 * max(1, w))
        y_min = self.bottom_level
        y_scale = (ref_lvl - self.bottom_level) / max(1, h)
        
        self.img_item.setImage(disp_matrix, levels=[0, 255], autoLevels=False)
        self.img_item.setRect(pg.QtCore.QRectF(x_min, y_min, (stop_f - start_f)/1e6, ref_lvl - y_min))

    def _on_mouse_moved(self, pos):
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_pt = self.plot_item.getViewBox().mapSceneToView(pos)
            f_mhz = mouse_pt.x()
            p_dbm = mouse_pt.y()
            
            if self.start_freq_hz / 1e6 <= f_mhz <= self.stop_freq_hz / 1e6 and self.bottom_level <= p_dbm <= self.ref_level + 5.0:
                self.v_line.setPos(f_mhz)
                self.h_line.setPos(p_dbm)
                self.v_line.show()
                self.h_line.show()
                self.cursor_hud.setText(f"FREQ: {f_mhz:07.3f} MHz | PWR: {p_dbm:05.1f} dBm")
                return
        self.v_line.hide()
        self.h_line.hide()

    def _on_plot_range_changed(self, vb, r):
        self._update_text_items()

    def _calc_text_y_pos(self):
        try:
            vb = self.plot_item.getViewBox()
            y_range = vb.viewRange()[1]
            y_min, y_max = y_range[0], y_range[1]
            if y_min < 0.0 < y_max:
                return 0.0
            elif y_max <= 0.0:
                return y_max - (y_max - y_min) * 0.12
            else:
                return y_max - 10.0
        except Exception:
            return 0.0

    def _fit_channel_text(self, mask_w_px, ch_label, f_start, f_stop, hdr_color, call_sign):
        if mask_w_px < 22:
            return ""
            
        line1 = f"DTV {ch_label}"
        if mask_w_px >= 85:
            line2 = f"{f_start:g} - {f_stop:g} MHz"
        elif mask_w_px >= 55:
            line2 = f"{f_start:g}-{f_stop:g} MHz"
        else:
            line2 = f"{int(f_start)}-{int(f_stop)}"
            
        display_call = None
        if call_sign:
            cs = str(call_sign).strip()
            if cs.startswith("LMR"):
                display_call = "LMR"
            elif len(cs) > 7:
                display_call = cs[:7]
            else:
                display_call = cs

        lines = [line1, line2]
        if display_call:
            lines.append(display_call)
            
        avail_w = max(mask_w_px - 4, 10)
        best_pt = 10.0
        f = QFont('sans-serif')
        f.setBold(True)
        while best_pt >= 5.5:
            f.setPointSizeF(best_pt)
            fm = QFontMetrics(f)
            max_line_w = max(fm.horizontalAdvance(l) for l in lines)
            if max_line_w <= avail_w:
                break
            best_pt -= 0.5
            
        pt_h1 = f"{best_pt:.1f}pt"
        pt_h2 = f"{max(best_pt - 1.0, 5.0):.1f}pt"
        pt_h3 = f"{best_pt:.1f}pt"
        
        html = (
            f"<div style='text-align: center; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; line-height: 1.15;'>"
            f"<div style='color: {hdr_color}; font-weight: bold; font-size: {pt_h1};'>{line1}</div>"
            f"<div style='color: #cbd5e1; font-size: {pt_h2}; font-weight: normal;'>{line2}</div>"
        )
        if display_call:
            html += f"<div style='color: #facc15; font-weight: bold; font-size: {pt_h3};'>{display_call}</div>"
        html += "</div>"
        return html

    def _update_text_items(self):
        vb = self.plot_item.getViewBox()
        if vb is None:
            return
        y_pos = self._calc_text_y_pos()
        for ch_id, t_item in self.channel_text_items.items():
            if ch_id not in self.channel_text_meta:
                continue
            meta = self.channel_text_meta[ch_id]
            f_start, f_stop, ch_label, hdr_color, call_sign, is_active = meta
            if not is_active:
                t_item.setVisible(False)
                continue
            p1 = vb.mapViewToDevice(QPointF(f_start, 0.0))
            p2 = vb.mapViewToDevice(QPointF(f_stop, 0.0))
            mask_w = abs(p2.x() - p1.x())
            if mask_w < 22:
                t_item.setVisible(False)
                continue
            html = self._fit_channel_text(mask_w, ch_label, f_start, f_stop, hdr_color, call_sign)
            t_item.setHtml(html)
            t_item.setPos((f_start + f_stop) / 2.0, y_pos)
            t_item.setVisible(True)

    def set_active_channels(self, active_dict: dict, ps_dict: dict = None):
        if hasattr(self, 'channel_bar'):
            self.channel_bar.set_active_channels(active_dict, ps_dict)

    def update_channel_masks(self, active_dict: dict, standards: list, public_safety_dict: dict, channel_names: dict = None):
        self._last_active_dict = dict(active_dict)
        self._last_standard = standards
        self._last_ps_dict = dict(public_safety_dict) if public_safety_dict else {}
        if channel_names is not None:
            self._channel_names = channel_names
        else:
            channel_names = getattr(self, '_channel_names', {})
            
        all_channels = {}
        for band in standards:
            if "custom_items" in band:
                for item in band["custom_items"]:
                    all_channels[item["id"]] = (item["start"], item["stop"], item.get("label", str(item["id"])), item.get("type", "normal"))
            elif "start_ch" in band and "end_ch" in band:
                for ch in range(band["start_ch"], band["end_ch"] + 1):
                    f_start = band["start_freq"] + (ch - band["start_ch"]) * band["spacing"]
                    f_stop = f_start + band["spacing"]
                    all_channels[ch] = (f_start, f_stop, str(ch), "normal")

        y_pos = self._calc_text_y_pos()

        for ch_id, (f_start, f_stop, ch_label, c_type) in all_channels.items():
            is_active = active_dict.get(ch_id, False)
            if is_active:
                is_ps = public_safety_dict.get(ch_id, False)
                if is_ps:
                    brush = pg.mkBrush(239, 68, 68, 40)
                    pen = pg.mkPen('#ef4444', width=1, style=Qt.PenStyle.DashLine)
                    border_color = '#ef4444'
                    hdr_color = '#f87171'
                elif c_type == "ch37" or ch_id == 37 or str(ch_id).strip() == "37":
                    brush = pg.mkBrush(100, 116, 139, 50)
                    pen = pg.mkPen('#94a3b8', width=1.5, style=Qt.PenStyle.DashLine)
                    border_color = '#94a3b8'
                    hdr_color = '#94a3b8'
                elif c_type == "uplink":
                    brush = pg.mkBrush(16, 185, 129, 40)
                    pen = pg.mkPen('#10b981', width=1, style=Qt.PenStyle.DashLine)
                    border_color = '#10b981'
                    hdr_color = '#34d399'
                elif c_type == "downlink":
                    brush = pg.mkBrush(139, 92, 246, 40)
                    pen = pg.mkPen('#8b5cf6', width=1, style=Qt.PenStyle.DashLine)
                    border_color = '#8b5cf6'
                    hdr_color = '#a78bfa'
                elif c_type == "guard":
                    brush = pg.mkBrush(100, 116, 139, 40)
                    pen = pg.mkPen('#64748b', width=1, style=Qt.PenStyle.DashLine)
                    border_color = '#64748b'
                    hdr_color = '#94a3b8'
                else:
                    brush = pg.mkBrush(6, 182, 212, 35)
                    pen = pg.mkPen('#06b6d4', width=1, style=Qt.PenStyle.DashLine)
                    border_color = '#06b6d4'
                    hdr_color = '#38bdf8'

                if ch_id not in self.channel_masks:
                    region = pg.LinearRegionItem(
                        values=[f_start, f_stop],
                        orientation='vertical',
                        movable=False,
                        brush=brush,
                        pen=pen
                    )
                    region.setZValue(5)
                    region.setAcceptHoverEvents(False)
                    region.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                    self.plot_item.addItem(region)
                    self.channel_masks[ch_id] = region
                else:
                    self.channel_masks[ch_id].setRegion([f_start, f_stop])
                    self.channel_masks[ch_id].setBrush(brush)
                    for line in self.channel_masks[ch_id].lines:
                        line.setPen(pen)
                    self.channel_masks[ch_id].setVisible(True)

                x_center = (f_start + f_stop) / 2.0
                if isinstance(ch_id, int) or str(ch_id).isdigit():
                    ch_title = f"{ch_id}"
                else:
                    ch_title = f"{ch_label}"

                call_sign = channel_names.get(ch_id) or channel_names.get(str(ch_id))
                self.channel_text_meta[ch_id] = (f_start, f_stop, ch_title, hdr_color, call_sign, True)

                vb = self.plot_item.getViewBox()
                p1 = vb.mapViewToDevice(QPointF(f_start, 0.0))
                p2 = vb.mapViewToDevice(QPointF(f_stop, 0.0))
                mask_w = abs(p2.x() - p1.x())

                html_text = self._fit_channel_text(mask_w, ch_title, f_start, f_stop, hdr_color, call_sign)

                if ch_id not in self.channel_text_items:
                    t_item = pg.TextItem(
                        anchor=(0.5, 0.0),
                        fill=None,
                        border=None
                    )
                    t_item.setHtml(html_text)
                    t_item.setPos(x_center, y_pos)
                    t_item.setZValue(15)
                    self.plot_item.addItem(t_item)
                    self.channel_text_items[ch_id] = t_item
                else:
                    t_item = self.channel_text_items[ch_id]
                    t_item.setHtml(html_text)
                    t_item.setPos(x_center, y_pos)
                    t_item.setVisible(True if mask_w >= 22 else False)
            else:
                if ch_id in self.channel_text_meta:
                    f_s, f_e, lbl, clr, cs, _ = self.channel_text_meta[ch_id]
                    self.channel_text_meta[ch_id] = (f_s, f_e, lbl, clr, cs, False)
                if ch_id in self.channel_masks:
                    self.channel_masks[ch_id].setVisible(False)
                if ch_id in self.channel_text_items:
                    self.channel_text_items[ch_id].setVisible(False)

    def clear_channel_masks(self):
        for region in self.channel_masks.values():
            self.plot_item.removeItem(region)
        self.channel_masks.clear()
        for t_item in self.channel_text_items.values():
            self.plot_item.removeItem(t_item)
        self.channel_text_items.clear()
        self.channel_text_meta.clear()

    def update_channel_names(self, channel_names: dict):
        self._channel_names = channel_names or {}
        if hasattr(self, '_last_active_dict') and hasattr(self, '_last_standard') and self._last_standard:
            self.update_channel_masks(
                self._last_active_dict,
                self._last_standard,
                getattr(self, '_last_ps_dict', {}),
                self._channel_names
            )
