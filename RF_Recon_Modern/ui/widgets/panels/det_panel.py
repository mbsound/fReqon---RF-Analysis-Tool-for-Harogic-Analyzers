"""
det_panel.py - Zero-Span / Power vs. Time (DET) Parameter Control Panel.
Provides precision controls for Center Frequency, Decimation (Time Resolution),
Acquisition Window Length, Reference Level, Attenuation, Preamp, and Trigger Source.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QSpinBox, QFrame, QScrollArea
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
        preamp_lbl = QLabel("Pre-Amplifier:")
        preamp_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.preamp_combo = QComboBox()
        self.preamp_combo.addItem("Auto On", 0x00)
        self.preamp_combo.addItem("Forced Off", 0x01)
        preamp_row.addWidget(preamp_lbl)
        preamp_row.addWidget(self.preamp_combo)
        gain_layout.addLayout(preamp_row)
        
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

    def _update_window_info(self):
        pts = self.len_combo.currentData() or 16240
        dec = self.dec_combo.currentData() or 2
        dur_s = pts * 8e-9 * dec
        if dur_s >= 1e-3:
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
            "trigger_mode": 0
        }
