"""
spectrum_view.py - High-Performance Real-Time Spectrum Analyzer Viewport.
Features multi-trace curves, draggable RF thresholds, crosshair telemetry HUD,
and synchronized channel allocation markers.
"""

import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QCursor
from .channel_marker_bar import MHzAxisItem, ChannelMarkerBar

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
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Header Toolbar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        
        self.title_label = QLabel("REAL-TIME SPECTRUM (SWP MODE)")
        self.title_label.setStyleSheet("font-weight: 700; font-size: 11px; color: #8b949e; letter-spacing: 0.5px;")
        header_layout.addWidget(self.title_label)
        
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
        
        # Plot Widget
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': MHzAxisItem(orientation='bottom')})
        self.plot_widget.setBackground('#0d1117')
        self.plot_widget.setLabel('left', 'Power', units='dBm')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.setYRange(-130, 10, padding=0)
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
        
        # Traces
        self.curves = {
            "Real-Time": self.plot_widget.plot(pen=pg.mkPen('#eab308', width=1.8)),
            "Average": self.plot_widget.plot(pen=pg.mkPen('#10b981', width=1.8)),
            "Max. Hold": self.plot_widget.plot(pen=pg.mkPen('#06b6d4', width=1.5)),
            "Min. Hold": self.plot_widget.plot(pen=pg.mkPen('#d946ef', width=1.5)),
            "Trace A": self.plot_widget.plot(pen=pg.mkPen('#38bdf8', width=1.8)),
            "Trace B": self.plot_widget.plot(pen=pg.mkPen('#f97316', width=1.8)),
            "Delta": self.plot_widget.plot(pen=pg.mkPen('#a855f7', width=1.8, style=Qt.PenStyle.DashLine))
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
            angle=0, movable=True, pen=pg.mkPen('#ef4444', width=1.5, style=Qt.PenStyle.DashLine)
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
        self.plot_widget.scene().sigMouseClicked.connect(self._on_scene_mouse_clicked)
        self.mouse_proxy = pg.SignalProxy(self.plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved)

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
            vb = self.plot_widget.getViewBox()
            y_range = vb.viewRange()[1]
            y_min, y_max = y_range[0], y_range[1]
            # When scale spans +10 to -30 dBm (or whenever 0 dBm is in range), use 0 dBm as reference
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
            
        if str(ch_label).strip() == "37":
            line1 = "CH 37 - OFF LIMITS" if mask_w_px >= 90 else ("CH 37" if mask_w_px >= 40 else "37")
        else:
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
        vb = self.plot_widget.getViewBox()
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

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_pt = self.plot_widget.getViewBox().mapSceneToView(pos)
            self.v_line.setPos(mouse_pt.x())
            self.mouseMoved.emit(mouse_pt.x(), mouse_pt.y())

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

    def set_view_range(self, start_mhz: float, stop_mhz: float):
        self.plot_widget.setXRange(start_mhz, stop_mhz, padding=0)

    def set_span_alert(self, visible: bool):
        self.span_alert.setVisible(visible)

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
                    all_channels.append((ch, f1, f2, "dtv", str(ch)))

        y_pos = self._calc_text_y_pos()

        for ch_info in all_channels:
            if len(ch_info) == 5:
                ch_id, f_start, f_stop, ch_type, ch_label = ch_info
            else:
                ch_id, f_start, f_stop, ch_type = ch_info
                ch_label = str(ch_id)

            is_active = active_dict.get(ch_id, False)
            is_ps = ps_dict.get(ch_id, False)

            if is_ps:
                brush = pg.mkBrush(QColor(239, 68, 68, 40))
                pen = pg.mkPen(QColor(248, 113, 113, 120), width=1, style=Qt.PenStyle.DashLine)
                hdr_color = "#f87171"
                border_color = QColor(248, 113, 113, 160)
            elif ch_type == "ch37" or ch_id == 37 or str(ch_id).strip() == "37":
                # Channel 37 is radio astronomy / medical telemetry - OFF LIMITS (Gray mask)
                brush = pg.mkBrush(QColor(100, 116, 139, 50))
                pen = pg.mkPen(QColor(148, 163, 184, 130), width=1.5, style=Qt.PenStyle.DashLine)
                hdr_color = "#94a3b8"
                border_color = QColor(148, 163, 184, 160)
            elif ch_type == "uplink":
                brush = pg.mkBrush(QColor(236, 72, 153, 35))
                pen = pg.mkPen(QColor(244, 114, 182, 110), width=1, style=Qt.PenStyle.DashLine)
                hdr_color = "#f472b6"
                border_color = QColor(244, 114, 182, 160)
            elif ch_type == "downlink":
                brush = pg.mkBrush(QColor(168, 85, 247, 35))
                pen = pg.mkPen(QColor(192, 132, 252, 110), width=1, style=Qt.PenStyle.DashLine)
                hdr_color = "#c084fc"
                border_color = QColor(192, 132, 252, 160)
            elif ch_type == "guard":
                brush = pg.mkBrush(QColor(100, 116, 139, 30))
                pen = pg.mkPen(QColor(148, 163, 184, 90), width=1, style=Qt.PenStyle.DashLine)
                hdr_color = "#94a3b8"
                border_color = QColor(148, 163, 184, 140)
            else:
                brush = pg.mkBrush(QColor(6, 182, 212, 35))
                pen = pg.mkPen(QColor(6, 182, 212, 110), width=1, style=Qt.PenStyle.DashLine)
                hdr_color = "#38bdf8"
                border_color = QColor(6, 182, 212, 160)

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

                call_sign = channel_names.get(ch_id) or channel_names.get(str(ch_id))
                self.channel_text_meta[ch_id] = (f_start, f_stop, ch_title, hdr_color, call_sign, True)

                # Compute device pixel width of the 6 MHz mask to auto-fit text inside it
                vb = self.plot_widget.getViewBox()
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

    def set_soundbase_mask_visible(self, carrier_id: str, visible: bool):
        c_id = str(carrier_id)
        if c_id in self.soundbase_masks:
            self.soundbase_masks[c_id].setVisible(visible)

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

    def clear_soundbase_masks(self):
        for region in self.soundbase_masks.values():
            self.plot_widget.removeItem(region)
        self.soundbase_masks.clear()

