"""
audio_demodulator.py - Real-Time Analog AM/FM Audio Demodulation & Live Monitoring.
Supports FM Wide (broadcast / wireless mic), FM Narrow (NFM comms), and AM.
Streams demodulated audio directly to ALSA/PulseAudio (aplay) with zero latency
and computes real-time audio oscilloscope & audio FFT spectra.

CRITICAL PROJECT RULE: Operates strictly on real hardware IQ streams.
"""

import subprocess
import threading
import numpy as np
import scipy.signal as signal
from PyQt6.QtCore import QObject, pyqtSignal

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
        
        self.audio_process = None
        self._lock = threading.Lock()
        self._prev_sample = 0.0 + 0.0j
        self._deemphasis_state = 0.0

    def start_playback(self):
        """
        Starts the aplay audio playback subprocess pipe.
        """
        with self._lock:
            if self.is_playing:
                return
            try:
                # Open aplay with 32-bit float LE PCM audio stream at 48 kHz
                self.audio_process = subprocess.Popen(
                    [
                        "aplay", "-t", "raw", "-f", "FLOAT_LE",
                        "-r", str(self.audio_rate), "-c", "1", "-q"
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.is_playing = True
                self._deemphasis_state = 0.0
                self._prev_sample = 0.0 + 0.0j
                self.status_changed.emit(f"Audio monitor active ({self.demod_mode})")
            except Exception as e:
                self.status_changed.emit(f"Audio playback error: {e}")
                self.is_playing = False

    def stop_playback(self):
        """
        Stops the audio playback subprocess pipe.
        """
        with self._lock:
            if not self.is_playing:
                return
            self.is_playing = False
            if self.audio_process:
                try:
                    if self.audio_process.stdin:
                        self.audio_process.stdin.close()
                    self.audio_process.terminate()
                    self.audio_process.wait(timeout=0.2)
                except Exception:
                    pass
                self.audio_process = None
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
        self.status_changed.emit(f"Demodulation mode set to {self.demod_mode}")

    def process_iq_stream(self, raw_iq: np.ndarray, sample_rate: float, carrier_offset_hz: float = 0.0):
        """
        Demodulates physical hardware IQ stream into 48 kHz audio, pipes to aplay,
        and emits telemetry for the audio oscilloscope and FFT.
        """
        if len(raw_iq) < 64 or sample_rate <= 0:
            return

        iq = raw_iq.astype(np.complex64)
        n_samples = len(iq)

        # 1. Baseband Analog Demodulation
        if "AM" in self.demod_mode:
            # AM Envelope Detection: |IQ| - DC
            env = np.abs(iq)
            raw_audio = env - np.mean(env)
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

        # 2. Resample from Hardware IQ rate (e.g. 1.5625 MSPS) to Audio Rate (48 kHz)
        target_len = int(round(n_samples * (self.audio_rate / float(sample_rate))))
        if target_len < 16:
            return
            
        try:
            audio_48k = signal.resample(raw_audio, target_len)
        except Exception:
            return

        # 3. Post-Detection Audio Filtering
        if "FM" in self.demod_mode:
            # 75 us De-emphasis Filter (Single-pole IIR lowpass)
            # RC time constant tau = 75 us -> alpha = dt / (tau + dt)
            dt = 1.0 / self.audio_rate
            tau = 75e-6
            alpha = dt / (tau + dt)
            deemph = np.empty_like(audio_48k)
            val = self._deemphasis_state
            for k in range(len(audio_48k)):
                val = alpha * audio_48k[k] + (1.0 - alpha) * val
                deemph[k] = val
            self._deemphasis_state = val
            audio_filtered = deemph
        else:
            audio_filtered = audio_48k

        # 4. Squelch / AGC & Gain
        rms = np.sqrt(np.mean(audio_filtered ** 2) + 1e-12)
        if rms > 1e-4:
            # Gentle soft limiting / peak AGC
            peak = np.max(np.abs(audio_filtered)) + 1e-6
            audio_scaled = (audio_filtered / peak) * 0.7 * self.volume
        else:
            audio_scaled = audio_filtered * self.volume

        audio_bytes = audio_scaled.astype(np.float32).tobytes()

        # 5. Send to aplay audio output pipe
        with self._lock:
            if self.is_playing and self.audio_process and self.audio_process.stdin:
                try:
                    self.audio_process.stdin.write(audio_bytes)
                    self.audio_process.stdin.flush()
                except Exception:
                    pass

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
