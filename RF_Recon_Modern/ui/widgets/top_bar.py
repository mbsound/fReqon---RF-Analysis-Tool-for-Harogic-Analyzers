"""
top_bar.py - Unified Top Transport, Hardware Telemetry & Multi-Device Control Bar.
Provides real-time device connection chips, multi-device topology selectors,
master sweep play/pause controls, live threat banners, trace pills, and regional preset switchers.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox, QFrame, QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor


class ElidedLabel(QLabel):
    """A label that shortens its text with an ellipsis instead of being
    clipped, keeping the full text in the tooltip."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full = text
        self.setMinimumWidth(90)
        self.setMaximumWidth(200)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def setText(self, text: str):
        self._full = text
        self._refit()

    def fullText(self) -> str:
        return self._full

    def _refit(self):
        fm = self.fontMetrics()
        avail = max(20, self.maximumWidth() if self.width() <= 1 else self.width())
        super().setText(fm.elidedText(self._full, Qt.TextElideMode.ElideRight, avail))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._refit()
from ..icons import get_play_icon, get_pause_icon, get_settings_icon, get_chevron_icon
from core.multi_device_manager import MultiDeviceTopology

class TopBar(QWidget):
    """
    Unified Master Control Bar at the top of the application.
    """
    connectToggled = pyqtSignal()
    connectionConfigClicked = pyqtSignal()
    playPauseToggled = pyqtSignal(bool)
    regionChanged = pyqtSignal(str)
    settingsClicked = pyqtSignal()
    calManagerClicked = pyqtSignal()
    inputChainsClicked = pyqtSignal()
    traceToggled = pyqtSignal(str, bool)
    traceColorChanged = pyqtSignal(str, QColor)
    viewModeChanged = pyqtSignal(str)
    audioDemodClicked = pyqtSignal()
    intruderPrevClicked = pyqtSignal()
    intruderNextClicked = pyqtSignal()
    intruderBadgeClicked = pyqtSignal()
    
    # Multi-Device Signals
    multiDeviceFocusChanged = pyqtSignal(str) # slot_id
    diversityModeChanged = pyqtSignal(str) # "both", "slot_a", "slot_b", "delta"
    fanStateRequested = pyqtSignal(int, float) # fan_state, threshold_temp

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(44)
        self.current_topology = MultiDeviceTopology.SINGLE
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(8)
        
        # 1. Branding
        self.logo_label = QLabel("FREQON")
        self.logo_label.setStyleSheet("font-weight: 800; font-size: 14px; color: #38bdf8; letter-spacing: 1.5px; padding-left: 2px;")
        main_layout.addWidget(self.logo_label)
        
        self._add_separator(main_layout)
        
        # 2. Hardware Device Chip & Multi-Device Selector
        self.hw_endorsements = None
        self.power_state = None
        self.dev_chip = QFrame()
        self.dev_chip.setObjectName("cardFrame")
        self.dev_chip.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 2px 6px;")
        self.dev_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dev_chip.mousePressEvent = self._on_dev_chip_clicked
        dev_chip_layout = QHBoxLayout(self.dev_chip)
        dev_chip_layout.setContentsMargins(4, 2, 4, 2)
        dev_chip_layout.setSpacing(6)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #f43f5e; font-size: 12px;")
        self.status_dot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.status_dot.setToolTip("Click to view Hardware Endorsements & Licenses")
        self.status_dot.mousePressEvent = lambda ev: self._show_endorsements_menu()
        
        self.dev_label = ElidedLabel("Disconnected")
        self.dev_label.setStyleSheet("font-weight: 600; font-size: 11px; color: #8b949e;")
        self._identity_text = "Disconnected"   # what the label returns to after a transient notice
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.timeout.connect(lambda: self.dev_label.setText(self._identity_text))
        self.dev_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dev_label.setToolTip("Click to view Hardware Endorsements & Licenses")
        self.dev_label.mousePressEvent = lambda ev: self._show_endorsements_menu()
        
        self.topo_badge = QLabel("SINGLE")
        self.topo_badge.setStyleSheet("""
            background-color: #21262d;
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 9px;
            font-weight: 700;
            padding: 1px 4px;
            border-radius: 3px;
            border: 1px solid #30363d;
        """)
        self.topo_badge.hide()
        
        self.temp_unit = "C" # "C" or "F"
        self.current_temp_c = None
        self.current_fan_state = 2 # FanState_Auto (0=On, 1=Off, 2=Auto)
        self.current_fan_threshold = 50.0

        self.temp_label = QLabel("--.- °C")
        self.temp_label.setStyleSheet("""
            background-color: #21262d;
            color: #10b981;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            padding: 1px 5px;
            border-radius: 3px;
            border: 1px solid #30363d;
        """)
        self.temp_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.temp_label.setToolTip("Hardware Temperature & Fan Control (Click to configure)")
        self.temp_label.mousePressEvent = lambda ev: self._show_temp_fan_menu()
        self.temp_label.hide()
        
        self.interface_btn = QPushButton("Config...")
        self.interface_btn.setObjectName("pillBtn")
        self.interface_btn.setToolTip("Configure Connection Interface & Multi-Device Roles")
        self.interface_btn.setFixedHeight(20)
        self.interface_btn.setStyleSheet("""
            QPushButton#pillBtn {
                background-color: #21262d;
                border: 1px solid #30363d;
                color: #c9d1d9;
                font-size: 10px;
                font-weight: 600;
                padding: 1px 6px;
                border-radius: 3px;
            }
            QPushButton#pillBtn:hover {
                background-color: #30363d;
                color: #38bdf8;
                border-color: #38bdf8;
            }
        """)
        self.interface_btn.clicked.connect(self.connectionConfigClicked.emit)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primaryActionBtn")
        self.connect_btn.setFixedHeight(22)
        self.connect_btn.setMinimumWidth(88)
        self.connect_btn.setStyleSheet("""
            QPushButton#primaryActionBtn {
                background-color: #0969da;
                color: #ffffff;
                border: 1px solid #218bff;
                font-size: 11px;
                font-weight: 600;
                padding: 1px 8px;
                border-radius: 3px;
            }
            QPushButton#primaryActionBtn:hover {
                background-color: #1f7bf2;
            }
            QPushButton#dangerBtn {
                background-color: #da3633;
                color: #ffffff;
                border: 1px solid #f85149;
                font-size: 11px;
                font-weight: 600;
                padding: 1px 8px;
                border-radius: 3px;
            }
            QPushButton#dangerBtn:hover {
                background-color: #b62324;
            }
        """)
        self.connect_btn.clicked.connect(self.connectToggled.emit)
        
        dev_chip_layout.addWidget(self.status_dot)
        dev_chip_layout.addWidget(self.dev_label)
        dev_chip_layout.addWidget(self.topo_badge)
        dev_chip_layout.addWidget(self.temp_label)

        # Supply power (total W); per-port detail in the tooltip and device menu
        self.power_label = QLabel("-- W")
        self.power_label.hide()
        dev_chip_layout.addWidget(self.power_label)
        dev_chip_layout.addWidget(self.interface_btn)
        dev_chip_layout.addWidget(self.connect_btn)
        main_layout.addWidget(self.dev_chip, 0)
        
        # 2b. Multi-Device Mode Dynamic View Controls (Diversity / Multi-Zone Focus)
        self.multi_ctrl_frame = QFrame()
        self.multi_ctrl_frame.setStyleSheet("background-color: transparent;")
        self.multi_ctrl_layout = QHBoxLayout(self.multi_ctrl_frame)
        self.multi_ctrl_layout.setContentsMargins(0, 0, 0, 0)
        self.multi_ctrl_layout.setSpacing(4)
        
        self.focus_combo = QComboBox()
        self.focus_combo.setObjectName("pillCombo")
        self.focus_combo.setStyleSheet("""
            QComboBox {
                background-color: #161b22;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                color: #38bdf8;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
            }
        """)
        self.focus_combo.currentTextChanged.connect(self._on_focus_combo_changed)
        self.multi_ctrl_layout.addWidget(self.focus_combo)
        self.multi_ctrl_frame.hide()
        main_layout.addWidget(self.multi_ctrl_frame)
        
        # 3. Master Transport & Sweep Status
        self.play_pause_btn = QPushButton("Sweep")
        self.play_pause_btn.setObjectName("successBtn")
        self.play_pause_btn.setIcon(get_play_icon("#ffffff", 16))
        self.play_pause_btn.setFixedHeight(26)
        self.play_pause_btn.setCheckable(True)
        self.play_pause_btn.setEnabled(True)
        self.play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        main_layout.addWidget(self.play_pause_btn)
        
        self.fps_label = QLabel("0.0 FPS")
        self.fps_label.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #8b949e;")
        main_layout.addWidget(self.fps_label)
        
        self._add_separator(main_layout)
        
        # 4. Live Intruder Threat Banner (Dynamic)
        self.intruder_frame = QFrame()
        self.intruder_frame.setStyleSheet("""
            background-color: rgba(244, 63, 94, 0.15);
            border: 1px solid #f43f5e;
            border-radius: 4px;
            padding: 1px 4px;
        """)
        self.intruder_frame.hide()
        intr_layout = QHBoxLayout(self.intruder_frame)
        intr_layout.setContentsMargins(4, 0, 4, 0)
        intr_layout.setSpacing(4)
        
        self.intr_prev_btn = QPushButton()
        self.intr_prev_btn.setObjectName("iconBtn")
        self.intr_prev_btn.setIcon(get_chevron_icon("left", "#f43f5e", 14))
        self.intr_prev_btn.setFixedSize(18, 18)
        self.intr_prev_btn.clicked.connect(self.intruderPrevClicked.emit)
        
        self.intr_label = QPushButton("Intruder Detected (0)")
        self.intr_label.setStyleSheet("background: transparent; border: none; color: #f43f5e; font-weight: 700; font-size: 11px;")
        self.intr_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.intr_label.clicked.connect(self.intruderBadgeClicked.emit)
        
        self.intr_next_btn = QPushButton()
        self.intr_next_btn.setObjectName("iconBtn")
        self.intr_next_btn.setIcon(get_chevron_icon("right", "#f43f5e", 14))
        self.intr_next_btn.setFixedSize(18, 18)
        self.intr_next_btn.clicked.connect(self.intruderNextClicked.emit)
        
        intr_layout.addWidget(self.intr_prev_btn)
        intr_layout.addWidget(self.intr_label)
        intr_layout.addWidget(self.intr_next_btn)
        self.intruder_frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(self.intruder_frame)
        
        main_layout.addStretch()
        
        # 5. Trace Quick-Pills
        trace_frame = QFrame()
        trace_frame.setStyleSheet("background-color: transparent;")
        trace_layout = QHBoxLayout(trace_frame)
        trace_layout.setContentsMargins(0, 0, 0, 0)
        trace_layout.setSpacing(4)
        
        self.trace_buttons = {}
        traces = [
            ("Real-Time", True, "#eab308"),
            ("Max. Hold", False, "#06b6d4"),
            ("Min. Hold", False, "#d946ef"),
            ("Average", False, "#10b981")
        ]
        
        for name, default_on, color in traces:
            btn = QPushButton(name)
            btn.setObjectName("tracePillBtn")
            btn.setCheckable(True)
            btn.setChecked(default_on)
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #161b22;
                    color: #8b949e;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #21262d;
                    color: #c9d1d9;
                    border-color: #484f58;
                }}
                QPushButton:checked {{
                    background-color: rgba({r}, {g}, {b}, 0.18);
                    color: {color};
                    border: 1px solid {color};
                }}
            """)
            btn.clicked.connect(lambda chk, n=name: self.traceToggled.emit(n, chk))
            
            trace_layout.addWidget(btn)
            self.trace_buttons[name] = btn
            
        main_layout.addWidget(trace_frame)
        
        self._add_separator(main_layout)
        
        # 6. View Mode Selector
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.setObjectName("viewModeCombo")
        self.view_mode_combo.addItems(["Dual View", "Multi-Row Waterfall", "Spectrum Only", "Waterfall Only"])
        self.view_mode_combo.setToolTip("Select Viewport Canvas Layout")
        self.view_mode_combo.currentTextChanged.connect(self.viewModeChanged.emit)
        main_layout.addWidget(self.view_mode_combo)
        
        # 7. Region: chosen in Preferences & Settings (the gear button), not here. The
        # combo is kept, hidden, as the list set_regions() fills.
        self.region_combo = QComboBox(self)
        self.region_combo.setObjectName("regionCombo")
        self.region_combo.currentTextChanged.connect(self.regionChanged.emit)
        self.region_combo.hide()
        
        # 8. Settings, Audio & Cal Buttons
        self.audio_btn = QPushButton("Listen")
        self.audio_btn.setObjectName("pillBtn")
        self.audio_btn.setFixedHeight(24)
        self.audio_btn.setToolTip("Live Analog AM/FM Audio Demodulation & Acoustic Monitor")
        self.audio_btn.clicked.connect(self.audioDemodClicked.emit)
        main_layout.addWidget(self.audio_btn)
        
        self.cal_btn = QPushButton("Calibration ▾")
        self.cal_btn.setFixedHeight(24)
        cal_menu = QMenu(self.cal_btn)
        cal_menu.addAction("Calibration Manager…", self.calManagerClicked.emit)
        cal_menu.addAction("Input Chains (Antenna / Cable / Amplifier)…", self.inputChainsClicked.emit)
        self.cal_btn.setMenu(cal_menu)
        main_layout.addWidget(self.cal_btn)

        self.set_input_chain_state({})
        
        self.settings_btn = QPushButton()
        self.settings_btn.setObjectName("iconBtn")
        self.settings_btn.setIcon(get_settings_icon("#8b949e", 18))
        self.settings_btn.setFixedSize(26, 26)
        self.settings_btn.setToolTip("Preferences & Settings")
        self.settings_btn.clicked.connect(self.settingsClicked.emit)
        main_layout.addWidget(self.settings_btn)

    def set_device_temperature(self, temp_c: float):
        self.current_temp_c = temp_c
        self._update_temp_display()

    def _update_temp_display(self):
        if self.current_temp_c is None or self.current_temp_c <= 0.0:
            self.temp_label.hide()
            return
        self.temp_label.show()
        temp_c = self.current_temp_c
        color = "#10b981" if temp_c < 55.0 else ("#f59e0b" if temp_c < 70.0 else "#f43f5e")
        if self.temp_unit == "F":
            temp_f = temp_c * 9.0 / 5.0 + 32.0
            self.temp_label.setText(f"{temp_f:.1f} °F")
        else:
            self.temp_label.setText(f"{temp_c:.1f} °C")

        self.temp_label.setStyleSheet(f"""
            background-color: #21262d;
            color: {color};
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            padding: 1px 5px;
            border-radius: 3px;
            border: 1px solid #30363d;
        """)

    # USB 3 ports supply up to 0.9 A; warn a little before that
    USB_CURRENT_WARN_A = 0.8
    # Below this, nothing is connected to the analyzer's power port
    POWER_PORT_MIN_V = 3.0

    @classmethod
    def describe_power(cls, p: dict, interface: str = "USB Direct"):
        """(summary lines, warning or None) for a power reading. USB analyzers
        report the power port and the USB port separately; network analyzers
        (e.g. model 0x43) report their DC input in the second pair of fields."""
        port_w, usb_w = p["port_v"] * p["port_a"], p["usb_v"] * p["usb_a"]
        if interface.lower().startswith("network"):
            v, a = (p["port_v"], p["port_a"]) if p["port_v"] >= cls.POWER_PORT_MIN_V else (p["usb_v"], p["usb_a"])
            return [f"DC input: {v:.2f} V  {a:.2f} A  ({v * a:.1f} W)"], None
        lines = [f"Power port: {p['port_v']:.2f} V  {p['port_a']:.2f} A  ({port_w:.1f} W)",
                 f"USB port: {p['usb_v']:.2f} V  {p['usb_a']:.2f} A  ({usb_w:.1f} W)"]
        warning = None
        if p["port_v"] < cls.POWER_PORT_MIN_V:
            warning = ("Running on USB bus power. Connect the analyzer's power supply for "
                       "high-rate RTA/IQ streaming; bus power can drop the analyzer off USB.")
        elif p["usb_a"] >= cls.USB_CURRENT_WARN_A:
            warning = f"USB port current {p['usb_a']:.2f} A is near the 0.9 A limit of a USB 3 port."
        return lines, warning

    def set_power_state(self, p: dict, interface: str = "USB Direct"):
        self.power_state = p
        self.power_interface = interface
        lines, warning = self.describe_power(p, interface)
        total_w = p["port_v"] * p["port_a"] + p["usb_v"] * p["usb_a"]
        bus_powered = p["port_v"] < self.POWER_PORT_MIN_V and not interface.lower().startswith("network")
        self.power_label.setText(f"{'USB ' if bus_powered else ''}{total_w:.1f} W")
        self.power_label.setToolTip("Analyzer supply\n" + "\n".join(lines) + (f"\n\n⚠ {warning}" if warning else ""))
        color = "#f59e0b" if warning else "#8b949e"
        self.power_label.setStyleSheet(f"""
            background-color: #21262d;
            color: {color};
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            font-weight: 700;
            padding: 1px 5px;
            border-radius: 3px;
            border: 1px solid #30363d;
        """)
        self.power_label.show()

    def set_input_chain_state(self, lines: dict):
        """lines: {analyzer label: 'chain name: correction summary'} for analyzers with a chain."""
        if lines:
            self.cal_btn.setText("Calibration ● ▾")
            self.cal_btn.setStyleSheet("QPushButton { color: #38bdf8; border: 1px solid #38bdf8; }")
            self.cal_btn.setToolTip("Input chain correction applied to levels:\n"
                                    + "\n".join(f"{k}: {v}" for k, v in lines.items()))
        else:
            self.cal_btn.setText("Calibration ▾")
            self.cal_btn.setStyleSheet("")
            self.cal_btn.setToolTip("Calibration files and input chains (antenna / cable / amplifier). "
                                    "No input chain is applied: levels are at the analyzer's input.")

    def flash_status(self, text: str, ms: int = 4000):
        """Show a transient notice in the device label, then restore the analyzer name."""
        self.dev_label.setText(text)
        self._notice_timer.start(ms)

    # Trace toggles shorten their labels only when the bar runs out of room
    TRACE_SHORT = {"Real-Time": "Live", "Max. Hold": "Max", "Min. Hold": "Min", "Average": "Avg"}

    def _fit(self):
        for name, btn in self.trace_buttons.items():
            btn.setText(name)
        self.layout().activate()
        if self.layout().sizeHint().width() > self.width():
            for name, btn in self.trace_buttons.items():
                btn.setText(self.TRACE_SHORT[name])
                btn.setToolTip(name)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._fit()

    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #30363d; margin: 4px 2px;")
        layout.addWidget(sep)

    def set_multi_device_state(self, topology: str, slots: dict):
        self.current_topology = topology
        self.focus_combo.blockSignals(True)
        self.focus_combo.clear()
        
        if topology == MultiDeviceTopology.SPLIT_SWEEP:
            self.topo_badge.setText("SPLIT 2X")
            self.topo_badge.show()
            self.multi_ctrl_frame.hide()
        elif topology == MultiDeviceTopology.DIVERSITY:
            self.topo_badge.setText("DIVERSITY")
            self.topo_badge.show()
            self.focus_combo.addItems(["A+B Overlay", "Antenna A", "Antenna B", "Delta (A-B)"])
            self.multi_ctrl_frame.show()
        elif topology in (MultiDeviceTopology.INDEPENDENT, MultiDeviceTopology.SENSOR_NET):
            n = sum(1 for s in slots.values() if s.get("enabled"))
            self.topo_badge.setText("MULTI-ZONE" if topology == MultiDeviceTopology.INDEPENDENT else f"SENSORS {n}")
            self.topo_badge.show()
            for slot_id in sorted(slots):
                if topology == MultiDeviceTopology.SENSOR_NET and not slots[slot_id].get("enabled"):
                    continue
                raw = slots[slot_id].get("alias", "")
                alias = raw.strip() if (raw and raw.strip()) else f"Analyzer {slot_id.split('_')[-1].upper()}"
                self.focus_combo.addItem(f"Focus: {alias}", slot_id)
            self.multi_ctrl_frame.show()
        else:
            self.topo_badge.hide()
            self.multi_ctrl_frame.hide()
            
        self.focus_combo.blockSignals(False)

    def _on_focus_combo_changed(self, text: str):
        if self.current_topology == MultiDeviceTopology.DIVERSITY:
            mode_map = {
                "A+B Overlay": "both",
                "Antenna A": "slot_a",
                "Antenna B": "slot_b",
                "Delta (A-B)": "delta"
            }
            self.diversityModeChanged.emit(mode_map.get(text, "both"))
        elif self.current_topology == MultiDeviceTopology.INDEPENDENT:
            data = self.focus_combo.currentData()
            if data:
                self.multiDeviceFocusChanged.emit(data)

    def set_interface_badge(self, interface_type: str, ip: str = None):
        if interface_type and interface_type.lower() == "network":
            self.interface_btn.setText("Net")
            self.interface_btn.setToolTip(f"Network Connection (IP: {ip or 'Not configured'})")
        else:
            self.interface_btn.setText("USB")
            self.interface_btn.setToolTip("USB Direct Connection")

    def set_device_status(self, connected: bool, text: str):
        if not connected:
            self.power_state = None
            self.power_label.hide()
        self._identity_text = text
        self._notice_timer.stop()
        if connected:
            self.status_dot.setStyleSheet("color: #10b981; font-size: 12px;")
            self.dev_label.setText(text)
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setStyleSheet("""
                background-color: #da3633;
                color: #ffffff;
                border: 1px solid #f85149;
                font-size: 11px;
                font-weight: 600;
                padding: 1px 8px;
                border-radius: 3px;
            """)
            self.play_pause_btn.setEnabled(True)
        else:
            self.status_dot.setStyleSheet("color: #f43f5e; font-size: 12px;")
            self.dev_label.setText(text)
            self.connect_btn.setText("Connect")
            self.connect_btn.setStyleSheet("""
                background-color: #0969da;
                color: #ffffff;
                border: 1px solid #218bff;
                font-size: 11px;
                font-weight: 600;
                padding: 1px 8px;
                border-radius: 3px;
            """)
            self.play_pause_btn.setEnabled(True)
            self.set_sweeping_state(False)

    def set_sweeping_state(self, sweeping: bool):
        self.play_pause_btn.setChecked(sweeping)
        if sweeping:
            self.play_pause_btn.setText("Pause")
            self.play_pause_btn.setIcon(get_pause_icon("#ffffff", 16))
            self.play_pause_btn.setObjectName("primaryActionBtn")
        else:
            self.play_pause_btn.setText("Sweep")
            self.play_pause_btn.setIcon(get_play_icon("#ffffff", 16))
            self.play_pause_btn.setObjectName("successBtn")
        self.play_pause_btn.setStyle(self.play_pause_btn.style())

    def _on_play_pause_clicked(self, checked: bool):
        self.set_sweeping_state(checked)
        self.playPauseToggled.emit(checked)

    def update_fps(self, fps: float):
        self.fps_label.setText(f"{fps:.1f} FPS")

    def set_intruders_banner(self, count: int, current_idx: int = 0, current_freq: float = None):
        if count > 0:
            self.intruder_frame.show()
            if current_freq is not None:
                self.intr_label.setText(f"Threat {current_idx + 1}/{count}: {current_freq:.2f} MHz")
            else:
                self.intr_label.setText(f"Threats ({count})")
        else:
            self.intruder_frame.hide()

    def set_regions(self, regions: list, current_region: str):
        self.region_combo.blockSignals(True)
        self.region_combo.clear()
        self.region_combo.addItems(regions)
        idx = self.region_combo.findText(current_region)
        if idx >= 0:
            self.region_combo.setCurrentIndex(idx)
        self.region_combo.blockSignals(False)

    def set_trace_active(self, name: str, active: bool):
        if name in self.trace_buttons:
            self.trace_buttons[name].setChecked(active)

    def set_hw_endorsements(self, data: dict):
        self.hw_endorsements = data

    def set_audio_available(self, available: bool, reason: str = ""):
        """Grey out Listen when the analyzer has no IQ stream to demodulate."""
        self.audio_btn.setEnabled(available)
        self.audio_btn.setToolTip("Live Analog AM/FM Audio Demodulation & Acoustic Monitor" if available else reason)

    def _on_dev_chip_clicked(self, event):
        child = self.dev_chip.childAt(event.pos())
        if child not in (self.interface_btn, self.connect_btn, self.temp_label):
            self._show_endorsements_menu()

    def _show_endorsements_menu(self):
        menu = QMenu(self)
        menu.setObjectName("endorsementsMenu")
        menu.setStyleSheet("""
            QMenu#endorsementsMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 4px;
                color: #e6edf3;
            }
            QMenu#endorsementsMenu::item {
                padding: 5px 14px;
                border-radius: 4px;
                font-size: 11px;
                background-color: transparent;
            }
            QMenu#endorsementsMenu::item:disabled {
                color: #8b949e;
            }
            QMenu#endorsementsMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QMenu#endorsementsMenu::separator {
                height: 1px;
                background-color: #30363d;
                margin: 4px 8px;
            }
        """)

        if not self.hw_endorsements:
            hdr = menu.addAction("HAROGIC SPECTRUM ANALYZER")
            hdr.setEnabled(False)
            menu.addSeparator()
            no_conn = menu.addAction("No Hardware Telemetry Available")
            no_conn.setEnabled(False)
            hint = menu.addAction("Connect an analyzer to inspect on-board licenses.")
            hint.setEnabled(False)
            menu.exec(self.dev_chip.mapToGlobal(self.dev_chip.rect().bottomLeft()))
            return

        model = self.hw_endorsements.get('model', 'Unknown')
        hw_ver = self.hw_endorsements.get('hw_ver', '')
        uid = self.hw_endorsements.get('uid', 'Unknown')
        full_uid = self.hw_endorsements.get('full_uid', uid)
        mfw = self.hw_endorsements.get('mfw_ver', 'Unknown')
        ffw = self.hw_endorsements.get('ffw_ver', 'Unknown')
        interface = self.hw_endorsements.get('interface', 'USB Direct')
        
        # 1. Device Header (analyzers other than Harogic ones supply their own title)
        title = self.hw_endorsements.get('title')
        hdr = menu.addAction(f"{title} (Hardware Rev {hw_ver})" if title else f"HAROGIC MODEL {model} (Hardware Rev {hw_ver})")
        hdr.setEnabled(False)
        uid_act = menu.addAction(f"Serial UID: 0x{uid}")
        uid_act.setEnabled(False)
        if_act = menu.addAction(f"Interface: {interface}")
        if_act.setEnabled(False)
        if self.power_state:
            lines, warning = self.describe_power(self.power_state, getattr(self, "power_interface", "USB Direct"))
            for line in lines + ([f"⚠ {warning}"] if warning else []):
                menu.addAction(line).setEnabled(False)
        
        menu.addSeparator()

        # 2. Licenses & Endorsements Section (licenses None: the analyzer has no license options)
        licenses = self.hw_endorsements.get('licenses', [])
        if licenses is not None:
            lic_hdr = menu.addAction("LICENSES && ENDORSEMENTS")
            lic_hdr.setEnabled(False)

        if licenses:
            sorted_licenses = sorted(licenses, key=lambda x: (not x.get('enabled', False), x.get('name', '')))
            for lic in sorted_licenses:
                name = lic.get('name', '')
                desc = lic.get('description', name).replace("&", "&&")
                is_enabled = lic.get('enabled', False)
                if is_enabled:
                    act = menu.addAction(f"[ACTIVE]  {desc}")
                else:
                    act = menu.addAction(f"[NOT LICENSED]  {desc}")
                act.setEnabled(False)
        elif licenses is not None:
            none_act = menu.addAction("No license options configured in baseband flash")
            none_act.setEnabled(False)

        if licenses is not None:
            menu.addSeparator()

        # 3. Hardware Features Section
        hw_features = self.hw_endorsements.get('hardware_features', [])
        if title:
            hw_hdr = menu.addAction("HARDWARE")
            hw_hdr.setEnabled(False)
            for feat in hw_features:
                menu.addAction(feat).setEnabled(False)
        else:
            hw_hdr = menu.addAction("HARDWARE MODULES && ARCHITECTURE")
            hw_hdr.setEnabled(False)
            if hw_features:
                for feat in hw_features:
                    act = menu.addAction(f"[INSTALLED]  {feat}")
                    act.setEnabled(False)
            else:
                act = menu.addAction("Standard Front-End Architecture")
                act.setEnabled(False)

        menu.addSeparator()

        # 4. Telemetry Details
        firmware = self.hw_endorsements.get('firmware')
        fw_act = menu.addAction(f"Firmware: {firmware}" if firmware else f"Firmware: MCU {mfw} / FPGA {ffw}")
        fw_act.setEnabled(False)
        if full_uid and full_uid != uid:
            full_act = menu.addAction(f"Full Hardware ID: {full_uid}")
            full_act.setEnabled(False)
        menu.popup(self.dev_chip.mapToGlobal(self.dev_chip.rect().bottomLeft()))
        self._active_endorsements_menu = menu

    def _show_temp_fan_menu(self):
        menu = QMenu(self)
        menu.setObjectName("tempFanMenu")
        menu.setStyleSheet("""
            QMenu#tempFanMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 4px;
                color: #e6edf3;
            }
            QMenu#tempFanMenu::item {
                padding: 5px 14px;
                border-radius: 4px;
                font-size: 11px;
                background-color: transparent;
            }
            QMenu#tempFanMenu::item:disabled {
                color: #8b949e;
            }
            QMenu#tempFanMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QMenu#tempFanMenu::separator {
                height: 1px;
                background-color: #30363d;
                margin: 4px 8px;
            }
        """)

        # 1. Header: Current Live Readings
        if self.current_temp_c is not None and self.current_temp_c > 0.0:
            tc = self.current_temp_c
            tf = tc * 9.0 / 5.0 + 32.0
            hdr = menu.addAction(f"HARDWARE TEMPERATURE: {tc:.1f} °C / {tf:.1f} °F")
        else:
            hdr = menu.addAction("HARDWARE TEMPERATURE & FAN CONTROL")
        hdr.setEnabled(False)

        menu.addSeparator()

        # 2. Temperature Unit Selection
        unit_hdr = menu.addAction("TEMPERATURE DISPLAY UNIT")
        unit_hdr.setEnabled(False)

        act_c = menu.addAction("Celsius (°C)")
        act_c.setCheckable(True)
        act_c.setChecked(self.temp_unit == "C")
        def select_c():
            self.temp_unit = "C"
            self._update_temp_display()
        act_c.triggered.connect(select_c)

        act_f = menu.addAction("Fahrenheit (°F)")
        act_f.setCheckable(True)
        act_f.setChecked(self.temp_unit == "F")
        def select_f():
            self.temp_unit = "F"
            self._update_temp_display()
        act_f.triggered.connect(select_f)

        menu.addSeparator()

        # 3. Fan Speed Control
        fan_hdr = menu.addAction("HARDWARE FAN SPEED")
        fan_hdr.setEnabled(False)

        # Mode 1: Auto (Threshold 50.0°C)
        act_auto = menu.addAction("Automatic (Temp Threshold 50°C)")
        act_auto.setCheckable(True)
        act_auto.setChecked(self.current_fan_state == 2)
        def select_auto():
            self.current_fan_state = 2
            self.fanStateRequested.emit(2, 50.0)
        act_auto.triggered.connect(select_auto)

        # Mode 2: Forced On (Max Cooling)
        act_on = menu.addAction("Forced On (Maximum Cooling)")
        act_on.setCheckable(True)
        act_on.setChecked(self.current_fan_state == 0)
        def select_on():
            self.current_fan_state = 0
            self.fanStateRequested.emit(0, 50.0)
        act_on.triggered.connect(select_on)

        # Mode 3: Forced Off (Silent Mode)
        act_off = menu.addAction("Forced Off (Silent / No Fan Noise)")
        act_off.setCheckable(True)
        act_off.setChecked(self.current_fan_state == 1)
        def select_off():
            self.current_fan_state = 1
            self.fanStateRequested.emit(1, 50.0)
        act_off.triggered.connect(select_off)

        menu.popup(self.temp_label.mapToGlobal(self.temp_label.rect().bottomLeft()))
        self._active_temp_fan_menu = menu
