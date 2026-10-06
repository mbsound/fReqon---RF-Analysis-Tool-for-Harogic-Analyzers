"""
main_window.py - Master Application Window for RF Recon Modern (Freqon).
Coordinates the Top Transport Bar, Left Workflow Navigation Hub, Central Dual-Canvas
Spectrogram & Spectrum Viewports, RF Hardware Engine, and Specialized Telemetry Subsystems.
"""

import os
import math
import json
import time
import numpy as np
import scipy.signal as signal
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStackedWidget, QFileDialog, QMessageBox, QTableWidgetItem,
    QTreeWidgetItem
)
import threading
from datetime import datetime
from PyQt6.QtCore import Qt, QTimer, QSettings, QStandardPaths, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices

from core.constants import (
    TV_CHANNEL_STANDARDS, DEFAULT_REGIONS, DEFAULT_NORTH_AMERICA_ACTIVE,
    DEFAULT_EUROPE_ACTIVE
)
from core import device_caps
from core.device_controller import IQ_FALLBACK_BASE_RATE_HZ
from core.multi_device_manager import MultiDeviceManager, MultiDeviceTopology
from core.calibration_manager import CalibrationManager
from core.fcc_database import FCCDatabaseManager
from core.dtv_detect import DTVOccupancyDetector
from core.tband_scan import TBandScanner
from core.propagation import worth_masking
from core.ofcom_database import OfcomDatabaseManager
from core.dect_analyzer import DECTAnalyzerEngine, DECT_BANDS, TDMATimeslotDialog
from core.showlink_crmx_analyzer import ShowLinkCRMXEngine, ShowlinkMapDialog
from core import band24
from core import emission_mask
from core import tdoa
from core.geolocate import latlon_from_enu
from core.iberia_tv import SpainTDTPlan, PortugalTDT
from core.carrier_fingerprint import CarrierFingerprinter, WIDE_BLOCK_KHZ
from core.intermod import Transmitter, IntermodMap, analyzer_or_real, estimate_level
from core.input_chain import InputChainStore
from core.sensor_net import SensorNet

from .widgets.top_bar import TopBar
from .widgets.nav_rail import NavRail
from .widgets.spectrum_view import SpectrumView
from .widgets.waterfall_view import WaterfallView
from .widgets.multi_row_waterfall import MultiRowWaterfallView
from .widgets.rtsa_view import RTSAView
from .widgets.map_view import MapView
from .widgets.panels.locate_panel import LocatePanel
from .widgets.det_view import DETView
from .widgets.demod_view import DemodView
from .widgets.panels.sweep_panel import SweepPanel
from .widgets.panels.rtsa_panel import RTSAPanel
from .widgets.panels.det_panel import DETPanel
from .widgets.panels.demod_panel import DemodPanel
from .widgets.panels.dtv_panel import DTVPanel
from .widgets.panels.dect_panel import DECTPanel
from .widgets.panels.showlink_panel import ShowLinkPanel
from .widgets.panels.threats_panel import ThreatsPanel, NumericTableWidgetItem
from .widgets.panels.mscan_panel import MSCANPanel
from .widgets.mscan_view import MSCANView
from core.demod_engine import DemodEngine
from core.soundbase_parser import SoundbaseParser
from core.wwb_parser import WWBParser

from .dialogs.cal_dialogs import CalibrationManagerDialog, MissingCalDialog
from .dialogs.connection_dialog import ConnectionDialog
from .dialogs.input_chain_dialog import InputChainDialog
from .dialogs.audio_demod_dialog import AudioDemodDialog
from .dialogs.settings_dialogs import (
    QuickSettingsDialog, LaunchSettingsDialog
)

# Ofcom's DTT transmitter details page (spreadsheet download)
OFCOM_TRANSMITTER_PAGE = "https://www.ofcom.org.uk/tv-radio-and-on-demand/coverage-and-transmitters/transmitter-frequency"

# Intruders not seen for this long are shown greyed out (they are kept until cleared)
INTRUDER_STALE_S = 10.0
RENDER_PERIOD_S = 1 / 30        # traces and waterfall are drawn at most this often
FP_MEASURE_PERIOD_S = 0.1       # carrier fingerprint measurements per sweep, at most this often

class MainWindow(QMainWindow):
    """
    Main Application Window orchestrating the entire RF coordination workspace.
    """
    # Station lookups run on a worker thread and report back through this signal
    stationLookupFinished = pyqtSignal(object, object)  # stations, source info

    def __init__(self):
        super().__init__()
        self._initializing = True
        self.setWindowTitle("Freqon - RF Reconnaissance Workstation")
        self.resize(1600, 950)
        self.setMinimumSize(960, 600)
        
        # 1. Settings & Persistence
        self.settings = QSettings("Harogic", "RF_Recon_Modern")
        self._load_settings()
        
        # 2. Engines & Hardware Controllers
        self.cal_manager = CalibrationManager()
        self.fcc_db = FCCDatabaseManager()
        self.ofcom_db = OfcomDatabaseManager()
        self.spain_tv = SpainTDTPlan()
        self.portugal_tv = PortugalTDT()
        # Carrier fingerprinting (see core/carrier_fingerprint.py)
        self.fingerprinter = CarrierFingerprinter()
        self._fp_last_refresh = 0.0
        self._fp_pass = None            # active MSCAN fingerprint pass on the focused analyzer
        self._fp_background = False     # Analyzer B fingerprinting continuously
        self._fp_bg_channels = ()
        self._rbw_by_slot = {}
        self._bw_by_slot = {}               # slot -> (RBW, VBW) the analyzer last reported
        self._holds_restart_pending = False
        self._last_detect = None
        # Intermodulation analysis (see core/intermod.py)
        self.coord_carriers = []        # coordinated carriers with zone and spare flag
        self._im_map = None
        self._im_source_key = None
        self._last_sweep = None         # (freq_hz, power_dbm) of the latest sweep
        self._im_verify = None          # attenuation test in progress
        
        self.dect_engine = DECTAnalyzerEngine(self)
        self.dect_engine.analysis_updated.connect(self._on_dect_analysis_updated)
        
        self.showlink_engine = ShowLinkCRMXEngine(self)
        self.showlink_engine.analysis_updated.connect(self._on_showlink_analysis_updated)
        
        self.multi_device_manager = MultiDeviceManager(self)
        self.multi_device_manager.composite_sweep_ready.connect(self._on_sweep_data)
        self.multi_device_manager.diversity_sweep_ready.connect(self._on_diversity_sweep_data)
        self.multi_device_manager.device_sweep_ready.connect(self._on_device_sweep_data)
        self.multi_device_manager.rta_data_ready.connect(self._on_rta_data)
        self.multi_device_manager.det_data_ready.connect(self._on_det_data)
        self.multi_device_manager.iqs_data_ready.connect(self._on_iqs_data)
        self.multi_device_manager.temperature_updated.connect(self._on_temperature_updated)
        self.multi_device_manager.power_updated.connect(self._on_power_updated)
        self.multi_device_manager.input_comp_applied.connect(self._on_input_comp_applied)
        # Sensor network (Locate mode): every slot's sweep and GNSS state
        self.sensor_net = SensorNet()
        self._locate_selected_hz = None
        self.multi_device_manager.gnss_updated.connect(self._on_gnss_updated)
        self.multi_device_manager.timed_capture_ready.connect(self._on_timed_capture)
        self._tdoa = None                   # a time-difference location run in progress (start_tdoa)
        self._locate_status_hold = 0.0
        self.multi_device_manager.slots_changed.connect(self._sync_sensors)
        self._locate_timer = QTimer(self)
        self._locate_timer.timeout.connect(self._refresh_locate)
        self._locate_timer.start(1000)
        self.input_chains = InputChainStore(self.settings)
        self.multi_device_manager.focus_changed.connect(self._refresh_top_bar_hardware)
        self.multi_device_manager.focus_changed.connect(self._apply_capabilities)
        self.multi_device_manager.capabilities_changed.connect(self._apply_capabilities)
        self.multi_device_manager.sweep_plan_changed.connect(self._on_sweep_plan)
        self._input_summary = None      # last "which RF input is in use" shown
        # Per-analyzer RF settings (amplitude, bandwidth, sweep, RF input)
        self._settings_slot = None      # slot the sweep panel edits; None: every analyzer
        self._slot_settings = {}        # slot id -> the settings last applied to its analyzer
        self._slots_synced = set()      # connected slots whose remembered settings have been sent
        self.demod_engine = DemodEngine()
        # Undecimated IQ rate, learned from the analyzer's IQ packets (SAN-60: 125 MS/s)
        self._iq_base_rate_hz = IQ_FALLBACK_BASE_RATE_HZ
        self._last_demod_render_time = 0.0
        self.multi_device_manager.slot_status_changed.connect(self._on_slot_status_changed)
        self.multi_device_manager.slot_info_received.connect(self._on_slot_info_received)
        self.multi_device_manager.all_connection_status.connect(self._on_all_connection_status)
        self.multi_device_manager.status_message.connect(self._on_device_status)
        self.multi_device_manager.amplitude_clamped.connect(self._on_amplitude_clamped)
        self.multi_device_manager.bandwidth_updated.connect(self._on_bandwidth_updated)
        self.multi_device_manager.hw_endorsements.connect(self._on_hw_endorsements)
        
        # 3. State Buffers
        self.is_connected = False
        self.is_sweeping = False
        self.current_model = None
        self.current_uid = None
        self.target_device_model = None
        self.target_device_uid = None
        self._x_multiplier = 1e6 # MHz
        self._updating_freqs = False
        self._updating_view_freqs = False
        self._last_operating_mode = "SWP"
        
        self.max_hold_data = None
        self.min_hold_data = None
        self.avg_history = []
        self.last_freq = None
        self.last_power = None
        self.audio_demod_dialog = None
        self._pre_audio_mode = "SWP"
        # Ring buffer: row _wf_head is the newest sweep; _waterfall_ordered()
        # gives it newest-first for display
        self.waterfall_buffer = np.full((self.waterfall_history_depth, 1000), -130.0, dtype=np.float32)
        self._wf_head = 0
        self._last_render_time = 0.0
        self._fp_last_measure = 0.0
        self._mscan_telemetry_time = 0.0
        self._mask_cache = (0.0, [])       # (time, masked ranges) for intruder detection
        self._last_div_render_time = 0.0
        
        self.intruders = {} # freq -> {power, signature, ...}
        self.current_intruder_index = -1
        self._last_intruder_ui_update = 0.0
        self.dtv_detect_active = False
        self.tband_detect_active = False
        # Broadcast / DTV: looked-up transmitters, what is measured, and the masks
        self.dtv_detector = DTVOccupancyDetector()
        self.dtv_stations = {}             # TV channel -> transmitters from the last lookup
        self.lmr_stations = {}             # TV channel -> public-safety LMR (T-Band) entries: drawn red
        self.station_info = {}             # channel -> what is written on its mask
        self._dtv_results = {}             # channel -> latest detector result
        self._dtv_override = {}            # channel -> mask pinned by hand (automatic processes leave it alone)
        self._dtv_table_mode = None        # "lookup": looked-up transmitters; "scanned": swept channels
        self._dtv_scanned_key = None
        self._dtv_last_run = 0.0
        self._dtv_last_status_time = 0.0
        self._dtv_auto_floor = None        # noise floor (dBm) behind the automatic threshold line
        self._dtv_line_timer = QTimer(self)    # keeps that line on the current sweep
        self._dtv_line_timer.timeout.connect(self._sync_dtv_threshold_line)
        self._tv_channel_cache = (None, [])
        self.tband_scanner = TBandScanner()
        self._tband_results = {}           # T-Band channel -> what the scan finds there
        self._tband_lmr = set()            # channels the scan found land mobile radio in (masked red)
        self._tband_auto_on = set()        # masks the scan itself switched on (switched off again when released)
        self._tband_last_run = 0.0
        self.active_channels = {}
        self.coordination_ps_channels = set()
        self.marker_items = {}
        
        # Performance Tracking
        self.frame_count = 0
        self.total_frames = 0
        self.last_fps_time = time.time()
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self._update_fps_calc)
        self.fps_timer.start(500)
        
        # 4. Build UI Layout
        self._build_ui()
        self._setup_connections()
        self._init_state()
        self._initializing = False

    def _load_settings(self):
        try:
            self.region_configs = json.loads(self.settings.value("regions", json.dumps(DEFAULT_REGIONS)))
            for reg_k, reg_v in DEFAULT_REGIONS.items():
                if reg_k not in self.region_configs:
                    self.region_configs[reg_k] = reg_v
        except Exception:
            self.region_configs = DEFAULT_REGIONS.copy()
            
        self.current_region = self.settings.value(
            "launch_default_region", self.settings.value("current_region", "North America")
        )
        if self.current_region not in self.region_configs:
            self.current_region = list(self.region_configs.keys())[0]
            
        self.waterfall_history_depth = int(self.settings.value("waterfall_depth", 120))
        self.waterfall_colormap = self.settings.value("waterfall_colormap", "viridis")
        self.marker_opacity = float(self.settings.value("marker_opacity", 0.85))
        self.show_channel_labels = self.settings.value("show_channel_labels", True, type=bool)
        
        self.connection_interface = self.settings.value("connection_interface", "usb")
        self.network_ip = self.settings.value("network_ip", "192.168.1.50")
        self.network_port = int(self.settings.value("network_port", 5000))
        try:
            self.ip_history = json.loads(self.settings.value("ip_history", '["192.168.1.50"]'))
        except Exception:
            self.ip_history = ["192.168.1.50"]

    def _build_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top Bar
        self.top_bar = TopBar(self)
        self.top_bar.set_regions(list(self.region_configs.keys()), self.current_region)
        main_layout.addWidget(self.top_bar)
        
        # Horizontal Splitter (Left Drawer + Central Dual-Canvas)
        self.main_h_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_h_splitter.setHandleWidth(2)
        main_layout.addWidget(self.main_h_splitter, 1)
        
        # --- LEFT WORKFLOW HUB ---
        self.left_hub = QWidget()
        left_hub_layout = QHBoxLayout(self.left_hub)
        left_hub_layout.setContentsMargins(0, 0, 0, 0)
        left_hub_layout.setSpacing(0)
        
        self.nav_rail = NavRail(self.left_hub)
        left_hub_layout.addWidget(self.nav_rail)
        
        self.panel_stack = QStackedWidget(self.left_hub)
        # The mode rail has a fixed width; whatever the splitter gives the hub beyond that
        # goes to the module panel (its tables need the room), so there is no upper limit
        self.panel_stack.setMinimumWidth(280)
        
        self.sweep_panel = SweepPanel(self.panel_stack)
        self.rtsa_panel = RTSAPanel(self.panel_stack)
        self.det_panel = DETPanel(self.panel_stack)
        self.demod_panel = DemodPanel(self.panel_stack)
        self.dtv_panel = DTVPanel(self.panel_stack)
        self.dect_panel = DECTPanel(self.panel_stack)
        self.showlink_panel = ShowLinkPanel(self.panel_stack)
        self.threats_panel = ThreatsPanel(self.panel_stack)
        self.mscan_panel = MSCANPanel(self.panel_stack)
        
        self.panel_stack.addWidget(self.sweep_panel)
        self.panel_stack.addWidget(self.threats_panel)
        self.panel_stack.addWidget(self.mscan_panel)
        self.panel_stack.addWidget(self.rtsa_panel)
        self.panel_stack.addWidget(self.det_panel)
        self.panel_stack.addWidget(self.demod_panel)
        self.panel_stack.addWidget(self.dtv_panel)
        self.panel_stack.addWidget(self.dect_panel)
        self.panel_stack.addWidget(self.showlink_panel)
        self.locate_panel = LocatePanel()
        self.panel_stack.addWidget(self.locate_panel)
        
        left_hub_layout.addWidget(self.panel_stack, 1)
        self.main_h_splitter.addWidget(self.left_hub)
        
        # --- CENTRAL VIEWPORTS ---
        self.viewport_container = QWidget()
        viewport_layout = QVBoxLayout(self.viewport_container)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setSpacing(0)
        
        self.viewport_stack = QStackedWidget(self.viewport_container)
        
        # Viewport Page 0: Standard Dual View (Splitter with Waterfall + Spectrum)
        self.dual_view_widget = QWidget()
        dual_layout = QVBoxLayout(self.dual_view_widget)
        dual_layout.setContentsMargins(4, 4, 4, 4)
        dual_layout.setSpacing(0)
        
        self.view_v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.view_v_splitter.setHandleWidth(2)
        
        self.waterfall_view = WaterfallView(self.view_v_splitter)
        self.waterfall_view.set_colormap(self.waterfall_colormap)
        self.waterfall_view.set_history_depth(self.waterfall_history_depth)
        
        self.spectrum_view = SpectrumView(self.view_v_splitter)
        
        # Cross-Link Axes
        self.waterfall_view.waterfall_widget.setXLink(self.spectrum_view.plot_widget)
        self.waterfall_view.channel_bar.setXLink(self.spectrum_view.plot_widget)
        self.spectrum_view.channel_bar.setXLink(self.spectrum_view.plot_widget)
        
        self.view_v_splitter.addWidget(self.waterfall_view)
        self.view_v_splitter.addWidget(self.spectrum_view)

        # A second spectrum, for the other antenna in diversity (view mode "Dual Spectrum")
        self.spectrum_view_b = SpectrumView(self.view_v_splitter)
        self.spectrum_view_b.title_label.setText("ANTENNA B")
        self.spectrum_view_b.plot_widget.setXLink(self.spectrum_view.plot_widget)
        self.spectrum_view_b.channel_bar.setXLink(self.spectrum_view.plot_widget)
        self.spectrum_view_b.set_trace_visible("Trace B", True)
        self.spectrum_view.amplitude_follower = self.spectrum_view_b
        self.spectrum_view.mirror_masks_to(self.spectrum_view_b)
        self._last_div_b = None             # antenna B's latest sweep (Hz, dBm): its ETSI masks, intruders
        self._last_div_a = None             # and antenna A's, whatever the main view is showing
        self._zero_span_slot = None         # the analyzer a zero-span run put into zero span, if not the focused one
        self._reset_b_holds()
        self.view_v_splitter.addWidget(self.spectrum_view_b)
        self.spectrum_view_b.hide()
        self._dual_spectrum = False
        self._spectrum_title = self.spectrum_view.title_label.text()
        self.view_v_splitter.setSizes([340, 360, 0])
        dual_layout.addWidget(self.view_v_splitter)
        
        # Viewport Page 1: Multi-Row Folded Waterfall Viewport (Aaronia RTSA Mode)
        self.multi_row_view = MultiRowWaterfallView(self.viewport_stack)
        self.multi_row_view.set_colormap(self.waterfall_colormap)
        self.multi_row_view.set_history_depth(self.waterfall_history_depth)
        self.multi_row_view.set_sweep_range(self.sweep_panel.start_spin.value(), self.sweep_panel.stop_spin.value())
        
        # Viewport Page 2: Real-Time Spectrum Analysis Persistence Heatmap Viewport (RTSA)
        self.rtsa_view = RTSAView(self.viewport_stack)
        
        # Viewport Page 3: Zero-Span / Power vs. Time Oscilloscope Viewport (DET)
        self.det_view = DETView(self.viewport_stack)
        
        # Viewport Page 4: Demodulation Analysis Viewport (DemodView)
        self.demod_view = DemodView(self.viewport_stack)
        self.demod_view.waterfall_view.set_colormap(self.waterfall_colormap)
        self.demod_view.waterfall_view.set_history_depth(self.waterfall_history_depth)
        
        # Viewport Page 5: Hardware Discrete Channel Scanning Viewport (MSCAN)
        self.mscan_view = MSCANView(self.viewport_stack)
        
        self.viewport_stack.addWidget(self.dual_view_widget)
        self.viewport_stack.addWidget(self.multi_row_view)
        self.viewport_stack.addWidget(self.rtsa_view)
        self.viewport_stack.addWidget(self.det_view)
        self.viewport_stack.addWidget(self.demod_view)
        self.viewport_stack.addWidget(self.mscan_view)
        self.map_view = MapView()
        self.viewport_stack.addWidget(self.map_view)   # index 6
        
        viewport_layout.addWidget(self.viewport_stack)
        self.main_h_splitter.addWidget(self.viewport_container)
        
        # Set Splitter Stretch Factors (Left: 0, Center Viewport: 1)
        self.main_h_splitter.setSizes([self.HUB_DEFAULT_WIDTH, 880])
        self.main_h_splitter.setStretchFactor(0, 0)
        self.main_h_splitter.setStretchFactor(1, 1)
        self._restore_hub_width()

    def _setup_connections(self):
        # Top Bar
        self.top_bar.connectToggled.connect(self.toggle_connection)
        self.top_bar.connectionConfigClicked.connect(self.open_connection_manager)
        self.top_bar.audioDemodClicked.connect(self.open_audio_demod_dialog)
        self.top_bar.playPauseToggled.connect(self.toggle_sweep)
        self.top_bar.regionChanged.connect(self.change_region)
        self.top_bar.viewModeChanged.connect(self._on_view_mode_changed)
        self.top_bar.settingsClicked.connect(self.open_launch_settings)
        self.top_bar.calManagerClicked.connect(lambda: self.open_calibration_manager())
        self.top_bar.inputChainsClicked.connect(self.open_input_chains)
        self.locate_panel.sensorPositionEdited.connect(self._on_sensor_position_edited)
        self.locate_panel.settingsChanged.connect(self._on_locate_settings)
        self.locate_panel.carrierSelected.connect(self._on_locate_carrier_selected)
        self.locate_panel.tdoaRequested.connect(self.start_tdoa)
        self.map_view.carrierClicked.connect(self._on_locate_carrier_selected)
        self.locate_panel.openConnections.connect(self.open_connection_manager)
        self.locate_panel.restartAverages.connect(self._restart_position_averages)
        self._load_sensor_positions()
        self._restore_slots()
        self._sync_sensors()
        self._apply_input_chains()
        self.top_bar.traceToggled.connect(self._on_top_trace_toggled)
        self.top_bar.intruderPrevClicked.connect(self._on_intruder_prev)
        self.top_bar.intruderNextClicked.connect(self._on_intruder_next)
        self.top_bar.intruderBadgeClicked.connect(self._on_intruder_badge_clicked)
        self.top_bar.multiDeviceFocusChanged.connect(self._on_focus_slot_changed)
        self.top_bar.diversityModeChanged.connect(self._on_diversity_mode_changed)
        self.top_bar.fanStateRequested.connect(self._on_fan_state_requested)
        
        # Nav Rail
        self.nav_rail.modeChanged.connect(self._on_nav_mode_changed)
        self.nav_rail.collapseToggled.connect(self._on_nav_collapse)
        
        # RTSA Panel & View
        self.rtsa_panel.paramsChanged.connect(self._on_rtsa_params_changed)
        self.rtsa_panel.decay_slider.valueChanged.connect(lambda v: self.rtsa_view.set_persistence_decay(v / 100.0))
        
        # DET Panel & View
        self.det_panel.paramsChanged.connect(self._on_det_params_changed)
        self.det_panel.triggerRequested.connect(self._on_det_trigger_requested)
        self.det_panel.pauseRequested.connect(self._on_det_pause_requested)
        self.det_panel.presetSelected.connect(self.det_view.set_tdma_grid_standard)
        self.det_view.fitWindowRequested.connect(self._on_det_fit_window_requested)
        
        # Demod Panel & View
        self.demod_panel.paramsChanged.connect(self._on_demod_params_changed)
        self.demod_panel.demodRequested.connect(self._on_demod_requested)
        self.demod_panel.pauseRequested.connect(self._on_demod_pause_requested)
        self.demod_panel.tuneRequested.connect(self._on_demod_panel_tune_requested)
        self.demod_view.tuneDemodRequested.connect(self._on_demod_view_tune_requested)
        self.demod_view.waterfall_view.colormapChanged.connect(self._on_colormap_changed)
        self.demod_view.spectrum_view.mouseMoved.connect(self._on_demod_spectrum_mouse_moved)
        self.demod_view.waterfall_view.mouseMoved.connect(self._on_demod_waterfall_mouse_moved)
        self.demod_view.spectrum_view.triggerZeroSpanRequested.connect(self._on_spectrum_trigger_zero_span)
        self.demod_view.waterfall_view.triggerZeroSpanRequested.connect(self._on_spectrum_trigger_zero_span)
        self.demod_view.waterfall_view.channel_bar.channel_clicked.connect(self._on_channel_bar_clicked)
        self.demod_view.spectrum_view.channel_bar.channel_clicked.connect(self._on_channel_bar_clicked)
        
        # Viewports
        self.spectrum_view.mouseMoved.connect(self._on_spectrum_mouse_moved)
        self.waterfall_view.mouseMoved.connect(self._on_waterfall_mouse_moved)
        self.spectrum_view.triggerZeroSpanRequested.connect(self._on_spectrum_trigger_zero_span)
        self.waterfall_view.triggerZeroSpanRequested.connect(self._on_spectrum_trigger_zero_span)
        self.spectrum_view.rangeChanged.connect(self._on_view_range_changed)
        # Zooming or dragging a plot by hand, with the view linked: the analyzer follows
        self._link_follow_timer = QTimer(self)
        self._link_follow_timer.setSingleShot(True)
        self._link_follow_timer.setInterval(350)       # once the gesture has come to rest
        self._link_follow_timer.timeout.connect(self._sweep_follows_view)
        for plot in (self.spectrum_view.plot_widget, self.waterfall_view.waterfall_widget,
                     self.spectrum_view.channel_bar, self.waterfall_view.channel_bar,
                     self.spectrum_view_b.plot_widget, self.spectrum_view_b.channel_bar):
            plot.getViewBox().sigRangeChangedManually.connect(self._on_view_moved_by_hand)
        self.spectrum_view.thresholdChanged.connect(self._on_dtv_threshold_dragged)
        self.spectrum_view.intruderThresholdChanged.connect(self.threats_panel.intruder_thresh_spin.setValue)
        self.waterfall_view.colormapChanged.connect(self._on_colormap_changed)
        self.multi_row_view.colormapChanged.connect(self._on_colormap_changed)
        self.multi_row_view.rowModeChanged.connect(self._on_multi_row_mode_changed)
        self.multi_row_view.tuneFrequencyRequested.connect(self._on_multi_row_tune_requested)
        
        self.waterfall_view.channel_bar.channel_clicked.connect(self._on_channel_bar_clicked)
        self.spectrum_view.channel_bar.channel_clicked.connect(self._on_channel_bar_clicked)
        self.multi_row_view.channel_clicked.connect(self._on_channel_bar_clicked)
        self.rtsa_view.channel_bar.channel_clicked.connect(self._on_channel_bar_clicked)
        
        # Sweep Panel
        self.sweep_panel.frequenciesChanged.connect(self.apply_frequencies)
        self.sweep_panel.viewFrequenciesChanged.connect(self.apply_view_frequencies)
        self.sweep_panel.quickSettingToggled.connect(self._on_quick_setting_toggled)
        self.sweep_panel.quickSoloToggled.connect(self._on_quick_solo_toggled)
        self.sweep_panel.frequenciesChanged.connect(self._on_custom_span_entered)
        self.sweep_panel.solo_qs_btn.setChecked(self.settings.value("quick_band_solo", False, type=bool))
        self.sweep_panel.editQuickSettingsClicked.connect(self.open_quick_settings_editor)
        self.sweep_panel.amplitudeChanged.connect(self.apply_amplitude_settings)
        self.sweep_panel.scaleDivChanged.connect(self._on_scale_div_changed)
        self.sweep_panel.autoRefLevelClicked.connect(self.auto_reference_level)
        self.sweep_panel.sweepSettingsChanged.connect(self.apply_sweep_settings)
        self.sweep_panel.detectSettingsChanged.connect(self.apply_detect_settings)
        self.sweep_panel.bwSettingsChanged.connect(self.apply_bw_settings)
        self.sweep_panel.traceToggled.connect(self._on_panel_trace_toggled)
        self.sweep_panel.traceFreezeToggled.connect(self._on_trace_freeze_toggled)
        self.sweep_panel.traceColorChanged.connect(self._on_trace_color_changed)
        self.sweep_panel.avgSweepsChanged.connect(self._on_avg_sweeps_changed)
        self.sweep_panel.linkViewToggled.connect(self._on_link_view_toggled)
        self.sweep_panel.rfInputChanged.connect(self._on_rf_input_changed)
        self.sweep_panel.settingsTargetChanged.connect(self._select_settings_slot)
        self.multi_device_manager.topology_changed.connect(lambda _t: self._refresh_antenna_sources())
        self.multi_device_manager.topology_changed.connect(lambda _t: self._refresh_connection_dot())
        self._refresh_antenna_sources()
        self.sweep_panel.levelTrimChanged.connect(self._on_level_trim_changed)
        self.sweep_panel.alignTracesClicked.connect(self._align_split_traces)
        self._load_level_trims()
        
        # Freq Coupling
        self.sweep_panel.start_spin.valueChanged.connect(self._on_start_stop_changed)
        self.sweep_panel.stop_spin.valueChanged.connect(self._on_start_stop_changed)
        self.sweep_panel.center_spin.valueChanged.connect(self._on_center_changed)
        self.sweep_panel.span_spin.valueChanged.connect(self._on_span_changed)
        self.sweep_panel.view_start_spin.valueChanged.connect(self._on_view_start_stop_changed)
        self.sweep_panel.view_stop_spin.valueChanged.connect(self._on_view_start_stop_changed)
        self.sweep_panel.view_center_spin.valueChanged.connect(self._on_view_center_changed)
        self.sweep_panel.view_span_spin.valueChanged.connect(self._on_view_span_changed)
        
        # DTV Panel
        self.dtv_panel.lookupRequested.connect(self._on_fcc_lookup)
        self.stationLookupFinished.connect(self._on_station_lookup_finished)
        self.dtv_panel.updateUkDataRequested.connect(self._on_update_uk_data)
        self.dtv_panel.thresholdChanged.connect(self.spectrum_view.threshold_line.setPos)
        self.dtv_panel.showThresholdToggled.connect(lambda _on: self._sync_dtv_threshold_line())
        self.dtv_panel.dtvDetectToggled.connect(self._on_dtv_detect_toggled)
        self.dtv_panel.detectSettingsChanged.connect(self._on_dtv_detect_settings_changed)
        self.dtv_panel.stationMaskToggled.connect(self._set_channel_mask)
        self.dtv_panel.allMasksRequested.connect(self._on_all_station_masks)
        self.dtv_panel.tbandScanToggled.connect(self._on_tband_scan_toggled)
        self.dtv_panel.stationSelected.connect(self._on_dtv_table_clicked)
        self.dtv_panel.zoneSelected.connect(self._on_zone_selected)
        
        # DECT Panel
        self.dect_panel.bandChanged.connect(self._on_dect_band_changed)
        self.dect_panel.monitorToggled.connect(self._on_dect_monitor_toggled)
        self.dect_panel.thresholdChanged.connect(self._on_dect_threshold_spin_changed)
        self.dect_panel.showThresholdToggled.connect(self._on_dect_show_threshold_toggled)
        self.spectrum_view.dectThresholdChanged.connect(self._on_dect_threshold_dragged)
        self.dect_panel.tuneSweepClicked.connect(self.tune_to_dect_band)
        self.dect_panel.openMatrixClicked.connect(self.open_dect_matrix_dialog)
        self.dect_panel.clearClicked.connect(self.dect_engine.reset_data)
        self.dect_panel.countClicked.connect(self.start_dect_count)
        self._dect_count = None             # a zero-span count run in progress (see start_dect_count)
        
        # ShowLink Panel
        self.showlink_panel.monitorToggled.connect(self._on_showlink_monitor_toggled)
        self.showlink_panel.thresholdChanged.connect(self._on_showlink_threshold_spin_changed)
        self.showlink_panel.showThresholdToggled.connect(self._on_showlink_show_threshold_toggled)
        self.spectrum_view.showlinkThresholdChanged.connect(self._on_showlink_threshold_dragged)
        self.showlink_panel.tuneSweepClicked.connect(self.tune_to_showlink_band)
        self.showlink_panel.openMapClicked.connect(self.open_showlink_map_dialog)
        self.showlink_panel.clearClicked.connect(self._clear_showlink_data)
        self.showlink_panel.myChannelChanged.connect(self._on_showlink_my_channel_changed)
        self.showlink_panel.airtimeClicked.connect(self.start_showlink_airtime)
        self.showlink_panel.copySurveyClicked.connect(self._copy_showlink_survey)
        self._showlink_airtime = None
        saved_ch = self.settings.value("showlink_judge_channel", 0, type=int)
        self.showlink_panel.my_channel_combo.setCurrentIndex(max(0, self.showlink_panel.my_channel_combo.findData(saved_ch)))
        self.showlink_engine.set_my_channel(saved_ch)
        
        # Threats Panel
        self.threats_panel.intruderAlertToggled.connect(self._on_intruder_alert_toggled)
        self.threats_panel.intruderThresholdChanged.connect(self._on_intruder_threshold_changed)
        self.threats_panel.carrierMaskChanged.connect(self._on_carrier_mask_changed)
        tp = self.threats_panel
        tp.carrier_mask_combo.blockSignals(True)
        tp.carrier_mask_combo.setCurrentIndex(max(0, tp.carrier_mask_combo.findData(self.settings.value("carrier_mask", "auto", type=str))))
        tp.carrier_mask_combo.blockSignals(False)
        tp.carrier_mask_margin_spin.blockSignals(True)
        tp.carrier_mask_margin_spin.setValue(self.settings.value("carrier_mask_margin_db", 6.0, type=float))
        tp.carrier_mask_margin_spin.blockSignals(False)
        self._mask_breaks = {}              # intruder key (MHz) -> the carrier whose mask it breaks, and by how much
        self._mask_drawn = False
        self._mask_draw_time = 0.0
        self.threats_panel.showThresholdToggled.connect(self._on_intruder_show_threshold_toggled)
        self.threats_panel.intruder_table.cellClicked.connect(self._on_intruder_row_clicked)
        self.threats_panel.clearIntrudersClicked.connect(self._clear_intruders)
        self.threats_panel.addIntruderToMarkersClicked.connect(self._add_intruders_to_markers)
        self.threats_panel.fingerprintRequested.connect(self._on_fingerprint_requested)
        self.threats_panel.intermodSettingsChanged.connect(lambda: self._rebuild_intermod(force=True))
        self.threats_panel.intermodCheckRequested.connect(self._on_intermod_check)
        self.threats_panel.intermodVerifyRequested.connect(self._on_intermod_verify)
        self.threats_panel.backgroundFingerprintToggled.connect(self._on_background_fingerprint_toggled)
        self.threats_panel.loadCoordinationClicked.connect(self.load_coordination_file)
        self.threats_panel.markerItemChanged.connect(self._on_marker_tree_item_changed)
        self.threats_panel.carrierSelected.connect(self._on_soundbase_carrier_selected)
        self.threats_panel.carrierColorChanged.connect(self._on_carrier_color_changed)

        # MSCAN Panel & View
        self.multi_device_manager.mscan_data_ready.connect(self._on_mscan_data)
        self.mscan_panel.scanToggled.connect(self._on_mscan_toggled)
        self.mscan_panel.paramsChanged.connect(self._on_mscan_params_changed)
        self.mscan_panel.loadCoordinationClicked.connect(self.load_coordination_file)
        self.mscan_panel.channelsSelectionChanged.connect(self._on_mscan_channels_selected)
        self.mscan_panel.tuneAudioDemodRequested.connect(self.tune_audio_demod_carrier)
        self.mscan_panel.inspectRtsaRequested.connect(self.inspect_rtsa_carrier)
        self.mscan_panel.carrierColorChanged.connect(self._on_carrier_color_changed)

        self.mscan_view.tuneDemodRequested.connect(self.tune_audio_demod_carrier)
        self.mscan_view.inspectRtsaRequested.connect(self.inspect_rtsa_carrier)
        self.mscan_view.carrierColorChanged.connect(self._on_carrier_color_changed)

    def _init_state(self):
        # Active regional presets & channels
        self.top_bar.set_interface_badge(self.connection_interface, self.network_ip)
        self._restore_table_columns()
        rf_input = self.settings.value("rf_input", "auto", type=str)
        self.sweep_panel.set_rf_input(rf_input)
        self.multi_device_manager.set_rf_input(rf_input)
        self._update_region_ui()
        self.apply_frequencies()
        self.apply_view_frequencies()
        self.apply_amplitude_settings()
        self.apply_bw_settings()
        self.apply_sweep_settings()
        # Auto-connect on startup to immediately begin streaming live RF spectrum
        QTimer.singleShot(150, self.connect_analyzer)

    HUB_DEFAULT_WIDTH = 540        # mode rail (160) plus a module panel wide enough for its tables

    def _restore_hub_width(self):
        """Bring back the width the user left the module panel at, and remember later changes."""
        w = self.settings.value("hub_width", self.HUB_DEFAULT_WIDTH, type=int)
        self._hub_width = max(440, w)
        self.main_h_splitter.setSizes([self._hub_width, max(400, self.width() - self._hub_width)])
        self.main_h_splitter.splitterMoved.connect(self._on_hub_splitter_moved)

    def _fit_hub_to_panels(self):
        """
        A module panel narrower than its widest row loses that row's right-hand end (the
        panels scroll vertically only). So the panel area is never narrower than the widest
        panel needs, measured once the stylesheet's fonts and paddings are in effect.
        """
        from PyQt6.QtWidgets import QScrollArea
        need = 280
        for i in range(self.panel_stack.count()):
            panel = self.panel_stack.widget(i)
            area = panel if isinstance(panel, QScrollArea) else panel.findChild(QScrollArea)
            if area is not None and area.widget() is not None:
                bar = area.verticalScrollBar().sizeHint().width()
                need = max(need, area.widget().minimumSizeHint().width() + bar + 2 * area.frameWidth() + 2)
        self.panel_stack.setMinimumWidth(need)
        hub = self.nav_rail.width() + need
        if self.panel_stack.isVisible() and self.main_h_splitter.sizes()[0] < hub:
            self._hub_width = hub
            self.main_h_splitter.setSizes([hub, max(400, self.width() - hub)])

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_hub_fitted", False):
            self._hub_fitted = True
            QTimer.singleShot(0, self._fit_hub_to_panels)

    def _on_hub_splitter_moved(self, *_):
        if self.panel_stack.isVisible():
            self._hub_width = self.main_h_splitter.sizes()[0]
            self.settings.setValue("hub_width", int(self._hub_width))

    def _on_nav_collapse(self, collapsed: bool):
        self.panel_stack.setVisible(not collapsed)
        if collapsed:
            self.main_h_splitter.setSizes([48, self.width() - 48])
        else:
            w = getattr(self, "_hub_width", self.HUB_DEFAULT_WIDTH)
            self.main_h_splitter.setSizes([w, self.width() - w])

    # --- Hardware & Multi-Device Sweep Loop ---
    def toggle_connection(self):
        if not self.is_connected:
            busy = self.multi_device_manager.connecting()
            if busy:
                # An open is under way (a network analyzer takes 5 s or more): starting over
                # would abandon it half-way and the analyzer may then refuse the next one
                names = ", ".join(self._slot_label(sid) for sid in busy)
                self.top_bar.flash_status(f"Still connecting to {names}… (click again to give up and reconnect)", 3000)
                self._connect_pressed_while_busy = getattr(self, "_connect_pressed_while_busy", 0) + 1
                if self._connect_pressed_while_busy < 2:
                    return
            self._connect_pressed_while_busy = 0
            self.top_bar.set_device_status(False, "Connecting...")
            started = self.multi_device_manager.connect_all_enabled()
            if not started:
                self.open_connection_manager()
        else:
            self.multi_device_manager.disconnect_all()
            self.is_connected = False
            self.is_sweeping = False
            self.top_bar.set_device_status(False, "Disconnected")

    def connect_analyzer(self):
        self.top_bar.set_device_status(False, "Connecting...")
        self.multi_device_manager.connect_all_enabled()

    def open_connection_manager(self):
        dlg = ConnectionDialog(manager=self.multi_device_manager, parent=self)
        if dlg.exec():
            cfg = dlg.get_multi_device_config()
            topo = cfg.get("topology", MultiDeviceTopology.SINGLE)
            self.multi_device_manager.set_topology(topo)
            
            # Apply slots config
            for s_id, s_cfg in cfg.get("slots", {}).items():
                slot = self.multi_device_manager.ensure_slot(s_id)
                if slot:
                    slot.is_enabled = s_cfg["enabled"]
                    slot.role_alias = s_cfg.get("alias", "").strip()
                    slot.interface_type = s_cfg["interface"]
                    slot.ip_address = s_cfg["ip"]
                    slot.port = s_cfg["port"]
                    slot.usb_index = s_cfg["usb_index"]
                    slot.target_model = s_cfg.get("target_model")
                    slot.target_uid = s_cfg.get("target_uid")
                    slot.serial_port = s_cfg.get("serial_port")
                    
            if cfg.get("remember", True):
                self.settings.setValue("multi_device_topology", topo)
                self.settings.setValue("multi_device_slots", json.dumps(cfg.get("slots", {})))
                
            self.top_bar.set_multi_device_state(topo, {
                s_id: {"alias": s.role_alias, "enabled": s.is_enabled}
                for s_id, s in self.multi_device_manager.slots.items()
            })
            self._apply_input_chains()   # analyzer names may have changed
            
            # Reconnect if already connected or start connection
            if self.is_connected:
                self.multi_device_manager.disconnect_all()
            self.top_bar.set_device_status(False, "Connecting...")
            self.multi_device_manager.connect_all_enabled()

    def toggle_sweep(self, sweeping: bool):
        if not self.is_connected:
            if sweeping:
                self.toggle_connection()
            return
        if sweeping:
            self.is_sweeping = True
            self.top_bar.set_sweeping_state(True)
            if self._last_operating_mode == "DET":
                self.det_panel.set_active_state(True)
            self.multi_device_manager.start_sweeping_all()
        else:
            self.is_sweeping = False
            self.top_bar.set_sweeping_state(False)
            if self._last_operating_mode == "DET":
                self.det_panel.set_active_state(False)
            self.multi_device_manager.pause_sweeping_all()

    def _on_all_connection_status(self, any_connected: bool):
        self.is_connected = any_connected
        if self.panel_stack.currentIndex() == 9:
            self._sync_sensors()            # Locate: a sensor that has gone says so at once
        self._refresh_slot_readouts()
        self._refresh_connection_dot()
        self._refresh_antenna_sources()
        if any_connected:
            topo = self.multi_device_manager.topology
            connected_slots = [s for s in self.multi_device_manager.slots.values() if s.is_connected]
            
            # Dynamically reflect active interface type on top bar badge (Net vs USB)
            net_slot = next((s for s in connected_slots if s.interface_type.lower() == "network"), None)
            if net_slot:
                self.top_bar.set_interface_badge("network", net_slot.ip_address)
            else:
                self.top_bar.set_interface_badge("usb")

            if len(connected_slots) > 1:
                info_str = f"{len(connected_slots)} Analyzers Online"      # the mode is in the badge beside it
            elif len(connected_slots) == 1:
                s = connected_slots[0]
                if s.capabilities:
                    m_str = s.capabilities["name"]
                else:
                    m_str = f"Model {s.detected_model:03d}" if s.detected_model else "Analyzer"
                alias = s.role_alias.strip()
                info_str = f"{m_str} • {alias}" if alias else m_str
            else:
                info_str = "Online"
            self.top_bar.set_device_status(True, info_str)
            self.top_bar.set_sweeping_state(True)
            self.is_sweeping = True
            self.apply_frequencies()
            self.multi_device_manager.start_sweeping_all()
        else:
            # When disconnected, reflect primary configured slot interface
            slot_a = self.multi_device_manager.slots.get("slot_a")
            if slot_a and slot_a.interface_type.lower() == "network":
                self.top_bar.set_interface_badge("network", slot_a.ip_address)
            else:
                self.top_bar.set_interface_badge(self.connection_interface, self.network_ip)

            self.top_bar.set_device_status(False, "Disconnected")
            self.top_bar.set_sweeping_state(False)
            self.is_sweeping = False
            self._clear_live_display()

    def _clear_live_display(self):
        """
        No analyzer is connected: nothing on screen should look like a live measurement.
        The spectrum traces and the waterfall are emptied in every view that shows them
        (RF & Sweep, Threats, Demodulation, Broadcast / DTV, DECT, ShowLink), and the held
        traces and history start again with the next connection. Masks, markers, thresholds
        and the lists built from earlier sweeps (threats, stations) are left as they are.
        """
        self.last_freq = self.last_power = None
        self._last_sweep = None
        self._last_div_b = self._last_div_a = None
        self._reset_b_holds()
        self.max_hold_data = self.min_hold_data = None
        self.avg_history = []
        self.waterfall_buffer[:] = -130.0
        self._wf_head = 0
        self.spectrum_view.clear_traces()
        self.spectrum_view_b.clear_traces()
        self.waterfall_view.clear_image()
        if hasattr(self, "multi_row_view"):
            self.multi_row_view.clear_data()
        if hasattr(self, "demod_view"):
            self.demod_view.spectrum_view.clear_traces()
            self.demod_view.waterfall_view.clear_image()
        self.top_bar.set_fps(0.0) if hasattr(self.top_bar, "set_fps") else None
        if hasattr(self, "_mask_drawn"):
            self._draw_carrier_masks()      # the masks go back to their dashed, nothing-on-air shapes

    def _on_slot_status_changed(self, slot_id: str, is_connected: bool, msg: str):
        self._on_all_connection_status(self.is_connected)

    def _on_slot_info_received(self, slot_id: str, model: int, uid: object):
        slot = self.multi_device_manager.slots.get(slot_id)
        if slot and not device_caps.resolve(slot.capabilities)["calibration_files"]:
            return   # this analyzer is calibrated internally (e.g. a tinySA)
        if model and uid:
            is_cal = self.cal_manager.is_calibrated(model, uid)
            if not is_cal:
                dlg = MissingCalDialog(model, uid, self)
                if dlg.exec() and dlg.result_action == "open_manager":
                    self.open_calibration_manager(model, uid)

    def _on_device_status(self, status_str: str):
        if not self.is_connected:
            self.top_bar.dev_label.setText(status_str)

    def _on_amplitude_clamped(self, slot_id: str, ref_level: float, atten: int):
        if self._settings_slot and slot_id != self._settings_slot:
            return      # another analyzer's settings are on screen
        mdm = self.multi_device_manager
        if not self._settings_slot and sum(1 for s in mdm.slots.values() if s.is_connected) > 1:
            # Several analyzers share the panel's settings: one of them reaching its own
            # limit must not pull the control (and the display) back for all of them
            tag = slot_id.split("_")[-1].upper()
            self.top_bar.flash_status(f"Analyzer {tag}: Ref Level limited to {ref_level:.1f} dBm by hardware")
            return
        if self.sweep_panel.attenuation >= 0:
            # Manual attenuation: the analyzer takes its reference level from the attenuation
            # and reports that one back on every change. The control stays the user's (it
            # sets the top of the display); writing the report back would pin it.
            # Said once per range: the analyzer repeats its report every time the sweep is re-armed
            if getattr(self, "_manual_range_told", None) != (slot_id, ref_level):
                self._manual_range_told = (slot_id, ref_level)
                self.top_bar.flash_status(
                    f"Manual attenuation: the analyzer's range is {ref_level:.0f} dBm; Ref. Level moves the display only", 5000)
            return
        self.sweep_panel.ref_level_spin.blockSignals(True)
        self.sweep_panel.ref_level_spin.setValue(ref_level)
        self.sweep_panel.ref_level_spin.blockSignals(False)
        self.spectrum_view.set_amplitude_scale(ref_level, self.sweep_panel.scale_div)
        if hasattr(self, 'demod_view') and hasattr(self.demod_view, 'spectrum_view'):
            self.demod_view.spectrum_view.set_amplitude_scale(ref_level, self.sweep_panel.scale_div)
        if atten >= 0:
            self.sweep_panel.atten_spin.blockSignals(True)
            self.sweep_panel.atten_spin.setValue(atten)
            self.sweep_panel.atten_spin.blockSignals(False)
        self.top_bar.flash_status(f"Ref Level adjusted to {ref_level:.1f} dBm by hardware")

    def _restart_held_traces(self, why: str = ""):
        """
        Max hold, min hold and average start again from the next sweep. They are built from
        earlier sweeps, and once the bandwidth or the detector changes those sweeps are not
        comparable: a max hold kept from a wide VBW stays up at the old noise peaks for good,
        on screen and in an export.
        """
        had = self.max_hold_data is not None or self.min_hold_data is not None or bool(self.avg_history)
        self.max_hold_data = self.min_hold_data = None
        self.avg_history = []
        self._reset_b_holds()
        if had and why:
            self.top_bar.flash_status(f"Max / Min / Average restarted: {why}", 4000)

    def _on_bandwidth_updated(self, slot_id: str, rbw_hz: float, vbw_hz: float):
        # The analyzer reports its bandwidths each time the sweep is re-armed, ahead of the
        # first sweep taken with them: the moment to restart the held traces
        before = self._bw_by_slot.get(slot_id)
        self._bw_by_slot[slot_id] = (round(float(rbw_hz), 3), round(float(vbw_hz), 3))
        if before is not None and before != self._bw_by_slot[slot_id]:
            self._restart_held_traces("the bandwidth changed")
        elif self._holds_restart_pending:
            self._restart_held_traces("the detector changed")
        self._holds_restart_pending = False
        self._rbw_by_slot[slot_id] = rbw_hz
        if not self._settings_slot or slot_id == self._settings_slot:
            self.sweep_panel.update_hardware_bandwidth(rbw_hz, vbw_hz)

    # Per-analyzer hardware readouts; the top bar shows the focused analyzer's
    def _slot_hw(self, slot_id: str) -> dict:
        if not hasattr(self, "_hw_by_slot"):
            self._hw_by_slot = {}
        return self._hw_by_slot.setdefault(slot_id, {})

    def _is_focused_slot(self, slot_id: str) -> bool:
        return slot_id == self.multi_device_manager.focused_slot_id

    def _refresh_top_bar_hardware(self, slot_id: str = None):
        hw = self._slot_hw(slot_id or self.multi_device_manager.focused_slot_id)
        if "endorsements" in hw:
            self.top_bar.set_hw_endorsements(hw["endorsements"])
        if "temp_c" in hw:
            self.top_bar.set_device_temperature(hw["temp_c"])
        if "power" in hw:
            self.top_bar.set_power_state(hw["power"], hw.get("endorsements", {}).get("interface", "USB Direct"))

    def _refresh_connection_dot(self):
        """Two analyzers in use (any topology but single): the dot shows each one's connection."""
        mdm = self.multi_device_manager
        a, b = mdm.slots.get("slot_a"), mdm.slots.get("slot_b")
        if mdm.topology == MultiDeviceTopology.SINGLE or a is None or b is None:
            self.top_bar.set_slot_connections(None)
        else:
            self.top_bar.set_slot_connections((a.is_connected, b.is_connected))

    def _refresh_slot_readouts(self):
        """With several analyzers online the top bar shows each one's readouts, not just the focused one's."""
        entries = []
        for slot_id in sorted(self.multi_device_manager.slots):
            slot = self.multi_device_manager.slots[slot_id]
            if not slot.is_connected:
                continue
            hw = self._slot_hw(slot_id)
            end = hw.get("endorsements", {})
            if slot.capabilities:
                name = slot.capabilities["name"]
            else:
                name = f"Model {slot.detected_model:03d}" if slot.detected_model else "Analyzer"
            alias = (slot.role_alias or "").strip()
            interface = end.get("interface") or ("Network" if slot.interface_type.lower() == "network" else "USB Direct")
            entries.append({"slot_id": slot_id, "tag": slot_id.split("_")[-1].upper(),
                            "name": f"{name} • {alias}" if alias else name, "interface": interface,
                            "endorsements": end, "temp_c": hw.get("temp_c"), "power": hw.get("power")})
        self.top_bar.set_slot_readouts(entries)

    def _on_hw_endorsements(self, slot_id: str, endorsements: dict):
        # Sent once per connection: readings kept from the slot's previous
        # analyzer (temperature, power) no longer apply
        hw = self._slot_hw(slot_id)
        hw.clear()
        hw["endorsements"] = endorsements
        if self._is_focused_slot(slot_id):
            self.top_bar.set_hw_endorsements(endorsements)
            self.top_bar.set_device_temperature(None)
        self._refresh_slot_readouts()

    # --- Analyzer capabilities: grey out what the focused analyzer cannot do ---
    def _capabilities(self) -> dict:
        return device_caps.resolve(self.multi_device_manager.focused_capabilities())

    def _mode_available(self, mode: str, what: str) -> bool:
        """True if the focused analyzer has `mode`; otherwise says so in the top bar."""
        caps = self._capabilities()
        if mode in caps["modes"]:
            return True
        self.top_bar.flash_status(f"{what} is not available on the {caps['name']}")
        return False

    # --- Per-analyzer settings: with two or more analyzers, each keeps its own ---
    def _settings_target(self):
        """The slot that settings changes go to; None: every analyzer."""
        if self._settings_slot:
            return self._settings_slot
        mdm = self.multi_device_manager
        return mdm.focused_slot_id if mdm.topology == MultiDeviceTopology.INDEPENDENT else None

    def _settings_caps(self) -> dict:
        """Capabilities of the analyzer whose settings the sweep panel shows."""
        slot = self.multi_device_manager.slots.get(self._settings_slot) if self._settings_slot else None
        if slot is not None and slot.is_connected:
            return device_caps.resolve(slot.capabilities)
        return self._capabilities()

    def _slot_model(self, slot) -> str:
        if slot.capabilities:
            return slot.capabilities["name"]
        return f"Harogic model {slot.detected_model:03d}" if slot.detected_model else "Harogic analyzer"

    def _panel_settings(self) -> dict:
        return dict(self.sweep_panel.analyzer_settings(), _model=self._settings_caps()["name"])

    def _store_panel_settings(self):
        """Remember what was just applied, for the analyzer(s) it was applied to."""
        mdm = self.multi_device_manager
        settings = self._panel_settings()
        target = self._settings_target()
        for sid, slot in mdm.slots.items():
            if slot.is_connected and target in (None, sid):
                self._slot_settings[sid] = dict(settings)

    def _send_settings(self, d: dict, slot_id: str):
        """Apply remembered settings to one analyzer."""
        mdm = self.multi_device_manager
        mdm.set_amplitude_params(d["ref_level"], -1 if d["auto_atten"] else int(d["atten"]), d["preamp"] or 0,
                                 int(d["ifagc"]), d["ifagc_target"], d["ifagc_period"], int(d["if_out"]),
                                 target_slot_id=slot_id)
        mdm.set_bandwidth_params(d["rbw_mode"], d["rbw_hz"], d["vbw_mode"], d["vbw_hz"], target_slot_id=slot_id)
        mdm.set_sweep_params(d["swt_mode"], d["sweep_time"], d["spur"], d["window"], target_slot_id=slot_id)
        mdm.set_detect_params(d["detector"], d["trace_detector"], target_slot_id=slot_id)
        mdm.set_rf_input(d["rf_input"], slot_id)

    def _sync_connected_settings(self):
        """An analyzer that (re)connects gets the settings remembered for it, unless
        a different model is now on that slot."""
        for sid, slot in self.multi_device_manager.slots.items():
            if not slot.is_connected:
                self._slots_synced.discard(sid)
            elif sid not in self._slots_synced:
                self._slots_synced.add(sid)
                stored = self._slot_settings.get(sid)
                if stored and stored.get("_model") == device_caps.resolve(slot.capabilities)["name"]:
                    self._send_settings(stored, sid)
                else:
                    self._slot_settings.pop(sid, None)

    def _refresh_settings_targets(self):
        """Offer a choice of analyzer in the sweep panel when two or more are connected:
        each one, plus all together when they are the same model."""
        mdm = self.multi_device_manager
        connected = [(sid, slot) for sid, slot in sorted(mdm.slots.items()) if slot.is_connected]
        entries = []
        if len(connected) >= 2:
            if all(slot.capabilities == connected[0][1].capabilities for _sid, slot in connected):
                entries.append((None, "All analyzers"))
            entries += [(sid, f"{self._slot_label(sid)} · {self._slot_model(slot)}") for sid, slot in connected]
        choices = [slot_id for slot_id, _label in entries]
        target = self._settings_slot
        if target not in choices:
            # Different models cannot share settings: start on the focused analyzer
            target = None if not choices or None in choices else (
                mdm.focused_slot_id if mdm.focused_slot_id in choices else choices[0])
        self.sweep_panel.set_settings_targets(entries, target)
        self._refresh_level_trims()
        if target != self._settings_slot:
            self._select_settings_slot(target)

    # --- Level trim: a few dB per analyzer, to line their traces up with each other ---
    def _load_level_trims(self):
        try:
            trims = json.loads(self.settings.value("slot_level_trims", "") or "{}")
        except (TypeError, ValueError):
            trims = {}
        for sid, slot in self.multi_device_manager.slots.items():
            try:
                slot.level_trim_db = float(trims.get(sid, 0.0))
            except (TypeError, ValueError):
                slot.level_trim_db = 0.0

    def _refresh_level_trims(self):
        mdm = self.multi_device_manager
        entries = [(sid, sid.split("_")[-1].upper(), slot.level_trim_db)
                   for sid, slot in sorted(mdm.slots.items()) if slot.is_connected]
        self.sweep_panel.set_level_trims(entries, mdm.topology == MultiDeviceTopology.SPLIT_SWEEP)

    def _on_level_trim_changed(self, slot_id: str, trim_db: float):
        slots = self.multi_device_manager.slots
        if slot_id not in slots:
            return
        slots[slot_id].level_trim_db = trim_db
        self.settings.setValue("slot_level_trims", json.dumps(
            {sid: s.level_trim_db for sid, s in slots.items() if s.level_trim_db}))
        # The held traces were built with the old trim
        self.max_hold_data = self.min_hold_data = None
        self.avg_history = []
        self._reset_b_holds()

    def _align_split_traces(self):
        step = self.multi_device_manager.seam_step_db()
        if step is None:
            self.top_bar.flash_status("Align at Seam: needs a sweep from both analyzers in split mode")
            return
        step_db, slot_id = step
        slot = self.multi_device_manager.slots[slot_id]
        trim = round(max(-40.0, min(40.0, slot.level_trim_db + step_db)), 1)
        self._on_level_trim_changed(slot_id, trim)
        self._refresh_level_trims()
        tag = slot_id.split("_")[-1].upper()
        self.top_bar.flash_status(f"Analyzer {tag} trimmed to {trim:+.1f} dB (step at the seam was {step_db:+.1f} dB)", 6000)

    def _select_settings_slot(self, slot_id):
        """Show the settings of one analyzer (or of all, None) in the sweep panel."""
        self._settings_slot = slot_id
        self._input_summary = None
        sp = self.sweep_panel
        caps = self._settings_caps()
        # For "all analyzers" (or the one left connected) the panel shows the
        # focused analyzer's settings, or failing that the first connected one's
        mdm = self.multi_device_manager
        connected = [sid for sid, slot in sorted(mdm.slots.items()) if slot.is_connected]
        shown = slot_id or (mdm.focused_slot_id if mdm.focused_slot_id in connected else (connected or [None])[0])
        stored = self._slot_settings.get(shown)
        if stored and stored.get("_model") != caps["name"]:
            stored = None
        # Changing what the panel shows must not be taken for the user changing settings
        sp.blockSignals(True)
        try:
            sp.apply_capabilities(caps)
            if slot_id and stored is None:
                # First look at this analyzer: what is known of its state (the
                # amplitude settings it was connected with), the rest as shown
                slot = self.multi_device_manager.slots[slot_id]
                stored = dict(sp.analyzer_settings(), ref_level=slot.ref_level, auto_atten=slot.atten < 0,
                              atten=max(0, slot.atten), ifagc=bool(slot.ifagc), rf_input=slot.rf_input)
                if sp.preamp_combo.findData(slot.preamp) >= 0:
                    stored["preamp"] = slot.preamp
            if stored is not None:
                sp.set_analyzer_settings(stored)
        finally:
            sp.blockSignals(False)
        if slot_id:
            self._slot_settings[slot_id] = self._panel_settings()
        self.spectrum_view.set_amplitude_scale(sp.ref_level_spin.value(), sp.scale_div)
        if hasattr(self, 'demod_view') and hasattr(self.demod_view, 'spectrum_view'):
            self.demod_view.spectrum_view.set_amplitude_scale(sp.ref_level_spin.value(), sp.scale_div)

    def _apply_capabilities(self, *_):
        self._sync_connected_settings()
        self._refresh_settings_targets()
        caps = self._capabilities()
        name, modes = caps["name"], caps["modes"]
        rail = self.nav_rail
        for idx, mode, what in ((2, "MSCAN", "Rapid channel monitoring"), (3, "RTA", "Real-time spectrum analysis"),
                                (4, "DET", "Zero-span"), (5, "IQS", "Demodulation")):
            rail.set_mode_enabled(idx, mode in modes, f"{what} is not available on the {name}")
        dect_ok = any(device_caps.covers(caps, b["start_mhz"] * 1e6, b["stop_mhz"] * 1e6) for b in DECT_BANDS.values())
        rail.set_mode_enabled(7, dect_ok, f"The {name} does not cover the DECT bands")
        rail.set_mode_enabled(8, device_caps.covers(caps, 2400e6, 2483.5e6), f"The {name} does not cover 2.4 GHz")
        self.top_bar.set_audio_available("IQS" in modes, f"Audio demodulation is not available on the {name}")
        self.sweep_panel.apply_capabilities(self._settings_caps())
        self.det_panel.apply_capabilities(caps)
        self.det_panel.set_rf_input(self.sweep_panel.rf_input)
        if not rail.is_mode_enabled(rail.btn_group.checkedId()):
            rail.set_active_mode(0)
        if not self._settings_caps()["inputs"]:
            self._input_summary = None

    # --- RF input (analyzers with several: a tinySA's Low and High connectors) ---
    def _on_rf_input_changed(self, rf_input: str):
        self.settings.setValue("rf_input", rf_input)
        self.multi_device_manager.set_rf_input(rf_input, self._settings_target())
        self.det_panel.set_rf_input(rf_input)
        self._store_panel_settings()

    def _on_sweep_plan(self, slot_id: str, plan: dict):
        # Shown for the analyzer whose settings are in the sweep panel
        shown_slot = self._settings_slot or self.multi_device_manager.focused_slot_id
        if slot_id != shown_slot or not self._settings_caps()["inputs"]:
            return
        summary = self.sweep_panel.show_sweep_plan(plan)
        # The inputs are separate connectors, so a change is worth announcing
        if summary != self._input_summary:
            self._input_summary = summary
            self.top_bar.flash_status(f"{self._settings_caps()['name']}: {summary}", 6000)

    def _on_diversity_mode_changed(self, mode: str):
        self.multi_device_manager.set_diversity_view_mode(mode)

    def _on_focus_slot_changed(self, slot_id: str):
        self.multi_device_manager.set_focused_slot(slot_id)
        slot = self.multi_device_manager.slots.get(slot_id)
        if slot and slot.is_connected and self._settings_slot and self._settings_slot != slot_id:
            # The sweep panel follows the focus when it is showing one analyzer's settings
            self.sweep_panel.select_settings_target(slot_id)
            self._select_settings_slot(slot_id)
        if slot:
            self._updating_freqs = True
            self.sweep_panel.start_spin.setValue(slot.start_freq_hz / 1e6)
            self.sweep_panel.stop_spin.setValue(slot.stop_freq_hz / 1e6)
            self._updating_freqs = False

    def _on_diversity_sweep_data(self, freq, power_a, power_b, delta):
        if not self.is_sweeping or self.multi_device_manager.topology != MultiDeviceTopology.DIVERSITY:
            return
        # Antenna B as the rest of the program sees antenna A: with the amplitude offset, and
        # finite (outside B's coverage there is nothing, not a signal)
        power_b = np.nan_to_num(np.asarray(power_b, dtype=float) + self.sweep_panel.amp_offset_spin.value(),
                                nan=-200.0, posinf=0.0, neginf=-200.0)
        self._last_div_b = (freq, power_b)
        self._last_div_a = (freq, np.nan_to_num(np.asarray(power_a, dtype=float) + self.sweep_panel.amp_offset_spin.value(),
                                                nan=-200.0, posinf=0.0, neginf=-200.0))
        b_traces = self._update_b_holds(power_b)
        # One pair arrives per sweep of either analyzer (~300/s); draw at ~30 FPS
        now = time.monotonic()
        if now - self._last_div_render_time < RENDER_PERIOD_S:
            return
        self._last_div_render_time = now
        x_scaled = freq / self._x_multiplier
        if self._dual_spectrum:
            for name, y in b_traces.items():
                self.spectrum_view_b.update_curve_data(name, x_scaled, y)
        mode = self.multi_device_manager.diversity_view_mode
        if self._dual_spectrum:
            # Antenna A in the main view, antenna B in the second one
            self.spectrum_view.set_trace_visible("Trace A", True)
            self.spectrum_view.set_trace_visible("Trace B", False)
            self.spectrum_view.set_trace_visible("Delta", False)
            self.spectrum_view.update_curve_data("Trace A", x_scaled, power_a)
            self.spectrum_view_b.update_curve_data("Trace B", x_scaled, power_b)
        elif mode == "both":
            self.spectrum_view.set_trace_visible("Trace A", True)
            self.spectrum_view.set_trace_visible("Trace B", True)
            self.spectrum_view.set_trace_visible("Delta", False)
            self.spectrum_view.update_curve_data("Trace A", x_scaled, power_a)
            self.spectrum_view.update_curve_data("Trace B", x_scaled, power_b)
        elif mode == "slot_a":
            self.spectrum_view.set_trace_visible("Trace A", True)
            self.spectrum_view.set_trace_visible("Trace B", False)
            self.spectrum_view.set_trace_visible("Delta", False)
            self.spectrum_view.update_curve_data("Trace A", x_scaled, power_a)
        elif mode == "slot_b":
            self.spectrum_view.set_trace_visible("Trace A", False)
            self.spectrum_view.set_trace_visible("Trace B", True)
            self.spectrum_view.set_trace_visible("Delta", False)
            self.spectrum_view.update_curve_data("Trace B", x_scaled, power_b)
        elif mode == "delta":
            self.spectrum_view.set_trace_visible("Trace A", False)
            self.spectrum_view.set_trace_visible("Trace B", False)
            self.spectrum_view.set_trace_visible("Delta", True)
            self.spectrum_view.update_curve_data("Delta", x_scaled, delta)

    # --- Which antenna a detector reads (DECT, ShowLink, Broadcast / DTV) ---
    def _refresh_antenna_sources(self):
        topo = self.multi_device_manager.topology
        for panel in (self.dect_panel, self.showlink_panel, self.dtv_panel):
            panel.antenna_row.set_topology(topo)

    def _detector_sweep(self, panel, x_data, y_data):
        """
        The sweep a detector works on. Diversity: the antenna chosen in its panel, whatever
        the main view shows (A, B or their difference). Otherwise the sweep as given.
        """
        if self.multi_device_manager.topology == MultiDeviceTopology.DIVERSITY:
            pair = self._last_div_b if panel.antenna_row.choice() == "B" else self._last_div_a
            if pair is not None:
                return pair
        return x_data, y_data

    def _detector_slot(self, panel):
        """The analyzer a detector's zero-span captures are taken by; None: the focused one."""
        mdm = self.multi_device_manager
        if mdm.topology == MultiDeviceTopology.DIVERSITY and panel.antenna_row.choice() == "B" \
                and mdm.slots["slot_b"].is_connected:
            return "slot_b"
        return None

    def _update_b_holds(self, power_b) -> dict:
        """
        Max hold, min hold and average of antenna B (Dual Spectrum), following the same
        switches as antenna A's. A pair arrives for every sweep of either analyzer, so
        only a new sweep from B counts. Returns the traces to draw.
        """
        if not self._dual_spectrum:
            return {}
        rows = self.sweep_panel.trace_rows
        slot_b = self.multi_device_manager.slots.get("slot_b")
        stamp = getattr(slot_b, "last_update_time", None)
        fresh = stamp is None or stamp != self._b_stamp
        self._b_stamp = stamp
        h = self._b_holds
        n = len(power_b)
        traces = {}
        if rows["Max. Hold"]["cb"].isChecked():
            if h["max"] is None or len(h["max"]) != n:
                h["max"] = np.copy(power_b)
            elif fresh and not rows["Max. Hold"]["freeze"].isChecked():
                np.maximum(h["max"], power_b, out=h["max"])
            traces["Max. Hold"] = h["max"]
        if rows["Min. Hold"]["cb"].isChecked():
            if h["min"] is None or len(h["min"]) != n:
                h["min"] = np.copy(power_b)
            elif fresh and not rows["Min. Hold"]["freeze"].isChecked():
                np.minimum(h["min"], power_b, out=h["min"])
            traces["Min. Hold"] = h["min"]
        if rows["Average"]["cb"].isChecked():
            if h["avg"] and len(h["avg"][0]) != n:
                h["avg"] = []
            if (fresh and not rows["Average"]["freeze"].isChecked()) or not h["avg"]:
                h["avg"] = (h["avg"] + [power_b])[-max(1, self.sweep_panel.avg_sweeps_spin.value()):]
            traces["Average"] = np.mean(h["avg"], axis=0)
        return traces

    def _reset_b_holds(self):
        self._b_holds = {"max": None, "min": None, "avg": []}
        self._b_stamp = None

    def _on_device_sweep_data(self, slot_id: str, x_data: np.ndarray, y_data: np.ndarray):
        if not self.is_sweeping or x_data is None or y_data is None or len(x_data) == 0:
            return
        if self.multi_device_manager.topology == MultiDeviceTopology.SENSOR_NET:
            self.sensor_net.update_sweep(slot_id, x_data, y_data, self._rbw_by_slot.get(slot_id))
            return
        # Per-analyzer routing applies only to the Independent topology; in all
        # other topologies the analyzers run once, on the composite trace, in
        # _on_sweep_data (running both paths analyzed every sweep twice).
        if self.multi_device_manager.topology != MultiDeviceTopology.INDEPENDENT:
            return
        offset = self.sweep_panel.amp_offset_spin.value()
        y_offset = y_data + offset

        if slot_id == "slot_a":
            if self.threats_panel.intruder_enable_cb.isChecked():
                self._process_intruder_sweep(x_data, y_offset)
            else:
                self._draw_masks_without_detection(x_data, y_offset)
            if self.dtv_detect_active:
                self._process_dtv_detect(x_data, y_offset)
            if self.tband_detect_active:
                self._process_tband_scan(x_data, y_offset)
        elif slot_id == "slot_b":
            if self.dect_panel.enable_cb.isChecked():
                self.dect_engine.process_sweep_data(x_data, y_offset)
            if self.showlink_panel.enable_cb.isChecked():
                self.showlink_engine.process_sweep_data(x_data, y_offset)

    def _waterfall_ordered(self) -> np.ndarray:
        """The waterfall history newest-first (one copy, made only when drawing)."""
        h = self._wf_head
        if h == 0:
            return self.waterfall_buffer
        return np.concatenate((self.waterfall_buffer[h:], self.waterfall_buffer[:h]))

    def _on_sweep_data(self, x_data, y_data):
        if not self.is_sweeping or x_data is None or y_data is None or len(x_data) < 2:
            return
            
        if x_data[-1] <= x_data[0]:
            return
            
        self.frame_count += 1
        self.total_frames += 1
        
        # Apply amplitude offset in software
        offset = self.sweep_panel.amp_offset_spin.value()
        y_offset = y_data + offset
        if np.isnan(y_offset).any() or np.isinf(y_offset).any():
            y_offset = np.nan_to_num(y_offset, nan=-130.0, posinf=0.0, neginf=-130.0)
        self._last_sweep = (np.asarray(x_data, dtype=float), y_offset)
        x_scaled = x_data / self._x_multiplier
        self.last_freq = x_scaled
        self.last_power = y_offset
        
        traces = {"Real-Time": y_offset}

        # Max Hold (Only compute if active)
        if self.sweep_panel.trace_rows["Max. Hold"]["cb"].isChecked():
            if self.max_hold_data is None or len(self.max_hold_data) != len(y_offset):
                self.max_hold_data = np.copy(y_offset)
            else:
                if not self.sweep_panel.trace_rows["Max. Hold"]["freeze"].isChecked():
                    np.maximum(self.max_hold_data, y_offset, out=self.max_hold_data)
            traces["Max. Hold"] = self.max_hold_data
        
        # Min Hold (Only compute if active)
        if self.sweep_panel.trace_rows["Min. Hold"]["cb"].isChecked():
            if self.min_hold_data is None or len(self.min_hold_data) != len(y_offset):
                self.min_hold_data = np.copy(y_offset)
            else:
                if not self.sweep_panel.trace_rows["Min. Hold"]["freeze"].isChecked():
                    np.minimum(self.min_hold_data, y_offset, out=self.min_hold_data)
            traces["Min. Hold"] = self.min_hold_data
        
        # Average (Only compute if active)
        if self.sweep_panel.trace_rows["Average"]["cb"].isChecked():
            if not self.sweep_panel.trace_rows["Average"]["freeze"].isChecked():
                max_avg = self.sweep_panel.avg_sweeps_spin.value()
                if len(self.avg_history) >= max_avg or (len(self.avg_history) > 0 and len(self.avg_history[0]) != len(y_offset)):
                    self.avg_history = self.avg_history[-(max_avg - 1):] if len(self.avg_history[0]) == len(y_offset) else []
                self.avg_history.append(y_offset)
                avg_curve = np.mean(self.avg_history, axis=0)
            else:
                avg_curve = np.mean(self.avg_history, axis=0) if self.avg_history else y_offset
            traces["Average"] = avg_curve
        
        # Waterfall: every sweep is recorded; the newest row is at _wf_head
        num_pts = len(y_offset)
        if self.waterfall_buffer.shape[1] != num_pts:
            self.waterfall_buffer = np.full((self.waterfall_history_depth, num_pts), -130.0, dtype=np.float32)
            self._wf_head = 0
        self._wf_head = (self._wf_head - 1) % self.waterfall_buffer.shape[0]
        self.waterfall_buffer[self._wf_head, :] = y_offset
        
        # Draw at up to ~30 FPS. Sweeps arrive faster than that, and every
        # redraw of the traces and the waterfall texture costs more than the
        # maths above, so the screen is updated on a fixed cadence while every
        # sweep still feeds the holds, the average, the history and the analyzers.
        now = time.monotonic()
        if now - self._last_render_time >= RENDER_PERIOD_S:
            self._last_render_time = now
            for name, y in traces.items():
                self.spectrum_view.update_curve_data(name, x_scaled, y)
            if hasattr(self, 'demod_view') and self.viewport_stack.currentIndex() in (0, 4):
                self.demod_view.spectrum_view.update_curve_data("Real-Time", x_scaled, y_offset)
            start_mhz = min(float(x_scaled[0]), float(x_scaled[-1]))
            stop_mhz = max(float(x_scaled[0]), float(x_scaled[-1]))
            width_mhz = max(0.001, stop_mhz - start_mhz)
            wf = self._waterfall_ordered()
            if self.viewport_stack.currentIndex() == 1:
                self.multi_row_view.update_sweep_data(wf, start_mhz, stop_mhz)
            elif self.viewport_stack.currentIndex() == 4:
                self.demod_view.waterfall_view.update_image(
                    wf.T,
                    (start_mhz, 0, width_mhz, self.waterfall_history_depth)
                )
            else:
                self.waterfall_view.update_image(
                    wf.T,
                    (start_mhz, 0, width_mhz, self.waterfall_history_depth)
                )
        
        # Process Specialized Analyzers (Independent topology routes per analyzer
        # in _on_device_sweep_data instead)
        if self.multi_device_manager.topology == MultiDeviceTopology.INDEPENDENT:
            return
        if self.threats_panel.intruder_enable_cb.isChecked():
            self._process_intruder_sweep(x_data, y_offset)
        else:
            self._draw_masks_without_detection(x_data, y_offset)
            
        # (In diversity each detector reads the antenna chosen in its panel)
        if self.dect_panel.enable_cb.isChecked():
            self.dect_engine.process_sweep_data(*self._detector_sweep(self.dect_panel, x_data, y_offset))
            
        if self.showlink_panel.enable_cb.isChecked():
            self.showlink_engine.process_sweep_data(*self._detector_sweep(self.showlink_panel, x_data, y_offset))
            
        if self.dtv_detect_active:
            self._process_dtv_detect(*self._detector_sweep(self.dtv_panel, x_data, y_offset))
        if self.tband_detect_active:
            self._process_tband_scan(*self._detector_sweep(self.dtv_panel, x_data, y_offset))

    def resume_rf_sweep(self):
        self._last_operating_mode = "SWP"
        if hasattr(self, 'det_panel'):
            self.det_panel.set_active_state(False)
        if hasattr(self, 'mscan_panel') and (self.mscan_panel.is_scanning or self.mscan_panel.scan_btn.isChecked()):
            self.mscan_panel.stop_scan(emit_signal=False)
        if not self.is_connected:
            if self.nav_rail.btn_group.checkedId() == 5:
                self.viewport_stack.setCurrentIndex(4)
            elif self.nav_rail.btn_group.checkedId() == 2 and self.mscan_panel.is_scanning:
                self.viewport_stack.setCurrentIndex(5)
            else:
                self._on_view_mode_changed(self.top_bar.view_mode_combo.currentText())
            return
            
        self.multi_device_manager.stop_mscan()
        self._release_zero_span_slot()
        self.multi_device_manager.set_operating_mode("SWP")
        self.apply_frequencies()
        self.apply_amplitude_settings()
        self.apply_bw_settings()
        self.apply_sweep_settings()
        self.apply_detect_settings()
        if self.nav_rail.btn_group.checkedId() == 5:
            self.viewport_stack.setCurrentIndex(4) # Keep DemodView active
        elif self.nav_rail.btn_group.checkedId() == 2 and self.mscan_panel.is_scanning:
            self.viewport_stack.setCurrentIndex(5) # Keep MSCANView active only when actively scanning
        else:
            self._on_view_mode_changed(self.top_bar.view_mode_combo.currentText())
        self.is_sweeping = True
        self.top_bar.set_sweeping_state(True)
        self.multi_device_manager.start_sweeping_all()

    def _release_zero_span_slot(self):
        """An analyzer other than the focused one that a run put into zero span goes back to sweeping."""
        if self._zero_span_slot:
            self.multi_device_manager.set_operating_mode("SWP", target_slot_id=self._zero_span_slot)
            self._zero_span_slot = None

    def _on_det_trigger_requested(self, params: dict):
        if not self.is_connected:
            return
        self._last_operating_mode = "DET"
        self.det_panel.set_active_state(True)
        self.multi_device_manager.set_operating_mode("DET")
        self._on_det_params_changed(params)
        cf_mhz = params.get('center_freq_hz', 0) / 1e6
        self.top_bar.dev_label.setText(f"Zero-Span Active @ {cf_mhz:.2f} MHz")
        self.is_sweeping = True
        self.top_bar.set_sweeping_state(True)

    def _on_det_pause_requested(self):
        self.det_panel.set_active_state(False)
        self.multi_device_manager.pause_sweeping_all()
        self.is_sweeping = False
        self.top_bar.set_sweeping_state(False)
        cf_mhz = self.det_panel.cf_spin.value()
        self.top_bar.dev_label.setText(f"Zero-Span Paused @ {cf_mhz:.2f} MHz")

    def _on_spectrum_trigger_zero_span(self, freq_mhz: float):
        if not self._mode_available("DET", "Zero-span"):
            return
        self.det_panel.cf_spin.setValue(freq_mhz)
        self.nav_rail.set_active_mode(4)
        params = self.det_panel.get_params()
        params["center_freq_hz"] = freq_mhz * 1e6
        self._on_det_trigger_requested(params)

    def _on_det_fit_window_requested(self, min_duration_ns: float):
        self.det_panel.auto_fit_window(min_duration_ns)
        params = self.det_panel.get_params()
        self._on_det_trigger_requested(params)

    def _on_nav_mode_changed(self, mode_idx: int):
        if mode_idx != 2 and hasattr(self, 'mscan_panel') and (self.mscan_panel.is_scanning or self.mscan_panel.scan_btn.isChecked()):
            self.mscan_panel.stop_scan(emit_signal=False)

        self.panel_stack.setCurrentIndex(mode_idx)
        if getattr(self, "_hub_fitted", False):
            QTimer.singleShot(0, self._fit_hub_to_panels)     # a panel's rows may have grown since
        
        if mode_idx == 0: # RF & Sweep
            self.resume_rf_sweep()
        elif mode_idx == 1: # Threats & Markers
            if self._last_operating_mode != "SWP":
                self.resume_rf_sweep()
            else:
                self._on_view_mode_changed(self.top_bar.view_mode_combo.currentText())
        elif mode_idx == 2: # Rapid Channel Monitoring (MSCAN)
            self.viewport_stack.setCurrentIndex(5) # MSCANView
            if self.mscan_panel.is_scanning:
                self._on_mscan_toggled(True)
            elif self._last_operating_mode != "SWP":
                self.resume_rf_sweep()
        elif mode_idx == 3: # Real-Time (RTSA)
            self._last_operating_mode = "RTA"
            if hasattr(self, 'det_panel'):
                self.det_panel.set_active_state(False)
            self.multi_device_manager.set_operating_mode("RTA")
            self.viewport_stack.setCurrentIndex(2)
            ps_dict = self._public_safety_channels()
            std = TV_CHANNEL_STANDARDS.get(self.current_region, [])
            self.rtsa_view.channel_bar.draw_channels(std, self._x_multiplier)
            self.rtsa_view.set_active_channels(self.active_channels, ps_dict)
            self.rtsa_view.update_channel_masks(self.active_channels, std, ps_dict, self.station_info)
            self._on_rtsa_params_changed(self.rtsa_panel.get_params())
        elif mode_idx == 4: # Zero-Span (DET)
            self.viewport_stack.setCurrentIndex(3)
            # Opening the mode starts it, as Real-Time does. A centre frequency the analyzer
            # cannot tune (the default is a DECT carrier) becomes the strongest signal of the
            # last sweep.
            if self.is_connected and self.is_sweeping and self._last_operating_mode != "DET" \
                    and device_caps.supports_mode(self._capabilities(), "DET"):
                cf_hz = self.det_panel.cf_spin.value() * 1e6
                if not device_caps.covers(self._capabilities(), cf_hz, cf_hz) or self.det_panel.cf_spin.value() in (
                        self.det_panel.cf_spin.minimum(), self.det_panel.cf_spin.maximum()):
                    if self.last_freq is not None and self.last_power is not None and len(self.last_power):
                        self.det_panel.cf_spin.setValue(float(self.last_freq[int(np.argmax(self.last_power))]))
                if self._capabilities().get("det"):
                    # Start from the sweep's attenuation and pre-amplifier
                    self.det_panel.set_gain(self.sweep_panel.attenuation, self.sweep_panel.preamp_combo.currentData())
                self._on_det_trigger_requested(self.det_panel.get_params())
        elif mode_idx == 5: # Demodulation (IQS)
            self.viewport_stack.setCurrentIndex(4) # DemodView
            cf = self.demod_panel.cf_spin.value()
            self.demod_view.set_channel_params(cf, self.demod_view.current_channel_bw_mhz)
            # Instantly display existing RF spectrum & waterfall history
            if self.last_freq is not None and self.last_power is not None:
                start_mhz = min(float(self.last_freq[0]), float(self.last_freq[-1]))
                stop_mhz = max(float(self.last_freq[0]), float(self.last_freq[-1]))
                width_mhz = max(0.001, stop_mhz - start_mhz)
                self.demod_view.spectrum_view.set_view_range(start_mhz, stop_mhz)
                self.demod_view.spectrum_view.update_curve_data("Real-Time", self.last_freq, self.last_power)
                self.demod_view.waterfall_view.update_image(
                    self._waterfall_ordered().T,
                    (start_mhz, 0, width_mhz, self.waterfall_history_depth)
                )
            if not self.demod_panel.is_active:
                if self._last_operating_mode != "SWP" or not self.is_sweeping:
                    self.resume_rf_sweep()
        elif mode_idx == 9: # Locate (sensor network)
            if self._last_operating_mode != "SWP":
                self.resume_rf_sweep()
            self.viewport_stack.setCurrentIndex(6)
            self._sync_sensors()
            self._refresh_locate(force=True)
        else: # Broadcast/DTV (6), DECT (7), ShowLink (8)
            if self._last_operating_mode != "SWP":
                self.resume_rf_sweep()
            else:
                self._on_view_mode_changed(self.top_bar.view_mode_combo.currentText())
                
        # Update mode-specific spectrum threshold lines
        if hasattr(self, 'spectrum_view'):
            if hasattr(self.spectrum_view, 'intruder_threshold_line'):
                is_threats = (mode_idx == 1)
                self.spectrum_view.intruder_threshold_line.setVisible(
                    is_threats and self.threats_panel.show_thresh_cb.isChecked()
                )
                if is_threats:
                    self.spectrum_view.intruder_threshold_line.setPos(self.threats_panel.intruder_thresh_spin.value())

            if hasattr(self.spectrum_view, 'dect_threshold_line'):
                is_dect = (mode_idx == 7)
                self.spectrum_view.dect_threshold_line.setVisible(
                    is_dect and self.dect_panel.show_thresh_cb.isChecked()
                )
                if is_dect:
                    self.spectrum_view.dect_threshold_line.setPos(self.dect_panel.thresh_spin.value())

            if hasattr(self.spectrum_view, 'showlink_threshold_line'):
                is_showlink = (mode_idx == 8)
                self.spectrum_view.showlink_threshold_line.setVisible(
                    is_showlink and self.showlink_panel.show_thresh_cb.isChecked()
                )
                if is_showlink:
                    self.spectrum_view.showlink_threshold_line.setPos(self.showlink_panel.thresh_spin.value())

    def _on_demod_requested(self, params: dict):
        self._last_operating_mode = "IQS"
        if hasattr(self, 'det_panel'):
            self.det_panel.set_active_state(False)
        self.multi_device_manager.set_operating_mode("IQS")
        c_freq = params.get("center_freq_hz", 500e6)
        dec_factor = params.get("decimate_factor", 64)
        r_level = params.get("ref_level", 0.0)
        preamp = params.get("preamp", 0x00)
        trig_len = params.get("trigger_length", 16384)
        self.multi_device_manager.configure_iqs(
            center_freq_hz=c_freq,
            decimate_factor=dec_factor,
            ref_level=r_level,
            trig_src=2,
            trig_length=trig_len,
            preamp=preamp,
            atten=0
        )
        self.demod_panel.set_active_state(True)
        self.top_bar.dev_label.setText(f"Demod: {params.get('mod_type', 'QPSK')} @ {c_freq/1e6:.3f} MHz")

    def _on_demod_pause_requested(self):
        self.demod_panel.set_active_state(False)
        cf_mhz = self.demod_panel.cf_spin.value()
        self.top_bar.dev_label.setText(f"Demod Paused @ {cf_mhz:.2f} MHz")
        self.resume_rf_sweep()

    def _on_demod_panel_tune_requested(self, freq_mhz: float):
        self.demod_view.set_channel_params(freq_mhz, self.demod_view.current_channel_bw_mhz)

    def _on_demod_view_tune_requested(self, freq_mhz: float):
        self.demod_panel.cf_spin.blockSignals(True)
        self.demod_panel.cf_spin.setValue(freq_mhz)
        self.demod_panel.cf_spin.blockSignals(False)
        if self.demod_panel.is_active:
            params = self.demod_panel.get_params()
            self._on_demod_requested(params)

    def _on_demod_params_changed(self, params: dict):
        dec = params.get("decimate_factor", 64)
        bw_mhz = (self._iq_base_rate_hz / 1e6 / dec) * 0.8
        self.demod_view.set_channel_params(params.get("center_freq_mhz", 500.0), bw_mhz)

    def _on_iqs_data(self, slot_id: str, iq_complex: np.ndarray, sample_rate: float, info: dict):
        if info.get("base_sample_rate", 0) > 0:
            self._iq_base_rate_hz = float(info["base_sample_rate"])
        # 1. Route to Audio Demodulator if listening
        if (self.audio_demod_dialog is not None and 
            self.audio_demod_dialog.isVisible() and 
            self.audio_demod_dialog.listen_btn.isChecked()):
            try:
                self.audio_demod_dialog.demodulator.process_iq_stream(iq_complex, sample_rate)
            except Exception as e:
                print(f"[MainWindow] Audio demod error: {e}")

        # 2. Route to Digital Demod Engine if Demodulation View is active
        if self.viewport_stack.currentIndex() == 4 and hasattr(self, 'demod_engine') and self.demod_panel.is_active:
            now = time.time()
            if hasattr(self, '_last_demod_render_time') and (now - self._last_demod_render_time < 0.045):
                return
            self._last_demod_render_time = now
            try:
                self.frame_count += 1
                self.total_frames += 1
                params = self.demod_panel.get_params()
                res = self.demod_engine.process_iq_stream(
                    raw_iq=iq_complex,
                    sample_rate=sample_rate,
                    mod_type=params.get("mod_type", "QPSK"),
                    symbol_rate=params.get("symbol_rate", 1e6),
                    filter_type=params.get("filter_type", "RootRaisedCosine"),
                    filter_alpha=params.get("filter_alpha", 0.35),
                    center_freq_hz=info.get("center_freq", 500e6)
                )
                self.demod_view.update_demod_results(res)
                self.demod_panel.update_metrics(res)
            except Exception as e:
                import traceback
                print(f"[MainWindow] Error in _on_iqs_data: {e}")
                traceback.print_exc()

    def _on_rta_data(self, slot_id: str, freq_hz: np.ndarray, trace: np.ndarray, bitmap: np.ndarray, info: dict):
        if self.viewport_stack.currentIndex() == 2:
            self.frame_count += 1
            self.total_frames += 1
            # Frames arrive faster than they can be drawn; the reader already
            # keeps only the newest while the GUI is busy, and drawing at ~30 FPS
            # leaves time for everything else
            now = time.monotonic()
            if now - self._last_render_time >= RENDER_PERIOD_S:
                self._last_render_time = now
                self.rtsa_view.update_rta_data(freq_hz, trace, bitmap, info)

    def _on_det_data(self, slot_id: str, time_ns: np.ndarray, power: np.ndarray, info: dict):
        if self._dect_count is not None:
            self._dect_count_capture(time_ns, power, info)
            return
        if self._showlink_airtime is not None:
            self._showlink_airtime_capture(time_ns, power, info)
            return
        if self.viewport_stack.currentIndex() == 3:
            self.frame_count += 1
            self.total_frames += 1
            now = time.monotonic()
            if now - self._last_render_time >= RENDER_PERIOD_S:
                self._last_render_time = now
                self.det_view.update_det_data(time_ns, power, info)

    def _on_mscan_data(self, slot_id: str, el_idx: int, freq_hz: float, peak_power: float, spec_data, info: dict):
        # Fingerprint passes (focused analyzer) and background fingerprinting
        # (Analyzer B) feed the fingerprinter instead of the channel monitor
        fp_slot = self._fp_pass["slot"] if self._fp_pass else ("slot_b" if self._fp_background else None)
        if slot_id == fp_slot:
            if spec_data is not None and info.get("span_hz", 0) > 0:
                self.fingerprinter.update_mscan(freq_hz, info["span_hz"], spec_data)
                if self._fp_pass:
                    self._fp_pass["spectra"] += 1
            return
        if self.viewport_stack.currentIndex() == 5:
            self.frame_count += 1
            self.total_frames += 1
            dropout_thresh = self.mscan_panel.dropout_spin.value()
            self.mscan_view.update_channel_data(el_idx, freq_hz, peak_power, spec_data, info, dropout_thresh)
            now = time.monotonic()
            if now - self._mscan_telemetry_time >= 0.5:
                self._mscan_telemetry_time = now
                n_ch = max(1, len(self.mscan_panel.selected_carriers))
                hr = max(0.1, self.mscan_view.hop_rate)
                self.mscan_panel.update_telemetry(n_ch, hr, (n_ch / hr) * 1000.0)

    # --- MSCAN Mode Control Handlers ---
    def _on_mscan_toggled(self, is_active: bool):
        if is_active:
            self._last_operating_mode = "MSCAN"
            params = self.mscan_panel.get_params()
            channels = params.get("channels", [])
            if not channels:
                QMessageBox.information(self, "Rapid Channel Monitor", "Please load a Soundbase coordination file or select channels to monitor.")
                self.mscan_panel.scan_btn.setChecked(False)
                self.mscan_panel._update_scan_btn_style()
                return
            self.viewport_stack.setCurrentIndex(5)
            self.mscan_view.set_channels(channels)
            dwell = params.get("dwell_time", 0.001)
            det = params.get("detector", 1)
            ref_lvl = params.get("ref_level", -10.0)
            preamp = params.get("preamp", 0)
            atten = params.get("atten", 0)
            decimate = params.get("decimate", 256)
            self.multi_device_manager.configure_mscan(channels, dwell, det, ref_lvl, preamp, atten, decimate)
            self.top_bar.dev_label.setText(f"Rapid Monitoring: {len(channels)} channels hopping @ {dwell*1000:.1f}ms")
        else:
            self.multi_device_manager.stop_mscan()
            self.multi_device_manager.set_operating_mode("SWP")
            self.resume_rf_sweep()

    def _on_mscan_params_changed(self, params: dict):
        if self.mscan_panel.is_scanning:
            channels = params.get("channels", [])
            if channels:
                dwell = params.get("dwell_time", 0.001)
                det = params.get("detector", 1)
                ref_lvl = params.get("ref_level", -10.0)
                preamp = params.get("preamp", 0)
                atten = params.get("atten", 0)
                decimate = params.get("decimate", 256)
                self.multi_device_manager.configure_mscan(channels, dwell, det, ref_lvl, preamp, atten, decimate)

    def _on_mscan_channels_selected(self, selected_channels: list):
        self.mscan_view.set_channels(selected_channels)

    def tune_audio_demod_carrier(self, freq_mhz: float):
        if not self._mode_available("IQS", "Audio demodulation"):
            return
        if self.audio_demod_dialog is None:
            self.audio_demod_dialog = AudioDemodDialog(initial_freq_hz=freq_mhz * 1e6, parent=self)
            self.audio_demod_dialog.listenStarted.connect(self._on_audio_listen_started)
            self.audio_demod_dialog.listenStopped.connect(self._on_audio_listen_stopped)
            self.audio_demod_dialog.retuneRequested.connect(self._on_audio_retune_requested)
        else:
            self.audio_demod_dialog.cf_spin.setValue(freq_mhz)
        self.audio_demod_dialog.show()
        self.audio_demod_dialog.raise_()
        self.audio_demod_dialog.activateWindow()

    def inspect_rtsa_carrier(self, freq_mhz: float):
        if not self._mode_available("RTA", "Real-time spectrum analysis"):
            return
        self.nav_rail.set_active_mode(3)
        self.rtsa_panel.cf_spin.setValue(freq_mhz)

    def _on_temperature_updated(self, slot_id: str, temp_c: float):
        self._slot_hw(slot_id)["temp_c"] = temp_c
        if self._is_focused_slot(slot_id):
            self.top_bar.set_device_temperature(temp_c)
        self._refresh_slot_readouts()

    def _on_power_updated(self, slot_id: str, power: dict):
        hw = self._slot_hw(slot_id)
        hw["power"] = power
        if self._is_focused_slot(slot_id):
            self.top_bar.set_power_state(power, hw.get("endorsements", {}).get("interface", "USB Direct"))
        self._refresh_slot_readouts()

    def _on_fan_state_requested(self, fan_state: int, threshold_temp: float):
        if hasattr(self, 'multi_device_manager'):
            self.multi_device_manager.set_fan_state(fan_state, threshold_temp)
            state_names = {0: "Forced On", 1: "Forced Off", 2: f"Automatic ({threshold_temp:.0f}°C)"}
            name = state_names.get(fan_state, str(fan_state))
            self.top_bar.dev_label.setText(f"Fan Mode: {name}")

    def _on_rtsa_params_changed(self, params: dict):
        if hasattr(self, 'rtsa_view'):
            self.rtsa_view.set_persistence_decay(params.get("decay", 0.90))
        if hasattr(self, 'multi_device_manager'):
            self.multi_device_manager.configure_rta(
                center_freq_hz=params.get("center_freq_hz", 539e6),
                decimate_factor=params.get("decimate_factor", 1),
                ref_level=params.get("ref_level", 0.0),
                trig_src=params.get("trigger_source", 2),
                trig_mode=params.get("trigger_mode", 0),
                trig_time=params.get("trigger_time", 0.05),
                preamp=params.get("preamp", 0x00),
                atten=params.get("atten", 0)
            )

    def _on_det_params_changed(self, params: dict, slot_id: str = None):
        if hasattr(self, 'multi_device_manager'):
            self.multi_device_manager.configure_det(
                target_slot_id=slot_id,
                center_freq_hz=params.get("center_freq_hz", 1925e6),
                decimate_factor=params.get("decimate_factor", 2),
                ref_level=params.get("ref_level", 0.0),
                trig_src=params.get("trigger_source", 2),
                trig_mode=params.get("trigger_mode", 0),
                trig_length=params.get("trigger_length", 16240),
                trig_level=params.get("trigger_level"),
                atten=params.get("atten") if params.get("own_gain") else None,
                preamp=params.get("preamp") if params.get("own_gain") else None
            )

    def open_audio_demod_dialog(self):
        if not self._mode_available("IQS", "Audio demodulation"):
            return
        # Carry over center frequency from Demodulation panel if active, else from RF & Sweep panel
        if self.nav_rail.btn_group.checkedId() == 5:
            cf_hz = self.demod_panel.cf_spin.value() * 1e6
        else:
            cf_hz = self.sweep_panel.center_spin.value() * 1e6

        if self.audio_demod_dialog is None:
            self.audio_demod_dialog = AudioDemodDialog(initial_freq_hz=cf_hz, parent=self)
            self.audio_demod_dialog.listenStarted.connect(self._on_audio_listen_started)
            self.audio_demod_dialog.listenStopped.connect(self._on_audio_listen_stopped)
            self.audio_demod_dialog.retuneRequested.connect(self._on_audio_retune_requested)
        else:
            self.audio_demod_dialog.cf_spin.setValue(cf_hz / 1e6)

        self.audio_demod_dialog.show()
        self.audio_demod_dialog.raise_()
        self.audio_demod_dialog.activateWindow()

    def _on_audio_listen_started(self, freq_hz: float, mode: str):
        if not self.is_connected or not self._mode_available("IQS", "Audio demodulation"):
            return
        self._pre_audio_mode = self._last_operating_mode
        self._last_operating_mode = "IQS"
        self.multi_device_manager.set_operating_mode("IQS")
        self.multi_device_manager.configure_iqs(
            center_freq_hz=freq_hz,
            decimate_factor=64, # ~2 MS/s baseband for audio extraction (125 MS/s / 64 on the SAN-60)
            ref_level=0.0,
            trig_src=2,
            trig_length=16384,
            preamp=0x00,
            atten=0,
            continuous=True  # gap-free IQ for audio
        )
        self.top_bar.dev_label.setText(f"Audio Demod: {mode.upper()} @ {freq_hz/1e6:.3f} MHz")

    def _on_audio_listen_stopped(self):
        if not self.is_connected:
            return
        self.top_bar.dev_label.setText("Audio Demod Stopped")
        if self._pre_audio_mode == "SWP":
            self.resume_rf_sweep()
        elif self._pre_audio_mode == "IQS" and self.nav_rail.btn_group.checkedId() == 5 and self.demod_panel.is_active:
            params = self.demod_panel.get_params()
            self._on_demod_requested(params)
        else:
            self.resume_rf_sweep()

    def _on_audio_retune_requested(self, freq_hz: float):
        if not self.is_connected:
            return
        self.multi_device_manager.configure_iqs(
            center_freq_hz=freq_hz,
            decimate_factor=64,
            ref_level=0.0,
            trig_src=2,
            trig_length=16384,
            preamp=0x00,
            atten=0,
            continuous=True
        )
        if self.audio_demod_dialog:
            mode = self.audio_demod_dialog.mode_combo.currentData()
            self.top_bar.dev_label.setText(f"Audio Demod: {mode.upper()} @ {freq_hz/1e6:.3f} MHz")

    def _on_view_mode_changed(self, mode: str):
        if self.nav_rail.btn_group.checkedId() in (2, 3, 4, 5):
            # If in MSCAN(2), RTSA(3), DET(4), or Demodulation(5), selecting a view mode combo switches back to RF & Sweep
            self.nav_rail.set_active_mode(0)
            return
            
        dual_spectrum = mode == self.top_bar.DUAL_SPECTRUM
        if dual_spectrum != self._dual_spectrum:
            self._dual_spectrum = dual_spectrum
            self.spectrum_view_b.setVisible(dual_spectrum)
            self.spectrum_view.title_label.setText("ANTENNA A" if dual_spectrum else self._spectrum_title)
            self.top_bar.set_antenna_view_locked(dual_spectrum)
            self._reset_b_holds()
            for name in self.B_VIEW_TRACES:      # the same traces, in the same colours, as antenna A's view
                self.spectrum_view_b.set_trace_visible(name, self.sweep_panel.trace_rows[name]["cb"].isChecked())
                self.spectrum_view_b.curves[name].setPen(self.spectrum_view.curves[name].opts["pen"])
            if hasattr(self, "_mask_drawn"):
                self._mask_draw_time = 0.0
                self._draw_carrier_masks()      # antenna B's view gets (or loses) its ETSI masks now
        if dual_spectrum:
            self.viewport_stack.setCurrentIndex(0)
            self.waterfall_view.hide()
            self.spectrum_view.show()
            self.view_v_splitter.setSizes([0, 350, 350])
        elif mode == "Dual View":
            self.viewport_stack.setCurrentIndex(0)
            self.waterfall_view.show()
            self.spectrum_view.show()
            self.view_v_splitter.setSizes([340, 360, 0])
        elif mode == "Multi-Row Waterfall":
            self.viewport_stack.setCurrentIndex(1)
            if hasattr(self, 'waterfall_buffer') and self.waterfall_buffer is not None:
                start_mhz = self.sweep_panel.start_spin.value()
                stop_mhz = self.sweep_panel.stop_spin.value()
                self.multi_row_view.update_sweep_data(self._waterfall_ordered(), start_mhz, stop_mhz)
        elif mode == "Spectrum Only":
            self.viewport_stack.setCurrentIndex(0)
            self.waterfall_view.hide()
            self.spectrum_view.show()
        elif mode == "Waterfall Only":
            self.viewport_stack.setCurrentIndex(0)
            self.spectrum_view.hide()
            self.waterfall_view.show()

    def _on_multi_row_mode_changed(self, num_rows: int):
        if hasattr(self, 'waterfall_buffer') and self.waterfall_buffer is not None:
            start_mhz = self.sweep_panel.start_spin.value()
            stop_mhz = self.sweep_panel.stop_spin.value()
            self.multi_row_view.update_sweep_data(self._waterfall_ordered(), start_mhz, stop_mhz)

    def _on_multi_row_tune_requested(self, freq_mhz: float):
        current_span = self.sweep_panel.span_spin.value()
        half_span = current_span / 2.0
        new_start = max(0.001, freq_mhz - half_span)
        new_stop = new_start + current_span
        self.sweep_panel.start_spin.setValue(new_start)
        self.sweep_panel.stop_spin.setValue(new_stop)
        self.apply_frequencies()

    def _update_fps_calc(self):
        now = time.time()
        dt = now - self.last_fps_time
        if dt > 0.4:
            fps = self.frame_count / dt
            self.top_bar.update_fps(fps)
            self.frame_count = 0
            self.last_fps_time = now

    # --- Telemetry HUD & Crosshairs ---
    def _on_spectrum_mouse_moved(self, x_val: float, y_val: float):
        self.waterfall_view.v_line.setPos(x_val)
        self._update_hud_readout(x_val, y_val, target_view=self.spectrum_view)

    def _on_waterfall_mouse_moved(self, x_val: float, y_val: float):
        self.spectrum_view.v_line.setPos(x_val)
        self._update_hud_readout(x_val, None, target_view=self.spectrum_view)

    def _on_demod_spectrum_mouse_moved(self, x_val: float, y_val: float):
        self.demod_view.waterfall_view.v_line.setPos(x_val)
        self._update_hud_readout(x_val, y_val, target_view=self.demod_view.spectrum_view)

    def _on_demod_waterfall_mouse_moved(self, x_val: float, y_val: float):
        self.demod_view.spectrum_view.v_line.setPos(x_val)
        self._update_hud_readout(x_val, None, target_view=self.demod_view.spectrum_view)

    def _update_hud_readout(self, freq_mhz: float, power_dbm: float = None, target_view=None):
        # Match TV Channel or Band
        matched_tag = None
        current_stds = TV_CHANNEL_STANDARDS.get(self.current_region, [])
        for band in current_stds:
            if "custom_items" in band:
                for c in band["custom_items"]:
                    if c["start"] <= freq_mhz <= c["stop"]:
                        matched_tag = c.get("display_name", c.get("label"))
                        break
            elif "start_ch" in band:
                start_f = band["start_freq"]
                spacing = band["spacing"]
                start_ch = band["start_ch"]
                end_ch = band["end_ch"]
                if start_f <= freq_mhz <= start_f + (end_ch - start_ch + 1) * spacing:
                    ch_num = int((freq_mhz - start_f) // spacing) + start_ch
                    matched_tag = f"DTV Ch {ch_num}"
                    break
        if target_view is not None:
            target_view.update_hud(freq_mhz, power_dbm, matched_tag)
        else:
            self.spectrum_view.update_hud(freq_mhz, power_dbm, matched_tag)
            if hasattr(self, 'demod_view'):
                self.demod_view.spectrum_view.update_hud(freq_mhz, power_dbm, matched_tag)

    # --- Frequency Coupling & Views ---
    def _on_start_stop_changed(self):
        if self._updating_freqs: return
        self._updating_freqs = True
        start = self.sweep_panel.start_spin.value()
        stop = self.sweep_panel.stop_spin.value()
        if stop < start:
            stop = start + 1.0
            self.sweep_panel.stop_spin.setValue(stop)
        self.sweep_panel.center_spin.setValue((start + stop) / 2.0)
        self.sweep_panel.span_spin.setValue(stop - start)
        self._updating_freqs = False

    def _on_center_changed(self):
        if self._updating_freqs: return
        self._updating_freqs = True
        center = self.sweep_panel.center_spin.value()
        span = self.sweep_panel.span_spin.value()
        start = center - span / 2.0
        stop = center + span / 2.0
        self.sweep_panel.start_spin.setValue(start)
        self.sweep_panel.stop_spin.setValue(stop)
        self._updating_freqs = False

    def _on_span_changed(self):
        if self._updating_freqs: return
        self._updating_freqs = True
        center = self.sweep_panel.center_spin.value()
        span = self.sweep_panel.span_spin.value()
        start = center - span / 2.0
        stop = center + span / 2.0
        self.sweep_panel.start_spin.setValue(start)
        self.sweep_panel.stop_spin.setValue(stop)
        self._updating_freqs = False

    def _on_view_start_stop_changed(self):
        if self._updating_view_freqs: return
        self._updating_view_freqs = True
        v_start = self.sweep_panel.view_start_spin.value()
        v_stop = self.sweep_panel.view_stop_spin.value()
        if v_stop < v_start:
            v_stop = v_start + 1.0
            self.sweep_panel.view_stop_spin.setValue(v_stop)
        self.sweep_panel.view_center_spin.setValue((v_start + v_stop) / 2.0)
        self.sweep_panel.view_span_spin.setValue(v_stop - v_start)
        self._updating_view_freqs = False

    def _on_view_center_changed(self):
        if self._updating_view_freqs: return
        self._updating_view_freqs = True
        center = self.sweep_panel.view_center_spin.value()
        span = self.sweep_panel.view_span_spin.value()
        self.sweep_panel.view_start_spin.setValue(center - span / 2.0)
        self.sweep_panel.view_stop_spin.setValue(center + span / 2.0)
        self._updating_view_freqs = False

    def _on_view_span_changed(self):
        if self._updating_view_freqs: return
        self._updating_view_freqs = True
        center = self.sweep_panel.view_center_spin.value()
        span = self.sweep_panel.view_span_spin.value()
        self.sweep_panel.view_start_spin.setValue(center - span / 2.0)
        self.sweep_panel.view_stop_spin.setValue(center + span / 2.0)
        self._updating_view_freqs = False

    def _on_view_range_changed(self, r):
        if not self._initializing:
            x_min, x_max = r[0]
            if x_max > x_min:
                self._updating_view_freqs = True
                self.sweep_panel.view_start_spin.setValue(x_min)
                self.sweep_panel.view_stop_spin.setValue(x_max)
                self.sweep_panel.view_center_spin.setValue((x_min + x_max) / 2.0)
                self.sweep_panel.view_span_spin.setValue(x_max - x_min)
                self._updating_view_freqs = False
                self._check_span_correlation()

    def _check_span_correlation(self):
        swp_span = self.sweep_panel.span_spin.value()
        view_span = self.sweep_panel.view_span_spin.value()
        exceeds = view_span > (swp_span * 1.02)
        self.spectrum_view.set_span_alert(exceeds)

    def apply_frequencies(self):
        start_mhz = self.sweep_panel.start_spin.value()
        stop_mhz = self.sweep_panel.stop_spin.value()
        if hasattr(self, 'multi_row_view'):
            self.multi_row_view.set_sweep_range(start_mhz, stop_mhz)
        if hasattr(self, 'multi_device_manager'):
            if self.multi_device_manager.topology == MultiDeviceTopology.INDEPENDENT:
                self.multi_device_manager.set_slot_sweep_range(
                    self.multi_device_manager.focused_slot_id, int(start_mhz * 1e6), int(stop_mhz * 1e6)
                )
            else:
                self.multi_device_manager.set_global_sweep_range(int(start_mhz * 1e6), int(stop_mhz * 1e6))
        if self.sweep_panel.link_view_check.isChecked():
            self.sweep_panel.view_start_spin.setValue(start_mhz)
            self.sweep_panel.view_stop_spin.setValue(stop_mhz)
            self.apply_view_frequencies()
        self._check_span_correlation()
        if hasattr(self, "_mask_drawn") and not self.is_sweeping:
            self._draw_carrier_masks()          # the shapes follow the new range until a sweep arrives

    def apply_view_frequencies(self):
        v_start = self.sweep_panel.view_start_spin.value()
        v_stop = self.sweep_panel.view_stop_spin.value()
        self.spectrum_view.set_view_range(v_start, v_stop)
        if hasattr(self, 'demod_view'):
            self.demod_view.spectrum_view.set_view_range(v_start, v_stop)
        self._check_span_correlation()

    def _on_view_moved_by_hand(self, *_):
        if self.sweep_panel.link_view_check.isChecked():
            self._link_follow_timer.start()

    def _sweep_follows_view(self):
        """
        The view is linked to the analyzer sweep and was zoomed or dragged on the plot:
        the sweep is set to what the view now shows (within what the analyzer can tune;
        the view then settles on the sweep it got). Views moved by the program, such as
        a click on a TV channel, do not retune the analyzer.
        """
        sp = self.sweep_panel
        if not sp.link_view_check.isChecked():
            return
        x_min, x_max = self.spectrum_view.plot_widget.viewRange()[0]
        if not x_max > x_min:
            return
        if abs(x_min - sp.start_spin.value()) < 1e-3 and abs(x_max - sp.stop_spin.value()) < 1e-3:
            return
        sp.start_spin.setValue(x_min)
        sp.stop_spin.setValue(x_max)
        sp.frequenciesChanged.emit()        # as if the range had been typed in

    def _on_link_view_toggled(self, linked: bool):
        if linked:
            self.sweep_panel.view_start_spin.setValue(self.sweep_panel.start_spin.value())
            self.sweep_panel.view_stop_spin.setValue(self.sweep_panel.stop_spin.value())
            self.apply_view_frequencies()

    # --- Amplitude, BW & Sweep Configuration ---
    def _on_scale_div_changed(self, scale_div: float):
        ref = self.sweep_panel.ref_level_spin.value()
        self.spectrum_view.set_amplitude_scale(ref, scale_div)
        if hasattr(self, 'demod_view') and hasattr(self.demod_view, 'spectrum_view'):
            self.demod_view.spectrum_view.set_amplitude_scale(ref, scale_div)
        # A finer scale shows fewer dB: keep the signal in view
        self.auto_reference_level(quiet=True)

    def apply_amplitude_settings(self):
        ref = self.sweep_panel.ref_level_spin.value()
        scale_div = self.sweep_panel.scale_div
        self.spectrum_view.set_amplitude_scale(ref, scale_div)
        if hasattr(self, 'demod_view') and hasattr(self.demod_view, 'spectrum_view'):
            self.demod_view.spectrum_view.set_amplitude_scale(ref, scale_div)

        if not self.is_connected: return
        atten = self.sweep_panel.attenuation
        preamp = self.sweep_panel.preamp_combo.currentData()
        if preamp is None:
            preamp = 0
        ifagc = 1 if self.sweep_panel.ifagc_check.isChecked() else 0
        target = self.sweep_panel.ifagc_target_spin.value()
        period = self.sweep_panel.ifagc_period_spin.value()
        if_out = 1 if self.sweep_panel.if_out_check.isChecked() else 0
        
        target_slot = self._settings_target()
        self.multi_device_manager.set_amplitude_params(ref, atten, preamp, ifagc, target, period, if_out, target_slot_id=target_slot)
        self._store_panel_settings()

    def auto_reference_level(self, quiet: bool = False):
        """
        Put the reference level (the top of the Y axis) just above the strongest
        signal: on a graticule line, with at least half a division of headroom,
        so the trace is in view without touching the top. Uses the latest sweep,
        and the Max Hold trace while that is shown.
        """
        peaks = []
        if self._last_sweep is not None and len(self._last_sweep[1]):
            peaks.append(float(np.max(self._last_sweep[1])))
        if self.max_hold_data is not None and len(self.max_hold_data) \
                and self.sweep_panel.trace_rows["Max. Hold"]["cb"].isChecked():
            peaks.append(float(np.max(self.max_hold_data)))
        peaks = [p for p in peaks if math.isfinite(p)]
        if not peaks:
            if not quiet:
                self.top_bar.flash_status("Auto Ref. Level: no sweep to measure yet")
            return
        spin = self.sweep_panel.ref_level_spin
        div = self.sweep_panel.scale_div
        new_ref = math.ceil((max(peaks) + 0.5 * div) / div) * div
        new_ref = min(max(new_ref, spin.minimum()), spin.maximum())
        if abs(new_ref - spin.value()) > 1e-9:
            spin.setValue(new_ref)      # applies it (display, and the analyzer's reference level)

    def apply_bw_settings(self):
        if not self.is_connected: return
        rbw_mode = self.sweep_panel.rbw_mode
        rbw_hz = self.sweep_panel.rbw_hz
        vbw_mode = self.sweep_panel.vbw_mode
        vbw_hz = self.sweep_panel.vbw_hz
        target_slot = self._settings_target()
        self.multi_device_manager.set_bandwidth_params(rbw_mode, rbw_hz, vbw_mode, vbw_hz, target_slot_id=target_slot)
        self._store_panel_settings()

    def apply_sweep_settings(self):
        if not self.is_connected: return
        swt_mode = self.sweep_panel.swt_mode_combo.currentIndex()
        swt_val = self.sweep_panel.sweep_time_spin.value()
        spur = self.sweep_panel.spur_combo.currentIndex()
        window = self.sweep_panel.window_combo.currentIndex()
        target_slot = self._settings_target()
        self.multi_device_manager.set_sweep_params(swt_mode, swt_val, spur, window, target_slot_id=target_slot)
        self._store_panel_settings()

    def apply_detect_settings(self):
        if not self.is_connected: return
        det = self.sweep_panel.detector_combo.currentIndex()
        tdet = self.sweep_panel.trace_detector_combo.currentIndex()
        if self._last_detect is not None and self._last_detect != (det, tdet):
            self._holds_restart_pending = True          # acted on when the analyzer has re-armed
        self._last_detect = (det, tdet)
        target_slot = self._settings_target()
        self.multi_device_manager.set_detect_params(det, tdet, target_slot_id=target_slot)
        self._store_panel_settings()

    # --- Traces ---
    B_VIEW_TRACES = ("Max. Hold", "Min. Hold", "Average")      # its live trace is "Trace B"

    def _on_top_trace_toggled(self, name: str, active: bool):
        self.spectrum_view.set_trace_visible(name, active)
        if name in self.B_VIEW_TRACES:
            self.spectrum_view_b.set_trace_visible(name, active)
        if name in self.sweep_panel.trace_rows:
            self.sweep_panel.trace_rows[name]["cb"].blockSignals(True)
            self.sweep_panel.trace_rows[name]["cb"].setChecked(active)
            self.sweep_panel.trace_rows[name]["cb"].blockSignals(False)

    def _on_panel_trace_toggled(self, name: str, active: bool):
        self.spectrum_view.set_trace_visible(name, active)
        if name in self.B_VIEW_TRACES:
            self.spectrum_view_b.set_trace_visible(name, active)
        self.top_bar.set_trace_active(name, active)

    def _on_trace_freeze_toggled(self, name: str, frozen: bool):
        pass # state is read dynamically in sweep data handler

    def _on_trace_color_changed(self, name: str, color: QColor):
        self.spectrum_view.set_trace_color(name, color)
        if name in self.B_VIEW_TRACES:
            self.spectrum_view_b.set_trace_color(name, color)

    def _on_avg_sweeps_changed(self, sweeps: int):
        self.avg_history = []
        self._b_holds["avg"] = []

    # --- Region & Presets ---
    def change_region(self, region_name: str):
        if region_name in self.region_configs:
            self.current_region = region_name
            self.settings.setValue("current_region", region_name)
            self.dtv_stations, self.lmr_stations, self.station_info = {}, {}, {}
            self._dtv_results.clear()
            self._dtv_override.clear()
            self.dtv_detector.reset()
            self._dtv_table_mode = self._dtv_scanned_key = None
            self.dtv_panel.show_stations([])
            for view in (self.spectrum_view, self.waterfall_view, self.multi_row_view, self.rtsa_view):
                view.clear_channel_masks()      # the other region's bands
            self._update_region_ui()

    def _update_region_ui(self):
        presets = self.region_configs.get(self.current_region, [])
        self.dtv_panel.set_region(self.current_region)
        self.sweep_panel.update_quick_settings_labels(presets)
        
        # Redraw Channel Markers
        standard = TV_CHANNEL_STANDARDS.get(self.current_region, [])
        self.spectrum_view.channel_bar.draw_channels(standard, self._x_multiplier)
        self.spectrum_view_b.channel_bar.draw_channels(standard, self._x_multiplier)
        self.waterfall_view.channel_bar.draw_channels(standard, self._x_multiplier)
        
        if self.current_region == "North America":
            self.active_channels = dict(DEFAULT_NORTH_AMERICA_ACTIVE)
        else:
            self.active_channels = dict(DEFAULT_EUROPE_ACTIVE)
        ps_dict = self._public_safety_channels()
        self.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_view_b.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_view.update_channel_masks(self.active_channels, standard, ps_dict, self.station_info)
        self.waterfall_view.update_channel_masks(self.active_channels, standard, ps_dict)
        if hasattr(self, 'multi_row_view'):
            self.multi_row_view.set_channels(standard, self._x_multiplier, self.active_channels)
            self.multi_row_view.update_channel_masks(self.active_channels, standard, ps_dict)
        if hasattr(self, 'rtsa_view'):
            self.rtsa_view.channel_bar.draw_channels(standard, self._x_multiplier)
            self.rtsa_view.set_active_channels(self.active_channels, ps_dict)
            self.rtsa_view.update_channel_masks(self.active_channels, standard, ps_dict, self.station_info)
        if hasattr(self, 'demod_view'):
            self.demod_view.spectrum_view.channel_bar.draw_channels(standard, self._x_multiplier)
            self.demod_view.waterfall_view.channel_bar.draw_channels(standard, self._x_multiplier)
            self.demod_view.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
            self.demod_view.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)

    # --- Quick band presets ---
    # Solo off (the default): the sweep covers all selected bands, from the lowest
    # start to the highest stop. Solo on: one band at a time, and a start/stop typed
    # by hand deselects the bands.
    def _on_quick_setting_toggled(self, idx: int, checked: bool):
        presets = self.region_configs.get(self.current_region, [])
        if not 0 <= idx < len(presets):
            return
        sp = self.sweep_panel
        if sp.solo_qs_btn.isChecked():
            # Clicking the selected band again deselects it and leaves the span alone
            sp.set_checked_quick_settings([idx] if checked else [])
        self._last_quick_idx = idx
        self._apply_quick_bands()

    def _apply_quick_bands(self):
        presets = self.region_configs.get(self.current_region, [])
        bands = [presets[i] for i in self.sweep_panel.checked_quick_settings() if i < len(presets)]
        if not bands:
            return                      # nothing selected: the span stays as it is
        self.sweep_panel.start_spin.setValue(min(float(p["start"]) for p in bands))
        self.sweep_panel.stop_spin.setValue(max(float(p["stop"]) for p in bands))
        self.apply_frequencies()

    def _on_quick_solo_toggled(self, solo: bool):
        self.settings.setValue("quick_band_solo", solo)
        sp = self.sweep_panel
        selected = sp.checked_quick_settings()
        if solo and len(selected) > 1:
            # Keep the band clicked last
            last = getattr(self, "_last_quick_idx", None)
            sp.set_checked_quick_settings([last if last in selected else selected[0]])
            self._apply_quick_bands()

    def _on_custom_span_entered(self):
        """Start/stop/centre/span edited by hand: in solo, bands that are no longer the span are deselected."""
        sp = self.sweep_panel
        if not sp.solo_qs_btn.isChecked():
            return
        presets = self.region_configs.get(self.current_region, [])
        start, stop = sp.start_spin.value(), sp.stop_spin.value()
        keep = [i for i in sp.checked_quick_settings() if i < len(presets)
                and abs(float(presets[i]["start"]) - start) < 0.001 and abs(float(presets[i]["stop"]) - stop) < 0.001]
        sp.set_checked_quick_settings(keep)

    def open_quick_settings_editor(self):
        presets = self.region_configs.get(self.current_region, [])
        dlg = QuickSettingsDialog(self.current_region, presets, self)
        if dlg.exec():
            self.region_configs[self.current_region] = dlg.buttons_data
            self.settings.setValue("regions", json.dumps(self.region_configs))
            self._update_region_ui()

    def open_launch_settings(self):
        traces = self._exportable_traces()
        dlg = LaunchSettingsDialog(
            self.region_configs, self.current_region,
            self.sweep_panel.start_spin.value(), self.sweep_panel.stop_spin.value(),
            link_view=self.sweep_panel.link_view_check.isChecked(),
            export_traces=[(name, label, "" if name in traces else why)
                           for name, label, why in self._export_choices(traces)],
            parent=self
        )
        dlg.exportRequested.connect(lambda names: self._export_spectrum_csv(names, dlg))
        if dlg.exec():
            res = dlg.get_settings()
            self.settings.setValue("launch_default_region", res["default_region"])
            if res["default_region"] != self.current_region:
                # The region is chosen here (it used to have a selector in the top bar too)
                self.change_region(res["default_region"])
                self.top_bar.set_regions(list(self.region_configs.keys()), self.current_region)
            self.settings.setValue("launch_sweep_start", res["sweep_start"])
            self.settings.setValue("launch_sweep_stop", res["sweep_stop"])
            self.settings.setValue("launch_link_view", res["link_view"])

    # --- Spectrum export (core/spectrum_export.py: the layout SAStudio4 exports) ---
    def _exportable_traces(self) -> dict:
        """{trace name: (frequencies Hz, levels dBm)} for the traces that are on and have data."""
        if self._last_sweep is None or len(self._last_sweep[0]) < 2:
            return {}
        f, live = self._last_sweep
        rows = self.sweep_panel.trace_rows
        on = lambda name: rows[name]["cb"].isChecked()
        out = {}
        if on("Real-Time"):
            out["Real-Time"] = (f, live)
        if on("Max. Hold") and self.max_hold_data is not None and len(self.max_hold_data) == len(f):
            out["Max. Hold"] = (f, self.max_hold_data)
        if on("Min. Hold") and self.min_hold_data is not None and len(self.min_hold_data) == len(f):
            out["Min. Hold"] = (f, self.min_hold_data)
        if on("Average") and self.avg_history and len(self.avg_history[0]) == len(f):
            out["Average"] = (f, np.mean(self.avg_history, axis=0))
        return out

    def _export_choices(self, traces: dict) -> list:
        """[(trace name, label, why it cannot be exported)] for the settings dialog."""
        rows = self.sweep_panel.trace_rows
        choices = []
        for name, label in (("Real-Time", "Live"), ("Max. Hold", "Max hold"), ("Min. Hold", "Min hold"), ("Average", "Average")):
            if self._last_sweep is None:
                why = "No sweep yet: connect an analyzer and sweep first."
            elif not rows[name]["cb"].isChecked():
                why = f"The {label} trace is switched off (the trace buttons in the top bar)."
            else:
                why = f"The {label} trace has no data yet."
            choices.append((name, label, why))
        return choices

    def _export_spectrum_csv(self, names: list, dlg=None):
        """Write the chosen traces, one file each, into a folder the user picks. Returns the paths."""
        from datetime import datetime
        from PyQt6.QtWidgets import QFileDialog
        from core import spectrum_export
        traces = self._exportable_traces()
        names = [n for n in names if n in traces]
        say = (lambda text, ok=True: dlg.set_export_result(text, ok)) if dlg is not None else (lambda text, ok=True: self.top_bar.flash_status(text, 6000))
        if not names:
            say("Nothing to export: no trace that is switched on has data.", False)
            return []
        start = self.settings.value("export_folder", "") or os.path.expanduser("~/Documents")
        folder = QFileDialog.getExistingDirectory(dlg or self, "Export spectrum CSV to folder", start)
        if not folder:
            return []
        self.settings.setValue("export_folder", folder)
        when = datetime.now()               # one time stamp for the set: the files belong together
        try:
            paths = [spectrum_export.write_csv(folder, n, *traces[n], when=when) for n in names]
        except OSError as e:
            say(f"Export failed: {e}", False)
            return []
        say(f"Exported {len(paths)} file{'' if len(paths) == 1 else 's'} to {folder}: " + ", ".join(p.name for p in paths))
        return paths

    # --- DTV & Broadcast Coordination ---
    def _on_fcc_lookup(self, zip_code: str):
        """Look up nearby broadcast stations on a worker thread (the FCC lookup is
        a network call, and geocoding may download postcode data on first use)."""
        region = self.current_region
        if region not in ("North America", "UK", "Spain", "Portugal"):
            self.dtv_panel.set_lookup_status("No station database for this region.")
            return
        self.dtv_panel.set_lookup_busy(True)
        self.dtv_panel.set_lookup_status("Looking up stations…")

        def work():
            info = {}
            try:
                if region == "North America":
                    stations = self.fcc_db.query_by_zip(zip_code, radius_miles=65)
                    info = dict(self.fcc_db.last_lookup)
                elif region == "Spain":
                    stations, plan = self.spain_tv.query_by_postcode(zip_code)
                    info = {"source": "spain_plan", "fetched_at": None, "plan": plan,
                            "error": None if stations else "postcode not found in the national plan"}
                elif region == "Portugal":
                    stations = self.portugal_tv.query_by_postcode(zip_code, radius_km=80)
                    info = {"source": "portugal", "fetched_at": None, "dated": self.portugal_tv.data.get("dated"),
                            "error": None if stations else "postcode not found, or no transmitter within 80 km"}
                else:
                    stations = self.ofcom_db.query_by_postcode(zip_code, radius_km=80)
                    info = {"source": "ofcom", "fetched_at": self.ofcom_db.get_last_update_time() or None,
                            "error": None if self.ofcom_db.has_data() else "no Ofcom data imported",
                            "ofcom": self.ofcom_db.info()}
            except Exception as e:
                stations, info = [], {"source": None, "fetched_at": None, "error": str(e)}
            self.stationLookupFinished.emit(stations, info)

        threading.Thread(target=work, daemon=True).start()

    def _on_update_uk_data(self):
        """Import Ofcom's TV transmitter spreadsheet. Ofcom's site blocks automated
        downloads, so the user downloads it in their browser and picks the file."""
        box = QMessageBox(self)
        box.setWindowTitle("Update UK Transmitter Data")
        box.setText("Ofcom publishes UK television transmitter details as a spreadsheet.")
        box.setInformativeText(
            f"In use now: {self._ofcom_data_text()}.\n\n"
            "To replace it with a newer one:\n"
            "1. Open Ofcom's page and download “Television transmitter frequency data” (.xlsx).\n"
            "2. Choose Import and select the downloaded file.")
        open_btn = box.addButton("Open Ofcom Page", QMessageBox.ButtonRole.ActionRole)
        import_btn = box.addButton("Import File…", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        while True:
            box.exec()
            if box.clickedButton() is open_btn:
                QDesktopServices.openUrl(QUrl(OFCOM_TRANSMITTER_PAGE))
                continue  # keep the dialog open for the import step
            break
        if box.clickedButton() is not import_btn:
            return
        start_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        path, _ = QFileDialog.getOpenFileName(self, "Ofcom Transmitter Spreadsheet", start_dir,
                                              "Excel Workbook (*.xlsx)")
        if not path:
            return
        try:
            count = self.ofcom_db.import_excel(path)
        except ValueError as e:
            QMessageBox.warning(self, "Import Failed", str(e))
            return
        self.dtv_panel.set_lookup_status(f"Imported {count} UK transmitter records: {self._ofcom_data_text()}.")

    def _ofcom_data_text(self, info=None) -> str:
        """Which Ofcom data is in use: the copy shipped with fReqon, or the user's import, and its date."""
        info = info or self.ofcom_db.info()
        if not info["records"]:
            return "no UK transmitter data"
        try:
            dated = datetime.strptime(info["data_date"], "%Y-%m-%d").strftime("%-d %b %Y")
        except (TypeError, ValueError):
            dated = None
        which = "Ofcom data shipped with fReqon" if info["source"] == "bundled" else "Ofcom data you imported"
        return which + (f" (Ofcom's file of {dated})" if dated else "")

    def _describe_lookup(self, count, info):
        src, when, err = info.get("source"), info.get("fetched_at"), info.get("error")
        age = datetime.fromtimestamp(when).strftime("%Y-%m-%d %H:%M") if when else None
        if src == "live":
            return f"{count} stations · live FCC data"
        if src == "cache":
            return f"{count} stations · offline, FCC data cached {age}"
        if src == "bundled":
            return f"{count} stations · offline, bundled FCC data (may be out of date)"
        if src == "spain_plan":
            plan = info.get("plan") or {}
            if err or not plan.get("areas"):
                return "Postcode not found in Spain's national TV plan (five digits, e.g. 28013)."
            if plan.get("exact"):
                return (f"{count} multiplex channels planned for the {plan['areas'][0]} area · "
                        f"Plan Técnico Nacional de la TDT (no transmitter list is published)")
            return (f"Could not tell which area of the province this postcode is in: showing the channels of "
                    f"{', '.join(plan['areas'])} ({count}) · Plan Técnico Nacional de la TDT")
        if src == "portugal":
            if err:
                return "No transmitter found: enter a Portuguese postcode such as 1000-001 (or its first four digits)."
            dated = f", {info['dated']}" if info.get("dated") else ""
            return f"{count} transmitters within 80 km · ANACOM / network operator list{dated}"
        if src == "ofcom":
            if err:
                return "No UK transmitter data yet: use Update UK Data to import Ofcom's spreadsheet."
            return f"{count} transmitter records · {self._ofcom_data_text(info.get('ofcom'))}"
        return f"Lookup failed: {err}" if err else f"{count} stations"

    def _on_station_lookup_finished(self, stations, info):
        self.dtv_panel.set_lookup_busy(False)
        self.dtv_panel.set_lookup_status(self._describe_lookup(len(stations), info),
                                         warn=info.get("source") not in ("live", "ofcom", "spain_plan", "portugal")
                                         or bool(info.get("error")) or info.get("plan", {}).get("exact") is False)
        # Transmitters by TV channel. Public-safety LMR (T-Band) entries are kept
        # apart: their channels are drawn red and are not judged by the detector.
        self.dtv_stations, self.lmr_stations = {}, {}
        for st in stations:
            ch = st.get("channel")
            if ch is not None:
                (self.lmr_stations if st.get("is_public_safety") else self.dtv_stations).setdefault(ch, []).append(st)
        self.station_info = self._station_mask_info()
        self._dtv_override.clear()

        # Masks go on for what blocks a channel here: land mobile radio channels
        # always, and a TV channel when a station on it is strong enough, judged from
        # the licence alone (core/propagation.py): a full-power station by its power
        # and distance, a low-power one only when practically next door, and nothing
        # that is not licensed yet. In a city every channel has some licensed station
        # within range; most of them are not worth giving a channel up for. Any row
        # can be ticked or unticked by hand. Masks from an earlier lookup or
        # detection are dropped.
        # (the low-power station class is a US one; elsewhere a relay is judged by its field strength)
        us = self.current_region == "North America"
        likely = {ch: any(worth_masking(st.get("erp"), st.get("distance_km"), ch, st.get("status"), low_power_class=us)[0]
                          for st in sts)
                  for ch, sts in self.dtv_stations.items()}
        for ch, _f0, _f1 in self._tv_channels():
            if ch in self.lmr_stations:
                self.active_channels[ch] = True
            elif self.dtv_detect_active and ch in self._dtv_results:
                self.active_channels[ch] = bool(self._dtv_results[ch]["occupied"])   # detection is running: it decides
            else:
                self.active_channels[ch] = likely.get(ch, False)
        if self.tband_detect_active:        # the scan's land mobile flags survive a lookup
            flagged, self._tband_lmr = self._tband_lmr, set()
            self._tband_auto_on.clear()
            self._set_tband_lmr(flagged)
        if likely and self.dtv_detect_active:
            self.dtv_panel.set_detect_status(
                "Lookup done. Auto DTV Detect is running, so TV masks follow what is received; "
                "turn it off to use the lookup's choice.", "ok")
        elif likely:
            n_on = sum(likely.values())
            self.dtv_panel.set_detect_status(
                f"Lookup: {n_on} of {len(likely)} listed TV channels have a station strong enough to block "
                "them here (by licensed power and distance) and are masked. Low-power and distant stations "
                "are listed unticked; tick a row to mask it.", "ok")

        miles = self.current_region == "North America"
        rows = []
        for st in stations:
            ch = st.get("channel")
            if ch is None:
                continue
            is_lmr = bool(st.get("is_public_safety"))
            name = st.get("call_sign") or st.get("site_name") or "UNKNOWN"
            rows.append((ch, name.split(",")[0] if is_lmr else name,       # "LMR Boston": the column is narrow
                         "LMR" if is_lmr else self._erp_text(st.get("erp")),
                         self._distance_text(st.get("distance_km"), miles),
                         self.active_channels.get(ch, False), is_lmr))
        self.dtv_panel.show_stations(rows)
        self._dtv_table_mode = "lookup"
        self._refresh_channel_masks_all_views()
        self._show_dtv_live_rf(self._dtv_results)

    @staticmethod
    def _erp_text(erp) -> str:
        try:
            return f"{float(erp):g} kW"
        except (TypeError, ValueError):
            return str(erp) if erp else "--"

    @staticmethod
    def _distance_text(km, miles: bool) -> str:
        try:
            return f"{float(km) * 0.621371:.0f} mi" if miles else f"{float(km):.0f} km"
        except (TypeError, ValueError):
            return "--"

    def _station_mask_info(self) -> dict:
        """What is written on each looked-up channel's mask: {channel: {call, place, detail, more}}."""
        miles = self.current_region == "North America"

        def strength(st):
            # Likely the strongest here: ERP over distance squared (unknown ERP: nearest first)
            try:
                return float(st.get("erp") or 0.0) / max(float(st.get("distance_km") or 1.0), 1.0) ** 2
            except (TypeError, ValueError):
                return 0.0

        info = {}
        for ch, sts in self.dtv_stations.items():
            st = max(sts, key=strength)
            place = ", ".join(x for x in (st.get("city"), st.get("state")) if x)
            detail = " · ".join(x for x in (self._erp_text(st.get("erp")), self._distance_text(st.get("distance_km"), miles))
                                if x != "--")
            info[ch] = {"call": st.get("call_sign") or st.get("site_name") or "", "place": place,
                        "detail": detail, "more": len(sts) - 1}
        for ch, sts in self.lmr_stations.items():
            st = sts[0]
            info[ch] = {"call": "PUBLIC SAFETY", "place": str(st.get("call_sign", "")).replace("LMR ", "", 1),
                        "detail": "T-Band LMR · " + self._distance_text(st.get("distance_km"), miles), "more": 0}
        return info

    def _on_dtv_table_clicked(self, row: int, col: int):
        if col == self.dtv_panel.COL_MASK:
            return
        ch_num = self.dtv_panel.channel_at_row(row)
        for ch, f_start, f_stop in self._tv_channels():
            if ch == ch_num:
                self.sweep_panel.view_start_spin.setValue(f_start - 2.0)
                self.sweep_panel.view_stop_spin.setValue(f_stop + 2.0)
                self.apply_view_frequencies()
                break

    # --- Channel masks ---
    def _tv_channels(self) -> list:
        """(channel, start MHz, stop MHz) of the region's TV channels. Channel 37
        in the US is not among them: it is off limits whatever is measured."""
        if self._tv_channel_cache[0] != self.current_region:
            channels = []
            for band in TV_CHANNEL_STANDARDS.get(self.current_region, []):
                if "start_ch" in band and band.get("type") != "ch37":
                    for ch in range(band["start_ch"], band["end_ch"] + 1):
                        f_start = band["start_freq"] + (ch - band["start_ch"]) * band["spacing"]
                        channels.append((ch, f_start, f_start + band["spacing"]))
            self._tv_channel_cache = (self.current_region, channels)
        return self._tv_channel_cache[1]

    def _public_safety_channels(self) -> dict:
        """Channels drawn red: T-Band while it is being scanned, and public-safety
        LMR channels from the coordination file and the transmitter lookup."""
        ps = {ch: True for ch in self._tband_lmr} if self.tband_detect_active else {}
        for ch in self.coordination_ps_channels:
            ps[ch] = True
        for ch in self.lmr_stations:
            ps[ch] = True
        return ps

    def _set_channel_mask(self, ch, on: bool, refresh: bool = True):
        """Turn a channel's mask on or off by hand. The choice is pinned: neither
        Auto DTV Detect nor Scan T-Band changes it (see "Who sets a channel's mask")."""
        self.active_channels[ch] = bool(on)
        self._dtv_override[ch] = bool(on)
        self._tband_auto_on.discard(ch)
        self._mask_cache = (0.0, [])
        self.dtv_panel.set_mask_checked(ch, bool(on))
        if refresh:
            self._refresh_channel_masks_all_views()

    def _on_all_station_masks(self, on: bool):
        for ch in self.dtv_panel.listed_channels():
            self._set_channel_mask(ch, on, refresh=False)
        self._refresh_channel_masks_all_views()

    def _on_channel_bar_clicked(self, ch_num, start_freq, stop_freq):
        self._set_channel_mask(ch_num, not self.active_channels.get(ch_num, False))

    # --- Who sets a channel's mask ---------------------------------------------
    # One rule, so that nothing fights: the last thing clicked decides.
    #   * Ticking or unticking a channel (its row, the channel bar, All On / All
    #     Off) pins it: no automatic process changes a pinned channel.
    #   * Lookup, starting Auto DTV Detect and starting Scan T-Band are clicks
    #     too: each drops the pins on the channels it takes charge of.
    #   * Auto DTV Detect owns the TV masks while it runs; Scan T-Band owns only
    #     the land mobile (red) flags on channels 14-20 and never touches a TV
    #     mask; a channel the scan has flagged is left alone by the detector.
    #   * Turning either off leaves the masks as they are, except that the scan
    #     takes back the flags it raised itself.
    # The pins are in _dtv_override (channel -> mask on/off).

    def _on_tband_scan_toggled(self, active: bool):
        self.tband_detect_active = active
        self.tband_scanner.reset()
        self._tband_results, self._tband_last_run = {}, 0.0
        if active:
            for ch in self.TBAND_CHANNELS:
                self._dtv_override.pop(ch, None)
        self._set_tband_lmr(set())
        self.dtv_panel.set_tband_status("T-Band: listening on channels 14–20…" if active else "", "warn")
        self._mask_cache = (0.0, [])
        self._refresh_channel_masks_all_views()

    def _set_tband_lmr(self, lmr: set) -> bool:
        """Flag these channels as land mobile radio. A mask is only drawn while it is
        on, so the scan switches on the masks it needs (never a pinned channel's) and
        switches off again the ones it switched on once a channel is released.
        True if anything changed."""
        changed = lmr != self._tband_lmr
        for ch in lmr:
            if not self.active_channels.get(ch, False) and ch not in self._dtv_override:
                self.active_channels[ch] = True
                self._tband_auto_on.add(ch)
                self.dtv_panel.set_mask_checked(ch, True)
                changed = True
        for ch in list(self._tband_auto_on - lmr):
            self._tband_auto_on.discard(ch)
            if ch not in self.lmr_stations and ch not in self._dtv_override:
                self.active_channels[ch] = False
                self.dtv_panel.set_mask_checked(ch, False)
            changed = True
        self._tband_lmr = set(lmr)
        return changed

    def _process_tband_scan(self, x_data, y_data):
        """What each T-Band channel carries, from the sweep: a TV station, land
        mobile radio (flagged red while it is heard and for a minute after), or
        nothing. Only the land mobile flags are set; TV masks are left alone."""
        now = time.monotonic()
        if now - self._tband_last_run < 0.2:
            return
        self._tband_last_run = now
        channels = [c for c in self._tv_channels() if c[0] in self.TBAND_CHANNELS]
        meta = getattr(self.spectrum_view, "_carrier_meta", {})
        ignore = [tuple(float(v) for v in region.getRegion())
                  for c_id, region in self.spectrum_view.soundbase_masks.items()
                  if meta.get(c_id, {}).get("visible", True)]
        rbw = self._rbw_by_slot.get(self.multi_device_manager.focused_slot_id)
        results = self.tband_scanner.update(x_data / 1e6, y_data, channels, margin_db=self.dtv_panel.margin_db,
                                            ignore=ignore, rbw_mhz=(rbw or 0) / 1e6, known_lmr=set(self.lmr_stations))
        self._tband_results = results
        if not results:
            self.dtv_panel.set_tband_status("T-Band: sweep 470–512 MHz (at least three whole TV channels) to scan it.", "warn")
            return
        lmr = {ch for ch, r in results.items() if r["kind"] == "lmr"}
        tv = [ch for ch, r in results.items() if r["kind"] == "tv"]
        if self._set_tband_lmr(lmr):
            self._mask_cache = (0.0, [])
            self._refresh_channel_masks_all_views()

        def chans(items):
            return ", ".join(str(c) for c in sorted(items))
        parts = []
        if lmr:
            live = [ch for ch in lmr if results[ch]["live"]]
            packed = [ch for ch in lmr if results[ch]["carriers"] is None]
            n = sum(results[ch]["carriers"] or 0 for ch in lmr)
            detail = []
            if n:
                detail.append(f"{n} carrier(s)")
            if packed:
                detail.append(f"packed on {chans(packed)}")
            if live:
                detail.append(f"transmitting now on {chans(live)}")
            parts.append(f"land mobile radio on ch {chans(lmr)}" + (f" ({', '.join(detail)})" if detail else ""))
            unflagged = [ch for ch in lmr if not self.active_channels.get(ch, False)]
            if unflagged:
                parts.append(f"ch {chans(unflagged)} left unmasked as you set it")
        if tv:
            parts.append(f"TV on ch {chans(tv)}")
        clear = [ch for ch, r in results.items() if r["kind"] == "clear"]
        if clear:
            parts.append(f"nothing heard on ch {chans(clear)}")
        self.dtv_panel.set_tband_status("T-Band: " + " · ".join(parts), "ok" if lmr else "idle")

    def _on_dtv_threshold_dragged(self, level: float):
        """The threshold line was dragged: in Fixed mode that is the threshold; in
        Automatic mode the line is the noise floor plus the margin, so it sets the margin."""
        panel = self.dtv_panel
        if panel.auto_threshold and self._dtv_auto_floor is not None:
            spin = panel.margin_spin
            spin.setValue(min(max(round(level - self._dtv_auto_floor), spin.minimum()), spin.maximum()))
        else:
            panel.threshold_spin.setValue(level)

    # --- Column widths and order of the Broadcast / DTV tables ---
    def _dtv_tables(self) -> dict:
        # (v2: the first layout's channel column was too narrow to show two digits)
        return {"dtv_station_columns_v2": self.dtv_panel.stations_table,
                "dtv_zone_columns": self.dtv_panel.zones_table}

    def _column_headers(self) -> dict:
        """Every header whose layout is remembered: settings key -> QHeaderView."""
        headers = {key: table.horizontalHeader() for key, table in self._dtv_tables().items()}
        headers["markers_tree_columns"] = self.threats_panel.markers_tree.header()
        return headers

    def _restore_table_columns(self):
        """Bring back the column layouts the user left, and remember later changes."""
        self._column_save_timer = QTimer(self)
        self._column_save_timer.setSingleShot(True)
        self._column_save_timer.timeout.connect(self._save_table_columns)
        for key, header in self._column_headers().items():
            state = self.settings.value(key)
            if state is not None:
                header.restoreState(state)
            header.sectionResized.connect(lambda *_: self._column_save_timer.start(500))
            header.sectionMoved.connect(lambda *_: self._column_save_timer.start(500))

    def _save_table_columns(self):
        for key, header in self._column_headers().items():
            self.settings.setValue(key, header.saveState())

    # --- Auto DTV detect (see core/dtv_detect.py) ---
    def _on_dtv_detect_toggled(self, active: bool):
        self.dtv_detect_active = active
        self.dtv_detector.reset()
        if active:      # starting detection hands it the TV masks; stopping leaves everything as it is
            self._dtv_override.clear()
        self._dtv_last_run = self._dtv_last_status_time = 0.0
        if active and not self.dtv_panel.auto_threshold:
            self.dtv_panel.show_thresh_cb.setChecked(True)
        self._sync_dtv_threshold_line()
        if active:
            self.dtv_panel.set_detect_status("Auto DTV: waiting for a sweep…", "warn")
        else:
            self.dtv_panel.set_detect_status("Auto DTV: off (masks stay as they are)")

    def _on_dtv_detect_settings_changed(self):
        self.dtv_detector.reset()
        self._dtv_last_run = self._dtv_last_status_time = 0.0
        if self.dtv_detect_active and not self.dtv_panel.auto_threshold:
            self.dtv_panel.show_thresh_cb.setChecked(True)
        self._sync_dtv_threshold_line()

    def _sync_dtv_threshold_line(self):
        """
        The threshold line on the spectrum, when its checkbox is ticked. Fixed
        threshold: the level set, draggable. Automatic: the level the detector
        uses, the noise floor plus the margin, following the sweep.
        """
        panel = self.dtv_panel
        if not panel.show_thresh_cb.isChecked():
            self._dtv_line_timer.stop()
            self.spectrum_view.show_dtv_threshold(None)
        elif not panel.auto_threshold:
            self._dtv_line_timer.stop()
            self.spectrum_view.show_dtv_threshold(panel.threshold_spin.value(), "DTV THRESH", movable=True)
        else:
            # While detection runs it reports the floor; otherwise it is read off the sweep here
            if not self.dtv_detect_active and self._last_sweep is not None:
                floor = DTVOccupancyDetector.noise_floor(self._last_sweep[0] / 1e6, self._last_sweep[1])
                if floor is not None:
                    self._dtv_auto_floor = floor
            if self._dtv_auto_floor is None:
                self.spectrum_view.show_dtv_threshold(None)     # no sweep yet
            else:
                self.spectrum_view.show_dtv_threshold(self._dtv_auto_floor + panel.margin_db,
                                                      f"DTV: FLOOR + {panel.margin_db:.0f} dB", movable=True)
            if not self._dtv_line_timer.isActive():
                self._dtv_line_timer.start(1000)

    def _process_dtv_detect(self, x_data, y_data):
        now = time.monotonic()
        if now - self._dtv_last_run < 0.1:      # sweeps can arrive hundreds of times a second
            return
        self._dtv_last_run = now
        panel = self.dtv_panel
        # Land mobile channels (from the lookup, or flagged by the T-Band scan) are not TV channels to judge
        channels = [c for c in self._tv_channels()
                    if c[0] not in self.lmr_stations and c[0] not in self._tband_lmr]
        results = self.dtv_detector.update(
            x_data / 1e6, y_data, channels, margin_db=panel.margin_db,
            threshold_dbm=None if panel.auto_threshold else panel.threshold_spin.value())

        changed = []
        for ch, res in results.items():
            self._dtv_results[ch] = res
            want = self._dtv_override.get(ch, res["occupied"])
            if bool(self.active_channels.get(ch, False)) != want:
                self.active_channels[ch] = want
                changed.append(ch)
        if changed:
            self._refresh_channel_masks_all_views()
            for ch in changed:
                panel.set_mask_checked(ch, self.active_channels[ch])

        if now - self._dtv_last_status_time >= 0.5:
            self._dtv_last_status_time = now
            if not results:
                panel.set_detect_status(
                    "Auto DTV: nothing to judge in this sweep. Sweep at least three whole TV channels"
                    + (" (or use a fixed threshold)." if panel.auto_threshold else "."), "warn")
            else:
                occupied = sum(r["occupied"] for r in results.values())
                text = f"Auto DTV: {occupied} occupied, {len(results) - occupied} clear of {len(results)} channels swept"
                floors = [r["floor_dbm"] for r in results.values() if r["floor_dbm"] is not None]
                if floors:
                    self._dtv_auto_floor = float(np.median(floors))
                    text += f" · noise floor {self._dtv_auto_floor:.0f} dBm"
                panel.set_detect_status(text, "ok")
            self._show_dtv_live_rf(results)

    def _show_dtv_live_rf(self, results: dict):
        """Measured level and state of each channel in the transmitter table. With no
        lookup, the table lists the swept channels instead."""
        if not results:
            return
        panel = self.dtv_panel
        if self._dtv_table_mode != "lookup":
            key = tuple(sorted(results))
            if key != self._dtv_scanned_key:
                self._dtv_scanned_key, self._dtv_table_mode = key, "scanned"
                bounds = {ch: (f0, f1) for ch, f0, f1 in self._tv_channels()}
                panel.show_stations([(ch, f"DTV Ch {ch}", "{:g} - {:g} MHz".format(*bounds[ch]), "--",
                                      self.active_channels.get(ch, False), False) for ch in key])
        over = "the noise floor" if panel.auto_threshold else "the threshold"
        for ch, res in results.items():
            detail = f"{res['level_dbm']:.0f} dBm per RBW, {res['excess_db']:+.0f} dB relative to {over}"
            if res["occupied"]:
                panel.set_live_rf(ch, f"+{res['excess_db']:.0f} dB", True, "On the air: " + detail)
            else:
                panel.set_live_rf(ch, "clear", False, "Not received: " + detail)

    def _on_zone_selected(self, zone_idx: int):
        pass

    # --- DECT & Intercom ---
    def _on_dect_band_changed(self, band_name: str):
        self.dect_engine.set_band(band_name)

    def _on_dect_monitor_toggled(self, active: bool):
        self.dect_engine.set_enabled(active)

    def _on_dect_threshold_dragged(self, val: float):
        self.dect_panel.thresh_spin.blockSignals(True)
        self.dect_panel.thresh_spin.setValue(val)
        self.dect_panel.thresh_spin.blockSignals(False)
        self.dect_engine.set_threshold(val)

    def _on_dect_threshold_spin_changed(self, val: float):
        if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'dect_threshold_line'):
            self.spectrum_view.dect_threshold_line.blockSignals(True)
            self.spectrum_view.dect_threshold_line.setPos(val)
            self.spectrum_view.dect_threshold_line.blockSignals(False)
        self.dect_engine.set_threshold(val)

    def _on_dect_show_threshold_toggled(self, checked: bool):
        is_dect = (self.nav_rail.btn_group.checkedId() == 7)
        if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'dect_threshold_line'):
            self.spectrum_view.dect_threshold_line.setVisible(checked and is_dect)

    def tune_to_dect_band(self):
        b_info = DECT_BANDS.get(self.dect_panel.band_combo.currentText())
        if b_info:
            self.sweep_panel.start_spin.setValue(b_info["start_mhz"])
            self.sweep_panel.stop_spin.setValue(b_info["stop_mhz"])
            self.apply_frequencies()
            if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'dect_threshold_line'):
                self.spectrum_view.dect_threshold_line.setPos(self.dect_panel.thresh_spin.value())
                self.spectrum_view.dect_threshold_line.setVisible(self.dect_panel.show_thresh_cb.isChecked())

    # --- Counting antennas and beltpacks with zero span ---
    #
    # The duty-cycle estimate from sweeps cannot tell a beacon from a call. A zero-span
    # capture of a carrier over a few 10 ms frames can: antennas transmit in the first
    # half of every frame, beltpacks on calls in the second half (core/dect_frames.py).
    # The run takes each occupied carrier in turn, a few captures each, then goes back
    # to sweeping.
    DECT_COUNT_CAPTURES = 3
    DECT_COUNT_TIMEOUT_S = 6.0

    def start_dect_count(self):
        if self._dect_count is not None or not self.is_connected:
            return
        carriers = self.dect_engine.occupied_carriers()
        if not carriers:
            self.dect_panel.set_count_status("No occupied carrier in the recent sweeps: nothing to count. "
                                             "Enable the monitor and tune to the band first.")
            return
        caps = self._capabilities()
        if "DET" not in caps["modes"]:
            self.dect_panel.set_count_status(f"Zero span is not available on the {caps['name']}.")
            return
        det = caps.get("det")
        if det:
            # An analyzer with one zero-span rate (a tinySA Ultra): enough samples for 5 frames
            dt_ns = float(det["sample_interval_ns"])
            lengths = det.get("lengths") or [det["max_points"]]
            length = next((n for n in lengths if n * dt_ns >= 50e6), lengths[-1])
            params = {"decimate_factor": 1, "trigger_length": int(length)}
        else:
            # Harogic: 1.024 us a sample, 67 ms (6 frames) a capture
            params = {"decimate_factor": 128, "trigger_length": 65536}
        params.update({"ref_level": 0.0, "trigger_source": 2, "trigger_mode": 0,
                       "atten": self.sweep_panel.attenuation, "preamp": self.sweep_panel.preamp_combo.currentData(),
                       "own_gain": bool(det)})
        self._dect_count = {"carriers": carriers, "i": -1, "got": 0, "params": params, "counted": [],
                            "resume_mode": self._last_operating_mode, "started": time.monotonic(),
                            "timer": QTimer(self)}
        self._dect_count["timer"].timeout.connect(self._dect_count_watch)
        self._dect_count["timer"].start(500)
        self._dect_count_next()

    def _dect_count_next(self):
        run = self._dect_count
        if run["i"] >= 0 and run["got"] and run["i"] < len(run["carriers"]):
            run["counted"].append(run["carriers"][run["i"]])
        run["i"] += 1
        run["got"] = 0
        run["since"] = time.monotonic()
        if run["i"] >= len(run["carriers"]):
            self._dect_count_finish()
            return
        c = run["carriers"][run["i"]]
        self.dect_panel.set_count_status(f"Zero span on Ch {c['ch']} ({c['freq_mhz']:.3f} MHz), "
                                         f"carrier {run['i'] + 1} of {len(run['carriers'])}…", busy=True)
        params = dict(run["params"], center_freq_hz=c["freq_mhz"] * 1e6)
        self._zero_span_slot = self._detector_slot(self.dect_panel)
        self.multi_device_manager.set_operating_mode("DET", target_slot_id=self._zero_span_slot)
        self._on_det_params_changed(params, self._zero_span_slot)

    def _dect_count_capture(self, time_ns, power, info):
        run = self._dect_count
        c = run["carriers"][run["i"]] if 0 <= run["i"] < len(run["carriers"]) else None
        if c is None or abs(info.get("center_freq", 0) - c["freq_mhz"] * 1e6) > 0.5e6:
            return                                  # a capture from before the retune
        r = self.dect_engine.process_zero_span(info.get("center_freq", c["freq_mhz"] * 1e6), time_ns, power)
        if r is None:
            self.dect_panel.set_count_status(f"Ch {c['ch']}: capture too short for a frame count; skipped.", busy=True)
            self._dect_count_next()
            return
        run["got"] += 1
        if run["got"] >= self.DECT_COUNT_CAPTURES:
            self._dect_count_next()

    def _dect_count_watch(self):
        run = self._dect_count
        if run is None:
            return
        if time.monotonic() - run["since"] > self.DECT_COUNT_TIMEOUT_S:
            c = run["carriers"][run["i"]] if 0 <= run["i"] < len(run["carriers"]) else None
            if c is not None:
                self.top_bar.flash_status(f"DECT count: no zero-span capture on Ch {c['ch']}; skipped", 4000)
            self._dect_count_next()

    def _dect_count_finish(self):
        run, self._dect_count = self._dect_count, None
        if run is None:
            return
        run["timer"].stop()
        counted = run["counted"]
        ant = sum(self.dect_engine.zero_span[c["freq_mhz"]]["antennas"] for c in counted)
        packs = sum(self.dect_engine.zero_span[c["freq_mhz"]]["calls"] for c in counted)
        self.dect_panel.set_count_status(
            f"Counted {len(counted)} of {len(run['carriers'])} carriers in {time.monotonic() - run['started']:.0f} s: "
            f"{ant} antennas, {packs} beltpacks on calls. Idle beltpacks are silent and cannot be counted. "
            f"Counts stand for {int(self.dect_engine.ZERO_SPAN_FRESH_S)} s.")
        # Back to what the analyzer was doing
        self._release_zero_span_slot()
        if run["resume_mode"] == "DET":
            self._on_det_trigger_requested(self.det_panel.get_params())
        else:
            self.resume_rf_sweep()

    def open_dect_matrix_dialog(self):
        dlg = TDMATimeslotDialog(self.dect_engine, self)
        dlg.exec()

    def _on_dect_analysis_updated(self, stats: dict):
        total_ant = stats.get("total_antennas", 0)
        total_bp = stats.get("total_beltpacks", 0)
        band_load = stats.get("band_load_pct", 0.0)
        status_str = stats.get("band_status", "CLEAN")
        self.dect_panel.update_summary(band_load, total_ant, total_bp, status_str)
        
        carriers = stats.get("carriers", {})
        self.dect_panel.carriers_table.setRowCount(len(carriers))
        # carriers is keyed by carrier frequency; show the DECT channel number
        for r_idx, c_data in enumerate(sorted(carriers.values(), key=lambda c: c.get("ch", 0))):
            ch_item = QTableWidgetItem(f"{c_data.get('ch', '--')}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            rssi_item = QTableWidgetItem(f"{c_data.get('peak_dbm', -120.0):.0f} dBm")
            rssi_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            load_item = QTableWidgetItem(f"{c_data.get('duty_cycle_pct', 0.0):.0f}%")
            load_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            bp = c_data.get('beltpacks', 0)
            st = c_data.get('status', 'IDLE')
            if st == 'IDLE' or bp == 0:
                status_item = QTableWidgetItem(st)
            else:
                status_item = QTableWidgetItem(f"{st} ({bp} BP)")
            if c_data.get("slots"):
                slots = c_data["slots"]
                status_item.setToolTip(f"Slots 0-11 (downlink, antennas) {slots[:12]}\n"
                                       f"Slots 12-23 (uplink, beltpacks) {slots[12:]}\n"
                                       f"F antenna burst, P beltpack burst, . empty")
            
            for it in (ch_item, rssi_item, load_item, status_item):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
            self.dect_panel.carriers_table.setItem(r_idx, 0, ch_item)
            self.dect_panel.carriers_table.setItem(r_idx, 1, rssi_item)
            self.dect_panel.carriers_table.setItem(r_idx, 2, load_item)
            self.dect_panel.carriers_table.setItem(r_idx, 3, status_item)

    # --- 2.4 GHz ShowLink & CRMX ---
    def _on_showlink_monitor_toggled(self, active: bool):
        self.showlink_engine.set_enabled(active)

    def _on_showlink_threshold_dragged(self, val: float):
        self.showlink_panel.thresh_spin.blockSignals(True)
        self.showlink_panel.thresh_spin.setValue(val)
        self.showlink_panel.thresh_spin.blockSignals(False)
        self.showlink_engine.threshold_dbm = val

    def _on_showlink_threshold_spin_changed(self, val: float):
        if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'showlink_threshold_line'):
            self.spectrum_view.showlink_threshold_line.blockSignals(True)
            self.spectrum_view.showlink_threshold_line.setPos(val)
            self.spectrum_view.showlink_threshold_line.blockSignals(False)
        self.showlink_engine.threshold_dbm = val

    def _on_showlink_show_threshold_toggled(self, checked: bool):
        is_showlink = (self.nav_rail.btn_group.checkedId() == 8)
        if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'showlink_threshold_line'):
            self.spectrum_view.showlink_threshold_line.setVisible(checked and is_showlink)

    def tune_to_showlink_band(self):
        self.sweep_panel.start_spin.setValue(2400.0)
        self.sweep_panel.stop_spin.setValue(2483.5)
        self.apply_frequencies()
        if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'showlink_threshold_line'):
            self.spectrum_view.showlink_threshold_line.setPos(self.showlink_panel.thresh_spin.value())
            self.spectrum_view.showlink_threshold_line.setVisible(self.showlink_panel.show_thresh_cb.isChecked())

    def open_showlink_map_dialog(self):
        dlg = ShowlinkMapDialog(self.showlink_engine, self)
        dlg.exec()

    def _clear_showlink_data(self):
        self.showlink_engine.reset_data()
        self.showlink_panel.showlink_table.setRowCount(0)
        self.showlink_panel.wifi_table.setRowCount(0)
        self.showlink_panel.airtime_lbl.setText("")

    def _on_showlink_my_channel_changed(self, ch: int):
        self.settings.setValue("showlink_judge_channel", int(ch))
        self.showlink_engine.set_my_channel(ch)

    # Airtime of the ShowLink channel in use, from zero-span captures (same run as the
    # DECT count: a few captures, then back to sweeping)
    SHOWLINK_AIRTIME_CAPTURES = 3

    def start_showlink_airtime(self):
        if self._dect_count is not None or self._showlink_airtime is not None or not self.is_connected:
            return
        caps = self._capabilities()
        if "DET" not in caps["modes"]:
            self.showlink_panel.airtime_lbl.setText(f"Zero span is not available on the {caps['name']}.")
            return
        ch = self.showlink_engine.judged_channel
        if not ch:
            self.showlink_panel.airtime_lbl.setText("No ShowLink traffic seen yet: pick a channel to measure, or wait for the sweep.")
            return
        cf_hz = (2405.0 + 5.0 * (ch - 11)) * 1e6
        det = caps.get("det")
        if det:
            dt_ns = float(det["sample_interval_ns"])
            lengths = det.get("lengths") or [det["max_points"]]
            params = {"decimate_factor": 1, "trigger_length": int(next((n for n in lengths if n * dt_ns >= 50e6), lengths[-1]))}
        else:
            params = {"decimate_factor": 128, "trigger_length": 65536}      # 67 ms at 1.024 us
        params.update({"center_freq_hz": cf_hz, "ref_level": 0.0, "trigger_source": 2, "trigger_mode": 0,
                       "atten": self.sweep_panel.attenuation, "preamp": self.sweep_panel.preamp_combo.currentData(),
                       "own_gain": bool(det)})
        self._showlink_airtime = {"ch": ch, "cf_hz": cf_hz, "got": 0, "resume_mode": self._last_operating_mode,
                                  "since": time.monotonic(), "timer": QTimer(self)}
        self._showlink_airtime["timer"].timeout.connect(self._showlink_airtime_watch)
        self._showlink_airtime["timer"].start(500)
        self.showlink_panel.airtime_btn.setEnabled(False)
        self.showlink_panel.airtime_lbl.setText(f"Zero span on Ch {ch}…")
        self._zero_span_slot = self._detector_slot(self.showlink_panel)
        self.multi_device_manager.set_operating_mode("DET", target_slot_id=self._zero_span_slot)
        self._on_det_params_changed(params, self._zero_span_slot)

    def _showlink_airtime_capture(self, time_ns, power, info):
        run = self._showlink_airtime
        if abs(info.get("center_freq", 0) - run["cf_hz"]) > 0.5e6:
            return
        if self.showlink_engine.process_zero_span(run["cf_hz"], time_ns, power) is not None:
            run["got"] += 1
        if run["got"] >= self.SHOWLINK_AIRTIME_CAPTURES:
            self._showlink_airtime_finish()

    def _showlink_airtime_watch(self):
        run = self._showlink_airtime
        if run and time.monotonic() - run["since"] > self.DECT_COUNT_TIMEOUT_S:
            self.showlink_panel.airtime_lbl.setText(f"No zero-span capture arrived for Ch {run['ch']}.")
            self._showlink_airtime_finish()

    def _showlink_airtime_finish(self):
        run, self._showlink_airtime = self._showlink_airtime, None
        if run is None:
            return
        run["timer"].stop()
        self.showlink_panel.airtime_btn.setEnabled(True)
        self._release_zero_span_slot()
        if run["resume_mode"] == "DET":
            self._on_det_trigger_requested(self.det_panel.get_params())
        else:
            self.resume_rf_sweep()

    def _copy_showlink_survey(self):
        text = self.showlink_engine.survey_text
        if not text:
            self.top_bar.flash_status("Nothing surveyed yet: enable the monitor and tune to the 2.4 GHz band")
            return
        QApplication.clipboard().setText(text)
        self.top_bar.flash_status("Survey summary copied", 3000)

    def _show_showlink_feasibility(self, stats: dict):
        sp = self.showlink_panel
        feas = stats.get("feasibility") or {}
        verdict = feas.get("verdict", "UNKNOWN")
        if verdict == "UNKNOWN":
            return
        color = {"FEASIBLE": "#4ade80", "MARGINAL": "#f59e0b", "NOT WITHOUT CHANGES": "#f87171"}.get(verdict, "#c9d1d9")
        clear = feas.get("clear", [])
        parts = [f"<b style='color:{color}'>{verdict}</b> — {len(clear)} clear ShowLink channel{'s' if len(clear) != 1 else ''}"
                 + (f" ({', '.join(map(str, clear))})" if clear else "")
                 + f" in {stats.get('sweeps', 0)} sweeps"]
        wifi = feas.get("wifi_in_use", [])
        if wifi:
            parts.append("Wi-Fi in use: " + ", ".join(f"ch {w} ({stats['wifi'][w]['busy_pct']:.0f}%)" for w in wifi if w in stats.get("wifi", {})))
        else:
            parts.append("No Wi-Fi channel in use above the threshold.")
        if verdict != "FEASIBLE" and feas.get("disable"):
            parts.append("Ask the venue to switch off: " + "; ".join(
                f"<b>Wi-Fi ch {w}</b> → frees ShowLink {', '.join(map(str, freed))}" for w, freed in feas["disable"][:3]))
        elif verdict != "FEASIBLE":
            parts.append("Switching Wi-Fi off would not help: the interference is not Wi-Fi-shaped (hopping or wideband).")
        sp.feas_lbl.setText("<br>".join(parts))

    def _on_showlink_analysis_updated(self, stats: dict):
        sp = self.showlink_panel
        self._show_showlink_feasibility(stats)
        ch_stats = stats.get("channels", {})
        my = stats.get("my_channel")
        sp.showlink_table.setRowCount(len(ch_stats))
        for r_idx, (ch_num, s_data) in enumerate(sorted(ch_stats.items())):
            ch_item = QTableWidgetItem(f"{ch_num}" + (" ★" if ch_num == my else ""))
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            freq_item = QTableWidgetItem(f"{float(s_data.get('freq_mhz', 0.0)):.0f}")
            freq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            busy_item = QTableWidgetItem(f"{s_data.get('busy_pct', 0.0):.0f}%")
            busy_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rssi_item = QTableWidgetItem(f"{s_data.get('peak_dbm', -120.0):.0f} dBm")
            rssi_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            raw_status = str(s_data.get("status", ""))
            words = raw_status.replace("🔴", "").replace("🟡", "").replace("🟢", "").replace("🔵", "").strip().split()
            health_item = QTableWidgetItem(words[0] if words else "CLEAN")
            health_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            health_item.setForeground(QColor(s_data.get("color", "#c9d1d9")))
            font = health_item.font()
            font.setBold(True)
            health_item.setFont(font)
            kinds = s_data.get("kinds", {})
            seen = "\n".join(f"  {band24.KIND_LABEL[k]}: {v:.0f}% of sweeps" for k, v in kinds.items() if v >= 2.0) or "  nothing above threshold"
            air = s_data.get("airtime")
            air_txt = (f"\nAirtime (zero span): {air['busy_pct']:.0f}%, {air['bursts']} bursts, longest {air['longest_us'] / 1e3:.1f} ms"
                       if air else "")
            tip = (f"Channel {ch_num} ({s_data.get('freq_mhz', 0.0):.0f} MHz), under Wi-Fi {', '.join(map(str, s_data.get('wifi_channels', [])))}\n"
                   f"Busy in {s_data.get('busy_pct', 0.0):.0f}% of recent sweeps, "
                   f"{s_data.get('interference_pct', 0.0):.0f}% with something other than Zigbee\n"
                   f"Peak {s_data.get('peak_dbm', -120.0):.1f} dBm\nSeen on it:\n{seen}{air_txt}")
            for it in (ch_item, freq_item, busy_item, rssi_item, health_item):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it.setToolTip(tip)
            for c, it in enumerate((ch_item, freq_item, busy_item, rssi_item, health_item)):
                sp.showlink_table.setItem(r_idx, c, it)

        wifi = stats.get("wifi", {})
        sp.wifi_table.setRowCount(len(wifi))
        for r_idx, (n, w) in enumerate(sorted(wifi.items())):
            vals = (f"{n}", f"{w['center_mhz']:.0f}", f"{w['busy_pct']:.0f}%", f"{w['peak_dbm']:.0f} dBm")
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter if c < 2 else Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c == 2 and w["busy_pct"] >= 10.0:
                    it.setForeground(QColor("#f87171" if w["busy_pct"] >= 35.0 else "#f59e0b"))
                sp.wifi_table.setItem(r_idx, c, it)

        mix = stats.get("mix", {})
        parts = [f"{band24.KIND_LABEL[k]} {v:.0f}%" for k, v in sorted(mix.items(), key=lambda kv: -kv[1]) if v >= 1.0]
        sp.mix_lbl.setText(("Signals above threshold, by shape: " + ", ".join(parts) + f" ({stats.get('sweeps', 0)} sweeps)")
                           if parts else f"Nothing above threshold in the last {stats.get('sweeps', 0)} sweeps.")

        a = stats.get("assessment")
        detected = stats.get("detected_channel")
        where = (f"ShowLink seen on <b>Ch {detected}</b>" if detected else "No ShowLink (Zigbee-shaped) traffic seen")
        if my and self.showlink_engine.my_channel:
            where += f"; judging Ch {my}"
        if a and a["busy_pct"] is not None:
            color = {"GOOD": "#4ade80", "MARGINAL": "#f59e0b", "POOR": "#f87171"}.get(a["verdict"], "#c9d1d9")
            reasons = "".join(f"<br>• {r}" for r in a["reasons"]) or "<br>• nothing else seen on it"
            alts = ", ".join(f"Ch {c}" for c in a["alternatives"])
            sp.verdict_lbl.setText(
                f"{where}<br><b style='color:{color}'>{a['verdict']}</b> — interference in {a['busy_pct']:.0f}% of recent sweeps"
                f"{reasons}<br>Quietest channels for agility to move to: {alts or '—'}")
        elif a:
            sp.verdict_lbl.setText(f"{where}. Channel not in the sweep yet: tune to the 2.4 GHz band.")
        else:
            alts = ", ".join(f"Ch {c}" for c in stats.get("best_channels", []))
            sp.verdict_lbl.setText(f"{where}.<br>Quietest channels right now: {alts or '—'}")
        air = self.showlink_engine.airtime.get(my)
        if air:
            sp.airtime_lbl.setText(f"Airtime on Ch {my}: {air['busy_pct']:.0f}% busy over {air['captures']} × {air['span_s'] * 1e3:.0f} ms; "
                                   f"{air['bursts']} bursts, median {air['median_us'] / 1e3:.2f} ms, longest {air['longest_us'] / 1e3:.2f} ms"
                                   + (" — continuous energy, not packets" if air["continuous"] else ""))

    # --- Threats & Intruder Alert Engine ---
    def _on_intruder_alert_toggled(self, active: bool):
        is_threats = (self.nav_rail.btn_group.checkedId() == 1)
        if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'intruder_threshold_line'):
            self.spectrum_view.intruder_threshold_line.setVisible(
                is_threats and self.threats_panel.show_thresh_cb.isChecked()
            )
        if not active:
            self._clear_intruders()

    def _on_intruder_show_threshold_toggled(self, checked: bool):
        is_threats = (self.nav_rail.btn_group.checkedId() == 1)
        if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'intruder_threshold_line'):
            self.spectrum_view.intruder_threshold_line.setVisible(checked and is_threats)

    def _on_intruder_threshold_changed(self, val: float):
        if hasattr(self, 'spectrum_view') and hasattr(self.spectrum_view, 'intruder_threshold_line'):
            self.spectrum_view.intruder_threshold_line.blockSignals(True)
            self.spectrum_view.intruder_threshold_line.setPos(val)
            self.spectrum_view.intruder_threshold_line.blockSignals(False)
        thresh = float(val)
        to_del = [f for f, info in self.intruders.items() if info.get("power", -150.0) < thresh]
        if to_del:
            for f in to_del:
                del self.intruders[f]
            self._update_intruders_ui(force=True)

    def _on_intruder_row_clicked(self, row: int, col: int):
        tbl = self.threats_panel.intruder_table
        item0 = tbl.item(row, 0)
        if item0 is None:
            return
        freq_val = item0.data(Qt.ItemDataRole.UserRole)
        if freq_val is None:
            try:
                freq_val = float(item0.text())
            except ValueError:
                return
        
        target_f = float(freq_val)
        matched_key = None
        for k in self.intruders.keys():
            if abs(k - target_f) < 0.005:
                matched_key = k
                break
                
        if matched_key is not None:
            sorted_intruders = sorted(self.intruders.items(), key=lambda kv: kv[1]["power"], reverse=True)
            for idx, (f, _) in enumerate(sorted_intruders):
                if f == matched_key:
                    self.current_intruder_index = idx
                    break
            self._jump_to_current_intruder()

    def _process_intruder_sweep(self, x_data, y_data):
        if x_data is None or y_data is None or len(x_data) < 10 or len(y_data) < 10:
            return
            
        thresh = float(self.threats_panel.intruder_thresh_spin.value())
        
        # Ensure x is in MHz and y is clean finite float
        if x_data[0] > 1e5:
            x_mhz = x_data / 1e6
        else:
            x_mhz = x_data
            
        y_clean = np.nan_to_num(y_data, nan=-130.0, posinf=0.0, neginf=-130.0)
        masked = self._masked_ranges()
        filtered_peaks = self._intruder_candidates(x_mhz, y_clean, thresh, masked, draw=True)
        # Diversity: what only antenna B hears is an intruder too. Its sweep is searched the
        # same way (its own ETSI limits, at the levels B receives the carriers at), and each
        # entry says which antenna hears it, and on which it is stronger
        seen_on = {}
        b = self._last_div_b if self.multi_device_manager.topology == MultiDeviceTopology.DIVERSITY else None
        if b is not None and len(b[0]) == len(x_mhz):
            seen_on = {f: "A" for f, _p in filtered_peaks}
            for f, p in self._intruder_candidates(x_mhz, b[1], thresh, masked, draw=False):
                near = next((i for i, (fa, _pa) in enumerate(filtered_peaks) if abs(f - fa) < 0.15), None)
                if near is None:
                    filtered_peaks.append((f, p))
                    seen_on[f] = "B"
                else:
                    fa, pa = filtered_peaks[near]
                    del seen_on[fa]
                    if p > pa:
                        filtered_peaks[near] = (f, p)
                        seen_on[f] = "B>A"
                    else:
                        seen_on[fa] = "A>B"
            # Carriers are measured (for identification) where they are strongest
            y_clean = np.maximum(y_clean, b[1])
        self._track_intruders(x_mhz, y_clean, filtered_peaks, masked, seen_on)

    def _intruder_candidates(self, x_mhz, y_clean, thresh, masked, draw: bool) -> list:
        """
        What in one antenna's sweep is not accounted for: [(MHz, dBm)], strongest first, one
        per 150 kHz. draw: this is the sweep the main view shows (its ETSI masks are drawn).
        """
        # Find true local maxima above threshold using scipy find_peaks
        peak_indices, _ = signal.find_peaks(y_clean, height=thresh, prominence=1.0, distance=3)
        # (No early return when nothing is found: the table still refreshes below
        # so entries that have gone quiet are shown as stale.)

        # Sort detected peaks descending by power and cluster within 150 kHz in the current frame
        peak_powers = y_clean[peak_indices]
        sorted_indices = peak_indices[np.argsort(-peak_powers)]

        # ETSI masks around the coordinated carriers: a carrier's own skirts stay under its
        # mask; what breaks through is listed even where it is a shoulder and not a peak
        limit, etsi_masks = self._carrier_mask_limit(x_mhz, y_clean, thresh, draw=draw)
        filtered_peaks = []
        for idx in sorted_indices:
            f = float(x_mhz[idx])
            p = float(y_clean[idx])
            if masked and self._is_masked(f, masked):
                continue        # inside a TV/LMR mask, a coordinated carrier or an acknowledged marker
            if limit is not None and p <= limit[idx]:
                continue        # under a coordinated carrier's emission mask: that carrier's skirt
            if any(abs(f - acc_f) < 0.15 for acc_f, _ in filtered_peaks):
                continue
            filtered_peaks.append((f, p))
        for m in etsi_masks:
            if m["at_hz"] is None:
                continue
            f = m["at_hz"] / 1e6
            if masked and self._is_masked(f, masked):
                continue
            near = next((acc_f for acc_f, _ in filtered_peaks if abs(f - acc_f) < 0.15), None)
            if near is None:
                filtered_peaks.append((f, float(np.interp(f, x_mhz, y_clean))))
                near = f
            self._mask_breaks[round(near, 3)] = {"name": m["carrier"]["name"], "excess_db": m["excess_db"],
                                                 "kind": m["kind"], "peak_mhz": m["peak_hz"] / 1e6,
                                                 "fc_mhz": m["carrier"]["freq_hz"] / 1e6, "t": time.time()}
        return filtered_peaks

    def _track_intruders(self, x_mhz, y_clean, filtered_peaks, masked, seen_on):
        """Update the intruder list with this sweep's candidates (seen_on: MHz -> antenna, in diversity)."""
        if masked:
            for k in [k for k in self.intruders if self._is_masked(k, masked)]:
                del self.intruders[k]
                self.fingerprinter.forget(k * 1e6)
            
        # Match peaks against tracked self.intruders
        now = time.time()
        updated_any = False
        for f, p in filtered_peaks:
            matched_key = None
            for existing_f in list(self.intruders.keys()):
                if abs(existing_f - f) <= 0.15: # 150 kHz tracking tolerance
                    matched_key = existing_f
                    break
                    
            if matched_key is not None:
                entry = self.intruders[matched_key]
                if seen_on.get(f) != entry.get("antenna"):
                    entry["antenna"] = seen_on.get(f)
                    updated_any = True
                if now - entry["last_seen"] > 1.0:
                    entry["bursts"] = entry.get("bursts", 1) + 1     # it went away and came back
                entry["last_seen"] = now
                entry["on_s"] = entry.get("on_s", 0.0) + min(now - entry.get("_last_hit", now), 0.5)
                entry["_last_hit"] = now
                if p > entry["power"]:
                    entry["power"] = p
                    if round(f, 3) != matched_key:
                        del self.intruders[matched_key]
                        matched_key = round(f, 3)
                        entry["freq"] = matched_key
                    self.intruders[matched_key] = entry
                    updated_any = True
            else:
                # Identified by the fingerprinter once it has a few sweeps of evidence
                self.intruders[round(f, 3)] = {
                    "freq": round(f, 3),
                    "power": p,
                    "signature": "Analyzing…",
                    "details": "Collecting sweeps to identify this carrier",
                    "category": "RF Carrier",
                    "confidence": 0,
                    "color": "#8b949e",
                    "first_seen": now,
                    "last_seen": now,
                    "antenna": seen_on.get(f)
                }
                updated_any = True

        # Measure every recently seen carrier in this sweep, and re-identify
        # them about once a second as evidence accumulates
        # (At ~10 measurements a second: the signature history then spans a few
        # seconds of programme rather than a fraction of one, and measuring
        # every carrier on every sweep was the GUI's single biggest cost.)
        if now - self._fp_last_measure >= FP_MEASURE_PERIOD_S:
            recent = [k * 1e6 for k, e in self.intruders.items() if now - e["last_seen"] < 10.0]
            if recent:
                self._fp_last_measure = now
                rbw = self._rbw_by_slot.get(self.multi_device_manager.focused_slot_id)
                self.fingerprinter.update_sweep(x_mhz * 1e6, y_clean, recent, rbw)
        if now - self._fp_last_refresh >= 1.0:
            self._rebuild_intermod()
            if self._im_map and self.threats_panel.im_overlay_cb.isChecked():
                self._refresh_intermod_overlay()        # the carriers' levels move
            updated_any |= self._refresh_fingerprints()

        # Rebuilding the table is costly (every row is recreated), so it is
        # refreshed at ~5 FPS; nothing in it, a new carrier included, needs to
        # show sooner than that
        if now - self._last_intruder_ui_update >= 0.2:
            self._update_intruders_ui()

    def _update_intruders_ui(self, force=False):
        self._last_intruder_ui_update = time.time()
        count = len(self.intruders)
        sorted_intruders = sorted(self.intruders.items(), key=lambda kv: kv[1]["power"], reverse=True)
        cur_freq = sorted_intruders[self.current_intruder_index][0] if 0 <= self.current_intruder_index < count else None
        self.top_bar.set_intruders_banner(count, self.current_intruder_index, cur_freq)
        
        tbl = self.threats_panel.intruder_table
        
        # Preserve sorting indicator state while repopulating
        header = tbl.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        tbl.setSortingEnabled(False)
        
        tbl.setRowCount(count)
        now = time.time()
        for r_idx, (f, info) in enumerate(sorted_intruders):
            # Entries stay listed (a brief transmission is still worth knowing
            # about) but are greyed out once they have not been seen for a while.
            age_s = now - info.get("last_seen", now)
            stale = age_s > INTRUDER_STALE_S
            f_item = NumericTableWidgetItem(f"{f:.3f}", f)
            f_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            ant = info.get("antenna")
            p_item = NumericTableWidgetItem(f"{info['power']:.1f} dBm" + (f"  {ant}" if ant else ""), info['power'])
            if ant:
                p_item.setToolTip({"A": "Heard on antenna A only", "B": "Heard on antenna B only",
                                   "A>B": "Heard on both antennas, stronger on A",
                                   "B>A": "Heard on both antennas, stronger on B"}[ant])
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            sig_name = info.get("signature", "Unknown Carrier")
            if info.get("intermod"):
                sig_name += "  ⚠ possible intermod"
            s_item = QTableWidgetItem(sig_name)
            s_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            # Signature color badge & tooltip
            sig_color = info.get("color", "#d946ef")
            s_item.setForeground(QColor("#6e7681" if stale else sig_color))
            if stale:
                f_item.setForeground(QColor("#6e7681"))
                p_item.setForeground(QColor("#6e7681"))
            seen_txt = f"Last seen {age_s:.0f} s ago" if stale else "Active"
            tooltip_txt = (
                f"{seen_txt}\n"
                f"Signature: {sig_name}\n"
                f"Category: {info.get('category', 'RF Carrier')}\n"
                f"Peak Power: {info['power']:.1f} dBm\n"
                f"Confidence: {info.get('confidence', 50)}%\n"
                f"Details: {info.get('details', 'N/A')}"
            )
            if info.get("intermod"):
                tooltip_txt += "\nLands on intermod products of your transmitters:\n  • " + "\n  • ".join(info["intermod"])
            if info.get("candidates"):
                tooltip_txt += "\nCandidates: " + ", ".join(f"{n} {pct}%" for n, pct in info["candidates"])
            if info.get("evidence"):
                tooltip_txt += "\nEvidence:\n  • " + "\n  • ".join(info["evidence"])
            if info.get("suggestion"):
                tooltip_txt += f"\nTip: {info['suggestion']}"
            s_item.setToolTip(tooltip_txt)
            f_item.setToolTip(tooltip_txt)
            p_item.setToolTip(tooltip_txt)
            
            for it in (f_item, p_item, s_item):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
            tbl.setItem(r_idx, 0, f_item)
            tbl.setItem(r_idx, 1, p_item)
            tbl.setItem(r_idx, 2, s_item)
            
        tbl.setSortingEnabled(True)
        if sort_col >= 0:
            tbl.sortByColumn(sort_col, sort_order)
            
        # Re-highlight current intruder row if active
        if cur_freq is not None:
            for r in range(tbl.rowCount()):
                it = tbl.item(r, 0)
                if it:
                    val = it.data(Qt.ItemDataRole.UserRole)
                    if val is not None and abs(val - cur_freq) < 0.005:
                        tbl.selectRow(r)
                        break

    # --- Carrier fingerprinting ---
    def _refresh_fingerprints(self) -> bool:
        """Re-identify tracked carriers; merge peaks that lie inside one wide block."""
        self._fp_last_refresh = time.time()
        changed = False
        results = {}
        for key in list(self.intruders):
            r = self.fingerprinter.classify(key * 1e6)
            results[key] = r
            entry = self.intruders[key]
            if r["confidence"] == 0 and r["device"] == "Unknown carrier":
                # Nothing measurable yet: say so once it has had a fair chance.
                # (A brief keyed transmission may never be measurable: what
                # band it is in can still say what it probably is.)
                if time.time() - entry["first_seen"] > 5 and entry.get("signature") == "Analyzing…":
                    weak = self._apply_context(key, {
                        "signature": "Too weak to identify", "confidence": 0,
                        "details": "Less than 10 dB above the noise floor; raise the threshold, "
                                   "add gain, or move the antenna closer",
                        "category": "Weak carrier", "color": "#6e7681", "evidence": [], "suggestion": ""}, entry)
                    entry.update(weak)
                    changed = True
                elif entry.get("signature") == "Analyzing…" and time.time() - entry["first_seen"] > 1.5:
                    ctx = self._apply_context(key, {"signature": "Analyzing…", "category": "Weak carrier", "confidence": 0,
                                                    "details": entry.get("details", ""), "color": entry.get("color", "#8b949e"),
                                                    "evidence": [], "suggestion": ""}, entry)
                    if ctx["signature"] != "Analyzing…":
                        entry.update(ctx)
                        changed = True
                continue
            new = {"signature": r["device"], "details": r["details"], "category": r["category"],
                   "confidence": r["confidence"], "color": r["color"], "candidates": r["candidates"],
                   "evidence": r["evidence"], "suggestion": r["suggestion"],
                   "extent_hz": r.get("extent_hz"),
                   "intermod": self._intermod_at(key * 1e6)}
            new = self._apply_context(key, new, entry)
            if any(entry.get(k) != v for k, v in new.items()):
                entry.update(new)
                changed = True
        # A Spectera/TV block shows up as many peaks plus spectral shoulders.
        # The strongest entry in a block represents it (and is never removed);
        # weaker peaks inside it, and its shoulders up to 1 MHz either side
        # (15 dB or more down), are folded into it.
        blocks = [(k, results[k]["extent_hz"]) for k in results
                  if results[k].get("extent_hz") and k in self.intruders
                  and (results[k]["extent_hz"][1] - results[k]["extent_hz"][0]) / 1e3 >= WIDE_BLOCK_KHZ]
        for key, (lo, hi) in sorted(blocks, key=lambda b: -self.intruders[b[0]]["power"]):
            if key not in self.intruders:
                continue
            inside = [k for k in self.intruders if lo <= k * 1e6 <= hi]
            rep = max(inside + [key], key=lambda k: self.intruders[k]["power"])
            top = self.intruders[rep]["power"]
            for k in list(self.intruders):
                if k == rep:
                    continue
                f_hz = k * 1e6
                in_block = lo <= f_hz <= hi
                shoulder = (lo - 1e6 <= f_hz <= hi + 1e6) and self.intruders[k]["power"] <= top - 15
                if in_block or shoulder:
                    del self.intruders[k]
                    self.fingerprinter.forget(f_hz)
                    changed = True
            if rep != key and rep in self.intruders and key in results:
                r = results[key]   # the representative takes the block's identification
                self.intruders[rep].update({"signature": r["device"], "details": r["details"],
                                            "category": r["category"], "confidence": r["confidence"],
                                            "color": r["color"], "candidates": r["candidates"],
                                            "evidence": r["evidence"], "suggestion": r["suggestion"]})
        return changed

    # --- What the band says about a carrier ---
    TBAND_CHANNELS = range(14, 21)          # 470-512 MHz: shared with land mobile radio in US metro areas

    def _tv_channel_at(self, f_mhz: float):
        for ch, f0, f1 in self._tv_channels():
            if f0 <= f_mhz < f1:
                return ch, f0, f1
        return None

    # --- ETSI emission masks around coordinated carriers (core/emission_mask.py) ---
    def _on_carrier_mask_changed(self):
        tp = self.threats_panel
        self.settings.setValue("carrier_mask", tp.carrier_mask_combo.currentData())
        self.settings.setValue("carrier_mask_margin_db", tp.carrier_mask_margin_spin.value())
        self._mask_breaks.clear()
        if tp.carrier_mask_combo.currentData() == "channel":
            self._mask_drawn = False
            self.spectrum_view.set_emission_masks([])
            self.spectrum_view_b.set_emission_masks([])
        else:
            self._draw_carrier_masks()

    def _draw_carrier_masks(self):
        """
        Draw the masks now, whether or not threat detection is running: from the latest
        sweep when there is one, else just their shapes across the sweep range (dashed:
        a mask takes its level from the carrier, and nothing is on the air yet).
        """
        thresh = float(self.threats_panel.intruder_thresh_spin.value())
        self._mask_draw_time = 0.0
        if self._last_sweep is not None and self.is_sweeping:
            self._carrier_mask_limit(self._last_sweep[0] / 1e6, self._last_sweep[1], thresh)
        else:
            # (fine points: the mask is widened by twice the point spacing, and with nothing
            # swept there is no analyzer filter to allow for)
            lo, hi = self.sweep_panel.start_spin.value(), self.sweep_panel.stop_spin.value()
            x = np.linspace(lo, hi, int(min(60001, max(4001, (hi - lo) / 0.0025 + 1))))
            self._carrier_mask_limit(x, np.full(len(x), -300.0), thresh, rbw=0.0)

    def _draw_masks_without_detection(self, x_data, y_data):
        """The masks follow the sweep even while threat detection is off (a few times a second)."""
        if time.monotonic() - self._mask_draw_time < 0.25 or not getattr(self.spectrum_view, "_carrier_meta", None):
            return
        if self.threats_panel.carrier_mask_combo.currentData() == "channel":
            return
        x = np.asarray(x_data, dtype=float)
        self._carrier_mask_limit(x / 1e6 if x[0] > 1e5 else x, np.nan_to_num(y_data, nan=-130.0),
                                 float(self.threats_panel.intruder_thresh_spin.value()))

    def _carrier_mask_limit(self, x_mhz, y_dbm, thresh, rbw=None, draw=True):
        """
        (limit per sweep point, masks) for the coordinated carriers whose mask is shown,
        or (None, []) in "Channel only" mode or with no coordination loaded. Also draws
        the masks, a few times a second.
        """
        mode = self.threats_panel.carrier_mask_combo.currentData()
        meta = getattr(self.spectrum_view, "_carrier_meta", {})
        if mode == "channel" or not meta:
            if draw and self._mask_drawn:
                self._mask_drawn = False
                self.spectrum_view.set_emission_masks([])
                self.spectrum_view_b.set_emission_masks([])
            return None, []
        if draw:
            self._mask_drawn = True
        carriers = [{"freq_hz": (m["f_start"] + m["f_stop"]) / 2 * 1e6, "bw_hz": (m["f_stop"] - m["f_start"]) * 1e6,
                     "name": m["name"], "device": m.get("device", ""), "is_wmas": m.get("is_wmas", False)}
                    for m in meta.values() if m.get("visible", True)]
        if rbw is None:
            rbw = self._rbw_by_slot.get(self.multi_device_manager.focused_slot_id)
        # A carrier that is not on the air has no level to hang its mask on: its shape is
        # shown one division under the top of the plot
        idle_top = self.spectrum_view.ref_level - self.sweep_panel.scale_div
        limit, masks = emission_mask.limit_line(
            np.asarray(x_mhz, dtype=float) * 1e6, y_dbm, carriers, thresh,
            self.threats_panel.carrier_mask_margin_spin.value(), rbw,
            force_kind=None if mode == "auto" else mode, idle_top_dbm=idle_top)
        now = time.monotonic()
        if draw and now - self._mask_draw_time >= 0.25:
            self._mask_draw_time = now
            f_hz = np.asarray(x_mhz, dtype=float) * 1e6
            self.spectrum_view.set_emission_masks(self._mask_outlines(f_hz, masks))
            # Dual Spectrum: antenna B's view gets the same carriers' masks, hung on the
            # levels antenna B receives them at
            b = self._last_div_b if self._dual_spectrum else None
            if b is not None and len(b[0]) >= 4:
                fb = np.asarray(b[0], dtype=float)
                pb = np.nan_to_num(np.asarray(b[1], dtype=float), nan=-200.0)
                _limit_b, masks_b = emission_mask.limit_line(
                    fb, pb, carriers, thresh, self.threats_panel.carrier_mask_margin_spin.value(), rbw,
                    force_kind=None if mode == "auto" else mode, idle_top_dbm=idle_top)
                self.spectrum_view_b.set_emission_masks(self._mask_outlines(fb, masks_b))
            else:
                self.spectrum_view_b.set_emission_masks(self._mask_outlines(f_hz, [m for m in masks if not m["on_air"]])
                                                        if self._dual_spectrum else [])
        return limit, [m for m in masks if m["on_air"]]

    @staticmethod
    def _mask_outlines(f_hz, masks):
        """
        What to draw for a set of emission masks: one outline per state, the highest mask
        where neighbours' skirts overlap (that is the limit that applies there); broken
        masks are drawn whole, in red.
        """
        drawn = []
        for state in (False, "idle"):
            env = np.full(len(f_hz), np.nan)
            for m in masks:
                if (("idle" if not m["on_air"] else m["at_hz"] is not None) is state) and len(m["x_hz"]):
                    i = np.searchsorted(f_hz, m["x_hz"])
                    env[i] = np.fmax(env[i], m["y_dbm"])
            if not np.isnan(env).all():
                drawn.append((f_hz / 1e6, env, state))
        drawn += [(m["x_hz"] / 1e6, m["y_dbm"], True) for m in masks if m["on_air"] and m["at_hz"] is not None]
        return drawn

    def _mask_break_note(self, key_mhz: float, new: dict) -> dict:
        """Say on a listed carrier whose emission mask it breaks."""
        # (an entry's key moves to its strongest point, and a break is only news while it lasts)
        now = time.time()
        for k in [k for k, v in self._mask_breaks.items() if now - v["t"] > 10.0]:
            del self._mask_breaks[k]
        near = min(self._mask_breaks, key=lambda k: abs(k - key_mhz), default=None)
        b = self._mask_breaks[near] if near is not None and abs(near - key_mhz) <= 0.15 else None
        if not b:
            return new
        off_khz = (b["peak_mhz"] - b["fc_mhz"]) * 1e3
        note = (f"Breaks the {emission_mask.MASK_LABEL[b['kind']]} mask of {b['name']} ({b['fc_mhz']:.3f} MHz) by "
                f"{b['excess_db']:.0f} dB; the strongest signal in that channel is {off_khz:+.0f} kHz off its centre.")
        new = dict(new)
        new["details"] = (note + " " + (new.get("details") or "")).strip()
        new.setdefault("suggestion", "")
        if not new["suggestion"]:
            new["suggestion"] = f"Something other than {b['name']} is transmitting on or beside its frequency"
        return new

    def _apply_context(self, key_mhz: float, new: dict, entry: dict) -> dict:
        return self._mask_break_note(key_mhz, self._apply_channel_context(key_mhz, new, entry))

    def _apply_channel_context(self, key_mhz: float, new: dict, entry: dict) -> dict:
        """
        Refine a spectral identification with what is known about the channel
        it sits in: a wide block on a channel with a licensed TV station is
        that station, and a narrow or keyed carrier in the T-Band is most
        likely land mobile radio (assumed when no transmitter lookup has been
        run, confirmed or dropped when one has).
        """
        tv = self._tv_channel_at(key_mhz)
        if tv is None:
            return new
        ch, f0, f1 = tv
        cat = new.get("category", "")
        if cat in ("WMAS (TDMA)", "Wideband"):
            stations = self.dtv_stations.get(ch)
            if stations:
                call = str(stations[0].get("call_sign", "")).strip() or "licensed station"
                new.update({"signature": f"Digital TV — ch {ch} ({call})", "category": "Broadcast TV", "confidence": 85,
                            "color": "#9e9e9e", "candidates": [("Digital TV", 85)], "suggestion": "",
                            "details": f"{call} is licensed on TV channel {ch} ({f0:g}–{f1:g} MHz) here (transmitter lookup). "
                                       "Turn its channel mask on to stop it being listed."})
            elif cat == "Wideband":
                new["signature"] = f"Wideband block in TV ch {ch} (TV or WMAS)"
                if not (self.dtv_stations or self.lmr_stations):
                    new["suggestion"] = "Run the transmitter lookup (Broadcast / DTV) to see whether a TV station is licensed here"
            else:
                new["details"] = ((new.get("details") or "") + f" Occupies TV channel {ch}.").strip()
            return new
        narrow = cat in ("Unresolved", "Not wireless audio", "Weak carrier")
        if narrow and self.current_region == "North America" and ch in self.TBAND_CHANNELS:
            lookup_done = bool(self.dtv_stations or self.lmr_stations)
            age = time.time() - entry.get("first_seen", time.time())
            bursts = entry.get("bursts", 1)
            keyed = bursts >= 2 or (age > 4 and entry.get("on_s", 0.0) < 0.6 * age)
            ev = list(new.get("evidence") or [])
            if keyed:
                ev.append(f"Keys on and off ({bursts} transmission(s) in {age:.0f} s): typical of two-way radio")
            base = {"category": "Land mobile radio", "color": "#64748b", "candidates": [("Land mobile radio", 60)], "evidence": ev}
            if ch in self.lmr_stations:
                new.update(base, signature=f"Land mobile radio — T-Band ch {ch}", confidence=80, suggestion="",
                           details=f"Land mobile radio is licensed in TV channel {ch} ({f0:g}–{f1:g} MHz) here (transmitter lookup). "
                                   "Not usable for wireless audio.")
            elif not lookup_done:
                new.update(base, signature=f"Probable land mobile radio (T-Band ch {ch})", confidence=60 if keyed else 45,
                           details=f"A narrow carrier in the T-Band ({f0:g}–{f1:g} MHz), which is shared with public-safety "
                                   "and business two-way radio in US metro areas. Assumed because no transmitter lookup "
                                   "has been run for this location.",
                           suggestion="Run the transmitter lookup (Broadcast / DTV) to confirm what is licensed on this channel here")
            elif ch not in self.dtv_stations:
                new.update(base, signature=f"Possible land mobile radio (T-Band ch {ch})", confidence=50 if keyed else 35,
                           details=f"A narrow carrier in the T-Band; the transmitter lookup lists neither a TV station nor "
                                   f"land mobile radio on channel {ch} here.", suggestion="")
        return new

    # --- Intermodulation ---
    def _set_coordination(self, parsed: dict):
        """Keep coordinated carriers with their zone (only co-located transmitters
        mix) and whether they are spares (checked as targets, not sources)."""
        carriers = []
        for site in parsed.get("sites", []):
            for zone in site.get("zones", []):
                zone_key = f"{site.get('id', '')}/{zone.get('id', zone.get('name', ''))}"
                for group in zone.get("groups", []):
                    gname = str(group.get("name", ""))
                    spare = any(w in gname.lower() for w in ("spare", "backup", "back-up"))
                    for c in group.get("carriers", []):
                        f = c.get("freq_hz") or (c.get("freq_mhz", 0) * 1e6)
                        if f:
                            carriers.append({"name": c.get("name") or f"{f / 1e6:.3f}", "freq_hz": float(f),
                                             "bw_hz": float(c.get("bandwidth_hz") or 200e3),
                                             "zone": zone_key, "group": gname, "spare": spare})
        self.coord_carriers = carriers
        n_spare = sum(c["spare"] for c in carriers)
        self.threats_panel.im_status_lbl.setText(
            f"{len(carriers)} coordinated carriers ({n_spare} spare) in "
            f"{len({c['zone'] for c in carriers})} zone(s). Products are computed within each zone.")
        self._rebuild_intermod(force=True)

    def _level_at(self, freq_hz: float, bw_hz: float = 200e3):
        if self._last_sweep is None:
            return None
        f, p = self._last_sweep
        sel = np.abs(f - freq_hz) <= max(bw_hz / 2, f[1] - f[0])
        return float(p[sel].max()) if sel.any() else None

    def _is_on_air(self, freq_hz: float, bw_hz: float) -> bool:
        level = self._level_at(freq_hz, bw_hz)
        if level is None:
            return False
        floor = float(np.percentile(self._last_sweep[1], 20))
        return level >= max(floor + 10.0, self.threats_panel.intruder_thresh_spin.value())

    def _intermod_sources(self, settings):
        sources = []
        for c in self.coord_carriers:
            if c["spare"]:
                continue
            if settings["source"] == "on_air" and not self._is_on_air(c["freq_hz"], c["bw_hz"]):
                continue
            sources.append(Transmitter(c["freq_hz"], c["name"], c["zone"], c["bw_hz"]))
        if settings["include_detected"]:
            known = {round(t.freq_hz / 25e3) for t in sources}
            for k, e in self.intruders.items():
                if round(k * 1e6 / 25e3) not in known and time.time() - e["last_seen"] < 10:
                    sources.append(Transmitter(k * 1e6, f"{k:.3f} (detected)", "", 200e3))
            # Front-end intermod: everything reaching the receivers mixes
            sources = [Transmitter(t.freq_hz, t.name, "receivers", t.bandwidth_hz) for t in sources]
        return sources

    def _rebuild_intermod(self, force: bool = False):
        settings = self.threats_panel.intermod_settings()
        if not self.coord_carriers and not settings["include_detected"]:
            self._im_map = None
            self.spectrum_view.set_intermod_markers([])
            return
        sources = self._intermod_sources(settings)
        key = (tuple(sorted((round(t.freq_hz), t.zone) for t in sources)), settings["orders"])
        if not force and key == self._im_source_key:
            return
        self._im_source_key = key
        lo, hi = (self._last_sweep[0][0] - 5e6, self._last_sweep[0][-1] + 5e6) if self._last_sweep else (None, None)
        self._im_map = IntermodMap(sources, settings["orders"], lo_hz=lo, hi_hz=hi) if len(sources) >= 2 else None
        n = len(self._im_map.products) if self._im_map else 0
        n_coord = len(self.coord_carriers)
        n_spare = sum(c["spare"] for c in self.coord_carriers)
        self.threats_panel.im_status_lbl.setText(
            (f"{n_coord} coordinated ({n_spare} spare). " if n_coord else "")
            + f"Sources: {len(sources)} ({'on air' if settings['source'] == 'on_air' else 'all coordinated'}"
            f"{' + detected' if settings['include_detected'] else ''}), {n} products in range.")
        self._refresh_intermod_overlay(settings)

    def _refresh_intermod_overlay(self, settings=None):
        """Draw the products at their estimated levels (from the carriers' levels in the latest sweep)."""
        settings = settings or self.threats_panel.intermod_settings()
        if not (settings["overlay"] and self._im_map):
            self.spectrum_view.set_intermod_markers([])
            return
        products = self._im_map.products
        if len(products) > 3000:   # keep the display usable: lowest orders first
            products = sorted(products, key=lambda p: {3: 0, 5: 1, 33: 2, 7: 3}[p.order])[:3000]
        # A source's level: what the sweep shows at its frequency. A coordinated carrier that is
        # not on air (the "all coordinated" source setting) is assumed as strong as the on-air ones.
        levels = {}
        for t in {s for p in products for s in p.sources}:
            levels[t] = self._level_at(t.freq_hz, t.bandwidth_hz) if self._is_on_air(t.freq_hz, t.bandwidth_hz) else None
        on_air = [l for l in levels.values() if l is not None]
        assumed = float(np.median(on_air)) if on_air else None
        level_of = lambda t: levels[t] if levels[t] is not None else assumed
        marks = [(p.freq_hz / 1e6, p.order, estimate_level(p, level_of, settings["im3_dbc"])) for p in products]
        self.spectrum_view.set_intermod_markers(marks)

    def _intermod_at(self, freq_hz: float, bw_hz: float = 200e3, limit: int = 3):
        if not self._im_map:
            return []
        return [p.describe() + f" = {p.freq_hz / 1e6:.3f} MHz" for p in self._im_map.near(freq_hz, bw_hz, limit=limit)]

    def _on_intermod_check(self):
        if not self.coord_carriers:
            QMessageBox.information(self, "Intermodulation", "Import a Soundbase or Wireless Workbench coordination first.")
            return
        self._rebuild_intermod(force=True)
        rows = []
        for c in self.coord_carriers:
            hits = self._im_map.near(c["freq_hz"], c["bw_hz"]) if self._im_map else []
            if hits:
                counts = {}
                for h in hits:
                    counts[h.label] = counts.get(h.label, 0) + 1
                text = hits[0].describe()
                more = len(hits) - 1
                if more:
                    text += f"; +{more} more (" + ", ".join(f"{v} {k}" for k, v in counts.items()) + ")"
            else:
                text = "Clear"
            rows.append((c["name"], c["freq_hz"] / 1e6, text, c["spare"], len(hits)))
        rows.sort(key=lambda r: (-(r[4] > 0 and not r[3]), -(r[4] > 0), r[1]))
        self.threats_panel.show_intermod_results(rows)
        hit = sum(1 for r in rows if r[4] and not r[3])
        hit_sp = sum(1 for r in rows if r[4] and r[3])
        self.threats_panel.im_status_lbl.setText(
            f"{hit} coordinated and {hit_sp} spare frequencies have products landing on them "
            f"(of {len(rows)}).")

    def _on_intermod_verify(self):
        """Attenuation test on the selected threat: +10 dB input attenuation for a
        few sweeps. Real signals drop 10 dB; analyzer-made intermod drops ~30 dB."""
        if not self.is_connected or self._im_verify:
            return
        tbl = self.threats_panel.intruder_table
        row = tbl.currentRow()
        item = tbl.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(self, "Verify", "Select a carrier in the threat table first.")
            return
        freq_hz = float(item.data(Qt.ItemDataRole.UserRole) or float(item.text())) * 1e6
        sp = self.sweep_panel
        self._im_verify = {"freq": freq_hz, "auto": sp.auto_atten_check.isChecked(),
                           "atten": sp.atten_spin.value(), "levels": [], "base": None}
        base_atten = 0 if sp.auto_atten_check.isChecked() else sp.atten_spin.value()
        if base_atten + 10 > sp.atten_spin.maximum():
            QMessageBox.information(self, "Verify", "Attenuation is already near its maximum; lower it first.")
            self._im_verify = None
            return
        self._im_verify["base_atten"] = base_atten
        self.threats_panel.im_status_lbl.setText(f"Verifying {freq_hz / 1e6:.3f} MHz: measuring at {base_atten} dB…")
        sp.auto_atten_check.setChecked(False)
        sp.atten_spin.setValue(base_atten)
        self.apply_amplitude_settings()
        QTimer.singleShot(1500, lambda: self._im_verify_step("base"))

    def _im_verify_step(self, phase: str):
        v = self._im_verify
        if not v:
            return
        sp = self.sweep_panel
        level = self._level_at(v["freq"], 100e3)
        if phase == "base":
            v["base"] = level
            sp.atten_spin.setValue(v["base_atten"] + 10)
            self.apply_amplitude_settings()
            QTimer.singleShot(1500, lambda: self._im_verify_step("raised"))
            return
        # restore the user's settings
        sp.atten_spin.setValue(v["atten"])
        sp.auto_atten_check.setChecked(v["auto"])
        self.apply_amplitude_settings()
        self._im_verify = None
        if v["base"] is None or level is None:
            self.threats_panel.im_status_lbl.setText("Verify: no level measured (is the sweep running?).")
            return
        # The displayed level already compensates attenuation, so a real signal
        # stays put and analyzer-made intermod drops by ~2x the step.
        drop = v["base"] - level
        verdict, _ = analyzer_or_real(0.0, -(drop + 10.0), 10.0)
        msg = {"real": "real signal on the air", "analyzer": "made inside the analyzer (overload): add attenuation",
               "unclear": "unclear (fluctuating signal?): try again"}[verdict]
        self.threats_panel.im_status_lbl.setText(
            f"Verify {v['freq'] / 1e6:.3f} MHz: {v['base']:.1f} → {level:.1f} dBm with +10 dB attenuation "
            f"({drop:+.1f} dB): {msg}.")

    def _fingerprint_channels(self, limit=32):
        """Recently seen carriers, strongest first, as MSCAN channel entries."""
        now = time.time()
        recent = [(k, e) for k, e in self.intruders.items() if now - e["last_seen"] < 30.0]
        recent.sort(key=lambda kv: -kv[1]["power"])
        return [{"freq_hz": k * 1e6, "name": f"{k:.3f} MHz"} for k, _ in recent[:limit]]

    def _on_fingerprint_requested(self):
        if not self.is_connected:
            QMessageBox.information(self, "Fingerprint Carriers", "Connect an analyzer first.")
            return
        if self._fp_background:
            self.threats_panel.fingerprint_status_lbl.setText(
                "Analyzer B is already fingerprinting carriers continuously.")
            return
        if self._fp_pass or not self._mode_available("MSCAN", "Fingerprinting with MSCAN"):
            return
        channels = self._fingerprint_channels()
        if not channels:
            QMessageBox.information(self, "Fingerprint Carriers",
                                    "No carriers detected yet. Enable threat detection and let it sweep first.")
            return
        if self._last_operating_mode != "SWP":
            QMessageBox.information(self, "Fingerprint Carriers",
                                    "Fingerprinting runs from the swept spectrum. Return to the spectrum view first.")
            return
        # ~0.12 s per carrier per round, enough rounds for the history the
        # fingerprinter needs; the sweep resumes afterwards (waterfall kept).
        duration_s = min(12.0, max(3.0, 0.12 * len(channels) * 8))
        self._fp_pass = {"slot": self.multi_device_manager.focused_slot_id, "spectra": 0,
                         "carriers": len(channels)}
        self.threats_panel.fingerprint_btn.setEnabled(False)
        self.threats_panel.fingerprint_status_lbl.setText(
            f"Fingerprinting {len(channels)} carrier(s) with MSCAN for ~{duration_s:.0f} s…")
        self.multi_device_manager.set_operating_mode("MSCAN")
        self.multi_device_manager.configure_mscan(
            channels, dwell_time=0.01, detector=3,  # RMS: average power, not peak
            ref_level=self.sweep_panel.ref_level_spin.value(), preamp=0, atten=-1, decimate=256)
        QTimer.singleShot(int(duration_s * 1000), self._finish_fingerprint_pass)

    def _finish_fingerprint_pass(self):
        fp, self._fp_pass = self._fp_pass, None
        self.threats_panel.fingerprint_btn.setEnabled(True)
        self.resume_rf_sweep()
        if not fp:
            return
        self._refresh_fingerprints()
        self._update_intruders_ui(force=True)
        if fp["spectra"] == 0:
            self.threats_panel.fingerprint_status_lbl.setText(
                "Fingerprint pass got no MSCAN data; identification is from the sweep only.")
        else:
            self.threats_panel.fingerprint_status_lbl.setText(
                f"Fingerprinted {fp['carriers']} carrier(s) from {fp['spectra']} MSCAN spectra "
                f"at {time.strftime('%H:%M:%S')}. Hover a row for the evidence.")

    def _on_background_fingerprint_toggled(self, enabled: bool):
        mdm = self.multi_device_manager
        slot_b = mdm.slots.get("slot_b")
        if enabled:
            if not slot_b or not slot_b.is_connected:
                QMessageBox.information(self, "Fingerprint Carriers",
                                        "Connect a second analyzer (Analyzer B) to fingerprint in the background.")
                self.threats_panel.bg_fingerprint_cb.setChecked(False)
                return
            if mdm.topology in (MultiDeviceTopology.SPLIT_SWEEP, MultiDeviceTopology.DIVERSITY):
                QMessageBox.information(self, "Fingerprint Carriers",
                                        "Analyzer B is part of the sweep in this topology. "
                                        "Switch to Single or Independent to use it for fingerprinting.")
                self.threats_panel.bg_fingerprint_cb.setChecked(False)
                return
            self._fp_background = True
            self._fp_bg_channels = ()
            self._update_background_fingerprint()
            if not hasattr(self, "_fp_bg_timer"):
                self._fp_bg_timer = QTimer(self)
                self._fp_bg_timer.timeout.connect(self._update_background_fingerprint)
            self._fp_bg_timer.start(10000)
        else:
            self._fp_background = False
            if hasattr(self, "_fp_bg_timer"):
                self._fp_bg_timer.stop()
            if slot_b and slot_b.is_connected:
                slot_b.controller.stop_mscan()
                slot_b.controller.set_operating_mode("SWP")
            self.threats_panel.fingerprint_status_lbl.setText("Background fingerprinting stopped.")

    def _update_background_fingerprint(self):
        """Point Analyzer B's MSCAN at the current carrier list when it changes."""
        slot_b = self.multi_device_manager.slots.get("slot_b")
        if not self._fp_background or not slot_b or not slot_b.is_connected:
            return
        channels = self._fingerprint_channels()
        key = tuple(round(c["freq_hz"]) for c in channels)
        if not channels:
            self.threats_panel.fingerprint_status_lbl.setText(
                "Analyzer B waiting for carriers to fingerprint…")
            return
        if key == self._fp_bg_channels:
            return
        self._fp_bg_channels = key
        slot_b.controller.set_operating_mode("MSCAN")
        slot_b.controller.configure_mscan(channels, 0.01, 3, self.sweep_panel.ref_level_spin.value(), 0, -1, 256)
        self.threats_panel.fingerprint_status_lbl.setText(
            f"Analyzer B fingerprinting {len(channels)} carrier(s) continuously.")

    def _clear_intruders(self):
        self.intruders.clear()
        self._mask_breaks.clear()
        self.fingerprinter.clear()
        self.current_intruder_index = -1
        self.top_bar.set_intruders_banner(0)
        self.threats_panel.intruder_table.setRowCount(0)

    def _on_intruder_prev(self):
        count = len(self.intruders)
        if count > 0:
            self.current_intruder_index = (self.current_intruder_index - 1) % count
            self._jump_to_current_intruder()

    def _on_intruder_next(self):
        count = len(self.intruders)
        if count > 0:
            self.current_intruder_index = (self.current_intruder_index + 1) % count
            self._jump_to_current_intruder()

    def _on_intruder_badge_clicked(self):
        self.nav_rail.set_active_mode(1) # Switch to Threats Panel

    def _jump_to_current_intruder(self):
        sorted_intruders = sorted(self.intruders.items(), key=lambda kv: kv[1]["power"], reverse=True)
        if 0 <= self.current_intruder_index < len(sorted_intruders):
            f, info = sorted_intruders[self.current_intruder_index]
            self.spectrum_view.v_line.setPos(f)
            self.spectrum_view.v_line.show()
            self.waterfall_view.v_line.setPos(f)
            self.waterfall_view.v_line.show()
            self._update_hud_readout(f, info["power"])
            self.top_bar.set_intruders_banner(len(sorted_intruders), self.current_intruder_index, f)
            
            # Select matching row in table regardless of sort order
            tbl = self.threats_panel.intruder_table
            for r in range(tbl.rowCount()):
                it = tbl.item(r, 0)
                if it:
                    val = it.data(Qt.ItemDataRole.UserRole)
                    if val is not None and abs(val - f) < 0.005:
                        tbl.selectRow(r)
                        break

    def _threat_marker_items(self):
        tree = self.threats_panel.markers_tree
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            f = it.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(f, float) and it.text(0).startswith("Threat:"):
                yield it, f

    def _masked_ranges(self) -> list:
        """
        (low, high) in MHz of everything already accounted for, exactly as drawn:
        TV and public-safety LMR channel masks that are on, coordinated carriers
        (Soundbase / Workbench) whose mask is shown, and carriers the user has
        moved from the alerts into the markers (while ticked). Intruder
        detection ignores whatever falls inside.
        """
        now = time.monotonic()
        if now - self._mask_cache[0] < 0.5:
            return self._mask_cache[1]
        r = []
        ps = self._public_safety_channels()
        for band in TV_CHANNEL_STANDARDS.get(self.current_region, []):
            if "start_ch" in band:
                for ch in range(band["start_ch"], band["end_ch"] + 1):
                    if self.active_channels.get(ch) or ps.get(ch):
                        f0 = band["start_freq"] + (ch - band["start_ch"]) * band["spacing"]
                        r.append((f0, f0 + band["spacing"]))
            for c_item in band.get("custom_items", []):
                if self.active_channels.get(c_item["id"]):
                    r.append((float(c_item["start"]), float(c_item["stop"])))
        meta = getattr(self.spectrum_view, "_carrier_meta", {})
        for c_id, region in self.spectrum_view.soundbase_masks.items():
            if meta.get(c_id, {}).get("visible", True):
                lo, hi = region.getRegion()
                r.append((float(lo), float(hi)))
        for it, f in self._threat_marker_items():
            if it.checkState(0) == Qt.CheckState.Checked:
                half = it.data(0, Qt.ItemDataRole.UserRole + 2) or 0.1
                r.append((f - half, f + half))
        r.sort()
        self._mask_cache = (now, r)
        return r

    def _is_masked(self, f_mhz: float, ranges=None) -> bool:
        for lo, hi in (self._masked_ranges() if ranges is None else ranges):
            if lo <= f_mhz <= hi:
                return True
            if lo > f_mhz:
                break
        return False

    def _add_intruders_to_markers(self):
        """Acknowledge the listed carriers: each becomes a ticked marker, which
        also takes it (and anything inside its width) out of the alerts."""
        known = {round(f, 3) for _, f in self._threat_marker_items()}
        for f, info in list(self.intruders.items()):
            if round(f, 3) in known:
                continue
            label = info.get("signature") or ""
            title = f"Threat: {f:.3f} MHz" + (f" — {label}" if label and "Analyzing" not in label else "")
            item = QTreeWidgetItem([title, f"{info['power']:.1f} dBm"])
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setData(0, Qt.ItemDataRole.UserRole, float(f))
            ext = info.get("extent_hz")
            half = max(0.1, (ext[1] - ext[0]) / 2e6 + 0.05) if ext else 0.1
            item.setData(0, Qt.ItemDataRole.UserRole + 2, float(half))
            self.threats_panel.markers_tree.addTopLevelItem(item)
        self._mask_cache = (0.0, [])

    def _on_marker_tree_item_changed(self, item, col):
        if col != 0:
            return
        self._mask_cache = (0.0, [])
        def update_item_masks(node):
            c_id = node.data(0, Qt.ItemDataRole.UserRole + 1)
            if c_id is not None:
                is_checked = (node.checkState(0) == Qt.CheckState.Checked)
                self.spectrum_view.set_soundbase_mask_visible(str(c_id), is_checked)
            for i in range(node.childCount()):
                update_item_masks(node.child(i))

        update_item_masks(item)

    def _on_soundbase_carrier_selected(self, freq: float):
        self.spectrum_view.v_line.setPos(freq)
        self.spectrum_view.v_line.show()
        self.waterfall_view.v_line.setPos(freq)
        self.waterfall_view.v_line.show()
        pwr = -85.0
        for f_key, info in self.intruders.items():
            if abs(f_key - freq) < 0.10:
                pwr = info.get("power", -85.0)
                break
        self._update_hud_readout(freq, pwr)

    def load_coordination_file(self, filepath: str = None):
        """
        Loads frequency coordination from either Soundbase (.sbcoordsite, .json)
        or Shure Wireless Workbench (.csv).
        Validates file format and prompts the user if invalid.
        """
        if filepath:
            fp = filepath
        else:
            # Start in the folder last loaded from, else the user's Documents
            default_dir = self.settings.value("last_coordination_dir", "", type=str)
            if not default_dir or not os.path.isdir(default_dir):
                default_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
            fp, _ = QFileDialog.getOpenFileName(
                self,
                "Load Coordination File (Soundbase / Wireless Workbench)",
                default_dir,
                "Supported Files (*.sbcoordsite *.json *.csv);;Soundbase Files (*.sbcoordsite *.json);;Wireless Workbench (*.csv);;All Files (*.*)"
            )

        if not fp:
            return
        self.settings.setValue("last_coordination_dir", os.path.dirname(os.path.abspath(fp)))

        ext = Path(fp).suffix.lower()
        if ext not in [".json", ".sbcoordsite", ".csv"]:
            QMessageBox.warning(
                self,
                "Invalid File Format",
                "Unsupported file selected.\n\nPlease upload a valid Soundbase JSON file (*.json, *.sbcoordsite) or a Wireless Workbench CSV file (*.csv)."
            )
            return

        try:
            if ext == ".csv":
                parsed = WWBParser.parse_file(fp)
            else:
                parsed = SoundbaseParser.parse_file(fp)

            carriers = parsed.get("all_carriers", [])
            self.spectrum_view.set_soundbase_masks(carriers)
            self._draw_carrier_masks()
            self._set_coordination(parsed)
            self.threats_panel.populate_soundbase_tree(parsed)
            site_name = parsed["sites"][0]["name"] if parsed.get("sites") else Path(fp).stem
            self.threats_panel.set_soundbase_active(site_name, len(carriers))
            if hasattr(self, 'mscan_panel'):
                self.mscan_panel.set_soundbase_data(parsed)
            if hasattr(self, 'mscan_view'):
                self.mscan_view.set_channels(carriers)

            # Check for exclusions imported from WWB
            active_tv = parsed.get("active_tv_channels", [])
            active_ps = parsed.get("active_public_safety_channels", [])
            if active_tv or active_ps:
                for ch in active_tv:
                    self.active_channels[ch] = True
                for ch in active_ps:
                    self.coordination_ps_channels.add(ch)

                # Ensure North America Channel 37 is strictly off-limits (Active)
                if self.current_region == "North America":
                    self.active_channels[37] = True

                self._refresh_channel_masks_all_views()

        except Exception as e:
            QMessageBox.warning(
                self,
                "Invalid File Format",
                f"Failed to parse coordination file:\n{e}\n\nPlease ensure you upload a valid Soundbase JSON file (*.json, *.sbcoordsite) or a Wireless Workbench CSV file (*.csv)."
            )

    def load_soundbase_json(self, filepath: str = None):
        """Backwards compatibility wrapper for load_coordination_file."""
        self.load_coordination_file(filepath)

    def _refresh_channel_masks_all_views(self):
        """Redraws channel and exclusion masks across all spectrum viewports."""
        ps_dict = self._public_safety_channels()
        std = TV_CHANNEL_STANDARDS.get(self.current_region, [])
        self.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_view_b.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_view.update_channel_masks(self.active_channels, std, ps_dict, self.station_info)
        self.waterfall_view.update_channel_masks(self.active_channels, std, ps_dict)
        if hasattr(self, 'multi_row_view'):
            self.multi_row_view.set_active_channels(self.active_channels, ps_dict)
            self.multi_row_view.update_channel_masks(self.active_channels, std, ps_dict)
        if hasattr(self, 'rtsa_view'):
            self.rtsa_view.set_active_channels(self.active_channels, ps_dict)
            self.rtsa_view.update_channel_masks(self.active_channels, std, ps_dict, self.station_info)
        if hasattr(self, 'demod_view'):
            self.demod_view.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
            self.demod_view.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)

    def _on_carrier_color_changed(self, carrier_id: str, new_color_hex: str):
        """
        Synchronizes per-frequency custom color selection across:
        1. Threats & Markers hierarchy tree
        2. Rapid Channel Monitor (MSCAN) hierarchy tree
        3. Main Spectrum View carrier masks
        4. Rapid Channel Monitor card widgets & timeline curve
        """
        c_id = str(carrier_id)
        if hasattr(self, 'threats_panel'):
            self.threats_panel.update_carrier_color(c_id, new_color_hex)
        if hasattr(self, 'mscan_panel'):
            self.mscan_panel.update_carrier_color(c_id, new_color_hex)
        if hasattr(self, 'spectrum_view'):
            self.spectrum_view.update_carrier_mask_color(c_id, new_color_hex)
        if hasattr(self, 'mscan_view'):
            self.mscan_view.update_channel_color(c_id, new_color_hex)

    # --- Calibration Management ---
    def open_calibration_manager(self, model=None, uid=None):
        target_m = model or self.current_model or self.target_device_model
        target_u = uid or self.current_uid or self.target_device_uid
        dlg = CalibrationManagerDialog(selected_model=target_m, selected_uid=target_u, parent=self)
        if dlg.exec():
            if not self.is_connected:
                self.connect_analyzer()

    def _restore_slots(self):
        """
        Every analyzer slot as the Connection dialog last remembered it: interface, address,
        the analyzer it was given, alias. (Slots A and B used to be left at their defaults,
        so a saved Ethernet analyzer came back as "USB Direct" at the next launch and the
        Connect button looked for a USB analyzer that was not there.)
        """
        try:
            slots = json.loads(self.settings.value("multi_device_slots", "") or "{}")
        except (TypeError, ValueError):
            return
        topo = self.settings.value("multi_device_topology", "")
        if topo:
            self.multi_device_manager.set_topology(topo)
        for s_id, s_cfg in slots.items():
            if not isinstance(s_cfg, dict):
                continue
            slot = self.multi_device_manager.ensure_slot(s_id)
            # Slot A is always in use on its own; the others as remembered
            slot.is_enabled = True if s_id == "slot_a" else bool(s_cfg.get("enabled", False))
            slot.role_alias = (s_cfg.get("alias") or "").strip()
            slot.interface_type = s_cfg.get("interface", slot.interface_type)
            slot.ip_address = s_cfg.get("ip", slot.ip_address)
            slot.port = int(s_cfg.get("port", slot.port))
            slot.usb_index = int(s_cfg.get("usb_index", slot.usb_index))
            slot.target_model = s_cfg.get("target_model")
            slot.target_uid = s_cfg.get("target_uid")
            slot.serial_port = s_cfg.get("serial_port")
            slot.serial_port = s_cfg.get("serial_port")

    # --- Sensor network / Locate ---
    def _sync_sensors(self):
        """Mirror the manager's slots into the sensor net and the Locate panel."""
        mdm = self.multi_device_manager
        for sid in list(self.sensor_net.sensors):
            if sid not in mdm.slots:
                self.sensor_net.remove_sensor(sid)
        for sid in sorted(mdm.slots):
            slot = mdm.slots[sid]
            s = self.sensor_net.ensure_sensor(sid, self._slot_label(sid))
            if not slot.is_connected:
                if s.gnss:
                    s.went_offline()
            elif slot.gnss and not s.gnss:
                s.add_fix(slot.gnss)
        if not self.locate_panel.sensor_table.hasFocus():
            self.locate_panel.show_sensors(self._locate_sensor_rows())
        self.locate_panel.show_gnss([(s.name, s.gnss_rows() if mdm.slots[sid].is_connected else "disconnected.")
                                     for sid, s in sorted(self.sensor_net.sensors.items())
                                     if sid in mdm.slots and (mdm.slots[sid].is_connected or mdm.slots[sid].is_enabled)])

    def _locate_sensor_rows(self) -> list:
        """
        The Locate panel's sensor rows (one place builds them: two that disagreed made the
        GNSS position blink in and out).
        """
        rows = []
        for sid in sorted(self.multi_device_manager.slots):
            slot = self.multi_device_manager.slots[sid]
            s = self.sensor_net.ensure_sensor(sid)
            # With GNSS as the source the table shows the (averaged) fix, not the manual fields
            lat, lon = s.lat, s.lon
            if s.position_source == "gnss":
                ll = s.latlon()
                lat, lon = (round(ll[0], 6), round(ll[1], 6)) if ll else (None, None)
            row = {"id": sid, "name": s.name, "source": s.position_source, "lat": lat, "lon": lon,
                   "x_m": s.x_m, "y_m": s.y_m, "connected": slot.is_connected, **s.table_fields()}
            if not slot.is_connected:
                # Nothing is heard from it: not "searching", whatever it said last
                row["lock"] = "Disconnected" if slot.is_enabled else "Not in use"
            rows.append(row)
        return rows

    def _on_gnss_updated(self, slot_id: str, g: dict):
        self.sensor_net.set_gnss(slot_id, g)
        if self.panel_stack.currentIndex() == 9:        # Locate is showing: keep its readout current
            self._sync_sensors()

    def _restart_position_averages(self):
        """Every sensor's GNSS position starts again from its next fix."""
        for s in self.sensor_net.sensors.values():
            s.restart_average()
        self.sensor_net.origin = None       # the local frame is rebuilt from the new positions
        self._sync_sensors()
        self._refresh_locate(force=True)
        self.locate_panel.set_status("Position averages restarted: each sensor's position builds up again from its next fixes.")
        self._locate_status_hold = time.monotonic() + 6.0

    def _on_sensor_position_edited(self, slot_id: str, d: dict):
        s = self.sensor_net.ensure_sensor(slot_id)
        if "source" in d:
            s.position_source = d["source"]
        for k in ("lat", "lon", "x_m", "y_m"):
            if k in d:
                setattr(s, k, d[k])
        self.sensor_net.origin = None   # recompute the local frame
        self._save_sensor_positions()
        self._sync_sensors()
        self._refresh_locate(force=True)

    # --- Time-difference location (core/tdoa.py) ---
    #
    # Every positioned sensor captures the carrier starting on the same GPS second (its own
    # GNSS 1PPS trigger), for several seconds running; the captures are correlated and the
    # arrival-time differences solved for a position. Requests go out early in a second so
    # that every analyzer is armed before the next one starts.
    TDOA_SECONDS = 8
    TDOA_SAMPLES = 32768
    TDOA_TIMEOUT_S = 40.0

    def start_tdoa(self, freq_hz: float):
        if self._tdoa is not None or self._dect_count is not None or self._showlink_airtime is not None:
            return
        net, mdm = self.sensor_net, self.multi_device_manager
        ready, waiting = {}, []
        for sid, xy in net.positions_xy().items():
            slot = mdm.slots.get(sid)
            if not slot or not slot.is_connected or "IQS" not in device_caps.resolve(slot.capabilities)["modes"]:
                continue
            if net.sensors[sid].has_fix():
                ready[sid] = xy
            else:
                waiting.append(net.sensors[sid].name)
        if len(ready) < 2:
            self.locate_panel.set_status(
                "Time-difference location needs two or more connected analyzers with a GNSS fix "
                "(three for a position)" + (f"; no fix yet on {', '.join(waiting)}." if waiting else "."))
            return
        bw = next((c["bw_hz"] for c in getattr(self, "coord_carriers", []) if abs(c["freq_hz"] - freq_hz) < 50e3), 200e3)
        self._tdoa = {"session": tdoa.TDOASession(ready, freq_hz), "freq": float(freq_hz), "sids": sorted(ready),
                      "dec": tdoa.decimation_for(bw), "started": time.monotonic(), "asked": None, "round": 0,
                      "timer": QTimer(self)}
        self._tdoa["timer"].timeout.connect(self._tdoa_tick)
        self._tdoa["timer"].start(50)
        self.locate_panel.set_tdoa_state(True)
        self.locate_panel.set_status(f"Locating {freq_hz / 1e6:.3f} MHz with {len(ready)} sensors: waiting for the GPS second…")

    def _tdoa_tick(self):
        run = self._tdoa
        if run is None:
            return
        now = time.monotonic()
        if len(run["session"].rounds) >= self.TDOA_SECONDS or now - run["started"] > self.TDOA_TIMEOUT_S:
            self._tdoa_finish()
            return
        if run["asked"] is not None and now - run["asked"] < 2.5:
            return                                  # this second's captures are still on their way
        if run["asked"] is not None:
            run["session"].discard_incomplete()     # not every sensor answered: start a new second
        if not 0.15 <= time.time() % 1.0 <= 0.55:
            return                                  # too close to a second's edge: sensors would split across it
        run["round"] += 1
        run["asked"] = now
        ref_level = self.sweep_panel.ref_level_spin.value()
        for sid in run["sids"]:
            self.multi_device_manager.request_timed_capture(sid, run["freq"], run["dec"], self.TDOA_SAMPLES, ref_level,
                                                            tdoa.PPS_TRIGGER, request_id=("tdoa", run["round"]))

    def _on_timed_capture(self, slot_id: str, iq, info: dict):
        run = self._tdoa
        if run is None or not isinstance(info.get("id"), tuple) or info["id"][0] != "tdoa":
            return
        if not info.get("ok"):
            self.top_bar.flash_status(f"{self._slot_label(slot_id)}: timed capture failed ({info.get('error', 'no data')})", 5000)
            return
        if run["session"].add_capture(slot_id, iq, info) is not None:
            run["asked"] = None                     # every sensor answered: on to the next second
            self.locate_panel.set_status(f"Locating {run['freq'] / 1e6:.3f} MHz: {len(run['session'].rounds)} of "
                                         f"{self.TDOA_SECONDS} seconds captured…")

    def _tdoa_finish(self):
        run, self._tdoa = self._tdoa, None
        if run is None:
            return
        run["timer"].stop()
        self.locate_panel.set_tdoa_state(False)
        res = run["session"].result()
        net = self.sensor_net
        names = {sid: net.sensors[sid].name for sid in run["sids"]}
        if res["fix"] is not None:
            fix = res["fix"]
            net.tdoa_fixes[run["freq"]] = (fix, time.time(), res)
            net.solve()
            where = f"{fix.x:.0f} m east, {fix.y:.0f} m north of the sensors' centre"
            if net.origin and net.origin[0] is not None:
                lat, lon = latlon_from_enu(fix.x, fix.y, net.origin[0], net.origin[1])
                where = f"{lat:.6f}, {lon:.6f}"
            spread = max(res["spread_ns"].values()) if res["spread_ns"] else 0.0
            text = (f"{run['freq'] / 1e6:.3f} MHz located by arrival time: {where}, ±{fix.radius_m:.0f} m "
                    f"({res['rounds']} seconds, {len(run['sids'])} sensors; timing scatter up to {spread:.0f} ns between seconds).")
        else:
            diffs = ", ".join(f"{names[sid]} {v:+.0f} ns" for sid, v in res["tdoa_ns"].items() if sid != res["ref"])
            text = (f"{run['freq'] / 1e6:.3f} MHz: {res['note']}" +
                    (f" Arrival times against {names.get(res['ref'], '?')}: {diffs}." if diffs else ""))
        self._tdoa_last = res
        self._locate_selected_hz = run["freq"]
        self._refresh_locate(force=True)
        self.locate_panel.set_status(text)
        self._locate_status_hold = time.monotonic() + 30.0      # leave the result up before the routine status returns

    def _on_locate_settings(self, d: dict):
        self.sensor_net.path_loss_exp = float(d.get("path_loss_exp", self.sensor_net.path_loss_exp))
        self.sensor_net.margin_db = float(d.get("margin_db", self.sensor_net.margin_db))

    def _on_locate_carrier_selected(self, freq_hz: float):
        self._locate_selected_hz = freq_hz
        self._refresh_locate(force=True)

    def _refresh_locate(self, force: bool = False):
        if not force and self.panel_stack.currentIndex() != 9:
            return
        net = self.sensor_net
        pos = net.positions_xy()
        sensors = [(net.sensors[sid].name, x, y, net.sensors[sid].status()) for sid, (x, y) in pos.items()]
        self.map_view.set_sensors(sensors)
        ests = list(net.estimates.values())
        self.map_view.set_carriers(ests, self._locate_selected_hz)
        self.locate_panel.show_carriers(ests, self._locate_selected_hz)
        n_pos = len(pos)
        n_on = sum(1 for s in self.multi_device_manager.slots.values() if s.is_connected)
        if self._tdoa is not None or time.monotonic() < self._locate_status_hold:
            pass                                    # a location run's own status line is showing
        elif self.multi_device_manager.topology != MultiDeviceTopology.SENSOR_NET:
            self.locate_panel.set_status("Choose the Sensor Network topology in the Connection dialog to feed this mode.")
        elif n_pos < 3:
            self.locate_panel.set_status(f"{n_on} sensor(s) connected, {n_pos} with a position. Positions for 3 or more "
                                         "sensors are needed for a fix (2 give a point between them).")
        else:
            self.locate_panel.set_status(f"{n_on} sensor(s) connected, {n_pos} positioned. Power-based fixes; "
                                         "expect tens of metres outdoors, a zone indoors.")
        if self.panel_stack.currentIndex() == 9 and not self.locate_panel.sensor_table.hasFocus():
            self.locate_panel.show_sensors(self._locate_sensor_rows())

    def _save_sensor_positions(self):
        d = {sid: {"source": s.position_source, "lat": s.lat, "lon": s.lon, "x_m": s.x_m, "y_m": s.y_m}
             for sid, s in self.sensor_net.sensors.items()}
        self.settings.setValue("sensor_positions", json.dumps(d))

    def _load_sensor_positions(self):
        try:
            d = json.loads(self.settings.value("sensor_positions", "") or "{}")
        except (TypeError, ValueError):
            d = {}
        for sid, v in d.items():
            s = self.sensor_net.ensure_sensor(sid)
            s.position_source = v.get("source", "gnss")
            s.lat, s.lon, s.x_m, s.y_m = v.get("lat"), v.get("lon"), v.get("x_m"), v.get("y_m")

    # --- Input chains (antenna / cable / amplifier compensation) ---
    def _slot_label(self, slot_id: str) -> str:
        slot = self.multi_device_manager.slots.get(slot_id)
        if not slot:
            return slot_id
        return slot.role_alias.strip() or slot.name

    def open_input_chains(self):
        slots = {sid: self._slot_label(sid) for sid in self.multi_device_manager.slots}
        dlg = InputChainDialog(self.input_chains, slots, self)
        if dlg.exec():
            self._apply_input_chains()

    def _apply_input_chains(self):
        lines = {}
        for sid in self.multi_device_manager.slots:
            chain = self.input_chains.for_slot(sid)
            freqs, corr = chain.sdk_table() if chain else ([], [])
            self.multi_device_manager.set_input_compensation(sid, chain.name if chain else "", freqs, corr)
            if chain:
                lines[self._slot_label(sid)] = f"{chain.name} ({chain.summary()})"
        self.top_bar.set_input_chain_state(lines)

    def _on_input_comp_applied(self, slot_id: str, status: int, points: int):
        slot = self.multi_device_manager.slots.get(slot_id)
        name = slot.input_chain_name if slot else ""
        if status != 0:
            QMessageBox.warning(self, "Input chain not applied",
                                f"{self._slot_label(slot_id)} did not accept the input chain correction "
                                f"(SDK status {status}). Levels are at the analyzer's input.")
        elif name and points:
            self.top_bar.flash_status(f"{self._slot_label(slot_id)}: input chain '{name}' applied")

    def import_calibration_files(self, model=None, uid=None):
        self.open_calibration_manager(model, uid)

    def _on_colormap_changed(self, cmap_name: str):
        self.waterfall_colormap = cmap_name
        self.settings.setValue("waterfall_colormap", cmap_name)
        if hasattr(self, 'waterfall_view'):
            self.waterfall_view.set_colormap(cmap_name)
        if hasattr(self, 'multi_row_view'):
            self.multi_row_view.set_colormap(cmap_name)

    def closeEvent(self, event):
        if hasattr(self, 'multi_device_manager'):
            self.multi_device_manager.disconnect_all()
        event.accept()
