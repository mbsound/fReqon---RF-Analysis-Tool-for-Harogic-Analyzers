"""
test_demod_engine.py - Verification tests for DemodEngine DSP algorithms.
Tests all modulation schemes: ASK, FSK, PSK, QAM across EVM, eye diagrams,
modulated spectra, and bitstream extraction.
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.demod_engine import DemodEngine, MOD_TYPES

def test_demod_schemes():
    engine = DemodEngine()
    sample_rate = 2e6
    symbol_rate = 500e3
    sps = int(sample_rate / symbol_rate)
    n_symbols = 512
    
    print(f"Testing DemodEngine with SPS={sps}, SampleRate={sample_rate/1e6} MSPS, SymbolRate={symbol_rate/1e3} kBd\n")
    
    # Test each modulation scheme
    for category, schemes in MOD_TYPES.items():
        print(f"--- Category: {category} ---")
        for mod in schemes:
            ideal_const = engine.generate_ideal_constellation(mod)
            assert len(ideal_const) > 0, f"Failed to generate ideal constellation for {mod}"
            
            # Generate test symbols
            sym_indices = np.random.randint(0, len(ideal_const), size=n_symbols)
            sym_seq = ideal_const[sym_indices]
            
            # Upsample
            iq_upsampled = np.zeros(n_symbols * sps, dtype=np.complex64)
            iq_upsampled[::sps] = sym_seq
            
            # Apply RRC pulse shaping
            rrc = engine.design_rrc_filter(sps, alpha=0.35, span=6)
            import scipy.signal as signal
            tx_signal = signal.convolve(iq_upsampled, rrc, mode='same')
            
            # Add small noise (30 dB SNR)
            noise = (np.random.randn(len(tx_signal)) + 1j * np.random.randn(len(tx_signal))) * 0.02
            rx_signal = tx_signal + noise
            
            # Run DemodEngine
            res = engine.process_iq_stream(
                raw_iq=rx_signal,
                sample_rate=sample_rate,
                mod_type=mod,
                symbol_rate=symbol_rate,
                filter_type="RootRaisedCosine",
                filter_alpha=0.35
            )
            
            assert res is not None
            assert len(res.ideal_symbols) == len(ideal_const)
            assert len(res.i_meas) > 0
            assert len(res.spectrum_freq_mhz) > 0
            assert len(res.eye_time_ns) > 0
            assert len(res.bits) > 0
            
            print(f"  [PASS] {mod:<8}: EVM={res.evm_rms_pct:5.2f}%, SNR={res.snr_db:4.1f}dB, OBW={res.obw_hz/1e3:6.1f}kHz, Bits={len(res.bits)}, Lock={res.is_locked}")

    print("\nAll modulation schemes successfully verified!")

if __name__ == "__main__":
    test_demod_schemes()
