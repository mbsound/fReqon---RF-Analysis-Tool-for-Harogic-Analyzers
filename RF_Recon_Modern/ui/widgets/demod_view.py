"""
demod_view.py - Demodulation & Vector Signal Analyzer Central Viewport.
Features:
- Top: Dual live Spectrum & Waterfall views with an interactive Click-to-Demod
  channel cursor band ([fc - BW/2, fc + BW/2]) with center carrier guide.
- Bottom: 4-Quadrant Analysis Dashboard:
  1. Constellation Diagram (I/Q scatter, ideal decision points, decision grid, EVM/SNR HUD)
  2. Eye Diagram (I(t) and Q(t) folded across 2 symbol periods with zero-crossings)
  3. Modulated Signal Spectrum (Baseband FFT, 99% OBW shaded region, channel power)
  4. Bit Table & Decoded Symbols (Hex bytes, raw binary bitstream, clipboard copy)

CRITICAL PROJECT RULE: Zero synthetic data. Strictly renders real hardware IQ data.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFrame,
    QGridLayout, QTextEdit, QPushButton, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from .spectrum_view import SpectrumView
from .waterfall_view import WaterfallView
from core.demod_engine import DemodResult

class DemodView(QWidget):
    """
    Complete Demodulation & Vector Signal Analyzer Workspace Viewport.
    """
    tuneDemodRequested = pyqtSignal(float) # Center frequency in MHz

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("demodView")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)
        
        # Main Vertical Splitter: Top (RF Sweep & Waterfall) vs Bottom (Demod Dashboard)
        self.main_v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_v_splitter.setHandleWidth(3)
        self.main_v_splitter.setStyleSheet("QSplitter::handle { background-color: #30363d; }")
        
        # =========================================================================
        # TOP PANE: Live RF Spectrum & Waterfall with Click-to-Demod Cursor Band
        # =========================================================================
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        
        self.rf_splitter = QSplitter(Qt.Orientation.Vertical)
        self.rf_splitter.setHandleWidth(2)
        
        self.waterfall_view = WaterfallView(self.rf_splitter)
        self.spectrum_view = SpectrumView(self.rf_splitter)
        
        # Cross-link X axes
        self.waterfall_view.waterfall_widget.setXLink(self.spectrum_view.plot_widget)
        self.waterfall_view.channel_bar.setXLink(self.spectrum_view.plot_widget)
        self.spectrum_view.channel_bar.setXLink(self.spectrum_view.plot_widget)
        
        self.rf_splitter.addWidget(self.waterfall_view)
        self.rf_splitter.addWidget(self.spectrum_view)
        self.rf_splitter.setSizes([160, 180])
        top_layout.addWidget(self.rf_splitter)
        
        # Add Demodulation Channel Selection Band to Spectrum Plot
        self.current_center_freq_mhz = 500.0
        self.current_channel_bw_mhz = 1.25
        
        self.demod_band = pg.LinearRegionItem(
            values=[self.current_center_freq_mhz - self.current_channel_bw_mhz / 2.0,
                    self.current_center_freq_mhz + self.current_channel_bw_mhz / 2.0],
            orientation=pg.LinearRegionItem.Vertical,
            brush=pg.mkBrush(56, 189, 248, 40),
            pen=pg.mkPen('#38bdf8', width=1.5, style=Qt.PenStyle.DashLine),
            movable=True
        )
        self.demod_band.setZValue(100)
        # Override lineMoved on the demod_band so adjusting left/right boundaries resizes symmetrically around static center frequency
        self.demod_band.lineMoved = self._on_band_boundary_moved
        self.demod_band.sigRegionChanged.connect(self._on_band_dragged)
        self.spectrum_view.plot_widget.addItem(self.demod_band)
        
        # Center Line inside band
        self.demod_center_line = pg.InfiniteLine(
            pos=self.current_center_freq_mhz,
            angle=90,
            pen=pg.mkPen('#f59e0b', width=2, style=Qt.PenStyle.SolidLine),
            movable=False
        )
        self.demod_center_line.setZValue(101)
        self.spectrum_view.plot_widget.addItem(self.demod_center_line)
        
        # Click-to-Demod mouse listener on Spectrum View
        self.spectrum_view.plot_widget.scene().sigMouseClicked.connect(self._on_spectrum_clicked)
        self.waterfall_view.waterfall_widget.scene().sigMouseClicked.connect(self._on_waterfall_clicked)
        
        self.main_v_splitter.addWidget(top_container)
        
        # =========================================================================
        # BOTTOM PANE: 4-Quadrant Demodulation Analysis Dashboard
        # =========================================================================
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(2, 4, 2, 2)
        bottom_layout.setSpacing(4)
        
        # Header banner
        dash_hdr = QHBoxLayout()
        dash_hdr.setContentsMargins(4, 2, 4, 2)
        dash_title = QLabel("DEMODULATION ANALYSIS DASHBOARD")
        dash_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        dash_hdr.addWidget(dash_title)
        dash_hdr.addStretch()
        
        self.dash_status_lbl = QLabel("Mode: Hardware IQ Streaming (IQS) | Rate: -- MSPS")
        self.dash_status_lbl.setStyleSheet("color: #38bdf8; font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 600;")
        dash_hdr.addWidget(self.dash_status_lbl)
        bottom_layout.addLayout(dash_hdr)
        
        # 4-Quadrant Grid Splitters
        quad_h_splitter = QSplitter(Qt.Orientation.Horizontal)
        quad_h_splitter.setHandleWidth(3)
        quad_h_splitter.setStyleSheet("QSplitter::handle { background-color: #30363d; }")
        
        left_quad_splitter = QSplitter(Qt.Orientation.Vertical)
        left_quad_splitter.setHandleWidth(3)
        left_quad_splitter.setStyleSheet("QSplitter::handle { background-color: #30363d; }")
        
        right_quad_splitter = QSplitter(Qt.Orientation.Vertical)
        right_quad_splitter.setHandleWidth(3)
        right_quad_splitter.setStyleSheet("QSplitter::handle { background-color: #30363d; }")
        
        # 1. Quadrant: Constellation Diagram
        self.constellation_frame = self._create_plot_frame("CONSTELLATION DIAGRAM")
        self.constellation_plot = pg.PlotWidget()
        self._format_plot(self.constellation_plot, "In-Phase (I)", "Quadrature (Q)")
        self.constellation_plot.setAspectLocked(True)
        self.constellation_plot.setRange(xRange=[-2.0, 2.0], yRange=[-2.0, 2.0])
        self._eye_max_peak = 2.5
        
        # Reference Crosshairs
        self.constellation_plot.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen('#30363d', width=1)))
        self.constellation_plot.addItem(pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('#30363d', width=1)))
        
        # Ideal Symbol Points Overlay
        self.ideal_scatter = pg.ScatterPlotItem(
            size=14, pen=pg.mkPen('#f59e0b', width=1.5),
            brush=pg.mkBrush(245, 158, 11, 40), symbol='+'
        )
        self.constellation_plot.addItem(self.ideal_scatter)
        
        # Measured IQ Scatter Points
        self.meas_scatter = pg.ScatterPlotItem(
            size=6, pen=pg.mkPen(None),
            brush=pg.mkBrush(56, 189, 248, 200), symbol='o'
        )
        self.constellation_plot.addItem(self.meas_scatter)
        
        # Constellation HUD Overlay
        self.const_hud = QLabel(self.constellation_plot)
        self.const_hud.setStyleSheet("""
            background-color: rgba(13, 17, 23, 0.85);
            color: #f0f6fc;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            padding: 4px 8px;
            border: 1px solid #30363d;
            border-radius: 4px;
        """)
        self.const_hud.setText("EVM: -- % | SNR: -- dB")
        self.const_hud.move(10, 10)
        self.const_hud.show()
        
        self.constellation_frame.layout().addWidget(self.constellation_plot)
        left_quad_splitter.addWidget(self.constellation_frame)
        
        # 2. Quadrant: Modulated Signal Spectrum
        self.spectrum_frame = self._create_plot_frame("MODULATED SIGNAL SPECTRUM (BASEBAND / IF)")
        self.baseband_spec_plot = pg.PlotWidget()
        self._format_plot(self.baseband_spec_plot, "Frequency (MHz)", "Power (dBm)")
        self.baseband_spec_plot.setYRange(-110, 10)
        self.baseband_curve = self.baseband_spec_plot.plot(pen=pg.mkPen('#38bdf8', width=1.5))
        
        # OBW Region shading
        self.obw_region = pg.LinearRegionItem(
            values=[-0.5, 0.5],
            orientation=pg.LinearRegionItem.Vertical,
            brush=pg.mkBrush(16, 185, 129, 30),
            pen=pg.mkPen('#10b981', width=1, style=Qt.PenStyle.DashLine),
            movable=False
        )
        self.baseband_spec_plot.addItem(self.obw_region)
        
        self.spec_hud = QLabel(self.baseband_spec_plot)
        self.spec_hud.setStyleSheet("""
            background-color: rgba(13, 17, 23, 0.85);
            color: #10b981;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            padding: 4px 8px;
            border: 1px solid #30363d;
            border-radius: 4px;
        """)
        self.spec_hud.setText("OBW: -- kHz | Power: -- dBm")
        self.spec_hud.move(10, 10)
        self.spec_hud.show()
        
        self.spectrum_frame.layout().addWidget(self.baseband_spec_plot)
        left_quad_splitter.addWidget(self.spectrum_frame)
        
        # 3. Quadrant: Eye Diagram
        self.eye_frame = self._create_plot_frame("EYE DIAGRAM (I & Q)")
        self.eye_plot = pg.PlotWidget()
        self._format_plot(self.eye_plot, "Time (ns)", "Amplitude (V)")
        self.eye_plot.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen('#30363d', width=1, style=Qt.PenStyle.DashLine)))
        self.eye_plot.setYRange(-2.5, 2.5, padding=0.1)
        self.eye_plot.getViewBox().disableAutoRange(axis=pg.ViewBox.YAxis)
        self.eye_curves = []
        for _ in range(48):
            c_i = self.eye_plot.plot(pen=pg.mkPen(QColor(56, 189, 248, 120), width=1))
            c_q = self.eye_plot.plot(pen=pg.mkPen(QColor(236, 72, 153, 90), width=1))
            self.eye_curves.append((c_i, c_q))
            
        self.eye_frame.layout().addWidget(self.eye_plot)
        right_quad_splitter.addWidget(self.eye_frame)
        
        # 4. Quadrant: Bit Table & Decoded Symbols
        self.bit_frame = self._create_plot_frame("BIT TABLE & DEMODULATED SYMBOLS")
        bit_inner = QWidget()
        bit_layout = QVBoxLayout(bit_inner)
        bit_layout.setContentsMargins(4, 4, 4, 4)
        bit_layout.setSpacing(4)
        
        # Toolbar with Copy and Stats
        bit_bar = QHBoxLayout()
        self.bit_stats_lbl = QLabel("Decoded: 0 bits | Scheme: QPSK")
        self.bit_stats_lbl.setStyleSheet("color: #8b949e; font-size: 10px; font-family: 'JetBrains Mono', monospace;")
        bit_bar.addWidget(self.bit_stats_lbl)
        bit_bar.addStretch()
        
        copy_hex_btn = QPushButton("Copy Hex")
        copy_hex_btn.setObjectName("pillBtn")
        copy_hex_btn.setFixedHeight(22)
        copy_hex_btn.clicked.connect(self._copy_hex_to_clipboard)
        bit_bar.addWidget(copy_hex_btn)
        
        copy_bits_btn = QPushButton("Copy Bits")
        copy_bits_btn.setObjectName("pillBtn")
        copy_bits_btn.setFixedHeight(22)
        copy_bits_btn.clicked.connect(self._copy_bits_to_clipboard)
        bit_bar.addWidget(copy_bits_btn)
        bit_layout.addLayout(bit_bar)
        
        # Text display for hex bytes and bit table
        self.bit_text = QTextEdit()
        self.bit_text.setReadOnly(True)
        self.bit_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
                font-size: 11px;
                padding: 6px;
                line-height: 1.4;
            }
        """)
        self.bit_text.setPlaceholderText("Demodulated bitstream and hexadecimal table will stream here...")
        bit_layout.addWidget(self.bit_text)
        
        self.bit_frame.layout().addWidget(bit_inner)
        right_quad_splitter.addWidget(self.bit_frame)
        
        quad_h_splitter.addWidget(left_quad_splitter)
        quad_h_splitter.addWidget(right_quad_splitter)
        quad_h_splitter.setSizes([450, 450])
        bottom_layout.addWidget(quad_h_splitter)
        
        self.main_v_splitter.addWidget(bottom_container)
        self.main_v_splitter.setSizes([340, 360])
        main_layout.addWidget(self.main_v_splitter)

    def _create_plot_frame(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("quadFrame")
        frame.setStyleSheet("""
            QFrame#quadFrame {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
            }
        """)
        l = QVBoxLayout(frame)
        l.setContentsMargins(6, 6, 6, 6)
        l.setSpacing(4)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        l.addWidget(lbl)
        return frame

    def _format_plot(self, plot: pg.PlotWidget, x_lbl: str, y_lbl: str):
        plot.setBackground('#0d1117')
        plot.showGrid(x=True, y=True, alpha=0.25)
        styles = {'color': '#8b949e', 'font-size': '10px'}
        plot.setLabel('bottom', x_lbl, **styles)
        plot.setLabel('left', y_lbl, **styles)
        for axis in ['bottom', 'left']:
            ax = plot.getAxis(axis)
            ax.setPen(pg.mkPen('#30363d'))
            ax.setTextPen(pg.mkPen('#8b949e'))

    def update_sweep_data(self, freq: np.ndarray, power: np.ndarray):
        """Update the top Spectrum and Waterfall views with live RF sweep data."""
        if len(freq) > 0 and len(power) > 0:
            x_mhz = freq / 1e6
            self.spectrum_view.update_curve_data("Real-Time", x_mhz, power)
            self.waterfall_view.update_waterfall(power, x_mhz[0], x_mhz[-1])

    def set_channel_params(self, center_freq_mhz: float, channel_bw_mhz: float):
        """Update the interactive selection band position and bandwidth."""
        self.current_center_freq_mhz = center_freq_mhz
        self.current_channel_bw_mhz = channel_bw_mhz
        self.demod_band.blockSignals(True)
        self.demod_band.setRegion([
            center_freq_mhz - channel_bw_mhz / 2.0,
            center_freq_mhz + channel_bw_mhz / 2.0
        ])
        self.demod_band.blockSignals(False)
        self.demod_center_line.setValue(center_freq_mhz)

    def _on_band_boundary_moved(self, line_idx: int):
        """
        Adjust mask bandwidth symmetrically around the static center carrier frequency.
        Dragging left or right boundary widens or narrows the channel without moving fc.
        """
        val = self.demod_band.lines[line_idx].value()
        half_bw = max(0.02, abs(val - self.current_center_freq_mhz))
        self.current_channel_bw_mhz = half_bw * 2.0
        
        self.demod_band.blockLineSignal = True
        self.demod_band.lines[0].setValue(self.current_center_freq_mhz - half_bw)
        self.demod_band.lines[1].setValue(self.current_center_freq_mhz + half_bw)
        self.demod_band.blockLineSignal = False
        self.demod_band.prepareGeometryChange()
        self.demod_band.sigRegionChanged.emit(self.demod_band)

    def _on_band_dragged(self):
        # If moving by body drag (neither boundary line is independently being dragged)
        if not (self.demod_band.lines[0].moving or self.demod_band.lines[1].moving):
            low, high = self.demod_band.getRegion()
            c_freq = (low + high) / 2.0
            self.current_center_freq_mhz = c_freq
            self.demod_center_line.setValue(c_freq)
            self.tuneDemodRequested.emit(c_freq)
        else:
            self.demod_center_line.setValue(self.current_center_freq_mhz)

    def _on_spectrum_clicked(self, event):
        """Single-click on the spectrum view instantly places the demodulation band."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            vb = self.spectrum_view.plot_widget.getViewBox()
            if vb.sceneBoundingRect().contains(pos):
                mouse_point = vb.mapSceneToView(pos)
                freq_mhz = float(mouse_point.x())
                self.set_channel_params(freq_mhz, self.current_channel_bw_mhz)
                self.tuneDemodRequested.emit(freq_mhz)

    def _on_waterfall_clicked(self, event):
        """Single-click on the waterfall view instantly places the demodulation band."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.scenePos()
            vb = self.waterfall_view.waterfall_widget.getViewBox()
            if vb.sceneBoundingRect().contains(pos):
                mouse_point = vb.mapSceneToView(pos)
                freq_mhz = float(mouse_point.x())
                self.set_channel_params(freq_mhz, self.current_channel_bw_mhz)
                self.tuneDemodRequested.emit(freq_mhz)

    def update_demod_results(self, res: DemodResult):
        """Render new physical DSP demodulation packet across all 4 quadrants."""
        # Update Dashboard Status
        self.dash_status_lbl.setText(
            f"Scheme: {res.mod_type} | SymRate: {res.symbol_rate/1e6:.3f} MBd | SampleRate: {res.sample_rate/1e6:.2f} MSPS"
        )
        
        # 1. Constellation
        if len(res.ideal_symbols) > 0:
            self.ideal_scatter.setData(
                x=np.real(res.ideal_symbols),
                y=np.imag(res.ideal_symbols)
            )
        if len(res.i_meas) > 0:
            # Downsample scatter if massive
            step = max(1, len(res.i_meas) // 1024)
            i_sub = res.i_meas[::step]
            q_sub = res.q_meas[::step]
            self.meas_scatter.setData(x=i_sub, y=q_sub)
            
        evm_col = "#3fb950" if res.evm_rms_pct < 8.0 else ("#d29922" if res.evm_rms_pct < 18.0 else "#f85149")
        self.const_hud.setText(
            f"EVM: <span style='color:{evm_col}; font-weight:700;'>{res.evm_rms_pct:.2f}%</span> | "
            f"Peak: {res.evm_peak_pct:.1f}% | SNR: {res.snr_db:.1f} dB"
        )
        
        # 2. Modulated Spectrum
        if len(res.spectrum_freq_mhz) > 0:
            self.baseband_curve.setData(res.spectrum_freq_mhz, res.spectrum_power_db)
            if res.obw_hz > 0:
                half_obw_mhz = (res.obw_hz / 2.0) / 1e6
                self.obw_region.setRegion([-half_obw_mhz, half_obw_mhz])
            self.spec_hud.setText(f"OBW: {res.obw_hz/1e3:.1f} kHz | Power: {res.channel_power_dbm:.1f} dBm")
            
        # 3. Eye Diagram
        if len(res.eye_time_ns) > 0 and len(res.eye_i_traces) > 0:
            n_curves = min(len(self.eye_curves), len(res.eye_i_traces))
            for idx in range(n_curves):
                c_i, c_q = self.eye_curves[idx]
                c_i.setData(res.eye_time_ns, res.eye_i_traces[idx])
                c_q.setData(res.eye_time_ns, res.eye_q_traces[idx])
            self.eye_plot.setXRange(res.eye_time_ns[0], res.eye_time_ns[-1])
            
            # Maintain a static, stable Y-axis view range with generous headroom
            max_i = float(np.max(np.abs(res.eye_i_traces))) if len(res.eye_i_traces) > 0 else 1.0
            max_q = float(np.max(np.abs(res.eye_q_traces))) if len(res.eye_q_traces) > 0 else 1.0
            curr_peak = max(max_i, max_q, 1.0)
            
            # Fast attack on large peaks, slow decay to keep scale calm and stable
            if curr_peak > self._eye_max_peak:
                self._eye_max_peak = curr_peak
            else:
                self._eye_max_peak = max(2.5, self._eye_max_peak * 0.98 + curr_peak * 0.02)
                
            y_limit = self._eye_max_peak * 1.25
            self.eye_plot.setYRange(-y_limit, y_limit, padding=0.0)
            
        # 4. Bit Table & Decoded Symbols
        if res.hex_stream:
            self.bit_stats_lbl.setText(
                f"Decoded: {len(res.bits)} bits ({len(res.symbols)} symbols) | Scheme: {res.mod_type}"
            )
            
            # Format hex table with byte offsets
            hex_parts = res.hex_stream.split()
            lines = []
            lines.append("HEX DUMP:")
            for i in range(0, len(hex_parts), 16):
                chunk = hex_parts[i:i+16]
                offset_str = f"0x{i:04X}:"
                hex_row = " ".join(chunk[:8]) + "  " + " ".join(chunk[8:])
                lines.append(f"{offset_str:<8} {hex_row}")
                
            lines.append("\nBINARY STREAM:")
            # 32 bits per line
            for b_i in range(0, min(256, len(res.bits)), 32):
                b_chunk = res.bits[b_i:b_i+32]
                grouped = " ".join([b_chunk[k:k+8] for k in range(0, len(b_chunk), 8)])
                lines.append(f"{b_i:04d}: {grouped}")
                
            self.bit_text.setPlainText("\n".join(lines))

    def _copy_hex_to_clipboard(self):
        txt = self.bit_text.toPlainText()
        if txt:
            QApplication.clipboard().setText(txt)

    def _copy_bits_to_clipboard(self):
        txt = self.bit_text.toPlainText()
        if "BINARY STREAM:" in txt:
            b_part = txt.split("BINARY STREAM:")[-1].strip()
            QApplication.clipboard().setText(b_part)
        else:
            QApplication.clipboard().setText(txt)
