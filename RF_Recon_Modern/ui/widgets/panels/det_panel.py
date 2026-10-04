"""
det_panel.py - Zero-Span / Power vs. Time (DET) Parameter Control Panel.
Provides precision controls for Center Frequency, Decimation (Time Resolution),
Acquisition Window Length, Reference Level, Attenuation, Preamp, and Trigger Source.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..freq_inputs import FreqSpinBox

class DETPanel(QWidget):
    """
    Zero-Span DET Oscilloscope Parameter & Acquisition Control Panel.
    """
    paramsChanged = pyqtSignal(dict)
    triggerRequested = pyqtSignal(dict)
    pauseRequested = pyqtSignal()
    presetSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detPanel")
        self.is_active = False
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Primary Trigger / Pause Zero-Span Button
        self.trigger_btn = QPushButton("Trigger Zero-Span")
        self.trigger_btn.setObjectName("triggerBtn")
        self.trigger_btn.setFixedHeight(34)
        self._update_trigger_btn_style()
        self.trigger_btn.clicked.connect(self._on_trigger_clicked)
        layout.addWidget(self.trigger_btn)
        
        # 1. Zero-Span Frequency Tuning Card
        rf_card, rf_layout = self._create_card("ZERO-SPAN TUNING")
        
        cf_row = QHBoxLayout()
        cf_lbl = QLabel("Center Freq:")
        cf_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.cf_spin = FreqSpinBox()
        self.cf_spin.setRange(1.0, 6000.0)
        self.cf_spin.setValue(1925.0) # Default DECT carrier center
        cf_row.addWidget(cf_lbl)
        cf_row.addWidget(self.cf_spin)
        rf_layout.addLayout(cf_row)
        
        # Quick Presets (2x2 Grid)
        from PyQt6.QtWidgets import QGridLayout
        presets_grid = QGridLayout()
        presets_grid.setSpacing(4)
        
        btn_dect = QPushButton("DECT 1.9G")
        btn_dect.setObjectName("pillBtn")
        btn_dect.setFixedHeight(22)
        btn_dect.clicked.connect(self._apply_preset_dect)
        presets_grid.addWidget(btn_dect, 0, 0)
        
        btn_bolero = QPushButton("Bolero")
        btn_bolero.setObjectName("pillBtn")
        btn_bolero.setFixedHeight(22)
        btn_bolero.clicked.connect(self._apply_preset_bolero)
        presets_grid.addWidget(btn_bolero, 0, 1)
        
        btn_bt = QPushButton("BT / 2.4G")
        btn_bt.setObjectName("pillBtn")
        btn_bt.setFixedHeight(22)
        btn_bt.clicked.connect(self._apply_preset_bt)
        presets_grid.addWidget(btn_bt, 1, 0)
        
        btn_uhf = QPushButton("UHF Mic")
        btn_uhf.setObjectName("pillBtn")
        btn_uhf.setFixedHeight(22)
        btn_uhf.clicked.connect(lambda: self.cf_spin.setValue(550.0))
        presets_grid.addWidget(btn_uhf, 1, 1)
        
        rf_layout.addLayout(presets_grid)
        
        layout.addWidget(rf_card)
        
        # 2. Time Resolution & Buffer Card
        time_card, time_layout = self._create_card("TIME RESOLUTION & LENGTH")
        
        dec_row = QHBoxLayout()
        dec_lbl = QLabel("Time Res:")
        dec_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.dec_combo = QComboBox()
        self.dec_combo.addItem("8 ns (Decimate 1)", 1)
        self.dec_combo.addItem("16 ns (Decimate 2)", 2)
        self.dec_combo.addItem("32 ns (Decimate 4)", 4)
        self.dec_combo.addItem("64 ns (Decimate 8)", 8)
        self.dec_combo.addItem("128 ns (Decimate 16)", 16)
        self.dec_combo.addItem("256 ns (Decimate 32)", 32)
        self.dec_combo.addItem("512 ns (Decimate 64)", 64)
        self.dec_combo.addItem("1.02 us (Decimate 128)", 128)
        self.dec_combo.setCurrentIndex(1) # Default 16 ns
        self._interval_ns = 8.0      # per sample at decimation 1
        self._det_caps = None        # an analyzer's own zero-span options (apply_capabilities)
        dec_row.addWidget(dec_lbl)
        dec_row.addWidget(self.dec_combo)
        time_layout.addLayout(dec_row)
        
        len_row = QHBoxLayout()
        len_lbl = QLabel("Trace Length:")
        len_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.len_combo = QComboBox()
        self.len_combo.addItem("2048 Points", 2048)
        self.len_combo.addItem("4096 Points", 4096)
        self.len_combo.addItem("8192 Points", 8192)
        self.len_combo.addItem("16240 Points", 16240)
        self.len_combo.addItem("32768 Points", 32768)
        self.len_combo.addItem("65536 Points", 65536)
        self.len_combo.setCurrentIndex(3) # 16240
        len_row.addWidget(len_lbl)
        len_row.addWidget(self.len_combo)
        time_layout.addLayout(len_row)
        
        # Live Time Window Span Readout
        self.window_info_lbl = QLabel("Window Span: 259.8 us")
        self.window_info_lbl.setStyleSheet("color: #10b981; font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600; padding-top: 2px;")
        time_layout.addWidget(self.window_info_lbl)
        self.caps_note_lbl = QLabel("")
        self.caps_note_lbl.setWordWrap(True)
        self.caps_note_lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
        self.caps_note_lbl.setVisible(False)
        time_layout.addWidget(self.caps_note_lbl)
        
        self.dec_combo.currentIndexChanged.connect(self._update_window_info)
        self.len_combo.currentIndexChanged.connect(self._update_window_info)
        
        layout.addWidget(time_card)
        
        # 3. Amplitude & Gain Card
        gain_card, gain_layout = self._create_card("AMPLITUDE & GAIN")
        
        ref_row = QHBoxLayout()
        ref_lbl = QLabel("Ref. Level:")
        ref_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.ref_spin = QDoubleSpinBox()
        self.ref_spin.setRange(-120.0, 30.0)
        self.ref_spin.setValue(0.0)
        self.ref_spin.setSuffix(" dBm")
        ref_row.addWidget(ref_lbl)
        ref_row.addWidget(self.ref_spin)
        gain_layout.addLayout(ref_row)
        
        att_row = QHBoxLayout()
        att_lbl = QLabel("Attenuation:")
        att_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.att_combo = QComboBox()
        self.att_combo.addItem("Auto (0 dB)", 0)
        self.att_combo.addItem("10 dB", 10)
        self.att_combo.addItem("20 dB", 20)
        self.att_combo.addItem("30 dB", 30)
        att_row.addWidget(att_lbl)
        att_row.addWidget(self.att_combo)
        gain_layout.addLayout(att_row)
        
        preamp_row = QHBoxLayout()
        preamp_lbl = self.preamp_lbl = QLabel("Pre-Amplifier:")
        preamp_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.preamp_combo = QComboBox()
        self.preamp_combo.addItem("Auto On", 0x00)
        self.preamp_combo.addItem("Forced Off", 0x01)
        preamp_row.addWidget(preamp_lbl)
        preamp_row.addWidget(self.preamp_combo)
        gain_layout.addLayout(preamp_row)
        self.gain_note_lbl = QLabel("")
        self.gain_note_lbl.setWordWrap(True)
        self.gain_note_lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
        self.gain_note_lbl.setVisible(False)
        gain_layout.addWidget(self.gain_note_lbl)
        self._caps = None            # the analyzer's capabilities, when it has its own gain choices
        self._rf_input = "auto"
        self.cf_spin.valueChanged.connect(self._refresh_gain_options)
        
        layout.addWidget(gain_card)
        
        # 4. Trigger Configuration Card
        trig_card, trig_layout = self._create_card("TRIGGER CONFIGURATION")
        
        tsrc_row = QHBoxLayout()
        tsrc_lbl = QLabel("Source:")
        tsrc_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.trig_source_combo = QComboBox()
        self.trig_source_combo.addItem("Internal Bus Trigger", 2)
        self.trig_source_combo.addItem("External Trigger (SMA)", 1)
        self.trig_source_combo.addItem("Level Threshold Trigger", 3)
        tsrc_row.addWidget(tsrc_lbl)
        tsrc_row.addWidget(self.trig_source_combo)
        trig_layout.addLayout(tsrc_row)

        # A trigger level, for analyzers whose zero span takes one (apply_capabilities)
        self.trig_level_lbl = QLabel("Level:")
        self.trig_level_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.trig_level_spin = QDoubleSpinBox()
        self.trig_level_spin.setRange(-130.0, 10.0)
        self.trig_level_spin.setDecimals(0)
        self.trig_level_spin.setValue(-60.0)
        self.trig_level_spin.setSuffix(" dBm")
        tlvl_row = QHBoxLayout()
        tlvl_row.addWidget(self.trig_level_lbl)
        tlvl_row.addWidget(self.trig_level_spin)
        trig_layout.addLayout(tlvl_row)
        self.trig_level_lbl.setVisible(False)
        self.trig_level_spin.setVisible(False)
        self.trig_source_combo.currentIndexChanged.connect(self._sync_trig_level)
        
        layout.addWidget(trig_card)
        
        # Apply Action Button
        self.apply_btn = QPushButton("Apply Zero-Span Parameters")
        self.apply_btn.setObjectName("primaryActionBtn")
        self.apply_btn.setFixedHeight(28)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        layout.addWidget(self.apply_btn)
        
        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_card(self, title: str):
        card = QFrame()
        card.setObjectName("cardFrame")
        card.setStyleSheet("""
            QFrame#cardFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(6, 6, 6, 6)
        c_layout.setSpacing(6)
        hdr = QLabel(title)
        hdr.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px; padding-bottom: 2px;")
        c_layout.addWidget(hdr)
        return card, c_layout

    def _update_trigger_btn_style(self):
        if self.is_active:
            self.trigger_btn.setText("Pause Zero-Span")
            self.trigger_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0969da;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    border-radius: 6px;
                    border: 1px solid #218bff;
                }
                QPushButton:hover {
                    background-color: #1f7bf2;
                }
                QPushButton:pressed {
                    background-color: #054da7;
                }
            """)
        else:
            self.trigger_btn.setText("Trigger Zero-Span")
            self.trigger_btn.setStyleSheet("""
                QPushButton {
                    background-color: #238636;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    border-radius: 6px;
                    border: 1px solid #2ea043;
                }
                QPushButton:hover {
                    background-color: #2ea043;
                }
                QPushButton:pressed {
                    background-color: #1a7f37;
                }
            """)

    def set_active_state(self, active: bool):
        self.is_active = active
        self._update_trigger_btn_style()

    def _on_trigger_clicked(self):
        if self.is_active:
            self.set_active_state(False)
            self.pauseRequested.emit()
        else:
            self.set_active_state(True)
            params = self.get_params()
            self.triggerRequested.emit(params)

    def _on_apply_clicked(self):
        params = self.get_params()
        self.set_active_state(True)
        self.triggerRequested.emit(params)
        self.paramsChanged.emit(params)

    def _select_combo_data(self, combo: QComboBox, data_val):
        for idx in range(combo.count()):
            if combo.itemData(idx) == data_val:
                combo.setCurrentIndex(idx)
                break

    HAROGIC_DECIMATIONS = (("8 ns (Decimate 1)", 1), ("16 ns (Decimate 2)", 2), ("32 ns (Decimate 4)", 4),
                           ("64 ns (Decimate 8)", 8), ("128 ns (Decimate 16)", 16), ("256 ns (Decimate 32)", 32),
                           ("512 ns (Decimate 64)", 64), ("1.02 us (Decimate 128)", 128))
    HAROGIC_LENGTHS = (2048, 4096, 8192, 16240, 32768, 65536)
    HAROGIC_TRIGGERS = (("Internal Bus Trigger", 2), ("External Trigger (SMA)", 1), ("Level Threshold Trigger", 3))

    @staticmethod
    def _fill(combo: QComboBox, items, select):
        combo.blockSignals(True)
        combo.clear()
        for label, data in items:
            combo.addItem(label, data)
        combo.setCurrentIndex(max(0, combo.findData(select)))
        combo.blockSignals(False)

    def apply_capabilities(self, caps: dict):
        """
        Offer the analyzer's own zero-span options (core/device_caps.py "det"). A
        Harogic analyzer samples every 8 ns x decimation; a tinySA has one, much
        slower, rate, takes its gain settings from RF & Sweep and has no external trigger.
        """
        self.cf_spin.setRange(max(0.001, caps["freq_min_hz"] / 1e6), caps["freq_max_hz"] / 1e6)
        det = caps.get("det")
        self._caps = caps if det else None
        self._refresh_gain_options()
        if det == self._det_caps:
            return
        self._det_caps = det
        if det:
            dt_ns = float(det["sample_interval_ns"])
            self._interval_ns = dt_ns
            self._fill(self.dec_combo, [(f"{dt_ns / 1e3:.0f} us (fixed)", 1)], 1)
            lengths = list(det.get("lengths") or [det["max_points"]])
            self._fill(self.len_combo, [(f"{n} Points", n) for n in lengths], lengths[-1])
            self._fill(self.trig_source_combo, list(det["trigger_sources"]), det["trigger_sources"][0][1])
        else:
            self._interval_ns = 8.0
            self._fill(self.dec_combo, self.HAROGIC_DECIMATIONS, 2)
            self._fill(self.len_combo, [(f"{n} Points", n) for n in self.HAROGIC_LENGTHS], 16240)
            self._fill(self.trig_source_combo, self.HAROGIC_TRIGGERS, 2)
        self.dec_combo.setEnabled(not det)
        has_level = bool(det and det.get("trigger_level"))
        self.trig_level_lbl.setVisible(has_level)
        self.trig_level_spin.setVisible(has_level)
        self._sync_trig_level()
        self.caps_note_lbl.setText((det or {}).get("note", ""))
        self.caps_note_lbl.setVisible(bool(det and det.get("note")))
        self._update_window_info()

    HAROGIC_ATTEN = (("Auto (0 dB)", 0), ("10 dB", 10), ("20 dB", 20), ("30 dB", 30))
    HAROGIC_PREAMP = (("Auto On", 0x00), ("Forced Off", 0x01))

    def set_rf_input(self, rf_input: str):
        """The RF input chosen in RF & Sweep ("auto": by frequency), for analyzers with several."""
        self._rf_input = rf_input or "auto"
        self._refresh_gain_options()

    def _input_in_use(self):
        """The analyzer input (capabilities "inputs" entry) the centre frequency is measured on, or None."""
        inputs = (self._caps or {}).get("inputs") or []
        chosen = next((i for i in inputs if i["id"] == self._rf_input), None)
        if chosen:
            return chosen
        f = self.cf_spin.value() * 1e6
        return next((i for i in inputs if i["min_hz"] <= f <= i["max_hz"]), None)   # the first that reaches it

    def _refresh_gain_options(self, *_):
        """
        Attenuation and pre-amplifier choices of the analyzer in use. A tinySA: 0-31 dB
        or automatic on the Low input, a pad in or out on the High input, no pre-amplifier;
        a tinySA Ultra: 0-31 dB or automatic, and its LNA.
        """
        caps = self._caps
        if not caps:
            atten, preamp, note = self.HAROGIC_ATTEN, self.HAROGIC_PREAMP, ""
        else:
            inp = self._input_in_use()
            kind = (inp or {}).get("atten") or ({"kind": "range", "db": caps["atten_db"]} if caps.get("atten_db") else None)
            note = ""
            if kind and kind["kind"] == "switch":
                label = kind.get("label", "pad")
                atten = (("Out (0 dB)", 0), (f"In ({label})", 10))
                note = f"The {inp['label']} input has no step attenuator, only a {label} that is in or out."
            elif kind:
                lo, hi, step = (int(v) for v in kind["db"])
                atten = ((("Auto", -1),) if caps.get("auto_atten") else ()) + tuple(
                    (f"{v} dB", v) for v in range(lo, hi + 1, max(1, step)))
            else:
                atten = ()
            preamp = (("LNA Off", 0x01), ("LNA On", 0x04)) if caps.get("preamp") == "lna" else ()
            if preamp:
                note = (note + " " if note else "") + "The LNA bypasses the attenuator."
        for combo, items in ((self.att_combo, atten), (self.preamp_combo, preamp)):
            if [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())] == list(items):
                continue
            was = combo.currentData()
            # The same setting where the new choices have it; a pad follows "some attenuation"
            if combo is self.att_combo and was is not None and was not in [d for _l, d in items]:
                was = next((d for _l, d in items if d > 0), None) if was > 0 else next((d for _l, d in items), None)
            self._fill(combo, items, was)
        self.att_combo.setEnabled(bool(atten))
        self.preamp_lbl.setVisible(bool(preamp))
        self.preamp_combo.setVisible(bool(preamp))
        self.gain_note_lbl.setText(note)
        self.gain_note_lbl.setVisible(bool(note))

    def set_gain(self, atten, preamp):
        """Show an attenuation (-1: automatic) and pre-amplifier setting, as far as the analyzer has them."""
        if atten is not None and self.att_combo.count():
            data = [self.att_combo.itemData(i) for i in range(self.att_combo.count())]
            if atten not in data:
                positive = [d for d in data if d > 0]
                atten = min(positive, key=lambda d: abs(d - atten)) if atten > 0 and positive else data[0]
            self._select_combo_data(self.att_combo, atten)
        if preamp is not None:
            self._select_combo_data(self.preamp_combo, preamp)

    def _sync_trig_level(self, *_):
        # Free run (the bus trigger) has no level
        self.trig_level_spin.setEnabled(self.trig_source_combo.currentData() != 2)

    def _update_window_info(self):
        pts = self.len_combo.currentData() or 16240
        dec = self.dec_combo.currentData() or 2
        dur_s = pts * self._interval_ns * 1e-9 * dec
        if dur_s >= 1.0:
            s_str = f"{dur_s:.2f} s"
        elif dur_s >= 1e-3:
            s_str = f"{dur_s * 1e3:.2f} ms"
        else:
            s_str = f"{dur_s * 1e6:.1f} us"
        self.window_info_lbl.setText(f"Window Span: {s_str}")

    def _apply_preset_dect(self):
        self.cf_spin.setValue(1925.0)
        # Decimate 32 (256 ns) with 16240 pts = 4.16 ms (10 full DECT slots with single-packet speed)
        self._select_combo_data(self.dec_combo, 32)
        self._select_combo_data(self.len_combo, 16240)
        self._update_window_info()
        self.presetSelected.emit("dect")

    def _apply_preset_bolero(self):
        self.cf_spin.setValue(1900.0)
        # Decimate 32 (256 ns) with 16240 pts = 4.16 ms (4+ full Bolero 1ms slots with single-packet speed)
        self._select_combo_data(self.dec_combo, 32)
        self._select_combo_data(self.len_combo, 16240)
        self._update_window_info()
        self.presetSelected.emit("bolero")

    def _apply_preset_bt(self):
        self.cf_spin.setValue(2440.0)
        # Decimate 16 (128 ns) with 16240 pts = 2.08 ms (3.3 full Bluetooth 625 us slots with single-packet speed)
        self._select_combo_data(self.dec_combo, 16)
        self._select_combo_data(self.len_combo, 16240)
        self._update_window_info()
        self.presetSelected.emit("bluetooth")

    def auto_fit_window(self, min_duration_ns: float):
        if self._det_caps:
            # One sample rate: the shortest length that covers it
            lengths = [self.len_combo.itemData(i) for i in range(self.len_combo.count())]
            fit = next((n for n in lengths if n * self._interval_ns >= min_duration_ns), lengths[-1])
            self._select_combo_data(self.len_combo, fit)
            self._update_window_info()
            return
        # Prefer 16240 points for ultra-fast single-packet USB transfers
        for pts in [16240, 32768, 65536]:
            for dec in [1, 2, 4, 8, 16, 32, 64, 128]:
                span_ns = pts * 8.0 * dec
                if span_ns >= min_duration_ns:
                    self._select_combo_data(self.dec_combo, dec)
                    self._select_combo_data(self.len_combo, pts)
                    self._update_window_info()
                    return
        self._select_combo_data(self.dec_combo, 128)
        self._select_combo_data(self.len_combo, 16240)
        self._update_window_info()

    def get_params(self) -> dict:
        return {
            "center_freq_hz": self.cf_spin.value() * 1e6,
            "decimate_factor": self.dec_combo.currentData(),
            "trigger_length": self.len_combo.currentData(),
            "ref_level": self.ref_spin.value(),
            "atten": self.att_combo.currentData(),
            "preamp": self.preamp_combo.currentData(),
            "trigger_source": self.trig_source_combo.currentData(),
            "trigger_mode": 0,
            # Sent with the zero-span settings for analyzers with their own gain choices (a tinySA)
            "own_gain": bool(self._caps),
            # None: the analyzer's zero span takes no level
            "trigger_level": self.trig_level_spin.value() if (self._det_caps or {}).get("trigger_level") else None,
        }
