"""
main_window.py - Master Application Window for RF Recon Modern (Freqon).
Coordinates the Top Transport Bar, Left Workflow Navigation Hub, Central Dual-Canvas
Spectrogram & Spectrum Viewports, RF Hardware Engine, and Specialized Telemetry Subsystems.
"""

import sys
import os
import math
import json
import time
import numpy as np
import scipy.signal as signal
import pyqtgraph as pg
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStackedWidget, QFileDialog, QMessageBox, QTableWidgetItem,
    QTreeWidgetItem, QRadioButton, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QSettings, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QAction, QActionGroup

from core.constants import (
    TV_CHANNEL_STANDARDS, DEFAULT_REGIONS, DEFAULT_NORTH_AMERICA_ACTIVE,
    DEFAULT_EUROPE_ACTIVE, WATERFALL_COLORMAPS
)
from core.device_controller import DeviceController
from core.multi_device_manager import MultiDeviceManager, MultiDeviceTopology
from core.calibration_manager import CalibrationManager
from core.fcc_database import FCCDatabaseManager
from core.ofcom_database import OfcomDatabaseManager
from core.dect_analyzer import DECTAnalyzerEngine, DECT_BANDS, TDMATimeslotDialog
from core.showlink_crmx_analyzer import ShowLinkCRMXEngine, SHOWLINK_CHANNELS, ShowlinkMapDialog
from core.transmitter_classifier import TransmitterClassifier

from .widgets.top_bar import TopBar
from .widgets.nav_rail import NavRail
from .widgets.spectrum_view import SpectrumView
from .widgets.waterfall_view import WaterfallView
from .widgets.multi_row_waterfall import MultiRowWaterfallView
from .widgets.rtsa_view import RTSAView
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
from core.demod_engine import DemodEngine, DemodResult
from core.soundbase_parser import SoundbaseParser

from .dialogs.cal_dialogs import CalibrationManagerDialog, MissingCalDialog, DragDropCalDialog, ClearCalDialog
from .dialogs.connection_dialog import ConnectionDialog
from .dialogs.audio_demod_dialog import AudioDemodDialog
from .dialogs.settings_dialogs import (
    WaterfallSettingsDialog, QuickSettingsDialog, LaunchSettingsDialog, MarkerSettingsDialog
)

class MainWindow(QMainWindow):
    """
    Main Application Window orchestrating the entire RF coordination workspace.
    """
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
        self.classifier = TransmitterClassifier()
        
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
        self.demod_engine = DemodEngine()
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
        self.waterfall_buffer = np.full((self.waterfall_history_depth, 1000), -130.0, dtype=np.float32)
        self._last_waterfall_render_time = 0.0
        
        self.intruders = {} # freq -> {power, signature, ...}
        self.current_intruder_index = -1
        self._last_intruder_ui_update = 0.0
        self.dtv_detect_active = False
        self.tband_detect_active = False
        self.tband_history = []
        self.active_channels = {}
        self.station_db_names = {}
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
        self.panel_stack.setMinimumWidth(280)
        self.panel_stack.setMaximumWidth(340)
        
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
        
        left_hub_layout.addWidget(self.panel_stack)
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
        self.view_v_splitter.setSizes([340, 360])
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
        
        viewport_layout.addWidget(self.viewport_stack)
        self.main_h_splitter.addWidget(self.viewport_container)
        
        # Set Splitter Stretch Factors (Left: 0, Center Viewport: 1)
        self.main_h_splitter.setSizes([460, 880])
        self.main_h_splitter.setStretchFactor(0, 0)
        self.main_h_splitter.setStretchFactor(1, 1)

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
        self.spectrum_view.thresholdChanged.connect(self.dtv_panel.threshold_spin.setValue)
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
        self.sweep_panel.editQuickSettingsClicked.connect(self.open_quick_settings_editor)
        self.sweep_panel.amplitudeChanged.connect(self.apply_amplitude_settings)
        self.sweep_panel.autoRefLevelClicked.connect(self.auto_reference_level)
        self.sweep_panel.sweepSettingsChanged.connect(self.apply_sweep_settings)
        self.sweep_panel.detectSettingsChanged.connect(self.apply_detect_settings)
        self.sweep_panel.bwSettingsChanged.connect(self.apply_bw_settings)
        self.sweep_panel.traceToggled.connect(self._on_panel_trace_toggled)
        self.sweep_panel.traceFreezeToggled.connect(self._on_trace_freeze_toggled)
        self.sweep_panel.traceColorChanged.connect(self._on_trace_color_changed)
        self.sweep_panel.avgSweepsChanged.connect(self._on_avg_sweeps_changed)
        self.sweep_panel.linkViewToggled.connect(self._on_link_view_toggled)
        
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
        self.dtv_panel.thresholdChanged.connect(self.spectrum_view.threshold_line.setPos)
        self.dtv_panel.showThresholdToggled.connect(self.spectrum_view.threshold_line.setVisible)
        self.dtv_panel.dtvDetectToggled.connect(self._on_dtv_detect_toggled)
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
        
        # ShowLink Panel
        self.showlink_panel.monitorToggled.connect(self._on_showlink_monitor_toggled)
        self.showlink_panel.thresholdChanged.connect(self._on_showlink_threshold_spin_changed)
        self.showlink_panel.showThresholdToggled.connect(self._on_showlink_show_threshold_toggled)
        self.spectrum_view.showlinkThresholdChanged.connect(self._on_showlink_threshold_dragged)
        self.showlink_panel.tuneSweepClicked.connect(self.tune_to_showlink_band)
        self.showlink_panel.openMapClicked.connect(self.open_showlink_map_dialog)
        self.showlink_panel.clearClicked.connect(self._clear_showlink_data)
        
        # Threats Panel
        self.threats_panel.intruderAlertToggled.connect(self._on_intruder_alert_toggled)
        self.threats_panel.intruderThresholdChanged.connect(self._on_intruder_threshold_changed)
        self.threats_panel.showThresholdToggled.connect(self._on_intruder_show_threshold_toggled)
        self.threats_panel.intruder_table.cellClicked.connect(self._on_intruder_row_clicked)
        self.threats_panel.clearIntrudersClicked.connect(self._clear_intruders)
        self.threats_panel.addIntruderToMarkersClicked.connect(self._add_intruders_to_markers)
        self.threats_panel.loadSoundbaseClicked.connect(self.load_soundbase_json)
        self.threats_panel.markerItemChanged.connect(self._on_marker_tree_item_changed)
        self.threats_panel.carrierSelected.connect(self._on_soundbase_carrier_selected)

        # MSCAN Panel & View
        self.multi_device_manager.mscan_data_ready.connect(self._on_mscan_data)
        self.mscan_panel.scanToggled.connect(self._on_mscan_toggled)
        self.mscan_panel.paramsChanged.connect(self._on_mscan_params_changed)
        self.mscan_panel.loadSoundbaseClicked.connect(self.load_soundbase_json)
        self.mscan_panel.channelsSelectionChanged.connect(self._on_mscan_channels_selected)
        self.mscan_panel.tuneAudioDemodRequested.connect(self.tune_audio_demod_carrier)
        self.mscan_panel.inspectRtsaRequested.connect(self.inspect_rtsa_carrier)

        self.mscan_view.tuneDemodRequested.connect(self.tune_audio_demod_carrier)
        self.mscan_view.inspectRtsaRequested.connect(self.inspect_rtsa_carrier)

    def _init_state(self):
        # Active regional presets & channels
        self.top_bar.set_interface_badge(self.connection_interface, self.network_ip)
        self._update_region_ui()
        self.apply_frequencies()
        self.apply_view_frequencies()
        self.apply_amplitude_settings()
        self.apply_bw_settings()
        self.apply_sweep_settings()
        # Auto-connect on startup to immediately begin streaming live RF spectrum
        QTimer.singleShot(150, self.connect_analyzer)

    def _on_nav_collapse(self, collapsed: bool):
        self.panel_stack.setVisible(not collapsed)
        if collapsed:
            self.main_h_splitter.setSizes([48, self.width() - 48])
        else:
            self.main_h_splitter.setSizes([460, self.width() - 460])

    # --- Hardware & Multi-Device Sweep Loop ---
    def toggle_connection(self):
        if not self.is_connected:
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
                slot = self.multi_device_manager.slots.get(s_id)
                if slot:
                    slot.is_enabled = s_cfg["enabled"]
                    slot.role_alias = s_cfg.get("alias", "").strip()
                    slot.interface_type = s_cfg["interface"]
                    slot.ip_address = s_cfg["ip"]
                    slot.port = s_cfg["port"]
                    slot.usb_index = s_cfg["usb_index"]
                    slot.target_model = s_cfg.get("target_model")
                    slot.target_uid = s_cfg.get("target_uid")
                    
            if cfg.get("remember", True):
                self.settings.setValue("multi_device_topology", topo)
                
            self.top_bar.set_multi_device_state(topo, {
                s_id: {"alias": s.role_alias, "enabled": s.is_enabled}
                for s_id, s in self.multi_device_manager.slots.items()
            })
            
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
                info_str = f"{len(connected_slots)} Analyzers Online ({topo.upper()})"
            elif len(connected_slots) == 1:
                s = connected_slots[0]
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

    def _on_slot_status_changed(self, slot_id: str, is_connected: bool, msg: str):
        self._on_all_connection_status(self.is_connected)

    def _on_slot_info_received(self, slot_id: str, model: int, uid: object):
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
        self.sweep_panel.ref_level_spin.blockSignals(True)
        self.sweep_panel.ref_level_spin.setValue(ref_level)
        self.sweep_panel.ref_level_spin.blockSignals(False)
        if atten >= 0:
            self.sweep_panel.atten_spin.blockSignals(True)
            self.sweep_panel.atten_spin.setValue(atten)
            self.sweep_panel.atten_spin.blockSignals(False)
        self.top_bar.dev_label.setText(f"Ref Level adjusted to {ref_level:.1f} dBm by hardware")

    def _on_bandwidth_updated(self, slot_id: str, rbw_hz: float, vbw_hz: float):
        self.sweep_panel.update_hardware_bandwidth(rbw_hz, vbw_hz)

    def _on_hw_endorsements(self, slot_id: str, endorsements: dict):
        self.top_bar.set_hw_endorsements(endorsements)

    def _on_diversity_mode_changed(self, mode: str):
        self.multi_device_manager.set_diversity_view_mode(mode)

    def _on_focus_slot_changed(self, slot_id: str):
        self.multi_device_manager.set_focused_slot(slot_id)
        slot = self.multi_device_manager.slots.get(slot_id)
        if slot:
            self._updating_freqs = True
            self.sweep_panel.start_spin.setValue(slot.start_freq_hz / 1e6)
            self.sweep_panel.stop_spin.setValue(slot.stop_freq_hz / 1e6)
            self._updating_freqs = False

    def _on_diversity_sweep_data(self, freq, power_a, power_b, delta):
        if not self.is_sweeping or self.multi_device_manager.topology != MultiDeviceTopology.DIVERSITY:
            return
        x_scaled = freq / self._x_multiplier
        mode = self.multi_device_manager.diversity_view_mode
        if mode == "both":
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

    def _on_device_sweep_data(self, slot_id: str, x_data: np.ndarray, y_data: np.ndarray):
        if not self.is_sweeping or x_data is None or y_data is None or len(x_data) == 0:
            return
        offset = self.sweep_panel.amp_offset_spin.value()
        y_offset = y_data + offset
        
        # Module routing
        if slot_id == "slot_a" or self.multi_device_manager.topology != MultiDeviceTopology.INDEPENDENT:
            if self.threats_panel.intruder_enable_cb.isChecked():
                self._process_intruder_sweep(x_data, y_offset)
            if self.dtv_detect_active:
                self._process_dtv_detect(x_data, y_offset)
                
        if slot_id == "slot_b" or self.multi_device_manager.topology != MultiDeviceTopology.INDEPENDENT:
            if self.dect_panel.enable_cb.isChecked():
                self.dect_engine.process_sweep_data(x_data, y_offset)
            if self.showlink_panel.enable_cb.isChecked():
                self.showlink_engine.process_sweep_data(x_data, y_offset)

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
        x_scaled = x_data / self._x_multiplier
        self.last_freq = x_scaled
        self.last_power = y_offset
        
        # Real-Time Trace
        self.spectrum_view.update_curve_data("Real-Time", x_scaled, y_offset)
        if hasattr(self, 'demod_view') and self.viewport_stack.currentIndex() in (0, 4):
            self.demod_view.spectrum_view.update_curve_data("Real-Time", x_scaled, y_offset)
        
        # Max Hold (Only compute if active)
        if self.sweep_panel.trace_rows["Max. Hold"]["cb"].isChecked():
            if self.max_hold_data is None or len(self.max_hold_data) != len(y_offset):
                self.max_hold_data = np.copy(y_offset)
            else:
                if not self.sweep_panel.trace_rows["Max. Hold"]["freeze"].isChecked():
                    self.max_hold_data = np.maximum(self.max_hold_data, y_offset)
            self.spectrum_view.update_curve_data("Max. Hold", x_scaled, self.max_hold_data)
        
        # Min Hold (Only compute if active)
        if self.sweep_panel.trace_rows["Min. Hold"]["cb"].isChecked():
            if self.min_hold_data is None or len(self.min_hold_data) != len(y_offset):
                self.min_hold_data = np.copy(y_offset)
            else:
                if not self.sweep_panel.trace_rows["Min. Hold"]["freeze"].isChecked():
                    self.min_hold_data = np.minimum(self.min_hold_data, y_offset)
            self.spectrum_view.update_curve_data("Min. Hold", x_scaled, self.min_hold_data)
        
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
            self.spectrum_view.update_curve_data("Average", x_scaled, avg_curve)
        
        # Waterfall Image Roll (Bottom-to-Top: newest sweep at y=0 bottom, scrolling upwards)
        num_pts = len(y_offset)
        if self.waterfall_buffer.shape[1] != num_pts:
            self.waterfall_buffer = np.full((self.waterfall_history_depth, num_pts), -130.0, dtype=np.float32)
            
        self.waterfall_buffer = np.roll(self.waterfall_buffer, 1, axis=0)
        self.waterfall_buffer[0, :] = y_offset
        
        # Render Waterfall at up to ~35 FPS (every frame is recorded in waterfall_buffer, but UI texture uploads are paced to prevent OpenGL/Qt paint queue choking)
        now = time.monotonic()
        if now - self._last_waterfall_render_time >= 0.028:
            self._last_waterfall_render_time = now
            start_mhz = min(float(x_scaled[0]), float(x_scaled[-1]))
            stop_mhz = max(float(x_scaled[0]), float(x_scaled[-1]))
            width_mhz = max(0.001, stop_mhz - start_mhz)
            
            if self.viewport_stack.currentIndex() == 1:
                self.multi_row_view.update_sweep_data(self.waterfall_buffer, start_mhz, stop_mhz)
            elif self.viewport_stack.currentIndex() == 4:
                self.demod_view.waterfall_view.update_image(
                    self.waterfall_buffer.T,
                    (start_mhz, 0, width_mhz, self.waterfall_history_depth)
                )
            else:
                self.waterfall_view.update_image(
                    self.waterfall_buffer.T,
                    (start_mhz, 0, width_mhz, self.waterfall_history_depth)
                )
        
        # Process Specialized Analyzers
        if self.threats_panel.intruder_enable_cb.isChecked():
            self._process_intruder_sweep(x_data, y_offset)
            
        if self.dect_panel.enable_cb.isChecked():
            self.dect_engine.process_sweep_data(x_data, y_offset)
            
        if self.showlink_panel.enable_cb.isChecked():
            self.showlink_engine.process_sweep_data(x_data, y_offset)
            
        if self.dtv_detect_active:
            self._process_dtv_detect(x_data, y_offset)

    def resume_rf_sweep(self):
        self._last_operating_mode = "SWP"
        if hasattr(self, 'det_panel'):
            self.det_panel.set_active_state(False)
        if hasattr(self, 'mscan_panel') and (self.mscan_panel.is_scanning or self.mscan_panel.scan_btn.isChecked()):
            self.mscan_panel.stop_scan()
        if not self.is_connected:
            if self.nav_rail.btn_group.checkedId() == 5:
                self.viewport_stack.setCurrentIndex(4)
            elif self.nav_rail.btn_group.checkedId() == 2:
                self.viewport_stack.setCurrentIndex(5)
            else:
                self._on_view_mode_changed(self.top_bar.view_mode_combo.currentText())
            return
            
        self.multi_device_manager.stop_mscan()
        self.multi_device_manager.set_operating_mode("SWP")
        self.apply_frequencies()
        self.apply_amplitude_settings()
        self.apply_bw_settings()
        self.apply_sweep_settings()
        self.apply_detect_settings()
        if self.nav_rail.btn_group.checkedId() == 5:
            self.viewport_stack.setCurrentIndex(4) # Keep DemodView active
        elif self.nav_rail.btn_group.checkedId() == 2:
            self.viewport_stack.setCurrentIndex(5) # Keep MSCANView active
        else:
            self._on_view_mode_changed(self.top_bar.view_mode_combo.currentText())
        self.is_sweeping = True
        self.top_bar.set_sweeping_state(True)
        self.multi_device_manager.start_sweeping_all()

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
            self.mscan_panel.stop_scan()

        self.panel_stack.setCurrentIndex(mode_idx)
        
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
            ps_dict = {ch: True for ch in range(14, 21)} if self.tband_detect_active else {}
            std = TV_CHANNEL_STANDARDS.get(self.current_region, [])
            self.rtsa_view.channel_bar.draw_channels(std, self._x_multiplier)
            self.rtsa_view.set_active_channels(self.active_channels, ps_dict)
            self.rtsa_view.update_channel_masks(self.active_channels, std, ps_dict, self.station_db_names)
            self._on_rtsa_params_changed(self.rtsa_panel.get_params())
        elif mode_idx == 4: # Zero-Span (DET)
            # View Zero-Span canvas without immediately interrupting or taking hold of RF hardware
            self.viewport_stack.setCurrentIndex(3)
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
                    self.waterfall_buffer.T,
                    (start_mhz, 0, width_mhz, self.waterfall_history_depth)
                )
            if not self.demod_panel.is_active:
                if self._last_operating_mode != "SWP" or not self.is_sweeping:
                    self.resume_rf_sweep()
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
        bw_mhz = (100.0 / dec) * 0.8
        self.demod_view.set_channel_params(params.get("center_freq_mhz", 500.0), bw_mhz)

    def _on_iqs_data(self, slot_id: str, iq_complex: np.ndarray, sample_rate: float, info: dict):
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
            self.rtsa_view.update_rta_data(freq_hz, trace, bitmap, info)

    def _on_det_data(self, slot_id: str, time_ns: np.ndarray, power: np.ndarray, info: dict):
        if self.viewport_stack.currentIndex() == 3:
            self.frame_count += 1
            self.total_frames += 1
            self.det_view.update_det_data(time_ns, power, info)

    def _on_mscan_data(self, slot_id: str, el_idx: int, freq_hz: float, peak_power: float, spec_data, info: dict):
        if self.viewport_stack.currentIndex() == 5:
            self.frame_count += 1
            self.total_frames += 1
            dropout_thresh = self.mscan_panel.dropout_spin.value()
            self.mscan_view.update_channel_data(el_idx, freq_hz, peak_power, spec_data, info, dropout_thresh)
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
        self.nav_rail.set_active_mode(3)
        self.rtsa_panel.cf_spin.setValue(freq_mhz)

    def _on_temperature_updated(self, slot_id: str, temp_c: float):
        self.top_bar.set_device_temperature(temp_c)

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

    def _on_det_params_changed(self, params: dict):
        if hasattr(self, 'multi_device_manager'):
            self.multi_device_manager.configure_det(
                center_freq_hz=params.get("center_freq_hz", 1925e6),
                decimate_factor=params.get("decimate_factor", 2),
                ref_level=params.get("ref_level", 0.0),
                trig_src=params.get("trigger_source", 2),
                trig_mode=params.get("trigger_mode", 0),
                trig_length=params.get("trigger_length", 16240)
            )

    def open_audio_demod_dialog(self):
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
        if not self.is_connected:
            return
        self._pre_audio_mode = self._last_operating_mode
        self._last_operating_mode = "IQS"
        self.multi_device_manager.set_operating_mode("IQS")
        self.multi_device_manager.configure_iqs(
            center_freq_hz=freq_hz,
            decimate_factor=64, # ~1.5625 MSPS clean baseband for audio extraction
            ref_level=0.0,
            trig_src=2,
            trig_length=16384,
            preamp=0x00,
            atten=0
        )
        self.top_bar.dev_label.setText(f"Audio Demod: {mode.upper()} @ {freq_hz/1e6:.3f} MHz")

    def _on_audio_listen_stopped(self):
        if not self.is_connected:
            return
        self.top_bar.dev_label.setText(f"Audio Demod Stopped")
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
            atten=0
        )
        if self.audio_demod_dialog:
            mode = self.audio_demod_dialog.mode_combo.currentData()
            self.top_bar.dev_label.setText(f"Audio Demod: {mode.upper()} @ {freq_hz/1e6:.3f} MHz")

    def _on_view_mode_changed(self, mode: str):
        if self.nav_rail.btn_group.checkedId() in (2, 3, 4, 5):
            # If in MSCAN(2), RTSA(3), DET(4), or Demodulation(5), selecting a view mode combo switches back to RF & Sweep
            self.nav_rail.set_active_mode(0)
            return
            
        if mode == "Dual View":
            self.viewport_stack.setCurrentIndex(0)
            self.waterfall_view.show()
            self.spectrum_view.show()
            self.view_v_splitter.setSizes([340, 360])
        elif mode == "Multi-Row Waterfall":
            self.viewport_stack.setCurrentIndex(1)
            if hasattr(self, 'waterfall_buffer') and self.waterfall_buffer is not None:
                start_mhz = self.sweep_panel.start_spin.value()
                stop_mhz = self.sweep_panel.stop_spin.value()
                self.multi_row_view.update_sweep_data(self.waterfall_buffer, start_mhz, stop_mhz)
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
            self.multi_row_view.update_sweep_data(self.waterfall_buffer, start_mhz, stop_mhz)

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

    def apply_view_frequencies(self):
        v_start = self.sweep_panel.view_start_spin.value()
        v_stop = self.sweep_panel.view_stop_spin.value()
        self.spectrum_view.set_view_range(v_start, v_stop)
        if hasattr(self, 'demod_view'):
            self.demod_view.spectrum_view.set_view_range(v_start, v_stop)
        self._check_span_correlation()

    def _on_link_view_toggled(self, linked: bool):
        if linked:
            self.sweep_panel.view_start_spin.setValue(self.sweep_panel.start_spin.value())
            self.sweep_panel.view_stop_spin.setValue(self.sweep_panel.stop_spin.value())
            self.apply_view_frequencies()

    # --- Amplitude, BW & Sweep Configuration ---
    def apply_amplitude_settings(self):
        if not self.is_connected: return
        ref = self.sweep_panel.ref_level_spin.value()
        atten = self.sweep_panel.attenuation
        preamp = self.sweep_panel.preamp_combo.currentData()
        if preamp is None:
            preamp = 0
        offset = self.sweep_panel.amp_offset_spin.value()
        ifagc = 1 if self.sweep_panel.ifagc_check.isChecked() else 0
        target = self.sweep_panel.ifagc_target_spin.value()
        period = self.sweep_panel.ifagc_period_spin.value()
        if_out = 1 if self.sweep_panel.if_out_check.isChecked() else 0
        
        target_slot = self.multi_device_manager.focused_slot_id if self.multi_device_manager.topology == MultiDeviceTopology.INDEPENDENT else None
        self.multi_device_manager.set_amplitude_params(ref, atten, preamp, ifagc, target, period, if_out, target_slot_id=target_slot)

    def auto_reference_level(self):
        if self.max_hold_data is not None and len(self.max_hold_data) > 0:
            peak = float(np.max(self.max_hold_data))
            new_ref = math.ceil((peak + 10.0) / 5.0) * 5.0
            self.sweep_panel.ref_level_spin.setValue(new_ref)
            self.apply_amplitude_settings()

    def apply_bw_settings(self):
        if not self.is_connected: return
        rbw_mode = self.sweep_panel.rbw_mode
        rbw_hz = self.sweep_panel.rbw_hz
        vbw_mode = self.sweep_panel.vbw_mode
        vbw_hz = self.sweep_panel.vbw_hz
        target_slot = self.multi_device_manager.focused_slot_id if self.multi_device_manager.topology == MultiDeviceTopology.INDEPENDENT else None
        self.multi_device_manager.set_bandwidth_params(rbw_mode, rbw_hz, vbw_mode, vbw_hz, target_slot_id=target_slot)

    def apply_sweep_settings(self):
        if not self.is_connected: return
        swt_mode = self.sweep_panel.swt_mode_combo.currentIndex()
        swt_val = self.sweep_panel.sweep_time_spin.value()
        spur = self.sweep_panel.spur_combo.currentIndex()
        window = self.sweep_panel.window_combo.currentIndex()
        target_slot = self.multi_device_manager.focused_slot_id if self.multi_device_manager.topology == MultiDeviceTopology.INDEPENDENT else None
        self.multi_device_manager.set_sweep_params(swt_mode, swt_val, spur, window, target_slot_id=target_slot)

    def apply_detect_settings(self):
        if not self.is_connected: return
        det = self.sweep_panel.detector_combo.currentIndex()
        tdet = self.sweep_panel.trace_detector_combo.currentIndex()
        target_slot = self.multi_device_manager.focused_slot_id if self.multi_device_manager.topology == MultiDeviceTopology.INDEPENDENT else None
        self.multi_device_manager.set_detect_params(det, tdet, target_slot_id=target_slot)

    # --- Traces ---
    def _on_top_trace_toggled(self, name: str, active: bool):
        self.spectrum_view.set_trace_visible(name, active)
        if name in self.sweep_panel.trace_rows:
            self.sweep_panel.trace_rows[name]["cb"].blockSignals(True)
            self.sweep_panel.trace_rows[name]["cb"].setChecked(active)
            self.sweep_panel.trace_rows[name]["cb"].blockSignals(False)

    def _on_panel_trace_toggled(self, name: str, active: bool):
        self.spectrum_view.set_trace_visible(name, active)
        self.top_bar.set_trace_active(name, active)

    def _on_trace_freeze_toggled(self, name: str, frozen: bool):
        pass # state is read dynamically in sweep data handler

    def _on_trace_color_changed(self, name: str, color: QColor):
        self.spectrum_view.set_trace_color(name, color)

    def _on_avg_sweeps_changed(self, sweeps: int):
        self.avg_history = []

    # --- Region & Presets ---
    def change_region(self, region_name: str):
        if region_name in self.region_configs:
            self.current_region = region_name
            self.settings.setValue("current_region", region_name)
            self._update_region_ui()

    def _update_region_ui(self):
        presets = self.region_configs.get(self.current_region, [])
        self.sweep_panel.update_quick_settings_labels(presets)
        
        # Redraw Channel Markers
        standard = TV_CHANNEL_STANDARDS.get(self.current_region, [])
        self.spectrum_view.channel_bar.draw_channels(standard, self._x_multiplier)
        self.waterfall_view.channel_bar.draw_channels(standard, self._x_multiplier)
        
        if self.current_region == "North America":
            self.active_channels = dict(DEFAULT_NORTH_AMERICA_ACTIVE)
        else:
            self.active_channels = dict(DEFAULT_EUROPE_ACTIVE)
        ps_dict = {ch: True for ch in range(14, 21)} if self.tband_detect_active else {}
        self.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_view.update_channel_masks(self.active_channels, standard, ps_dict, self.station_db_names)
        self.waterfall_view.update_channel_masks(self.active_channels, standard, ps_dict)
        if hasattr(self, 'multi_row_view'):
            self.multi_row_view.set_channels(standard, self._x_multiplier, self.active_channels)
            self.multi_row_view.update_channel_masks(self.active_channels, standard, ps_dict)
        if hasattr(self, 'rtsa_view'):
            self.rtsa_view.channel_bar.draw_channels(standard, self._x_multiplier)
            self.rtsa_view.set_active_channels(self.active_channels, ps_dict)
            self.rtsa_view.update_channel_masks(self.active_channels, standard, ps_dict, self.station_db_names)
        if hasattr(self, 'demod_view'):
            self.demod_view.spectrum_view.channel_bar.draw_channels(standard, self._x_multiplier)
            self.demod_view.waterfall_view.channel_bar.draw_channels(standard, self._x_multiplier)
            self.demod_view.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
            self.demod_view.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)

    def _on_quick_setting_toggled(self, idx: int, checked: bool):
        presets = self.region_configs.get(self.current_region, [])
        if 0 <= idx < len(presets):
            p = presets[idx]
            self.sweep_panel.start_spin.setValue(float(p["start"]))
            self.sweep_panel.stop_spin.setValue(float(p["stop"]))
            self.apply_frequencies()

    def open_quick_settings_editor(self):
        presets = self.region_configs.get(self.current_region, [])
        dlg = QuickSettingsDialog(self.current_region, presets, self)
        if dlg.exec():
            self.region_configs[self.current_region] = dlg.buttons_data
            self.settings.setValue("regions", json.dumps(self.region_configs))
            self._update_region_ui()

    def open_launch_settings(self):
        dlg = LaunchSettingsDialog(
            self.region_configs, self.current_region,
            self.sweep_panel.start_spin.value(), self.sweep_panel.stop_spin.value(),
            link_view=self.sweep_panel.link_view_check.isChecked(), parent=self
        )
        if dlg.exec():
            res = dlg.get_settings()
            self.settings.setValue("launch_default_region", res["default_region"])
            self.settings.setValue("launch_sweep_start", res["sweep_start"])
            self.settings.setValue("launch_sweep_stop", res["sweep_stop"])
            self.settings.setValue("launch_link_view", res["link_view"])

    # --- DTV & Broadcast Coordination ---
    def _on_fcc_lookup(self, zip_code: str):
        if self.current_region == "North America":
            stations = self.fcc_db.query_by_zip(zip_code, radius_miles=65)
        elif self.current_region == "UK":
            stations = self.ofcom_db.query_by_postcode(zip_code, radius_km=80)
        else:
            stations = []
            
        self.station_db_names.clear()
        for s in stations:
            ch = s.get("channel")
            call = s.get("call_sign") or s.get("site_name")
            if ch and call and ch not in self.station_db_names:
                self.station_db_names[ch] = call
                self.station_db_names[str(ch)] = call
        self.spectrum_view.update_channel_names(self.station_db_names)
        if hasattr(self, 'rtsa_view'):
            self.rtsa_view.update_channel_names(self.station_db_names)
        
        self.dtv_panel.stations_table.setRowCount(len(stations))
        self._dtv_table_mode = 'fcc'
        for r_idx, s in enumerate(stations):
            ch_item = QTableWidgetItem(str(s.get("channel", "--")))
            call_item = QTableWidgetItem(s.get("call_sign", s.get("site_name", "UNKNOWN")))
            erp_val = s.get('erp', 0.0)
            try:
                erp_str = f"{float(erp_val):.1f}"
            except (ValueError, TypeError):
                erp_str = str(erp_val)
            erp_item = QTableWidgetItem(erp_str)
            dist_item = QTableWidgetItem(f"{s.get('distance_miles', s.get('distance_km', 0.0)):.1f}")
            live_item = QTableWidgetItem("--")
            
            for item in (ch_item, call_item, erp_item, dist_item, live_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
            self.dtv_panel.stations_table.setItem(r_idx, 0, ch_item)
            self.dtv_panel.stations_table.setItem(r_idx, 1, call_item)
            self.dtv_panel.stations_table.setItem(r_idx, 2, erp_item)
            self.dtv_panel.stations_table.setItem(r_idx, 3, dist_item)
            self.dtv_panel.stations_table.setItem(r_idx, 4, live_item)

    def _on_dtv_table_clicked(self, row: int, col: int):
        ch_text = self.dtv_panel.stations_table.item(row, 0).text()
        try:
            ch_num = int(ch_text)
            # Find frequency for channel
            for band in TV_CHANNEL_STANDARDS.get(self.current_region, []):
                if "start_ch" in band and band["start_ch"] <= ch_num <= band["end_ch"]:
                    f_start = band["start_freq"] + (ch_num - band["start_ch"]) * band["spacing"]
                    f_stop = f_start + band["spacing"]
                    self.sweep_panel.view_start_spin.setValue(f_start - 2.0)
                    self.sweep_panel.view_stop_spin.setValue(f_stop + 2.0)
                    self.apply_view_frequencies()
                    break
        except ValueError:
            pass

    def _on_dtv_detect_toggled(self, active: bool):
        self.dtv_detect_active = active
        if active:
            self.dtv_panel.show_thresh_cb.blockSignals(True)
            self.dtv_panel.show_thresh_cb.setChecked(True)
            self.dtv_panel.show_thresh_cb.blockSignals(False)
            self.spectrum_view.threshold_line.setVisible(True)
            self.spectrum_view.threshold_line.setPos(self.dtv_panel.threshold_spin.value())
            self.dtv_panel.detect_status_lbl.setText("Auto DTV: Scanning spectrum...")
            self.dtv_panel.detect_status_lbl.setStyleSheet("color: #eab308; font-size: 11px; font-weight: 600; padding: 2px 0;")
        else:
            self.dtv_panel.update_detect_status(0, 0, self.dtv_panel.threshold_spin.value(), False)

    def _on_tband_scan_toggled(self, active: bool):
        self.tband_detect_active = active
        ps_dict = {ch: True for ch in range(14, 21)} if active else {}
        std = TV_CHANNEL_STANDARDS.get(self.current_region, [])
        self.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_view.update_channel_masks(self.active_channels, std, ps_dict, self.station_db_names)
        self.waterfall_view.update_channel_masks(self.active_channels, std, ps_dict)
        if hasattr(self, 'multi_row_view'):
            self.multi_row_view.set_active_channels(self.active_channels, ps_dict)
            self.multi_row_view.update_channel_masks(self.active_channels, std, ps_dict)
        if hasattr(self, 'rtsa_view'):
            self.rtsa_view.set_active_channels(self.active_channels, ps_dict)
            self.rtsa_view.update_channel_masks(self.active_channels, std, ps_dict, self.station_db_names)

    def _process_dtv_detect(self, x_data, y_data):
        thresh = self.dtv_panel.threshold_spin.value()
        x_mhz = x_data / 1e6 # Convert from Hz to MHz to match TV standards
        
        stds = TV_CHANNEL_STANDARDS.get(self.current_region, [])
        active_count = 0
        total_count = 0
        channel_data = []
        
        for band in stds:
            if "start_ch" in band:
                for ch in range(band["start_ch"], band["end_ch"] + 1):
                    f_start = band["start_freq"] + (ch - band["start_ch"]) * band["spacing"]
                    f_stop = f_start + band["spacing"]
                    mask = (x_mhz >= f_start) & (x_mhz <= f_stop)
                    if np.any(mask):
                        ch_pwr = float(np.mean(y_data[mask]))
                        ch_peak = float(np.max(y_data[mask]))
                        is_occupied = bool((ch_pwr >= thresh) or (ch_peak >= thresh + 4.0))
                        self.active_channels[ch] = is_occupied
                        total_count += 1
                        if is_occupied:
                            active_count += 1
                        channel_data.append((ch, f_start, f_stop, ch_pwr, is_occupied))
            elif "custom_items" in band:
                for c_item in band["custom_items"]:
                    c_id = c_item["id"]
                    f_start = c_item["start"]
                    f_stop = c_item["stop"]
                    mask = (x_mhz >= f_start) & (x_mhz <= f_stop)
                    if np.any(mask):
                        ch_pwr = float(np.mean(y_data[mask]))
                        ch_peak = float(np.max(y_data[mask]))
                        is_occupied = bool((ch_pwr >= thresh) or (ch_peak >= thresh + 4.0))
                        self.active_channels[c_id] = is_occupied
                        total_count += 1
                        if is_occupied:
                            active_count += 1

        ps_dict = {ch: True for ch in range(14, 21)} if self.tband_detect_active else {}
        self.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_view.update_channel_masks(self.active_channels, stds, ps_dict, self.station_db_names)
        self.waterfall_view.update_channel_masks(self.active_channels, stds, ps_dict)
        if hasattr(self, 'multi_row_view'):
            self.multi_row_view.set_active_channels(self.active_channels, ps_dict)
            self.multi_row_view.update_channel_masks(self.active_channels, stds, ps_dict)
        if hasattr(self, 'rtsa_view'):
            self.rtsa_view.set_active_channels(self.active_channels, ps_dict)
            self.rtsa_view.update_channel_masks(self.active_channels, stds, ps_dict, self.station_db_names)
            
        self.dtv_panel.update_detect_status(active_count, total_count, thresh, True)
        
        if channel_data:
            self._update_dtv_table_live_rf(channel_data)

    def _update_dtv_table_live_rf(self, channel_data):
        if self.frame_count % 15 != 0:
            return
            
        table = self.dtv_panel.stations_table
        if table.rowCount() == 0 or getattr(self, '_dtv_table_mode', None) == 'scanned':
            self._dtv_table_mode = 'scanned'
            if table.rowCount() != len(channel_data):
                table.setRowCount(len(channel_data))
            for r_idx, (ch, f1, f2, pwr, is_occ) in enumerate(channel_data):
                ch_item = QTableWidgetItem(str(ch))
                name_item = QTableWidgetItem(f"DTV Ch {ch}")
                range_item = QTableWidgetItem(f"{f1:g} - {f2:g} MHz")
                dist_item = QTableWidgetItem("--")
                status_str = f"{pwr:.1f} dBm  [OCCUPIED]" if is_occ else f"{pwr:.1f} dBm  [CLEAR]"
                rf_item = QTableWidgetItem(status_str)
                if is_occ:
                    rf_item.setForeground(QColor("#f87171"))
                else:
                    rf_item.setForeground(QColor("#4ade80"))
                for it in (ch_item, name_item, range_item, dist_item, rf_item):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r_idx, 0, ch_item)
                table.setItem(r_idx, 1, name_item)
                table.setItem(r_idx, 2, range_item)
                table.setItem(r_idx, 3, dist_item)
                table.setItem(r_idx, 4, rf_item)
        else:
            pwr_map = {ch: (pwr, is_occ) for ch, f1, f2, pwr, is_occ in channel_data}
            for r in range(table.rowCount()):
                ch_item = table.item(r, 0)
                if ch_item:
                    try:
                        c_num = int(ch_item.text())
                        if c_num in pwr_map:
                            pwr, is_occ = pwr_map[c_num]
                            status_str = f"{pwr:.1f} dBm  [OCCUPIED]" if is_occ else f"{pwr:.1f} dBm  [CLEAR]"
                            rf_item = table.item(r, 4)
                            if not rf_item:
                                rf_item = QTableWidgetItem()
                                rf_item.setFlags(rf_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                                table.setItem(r, 4, rf_item)
                            rf_item.setText(status_str)
                            if is_occ:
                                rf_item.setForeground(QColor("#f87171"))
                            else:
                                rf_item.setForeground(QColor("#4ade80"))
                    except ValueError:
                        pass

    def _on_channel_bar_clicked(self, ch_num, start_freq, stop_freq):
        # Toggle channel active mask
        self.active_channels[ch_num] = not self.active_channels.get(ch_num, False)
        ps_dict = {ch: True for ch in range(14, 21)} if self.tband_detect_active else {}
        std = TV_CHANNEL_STANDARDS.get(self.current_region, [])
        self.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
        self.spectrum_view.update_channel_masks(self.active_channels, std, ps_dict, self.station_db_names)
        self.waterfall_view.update_channel_masks(self.active_channels, std, ps_dict)
        if hasattr(self, 'multi_row_view'):
            self.multi_row_view.set_active_channels(self.active_channels, ps_dict)
            self.multi_row_view.update_channel_masks(self.active_channels, std, ps_dict)
        if hasattr(self, 'rtsa_view'):
            self.rtsa_view.set_active_channels(self.active_channels, ps_dict)
            self.rtsa_view.update_channel_masks(self.active_channels, std, ps_dict, self.station_db_names)
        if hasattr(self, 'demod_view'):
            self.demod_view.spectrum_view.channel_bar.set_active_channels(self.active_channels, ps_dict)
            self.demod_view.waterfall_view.channel_bar.set_active_channels(self.active_channels, ps_dict)

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
        for r_idx, (ch_idx, c_data) in enumerate(carriers.items()):
            ch_item = QTableWidgetItem(f"{ch_idx}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            rssi_item = QTableWidgetItem(f"{c_data.get('peak_dbm', -120.0):.0f} dBm")
            rssi_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            load_item = QTableWidgetItem(f"{c_data.get('duty_cycle_pct', 0.0):.0f}%")
            load_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            bp = c_data.get('beltpacks_est', 0)
            st = c_data.get('status', 'IDLE')
            if st == 'IDLE' or bp == 0:
                status_item = QTableWidgetItem(st)
            else:
                status_item = QTableWidgetItem(f"{st} ({bp} BP)")
            
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
        self.showlink_engine.channel_stats.clear()
        self.showlink_panel.showlink_table.setRowCount(0)

    def _on_showlink_analysis_updated(self, stats: dict):
        ch_stats = stats.get("channels", {})
        self.showlink_panel.showlink_table.setRowCount(len(ch_stats))
        for r_idx, (ch_num, s_data) in enumerate(ch_stats.items()):
            ch_item = QTableWidgetItem(f"{ch_num}")
            ch_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            freq_item = QTableWidgetItem(f"{s_data.get('freq_mhz', 0.0):.0f}")
            freq_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            rssi_item = QTableWidgetItem(f"{s_data.get('peak_dbm', -120.0):.0f} dBm")
            rssi_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            raw_status = str(s_data.get("status", "CLEAN"))
            if "EXCELLENT" in raw_status:
                state_text = "EXCELLENT"
                state_color = QColor("#4ade80")
            elif "CLEAR" in raw_status:
                state_text = "CLEAR"
                state_color = QColor("#4ade80")
            elif "MODERATE" in raw_status:
                state_text = "MODERATE"
                state_color = QColor("#f59e0b")
            elif "ACTIVE" in raw_status:
                state_text = "ACTIVE"
                state_color = QColor("#fb923c")
            elif "CONGESTED" in raw_status:
                state_text = "CONGESTED"
                state_color = QColor("#f87171")
            else:
                clean = raw_status.replace("🔴", "").replace("🟡", "").replace("🟢", "").strip()
                state_text = clean.split()[0] if clean else "CLEAN"
                state_color = QColor(s_data.get("color", "#c9d1d9"))

            health_item = QTableWidgetItem(state_text)
            health_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            health_item.setForeground(state_color)
            font = health_item.font()
            font.setBold(True)
            health_item.setFont(font)
            
            # Rich detailed diagnostic tooltip
            overlap = s_data.get("overlap", "None")
            peak_dbm = s_data.get("peak_dbm", -120.0)
            avg_dbm = s_data.get("avg_dbm", -120.0)
            health_item.setToolTip(
                f"Channel {ch_num} ({freq_mhz:.1f} MHz)\n"
                f"Status: {state_text}\n"
                f"Wi-Fi Overlap: {overlap}\n"
                f"Peak Power: {peak_dbm:.1f} dBm\n"
                f"Average Power: {avg_dbm:.1f} dBm"
            )
            
            for it in (ch_item, freq_item, rssi_item, health_item):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
            self.showlink_panel.showlink_table.setItem(r_idx, 0, ch_item)
            self.showlink_panel.showlink_table.setItem(r_idx, 1, freq_item)
            self.showlink_panel.showlink_table.setItem(r_idx, 2, rssi_item)
            self.showlink_panel.showlink_table.setItem(r_idx, 3, health_item)

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
        
        # Find true local maxima above threshold using scipy find_peaks
        peak_indices, _ = signal.find_peaks(y_clean, height=thresh, prominence=1.0, distance=3)
        if len(peak_indices) == 0:
            return
            
        # Sort detected peaks descending by power and cluster within 150 kHz in the current frame
        peak_powers = y_clean[peak_indices]
        sorted_indices = peak_indices[np.argsort(-peak_powers)]
        
        filtered_peaks = []
        for idx in sorted_indices:
            f = float(x_mhz[idx])
            p = float(y_clean[idx])
            if any(abs(f - acc_f) < 0.15 for acc_f, _ in filtered_peaks):
                continue
            filtered_peaks.append((f, p))
            
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
                entry["last_seen"] = now
                if p > entry["power"]:
                    entry["power"] = p
                    if round(f, 3) != matched_key:
                        del self.intruders[matched_key]
                        matched_key = round(f, 3)
                        entry["freq"] = matched_key
                    self.intruders[matched_key] = entry
                    updated_any = True
            else:
                # Classify unknown transmitter signature
                sig_res = self.classifier.classify_peak(x_mhz, y_clean, f, p, self.current_region)
                self.intruders[round(f, 3)] = {
                    "freq": round(f, 3),
                    "power": p,
                    "signature": sig_res.get("device", "Unknown Carrier"),
                    "details": sig_res.get("details", ""),
                    "category": sig_res.get("category", "RF Carrier"),
                    "confidence": sig_res.get("confidence", 50),
                    "color": sig_res.get("color", "#d946ef"),
                    "first_seen": now,
                    "last_seen": now
                }
                updated_any = True
                
        # Rate-limit table GUI updates to ~10 FPS (100ms) or whenever a new threat is logged
        if updated_any or (now - self._last_intruder_ui_update >= 0.10):
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
        for r_idx, (f, info) in enumerate(sorted_intruders):
            f_item = NumericTableWidgetItem(f"{f:.3f}", f)
            f_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            p_item = NumericTableWidgetItem(f"{info['power']:.1f} dBm", info['power'])
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            sig_name = info.get("signature", "Unknown Carrier")
            s_item = QTableWidgetItem(sig_name)
            s_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            # Signature color badge & tooltip
            sig_color = info.get("color", "#d946ef")
            s_item.setForeground(QColor(sig_color))
            tooltip_txt = (
                f"Signature: {sig_name}\n"
                f"Category: {info.get('category', 'RF Carrier')}\n"
                f"Peak Power: {info['power']:.1f} dBm\n"
                f"Confidence: {info.get('confidence', 50)}%\n"
                f"Details: {info.get('details', 'N/A')}"
            )
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

    def _clear_intruders(self):
        self.intruders.clear()
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

    def _add_intruders_to_markers(self):
        for f, info in self.intruders.items():
            item = QTreeWidgetItem([f"Threat: {f:.3f} MHz", f"{info['power']:.1f} dBm"])
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setData(0, Qt.ItemDataRole.UserRole, float(f))
            self.threats_panel.markers_tree.addTopLevelItem(item)

    def _on_marker_tree_item_changed(self, item, col):
        if col != 0:
            return
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

    def load_soundbase_json(self, filepath: str = None):
        if filepath:
            fp = filepath
        else:
            default_dir = "/home/parallels/Documents/Harogic Projects/Soundbase Resources"
            if not os.path.exists(default_dir):
                default_dir = ""
            fp, _ = QFileDialog.getOpenFileName(
                self, "Load Soundbase Site Coordination", default_dir, "Soundbase Files (*.sbcoordsite *.json);;All Files (*.*)"
            )
        if fp:
            try:
                parsed = SoundbaseParser.parse_file(fp)
                carriers = parsed.get("all_carriers", [])
                self.spectrum_view.set_soundbase_masks(carriers)
                self.threats_panel.populate_soundbase_tree(parsed)
                site_name = parsed["sites"][0]["name"] if parsed.get("sites") else Path(fp).stem
                self.threats_panel.set_soundbase_active(site_name, len(carriers))
                if hasattr(self, 'mscan_panel'):
                    self.mscan_panel.set_soundbase_data(parsed)
                if hasattr(self, 'mscan_view'):
                    self.mscan_view.set_channels(carriers)
            except Exception as e:
                QMessageBox.warning(self, "Import Notice", f"Failed to parse Soundbase file: {e}")

    # --- Calibration Management ---
    def open_calibration_manager(self, model=None, uid=None):
        target_m = model or self.current_model or self.target_device_model
        target_u = uid or self.current_uid or self.target_device_uid
        dlg = CalibrationManagerDialog(selected_model=target_m, selected_uid=target_u, parent=self)
        if dlg.exec():
            if not self.is_connected:
                self.connect_analyzer()

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
