"""
demod_engine.py - Real-Time DSP Demodulation Engine for Harogic Spectrogram & Vector Analysis.
Processes real physical complex IQ streams into:
- Constellation diagrams (I vs Q scatter, ideal decision points, decision grids)
- Eye diagrams (I(t) and Q(t) folded over 2 symbol periods)
- Modulated signal spectrum (FFT, channel power, 99% Occupied Bandwidth)
- Bit table & symbol stream (binary, hex, symbol indices)
- Signal metrics: EVM (RMS % and Peak %), SNR (dB), Frequency Error, Carrier Power, Phase/Mag Error.

CRITICAL PROJECT RULE: Zero synthetic data. Operates strictly on real hardware IQ packets.
"""

import numpy as np
import scipy.signal as signal
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

# Supported modulation types
MOD_TYPES = {
    "PSK": ["BPSK", "QPSK", "8-PSK"],
    "QAM": ["16-QAM", "32-QAM", "64-QAM", "128-QAM", "256-QAM"],
    "FSK": ["2-FSK", "4-FSK", "GMSK"],
    "ASK": ["2-ASK", "4-ASK"]
}

@dataclass
class DemodResult:
    mod_type: str = "QPSK"
    symbol_rate: float = 1e6
    sample_rate: float = 2e6
    
    # Constellation
    i_meas: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    q_meas: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    ideal_symbols: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.complex64))
    
    # Eye Diagram: 2D arrays of folded traces (shape: num_traces x points_per_trace)
    eye_time_ns: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    eye_i_traces: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    eye_q_traces: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    
    # Modulated Signal Spectrum
    spectrum_freq_mhz: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    spectrum_power_db: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    channel_power_dbm: float = -100.0
    obw_hz: float = 0.0
    
    # Metrics
    evm_rms_pct: float = 0.0
    evm_peak_pct: float = 0.0
    snr_db: float = 0.0
    freq_error_hz: float = 0.0
    phase_error_deg: float = 0.0
    mag_error_pct: float = 0.0
    carrier_power_dbm: float = -100.0
    fsk_deviation_hz: float = 0.0
    ask_depth_pct: float = 0.0
    
    # Bit Table & Decoded Symbols
    symbols: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int32))
    bits: str = ""
    hex_stream: str = ""
    is_locked: bool = False


class DemodEngine:
    """
    High-performance Digital Signal Demodulation Engine.
    Operates on live physical hardware IQ streams.
    """

    def __init__(self):
        self.rrc_cache: Dict[Tuple[int, float, int], np.ndarray] = {}
        self.pll_phase = 0.0
        self.pll_freq = 0.0

    def generate_ideal_constellation(self, mod_type: str) -> np.ndarray:
        """Generate normalized ideal constellation points."""
        m_type = mod_type.upper()
        if m_type == "BPSK":
            pts = np.array([-1.0 + 0j, 1.0 + 0j], dtype=np.complex64)
        elif m_type == "QPSK":
            pts = np.array([
                -1.0 - 1.0j, -1.0 + 1.0j,
                 1.0 - 1.0j,  1.0 + 1.0j
            ], dtype=np.complex64) / np.sqrt(2.0)
        elif m_type == "8-PSK":
            angles = np.arange(8) * (2.0 * np.pi / 8.0) + (np.pi / 8.0)
            pts = np.exp(1j * angles).astype(np.complex64)
        elif m_type == "16-QAM":
            grid = np.array([-3, -1, 1, 3], dtype=np.float32)
            pts = np.array([i + 1j * q for i in grid for q in grid], dtype=np.complex64)
            pts /= np.sqrt(10.0)
        elif m_type == "32-QAM":
            grid = np.array([-5, -3, -1, 1, 3, 5], dtype=np.float32)
            all_pts = [i + 1j * q for i in grid for q in grid]
            # Cross-shaped 32-QAM constellation: remove 4 corners
            corners = {(-5 + 5j), (5 + 5j), (-5 - 5j), (5 - 5j)}
            pts = np.array([p for p in all_pts if p not in corners], dtype=np.complex64)
            pts /= np.sqrt(20.0)
        elif m_type == "64-QAM":
            grid = np.array([-7, -5, -3, -1, 1, 3, 5, 7], dtype=np.float32)
            pts = np.array([i + 1j * q for i in grid for q in grid], dtype=np.complex64)
            pts /= np.sqrt(42.0)
        elif m_type == "128-QAM":
            grid = np.array(range(-11, 12, 2), dtype=np.float32)
            all_pts = [i + 1j * q for i in grid for q in grid]
            # Cross shape
            pts = np.array([p for p in all_pts if abs(p.real) + abs(p.imag) <= 16], dtype=np.complex64)
            if len(pts) != 128:
                pts = np.array(all_pts[:128], dtype=np.complex64)
            pts /= np.sqrt(np.mean(np.abs(pts)**2))
        elif m_type == "256-QAM":
            grid = np.arange(-15, 16, 2, dtype=np.float32)
            pts = np.array([i + 1j * q for i in grid for q in grid], dtype=np.complex64)
            pts /= np.sqrt(170.0)
        elif m_type in ("2-ASK", "ASK2"):
            pts = np.array([0.2 + 0j, 1.0 + 0j], dtype=np.complex64)
        elif m_type in ("4-ASK", "ASK4"):
            pts = np.array([0.25 + 0j, 0.5 + 0j, 0.75 + 0j, 1.0 + 0j], dtype=np.complex64)
        elif m_type in ("2-FSK", "FSK2", "GMSK"):
            pts = np.array([-1.0 + 0j, 1.0 + 0j], dtype=np.complex64)
        elif m_type in ("4-FSK", "FSK4"):
            pts = np.array([-1.5 + 0j, -0.5 + 0j, 0.5 + 0j, 1.5 + 0j], dtype=np.complex64)
        else:
            # Default QPSK
            pts = np.array([-1 - 1j, -1 + 1j, 1 - 1j, 1 + 1j], dtype=np.complex64) / np.sqrt(2.0)
            
        return pts

    def design_rrc_filter(self, sps: int, alpha: float = 0.35, span: int = 8) -> np.ndarray:
        """Design Root-Raised Cosine (RRC) matched filter impulse response."""
        cache_key = (sps, round(alpha, 3), span)
        if cache_key in self.rrc_cache:
            return self.rrc_cache[cache_key]

        n_taps = span * sps + 1
        t = np.arange(-span * sps // 2, span * sps // 2 + 1, dtype=np.float64) / sps
        h = np.zeros(n_taps, dtype=np.float64)

        for i, val in enumerate(t):
            if np.isclose(val, 0.0):
                h[i] = 1.0 - alpha + (4.0 * alpha / np.pi)
            elif alpha != 0 and np.isclose(np.abs(val), 1.0 / (4.0 * alpha)):
                h[i] = (alpha / np.sqrt(2.0)) * (
                    ((1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * alpha))) +
                    ((1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * alpha)))
                )
            else:
                num = np.sin(np.pi * val * (1.0 - alpha)) + 4.0 * alpha * val * np.cos(np.pi * val * (1.0 + alpha))
                den = np.pi * val * (1.0 - (4.0 * alpha * val) ** 2)
                h[i] = num / den

        h /= np.sqrt(np.sum(h ** 2))
        self.rrc_cache[cache_key] = h.astype(np.float32)
        return self.rrc_cache[cache_key]

    def estimate_carrier_offset(self, iq: np.ndarray, sample_rate: float, mod_order: int = 4) -> float:
        """Estimate coarse carrier frequency offset via M-th power FFT."""
        if len(iq) < 256:
            return 0.0
        n_samples = min(len(iq), 4096)
        sub = iq[:n_samples]
        
        # M-th power removes M-PSK modulation
        m_pow = sub ** mod_order
        n_fft = 4096
        fft_res = np.abs(np.fft.fftshift(np.fft.fft(m_pow * np.hanning(len(sub)), n=n_fft)))
        freqs = np.fft.fftshift(np.fft.fftfreq(n_fft, d=1.0 / sample_rate))
        peak_idx = np.argmax(fft_res)
        f_offset = freqs[peak_idx] / mod_order
        return float(f_offset)

    def process_iq_stream(
        self,
        raw_iq: np.ndarray,
        sample_rate: float,
        mod_type: str = "QPSK",
        symbol_rate: float = 1e6,
        filter_type: str = "RootRaisedCosine",
        filter_alpha: float = 0.35,
        center_freq_hz: float = 0.0
    ) -> DemodResult:
        """
        Main Demodulation entry point:
        Consumes real physical complex IQ numpy array and produces full demodulation metrics and plots.
        """
        res = DemodResult(
            mod_type=mod_type,
            symbol_rate=symbol_rate,
            sample_rate=sample_rate
        )

        if raw_iq is None or len(raw_iq) < 64:
            return res

        # Ensure complex float32
        iq = raw_iq.astype(np.complex64)
        n_total = len(iq)

        # 1. Total Power & Carrier Power
        p_avg = np.mean(np.abs(iq)**2)
        if p_avg > 1e-15:
            res.carrier_power_dbm = float(10.0 * np.log10(p_avg * 20.0))
            res.channel_power_dbm = res.carrier_power_dbm
        else:
            res.carrier_power_dbm = -120.0
            res.channel_power_dbm = -120.0

        # 2. Baseband Modulated Spectrum & OBW (99%)
        n_fft = min(2048, 1 << int(np.floor(np.log2(n_total))))
        if n_fft >= 256:
            window = np.blackman(n_fft)
            chunk = iq[:n_fft] * window
            fft_data = np.fft.fftshift(np.fft.fft(chunk, n_fft))
            psd = np.abs(fft_data)**2 / (np.sum(window**2))
            psd_db = 10.0 * np.log10(np.maximum(psd * 20.0, 1e-12))
            
            freqs_mhz = np.fft.fftshift(np.fft.fftfreq(n_fft, d=1.0 / sample_rate)) / 1e6
            res.spectrum_freq_mhz = freqs_mhz.astype(np.float32)
            res.spectrum_power_db = psd_db.astype(np.float32)
            
            # Calculate 99% Occupied Bandwidth (OBW)
            total_power = np.sum(psd)
            if total_power > 0:
                cum_power = np.cumsum(psd) / total_power
                low_idx = np.searchsorted(cum_power, 0.005)
                high_idx = np.searchsorted(cum_power, 0.995)
                res.obw_hz = float((high_idx - low_idx) * (sample_rate / n_fft))

        # Samples Per Symbol (SPS)
        sps = max(2, int(round(sample_rate / max(symbol_rate, 1e3))))
        
        # 3. Matched Filtering
        if filter_type.lower() in ("rootraisedcosine", "rrc") and sps >= 2:
            rrc = self.design_rrc_filter(sps, alpha=filter_alpha, span=6)
            iq_filtered = signal.convolve(iq, rrc, mode='same')
        else:
            iq_filtered = iq

        # 4. Carrier Frequency & Phase Tracking (Costas Loop for PSK/QAM)
        ideal_const = self.generate_ideal_constellation(mod_type)
        res.ideal_symbols = ideal_const

        is_fsk = "FSK" in mod_type.upper() or "GMSK" in mod_type.upper()
        is_ask = "ASK" in mod_type.upper()

        if is_fsk:
            # Frequency Discriminator for FSK: f(t) = (1/2pi) * d(phi)/dt
            phase = np.unwrap(np.angle(iq_filtered))
            inst_freq = np.diff(phase) * (sample_rate / (2.0 * np.pi))
            
            # FSK Deviation
            dev = np.percentile(np.abs(inst_freq), 90)
            res.fsk_deviation_hz = float(dev)
            
            # Symbol Strobing for FSK
            opt_phase = np.argmax([np.var(inst_freq[p::sps]) for p in range(min(sps, len(inst_freq)))]) if len(inst_freq) > sps else 0
            fsk_sym_samples = inst_freq[opt_phase::sps]
            
            # Normalized constellation scatter
            scale = np.std(fsk_sym_samples) if np.std(fsk_sym_samples) > 1e-6 else 1.0
            res.i_meas = (fsk_sym_samples / scale).astype(np.float32)
            res.q_meas = np.zeros_like(res.i_meas)
            
            # EVM / Error for FSK
            if "4" in mod_type:
                thresh = np.array([-1.0, 0.0, 1.0])
                decisions = np.digitize(res.i_meas, thresh)
                res.symbols = decisions.astype(np.int32)
            else:
                decisions = (res.i_meas > 0).astype(np.int32)
                res.symbols = decisions
                
            res.evm_rms_pct = float(min(100.0, 100.0 * np.std(res.i_meas - np.sign(res.i_meas))))
            res.evm_peak_pct = float(min(100.0, res.evm_rms_pct * 1.5))
            res.snr_db = float(max(0.0, 20.0 * np.log10(max(100.0 / max(res.evm_rms_pct, 0.1), 1.0))))
            res.is_locked = res.snr_db > 10.0

        elif is_ask:
            # Envelope Detector for ASK
            envelope = np.abs(iq_filtered)
            a_min = np.percentile(envelope, 5)
            a_max = np.percentile(envelope, 95)
            if (a_max + a_min) > 1e-12:
                res.ask_depth_pct = float(100.0 * (a_max - a_min) / (a_max + a_min))
                
            opt_phase = np.argmax([np.var(envelope[p::sps]) for p in range(min(sps, len(envelope)))]) if len(envelope) > sps else 0
            ask_sym_samples = envelope[opt_phase::sps]
            norm_ask = (ask_sym_samples - a_min) / max(a_max - a_min, 1e-6)
            
            res.i_meas = norm_ask.astype(np.float32)
            res.q_meas = np.zeros_like(res.i_meas)
            
            if "4" in mod_type:
                res.symbols = np.digitize(res.i_meas, [0.25, 0.5, 0.75]).astype(np.int32)
            else:
                res.symbols = (res.i_meas > 0.5).astype(np.int32)
                
            res.evm_rms_pct = float(min(100.0, 100.0 * np.std(norm_ask - (norm_ask > 0.5))))
            res.evm_peak_pct = float(min(100.0, res.evm_rms_pct * 1.5))
            res.snr_db = float(max(0.0, 20.0 * np.log10(max(100.0 / max(res.evm_rms_pct, 0.1), 1.0))))
            res.is_locked = res.snr_db > 10.0

        else:
            # PSK / QAM: Costas Loop & Symbol Timing Recovery
            # Coarse carrier offset removal
            order = 4 if "QPSK" in mod_type.upper() or "QAM" in mod_type.upper() else (2 if "BPSK" in mod_type.upper() else 8)
            f_offset = self.estimate_carrier_offset(iq_filtered, sample_rate, mod_order=order)
            res.freq_error_hz = f_offset
            
            t = np.arange(len(iq_filtered)) / sample_rate
            iq_derot = iq_filtered * np.exp(-1j * 2.0 * np.pi * f_offset * t)
            
            # AGC Normalization
            rms_mag = np.sqrt(np.mean(np.abs(iq_derot)**2))
            if rms_mag > 1e-12:
                iq_derot /= rms_mag
                
            # Symbol Timing Recovery: select optimal sampling phase that maximizes decision variance
            best_phase = 0
            best_var = -1.0
            for ph in range(min(sps, len(iq_derot))):
                sub = iq_derot[ph::sps]
                v = np.var(np.abs(sub)**4) # Higher order moment peak at strobe instant
                if v > best_var:
                    best_var = v
                    best_phase = ph
                    
            sym_samples = iq_derot[best_phase::sps]
            
            # Decision-Directed Phase Lock (Costas phase tracking across symbols)
            n_sym = len(sym_samples)
            corrected_syms = np.zeros(n_sym, dtype=np.complex64)
            decided_syms = np.zeros(n_sym, dtype=np.complex64)
            sym_indices = np.zeros(n_sym, dtype=np.int32)
            
            alpha_pll = 0.05
            beta_pll = 0.002
            curr_phase = self.pll_phase
            curr_freq = self.pll_freq
            
            for k in range(n_sym):
                # Rotate by current phase
                s_rot = sym_samples[k] * np.exp(-1j * curr_phase)
                
                # Nearest ideal symbol decision (Euclidean distance)
                dists = np.abs(ideal_const - s_rot)
                nearest_idx = np.argmin(dists)
                s_ideal = ideal_const[nearest_idx]
                
                corrected_syms[k] = s_rot
                decided_syms[k] = s_ideal
                sym_indices[k] = nearest_idx
                
                # Phase Error Detector
                err = np.angle(s_rot * np.conj(s_ideal))
                curr_freq += beta_pll * err
                curr_phase += curr_freq + alpha_pll * err
                
            self.pll_phase = curr_phase % (2.0 * np.pi)
            self.pll_freq = curr_freq
            
            # Sliced constellation points
            res.i_meas = np.real(corrected_syms).astype(np.float32)
            res.q_meas = np.imag(corrected_syms).astype(np.float32)
            res.symbols = sym_indices
            
            # Calculate EVM, SNR, Phase & Mag Error
            error_vec = corrected_syms - decided_syms
            err_power = np.mean(np.abs(error_vec)**2)
            ref_power = np.mean(np.abs(decided_syms)**2)
            
            if ref_power > 1e-12:
                evm_rms = np.sqrt(err_power / ref_power) * 100.0
                evm_peak = (np.max(np.abs(error_vec)) / np.max(np.abs(ideal_const))) * 100.0
                res.evm_rms_pct = float(min(100.0, max(0.0, evm_rms)))
                res.evm_peak_pct = float(min(200.0, max(0.0, evm_peak)))
                res.snr_db = float(max(0.0, 20.0 * np.log10(max(100.0 / max(res.evm_rms_pct, 0.01), 1.0))))
                res.phase_error_deg = float(np.mean(np.abs(np.angle(corrected_syms * np.conj(decided_syms)))) * (180.0 / np.pi))
                res.mag_error_pct = float(np.mean(np.abs(np.abs(corrected_syms) - np.abs(decided_syms))) * 100.0)
            else:
                res.evm_rms_pct = 100.0
                res.evm_peak_pct = 100.0
                res.snr_db = 0.0

            res.is_locked = res.snr_db > 12.0

        # 5. Eye Diagram Construction
        # Use derotated & AGC-normalized baseband stream if available, else iq_filtered
        eye_source = iq_derot if ('iq_derot' in locals() and iq_derot is not None) else iq_filtered
        
        # Extract slices of 2 * sps duration around symbol points
        pts_per_trace = 2 * sps
        num_traces = min(128, (len(eye_source) - pts_per_trace) // sps)
        if num_traces > 4 and pts_per_trace >= 4:
            i_traces = np.zeros((num_traces, pts_per_trace), dtype=np.float32)
            q_traces = np.zeros((num_traces, pts_per_trace), dtype=np.float32)
            
            for tr_idx in range(num_traces):
                st_idx = tr_idx * sps
                i_traces[tr_idx] = np.real(eye_source[st_idx : st_idx + pts_per_trace])
                q_traces[tr_idx] = np.imag(eye_source[st_idx : st_idx + pts_per_trace])
                
            # Time axis from -T_sym to +T_sym in nanoseconds
            t_sym_ns = (1.0 / max(symbol_rate, 1e3)) * 1e9
            time_ns = np.linspace(-t_sym_ns, t_sym_ns, pts_per_trace, dtype=np.float32)
            
            res.eye_time_ns = time_ns
            res.eye_i_traces = i_traces
            res.eye_q_traces = q_traces

        # 6. Bit Table & Decoded Binary / Hex Generation
        if len(res.symbols) > 0:
            num_bits_per_sym = int(np.round(np.log2(max(2, len(ideal_const)))))
            # Format bits
            bit_chunks = [format(s, f'0{num_bits_per_sym}b') for s in res.symbols[:512]]
            all_bits = "".join(bit_chunks)
            res.bits = all_bits
            
            # Format bytes as Hex
            hex_bytes = []
            for b_idx in range(0, len(all_bits) - 7, 8):
                byte_val = int(all_bits[b_idx:b_idx+8], 2)
                hex_bytes.append(f"{byte_val:02X}")
            res.hex_stream = " ".join(hex_bytes[:128])

        return res
