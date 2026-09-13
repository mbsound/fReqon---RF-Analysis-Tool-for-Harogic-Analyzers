"""
audio_demod_dialog.py - Live Analog AM/FM Audio Demodulation & Acoustic Monitor Dialog.
Provides real-time listening for wireless microphones, broadcast FM, and analog comms,
with interactive audio oscilloscope and audio FFT spectrum visualization.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QFrame, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from ..widgets.freq_inputs import FreqSpinBox
from core.audio_demodulator import AudioDemodulator

class AudioDemodDialog(QDialog):
    """
    Live Analog Audio Monitor & Demodulation Workstation.
    """
    listenStarted = pyqtSignal(float, str)  # freq_hz, mode
    listenStopped = pyqtSignal()
    retuneRequested = pyqtSignal(float)     # freq_hz

    def __init__(self, initial_freq_hz: float = 500e6, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Live Analog Audio Monitor & Demodulator")
        self.resize(560, 420)
        self.setModal(False)
        
        self.demodulator = AudioDemodulator(sample_rate=48000, parent=self)
        self.demodulator.audio_frame_ready.connect(self._on_audio_frame)
        self.demodulator.status_changed.connect(self._on_status_changed)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)
        
        # 1. Tuning & Demod Mode Card
        ctrl_card = QFrame()
        ctrl_card.setObjectName("cardFrame")
        ctrl_card.setStyleSheet("""
            QFrame#cardFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setSpacing(8)
        
        row1 = QHBoxLayout()
        cf_lbl = QLabel("Tuned Frequency:")
        cf_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        self.cf_spin = FreqSpinBox()
        self.cf_spin.setRange(1.0, 6000.0)
        self.cf_spin.setValue(initial_freq_hz / 1e6)
        self.cf_spin.valueChanged.connect(self._on_freq_changed)
        row1.addWidget(cf_lbl)
        row1.addWidget(self.cf_spin)
        
        mode_lbl = QLabel("Demod Mode:")
        mode_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("FM Wide (Wireless Mic / Broadcast)", "FM_WIDE")
        self.mode_combo.addItem("FM Narrow (Comms / NFM)", "FM_NARROW")
        self.mode_combo.addItem("AM (Aviation / Comms)", "AM")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        row1.addWidget(mode_lbl)
        row1.addWidget(self.mode_combo)
        ctrl_layout.addLayout(row1)
        
        # Volume & Transport Row
        row2 = QHBoxLayout()
        vol_lbl = QLabel("Volume:")
        vol_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.valueChanged.connect(lambda v: self.demodulator.set_volume(v / 100.0))
        row2.addWidget(vol_lbl)
        row2.addWidget(self.vol_slider)
        
        self.listen_btn = QPushButton("Start Listen")
        self.listen_btn.setObjectName("primaryActionBtn")
        self.listen_btn.setCheckable(True)
        self.listen_btn.setFixedHeight(26)
        self.listen_btn.clicked.connect(self._on_listen_toggled)
        row2.addWidget(self.listen_btn)
        ctrl_layout.addLayout(row2)
        
        main_layout.addWidget(ctrl_card)
        
        # 2. Real-Time Audio Visualizer (Waveform + Audio FFT)
        plot_frame = QFrame()
        plot_frame.setObjectName("cardFrame")
        plot_frame.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 4px;")
        plot_layout = QVBoxLayout(plot_frame)
        plot_layout.setContentsMargins(4, 4, 4, 4)
        
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground('#0d1117')
        plot_layout.addWidget(self.glw)
        
        # Audio Waveform Scope (Top)
        self.wave_plot = self.glw.addPlot(title="Audio Waveform (Time Domain)")
        self.wave_plot.showGrid(x=True, y=True, alpha=0.15)
        self.wave_plot.setYRange(-1.0, 1.0)
        self.wave_curve = self.wave_plot.plot(pen=pg.mkPen(color='#38bdf8', width=1.5))
        
        self.glw.nextRow()
        
        # Audio Spectrum (Bottom)
        self.fft_plot = self.glw.addPlot(title="Audio Spectrum (0 - 15 kHz)")
        self.fft_plot.showGrid(x=True, y=True, alpha=0.15)
        self.fft_plot.setYRange(-40.0, 40.0)
        self.fft_curve = self.fft_plot.plot(pen=pg.mkPen(color='#10b981', width=1.5))
        
        main_layout.addWidget(plot_frame)
        
        # Status Bar
        self.status_lbl = QLabel("Ready to demodulate analog RF audio.")
        self.status_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
        main_layout.addWidget(self.status_lbl)

    def _on_mode_changed(self):
        mode_data = self.mode_combo.currentData()
        self.demodulator.set_demod_mode(mode_data)

    def _on_freq_changed(self, val: float):
        if self.listen_btn.isChecked():
            self.retuneRequested.emit(val * 1e6)

    def _on_listen_toggled(self, checked: bool):
        if checked:
            self.listen_btn.setText("Mute / Stop")
            self.listen_btn.setStyleSheet("background-color: #f43f5e; color: #ffffff; font-weight: 700;")
            self.demodulator.start_playback()
            self.listenStarted.emit(self.cf_spin.value() * 1e6, self.mode_combo.currentData())
        else:
            self.listen_btn.setText("Start Listen")
            self.listen_btn.setStyleSheet("")
            self.demodulator.stop_playback()
            self.listenStopped.emit()

    def _on_audio_frame(self, wave: np.ndarray, fft_db: np.ndarray, carrier_offset: float):
        self.wave_curve.setData(wave)
        freq_axis = np.linspace(0, 15000, len(fft_db))
        self.fft_curve.setData(freq_axis, fft_db)
        if abs(carrier_offset) > 0:
            self.status_lbl.setText(f"Demodulating @ {self.cf_spin.value():.3f} MHz (Carrier Offset: {carrier_offset/1e3:+.2f} kHz)")

    def _on_status_changed(self, msg: str):
        self.status_lbl.setText(msg)

    def closeEvent(self, event):
        if self.listen_btn.isChecked():
            self.listenStopped.emit()
        self.demodulator.stop_playback()
        super().closeEvent(event)
