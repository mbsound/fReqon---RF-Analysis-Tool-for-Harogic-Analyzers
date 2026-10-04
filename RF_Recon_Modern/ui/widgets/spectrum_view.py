"""
spectrum_view.py - High-Performance Real-Time Spectrum Analyzer Viewport.
Features multi-trace curves, draggable RF thresholds, crosshair telemetry HUD,
and synchronized channel allocation markers.
"""

import bisect
import html

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu, QToolTip
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QFont, QFontMetrics
from .channel_marker_bar import MHzAxisItem, ChannelMarkerBar
from .plot_grid import install_grid
from .channel_style import channel_kind, mask_brush_pen, channel_label_html

class PowerDbAxisItem(pg.AxisItem):
    """
    Dedicated RF Spectrum Y-Axis Item.
    Maintains exact graticule division ticks aligned to the hardware Reference Level at the top,
    with custom scale per division (e.g., 10 dB/div, 5 dB/div, 2 dB/div, 1 dB/div).
    """
    def __init__(self, orientation='left', ref_level=0.0, scale_div=10.0, num_divisions=10, **kwargs):
        super().__init__(orientation, **kwargs)
        self.ref_level = float(ref_level)
        self.scale_div = float(scale_div)
        self.num_divisions = int(num_divisions)

    def set_params(self, ref_level: float, scale_div: float, num_divisions: int = 10):
        self.ref_level = float(ref_level)
        self.scale_div = float(scale_div)
        self.num_divisions = int(num_divisions)
        self.picture = None
        self.update()

    def tickValues(self, minVal, maxVal, size):
        major = [self.ref_level - i * self.scale_div for i in range(self.num_divisions + 1)]
        minor = []
        if self.scale_div >= 2.0:
            sub = self.scale_div / 2.0
            for m in major[:-1]:
                minor.append(m - sub)
        return [
            (self.scale_div, [t for t in major if (minVal - 0.05) <= t <= (maxVal + 0.05)]),
            (self.scale_div / 2.0, [t for t in minor if (minVal - 0.05) <= t <= (maxVal + 0.05)])
        ]

    def tickStrings(self, values, scale, spacing):
        return [f"{v:.0f}" if abs(v - round(v)) < 0.01 else f"{v:.1f}" for v in values]

class SpectrumView(QWidget):
    """
    Main Spectrum Plot Viewport with real-time trace rendering and interactive HUD.
    """
    rangeChanged = pyqtSignal(object)
    mouseMoved = pyqtSignal(float, float)
    thresholdChanged = pyqtSignal(float)
    intruderThresholdChanged = pyqtSignal(float)
    dectThresholdChanged = pyqtSignal(float)
    showlinkThresholdChanged = pyqtSignal(float)
    triggerZeroSpanRequested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._x_multiplier = 1e6 # MHz base
        self.ref_level = 0.0
        self.scale_div = 10.0
        self.num_divisions = 10
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Header Toolbar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        
        self.title_label = QLabel("REAL-TIME SPECTRUM (SWP MODE)")
        self.title_label.setStyleSheet("font-weight: 700; font-size: 11px; color: #8b949e; letter-spacing: 0.5px;")
        header_layout.addWidget(self.title_label)

        # Scale & Reference Level Badge
        self.scale_badge = QLabel("REF: 0.0 dBm | 10 dB/DIV")
        self.scale_badge.setStyleSheet("""
            background-color: #161b22;
            color: #facc15;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 2px 8px;
            font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
            font-weight: 700;
            font-size: 10px;
        """)
        header_layout.addWidget(self.scale_badge)
        
        header_layout.addStretch()
        
        # Warning Badge (Hidden by default)
        self.span_alert = QLabel("Spectrum View Span exceeds Sweep Span")
        self.span_alert.setStyleSheet("""
            background-color: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
            border: 1px solid #f59e0b;
            border-radius: 4px;
            padding: 2px 8px;
            font-weight: 600;
            font-size: 10px;
        """)
        self.span_alert.hide()
        header_layout.addWidget(self.span_alert)
        
        # Live HUD Telemetry Readout
        self.hud_label = QLabel("FREQ: --.--- MHz | PWR: --.- dBm")
        self.hud_label.setStyleSheet("""
            background-color: #161b22;
            color: #38bdf8;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 2px 8px;
            font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
            font-weight: 600;
            font-size: 11px;
        """)
        header_layout.addWidget(self.hud_label)
        
        layout.addLayout(header_layout)
        
        # Plot Widget with Custom PowerDbAxisItem linked to Ref Level
        self.power_axis = PowerDbAxisItem('left', ref_level=self.ref_level, scale_div=self.scale_div, num_divisions=self.num_divisions)
        self.plot_widget = pg.PlotWidget(axisItems={
            'bottom': MHzAxisItem(orientation='bottom'),
            'left': self.power_axis
        })
        self.plot_widget.setBackground('#0d1117')
        self.plot_widget.setLabel('left', 'Power', units='dBm')
        self.plot_grid = install_grid(self.plot_widget, x=True, y=True, alpha=0.15)
        initial_bottom = self.ref_level - (self.scale_div * self.num_divisions)
        self.plot_widget.setYRange(initial_bottom, self.ref_level, padding=0)
        self.plot_widget.hideButtons()
        self.plot_widget.getViewBox().setMouseEnabled(x=True, y=False)
        self.plot_widget.getViewBox().disableAutoRange()
        self.plot_widget.plotItem.setMenuEnabled(False)
        
        # Fixed Axis Widths for Pixel-Perfect Multi-Plot Alignment
        self.plot_widget.getAxis('left').setWidth(58)
        self.plot_widget.showAxis('right')
        r_axis = self.plot_widget.getAxis('right')
        r_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        r_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        r_axis.setWidth(15)
        
        layout.addWidget(self.plot_widget, 1)
        
        # Channel Marker Bar Under Spectrum
        self.channel_bar = ChannelMarkerBar()
        self.channel_bar.getAxis('left').setWidth(58)
        self.channel_bar.showAxis('right')
        cb_r_axis = self.channel_bar.getAxis('right')
        cb_r_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        cb_r_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        cb_r_axis.setWidth(15)
        self.channel_bar.setXLink(self.plot_widget)
        layout.addWidget(self.channel_bar)
        
        # Bottom Frequency Label
        self.freq_axis_label = QLabel("Frequency (MHz)")
        self.freq_axis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_axis_label.setStyleSheet("color: #6e7681; font-weight: 600; font-size: 10px; margin-top: 2px;")
        layout.addWidget(self.freq_axis_label)
        
        # 6 MHz Channel Exclusion Masks & Station Text Badges
        self.channel_masks = {}
        self.channel_text_items = {}
        self.channel_text_meta = {}
        self._channel_names = {}
        self._last_active_dict = {}
        self._last_standard = None
        self._last_ps_dict = {}
        
        # Soundbase Narrowband Carrier Masks
        self.soundbase_masks = {}
        # Name labels drawn on the carrier masks once zoomed in, and the hover
        # details shown at any zoom
        self._carrier_meta = {}            # carrier id -> name, device, span, colour, visible
        self._carrier_order = []           # (f_start, carrier id), sorted by frequency
        self._carrier_starts = []
        self._carrier_max_bw = 0.0
        self._carrier_labels = {}          # carrier id -> TextItem, created on first show
        self._carrier_label_state = {}     # carrier id -> (upright, html) last applied
        self._carrier_labels_shown = set()
        self._carrier_tip_shown = False
        self._carrier_font = QFont()
        self._carrier_font.setStyleHint(QFont.StyleHint.SansSerif)
        self._carrier_font.setPointSizeF(8.0)
        self._carrier_font.setBold(True)
        self._carrier_fm = QFontMetrics(self._carrier_font)

        # Traces
        # Pen width 1.0: Qt only antialiases a 1 px cosmetic line with its fast
        # stroker; anything wider tessellates each of the 4000 segments and
        # costs more than twice as much per frame
        self.curves = {
            "Real-Time": self.plot_widget.plot(pen=pg.mkPen('#eab308', width=1.0)),
            "Average": self.plot_widget.plot(pen=pg.mkPen('#10b981', width=1.0)),
            "Max. Hold": self.plot_widget.plot(pen=pg.mkPen('#06b6d4', width=1.0)),
            "Min. Hold": self.plot_widget.plot(pen=pg.mkPen('#d946ef', width=1.0)),
            "Trace A": self.plot_widget.plot(pen=pg.mkPen('#38bdf8', width=1.0)),
            "Trace B": self.plot_widget.plot(pen=pg.mkPen('#f97316', width=1.0)),
            "Delta": self.plot_widget.plot(pen=pg.mkPen('#a855f7', width=1.0, style=Qt.PenStyle.DashLine))
        }
        self.curves["Average"].hide()
        self.curves["Max. Hold"].hide()
        self.curves["Min. Hold"].hide()
        self.curves["Trace A"].hide()
        self.curves["Trace B"].hide()
        self.curves["Delta"].hide()
        
        # Crosshair Vertical Line
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#38bdf8', width=1, style=Qt.PenStyle.DashLine))
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        
        # DTV Threshold Line (Draggable)
        self.threshold_line = pg.InfiniteLine(
            angle=0, movable=True, pen=pg.mkPen('#ef4444', width=1.5, style=Qt.PenStyle.DashLine),
            hoverPen=pg.mkPen('#fca5a5', width=2.0, style=Qt.PenStyle.SolidLine),
            label="DTV THRESH: {value:.1f} dBm",
            labelOpts={'position': 0.12, 'color': '#ef4444', 'fill': (22, 27, 34, 220), 'movable': True}
        )
        self.threshold_line.setPos(-70.0)
        self.threshold_line.hide()
        self.threshold_line.sigDragged.connect(lambda l: self.thresholdChanged.emit(l.value()))
        self.plot_widget.addItem(self.threshold_line, ignoreBounds=True)
        
        # Intruder Threshold Line (Draggable)
        self.intruder_threshold_line = pg.InfiniteLine(
            angle=0, movable=True,
            pen=pg.mkPen('#d946ef', width=1.8, style=Qt.PenStyle.DashLine),
            hoverPen=pg.mkPen('#f0abfc', width=2.2, style=Qt.PenStyle.SolidLine),
            label="INTRUDER THRESH: {value:.1f} dBm",
            labelOpts={'position': 0.88, 'color': '#d946ef', 'fill': (22, 27, 34, 220), 'movable': True}
        )
        self.intruder_threshold_line.setPos(-80.0)
        self.intruder_threshold_line.hide()
        self.intruder_threshold_line.sigDragged.connect(lambda l: self.intruderThresholdChanged.emit(l.value()))
        self.plot_widget.addItem(self.intruder_threshold_line, ignoreBounds=True)
        
        # DECT Intercom Threshold Line (Draggable)
        self.dect_threshold_line = pg.InfiniteLine(
            angle=0, movable=True,
            pen=pg.mkPen('#f59e0b', width=1.8, style=Qt.PenStyle.DashLine),
            hoverPen=pg.mkPen('#fbbf24', width=2.2, style=Qt.PenStyle.SolidLine),
            label="DECT THRESH: {value:.1f} dBm",
            labelOpts={'position': 0.88, 'color': '#f59e0b', 'fill': (22, 27, 34, 220), 'movable': True}
        )
        self.dect_threshold_line.setPos(-85.0)
        self.dect_threshold_line.hide()
        self.dect_threshold_line.sigDragged.connect(lambda l: self.dectThresholdChanged.emit(l.value()))
        self.plot_widget.addItem(self.dect_threshold_line, ignoreBounds=True)
        
        # 2.4 GHz ShowLink & CRMX Threshold Line (Draggable)
        self.showlink_threshold_line = pg.InfiniteLine(
            angle=0, movable=True,
            pen=pg.mkPen('#2dd4bf', width=1.8, style=Qt.PenStyle.DashLine),
            hoverPen=pg.mkPen('#5eead4', width=2.2, style=Qt.PenStyle.SolidLine),
            label="SHOWLINK THRESH: {value:.1f} dBm",
            labelOpts={'position': 0.88, 'color': '#2dd4bf', 'fill': (22, 27, 34, 220), 'movable': True}
        )
        self.showlink_threshold_line.setPos(-80.0)
        self.showlink_threshold_line.hide()
        self.showlink_threshold_line.sigDragged.connect(lambda l: self.showlinkThresholdChanged.emit(l.value()))
        self.plot_widget.addItem(self.showlink_threshold_line, ignoreBounds=True)
        
        # Signals
        self.plot_widget.getViewBox().sigRangeChanged.connect(self._on_plot_range_changed)
        self.plot_widget.getViewBox().sigXRangeChanged.connect(self.channel_bar.update_visibility)
        self.plot_widget.getViewBox().sigResized.connect(lambda *_: self._update_carrier_labels())
        self.plot_widget.scene().sigMouseClicked.connect(self._on_scene_mouse_clicked)
        self.mouse_proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved)

    def show_dtv_threshold(self, level_dbm, caption: str = "DTV THRESH", movable: bool = True):
        """
        The DTV detector's level as a horizontal line; level_dbm None hides it.
        Movable: the user's fixed threshold (dragging emits thresholdChanged).
        Not movable: a level the detector works out itself.
        """
        line = self.threshold_line
        if level_dbm is None:
            line.setVisible(False)
            return
        line.setMovable(movable)
        line.setVisible(True)       # first: the label only updates its text while it is shown
        line.setPos(float(level_dbm))
        line.label.setFormat(caption + ": {value:.1f} dBm")

    def _on_scene_mouse_clicked(self, evt):
        if evt.button() == Qt.MouseButton.RightButton:
            pos = evt.scenePos()
            if self.plot_widget.sceneBoundingRect().contains(pos):
                vb = self.plot_widget.getViewBox()
                mouse_pt = vb.mapSceneToView(pos)
                freq_mhz = mouse_pt.x()
                
                menu = QMenu(self)
                menu.setStyleSheet("""
                    QMenu {
                        background-color: #161b22;
                        color: #c9d1d9;
                        border: 1px solid #30363d;
                        border-radius: 6px;
                        padding: 4px 0px;
                        font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
                        font-size: 11px;
                    }
                    QMenu::item {
                        padding: 6px 16px;
                    }
                    QMenu::item:selected {
                        background-color: #238636;
                        color: #ffffff;
                    }
                """)
                action_zero_span = menu.addAction(f"Trigger Zero-Span @ {freq_mhz:.4f} MHz")
                action_zero_span.triggered.connect(lambda: self.triggerZeroSpanRequested.emit(freq_mhz))
                global_pos = self.plot_widget.mapToGlobal(self.plot_widget.mapFromScene(pos))
                menu.exec(global_pos)
                evt.accept()

    def _on_plot_range_changed(self, vb, r):
        self.rangeChanged.emit(r)
        self._update_text_items()

    def _calc_text_y_pos(self):
        try:
            # Position station badges neatly below the top reference level line (0.3 divisions below ceiling)
            return self.ref_level - (self.scale_div * 0.30)
        except Exception:
            return self.ref_level - 3.0

    def set_amplitude_scale(self, ref_level: float, scale_div: float = 10.0):
        """
        Links the Spectrum View Y-axis height directly to the hardware Reference Level
        and user-defined Scale/Div (dB/division).
        The reference level forms the exact top line of the graticule.
        """
        self.ref_level = float(ref_level)
        self.scale_div = max(0.5, float(scale_div))
        bottom = self.ref_level - (self.scale_div * self.num_divisions)

        self.power_axis.set_params(self.ref_level, self.scale_div, self.num_divisions)
        self.plot_widget.setYRange(bottom, self.ref_level, padding=0)

        div_str = f"{self.scale_div:.0f}" if abs(self.scale_div - round(self.scale_div)) < 0.01 else f"{self.scale_div:.1f}"
        self.scale_badge.setText(f"REF: {self.ref_level:.1f} dBm | {div_str} dB/DIV")
        # A second view kept on the same scale (the other antenna's, in diversity)
        follower = getattr(self, "amplitude_follower", None)
        if follower is not None:
            follower.set_amplitude_scale(ref_level, scale_div)

        self._update_text_items()

    def _fit_channel_text(self, mask_w_px, ch_label, f_start, f_stop, kind, info):
        return channel_label_html(mask_w_px, kind, ch_label, f_start, f_stop, info)

    def _update_text_items(self):
        vb = self.plot_widget.getViewBox()
        if vb is None:
            return
        y_pos = self._calc_text_y_pos()
        for ch_id, t_item in self.channel_text_items.items():
            if ch_id not in self.channel_text_meta:
                continue
            meta = self.channel_text_meta[ch_id]
            f_start, f_stop, ch_label, kind, info, is_active = meta
            if not is_active:
                t_item.setVisible(False)
                continue
            p1 = vb.mapViewToDevice(QPointF(f_start, 0.0))
            p2 = vb.mapViewToDevice(QPointF(f_stop, 0.0))
            mask_w = abs(p2.x() - p1.x())
            if mask_w < 22:
                t_item.setVisible(False)
                continue
            html = self._fit_channel_text(mask_w, ch_label, f_start, f_stop, kind, info)
            t_item.setHtml(html)
            t_item.setPos((f_start + f_stop) / 2.0, y_pos)
            t_item.setVisible(True)
        self._update_carrier_labels()

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_pt = self.plot_widget.getViewBox().mapSceneToView(pos)
            self.v_line.setPos(mouse_pt.x())
            self.mouseMoved.emit(mouse_pt.x(), mouse_pt.y())
            self._update_carrier_tip(mouse_pt.x(), pos)
        else:
            self._hide_carrier_tip()

    def update_hud(self, freq_mhz: float, power_dbm: float, tag: str = None):
        if freq_mhz >= 1000.0:
            freq_str = f"{freq_mhz / 1000.0:.5f} GHz"
        else:
            freq_str = f"{freq_mhz:.4f} MHz"
            
        pwr_str = f"{power_dbm:.1f} dBm" if power_dbm is not None else "--.- dBm"
        tag_str = f" | {tag}" if tag else ""
        self.hud_label.setText(f"FREQ: {freq_str} | PWR: {pwr_str}{tag_str}")

    def set_trace_visible(self, name: str, visible: bool):
        if name in self.curves:
            self.curves[name].setVisible(visible)

    def set_trace_color(self, name: str, color: QColor):
        if name in self.curves:
            self.curves[name].setPen(pg.mkPen(color, width=1.8))

    def update_curve_data(self, name: str, x_data, y_data):
        if name in self.curves and self.curves[name].isVisible():
            self.curves[name].setData(x_data, y_data)

    def clear_traces(self):
        """Take every trace off the plot (no analyzer is supplying one). Masks, markers and
        threshold lines stay: they are settings, not measurements."""
        for curve in self.curves.values():
            curve.setData([], [])
        self.set_emission_masks([])
        self.set_intermod_markers([])

    def set_view_range(self, start_mhz: float, stop_mhz: float):
        self.plot_widget.setXRange(start_mhz, stop_mhz, padding=0)

    def set_span_alert(self, visible: bool):
        self.span_alert.setVisible(visible)

    MIRRORED_MASKS = ("update_channel_masks", "clear_channel_masks", "set_soundbase_masks",
                      "set_soundbase_mask_visible", "update_carrier_mask_color", "clear_soundbase_masks")

    def mirror_masks_to(self, other: "SpectrumView"):
        """
        Keep another spectrum view's channel and carrier masks the same as this one's (the
        second antenna's view in diversity): whatever sets them here sets them there too.
        """
        for name in self.MIRRORED_MASKS:
            own = getattr(self, name)

            def both(*args, _own=own, _name=name, **kwargs):
                result = _own(*args, **kwargs)
                getattr(other, _name)(*args, **kwargs)
                return result
            setattr(self, name, both)

    def update_channel_masks(self, active_dict: dict, standard, ps_dict: dict = None, channel_names: dict = None):
        if ps_dict is None:
            ps_dict = {}
        if channel_names is not None:
            self._channel_names = channel_names
        else:
            channel_names = self._channel_names or {}

        self._last_active_dict = active_dict
        self._last_standard = standard
        self._last_ps_dict = ps_dict

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
                    all_channels.append((c_id, start_f, stop_f, c_item.get("type", "default"), c_item.get("label", str(c_id))))
            elif "start_ch" in band:
                s_ch = band["start_ch"]
                e_ch = band["end_ch"]
                s_f = band["start_freq"]
                sp = band["spacing"]
                for ch in range(s_ch, e_ch + 1):
                    ch_idx = ch - s_ch
                    f1 = s_f + (ch_idx * sp)
                    f2 = f1 + sp
                    all_channels.append((ch, f1, f2, band.get("type", "dtv"), str(ch)))

        y_pos = self._calc_text_y_pos()

        for ch_info in all_channels:
            if len(ch_info) == 5:
                ch_id, f_start, f_stop, ch_type, ch_label = ch_info
            else:
                ch_id, f_start, f_stop, ch_type = ch_info
                ch_label = str(ch_id)

            is_active = active_dict.get(ch_id, False)
            is_ps = ps_dict.get(ch_id, False)

            kind = channel_kind(ch_type, is_ps)
            brush, pen = mask_brush_pen(kind)

            if is_active:
                # 1. 6 MHz Mask LinearRegionItem
                if ch_id not in self.channel_masks:
                    region = pg.LinearRegionItem(
                        values=[f_start, f_stop],
                        orientation='vertical',
                        movable=False,
                        brush=brush,
                        pen=pen
                    )
                    region.setZValue(-5)
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

                # 2. Station Text inside 6 MHz Mask at top of scale (0 dBm reference)
                x_center = (f_start + f_stop) / 2.0
                if isinstance(ch_id, int) or str(ch_id).isdigit():
                    ch_title = f"{ch_id}"
                else:
                    ch_title = f"{ch_label}"

                info = channel_names.get(ch_id) or channel_names.get(str(ch_id))
                self.channel_text_meta[ch_id] = (f_start, f_stop, ch_title, kind, info, True)

                # Compute device pixel width of the 6 MHz mask to auto-fit text inside it
                vb = self.plot_widget.getViewBox()
                p1 = vb.mapViewToDevice(QPointF(f_start, 0.0))
                p2 = vb.mapViewToDevice(QPointF(f_stop, 0.0))
                mask_w = abs(p2.x() - p1.x())

                html_text = self._fit_channel_text(mask_w, ch_title, f_start, f_stop, kind, info)

                if ch_id not in self.channel_text_items:
                    t_item = pg.TextItem(
                        anchor=(0.5, 0.0),
                        fill=None,
                        border=None
                    )
                    t_item.setHtml(html_text)
                    t_item.setPos(x_center, y_pos)
                    t_item.setZValue(10)
                    self.plot_widget.addItem(t_item)
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
            self.plot_widget.removeItem(region)
        self.channel_masks.clear()
        for t_item in self.channel_text_items.values():
            self.plot_widget.removeItem(t_item)
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

    # --- Soundbase Narrowband Carrier Masks ---
    def set_soundbase_masks(self, carriers: list):
        """
        Creates or updates narrowband LinearRegionItem masks for Soundbase carriers.
        """
        self.clear_soundbase_masks()
        for c in carriers:
            c_id = str(c.get("id"))
            f_start = float(c.get("f_start_mhz", 0.0))
            f_stop = float(c.get("f_stop_mhz", 0.0))
            if f_stop <= f_start:
                continue

            color_str = c.get("color", "#38bdf8")
            qcol = QColor(color_str)
            if not qcol.isValid():
                qcol = QColor("#38bdf8")

            # Semi-transparent brush and solid border pen
            brush = pg.mkBrush(QColor(qcol.red(), qcol.green(), qcol.blue(), 55))
            pen = pg.mkPen(QColor(qcol.red(), qcol.green(), qcol.blue(), 200), width=1.2, style=Qt.PenStyle.SolidLine)

            region = pg.LinearRegionItem(
                values=[f_start, f_stop],
                orientation='vertical',
                movable=False,
                brush=brush,
                pen=pen
            )
            region.setZValue(-4)
            region.setAcceptHoverEvents(False)
            region.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.plot_widget.addItem(region)
            self.soundbase_masks[c_id] = region

            name = str(c.get("name") or "").strip() or f"Ch {(f_start + f_stop) / 2.0:.3f}"
            device = self._carrier_device(c)
            self._carrier_meta[c_id] = {
                "name": name,
                "device": device,
                "f_start": f_start,
                "f_stop": f_stop,
                "color": self._carrier_text_color(qcol),
                "visible": True,
                "is_wmas": bool(c.get("is_wmas")),
                "name_w": self._carrier_fm.horizontalAdvance(name),
                "device_w": self._carrier_fm.horizontalAdvance(device),
            }

        self._carrier_order = sorted((m["f_start"], c_id) for c_id, m in self._carrier_meta.items())
        self._carrier_starts = [f for f, _ in self._carrier_order]
        self._carrier_max_bw = max((m["f_stop"] - m["f_start"] for m in self._carrier_meta.values()), default=0.0)
        self._update_carrier_labels()

    @staticmethod
    def _carrier_device(carrier: dict) -> str:
        """The transmitter a carrier belongs to, e.g. 'Shure AD/Standard (G57)'."""
        model = str(carrier.get("model") or "").strip()
        mfg = str(carrier.get("manufacturer") or "").strip()
        band = str(carrier.get("band") or "").strip()
        device = model
        if mfg and mfg.lower() not in model.lower():
            device = f"{mfg} {model}".strip()
        if band and band.lower() not in device.lower():
            device = f"{device} ({band})" if device else band
        return device

    @staticmethod
    def _carrier_text_color(qcol: QColor) -> str:
        """The carrier's colour, lightened where needed to read on the dark plot."""
        h, s, l, _ = qcol.getHslF()
        return QColor.fromHslF(max(h, 0.0), s, max(l, 0.68)).name()

    def set_soundbase_mask_visible(self, carrier_id: str, visible: bool):
        c_id = str(carrier_id)
        if c_id in self.soundbase_masks:
            self.soundbase_masks[c_id].setVisible(visible)
            self._carrier_meta[c_id]["visible"] = bool(visible)
            self._update_carrier_labels()

    def update_carrier_mask_color(self, carrier_id: str, new_color_hex: str):
        c_id = str(carrier_id)
        if c_id in self.soundbase_masks:
            qcol = QColor(new_color_hex)
            if not qcol.isValid():
                qcol = QColor("#38bdf8")
            brush = pg.mkBrush(QColor(qcol.red(), qcol.green(), qcol.blue(), 55))
            pen = pg.mkPen(QColor(qcol.red(), qcol.green(), qcol.blue(), 200), width=1.2, style=Qt.PenStyle.SolidLine)
            self.soundbase_masks[c_id].setBrush(brush)
            for line in self.soundbase_masks[c_id].lines:
                line.setPen(pen)
            self._carrier_meta[c_id]["color"] = self._carrier_text_color(qcol)
            self._update_carrier_labels()

    # Carrier labels start this far below the DTV station badges, in pixels
    CARRIER_LABEL_OFFSET_PX = 56
    # Narrowest mask, in pixels, that gets a name; below this only the hover names it
    CARRIER_LABEL_MIN_MASK_PX = 6

    def _update_carrier_labels(self):
        """
        Names each carrier on its mask once zoomed in far enough to tell the
        masks apart: rotated along the mask while it is narrow, upright (with
        the device underneath) once the name fits across it.
        """
        vb = self.plot_widget.getViewBox()
        shown = set()
        px_w = px_h = 0.0
        if self._carrier_order and vb is not None:
            try:
                px_w, px_h = vb.viewPixelSize()   # MHz and dB per pixel
            except Exception:
                px_w = px_h = 0.0

        line_h = self._carrier_fm.height()
        if px_w > 0 and px_h > 0 and self._carrier_max_bw / px_w >= self.CARRIER_LABEL_MIN_MASK_PX:
            x_min, x_max = vb.viewRange()[0]
            y_top = self._calc_text_y_pos() - self.CARRIER_LABEL_OFFSET_PX * px_h
            max_len = max(40, min(170, int(vb.height()) - self.CARRIER_LABEL_OFFSET_PX - 40))
            last_right = None
            lo = bisect.bisect_left(self._carrier_starts, x_min - self._carrier_max_bw)
            hi = bisect.bisect_right(self._carrier_starts, x_max)
            for f_start, c_id in self._carrier_order[lo:hi]:
                meta = self._carrier_meta[c_id]
                f_stop = meta["f_stop"]
                if not meta["visible"] or f_stop < x_min:
                    continue
                mask_w = (f_stop - f_start) / px_w
                if mask_w < self.CARRIER_LABEL_MIN_MASK_PX:
                    continue

                upright = meta["name_w"] + 8 <= mask_w
                half_w = (meta["name_w"] / 2.0 + 4) if upright else (line_h / 2.0)
                centre = (f_start + f_stop) / 2.0
                centre_px = (centre - x_min) / px_w
                if last_right is not None and centre_px - half_w < last_right:
                    continue   # would sit on top of the previous label
                last_right = centre_px + half_w + 1

                color = meta["color"]
                if upright:
                    text = f"<span style='color: {color};'>{html.escape(meta['name'])}</span>"
                    if meta["device"] and meta["device"] != meta["name"] and meta["device_w"] + 8 <= mask_w:
                        text += (f"<br><span style='color: #cbd5e1; font-weight: normal;'>"
                                 f"{html.escape(meta['device'])}</span>")
                    text = f"<div style='text-align: center;'>{text}</div>"
                else:
                    name = self._carrier_fm.elidedText(meta["name"], Qt.TextElideMode.ElideRight, max_len)
                    text = f"<span style='color: {color};'>{html.escape(name)}</span>"

                item = self._carrier_labels.get(c_id)
                if item is None:
                    item = pg.TextItem(anchor=(0.5, 0.0), fill=pg.mkBrush(13, 17, 23, 190))
                    item.setFont(self._carrier_font)
                    item.setZValue(9)
                    self.plot_widget.addItem(item, ignoreBounds=True)
                    self._carrier_labels[c_id] = item
                if self._carrier_label_state.get(c_id) != (upright, text):
                    self._carrier_label_state[c_id] = (upright, text)
                    item.setTextWidth(-1)
                    item.setHtml(text)
                    if upright:
                        # Centring needs a fixed width; use the text's own
                        item.setTextWidth(item.textItem.document().idealWidth())
                    # Rotated labels read upwards and hang from their last letter
                    item.setAngle(0 if upright else 90)
                    item.setAnchor((0.5, 0.0) if upright else (1.0, 0.5))
                item.setPos(centre, y_top)
                item.setVisible(True)
                shown.add(c_id)

        for c_id in self._carrier_labels_shown - shown:
            if c_id in self._carrier_labels:
                self._carrier_labels[c_id].setVisible(False)
        self._carrier_labels_shown = shown

    def _carrier_at(self, freq_mhz: float):
        """The visible carrier whose mask lies under, or within a few pixels of, freq_mhz."""
        if not self._carrier_order:
            return None
        try:
            tol = 3.0 * self.plot_widget.getViewBox().viewPixelSize()[0]
        except Exception:
            tol = 0.0
        best, best_dist = None, None
        lo = bisect.bisect_left(self._carrier_starts, freq_mhz - tol - self._carrier_max_bw)
        hi = bisect.bisect_right(self._carrier_starts, freq_mhz + tol)
        for _, c_id in self._carrier_order[lo:hi]:
            meta = self._carrier_meta[c_id]
            if not meta["visible"] or freq_mhz > meta["f_stop"] + tol:
                continue
            dist = abs(freq_mhz - (meta["f_start"] + meta["f_stop"]) / 2.0)
            if best_dist is None or dist < best_dist:
                best, best_dist = meta, dist
        return best

    def _update_carrier_tip(self, freq_mhz: float, scene_pos):
        """Hovering a carrier mask names the channel and its device, at any zoom."""
        meta = None
        if QApplication.mouseButtons() == Qt.MouseButton.NoButton:
            meta = self._carrier_at(freq_mhz)
        if meta is None:
            self._hide_carrier_tip()
            return
        centre = (meta["f_start"] + meta["f_stop"]) / 2.0
        bw_khz = (meta["f_stop"] - meta["f_start"]) * 1000.0
        tip = (
            f"<div style='white-space: nowrap;'>"
            f"<b style='color: {meta['color']};'>{html.escape(meta['name'])}</b><br>"
            f"{html.escape(meta['device']) or 'Device not specified'}<br>"
            f"<span style='color: #8b949e;'>{centre:.3f} MHz &middot; {bw_khz:.0f} kHz</span>"
            f"</div>"
        )
        global_pos = self.plot_widget.mapToGlobal(self.plot_widget.mapFromScene(scene_pos))
        # Qt leaves a tooltip where it is while its text is unchanged
        QToolTip.showText(global_pos, tip, self.plot_widget)
        self._carrier_tip_shown = True

    def _hide_carrier_tip(self):
        if self._carrier_tip_shown:
            QToolTip.hideText()
            self._carrier_tip_shown = False

    def set_emission_masks(self, masks: list):
        """
        Draw the emission masks around coordinated carriers (core/emission_mask.py):
        masks is [(x_mhz array, y_dbm array, state)], state False: the mask holds, True:
        something breaks through it, "idle": the carrier is not on the air (the shape
        only, dashed). One line item per state.
        """
        if not hasattr(self, "_emission_mask_items"):
            self._emission_mask_items = {}
            for state, color, style in ((False, "#e2e8f0", Qt.PenStyle.SolidLine), (True, "#ef4444", Qt.PenStyle.SolidLine),
                                        ("idle", "#64748b", Qt.PenStyle.DashLine)):
                item = pg.PlotDataItem(pen=pg.mkPen(QColor(color), width=1, style=style), connect="finite")
                item.setZValue(-2)
                self.plot_widget.addItem(item, ignoreBounds=True)
                self._emission_mask_items[state] = item
        for broken, item in self._emission_mask_items.items():
            xs, ys = [], []
            for x, y, b in masks:
                if b is broken and len(x):
                    y = np.asarray(y, dtype=float)
                    keep = ~np.isnan(y)
                    # drop the stretches no mask covers, leaving one gap marker between runs
                    keep[1:] |= keep[:-1]
                    xs += [np.asarray(x, dtype=float)[keep], [np.nan]]
                    ys += [y[keep], [np.nan]]
            if xs:
                item.setData(np.concatenate(xs), np.concatenate(ys))
            else:
                item.setData([], [])

    # One colour per order: IM3 orange, IM5 cyan, 3-tone magenta (the Intermod tab's
    # checkboxes are coloured the same way)
    INTERMOD_COLORS = {3: "#f97316", 5: "#22d3ee", 33: "#e879f9"}

    def set_intermod_markers(self, products: list):
        """
        Draw intermod products, one batched item per order. products: [(freq_mhz,
        order, level_dbm)] with order 3, 5 or 33 (3-tone). A product with an
        estimated level is a stem up to that level with a dot on top; one whose
        level is not known is a dashed line the full height of the plot.
        """
        if not hasattr(self, "intermod_items"):
            self.intermod_items = []
        for item in self.intermod_items:
            self.plot_widget.removeItem(item)
        self.intermod_items = []
        for order, color in self.INTERMOD_COLORS.items():
            known = [(f, lvl) for f, o, lvl in products if o == order and lvl is not None]
            unknown = [f for f, o, lvl in products if o == order and lvl is None]
            if unknown:
                x = np.repeat(np.asarray(unknown, dtype=float), 2)
                y = np.tile([-300.0, 100.0], len(unknown))
                item = pg.PlotDataItem(x, y, connect="pairs",
                                       pen=pg.mkPen(QColor(color), width=1, style=Qt.PenStyle.DashLine))
                item.setZValue(-3)
                self.plot_widget.addItem(item, ignoreBounds=True)
                self.intermod_items.append(item)
            if known:
                fs = np.asarray([f for f, _l in known], dtype=float)
                ls = np.asarray([l for _f, l in known], dtype=float)
                x = np.repeat(fs, 2)
                y = np.column_stack([np.full(len(fs), -300.0), ls]).ravel()
                stems = pg.PlotDataItem(x, y, connect="pairs", pen=pg.mkPen(QColor(color), width=1))
                stems.setZValue(-3)
                self.plot_widget.addItem(stems, ignoreBounds=True)
                tops = pg.ScatterPlotItem(fs, ls, size=5, pen=None, brush=QColor(color), pxMode=True)
                tops.setZValue(-3)
                self.plot_widget.addItem(tops, ignoreBounds=True)
                self.intermod_items += [stems, tops]

    def clear_soundbase_masks(self):
        for region in self.soundbase_masks.values():
            self.plot_widget.removeItem(region)
        self.soundbase_masks.clear()
        for item in self._carrier_labels.values():
            self.plot_widget.removeItem(item)
        self._carrier_labels.clear()
        self._carrier_label_state.clear()
        self._carrier_labels_shown = set()
        self._carrier_meta.clear()
        self._carrier_order = []
        self._carrier_starts = []
        self._carrier_max_bw = 0.0
        self._hide_carrier_tip()

