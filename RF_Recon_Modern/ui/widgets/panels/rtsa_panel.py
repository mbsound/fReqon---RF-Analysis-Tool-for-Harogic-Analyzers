"""
rtsa_panel.py - Real-Time Spectrum Analysis (RTSA) Parameter Control Panel.
Provides precision controls for Center Frequency, Decimation / Real-time Span,
Reference Level, Attenuation, Pre-Amplifier, Persistence Decay, and Trigger Source.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QSpinBox, QSlider, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..freq_inputs import FreqSpinBox
from core.constants import PREAMP_OPTIONS

class RTSAPanel(QWidget):
    """
    RTSA Hardware Parameters & Persistence Control Drawer Panel.
    """
    paramsChanged = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("rtsaPanel")
        
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
        
        # 1. Real-Time RF Tuning Card
        rf_card, rf_layout = self._create_card("REAL-TIME RF TUNING")
        
        cf_row = QHBoxLayout()
        cf_lbl = QLabel("Center Freq:")
        cf_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.cf_spin = FreqSpinBox()
        self.cf_spin.setRange(1.0, 6000.0)
        self.cf_spin.setValue(539.0) # Default UHF center
        cf_row.addWidget(cf_lbl)
        cf_row.addWidget(self.cf_spin)
        rf_layout.addLayout(cf_row)
        
        dec_row = QHBoxLayout()
        dec_lbl = QLabel("Decimation:")
        dec_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.dec_combo = QComboBox()
        self.dec_combo.addItem("1 (Full RT Bandwidth)", 1)
        self.dec_combo.addItem("2 (1/2 Bandwidth)", 2)
        self.dec_combo.addItem("4 (1/4 Bandwidth)", 4)
        self.dec_combo.addItem("8 (1/8 Bandwidth)", 8)
        self.dec_combo.addItem("16 (High Resolution)", 16)
        dec_row.addWidget(dec_lbl)
        dec_row.addWidget(self.dec_combo)
        rf_layout.addLayout(dec_row)
        
        layout.addWidget(rf_card)
        
        # 2. Amplitude & Gain Card
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
        for label, val in PREAMP_OPTIONS:
            self.preamp_combo.addItem(label, val)
        preamp_row.addWidget(preamp_lbl)
        preamp_row.addWidget(self.preamp_combo)
        gain_layout.addLayout(preamp_row)
        
        layout.addWidget(gain_card)
        
        # 3. Persistence & Density Display Card
        pers_card, pers_layout = self._create_card("PERSISTENCE & DECAY")
        
        decay_hdr = QHBoxLayout()
        decay_lbl = QLabel("Decay Speed:")
        decay_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.decay_val_lbl = QLabel("90%")
        self.decay_val_lbl.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 700;")
        decay_hdr.addWidget(decay_lbl)
        decay_hdr.addStretch()
        decay_hdr.addWidget(self.decay_val_lbl)
        pers_layout.addLayout(decay_hdr)
        
        self.decay_slider = QSlider(Qt.Orientation.Horizontal)
        self.decay_slider.setRange(50, 99)
        self.decay_slider.setValue(90)
        self.decay_slider.valueChanged.connect(lambda v: self.decay_val_lbl.setText(f"{v}%"))
        pers_layout.addWidget(self.decay_slider)
        
        layout.addWidget(pers_card)
        
        # 4. Trigger Configuration Card
        trig_card, trig_layout = self._create_card("REAL-TIME TRIGGER")
        
        tsrc_row = QHBoxLayout()
        tsrc_lbl = QLabel("Source:")
        tsrc_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.trig_source_combo = QComboBox()
        self.trig_source_combo.addItem("Internal Bus FreeRun", 2) # Bus trigger
        self.trig_source_combo.addItem("Level Trigger", 3)
        self.trig_source_combo.addItem("External Trigger", 1)
        tsrc_row.addWidget(tsrc_lbl)
        tsrc_row.addWidget(self.trig_source_combo)
        trig_layout.addLayout(tsrc_row)
        
        tmode_row = QHBoxLayout()
        tmode_lbl = QLabel("Mode:")
        tmode_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.trig_mode_combo = QComboBox()
        self.trig_mode_combo.addItem("Fixed Points (100% POI)", 0)
        self.trig_mode_combo.addItem("Continuous Adaptive", 1)
        tmode_row.addWidget(tmode_lbl)
        tmode_row.addWidget(self.trig_mode_combo)
        trig_layout.addLayout(tmode_row)
        
        layout.addWidget(trig_card)
        
        # Apply Action Button
        self.apply_btn = QPushButton("Apply RTSA Parameters")
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

    def _on_apply_clicked(self):
        params = self.get_params()
        self.paramsChanged.emit(params)

    def get_params(self) -> dict:
        return {
            "center_freq_hz": self.cf_spin.value() * 1e6,
            "decimate_factor": self.dec_combo.currentData(),
            "ref_level": self.ref_spin.value(),
            "atten": self.att_combo.currentData(),
            "preamp": self.preamp_combo.currentData(),
            "decay": self.decay_slider.value() / 100.0,
            "trigger_source": self.trig_source_combo.currentData(),
            "trigger_mode": self.trig_mode_combo.currentData(),
            "trigger_time": 0.05
        }
