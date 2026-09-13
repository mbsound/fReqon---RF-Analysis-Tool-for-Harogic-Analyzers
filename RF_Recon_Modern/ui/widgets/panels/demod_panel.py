"""
demod_panel.py - Demodulation Parameter & Vector Signal Analysis Control Panel.
Provides controls for:
- Modulation Type: ASK (2/4), FSK (2/4/GMSK), PSK (BPSK/QPSK/8-PSK), QAM (16/32/64/128/256-QAM)
- Symbol Rate (Baud / SPS) and Presets
- Matched Filter (RRC, RC, Gaussian) and Roll-Off Alpha
- Center Frequency (coupled with click-to-demod on spectrum/waterfall)
- Live Signal Metrics Card: EVM RMS / Peak, SNR, Frequency Error, Carrier Power, Lock State.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QSpinBox, QFrame, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..freq_inputs import FreqSpinBox
from core.demod_engine import MOD_TYPES, DemodResult

class DemodPanel(QWidget):
    """
    Demodulation & Vector Signal Analyzer Control Panel.
    """
    paramsChanged = pyqtSignal(dict)
    demodRequested = pyqtSignal(dict)
    pauseRequested = pyqtSignal()
    tuneRequested = pyqtSignal(float) # Center Freq in MHz

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("demodPanel")
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

        # Primary Trigger / Pause Demodulation Button
        self.trigger_btn = QPushButton("Demodulate Carrier")
        self.trigger_btn.setObjectName("triggerBtn")
        self.trigger_btn.setFixedHeight(34)
        self._update_trigger_btn_style()
        self.trigger_btn.clicked.connect(self._on_trigger_clicked)
        layout.addWidget(self.trigger_btn)
        
        # 1. Carrier Frequency Tuning Card
        rf_card, rf_layout = self._create_card("CARRIER FREQUENCY & TUNING")
        
        cf_row = QHBoxLayout()
        cf_lbl = QLabel("Center Freq:")
        cf_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.cf_spin = FreqSpinBox()
        self.cf_spin.setRange(1.0, 6000.0)
        self.cf_spin.setValue(500.0) # Default UHF
        self.cf_spin.valueChanged.connect(self._on_freq_spin_changed)
        cf_row.addWidget(cf_lbl)
        cf_row.addWidget(self.cf_spin)
        rf_layout.addLayout(cf_row)
        
        hint_lbl = QLabel("💡 Click any signal on the Spectrum / Waterfall to tune")
        hint_lbl.setStyleSheet("color: #38bdf8; font-size: 10px; font-style: italic; padding: 2px 0;")
        rf_layout.addWidget(hint_lbl)
        
        # Quick Presets (2x2 Grid)
        presets_grid = QGridLayout()
        presets_grid.setSpacing(4)
        
        btn_dtv = QPushButton("DTV 500M")
        btn_dtv.setObjectName("pillBtn")
        btn_dtv.setFixedHeight(22)
        btn_dtv.clicked.connect(lambda: self.set_center_freq_mhz(500.0))
        presets_grid.addWidget(btn_dtv, 0, 0)
        
        btn_dect = QPushButton("DECT 1925M")
        btn_dect.setObjectName("pillBtn")
        btn_dect.setFixedHeight(22)
        btn_dect.clicked.connect(lambda: self.set_center_freq_mhz(1925.0))
        presets_grid.addWidget(btn_dect, 0, 1)
        
        btn_ism = QPushButton("ISM 915M")
        btn_ism.setObjectName("pillBtn")
        btn_ism.setFixedHeight(22)
        btn_ism.clicked.connect(lambda: self.set_center_freq_mhz(915.0))
        presets_grid.addWidget(btn_ism, 1, 0)
        
        btn_24g = QPushButton("2.4G ISM")
        btn_24g.setObjectName("pillBtn")
        btn_24g.setFixedHeight(22)
        btn_24g.clicked.connect(lambda: self.set_center_freq_mhz(2440.0))
        presets_grid.addWidget(btn_24g, 1, 1)
        
        rf_layout.addLayout(presets_grid)
        layout.addWidget(rf_card)
        
        # 2. Modulation Scheme & Format Card
        mod_card, mod_layout = self._create_card("MODULATION & SCHEME")
        
        cat_row = QHBoxLayout()
        cat_lbl = QLabel("Category:")
        cat_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.category_combo = QComboBox()
        self.category_combo.addItems(["PSK", "QAM", "FSK", "ASK"])
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        cat_row.addWidget(cat_lbl)
        cat_row.addWidget(self.category_combo)
        mod_layout.addLayout(cat_row)
        
        type_row = QHBoxLayout()
        type_lbl = QLabel("Type:")
        type_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.type_combo = QComboBox()
        self._populate_mod_types("PSK")
        self.type_combo.currentIndexChanged.connect(self._on_params_changed)
        type_row.addWidget(type_lbl)
        type_row.addWidget(self.type_combo)
        mod_layout.addLayout(type_row)
        
        sym_row = QHBoxLayout()
        sym_lbl = QLabel("Symbol Rate:")
        sym_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.sym_rate_spin = QDoubleSpinBox()
        self.sym_rate_spin.setRange(0.01, 20.0)
        self.sym_rate_spin.setValue(1.0)
        self.sym_rate_spin.setDecimals(3)
        self.sym_rate_spin.setSuffix(" MBd")
        self.sym_rate_spin.valueChanged.connect(self._on_params_changed)
        sym_row.addWidget(sym_lbl)
        sym_row.addWidget(self.sym_rate_spin)
        mod_layout.addLayout(sym_row)
        
        # Symbol Rate Presets
        sym_presets = QHBoxLayout()
        sym_presets.setSpacing(4)
        for s_val, s_txt in [(0.1, "100k"), (0.5, "500k"), (1.0, "1M"), (2.0, "2M")]:
            btn = QPushButton(s_txt)
            btn.setObjectName("pillBtn")
            btn.setFixedHeight(20)
            btn.clicked.connect(lambda _, v=s_val: self.sym_rate_spin.setValue(v))
            sym_presets.addWidget(btn)
        mod_layout.addLayout(sym_presets)
        
        layout.addWidget(mod_card)
        
        # 3. Filter & Channel Card
        filt_card, filt_layout = self._create_card("FILTER & CHANNEL BANDWIDTH")
        
        filt_row = QHBoxLayout()
        filt_lbl = QLabel("Filter:")
        filt_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["RootRaisedCosine", "RaisedCosine", "Gaussian", "Rectangular"])
        self.filter_combo.currentIndexChanged.connect(self._on_params_changed)
        filt_row.addWidget(filt_lbl)
        filt_row.addWidget(self.filter_combo)
        filt_layout.addLayout(filt_row)
        
        alpha_row = QHBoxLayout()
        alpha_lbl = QLabel("Alpha (α):")
        alpha_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.05, 0.99)
        self.alpha_spin.setValue(0.35)
        self.alpha_spin.setSingleStep(0.05)
        self.alpha_spin.setDecimals(2)
        self.alpha_spin.valueChanged.connect(self._on_params_changed)
        alpha_row.addWidget(alpha_lbl)
        alpha_row.addWidget(self.alpha_spin)
        filt_layout.addLayout(alpha_row)
        
        dec_row = QHBoxLayout()
        dec_lbl = QLabel("IQ Bandwidth:")
        dec_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.dec_combo = QComboBox()
        self.dec_combo.addItem("5.00 MHz (Decimate 16)", 16)
        self.dec_combo.addItem("2.50 MHz (Decimate 32)", 32)
        self.dec_combo.addItem("1.25 MHz (Decimate 64)", 64)
        self.dec_combo.addItem("625 kHz (Decimate 128)", 128)
        self.dec_combo.setCurrentIndex(2) # Default Decimate 64 (1.25 MHz)
        self.dec_combo.currentIndexChanged.connect(self._on_params_changed)
        dec_row.addWidget(dec_lbl)
        dec_row.addWidget(self.dec_combo)
        filt_layout.addLayout(dec_row)
        
        layout.addWidget(filt_card)
        
        # 4. Live Signal Metrics Card
        metrics_card, metrics_layout = self._create_card("LIVE SIGNAL METRICS")
        
        # Lock status badge
        lock_row = QHBoxLayout()
        lock_lbl = QLabel("Sync Lock:")
        lock_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.lock_badge = QLabel("SEARCHING")
        self.lock_badge.setStyleSheet("""
            background-color: #30363d;
            color: #d29922;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        lock_row.addWidget(lock_lbl)
        lock_row.addStretch()
        lock_row.addWidget(self.lock_badge)
        metrics_layout.addLayout(lock_row)
        
        # Metrics Table (Grid)
        m_grid = QGridLayout()
        m_grid.setSpacing(6)
        
        m_grid.addWidget(self._create_metric_lbl("EVM RMS:"), 0, 0)
        self.evm_rms_val = self._create_val_lbl("-- %")
        m_grid.addWidget(self.evm_rms_val, 0, 1)
        
        m_grid.addWidget(self._create_metric_lbl("EVM Peak:"), 1, 0)
        self.evm_peak_val = self._create_val_lbl("-- %")
        m_grid.addWidget(self.evm_peak_val, 1, 1)
        
        m_grid.addWidget(self._create_metric_lbl("SNR:"), 2, 0)
        self.snr_val = self._create_val_lbl("-- dB")
        m_grid.addWidget(self.snr_val, 2, 1)
        
        m_grid.addWidget(self._create_metric_lbl("Freq Offset:"), 3, 0)
        self.freq_err_val = self._create_val_lbl("-- Hz")
        m_grid.addWidget(self.freq_err_val, 3, 1)
        
        m_grid.addWidget(self._create_metric_lbl("Carrier Power:"), 4, 0)
        self.carrier_pwr_val = self._create_val_lbl("-- dBm")
        m_grid.addWidget(self.carrier_pwr_val, 4, 1)
        
        m_grid.addWidget(self._create_metric_lbl("99% OBW:"), 5, 0)
        self.obw_val = self._create_val_lbl("-- kHz")
        m_grid.addWidget(self.obw_val, 5, 1)
        
        metrics_layout.addLayout(m_grid)
        layout.addWidget(metrics_card)
        
        # 5. Hardware Frontend Controls
        hw_card, hw_layout = self._create_card("RECEIVER FRONTEND")
        
        ref_row = QHBoxLayout()
        ref_lbl = QLabel("Ref. Level:")
        ref_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.ref_spin = QDoubleSpinBox()
        self.ref_spin.setRange(-120.0, 30.0)
        self.ref_spin.setValue(0.0)
        self.ref_spin.setSuffix(" dBm")
        ref_row.addWidget(ref_lbl)
        ref_row.addWidget(self.ref_spin)
        hw_layout.addLayout(ref_row)
        
        preamp_row = QHBoxLayout()
        preamp_lbl = QLabel("Pre-Amplifier:")
        preamp_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.preamp_combo = QComboBox()
        self.preamp_combo.addItem("Auto On", 0x00)
        self.preamp_combo.addItem("Forced Off", 0x01)
        self.preamp_combo.addItem("High Gain", 0x04)
        preamp_row.addWidget(preamp_lbl)
        preamp_row.addWidget(self.preamp_combo)
        hw_layout.addLayout(preamp_row)
        
        layout.addWidget(hw_card)
        
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

    def _create_metric_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        return lbl

    def _create_val_lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #f0f6fc; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;")
        return lbl

    def _populate_mod_types(self, category: str):
        self.type_combo.blockSignals(True)
        self.type_combo.clear()
        types = MOD_TYPES.get(category, ["QPSK"])
        self.type_combo.addItems(types)
        self.type_combo.blockSignals(False)

    def _on_category_changed(self):
        cat = self.category_combo.currentText()
        self._populate_mod_types(cat)
        self._on_params_changed()

    def _on_freq_spin_changed(self, val: float):
        self.tuneRequested.emit(val)
        if self.is_active:
            self._on_params_changed()

    def set_center_freq_mhz(self, freq_mhz: float):
        self.cf_spin.blockSignals(True)
        self.cf_spin.setValue(freq_mhz)
        self.cf_spin.blockSignals(False)
        self.tuneRequested.emit(freq_mhz)
        if self.is_active:
            self._on_params_changed()

    def _update_trigger_btn_style(self):
        if self.is_active:
            self.trigger_btn.setText("Pause Demodulation")
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
            """)
        else:
            self.trigger_btn.setText("Demodulate Carrier")
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
            """)

    def _on_trigger_clicked(self):
        self.is_active = not self.is_active
        self._update_trigger_btn_style()
        if self.is_active:
            params = self.get_params()
            self.demodRequested.emit(params)
        else:
            self.pauseRequested.emit()

    def set_active_state(self, active: bool):
        self.is_active = active
        self._update_trigger_btn_style()

    def _on_params_changed(self):
        params = self.get_params()
        self.paramsChanged.emit(params)
        if self.is_active:
            self.demodRequested.emit(params)

    def get_params(self) -> dict:
        return {
            "center_freq_hz": self.cf_spin.value() * 1e6,
            "center_freq_mhz": self.cf_spin.value(),
            "mod_category": self.category_combo.currentText(),
            "mod_type": self.type_combo.currentText(),
            "symbol_rate": self.sym_rate_spin.value() * 1e6,
            "filter_type": self.filter_combo.currentText(),
            "filter_alpha": self.alpha_spin.value(),
            "decimate_factor": self.dec_combo.currentData(),
            "ref_level": self.ref_spin.value(),
            "preamp": self.preamp_combo.currentData(),
            "trigger_length": 16384,
            "trigger_source": 2 # Bus Trigger
        }

    def update_metrics(self, res: DemodResult):
        """Update live signal metrics display."""
        if res.is_locked:
            self.lock_badge.setText("LOCKED")
            self.lock_badge.setStyleSheet("""
                background-color: #238636;
                color: #ffffff;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 4px;
            """)
        else:
            self.lock_badge.setText("SEARCHING")
            self.lock_badge.setStyleSheet("""
                background-color: #30363d;
                color: #d29922;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 4px;
            """)

        # EVM RMS color
        if res.evm_rms_pct < 8.0:
            evm_color = "#3fb950"
        elif res.evm_rms_pct < 18.0:
            evm_color = "#d29922"
        else:
            evm_color = "#f85149"
            
        self.evm_rms_val.setText(f"{res.evm_rms_pct:.2f} %")
        self.evm_rms_val.setStyleSheet(f"color: {evm_color}; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 700;")
        
        self.evm_peak_val.setText(f"{res.evm_peak_pct:.2f} %")
        self.snr_val.setText(f"{res.snr_db:.1f} dB")
        self.freq_err_val.setText(f"{res.freq_error_hz/1e3:+.2f} kHz")
        self.carrier_pwr_val.setText(f"{res.carrier_power_dbm:.1f} dBm")
        self.obw_val.setText(f"{res.obw_hz/1e3:.1f} kHz")
