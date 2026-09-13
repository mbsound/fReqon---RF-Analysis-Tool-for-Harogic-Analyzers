"""
multi_row_waterfall.py - Aaronia RTSA-Inspired Multi-Row Folded Waterfall Viewport.
Folds broad swept spans into N contiguous horizontal spectrogram rows (2, 4, 6, 8 rows),
multiplying horizontal pixel density by 2x-8x for high-resolution narrowband RF surveillance.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFrame, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QFont
from .channel_marker_bar import MHzAxisItem, ChannelMarkerBar
from core.constants import COLORMAP_CSS, WATERFALL_COLORMAPS

class WaterfallRowStrip(QWidget):
    """
    Individual spectrogram strip representing a contiguous sub-band slice.
    """
    mouseMoved = pyqtSignal(int, float, float) # row_idx, freq_mhz, time_val
    tuneRequested = pyqtSignal(float) # freq_mhz

    def __init__(self, row_idx: int, parent=None):
        super().__init__(parent)
        self.row_idx = row_idx
        self.f_start = 0.0
        self.f_stop = 0.0
        self.history_depth = 100
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        
        # Strip Header
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border-top: 1px solid #30363d;
                border-left: 1px solid #30363d;
                border-right: 1px solid #30363d;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 1px 6px;
            }
        """)
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(4, 1, 4, 1)
        h_layout.setSpacing(8)
        
        self.row_badge = QLabel(f"ROW {self.row_idx + 1}")
        self.row_badge.setStyleSheet("""
            background-color: #21262d;
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 3px;
        """)
        h_layout.addWidget(self.row_badge)
        
        self.span_label = QLabel("--.--- — --.--- MHz (Span: --.- MHz)")
        self.span_label.setStyleSheet("color: #f0f6fc; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;")
        h_layout.addWidget(self.span_label)
        h_layout.addStretch()
        
        self.row_hint_lbl = QLabel("Double-click to Tune")
        self.row_hint_lbl.setStyleSheet("color: #6e7681; font-size: 10px; font-weight: 500;")
        h_layout.addWidget(self.row_hint_lbl)
        
        layout.addWidget(self.header_frame)
        
        # Spectrogram Plot Widget
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': MHzAxisItem(orientation='bottom')})
        self.plot_widget.setBackground('#0d1117')
        self.plot_widget.setLabel('left', 'Sweeps', units='')
        self.plot_widget.showGrid(x=True, y=False, alpha=0.15)
        self.plot_widget.hideButtons()
        self.plot_widget.getViewBox().setMouseEnabled(x=False, y=False)
        self.plot_widget.getViewBox().disableAutoRange()
        
        # Fixed Axis Widths for Alignment
        self.plot_widget.getAxis('left').setWidth(48)
        self.plot_widget.showAxis('right')
        r_axis = self.plot_widget.getAxis('right')
        r_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        r_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        r_axis.setWidth(15)
        
        # Image Item
        self.img_item = pg.ImageItem(autoDownsample=True)
        self.plot_widget.addItem(self.img_item)
        
        # Crosshair Vertical Line
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#38bdf8', width=1, style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        
        # 6 MHz Channel Masks overlay
        self.channel_masks = {}
        
        layout.addWidget(self.plot_widget, 1)
        
        # Channel Marker Bar Under Strip
        self.channel_bar = ChannelMarkerBar()
        self.channel_bar.getAxis('left').setWidth(48)
        self.channel_bar.showAxis('right')
        cb_r = self.channel_bar.getAxis('right')
        cb_r.setPen(pg.mkPen(color=(0,0,0,0)))
        cb_r.setTextPen(pg.mkPen(color=(0,0,0,0)))
        cb_r.setWidth(15)
        self.channel_bar.setXLink(self.plot_widget)
        self.channel_bar.setFixedHeight(20)
        layout.addWidget(self.channel_bar)
        
        # Mouse Move Proxy
        self.mouse_proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved)
        self.plot_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_pt = self.plot_widget.getViewBox().mapSceneToView(pos)
            self.v_line.setPos(mouse_pt.x())
            self.mouseMoved.emit(self.row_idx, mouse_pt.x(), mouse_pt.y())

    def _on_mouse_clicked(self, evt):
        if evt.double():
            pos = evt.scenePos()
            if self.plot_widget.sceneBoundingRect().contains(pos):
                mouse_pt = self.plot_widget.getViewBox().mapSceneToView(pos)
                self.tuneRequested.emit(mouse_pt.x())
                evt.accept()

    def set_colormap(self, cmap):
        self.img_item.setColorMap(cmap)

    def set_history_depth(self, depth: int):
        self.history_depth = max(10, int(depth))
        self.plot_widget.setYRange(0, self.history_depth, padding=0)

    def set_frequency_range(self, f_start: float, f_stop: float):
        self.f_start = f_start
        self.f_stop = f_stop
        span = f_stop - f_start
        self.span_label.setText(f"{f_start:.3f} — {f_stop:.3f} MHz (Span: {span:.3f} MHz)")
        self.plot_widget.setXRange(f_start, f_stop, padding=0)
        self.channel_bar.setXRange(f_start, f_stop, padding=0)
        if self.img_item.image is not None:
            self.img_item.setRect((f_start, 0, span, self.history_depth))

    def update_strip(self, img_data: np.ndarray, f_start: float, f_stop: float):
        span = f_stop - f_start
        if self.f_start != f_start or self.f_stop != f_stop:
            self.f_start = f_start
            self.f_stop = f_stop
            self.span_label.setText(f"{f_start:.3f} — {f_stop:.3f} MHz (Span: {span:.3f} MHz)")
            self.img_item.setRect((f_start, 0, span, self.history_depth))
            self.plot_widget.setXRange(f_start, f_stop, padding=0)
            self.channel_bar.setXRange(f_start, f_stop, padding=0)
            
        self.img_item.setImage(img_data, levels=[-120.0, -20.0], autoLevels=False)

    def update_channel_masks(self, active_dict: dict, standard, ps_dict: dict = None):
        """
        Updates 6 MHz channel exclusion masks across this row's spectrogram viewport.
        """
        if ps_dict is None:
            ps_dict = {}
        if not standard:
            return
        if isinstance(standard, dict):
            standard = [standard]

        all_channels = []
        for band in standard:
            if "custom_items" in band:
                for c_item in band["custom_items"]:
                    c_id = c_item["id"]
                    start_f = c_item["start"]
                    stop_f = c_item["stop"]
                    all_channels.append((c_id, start_f, stop_f, c_item.get("type", "default")))
            elif "start_ch" in band:
                s_ch = band["start_ch"]
                e_ch = band["end_ch"]
                s_f = band["start_freq"]
                sp = band["spacing"]
                for ch in range(s_ch, e_ch + 1):
                    ch_idx = ch - s_ch
                    f1 = s_f + (ch_idx * sp)
                    f2 = f1 + sp
                    all_channels.append((ch, f1, f2, "dtv"))

        for ch_id, f_start, f_stop, ch_type in all_channels:
            is_active = active_dict.get(ch_id, False)
            is_ps = ps_dict.get(ch_id, False)

            # Check if this channel intersects this row's frequency range
            if self.f_stop > self.f_start:
                if f_stop < self.f_start or f_start > self.f_stop:
                    if ch_id in self.channel_masks:
                        self.channel_masks[ch_id].setVisible(False)
                    continue

            if is_ps:
                brush = pg.mkBrush(QColor(239, 68, 68, 40))
                pen = pg.mkPen(QColor(248, 113, 113, 120), width=1, style=Qt.PenStyle.DashLine)
            elif ch_type == "uplink":
                brush = pg.mkBrush(QColor(236, 72, 153, 35))
                pen = pg.mkPen(QColor(244, 114, 182, 110), width=1, style=Qt.PenStyle.DashLine)
            elif ch_type == "downlink":
                brush = pg.mkBrush(QColor(168, 85, 247, 35))
                pen = pg.mkPen(QColor(192, 132, 252, 110), width=1, style=Qt.PenStyle.DashLine)
            elif ch_type == "guard":
                brush = pg.mkBrush(QColor(100, 116, 139, 30))
                pen = pg.mkPen(QColor(148, 163, 184, 90), width=1, style=Qt.PenStyle.DashLine)
            else:
                brush = pg.mkBrush(QColor(6, 182, 212, 35))
                pen = pg.mkPen(QColor(6, 182, 212, 110), width=1, style=Qt.PenStyle.DashLine)

            if is_active:
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
                    self.plot_widget.addItem(region)
                    self.channel_masks[ch_id] = region
                else:
                    self.channel_masks[ch_id].setRegion([f_start, f_stop])
                    self.channel_masks[ch_id].setBrush(brush)
                    for line in self.channel_masks[ch_id].lines:
                        line.setPen(pen)
                    self.channel_masks[ch_id].setVisible(True)
            else:
                if ch_id in self.channel_masks:
                    self.channel_masks[ch_id].setVisible(False)

    def clear_channel_masks(self):
        for region in self.channel_masks.values():
            try:
                self.plot_widget.removeItem(region)
            except Exception:
                pass
        self.channel_masks.clear()


class MultiRowWaterfallView(QWidget):
    """
    Multi-Row Folded Spectrogram Viewport.
    Divides any wideband sweep into 2, 4, 6, or 8 vertically stacked sub-band waterfall strips.
    """
    colormapChanged = pyqtSignal(str)
    rowModeChanged = pyqtSignal(int)
    tuneFrequencyRequested = pyqtSignal(float)
    channel_clicked = pyqtSignal(object, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.num_rows = 4
        self.history_depth = 100
        self.current_colormap = "viridis"
        self.strips = []
        self._current_standard = None
        self._x_multiplier = 1e6
        self._active_channels = {}
        self._ps_dict = {}
        self._last_master_buffer = None
        self._last_f_start_mhz = 0.0
        self._last_f_stop_mhz = 0.0
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        
        # --- Top Header & Controls ---
        header = QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 2)
        
        title_lbl = QLabel("MULTI-ROW FOLDED SPECTROGRAM (RTSA MODE)")
        title_lbl.setStyleSheet("font-weight: 700; font-size: 11px; color: #38bdf8; letter-spacing: 0.5px;")
        header.addWidget(title_lbl)
        
        header.addStretch()
        
        # Telemetry HUD
        self.hud_label = QLabel("ROW: -- | FREQ: --.--- MHz | TIME: --.-s")
        self.hud_label.setStyleSheet("""
            background-color: #161b22;
            color: #38bdf8;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 2px 8px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 11px;
        """)
        header.addWidget(self.hud_label)
        
        # Row Selector
        row_lbl = QLabel("Layout:")
        row_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        header.addWidget(row_lbl)
        
        self.row_combo = QComboBox()
        self.row_combo.addItems(["2 Rows (2x Res)", "4 Rows (4x Res)", "6 Rows (6x Res)", "8 Rows (8x Res)"])
        self.row_combo.setCurrentIndex(1) # Default 4 Rows
        self.row_combo.currentIndexChanged.connect(self._on_row_combo_changed)
        header.addWidget(self.row_combo)
        
        # Colormap Selector
        cmap_lbl = QLabel("Theme:")
        cmap_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        header.addWidget(cmap_lbl)
        
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems([c.capitalize() for c in WATERFALL_COLORMAPS])
        self.cmap_combo.setMaximumWidth(90)
        self.cmap_combo.currentTextChanged.connect(self._on_cmap_changed)
        header.addWidget(self.cmap_combo)
        
        # Gradient Legend Bar
        self.color_scale_label = QLabel("-120 dBm       -70 dBm       -20 dBm")
        self.color_scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.color_scale_label.setFixedSize(220, 18)
        header.addWidget(self.color_scale_label)
        
        main_layout.addLayout(header)
        
        # Scroll Area for Strip Rows
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        self.strip_container = QWidget()
        self.strip_layout = QVBoxLayout(self.strip_container)
        self.strip_layout.setContentsMargins(0, 0, 0, 0)
        self.strip_layout.setSpacing(6)
        self.scroll.setWidget(self.strip_container)
        
        main_layout.addWidget(self.scroll, 1)
        
        self.update_color_scale_css()
        self._rebuild_rows()

    def _on_row_combo_changed(self, idx: int):
        rows_map = {0: 2, 1: 4, 2: 6, 3: 8}
        self.num_rows = rows_map.get(idx, 4)
        self._rebuild_rows()
        self.rowModeChanged.emit(self.num_rows)

    def _on_cmap_changed(self, text: str):
        cmap_name = text.lower()
        self.set_colormap(cmap_name)
        self.colormapChanged.emit(cmap_name)

    def set_colormap(self, cmap_name: str):
        if cmap_name in WATERFALL_COLORMAPS:
            self.current_colormap = cmap_name
            cmap = pg.colormap.get(cmap_name)
            for s in self.strips:
                s.set_colormap(cmap)
            self.update_color_scale_css()
            
            idx = self.cmap_combo.findText(cmap_name.capitalize())
            if idx >= 0 and self.cmap_combo.currentIndex() != idx:
                self.cmap_combo.blockSignals(True)
                self.cmap_combo.setCurrentIndex(idx)
                self.cmap_combo.blockSignals(False)

    def update_color_scale_css(self):
        css_stops = COLORMAP_CSS.get(self.current_colormap, COLORMAP_CSS['viridis'])
        self.color_scale_label.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, {css_stops});
                color: #ffffff;
                font-weight: 700;
                font-family: 'JetBrains Mono', monospace;
                font-size: 9px;
                border: 1px solid #30363d;
                border-radius: 3px;
                padding: 1px 6px;
            }}
        """)

    def set_history_depth(self, depth: int):
        self.history_depth = max(10, int(depth))
        for s in self.strips:
            s.set_history_depth(self.history_depth)

    def set_sweep_range(self, start_mhz: float, stop_mhz: float):
        self._last_f_start_mhz = start_mhz
        self._last_f_stop_mhz = stop_mhz
        self._apply_ranges_to_strips()

    def _apply_ranges_to_strips(self):
        if self._last_f_start_mhz >= self._last_f_stop_mhz or len(self.strips) == 0:
            return
        span = self._last_f_stop_mhz - self._last_f_start_mhz
        span_per_row = span / self.num_rows
        for i, strip in enumerate(self.strips):
            sub_f_start = self._last_f_start_mhz + i * span_per_row
            sub_f_stop = self._last_f_start_mhz + (i + 1) * span_per_row if i < self.num_rows - 1 else self._last_f_stop_mhz
            strip.set_frequency_range(sub_f_start, sub_f_stop)
            if self._current_standard:
                strip.update_channel_masks(self._active_channels, self._current_standard, self._ps_dict)

    def _rebuild_rows(self):
        # Clear existing
        for s in self.strips:
            self.strip_layout.removeWidget(s)
            s.deleteLater()
        self.strips.clear()
        
        cmap = pg.colormap.get(self.current_colormap)
        for i in range(self.num_rows):
            strip = WaterfallRowStrip(i, self.strip_container)
            strip.set_colormap(cmap)
            strip.set_history_depth(self.history_depth)
            strip.mouseMoved.connect(self._on_strip_mouse_moved)
            strip.tuneRequested.connect(self.tuneFrequencyRequested.emit)
            strip.channel_bar.channel_clicked.connect(self.channel_clicked.emit)
            if self._current_standard:
                strip.channel_bar.draw_channels(self._current_standard, self._x_multiplier)
                strip.channel_bar.set_active_channels(self._active_channels, self._ps_dict)
                strip.update_channel_masks(self._active_channels, self._current_standard, self._ps_dict)
            self.strip_layout.addWidget(strip, 1)
            self.strips.append(strip)

        # Re-apply sub-band frequency ranges to newly built strips immediately
        self._apply_ranges_to_strips()

        # If cached sweep buffer is available, slice and draw spectrograms immediately
        if self._last_master_buffer is not None and self._last_f_start_mhz < self._last_f_stop_mhz:
            self._render_master_buffer()

    def _on_strip_mouse_moved(self, row_idx: int, freq_mhz: float, time_val: float):
        # Update crosshairs on the active row and broadcast HUD
        dt_seconds = (self.history_depth - max(0, min(self.history_depth, time_val))) * 0.05
        self.hud_label.setText(f"ROW: {row_idx + 1} | FREQ: {freq_mhz:.4f} MHz | TIME: -{dt_seconds:.1f}s")

    def _render_master_buffer(self):
        if self._last_master_buffer is None or len(self.strips) == 0:
            return
        total_pts = self._last_master_buffer.shape[1]
        if total_pts < self.num_rows:
            return
        pts_per_row = total_pts // self.num_rows
        span = self._last_f_stop_mhz - self._last_f_start_mhz
        span_per_row = span / self.num_rows
        for i, strip in enumerate(self.strips):
            c_start = i * pts_per_row
            c_end = (i + 1) * pts_per_row if i < self.num_rows - 1 else total_pts
            sub_f_start = self._last_f_start_mhz + i * span_per_row
            sub_f_stop = self._last_f_start_mhz + (i + 1) * span_per_row if i < self.num_rows - 1 else self._last_f_stop_mhz
            sub_buf = self._last_master_buffer[:, c_start:c_end]
            strip.update_strip(sub_buf.T, sub_f_start, sub_f_stop)

    def update_sweep_data(self, master_buffer: np.ndarray, f_start_mhz: float, f_stop_mhz: float):
        """
        Slices the master 2D waterfall buffer into N contiguous horizontal strips.
        """
        self._last_master_buffer = master_buffer
        self._last_f_start_mhz = f_start_mhz
        self._last_f_stop_mhz = f_stop_mhz
        self._render_master_buffer()

    def set_channels(self, standard, x_multiplier=1e6, active_channels=None):
        self._current_standard = standard
        self._x_multiplier = x_multiplier
        if active_channels is not None:
            self._active_channels = active_channels
        for s in self.strips:
            s.channel_bar.draw_channels(standard, x_multiplier)
            s.channel_bar.set_active_channels(self._active_channels, self._ps_dict)
            s.update_channel_masks(self._active_channels, standard, self._ps_dict)

    def set_active_channels(self, active_dict, ps_dict=None):
        self._active_channels = active_dict
        if ps_dict is not None:
            self._ps_dict = ps_dict
        for s in self.strips:
            s.channel_bar.set_active_channels(self._active_channels, self._ps_dict)
            if self._current_standard:
                s.update_channel_masks(self._active_channels, self._current_standard, self._ps_dict)

    def update_channel_masks(self, active_dict: dict, standard, ps_dict: dict = None):
        self._active_channels = active_dict
        self._current_standard = standard
        if ps_dict is not None:
            self._ps_dict = ps_dict
        for s in self.strips:
            s.update_channel_masks(self._active_channels, self._current_standard, self._ps_dict)

    def clear_channel_masks(self):
        for s in self.strips:
            s.clear_channel_masks()
