"""
waterfall_view.py - High-Performance 2D Spectrogram / Waterfall Viewport.
Features fast image item rendering, customizable colormaps, dynamic gradient legend bar,
and synchronized frequency axis tracking.
"""

import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSlider, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor
from .channel_marker_bar import MHzAxisItem, ChannelMarkerBar
from core.constants import COLORMAP_CSS, WATERFALL_COLORMAPS

class WaterfallView(QWidget):
    """
    Spectrogram (Waterfall) 2D visualizer with dynamic colorbar legend and depth control.
    """
    colormapChanged = pyqtSignal(str)
    historyDepthChanged = pyqtSignal(int)
    mouseMoved = pyqtSignal(float, float)
    triggerZeroSpanRequested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_depth = 100
        self.current_colormap = "viridis"
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Top Header Bar
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 2)
        
        self.title_label = QLabel("SPECTROGRAM / WATERFALL")
        self.title_label.setStyleSheet("font-weight: 700; font-size: 11px; color: #8b949e; letter-spacing: 0.5px;")
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # Colormap Dropdown Selector
        cmap_label = QLabel("Theme:")
        cmap_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        header_layout.addWidget(cmap_label)
        
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems([c.capitalize() for c in WATERFALL_COLORMAPS])
        self.cmap_combo.setMaximumWidth(90)
        self.cmap_combo.currentTextChanged.connect(self._on_cmap_changed)
        header_layout.addWidget(self.cmap_combo)
        
        # Color Scale Gradient Legend Bar
        self.color_scale_label = QLabel("-120 dBm       -70 dBm       -20 dBm")
        self.color_scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.color_scale_label.setFixedSize(240, 18)
        header_layout.addWidget(self.color_scale_label)
        
        layout.addLayout(header_layout)
        
        # Plot Widget for Waterfall Image
        self.waterfall_widget = pg.PlotWidget(axisItems={'bottom': MHzAxisItem(orientation='bottom')})
        self.waterfall_widget.setBackground('#0d1117')
        self.waterfall_widget.setLabel('left', 'History', units='Sweeps')
        self.waterfall_widget.showGrid(x=True, y=False, alpha=0.15)
        self.waterfall_widget.hideButtons()
        self.waterfall_widget.getViewBox().setMouseEnabled(x=True, y=False)
        self.waterfall_widget.getViewBox().disableAutoRange()
        self.waterfall_widget.plotItem.setMenuEnabled(False)
        
        # Fixed Axis Widths for Alignment
        self.waterfall_widget.getAxis('left').setWidth(58)
        self.waterfall_widget.showAxis('right')
        r_axis = self.waterfall_widget.getAxis('right')
        r_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        r_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        r_axis.setWidth(15)
        
        # Image Item (autoDownsample=False prevents Qt render pipeline frame-skipping and strobing)
        self.waterfall_img = pg.ImageItem(autoDownsample=False)
        cmap = pg.colormap.get(self.current_colormap)
        self.waterfall_img.setColorMap(cmap)
        self.waterfall_widget.addItem(self.waterfall_img)
        
        # Crosshair Vertical Line
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#38bdf8', width=1, style=Qt.PenStyle.DashLine))
        self.waterfall_widget.addItem(self.v_line, ignoreBounds=True)
        
        layout.addWidget(self.waterfall_widget, 1)
        
        # Channel Marker Bar Under Waterfall
        self.channel_bar = ChannelMarkerBar()
        self.channel_bar.getAxis('left').setWidth(58)
        self.channel_bar.showAxis('right')
        cb_r_axis = self.channel_bar.getAxis('right')
        cb_r_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        cb_r_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        cb_r_axis.setWidth(15)
        layout.addWidget(self.channel_bar)
        
        self.update_color_scale_css()
        
        self._last_rect = None
        
        # 6 MHz Channel Exclusion Masks (LinearRegionItem per channel)
        self.channel_masks = {}
        
        # Mouse Move Proxy & Clicks
        self.waterfall_widget.scene().sigMouseClicked.connect(self._on_scene_mouse_clicked)
        self.mouse_proxy = pg.SignalProxy(self.waterfall_widget.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved)

    def _on_scene_mouse_clicked(self, evt):
        if evt.button() == Qt.MouseButton.RightButton:
            pos = evt.scenePos()
            if self.waterfall_widget.sceneBoundingRect().contains(pos):
                vb = self.waterfall_widget.getViewBox()
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
                global_pos = self.waterfall_widget.mapToGlobal(self.waterfall_widget.mapFromScene(pos))
                menu.exec(global_pos)
                evt.accept()

    def _on_mouse_moved(self, evt):
        pos = evt[0]
        if self.waterfall_widget.sceneBoundingRect().contains(pos):
            mouse_pt = self.waterfall_widget.getViewBox().mapSceneToView(pos)
            self.v_line.setPos(mouse_pt.x())
            self.mouseMoved.emit(mouse_pt.x(), mouse_pt.y())

    def _on_cmap_changed(self, text: str):
        cmap_name = text.lower()
        self.set_colormap(cmap_name)
        self.colormapChanged.emit(cmap_name)

    def set_colormap(self, cmap_name: str):
        if cmap_name in WATERFALL_COLORMAPS:
            self.current_colormap = cmap_name
            cmap = pg.colormap.get(cmap_name)
            self.waterfall_img.setColorMap(cmap)
            self.update_color_scale_css()
            # Sync combo box if needed
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
        self.waterfall_widget.setYRange(0, self.history_depth, padding=0)

    def update_image(self, img_data, rect_tuple):
        # rect_tuple: (x, y, w, h)
        if len(rect_tuple) == 4 and (rect_tuple[2] <= 0 or rect_tuple[3] <= 0):
            return
        self.waterfall_img.setImage(img_data, levels=[-120.0, -20.0], autoLevels=False)
        if self._last_rect != rect_tuple:
            self._last_rect = rect_tuple
            self.waterfall_img.setRect(rect_tuple)

    def update_channel_masks(self, active_dict: dict, standard: list, ps_dict: dict = None):
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
                    self.waterfall_widget.addItem(region)
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
            self.waterfall_widget.removeItem(region)
        self.channel_masks.clear()
