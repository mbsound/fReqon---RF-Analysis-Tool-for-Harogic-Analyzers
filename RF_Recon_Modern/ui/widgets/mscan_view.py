"""
mscan_view.py - High-Density Discrete Channel Monitor & Multi-Meter Matrix.
Provides real-time production channel strips, live RF bar meters, peak hold,
rolling 30s sparklines, and dropout alarms for wireless microphone coordination.
"""

import time
import numpy as np
from typing import Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSplitter, QMenu, QComboBox, QSizePolicy, QColorDialog
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

import pyqtgraph as pg

class ChannelCard(QFrame):
    """
    Individual Channel Strip Card for a monitored production wireless microphone/IEM.
    """
    tuneDemodRequested = pyqtSignal(float)
    inspectRtsaRequested = pyqtSignal(float)
    carrierColorChanged = pyqtSignal(str, str) # carrier_id, new_color_hex

    def __init__(self, carrier: dict, parent=None):
        super().__init__(parent)
        self._status = None   # last status shown (styles only change with it)
        self.carrier = carrier
        self.channel_id = str(carrier.get("id", ""))
        self.name = carrier.get("name", "Channel")
        self.freq_hz = float(carrier.get("freq_hz", carrier.get("freq", 500e6)))
        self.freq_mhz = self.freq_hz / 1e6
        self.color_hex = carrier.get("color", "#38bdf8")
        self.group_name = carrier.get("group_name", "Group")

        self.current_power_dbm = -120.0
        self.peak_power_dbm = -120.0
        self.history_power = np.full(40, -120.0, dtype=np.float32)
        self.last_update_time = time.time()
        self.dropout_threshold_dbm = -75.0
        self.is_dropout = False

        self.setObjectName("channelCard")
        self.setFixedHeight(125)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._init_ui()
        self._update_card_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        # Header Row: Name & Frequency
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(4)

        # Color Accent Indicator
        self.accent_lbl = QLabel()
        self.accent_lbl.setFixedSize(4, 14)
        self.accent_lbl.setStyleSheet(f"background-color: {self.color_hex}; border-radius: 2px;")
        hdr_layout.addWidget(self.accent_lbl)

        self.name_lbl = QLabel(self.name)
        self.name_lbl.setStyleSheet("color: #f0f6fc; font-weight: 700; font-size: 11px;")
        self.name_lbl.setToolTip(f"{self.name} ({self.carrier.get('model', '')})")
        hdr_layout.addWidget(self.name_lbl)
        hdr_layout.addStretch()

        self.freq_lbl = QLabel(f"{self.freq_mhz:.3f}M")
        self.freq_lbl.setStyleSheet("color: #8b949e; font-size: 10px; font-family: monospace;")
        hdr_layout.addWidget(self.freq_lbl)
        layout.addLayout(hdr_layout)

        # Power Readout & Status Row
        val_layout = QHBoxLayout()
        val_layout.setSpacing(6)

        self.power_lbl = QLabel("-120.0 dBm")
        self.power_lbl.setStyleSheet("color: #38bdf8; font-size: 14px; font-weight: 700; font-family: monospace;")
        val_layout.addWidget(self.power_lbl)

        self.peak_lbl = QLabel("Pk: -120.0")
        self.peak_lbl.setStyleSheet("color: #6e7681; font-size: 9px; font-family: monospace;")
        val_layout.addWidget(self.peak_lbl)
        val_layout.addStretch()

        self.status_badge = QLabel("OFFLINE")
        self.status_badge.setStyleSheet("""
            background-color: #21262d;
            color: #8b949e;
            font-size: 9px;
            font-weight: 700;
            padding: 2px 5px;
            border-radius: 3px;
        """)
        val_layout.addWidget(self.status_badge)
        layout.addLayout(val_layout)

        # Live RF Level Bar Meter
        self.bar_container = QFrame()
        self.bar_container.setFixedHeight(10)
        self.bar_container.setStyleSheet("""
            background-color: #0d1117;
            border: 1px solid #30363d;
            border-radius: 3px;
        """)
        self.bar_fill = QFrame(self.bar_container)
        self.bar_fill.setFixedHeight(8)
        self.bar_fill.setGeometry(1, 1, 0, 8)
        self.bar_fill.setStyleSheet("background-color: #10b981; border-radius: 2px;")
        layout.addWidget(self.bar_container)

        # Sparkline widget (mini rolling trend)
        self.sparkline = pg.PlotWidget()
        self.sparkline.setFixedHeight(30)
        self.sparkline.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sparkline.setBackground('#0d1117')
        self.sparkline.hideAxis('bottom')
        self.sparkline.hideAxis('left')
        self.sparkline.setYRange(-105, -20)
        self.sparkline.setXRange(0, 40)
        self.sparkline.setMouseEnabled(x=False, y=False)
        self.sparkline.getPlotItem().setContentsMargins(0, 0, 0, 0)
        
        pen = pg.mkPen(color=self.color_hex, width=1.0)
        self.sparkline_curve = self.sparkline.plot(self.history_power, pen=pen)
        layout.addWidget(self.sparkline)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        act_color = menu.addAction("Change Color...")
        act_demod = menu.addAction(f"Tune Audio Demod ({self.freq_mhz:.3f} MHz)")
        act_rtsa = menu.addAction(f"Inspect in RTSA ({self.freq_mhz:.3f} MHz)")
        act_reset = menu.addAction("Reset Peak Hold")

        action = menu.exec(event.globalPos())
        if action == act_color:
            selected_color = QColorDialog.getColor(QColor(self.color_hex), self, f"Select Color for {self.name}")
            if selected_color.isValid():
                hex_col = selected_color.name()
                self.set_color(hex_col)
                self.carrierColorChanged.emit(self.channel_id, hex_col)
        elif action == act_demod:
            self.tuneDemodRequested.emit(self.freq_mhz)
        elif action == act_rtsa:
            self.inspectRtsaRequested.emit(self.freq_mhz)
        elif action == act_reset:
            self.peak_power_dbm = self.current_power_dbm
            self.peak_lbl.setText(f"Pk: {self.peak_power_dbm:.1f}")

    def set_color(self, new_color_hex: str):
        self.color_hex = new_color_hex
        self.carrier["color"] = new_color_hex
        self.accent_lbl.setStyleSheet(f"background-color: {new_color_hex}; border-radius: 2px;")
        pen = pg.mkPen(color=new_color_hex, width=1.0)
        self.sparkline_curve.setPen(pen)
        self._update_card_style()

    STATUS_STYLES = {
        "GOOD RF":  ("#064e3b", "#34d399", "#10b981", False),
        "MARGINAL": ("#78350f", "#fbbf24", "#f59e0b", False),
        "DROPOUT":  ("#7f1d1d", "#f87171", "#ef4444", True),
        "STANDBY":  ("#21262d", "#8b949e", "#374151", False),
    }

    def update_power(self, power_dbm: float, dropout_threshold_dbm: float = -75.0, worst_dbm: float = None):
        """power_dbm is shown; the status is judged on worst_dbm (the weakest
        hop since the last redraw) so a brief dropout is not missed."""
        self.current_power_dbm = power_dbm
        self.dropout_threshold_dbm = dropout_threshold_dbm
        self.last_update_time = time.time()
        judge = power_dbm if worst_dbm is None else min(power_dbm, worst_dbm)

        if power_dbm > self.peak_power_dbm:
            self.peak_power_dbm = power_dbm

        self.power_lbl.setText(f"{power_dbm:.1f} dBm")
        self.peak_lbl.setText(f"Pk: {self.peak_power_dbm:.1f}")

        if judge >= -65.0:
            status = "GOOD RF"
        elif judge >= dropout_threshold_dbm:
            status = "MARGINAL"
        elif judge > -95.0:
            status = "DROPOUT"
        else:
            status = "STANDBY"
        # Stylesheets re-polish the widget, so they are only applied on a status change
        if status != self._status:
            self._status = status
            bg, fg, fill_color, self.is_dropout = self.STATUS_STYLES[status]
            self.status_badge.setText(status)
            self.status_badge.setStyleSheet(f"background-color: {bg}; color: {fg}; font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 3px;")
            self.power_lbl.setStyleSheet(f"color: {fg if status != 'STANDBY' else '#6e7681'}; font-size: 14px; font-weight: 700; font-family: monospace;")
            self.bar_fill.setStyleSheet(f"background-color: {fill_color}; border-radius: 2px;")
            self._update_card_style()

        # Level Bar fill width (-100 dBm = 0%, -20 dBm = 100%)
        container_w = max(10, self.bar_container.width() - 2)
        fraction = max(0.0, min(1.0, (power_dbm - (-100.0)) / 80.0))
        self.bar_fill.setGeometry(1, 1, int(fraction * container_w), 8)

        self.history_power[:-1] = self.history_power[1:]
        self.history_power[-1] = power_dbm
        self.sparkline_curve.setData(self.history_power)

    def _update_card_style(self):
        if self.is_dropout:
            border_css = "border: 2px solid #ef4444;"
        else:
            border_css = f"border: 1.5px solid {self.color_hex};"

        self.setStyleSheet(f"""
            QFrame#channelCard {{
                background-color: #161b22;
                {border_css}
                border-radius: 6px;
            }}
            QFrame#channelCard:hover {{
                border: 2px solid {self.color_hex};
                background-color: #1c2128;
            }}
        """)


class MSCANView(QWidget):
    """
    Dedicated High-Density MSCAN Multi-Meter Viewport.
    Displays responsive grid of production wireless channel cards and split timeline.
    """
    tuneDemodRequested = pyqtSignal(float)
    inspectRtsaRequested = pyqtSignal(float)
    carrierColorChanged = pyqtSignal(str, str) # carrier_id, color_hex

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending = {}            # element_idx -> [latest, weakest, threshold] since the last redraw
        self._timeline_dirty = set()
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_pending)
        self._flush_timer.start(50)
        self.channel_cards: Dict[int, ChannelCard] = {} # element_index -> ChannelCard
        self.channel_list = []
        self.active_channels = []
        self.last_cycle_time = time.time()
        self.hop_count = 0
        self.hop_rate = 0.0

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        outer_layout.setSpacing(6)

        # Top Control & Filter Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_title = QLabel("RAPID CHANNEL MONITOR")
        lbl_title.setStyleSheet("font-size: 12px; font-weight: 800; color: #38bdf8; letter-spacing: 0.5px;")
        top_bar.addWidget(lbl_title)

        self.ch_count_lbl = QLabel("0 Channels Monitored")
        self.ch_count_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        top_bar.addWidget(self.ch_count_lbl)

        top_bar.addStretch()

        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Show All Channels", "all")
        self.filter_combo.addItem("Show Active Only", "active")
        self.filter_combo.addItem("Show Dropouts & Warnings", "warnings")
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        top_bar.addWidget(self.filter_combo)

        btn_reset_peaks = QPushButton("Reset All Peak Holds")
        btn_reset_peaks.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #8b949e;
            }
        """)
        btn_reset_peaks.clicked.connect(self.reset_all_peaks)
        top_bar.addWidget(btn_reset_peaks)

        outer_layout.addLayout(top_bar)

        # Splitter: Upper Grid Rack, Lower Multi-Trace Timeline
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        outer_layout.addWidget(self.splitter)

        # Scroll Area for Channel Grid Rack
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setStyleSheet("background-color: #0b0e14; border: 1px solid #21262d; border-radius: 4px;")

        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(8)
        self.grid_scroll.setWidget(self.grid_container)
        self.splitter.addWidget(self.grid_scroll)

        # Lower Split: Real-Time Multi-Carrier Strip Timeline
        timeline_box = QFrame()
        timeline_box.setStyleSheet("background-color: #0d1117; border: 1px solid #21262d; border-radius: 4px;")
        timeline_layout = QVBoxLayout(timeline_box)
        timeline_layout.setContentsMargins(6, 4, 6, 4)
        timeline_layout.setSpacing(2)

        t_lbl = QLabel("MULTICHANNEL RF POWER TIMELINE (LAST 60 SECONDS)")
        t_lbl.setStyleSheet("color: #8b949e; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        timeline_layout.addWidget(t_lbl)

        self.timeline_plot = pg.PlotWidget()
        self.timeline_plot.setBackground('#0d1117')
        self.timeline_plot.showGrid(x=True, y=True, alpha=0.15)
        self.timeline_plot.setYRange(-105, -20)
        self.timeline_plot.setLabel('left', 'RF Power', units='dBm')
        self.timeline_plot.setLabel('bottom', 'Time', units='s')
        timeline_layout.addWidget(self.timeline_plot)
        self.splitter.addWidget(timeline_box)

        self.splitter.setSizes([450, 180])

        # Timeline data buffers (rolling 120 points for top channels)
        self.timeline_curves = {}
        self.timeline_data = {}

        # Resize Timer to dynamically reflow grid columns
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self._reflow_grid)

    def set_channels(self, channels: list):
        """Re-initializes the channel cards from the selected Soundbase channel list."""
        self.channel_list = channels
        self.ch_count_lbl.setText(f"{len(channels)} Channels Monitored")

        # Clear existing grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.channel_cards.clear()
        self.timeline_plot.clear()
        self.timeline_curves.clear()
        self.timeline_data.clear()

        # Create cards
        for idx, ch in enumerate(channels):
            card = ChannelCard(ch)
            card.tuneDemodRequested.connect(self.tuneDemodRequested.emit)
            card.inspectRtsaRequested.connect(self.inspectRtsaRequested.emit)
            card.carrierColorChanged.connect(self.carrierColorChanged.emit)
            self.channel_cards[idx] = card

            # Add timeline trace for first 8 channels
            if idx < 8:
                c_color = ch.get("color", "#38bdf8")
                pen = pg.mkPen(color=c_color, width=1.0)
                name = ch.get("name", f"Ch {idx}")
                curve = self.timeline_plot.plot(pen=pen, name=name)
                self.timeline_curves[idx] = curve
                self.timeline_data[idx] = np.full(120, -110.0, dtype=np.float32)

        self._reflow_grid()

    def update_channel_color(self, carrier_id: str, new_color_hex: str):
        """Updates the color for a specific channel across its card and timeline curve."""
        c_id = str(carrier_id)
        for idx, card in self.channel_cards.items():
            if str(card.channel_id) == c_id:
                card.set_color(new_color_hex)
                if idx in self.timeline_curves:
                    pen = pg.mkPen(color=new_color_hex, width=1.0)
                    self.timeline_curves[idx].setPen(pen)
                break

    def update_channel_data(self, element_idx: int, freq_hz: float, peak_power_dbm: float, spec_data, info: dict, dropout_thresh_dbm: float = -75.0):
        """
        Records one hop. Hops arrive up to a thousand times a second, so the
        cards and the timeline are redrawn from the recorded values by
        _flush_pending at ~20 Hz; nothing a hop reports is lost (the timeline
        keeps every hop and a card's status reflects the weakest hop since the
        last redraw).
        """
        pend = self._pending.get(element_idx)
        if pend is None:
            self._pending[element_idx] = [peak_power_dbm, peak_power_dbm, dropout_thresh_dbm]
        else:
            pend[0] = peak_power_dbm
            pend[1] = min(pend[1], peak_power_dbm)
            pend[2] = dropout_thresh_dbm

        if element_idx in self.timeline_data:
            buf = self.timeline_data[element_idx]
            buf[:-1] = buf[1:]
            buf[-1] = peak_power_dbm
            self._timeline_dirty.add(element_idx)

        self.hop_count += 1
        now = time.time()
        dt = now - self.last_cycle_time
        if dt >= 0.5:
            self.hop_rate = self.hop_count / dt
            self.hop_count = 0
            self.last_cycle_time = now

    def _flush_pending(self):
        if not self._pending and not self._timeline_dirty:
            return
        for idx, (latest, worst, thresh) in self._pending.items():
            card = self.channel_cards.get(idx)
            if card:
                card.update_power(latest, thresh, worst)
        self._pending.clear()
        for idx in self._timeline_dirty:
            curve = self.timeline_curves.get(idx)
            if curve is not None:
                curve.setData(self.timeline_data[idx])
        self._timeline_dirty.clear()

    def _reflow_grid(self):
        """Lays out cards in a consistent 5-column grid across the viewport."""
        if not self.channel_cards:
            return

        num_cols = 5

        # Detach items from layout before placing in new grid positions
        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        for c in range(num_cols):
            self.grid_layout.setColumnStretch(c, 1)

        for idx, (el_idx, card) in enumerate(self.channel_cards.items()):
            row = idx // num_cols
            col = idx % num_cols
            self.grid_layout.addWidget(card, row, col)

        self.grid_layout.setRowStretch((len(self.channel_cards) // num_cols) + 1, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_timer.start(50)

    def _apply_filter(self):
        mode = self.filter_combo.currentData()
        for card in self.channel_cards.values():
            if mode == "all":
                card.show()
            elif mode == "active":
                card.setVisible(card.current_power_dbm > -85.0)
            elif mode == "warnings":
                card.setVisible(card.is_dropout or card.current_power_dbm < -70.0)

    def reset_all_peaks(self):
        for card in self.channel_cards.values():
            card.peak_power_dbm = card.current_power_dbm
            card.peak_lbl.setText(f"Pk: {card.peak_power_dbm:.1f}")
