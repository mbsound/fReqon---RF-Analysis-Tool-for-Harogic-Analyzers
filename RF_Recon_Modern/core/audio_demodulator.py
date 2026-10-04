"""
audio_demodulator.py - Real-Time Analog AM/FM Audio Demodulation & Live Monitoring.
Supports FM Wide (broadcast / wireless mic), FM Narrow (NFM comms), and AM.
Plays demodulated audio through Qt Multimedia (CoreAudio on macOS, PulseAudio/ALSA
on Linux, WASAPI on Windows) and computes real-time audio oscilloscope & FFT spectra.

CRITICAL PROJECT RULE: Operates strictly on real hardware IQ streams.
"""

import threading
import numpy as np
import scipy.signal as signal
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

class AudioDemodulator(QObject):
    """
    Manages live demodulation of analog RF audio signals, audio playback piping,
    and audio oscilloscope / spectrum telemetry.
    """
    audio_frame_ready = pyqtSignal(np.ndarray, np.ndarray, float) # time_waveform, audio_fft, carrier_offset_hz
    status_changed = pyqtSignal(str)

    def __init__(self, sample_rate: int = 48000, parent=None):
        super().__init__(parent)
        self.audio_rate = sample_rate # Standard 48 kHz audio
        self.is_playing = False
        self.volume = 0.8
        self.demod_mode = "FM_WIDE" # "FM_WIDE", "FM_NARROW", "AM"
        self.center_freq_hz = 100.0e6
        
        self._sink = None          # QAudioSink (must be used from the GUI thread)
        self._sink_io = None       # QIODevice returned by QAudioSink.start()
        self._sink_float = True    # False: device only takes 16-bit PCM
        self._lock = threading.Lock()
        self._prev_sample = 0.0 + 0.0j
        self._reset_dsp()

    def start_playback(self):
        """
        Opens the default audio output (48 kHz mono) for push-mode playback.
        """
        with self._lock:
            if self.is_playing:
                return
            device = QMediaDevices.defaultAudioOutput()
            if device.isNull():
                self.status_changed.emit("Audio playback error: no audio output device")
                return
            fmt = QAudioFormat()
            fmt.setSampleRate(self.audio_rate)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
            self._sink_float = device.isFormatSupported(fmt)
            if not self._sink_float:
                fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
                if not device.isFormatSupported(fmt):
                    self.status_changed.emit("Audio playback error: output does not support 48 kHz mono")
                    return
            self._sink = QAudioSink(device, fmt, self)
            # ~250 ms of buffering absorbs the gaps between IQ acquisitions
            bytes_per_sample = 4 if self._sink_float else 2
            self._sink.setBufferSize(int(self.audio_rate * 0.25) * bytes_per_sample)
            self._sink_io = self._sink.start()
            if self._sink_io is None:
                self._sink = None
                self.status_changed.emit("Audio playback error: could not open audio output")
                return
            self.is_playing = True
            self._prev_sample = 0.0 + 0.0j
            self._reset_dsp()
            self.status_changed.emit(f"Audio monitor active ({self.demod_mode})")

    def stop_playback(self):
        """
        Stops audio playback and releases the output device.
        """
        with self._lock:
            if not self.is_playing:
                return
            self.is_playing = False
            if self._sink is not None:
                self._sink.stop()
                self._sink.deleteLater()
            self._sink = None
            self._sink_io = None
            self.status_changed.emit("Audio monitor stopped")

    def set_volume(self, volume: float):
        """
        Sets audio playback gain (0.0 to 1.0).
        """
        self.volume = max(0.0, min(1.0, float(volume)))

    def set_demod_mode(self, mode: str):
        """
        Sets demodulation mode: "FM_WIDE", "FM_NARROW", "AM".
        """
        self.demod_mode = mode.upper()
        self._reset_dsp()  # filters depend on the mode
        self.status_changed.emit(f"Demodulation mode set to {self.demod_mode}")

    def _reset_dsp(self):
        self._dsp_rate = None
        self._agc_peak = 1e-9

    def _setup_dsp(self, sample_rate: float):
        """(Re)build the resampling chain for an IQ rate and the current mode."""
        self._dsp_rate = sample_rate
        cutoff = 15e3 if self.demod_mode == "FM_WIDE" else 5e3
        cutoff = min(cutoff, 0.45 * sample_rate)
        # Anti-alias lowpass at the IQ rate, then integer decimation to the
        # lowest rate >= 48 kHz, then fractional (linear) interpolation to 48 kHz.
        self._sos = signal.ellip(8, 0.5, 70, cutoff, fs=sample_rate, output="sos")
        self._sos_zi = np.zeros((self._sos.shape[0], 2))
        self._dec = max(1, int(sample_rate // self.audio_rate))
        self._dec_phase = 0
        self._interp_step = (sample_rate / self._dec) / self.audio_rate
        self._interp_pos = 0.0
        self._interp_prev = None
        if "FM" in self.demod_mode:
            alpha = (1.0 / self.audio_rate) / (75e-6 + 1.0 / self.audio_rate)
            self._post_b, self._post_a = np.array([alpha]), np.array([1.0, alpha - 1.0])
        else:
            self._post_b, self._post_a = np.array([1.0, -1.0]), np.array([1.0, -0.995])
        self._post_zi = np.zeros(max(len(self._post_a), len(self._post_b)) - 1)
        self._agc_peak = 1e-9

    def _resample_to_audio(self, x: np.ndarray) -> np.ndarray:
        """Linear interpolation onto the 48 kHz grid, continuous across calls."""
        if self._interp_prev is not None:
            x = np.concatenate(([self._interp_prev], x))
        if len(x) < 2:
            return np.empty(0)
        last = len(x) - 1
        n_out = int(np.floor((last - self._interp_pos) / self._interp_step)) + 1
        if n_out <= 0:
            return np.empty(0)
        t = self._interp_pos + self._interp_step * np.arange(n_out)
        out = np.interp(t, np.arange(len(x)), x)
        # Next output position, relative to this block's last sample (which
        # becomes index 0 of the next call's buffer)
        self._interp_pos = t[-1] + self._interp_step - last
        self._interp_prev = x[-1]
        return out

    def process_iq_stream(self, raw_iq: np.ndarray, sample_rate: float, carrier_offset_hz: float = 0.0):
        """
        Demodulates physical hardware IQ stream into 48 kHz audio, plays it,
        and emits telemetry for the audio oscilloscope and FFT.
        """
        if len(raw_iq) < 64 or sample_rate <= 0:
            return

        iq = raw_iq.astype(np.complex64)
        n_samples = len(iq)

        # 1. Baseband Analog Demodulation
        if "AM" in self.demod_mode:
            # AM envelope detection; the carrier's DC level is removed after
            # resampling by a DC blocker (a per-block mean would step at joins)
            raw_audio = np.abs(iq)
        else:
            # Polar Frequency Discriminator: arg(x[n] * conj(x[n-1]))
            # Extends with previous sample across packet boundaries
            padded_iq = np.empty(n_samples + 1, dtype=np.complex64)
            padded_iq[0] = self._prev_sample if abs(self._prev_sample) > 1e-9 else iq[0]
            padded_iq[1:] = iq
            self._prev_sample = iq[-1]

            # Instantaneous frequency deviation d_phi
            diff_iq = padded_iq[1:] * np.conj(padded_iq[:-1])
            raw_audio = np.angle(diff_iq) # in radians per sample [-pi, pi]
            
            # Normalize to nominal deviation
            if self.demod_mode == "FM_WIDE":
                # Wide FM (75 kHz deviation nominal)
                dev_norm = (sample_rate / (2.0 * np.pi * 75e3))
                raw_audio = raw_audio * dev_norm
            else:
                # Narrow FM (5 kHz deviation nominal)
                dev_norm = (sample_rate / (2.0 * np.pi * 5e3))
                raw_audio = raw_audio * dev_norm

        # 2-4. Filter, resample to 48 kHz, de-emphasis/DC block and gain. Every stage
        # carries its state from one block to the next, so contiguous IQ blocks
        # (continuous IQS) produce seamless audio with no clicks at the joins.
        if self._dsp_rate != sample_rate:
            self._setup_dsp(sample_rate)
        filtered, self._sos_zi = signal.sosfilt(self._sos, raw_audio, zi=self._sos_zi)
        mid = filtered[self._dec_phase::self._dec]
        self._dec_phase = (self._dec_phase - len(filtered)) % self._dec
        audio_48k = self._resample_to_audio(mid)
        if len(audio_48k) == 0:
            return

        # FM: 75 us de-emphasis; AM: DC-blocking high-pass (see _setup_dsp)
        audio_filtered, self._post_zi = signal.lfilter(
            self._post_b, self._post_a, audio_48k, zi=self._post_zi)

        # Peak-tracking AGC: instant attack (no clipping), ~1 s release, so the
        # level no longer jumps from block to block.
        peak = float(np.max(np.abs(audio_filtered))) + 1e-9
        release = np.exp(-len(audio_filtered) / float(self.audio_rate))
        self._agc_peak = max(peak, self._agc_peak * release)
        audio_scaled = audio_filtered * (0.7 * self.volume / self._agc_peak)

        if self._sink_float:
            audio_bytes = audio_scaled.astype(np.float32).tobytes()
        else:
            audio_bytes = (np.clip(audio_scaled, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

        # 5. Push to the audio output. Never block: if the device buffer is full,
        # drop the excess samples rather than stall the GUI thread.
        with self._lock:
            if self.is_playing and self._sink_io is not None:
                free = self._sink.bytesFree()
                frame = 4 if self._sink_float else 2
                n = min(len(audio_bytes), free - free % frame)
                if n > 0:
                    self._sink_io.write(audio_bytes[:n])

        # 6. Compute Real-Time Visualizer Waveform & Audio Spectrum (0 - 15 kHz)
        disp_pts = min(len(audio_scaled), 512)
        wave_disp = audio_scaled[:disp_pts]
        
        fft_pts = min(len(audio_scaled), 1024)
        if fft_pts >= 128:
            win = np.hanning(fft_pts)
            audio_fft = np.abs(np.fft.rfft(audio_scaled[:fft_pts] * win))
            audio_fft_db = 20.0 * np.log10(np.maximum(audio_fft, 1e-5))
            self.audio_frame_ready.emit(wave_disp, audio_fft_db, carrier_offset_hz)

    def process_iq_samples(self, i_samples: np.ndarray, q_samples: np.ndarray, carrier_offset_hz: float = 0.0):
        """Backward-compatible signature accepting separated I and Q arrays."""
        if len(i_samples) == 0 or len(q_samples) == 0:
            return
        iq = i_samples.astype(np.float32) + 1j * q_samples.astype(np.float32)
        self.process_iq_stream(iq, float(self.audio_rate), carrier_offset_hz)
