"""
top_bar.py - Unified Top Transport, Hardware Telemetry & Multi-Device Control Bar.
Provides real-time device connection chips, multi-device topology selectors,
master sweep play/pause controls, live threat banners, trace pills, and regional preset switchers.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox, QFrame, QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from ..icons import get_play_icon, get_pause_icon, get_settings_icon, get_chevron_icon
from .trace_controls import SimpleColorPicker
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
        
        self.dev_label = QLabel("Disconnected")
        self.dev_label.setStyleSheet("font-weight: 600; font-size: 11px; color: #8b949e;")
        self.dev_label.setMinimumWidth(140)
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
        
        # 7. Region Switcher
        self.region_combo = QComboBox()
        self.region_combo.setObjectName("regionCombo")
        self.region_combo.setMaximumWidth(120)
        self.region_combo.currentTextChanged.connect(self.regionChanged.emit)
        main_layout.addWidget(self.region_combo)
        
        # 8. Settings, Audio & Cal Buttons
        self.audio_btn = QPushButton("Listen")
        self.audio_btn.setObjectName("pillBtn")
        self.audio_btn.setFixedHeight(24)
        self.audio_btn.setToolTip("Live Analog AM/FM Audio Demodulation & Acoustic Monitor")
        self.audio_btn.clicked.connect(self.audioDemodClicked.emit)
        main_layout.addWidget(self.audio_btn)
        
        self.cal_btn = QPushButton("Calibration")
        self.cal_btn.setFixedHeight(24)
        self.cal_btn.clicked.connect(self.calManagerClicked.emit)
        main_layout.addWidget(self.cal_btn)
        
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
        elif topology == MultiDeviceTopology.INDEPENDENT:
            self.topo_badge.setText("MULTI-ZONE")
            self.topo_badge.show()
            raw_a = slots.get("slot_a", {}).get("alias", "")
            raw_b = slots.get("slot_b", {}).get("alias", "")
            alias_a = raw_a.strip() if (raw_a and raw_a.strip()) else "Analyzer A"
            alias_b = raw_b.strip() if (raw_b and raw_b.strip()) else "Analyzer B"
            self.focus_combo.addItem(f"Focus: {alias_a}", "slot_a")
            self.focus_combo.addItem(f"Focus: {alias_b}", "slot_b")
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
                self.intr_label.setText(f"Intruders Detected ({count})")
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
        
        # 1. Device Header
        hdr = menu.addAction(f"HAROGIC MODEL {model} (Hardware Rev {hw_ver})")
        hdr.setEnabled(False)
        uid_act = menu.addAction(f"Serial UID: 0x{uid}")
        uid_act.setEnabled(False)
        
        menu.addSeparator()
        
        # 2. Licenses & Endorsements Section
        lic_hdr = menu.addAction("LICENSES && ENDORSEMENTS")
        lic_hdr.setEnabled(False)
        
        licenses = self.hw_endorsements.get('licenses', [])
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
        else:
            none_act = menu.addAction("No license options configured in baseband flash")
            none_act.setEnabled(False)
            
        menu.addSeparator()
        
        # 3. Hardware Features Section
        hw_hdr = menu.addAction("HARDWARE MODULES && ARCHITECTURE")
        hw_hdr.setEnabled(False)
        
        hw_features = self.hw_endorsements.get('hardware_features', [])
        if hw_features:
            for feat in hw_features:
                act = menu.addAction(f"[INSTALLED]  {feat}")
                act.setEnabled(False)
        else:
            act = menu.addAction("Standard Front-End Architecture")
            act.setEnabled(False)
            
        menu.addSeparator()
        
        # 4. Telemetry Details
        fw_act = menu.addAction(f"Firmware: MCU {mfw} / FPGA {ffw}")
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
