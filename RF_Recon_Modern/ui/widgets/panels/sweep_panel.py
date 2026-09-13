"""
sweep_panel.py - RF Sweep, Gain, Bandwidth & Trace Settings Panel.
Provides complete control over hardware sweep parameters, independent/linked view range,
quick preset band chips, amplitude/attenuation, RBW/VBW, and trace parameters.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox, QGridLayout, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..freq_inputs import FreqSpinBox, BWSpinBox
from ..trace_controls import SimpleColorPicker
from core.constants import (
    SWT_MODES, SPUR_REJECTION_MODES, WINDOW_FUNCTIONS,
    DETECTOR_TYPES, TRACE_DETECTOR_TYPES, RBW_MODES, VBW_MODES, PREAMP_OPTIONS
)

class SweepPanel(QWidget):
    """
    Comprehensive panel for all RF hardware sweep, view span, amplitude, and trace configurations.
    """
    frequenciesChanged = pyqtSignal()
    viewFrequenciesChanged = pyqtSignal()
    quickSettingToggled = pyqtSignal(int, bool)
    editQuickSettingsClicked = pyqtSignal()
    amplitudeChanged = pyqtSignal()
    autoRefLevelClicked = pyqtSignal()
    sweepSettingsChanged = pyqtSignal()
    detectSettingsChanged = pyqtSignal()
    bwSettingsChanged = pyqtSignal()
    traceToggled = pyqtSignal(str, bool)
    traceFreezeToggled = pyqtSignal(str, bool)
    traceColorChanged = pyqtSignal(str, object)
    avgSweepsChanged = pyqtSignal(int)
    linkViewToggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating_freqs = False
        self._updating_view_freqs = False
        
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        scroll.setWidget(container)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        
        # --- 1. ANALYZER SWEEP CARD ---
        sweep_card = self._create_card("ANALYZER SWEEP RANGE", layout)
        sweep_form = QFormLayout()
        sweep_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        sweep_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.start_spin = FreqSpinBox()
        self.start_spin.setValue(470.0)
        self.start_spin.editingFinished.connect(self.frequenciesChanged.emit)
        
        self.stop_spin = FreqSpinBox()
        self.stop_spin.setValue(608.0)
        self.stop_spin.editingFinished.connect(self.frequenciesChanged.emit)
        
        self.center_spin = FreqSpinBox()
        self.center_spin.setValue(539.0)
        self.center_spin.editingFinished.connect(self.frequenciesChanged.emit)
        
        self.span_spin = FreqSpinBox()
        self.span_spin.setValue(138.0)
        self.span_spin.editingFinished.connect(self.frequenciesChanged.emit)
        
        self.step_spin = FreqSpinBox()
        self.step_spin.setValue(1.0)
        
        sweep_form.addRow("Start:", self.start_spin)
        sweep_form.addRow("Stop:", self.stop_spin)
        sweep_form.addRow("Center:", self.center_spin)
        sweep_form.addRow("Span:", self.span_spin)
        sweep_form.addRow("CF Step:", self.step_spin)
        sweep_card.layout().addLayout(sweep_form)
        
        # Quick Presets Header
        qs_header = QHBoxLayout()
        qs_lbl = QLabel("QUICK BAND PRESETS")
        qs_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e;")
        qs_header.addWidget(qs_lbl)
        qs_header.addStretch()
        
        self.edit_qs_btn = QPushButton("Edit")
        self.edit_qs_btn.setObjectName("pillBtn")
        self.edit_qs_btn.setFixedHeight(20)
        self.edit_qs_btn.clicked.connect(self.editQuickSettingsClicked.emit)
        qs_header.addWidget(self.edit_qs_btn)
        sweep_card.layout().addLayout(qs_header)
        
        # Quick Presets Grid (10 buttons)
        self.quick_btn_layout = QGridLayout()
        self.quick_btn_layout.setSpacing(4)
        self.quick_btns = []
        for i in range(10):
            btn = QPushButton(f"Preset {i+1}")
            btn.setObjectName("pillBtn")
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.clicked.connect(lambda chk, idx=i: self.quickSettingToggled.emit(idx, chk))
            self.quick_btns.append(btn)
            self.quick_btn_layout.addWidget(btn, i // 2, i % 2)
        sweep_card.layout().addLayout(self.quick_btn_layout)
        
        # --- 2. VIEW SWEEP CARD ---
        view_card = self._create_card("VIEWPORT SPAN (ZOOM)", layout)
        
        self.link_view_check = QCheckBox("Link View to Analyzer Sweep")
        self.link_view_check.setChecked(True)
        self.link_view_check.toggled.connect(self.linkViewToggled.emit)
        view_card.layout().addWidget(self.link_view_check)
        
        view_form = QFormLayout()
        view_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        view_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.view_start_spin = FreqSpinBox()
        self.view_start_spin.setValue(470.0)
        self.view_start_spin.editingFinished.connect(self.viewFrequenciesChanged.emit)
        
        self.view_stop_spin = FreqSpinBox()
        self.view_stop_spin.setValue(608.0)
        self.view_stop_spin.editingFinished.connect(self.viewFrequenciesChanged.emit)
        
        self.view_center_spin = FreqSpinBox()
        self.view_center_spin.setValue(539.0)
        self.view_center_spin.editingFinished.connect(self.viewFrequenciesChanged.emit)
        
        self.view_span_spin = FreqSpinBox()
        self.view_span_spin.setValue(138.0)
        self.view_span_spin.editingFinished.connect(self.viewFrequenciesChanged.emit)
        
        self.view_step_spin = FreqSpinBox()
        self.view_step_spin.setValue(1.0)
        
        view_form.addRow("View Start:", self.view_start_spin)
        view_form.addRow("View Stop:", self.view_stop_spin)
        view_form.addRow("View Center:", self.view_center_spin)
        view_form.addRow("View Span:", self.view_span_spin)
        view_form.addRow("View Step:", self.view_step_spin)
        view_card.layout().addLayout(view_form)
        
        # --- 3. AMPLITUDE & GAIN CARD ---
        amp_card = self._create_card("AMPLITUDE & GAIN", layout)
        amp_form = QFormLayout()
        amp_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        amp_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.ref_level_spin = QDoubleSpinBox()
        self.ref_level_spin.setRange(-200.0, 100.0)
        self.ref_level_spin.setValue(0.0)
        self.ref_level_spin.setSuffix(" dBm")
        self.ref_level_spin.setSingleStep(5.0)
        self.ref_level_spin.valueChanged.connect(self.amplitudeChanged.emit)
        
        self.auto_ref_btn = QPushButton("Auto Ref. Level")
        self.auto_ref_btn.clicked.connect(self.autoRefLevelClicked.emit)
        
        atten_container = QWidget()
        atten_layout = QHBoxLayout(atten_container)
        atten_layout.setContentsMargins(0, 0, 0, 0)
        atten_layout.setSpacing(6)
        
        self.atten_spin = QSpinBox()
        self.atten_spin.setRange(0, 30)
        self.atten_spin.setSingleStep(10)
        self.atten_spin.setValue(0)
        self.atten_spin.setSuffix(" dB")
        self.atten_spin.valueChanged.connect(self.amplitudeChanged.emit)
        
        self.auto_atten_check = QCheckBox("Auto")
        self.auto_atten_check.setChecked(False)
        self.auto_atten_check.toggled.connect(self._on_auto_atten_toggled)
        
        atten_layout.addWidget(self.atten_spin, 1)
        atten_layout.addWidget(self.auto_atten_check)
        
        self.preamp_combo = QComboBox()
        for label, val in PREAMP_OPTIONS:
            self.preamp_combo.addItem(label, val)
        self.preamp_combo.currentIndexChanged.connect(self.amplitudeChanged.emit)
        
        self.amp_offset_spin = QDoubleSpinBox()
        self.amp_offset_spin.setRange(-200.0, 200.0)
        self.amp_offset_spin.setValue(0.0)
        self.amp_offset_spin.setSuffix(" dB")
        self.amp_offset_spin.valueChanged.connect(self.amplitudeChanged.emit)
        
        self.ifagc_check = QCheckBox()
        self.ifagc_check.setChecked(True)
        self.ifagc_check.toggled.connect(self.amplitudeChanged.emit)
        
        self.ifagc_target_spin = QDoubleSpinBox()
        self.ifagc_target_spin.setRange(-200.0, 100.0)
        self.ifagc_target_spin.setValue(-9.0)
        self.ifagc_target_spin.setSuffix(" dB")
        self.ifagc_target_spin.valueChanged.connect(self.amplitudeChanged.emit)
        
        self.ifagc_period_spin = QDoubleSpinBox()
        self.ifagc_period_spin.setRange(0.001, 10.0)
        self.ifagc_period_spin.setDecimals(3)
        self.ifagc_period_spin.setValue(0.01)
        self.ifagc_period_spin.setSuffix(" s")
        self.ifagc_period_spin.valueChanged.connect(self.amplitudeChanged.emit)
        
        self.if_out_check = QCheckBox()
        self.if_out_check.setChecked(False)
        self.if_out_check.toggled.connect(self.amplitudeChanged.emit)
        
        amp_form.addRow("Ref. Level:", self.ref_level_spin)
        amp_form.addRow("", self.auto_ref_btn)
        amp_form.addRow("Attenuation:", atten_container)
        amp_form.addRow("Pre-Amplifier:", self.preamp_combo)
        amp_form.addRow("Amp. Offset:", self.amp_offset_spin)
        amp_form.addRow("Enable IFAGC:", self.ifagc_check)
        amp_form.addRow("IFAGC Target:", self.ifagc_target_spin)
        amp_form.addRow("IFAGC Period:", self.ifagc_period_spin)
        amp_form.addRow("Enable IF Out:", self.if_out_check)
        amp_card.layout().addLayout(amp_form)
        
        # --- 4. BANDWIDTH (RBW / VBW) CARD ---
        bw_card = self._create_card("BANDWIDTH RESOLUTION", layout)
        bw_form = QFormLayout()
        bw_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        bw_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.rbw_presets = [
            ("Auto", 1, 0.0),
            ("1 kHz", 0, 1e3),
            ("3 kHz", 0, 3e3),
            ("10 kHz", 0, 10e3),
            ("30 kHz", 0, 30e3),
            ("50 kHz", 0, 50e3),
            ("100 kHz", 0, 100e3),
            ("300 kHz", 0, 300e3),
            ("1 MHz", 0, 1e6),
            ("3 MHz", 0, 3e6),
            ("0.001*Span", 2, 0.0),
            ("0.01*Span", 3, 0.0),
            ("Manual", 0, -1.0)
        ]
        self.rbw_mode_combo = QComboBox()
        for label, _, _ in self.rbw_presets:
            self.rbw_mode_combo.addItem(label)
        self.rbw_mode_combo.setCurrentIndex(0) # Auto
        self.rbw_mode_combo.currentIndexChanged.connect(self._on_rbw_mode_changed)
        
        self.rbw_spin = BWSpinBox()
        self.rbw_spin.setValue(0.030) # 30 kHz
        self.rbw_spin.setEnabled(True) # Always interactive
        self.rbw_spin.valueChanged.connect(self._on_rbw_spin_changed)
        self.rbw_spin.editingFinished.connect(self._on_rbw_editing_finished)
        
        self.vbw_presets = [
            ("Auto (VBW=RBW)", 1, 0.0),
            ("0.1 * RBW", 2, 0.0),
            ("0.01 * RBW", 3, 0.0),
            ("10 * RBW", 4, 0.0),
            ("1 kHz", 0, 1e3),
            ("3 kHz", 0, 3e3),
            ("10 kHz", 0, 10e3),
            ("30 kHz", 0, 30e3),
            ("50 kHz", 0, 50e3),
            ("100 kHz", 0, 100e3),
            ("300 kHz", 0, 300e3),
            ("1 MHz", 0, 1e6),
            ("3 MHz", 0, 3e6),
            ("Manual", 0, -1.0)
        ]
        self.vbw_mode_combo = QComboBox()
        for label, _, _ in self.vbw_presets:
            self.vbw_mode_combo.addItem(label)
        self.vbw_mode_combo.setCurrentIndex(0) # Auto (VBW=RBW)
        self.vbw_mode_combo.currentIndexChanged.connect(self._on_vbw_mode_changed)
        
        self.vbw_spin = BWSpinBox()
        self.vbw_spin.setValue(0.030)
        self.vbw_spin.setEnabled(True) # Always interactive
        self.vbw_spin.valueChanged.connect(self._on_vbw_spin_changed)
        self.vbw_spin.editingFinished.connect(self._on_vbw_editing_finished)
        
        bw_form.addRow("RBW Mode:", self.rbw_mode_combo)
        bw_form.addRow("RBW Value:", self.rbw_spin)
        bw_form.addRow("VBW Mode:", self.vbw_mode_combo)
        bw_form.addRow("VBW Value:", self.vbw_spin)
        bw_card.layout().addLayout(bw_form)
        
        # --- 5. ADVANCED SWEEP & DETECTOR CARD ---
        adv_card = self._create_card("SWEEP & DETECTOR SETTINGS", layout)
        adv_form = QFormLayout()
        adv_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        adv_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.swt_mode_combo = QComboBox()
        self.swt_mode_combo.addItems(SWT_MODES)
        self.swt_mode_combo.currentIndexChanged.connect(self.sweepSettingsChanged.emit)
        
        self.sweep_time_spin = QDoubleSpinBox()
        self.sweep_time_spin.setRange(0.001, 1000.0)
        self.sweep_time_spin.setDecimals(3)
        self.sweep_time_spin.setSuffix(" s")
        self.sweep_time_spin.setEnabled(False)
        self.sweep_time_spin.valueChanged.connect(self.sweepSettingsChanged.emit)
        
        self.trace_points_spin = QSpinBox()
        self.trace_points_spin.setRange(0, 100000)
        self.trace_points_spin.setReadOnly(True)
        
        self.spur_combo = QComboBox()
        self.spur_combo.addItems(SPUR_REJECTION_MODES)
        self.spur_combo.setCurrentIndex(1) # Standard
        self.spur_combo.currentIndexChanged.connect(self.sweepSettingsChanged.emit)
        
        self.window_combo = QComboBox()
        self.window_combo.addItems(WINDOW_FUNCTIONS)
        self.window_combo.setCurrentIndex(0) # FlatTop
        self.window_combo.currentIndexChanged.connect(self.sweepSettingsChanged.emit)
        
        self.detector_combo = QComboBox()
        self.detector_combo.addItems(DETECTOR_TYPES)
        self.detector_combo.setCurrentIndex(4) # MaxPower
        self.detector_combo.currentIndexChanged.connect(self.detectSettingsChanged.emit)
        
        self.trace_detector_combo = QComboBox()
        self.trace_detector_combo.addItems(TRACE_DETECTOR_TYPES)
        self.trace_detector_combo.setCurrentIndex(0) # AutoSample
        self.trace_detector_combo.currentIndexChanged.connect(self.detectSettingsChanged.emit)
        
        adv_form.addRow("SWT Mode:", self.swt_mode_combo)
        adv_form.addRow("Sweep Time:", self.sweep_time_spin)
        adv_form.addRow("Trace Points:", self.trace_points_spin)
        adv_form.addRow("Spur Rejection:", self.spur_combo)
        adv_form.addRow("Window:", self.window_combo)
        adv_form.addRow("Detector:", self.detector_combo)
        adv_form.addRow("Trace Detector:", self.trace_detector_combo)
        adv_card.layout().addLayout(adv_form)
        
        # --- 6. TRACE CONTROLS DETAIL CARD ---
        trace_card = self._create_card("TRACE MANAGER", layout)
        trace_grid = QGridLayout()
        trace_grid.setSpacing(6)
        
        # Headers
        trace_grid.addWidget(QLabel("Trace"), 0, 0)
        trace_grid.addWidget(QLabel("Freeze"), 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        trace_grid.addWidget(QLabel("Color"), 0, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.trace_rows = {}
        trace_configs = [
            ("Real-Time", True, '#eab308'),
            ("Max. Hold", False, '#06b6d4'),
            ("Min. Hold", False, '#d946ef'),
            ("Average", False, '#10b981')
        ]
        
        self.avg_sweeps_spin = QSpinBox()
        self.avg_sweeps_spin.setRange(2, 1000)
        self.avg_sweeps_spin.setValue(10)
        self.avg_sweeps_spin.setSuffix(" sweeps")
        self.avg_sweeps_spin.valueChanged.connect(self.avgSweepsChanged.emit)
        
        for row_idx, (name, def_on, col) in enumerate(trace_configs, start=1):
            cb = QCheckBox(name)
            cb.setChecked(def_on)
            cb.toggled.connect(lambda chk, n=name: self.traceToggled.emit(n, chk))
            
            freeze_cb = QCheckBox()
            freeze_cb.toggled.connect(lambda chk, n=name: self.traceFreezeToggled.emit(n, chk))
            
            picker = SimpleColorPicker(col)
            picker.colorChanged.connect(lambda c, n=name: self.traceColorChanged.emit(n, c))
            
            trace_grid.addWidget(cb, row_idx, 0)
            trace_grid.addWidget(freeze_cb, row_idx, 1, alignment=Qt.AlignmentFlag.AlignCenter)
            trace_grid.addWidget(picker, row_idx, 2, alignment=Qt.AlignmentFlag.AlignCenter)
            
            self.trace_rows[name] = {'cb': cb, 'freeze': freeze_cb, 'picker': picker}
            
        trace_grid.addWidget(QLabel("Avg Depth:"), 5, 0)
        trace_grid.addWidget(self.avg_sweeps_spin, 5, 1, 1, 2)
        trace_card.layout().addLayout(trace_grid)
        
        layout.addStretch()

    def _create_card(self, title: str, parent_layout: QVBoxLayout) -> QFrame:
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        card_layout.addWidget(title_lbl)
        
        parent_layout.addWidget(card)
        return card

    def update_quick_settings_labels(self, presets: list):
        for idx, btn in enumerate(self.quick_btns):
            if idx < len(presets):
                p = presets[idx]
                btn.setText(p.get("name", f"Band {idx+1}"))
                btn.setToolTip(f"{p.get('start')} - {p.get('stop')} MHz")
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _on_auto_atten_toggled(self, checked: bool):
        self.atten_spin.setEnabled(not checked)
        self.amplitudeChanged.emit()

    @property
    def attenuation(self) -> int:
        return -1 if self.auto_atten_check.isChecked() else int(self.atten_spin.value())

    @property
    def rbw_mode(self) -> int:
        idx = self.rbw_mode_combo.currentIndex()
        if 0 <= idx < len(self.rbw_presets):
            return self.rbw_presets[idx][1]
        return 0

    @property
    def rbw_hz(self) -> float:
        idx = self.rbw_mode_combo.currentIndex()
        if 0 <= idx < len(self.rbw_presets):
            preset_hz = self.rbw_presets[idx][2]
            if preset_hz > 0:
                return float(preset_hz)
        return float(self.rbw_spin.value() * 1e6)

    @property
    def vbw_mode(self) -> int:
        idx = self.vbw_mode_combo.currentIndex()
        if 0 <= idx < len(self.vbw_presets):
            return self.vbw_presets[idx][1]
        return 0

    @property
    def vbw_hz(self) -> float:
        idx = self.vbw_mode_combo.currentIndex()
        if 0 <= idx < len(self.vbw_presets):
            preset_hz = self.vbw_presets[idx][2]
            if preset_hz > 0:
                return float(preset_hz)
        return float(self.vbw_spin.value() * 1e6)

    def _on_rbw_mode_changed(self, idx: int):
        if 0 <= idx < len(self.rbw_presets):
            preset_hz = self.rbw_presets[idx][2]
            if preset_hz > 0:
                self.rbw_spin.blockSignals(True)
                self.rbw_spin.setValue(preset_hz / 1e6)
                self.rbw_spin.blockSignals(False)
        self.bwSettingsChanged.emit()

    def _on_vbw_mode_changed(self, idx: int):
        if 0 <= idx < len(self.vbw_presets):
            preset_hz = self.vbw_presets[idx][2]
            if preset_hz > 0:
                self.vbw_spin.blockSignals(True)
                self.vbw_spin.setValue(preset_hz / 1e6)
                self.vbw_spin.blockSignals(False)
        self.bwSettingsChanged.emit()

    def _on_rbw_spin_changed(self, val: float):
        hz = round(val * 1e6)
        matched = False
        for i, (label, mode, p_hz) in enumerate(self.rbw_presets):
            if mode == 0 and abs(p_hz - hz) < 1.0:
                self.rbw_mode_combo.blockSignals(True)
                self.rbw_mode_combo.setCurrentIndex(i)
                self.rbw_mode_combo.blockSignals(False)
                matched = True
                break
        if not matched:
            self.rbw_mode_combo.blockSignals(True)
            self.rbw_mode_combo.setCurrentIndex(len(self.rbw_presets) - 1) # Manual
            self.rbw_mode_combo.blockSignals(False)
        self.bwSettingsChanged.emit()

    def _on_rbw_editing_finished(self):
        self._on_rbw_spin_changed(self.rbw_spin.value())

    def _on_vbw_spin_changed(self, val: float):
        hz = round(val * 1e6)
        matched = False
        for i, (label, mode, p_hz) in enumerate(self.vbw_presets):
            if mode == 0 and abs(p_hz - hz) < 1.0:
                self.vbw_mode_combo.blockSignals(True)
                self.vbw_mode_combo.setCurrentIndex(i)
                self.vbw_mode_combo.blockSignals(False)
                matched = True
                break
        if not matched:
            self.vbw_mode_combo.blockSignals(True)
            self.vbw_mode_combo.setCurrentIndex(len(self.vbw_presets) - 1) # Manual
            self.vbw_mode_combo.blockSignals(False)
        self.bwSettingsChanged.emit()

    def _on_vbw_editing_finished(self):
        self._on_vbw_spin_changed(self.vbw_spin.value())

    def update_hardware_bandwidth(self, rbw_hz: float, vbw_hz: float):
        rbw_idx = self.rbw_mode_combo.currentIndex()
        if rbw_idx == 0 or (0 <= rbw_idx < len(self.rbw_presets) and self.rbw_presets[rbw_idx][1] != 0):
            self.rbw_spin.blockSignals(True)
            self.rbw_spin.setValue(rbw_hz / 1e6)
            self.rbw_spin.blockSignals(False)
        vbw_idx = self.vbw_mode_combo.currentIndex()
        if vbw_idx == 0 or (0 <= vbw_idx < len(self.vbw_presets) and self.vbw_presets[vbw_idx][1] != 0):
            self.vbw_spin.blockSignals(True)
            self.vbw_spin.setValue(vbw_hz / 1e6)
            self.vbw_spin.blockSignals(False)

