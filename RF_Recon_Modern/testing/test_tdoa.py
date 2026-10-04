"""
test_tdoa.py - Time-difference location: correlation, the session over several GPS
seconds, and the run in the main window (no analyzer needed).

    python testing/test_tdoa.py
"""

import os
import sys
import tempfile
import time

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.tdoa import TDOASession, synth_captures, correlate, decimation_for, gps_second, C

SENSORS = {"a": (0.0, 0.0), "b": (120.0, 0.0), "c": (60.0, 100.0), "d": (0.0, 90.0)}
TX = (75.0, 35.0)


def run(sensors=SENSORS, rounds=6, **kw):
    s = TDOASession(sensors, 540e6)
    for k in range(rounds):
        for sid, (iq, info) in synth_captures(sensors, TX, second=1_791_055_076 + k, seed=k, **kw).items():
            s.add_capture(sid, iq, info)
    return s, s.result()


def err_m(res):
    return float(np.hypot(res["fix"].x - TX[0], res["fix"].y - TX[1]))


def test_correlation():
    assert (decimation_for(200e3), decimation_for(350e3), decimation_for(6e6)) == (128, 64, 4)
    assert gps_second({"ns_since_epoch": 1_791_055_076 * 10**9 - 104}) == 1_791_055_076
    caps = synth_captures(SENSORS, TX, snr_db=30)
    sr = caps["a"][1]["sample_rate"]
    true = (np.hypot(120 - 75, 35) - np.hypot(75, 35)) / C
    d, q, f = correlate(caps["a"][0], caps["b"][0], sr)
    assert abs(d - true) < 3e-9 and q > 15 and abs(f) < 60, (d * 1e9, true * 1e9, q, f)
    # Analyzers whose references differ: the offset is found and the delay still comes out
    caps = synth_captures(SENSORS, TX, snr_db=30, ppm={"a": -0.29, "b": 0.12})
    d, q, f = correlate(caps["a"][0], caps["b"][0], sr, freq_offset_hz=-540e6 * (0.12 + 0.29) * 1e-6)
    assert abs(d - true) < 3e-9 and q > 15 and abs(f - -221.4) < 40, (d * 1e9, q, f)
    d, q, f = correlate(caps["a"][0], caps["b"][0], sr, freq_offset_hz=-150.0, search_hz=150.0)   # a poor first guess
    assert abs(d - true) < 5e-9 and abs(f - -221.4) < 40
    # Noise alone has no peak worth the name
    rng = np.random.default_rng(1)
    n1, n2 = (rng.normal(size=32768) + 1j * rng.normal(size=32768) for _ in range(2))
    assert correlate(n1, n2, sr)[1] < 6.0


def test_session():
    s, res = run()
    assert res["fix"] is not None and err_m(res) < 1.5 and res["rounds"] == 6 and res["fix"].method == "tdoa", res
    assert set(res["tdoa_ns"]) == set(SENSORS) and res["tdoa_ns"][res["ref"]] == 0.0
    # Different reference errors on every analyzer
    s, res = run(ppm={"a": -0.29, "b": 0.12, "c": -0.05, "d": 0.31})
    assert err_m(res) < 2.0, err_m(res)
    # Realistic PPS timing: metres, not centimetres, and the stated uncertainty says so
    s, res = run(pps_jitter_s=30e-9)
    assert err_m(res) < 20.0 and res["fix"].radius_m > 2.0 and max(res["spread_ns"].values()) > 10.0, (err_m(res), res["fix"].radius_m)
    s, res = run(pps_jitter_s=150e-9, rounds=30)
    assert err_m(res) < 40.0 and res["fix"].radius_m > 5.0, (err_m(res), res["fix"].radius_m)
    # A carrier too weak to correlate: no fix, and the reason
    s, res = run(snr_db=-25.0)
    assert res["fix"] is None and res["rounds"] == 0 and "too weak" in res["note"]
    # Two sensors: which one it is nearer to, not a point
    two = {k: SENSORS[k] for k in ("a", "b")}
    s, res = run(sensors=two)
    assert res["fix"] is None and "Two sensors give a line" in res["note"] and "nearer to" in res["note"] or "farther from" in res["note"]
    # A second that one sensor missed is not used
    s = TDOASession(SENSORS, 540e6)
    caps = synth_captures(SENSORS, TX, second=100)
    for sid in ("a", "b", "c"):
        s.add_capture(sid, *caps[sid])
    late = synth_captures(SENSORS, TX, second=101)["d"]
    assert s.add_capture("d", *late) is None and not s.rounds
    s.discard_incomplete()
    assert not s.captures and "did not all capture the same GPS second" in s.result()["note"]
    # A sensor's known cable delay is taken off its arrival time
    s = TDOASession(SENSORS, 540e6, delays_s={"c": 150e-9})
    for k in range(4):
        for sid, (iq, info) in synth_captures(SENSORS, TX, second=200 + k, seed=k, delays_s={"c": 150e-9}).items():
            s.add_capture(sid, iq, info)
    assert err_m(s.result()) < 1.5


def test_run_in_main_window():
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    mdm, net, lp = win.multi_device_manager, win.sensor_net, win.locate_panel
    win.nav_rail.set_active_mode(9)
    # Three analyzers around a field, each with a GNSS fix
    lat0, lon0 = 41.0, -74.0
    places = {"slot_a": (0.0, 0.0), "slot_b": (120.0, 0.0), "slot_c": (60.0, 100.0)}
    for sid, (e, n) in places.items():
        mdm.ensure_slot(sid)
        mdm.slots[sid].is_connected = True
        g = {"lat": lat0 + n / 111320.0, "lon": lon0 + e / (111320.0 * np.cos(np.radians(lat0))), "alt": 60.0, "sats": 12,
             "lock": True, "docxo_lock": False, "time": (2026, 10, 3, 19, 0, 0)}
        win._on_gnss_updated(sid, g)
    pos = net.positions_xy()
    assert set(pos) >= set(places)
    tx = (pos["slot_a"][0] + 75.0, pos["slot_a"][1] + 35.0)

    asked = []

    def fake_request(slot_id, cf, dec, n, ref, trig, request_id=None):
        asked.append((slot_id, cf, dec, n, trig, request_id))
        second = 1_791_055_000 + request_id[1]
        iq, info = synth_captures({s: pos[s] for s in places}, tx, second=second, seed=request_id[1], n=n,
                                  sample_rate=125e6 / dec, pps_jitter_s=20e-9)[slot_id]
        win._on_timed_capture(slot_id, iq, dict(info, id=request_id))
        return True

    mdm.request_timed_capture = fake_request
    # Without a carrier selected the button is off; a run needs sensors with a fix
    assert not lp.tdoa_btn.isEnabled()
    win.start_tdoa(540e6)
    assert win._tdoa is not None and not lp.tdoa_btn.isEnabled() and "Locating" in lp.tdoa_btn.text()
    deadline = time.monotonic() + 12
    while win._tdoa is not None and time.monotonic() < deadline:
        win._tdoa_tick()
        app.processEvents()
        time.sleep(0.01)
    assert win._tdoa is None, "the run finishes by itself"
    assert len(asked) == 3 * win.TDOA_SECONDS and {a[4] for a in asked} == {9} and {a[2] for a in asked} == {128}
    key = next(k for k in net.tdoa_fixes)
    fix = net.tdoa_fixes[key][0]
    assert np.hypot(fix.x - tx[0], fix.y - tx[1]) < 25.0, (fix.x - tx[0], fix.y - tx[1])
    text = lp.status_lbl.text()
    assert "540.000 MHz located by arrival time: 41.0" in text and "8 seconds, 3 sensors" in text, text
    assert "Locate precisely" in lp.tdoa_btn.text()

    # Only two sensors with a fix: says what is missing instead of starting
    win._on_gnss_updated("slot_c", {"lat": 0.0, "lon": 0.0, "alt": 0.0, "sats": 0, "lock": False, "docxo_lock": False,
                                    "time": (0, 0, 0, 0, 0, 0)})
    win._on_gnss_updated("slot_b", {"lat": 0.0, "lon": 0.0, "alt": 0.0, "sats": 0, "lock": False, "docxo_lock": False,
                                    "time": (0, 0, 0, 0, 0, 0)})
    win.start_tdoa(540e6)
    assert win._tdoa is None and "needs two or more connected analyzers with a GNSS fix" in lp.status_lbl.text()
    win.close()


if __name__ == "__main__":
    for test in (test_correlation, test_session, test_run_in_main_window):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All TDOA tests passed.")
