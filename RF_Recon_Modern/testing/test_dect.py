"""
test_dect.py - DECT monitor: frame analysis of zero-span captures, the engine's
counts, and the Count via Zero-Span run in the main window (no analyzer needed).

    python testing/test_dect.py
"""

import os
import sys
import tempfile
import time

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.dect_frames import analyse, synth_capture, FRAME_S


def test_frame_analysis():
    cases = [
        # (antennas, beltpacks on calls, slot map)                 downlink slots, uplink slots
        ((1, 0, "F......................."), dict(fp_slots=(0,), pp_slots=())),
        ((1, 2, "FFF..........PP........."), dict(fp_slots=(0, 1, 2), pp_slots=(13, 14))),
        ((2, 0, "F..F...................."), dict(fp_slots=(0, 3), pp_slots=())),
        ((2, 1, "F..FF...........P......."), dict(fp_slots=(0, 3, 4), pp_slots=(16,))),
        ((0, 2, "................P.P....."), dict(fp_slots=(), pp_slots=(13, 15), frames=6)),
        ((1, 1, "FF...........P.........."), dict(fp_slots=(7, 8), pp_slots=(20,))),       # any frame phase
        ((1, 2, "FFF..........PP........."), dict(fp_slots=(0, 1, 2), pp_slots=(13, 14), dt_s=57e-6, frames=5)),  # tinySA Ultra rate
        ((0, 0, "........................"), dict(fp_slots=(), pp_slots=())),
    ]
    for (ant, calls, slots), kw in cases:
        t, p = synth_capture(**kw)
        r = analyse(t, p, -85.0)
        assert (r["antennas"], r["calls"], r["slots"]) == (ant, calls, slots), (kw, r)
        assert not r["continuous"]
    # A beltpack talking steadily from close by looks like an antenna, except that it sits
    # exactly 5 ms after one: the pair is resolved by which level wanders less
    t, p = synth_capture(fp_slots=(0, 1), pp_slots=(13,), pp_wander_db=0.4)
    r = analyse(t, p, -85.0)
    assert (r["antennas"], r["calls"]) == (1, 1), r
    # A continuous signal is not DECT; a capture under two frames is not judged
    t, p = synth_capture(fp_slots=(0,))
    assert analyse(t, np.full(len(t), -40.0), -85.0)["continuous"]
    t, p = synth_capture(fp_slots=(0,), frames=1)
    assert analyse(t[: int(1.5 * FRAME_S / 1.024e-6)], p[: int(1.5 * FRAME_S / 1.024e-6)], -85.0) is None


def test_engine_counts():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from core.dect_analyzer import DECTAnalyzerEngine, DECT_BANDS
    eng = DECTAnalyzerEngine()
    eng.set_band("EU DECT (1880-1900 MHz)")
    eng.set_enabled(True)
    carriers = DECT_BANDS["EU DECT (1880-1900 MHz)"]["carriers"]
    assert [c["freq_mhz"] for c in carriers][:3] == [1881.792, 1883.52, 1885.248]      # numbered upwards
    assert eng.carrier_at(1883.6e6)["ch"] == 1 and eng.carrier_at(1870e6) is None
    results = []
    eng.analysis_updated.connect(results.append)
    f = np.linspace(1875e6, 1905e6, 1500)
    p = np.full(1500, -105.0)
    p[np.abs(f - 1883.52e6) < 0.8e6] = -60.0                          # Ch 1 occupied
    for _ in range(12):
        eng._last_analysis_time = 0.0
        eng.process_sweep_data(f, p)
    assert [c["ch"] for c in eng.occupied_carriers()] == [1]
    assert eng.carrier_stats[1883.52]["counted"] == "duty-cycle"
    # A zero-span capture of Ch 1 replaces the duty-cycle guess with a count
    t, pw = synth_capture(fp_slots=(0, 1), pp_slots=(13,), frames=6)
    r = eng.process_zero_span(1883.52e6, t * 1e9, pw)
    assert r["antennas"] == 1 and r["calls"] == 1
    st = eng.carrier_stats[1883.52]
    assert (st["antennas"], st["beltpacks"], st["counted"]) == (1, 1, "zero-span") and st["slots"].startswith("FF")
    assert results[-1]["counted"] == "zero-span" and results[-1]["total_beltpacks"] == 1
    assert "zero span" in st["status"]
    # The count survives later sweeps, and off-carrier captures are ignored
    eng._last_analysis_time = 0.0
    eng.process_sweep_data(f, p)
    assert eng.carrier_stats[1883.52]["counted"] == "zero-span"
    assert eng.process_zero_span(1870e6, t * 1e9, pw) is None
    eng.set_enabled(False)
    assert not eng.zero_span


def test_count_run_in_main_window():
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.is_connected = win.is_sweeping = True
    dp = win.dect_panel
    dp.band_combo.setCurrentText("US DECT 6.0 (1920-1930 MHz)")
    dp.enable_btn.setChecked(True)
    f = np.linspace(1910e6, 1940e6, 1500)
    p = np.full(1500, -105.0, dtype=np.float32)
    for cf in (1921.536e6, 1924.992e6):
        p[np.abs(f - cf) < 0.8e6] = -55.0
    for _ in range(12):
        win.dect_engine._last_analysis_time = 0.0
        win._last_render_time = 0.0
        win._on_sweep_data(f, p)
    assert [c["ch"] for c in win.dect_engine.occupied_carriers()] == [0, 2]

    sent = []
    win.multi_device_manager.configure_det = lambda **kw: sent.append(kw)
    win.start_dect_count()
    assert win._dect_count is not None and not dp.count_btn.isEnabled()
    assert sent[-1]["center_freq_hz"] == 1921.536e6 and sent[-1]["decimate_factor"] == 128 and sent[-1]["trig_length"] == 65536
    # Captures from the first carrier: one antenna with two calls; then the second: an idle antenna
    def feed(cf, **kw):
        t, pw = synth_capture(frames=6, **kw)
        win._on_det_data("slot_a", t * 1e9, pw.astype(np.float32), {"center_freq": cf, "sample_interval_ns": 1024.0})
    for _ in range(3):
        feed(1921.536e6, fp_slots=(0, 1, 2), pp_slots=(13, 14))
    assert sent[-1]["center_freq_hz"] == 1924.992e6, "moved on to the second carrier"
    feed(1921.536e6, fp_slots=(0,))                    # a late capture from the first carrier: ignored
    for _ in range(3):
        feed(1924.992e6, fp_slots=(5,))
    assert win._dect_count is None and dp.count_btn.isEnabled()
    assert "2 antennas, 2 beltpacks" in dp.count_status_lbl.text(), dp.count_status_lbl.text()
    z = win.dect_engine.zero_span
    assert (z[1921.536]["antennas"], z[1921.536]["calls"], z[1924.992]["antennas"]) == (1, 2, 1)
    assert dp.units_val_lbl.text() == "2 Ant | 2 Packs", dp.units_val_lbl.text()
    assert win._last_operating_mode == "SWP"
    # A carrier that never delivers a capture is skipped after the timeout
    win.DECT_COUNT_TIMEOUT_S = 0.0
    win.start_dect_count()
    win._dect_count_watch(); win._dect_count_watch()
    assert win._dect_count is None and "0 of 2" in dp.count_status_lbl.text()
    win.close()


if __name__ == "__main__":
    for test in (test_frame_analysis, test_engine_counts, test_count_run_in_main_window):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All DECT tests passed.")
