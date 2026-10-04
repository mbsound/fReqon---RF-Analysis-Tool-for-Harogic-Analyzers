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
    DETECTOR_TYPES, TRACE_DETECTOR_TYPES, PREAMP_OPTIONS
)

class SweepPanel(QWidget):
    """
    Comprehensive panel for all RF hardware sweep, view span, amplitude, and trace configurations.
    """
    frequenciesChanged = pyqtSignal()
    viewFrequenciesChanged = pyqtSignal()
    quickSettingToggled = pyqtSignal(int, bool)
    quickSoloToggled = pyqtSignal(bool)
    editQuickSettingsClicked = pyqtSignal()
    amplitudeChanged = pyqtSignal()
    scaleDivChanged = pyqtSignal(float)
    autoRefLevelClicked = pyqtSignal()
    sweepSettingsChanged = pyqtSignal()
    detectSettingsChanged = pyqtSignal()
    bwSettingsChanged = pyqtSignal()
    traceToggled = pyqtSignal(str, bool)
    traceFreezeToggled = pyqtSignal(str, bool)
    traceColorChanged = pyqtSignal(str, object)
    avgSweepsChanged = pyqtSignal(int)
    linkViewToggled = pyqtSignal(bool)
    rfInputChanged = pyqtSignal(str)   # "auto" or an input id from the analyzer's capabilities
    settingsTargetChanged = pyqtSignal(object)   # slot id whose settings are shown, None: all analyzers

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
        
        # --- Which analyzer the settings belong to (shown with two or more connected) ---
        self.target_card = self._create_card("ANALYZER SETTINGS FOR", layout)
        self.settings_target_combo = QComboBox()
        self.settings_target_combo.setToolTip(
            "The RF input, amplitude, bandwidth and sweep settings below are kept per analyzer.\n"
            "Choose whose settings to see and change.")
        self.settings_target_combo.currentIndexChanged.connect(self._on_settings_target_selected)
        self.target_card.layout().addWidget(self.settings_target_combo)
        target_hint = QLabel("RF input, amplitude, bandwidth and sweep settings below are this analyzer's.")
        target_hint.setWordWrap(True)
        target_hint.setStyleSheet("color: #8b949e; font-size: 10px;")
        self.target_card.layout().addWidget(target_hint)
        self.target_card.hide()

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
        
        # RF input, for analyzers with more than one (a tinySA's Low and High
        # connectors); the rows are shown by apply_capabilities
        self._rf_input = "auto"
        self._input_ranges = {}     # input id -> (label, min Hz, max Hz)
        self.rf_input_combo = QComboBox()
        self.rf_input_combo.setToolTip("Auto uses the input that covers the sweep.\n"
                                       "The inputs are separate connectors: the signal must be on the one in use.")
        self.rf_input_combo.currentIndexChanged.connect(self._on_rf_input_selected)
        self.rf_input_note = QLabel("")
        self.rf_input_note.setWordWrap(True)
        self.rf_input_note.setFixedWidth(190)
        self.rf_input_note.setStyleSheet("color: #8b949e; font-size: 10px;")
        self._sweep_form = sweep_form
        sweep_form.addRow("RF Input:", self.rf_input_combo)
        sweep_form.addRow("", self.rf_input_note)
        sweep_form.setRowVisible(self.rf_input_combo, False)
        sweep_form.setRowVisible(self.rf_input_note, False)

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

        # Off (the default): the sweep covers every selected band, lowest start to
        # highest stop. On: one band at a time.
        self.solo_qs_btn = QPushButton("Solo")
        self.solo_qs_btn.setObjectName("pillBtn")
        self.solo_qs_btn.setCheckable(True)
        self.solo_qs_btn.setFixedHeight(20)
        self.solo_qs_btn.setToolTip("Off: the sweep spans all selected bands, from the lowest start to the highest stop.\n"
                                    "On: one band at a time, and a start/stop typed by hand deselects the bands.")
        self.solo_qs_btn.toggled.connect(self.quickSoloToggled.emit)
        qs_header.addWidget(self.solo_qs_btn)
        
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

        # Scale / Division Selector
        self.scale_div_combo = QComboBox()
        self.scale_div_combo.addItem("10 dB / div", 10.0)
        self.scale_div_combo.addItem("5 dB / div", 5.0)
        self.scale_div_combo.addItem("2 dB / div", 2.0)
        self.scale_div_combo.addItem("1 dB / div", 1.0)
        self.scale_div_combo.currentIndexChanged.connect(self._on_scale_div_changed)
        
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
        
        # An input whose attenuator is one pad, in or out (a tinySA's High input), gets a
        # switch in place of the dB value. It is the same setting seen differently: the
        # pad is in whenever the attenuation is above 0 dB (and not automatic).
        self.atten_pad_check = QCheckBox("Attenuator in")
        self.atten_pad_check.setVisible(False)
        self.atten_pad_check.toggled.connect(self._on_atten_pad_toggled)
        self.atten_spin.valueChanged.connect(self._sync_atten_pad)
        self.atten_note = QLabel("")
        self.atten_note.setWordWrap(True)
        self.atten_note.setStyleSheet("color: #8b949e; font-size: 10px;")
        self._input_atten = {}
        self._atten_inputs = None

        atten_layout.addWidget(self.atten_spin, 1)
        atten_layout.addWidget(self.auto_atten_check)
        atten_layout.addWidget(self.atten_pad_check, 1)
        
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
        amp_form.addRow("Scale / Div:", self.scale_div_combo)
        amp_form.addRow("Attenuation:", atten_container)
        amp_form.addRow("", self.atten_note)
        amp_form.addRow("Pre-Amplifier:", self.preamp_combo)
        amp_form.addRow("Amp. Offset:", self.amp_offset_spin)
        amp_form.addRow("Enable IFAGC:", self.ifagc_check)
        amp_form.addRow("IFAGC Target:", self.ifagc_target_spin)
        amp_form.addRow("IFAGC Period:", self.ifagc_period_spin)
        amp_form.addRow("Enable IF Out:", self.if_out_check)
        amp_card.layout().addLayout(amp_form)
        self._amp_form = amp_form
        
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
        self._bw_form = bw_form
        
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
        self._adv_form, self._adv_card = adv_form, adv_card
        
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

    def checked_quick_settings(self) -> list:
        return [i for i, btn in enumerate(self.quick_btns) if btn.isChecked() and not btn.isHidden()]

    def set_checked_quick_settings(self, indices):
        for i, btn in enumerate(self.quick_btns):
            btn.setChecked(i in indices)

    def update_quick_settings_labels(self, presets: list):
        for idx, btn in enumerate(self.quick_btns):
            btn.setChecked(False)       # the bands may have changed under the selection
            if idx < len(presets):
                p = presets[idx]
                btn.setText(p.get("name", f"Band {idx+1}"))
                btn.setToolTip(f"{p.get('start')} - {p.get('stop')} MHz")
                btn.setVisible(True)
            else:
                btn.setVisible(False)

    def _on_auto_atten_toggled(self, checked: bool):
        self.atten_spin.setEnabled(not checked)
        self._sync_atten_pad()
        self.amplitudeChanged.emit()

    def _sync_atten_pad(self, *_):
        self.atten_pad_check.blockSignals(True)
        self.atten_pad_check.setChecked(not self.auto_atten_check.isChecked() and self.atten_spin.value() > 0)
        self.atten_pad_check.blockSignals(False)

    def _on_atten_pad_toggled(self, on: bool):
        # Off is 0 dB. On keeps the dB value if there is one, else 10 dB (what the
        # step attenuator of the other input would then use).
        self.auto_atten_check.blockSignals(True)
        self.auto_atten_check.setChecked(False)
        self.auto_atten_check.blockSignals(False)
        self.atten_spin.blockSignals(True)
        self.atten_spin.setValue((self.atten_spin.value() or 10) if on else 0)
        self.atten_spin.blockSignals(False)
        self.amplitudeChanged.emit()

    def _show_atten_for(self, inputs_in_use):
        """Fit the attenuation control to the RF input(s) the sweep uses."""
        kinds = {i: self._input_atten[i] for i in inputs_in_use if self._input_atten.get(i)}
        switches = [a for a in kinds.values() if a.get("kind") == "switch"]
        only_switch = bool(switches) and len(switches) == len(kinds)
        self.atten_spin.setVisible(not only_switch)
        self.auto_atten_check.setVisible(not only_switch)
        self.atten_pad_check.setVisible(only_switch)
        if only_switch:
            label = switches[0].get("label", "pad")
            self.atten_pad_check.setText(f"Attenuator in ({label})")
            note = (f"This input has no step attenuator, only a {label} that is in or out. "
                    f"Readings are corrected for it.")
        elif switches:
            note = (f"The dB value is for the input with the step attenuator. The other input's "
                    f"{switches[0].get('label', 'pad')} is in whenever this is above 0 dB, and out on Auto.")
        else:
            note = ""
        self.atten_note.setText(note)
        self._amp_form.setRowVisible(self.atten_note, bool(note))
        self._sync_atten_pad()

    def _on_scale_div_changed(self, idx: int):
        val = self.scale_div
        self.scaleDivChanged.emit(val)
        self.amplitudeChanged.emit()

    @property
    def scale_div(self) -> float:
        data = self.scale_div_combo.currentData()
        return float(data) if data is not None else 10.0

    def set_scale_div(self, val: float):
        for i in range(self.scale_div_combo.count()):
            if abs(float(self.scale_div_combo.itemData(i)) - float(val)) < 0.01:
                self.scale_div_combo.blockSignals(True)
                self.scale_div_combo.setCurrentIndex(i)
                self.scale_div_combo.blockSignals(False)
                break

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

    def apply_capabilities(self, caps: dict):
        """Show and limit the controls to what the analyzer has (core/device_caps.py)."""
        lo_mhz, hi_mhz = caps["freq_min_hz"] / 1e6, caps["freq_max_hz"] / 1e6
        for spin in (self.start_spin, self.stop_spin, self.center_spin):
            spin.setRange(lo_mhz, hi_mhz)
        self.span_spin.setRange(0.001, hi_mhz - lo_mhz)

        # RBW presets the analyzer does not have (Auto, the span ratios and Manual
        # stay: the analyzer uses its nearest bandwidth)
        rbws = caps["rbw_hz"]
        items = self.rbw_mode_combo.model()
        for i, (_label, mode, hz) in enumerate(self.rbw_presets):
            items.item(i).setEnabled(rbws is None or mode != 0 or hz <= 0 or any(abs(hz - r) < 1.0 for r in rbws))
        if not items.item(self.rbw_mode_combo.currentIndex()).isEnabled():
            self.rbw_mode_combo.setCurrentIndex(0)  # Auto

        atten = caps["atten_db"]
        if atten:
            self.atten_spin.setRange(int(atten[0]), int(atten[1]))
            self.atten_spin.setSingleStep(int(atten[2]))
        self.auto_atten_check.setEnabled(bool(atten) and caps["auto_atten"])
        self.atten_spin.setEnabled(bool(atten) and not self.auto_atten_check.isChecked())

        options = [("LNA Off", 0x01), ("LNA On", 0x04)] if caps["preamp"] == "lna" else PREAMP_OPTIONS
        if [self.preamp_combo.itemText(i) for i in range(self.preamp_combo.count())] != [o[0] for o in options]:
            self.preamp_combo.blockSignals(True)
            self.preamp_combo.clear()
            for label, val in options:
                self.preamp_combo.addItem(label, val)
            self.preamp_combo.blockSignals(False)

        inputs = caps["inputs"] or []
        self.rf_input_combo.blockSignals(True)
        self.rf_input_combo.clear()
        self.rf_input_combo.addItem("Auto (by frequency)", "auto")
        for inp in inputs:
            self.rf_input_combo.addItem(f"{inp['label']}  ({inp['min_hz'] / 1e6:g} – {inp['max_hz'] / 1e6:g} MHz)", inp["id"])
        self.rf_input_combo.setCurrentIndex(max(0, self.rf_input_combo.findData(self._rf_input)))
        self.rf_input_combo.blockSignals(False)
        self._input_ranges = {inp["id"]: (inp["label"], inp["min_hz"], inp["max_hz"]) for inp in inputs}
        self._input_atten = {inp["id"]: inp.get("atten") for inp in inputs}
        if not inputs or self._atten_inputs is None:
            self._atten_inputs = []
        self._show_atten_for(self._atten_inputs)
        self._sweep_form.setRowVisible(self.rf_input_combo, bool(inputs))
        self._sweep_form.setRowVisible(self.rf_input_note, bool(inputs))
        if not inputs:
            self.rf_input_note.setText("")

        # Spur rejection: the analyzer's own choices (a tinySA has Off/On or Off/Auto/On)
        spur_options = caps["spur_options"] or SPUR_REJECTION_MODES
        if [self.spur_combo.itemText(i) for i in range(self.spur_combo.count())] != list(spur_options):
            self.spur_combo.blockSignals(True)
            self.spur_combo.clear()
            self.spur_combo.addItems(list(spur_options))
            self.spur_combo.setCurrentIndex(min(int(caps["spur_default"]), len(spur_options) - 1))
            self.spur_combo.blockSignals(False)

        # Settings the analyzer does not have are not shown at all
        shown_adv = False
        for form, widget, ok in (
            (self._amp_form, self.preamp_combo, caps["preamp"] is not None),
            (self._amp_form, self.ifagc_check, caps["ifagc"]),
            (self._amp_form, self.ifagc_target_spin, caps["ifagc"]),
            (self._amp_form, self.ifagc_period_spin, caps["ifagc"]),
            (self._amp_form, self.if_out_check, caps["if_out"]),
            (self._bw_form, self.vbw_mode_combo, caps["vbw"]),
            (self._bw_form, self.vbw_spin, caps["vbw"]),
            (self._adv_form, self.swt_mode_combo, caps["sweep_time"]),
            (self._adv_form, self.sweep_time_spin, caps["sweep_time"]),
            (self._adv_form, self.trace_points_spin, caps["sweep_points"]),
            (self._adv_form, self.spur_combo, caps["spur_rejection"]),
            (self._adv_form, self.window_combo, caps["window"]),
            (self._adv_form, self.detector_combo, caps["detector"]),
            (self._adv_form, self.trace_detector_combo, caps["detector"]),
        ):
            form.setRowVisible(widget, bool(ok))
            shown_adv = shown_adv or (form is self._adv_form and bool(ok))
        self._adv_card.setVisible(shown_adv)

    # --- Per-analyzer settings ---
    def set_settings_targets(self, entries: list, current=None):
        """
        The analyzers whose settings can be shown: [(slot id or None for all, label)].
        With fewer than two there is nothing to choose and the selector is hidden.
        """
        combo = self.settings_target_combo
        combo.blockSignals(True)
        combo.clear()
        for slot_id, label in entries:
            combo.addItem(label, slot_id)
        combo.setCurrentIndex(max(0, combo.findData(current)))
        combo.blockSignals(False)
        self.target_card.setVisible(len(entries) >= 2)

    def select_settings_target(self, slot_id):
        """Show slot_id as the chosen analyzer, without announcing a change."""
        i = self.settings_target_combo.findData(slot_id)
        if i >= 0:
            self.settings_target_combo.blockSignals(True)
            self.settings_target_combo.setCurrentIndex(i)
            self.settings_target_combo.blockSignals(False)

    def _on_settings_target_selected(self, _index: int):
        self.settingsTargetChanged.emit(self.settings_target_combo.currentData())

    def analyzer_settings(self) -> dict:
        """The settings an analyzer keeps for itself, as shown."""
        return {
            "ref_level": self.ref_level_spin.value(),
            "atten": self.atten_spin.value(), "auto_atten": self.auto_atten_check.isChecked(),
            "preamp": self.preamp_combo.currentData(),
            "ifagc": self.ifagc_check.isChecked(), "ifagc_target": self.ifagc_target_spin.value(),
            "ifagc_period": self.ifagc_period_spin.value(), "if_out": self.if_out_check.isChecked(),
            "rbw_index": self.rbw_mode_combo.currentIndex(), "rbw_mhz": self.rbw_spin.value(),
            "vbw_index": self.vbw_mode_combo.currentIndex(), "vbw_mhz": self.vbw_spin.value(),
            "rbw_mode": self.rbw_mode, "rbw_hz": self.rbw_hz, "vbw_mode": self.vbw_mode, "vbw_hz": self.vbw_hz,
            "swt_mode": self.swt_mode_combo.currentIndex(), "sweep_time": self.sweep_time_spin.value(),
            "spur": self.spur_combo.currentIndex(), "window": self.window_combo.currentIndex(),
            "detector": self.detector_combo.currentIndex(), "trace_detector": self.trace_detector_combo.currentIndex(),
            "rf_input": self._rf_input,
        }

    def set_analyzer_settings(self, d: dict):
        """Show an analyzer's settings (after apply_capabilities for it). Nothing is sent anywhere."""
        widgets = (self.ref_level_spin, self.atten_spin, self.auto_atten_check, self.preamp_combo, self.ifagc_check,
                   self.ifagc_target_spin, self.ifagc_period_spin, self.if_out_check, self.rbw_mode_combo,
                   self.rbw_spin, self.vbw_mode_combo, self.vbw_spin, self.swt_mode_combo, self.sweep_time_spin,
                   self.spur_combo, self.window_combo, self.detector_combo, self.trace_detector_combo)
        for w in widgets:
            w.blockSignals(True)
        self.ref_level_spin.setValue(d["ref_level"])
        self.auto_atten_check.setChecked(d["auto_atten"])
        self.atten_spin.setValue(d["atten"])
        self.atten_spin.setEnabled(self.auto_atten_check.isEnabled() and not d["auto_atten"])
        self._sync_atten_pad()
        self.preamp_combo.setCurrentIndex(max(0, self.preamp_combo.findData(d["preamp"])))
        self.ifagc_check.setChecked(d["ifagc"])
        self.ifagc_target_spin.setValue(d["ifagc_target"])
        self.ifagc_period_spin.setValue(d["ifagc_period"])
        self.if_out_check.setChecked(d["if_out"])
        self.rbw_mode_combo.setCurrentIndex(d["rbw_index"])
        self.rbw_spin.setValue(d["rbw_mhz"])
        self.vbw_mode_combo.setCurrentIndex(d["vbw_index"])
        self.vbw_spin.setValue(d["vbw_mhz"])
        self.swt_mode_combo.setCurrentIndex(d["swt_mode"])
        self.sweep_time_spin.setValue(d["sweep_time"])
        self.spur_combo.setCurrentIndex(min(d["spur"], self.spur_combo.count() - 1))
        self.window_combo.setCurrentIndex(d["window"])
        self.detector_combo.setCurrentIndex(d["detector"])
        self.trace_detector_combo.setCurrentIndex(d["trace_detector"])
        for w in widgets:
            w.blockSignals(False)
        self.set_rf_input(d["rf_input"])

    @property
    def rf_input(self) -> str:
        """The RF input the user wants ("auto" or an input id); kept while no such analyzer is connected."""
        return self._rf_input

    def set_rf_input(self, rf_input: str):
        self._rf_input = rf_input or "auto"
        i = self.rf_input_combo.findData(self._rf_input)
        if i >= 0:
            self.rf_input_combo.blockSignals(True)
            self.rf_input_combo.setCurrentIndex(i)
            self.rf_input_combo.blockSignals(False)

    def _on_rf_input_selected(self, _index: int):
        choice = self.rf_input_combo.currentData()
        if choice and choice != self._rf_input:
            self._rf_input = choice
            self.rfInputChanged.emit(choice)

    def show_sweep_plan(self, plan: dict) -> str:
        """
        Show which RF input(s) the analyzer's sweep uses (and any range note)
        under the RF Input selector. Returns a one-line summary.
        """
        labels = [self._input_ranges[i][0] for i in plan.get("inputs", []) if i in self._input_ranges]
        self._atten_inputs = [i for i in plan.get("inputs", []) if i in self._input_ranges]
        self._show_atten_for(self._atten_inputs)
        note = plan.get("note") or ""
        if len(labels) == 1:
            summary = f"{labels[0]} input in use"
        elif labels:
            split_mhz = self._input_ranges[plan["inputs"][0]][2] / 1e6
            summary = (f"{labels[0]} input below {split_mhz:g} MHz, {labels[1]} input above: "
                       f"both connectors are used")
        else:
            summary = note or "No input covers this sweep"
            note = ""
        problem = not labels or bool(note)
        self.rf_input_note.setText(summary + (f"\n{note}" if note else ""))
        self.rf_input_note.setStyleSheet(f"color: {'#f59e0b' if problem else '#10b981'}; font-size: 10px;")
        return summary

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

