"""
test_band24.py - The 2.4 GHz / ShowLink monitor: signal classification, channel
busy figures, the verdict on the channel in use, airtime from zero span, and the
panel in the main window (no analyzer needed).

    python testing/test_band24.py
"""

import os
import sys
import tempfile
import time

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core import band24

F = np.linspace(2400.0, 2483.5, 1670)          # 50 kHz points


def sweep(rng, wifi=(), zigbee=(), hop=None, wide=None, noise=-100.0):
    """A synthetic 2.4 GHz sweep: Wi-Fi channels, Zigbee channels, one hop, a wideband blob."""
    p = noise + rng.normal(0, 1.5, len(F))
    for n in wifi:
        sel = np.abs(F - band24.WIFI_CHANNELS[n]) < 9.5
        p[sel] = -62 + rng.normal(0, 2, sel.sum())
    for k in zigbee:
        p[np.abs(F - band24.ZIGBEE_CHANNELS[k]) < 1.0] = -70
    if hop is not None:
        p[np.abs(F - hop) < 0.5] = -65
    if wide is not None:
        p[np.abs(F - wide) < 5.0] = -60
    return p


def test_classification():
    rng = np.random.default_rng(0)
    kinds = {band24.classify(s) for s in band24.segments(F, sweep(rng, wifi=(6,)), -80)}
    assert kinds == {"wifi"}, kinds
    segs = band24.segments(F, sweep(rng, wifi=(6,)), -80)
    assert band24.wifi_channel_for(segs[0]) == 6
    assert {band24.classify(s) for s in band24.segments(F, sweep(rng, zigbee=(26,)), -80)} == {"zigbee"}
    assert {band24.classify(s) for s in band24.segments(F, sweep(rng, hop=2441.0), -80)} == {"hop"}
    assert {band24.classify(s) for s in band24.segments(F, sweep(rng, wide=2455.0), -80)} == {"wide"}
    # A 2 MHz signal off the Zigbee raster is a hopper's, not ShowLink's
    p = sweep(rng); p[np.abs(F - 2442.3) < 1.0] = -70
    assert {band24.classify(s) for s in band24.segments(F, p, -80)} == {"hop"}


def test_monitor_and_verdict():
    rng = np.random.default_rng(1)
    m = band24.Band24Monitor(50)
    for i in range(50):
        m.update(F, sweep(rng, wifi=(6,) if i % 3 == 0 else (), zigbee=(26,) if i % 2 == 0 else (),
                          hop=2402 + rng.integers(0, 79)), -80)
    s = m.summary()
    assert s["sweeps"] == 50
    assert abs(s["wifi"][6]["busy_pct"] - 34.0) < 0.1 and s["wifi"][1]["busy_pct"] == 0.0
    z17 = s["zigbee"][17]
    assert 34.0 <= z17["busy_pct"] <= 40.0 and abs(z17["kinds"]["wifi"] - 34.0) < 0.1 and 6 in z17["wifi"]   # plus the odd hop
    z26 = s["zigbee"][26]
    assert z26["busy_pct"] >= 50.0 and z26["interference_pct"] < 10.0, z26     # ShowLink itself is not interference
    assert s["mix"]["hop"] > s["mix"]["wifi"] > 0
    a = band24.assess(s, 17)
    assert a["verdict"] in ("MARGINAL", "POOR") and "Wi-Fi channel 6" in a["reasons"][0], a
    assert band24.showlink_channel(s) == 26, "ShowLink is where the Zigbee-shaped traffic is"
    a = band24.assess(s, 26)
    assert a["verdict"] == "GOOD" and any("ShowLink itself" in r for r in a["reasons"]), a
    assert all(c != 26 for c in a["alternatives"]) and len(a["alternatives"]) == 3
    assert band24.assess(s, 15)["verdict"] == "GOOD"
    assert band24.assess({"zigbee": {}, "wifi": {}, "mix": {}, "sweeps": 0}, 15)["verdict"] == "UNKNOWN"
    assert band24.showlink_channel({"zigbee": {}, "wifi": {}, "mix": {}, "sweeps": 0}) is None


def test_feasibility():
    rng = np.random.default_rng(3)
    # A venue with Wi-Fi 1 and 6 busy and a Bluetooth hopper: the channels under 11 and the gaps are clear
    m = band24.Band24Monitor(50)
    for i in range(50):
        m.update(F, sweep(rng, wifi=(1, 6) if i % 2 == 0 else (6,), hop=2402 + rng.integers(0, 79)), -80)
    s = m.summary()
    f = band24.feasibility(s)
    assert f["verdict"] == "FEASIBLE" and {20, 21, 22, 23, 24, 25} <= set(f["clear"]), f
    assert f["wifi_in_use"] == [6, 1] and dict(f["disable"])[6] == [16, 17, 18, 19], f
    # Wi-Fi 1, 6 and 11 always busy: only the gaps between them (15 at 2425, 20 at 2450) and
    # the top (25, 26, above Wi-Fi 11) are clear; switching one Wi-Fi channel off frees the
    # ShowLink channels only it covers
    m = band24.Band24Monitor(50)
    for i in range(50):
        m.update(F, sweep(rng, wifi=(1, 6, 11)), -80)
    s = m.summary()
    f = band24.feasibility(s)
    assert f["verdict"] == "FEASIBLE" and f["clear"] == [15, 20, 25, 26], f
    freed = dict(f["disable"])
    assert freed[11] == [21, 22, 23, 24] and freed[6] == [16, 17, 18, 19] and freed[1] == [11, 12, 13, 14], f["disable"]
    text = band24.survey_text(s, f, detected=None, where="Hall A")
    assert text.startswith("ShowLink 2.4 GHz site survey - Hall A") and "FEASIBLE" in text
    assert "switching off Wi-Fi channel 11 would free ShowLink 21, 22, 23, 24" in text, text
    # With the gaps and the top blocked too (wideband interferers), nothing is clear
    m = band24.Band24Monitor(50)
    for i in range(50):
        p = sweep(rng, wifi=(1, 6, 11))
        for cf in (2425, 2450, 2478):
            p[np.abs(F - cf) < 3.5] = -60
        m.update(F, p, -80)
    f = band24.feasibility(m.summary())
    assert f["verdict"] == "NOT WITHOUT CHANGES" and f["clear"] == [], f
    # Interference that is not Wi-Fi-shaped stays when the Wi-Fi goes: Wi-Fi 6 half the time
    # and a wideband blob on 2437 MHz the other half; switching Wi-Fi 6 off frees 16 and 19 only
    m = band24.Band24Monitor(50)
    for i in range(50):
        m.update(F, sweep(rng, wifi=(6,)) if i % 2 == 0 else sweep(rng, wide=2437.0), -80)
    f = band24.feasibility(m.summary())
    assert dict(f["disable"])[6] == [16, 19], f["disable"]
    assert band24.feasibility({"zigbee": {}, "wifi": {}, "mix": {}, "sweeps": 0})["verdict"] == "UNKNOWN"


def test_airtime():
    t = np.arange(0, 0.067, 1.024e-6)
    p = np.full(len(t), -100.0)
    for k in range(10):
        p[(t >= k * 6e-3) & (t < k * 6e-3 + 1.2e-3)] = -60
    a = band24.airtime(t, p, -80)
    assert abs(a["busy_pct"] - 17.9) < 0.5 and a["bursts"] == 10 and abs(a["median_us"] - 1200) < 5 and not a["continuous"]
    assert band24.airtime(t, np.full(len(t), -50.0), -80)["continuous"]


def test_panel_in_main_window():
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.is_connected = win.is_sweeping = True
    sp, eng = win.showlink_panel, win.showlink_engine
    sp.my_channel_combo.setCurrentIndex(0)
    assert eng.my_channel is None, "by default the channel is read off the air"
    sp.enable_btn.setChecked(True)
    rng = np.random.default_rng(2)
    for i in range(30):
        eng._last_time = 0.0
        win._last_render_time = 0.0
        win._on_sweep_data(F * 1e6, sweep(rng, wifi=(6,) if i % 2 == 0 else (), zigbee=(17,) if i % 3 == 0 else ()).astype(np.float32))
    assert eng.detected_channel == 17 and "ShowLink seen on <b>Ch 17</b>" in sp.verdict_lbl.text(), sp.verdict_lbl.text()
    sp.my_channel_combo.setCurrentIndex(sp.my_channel_combo.findData(17))
    assert eng.my_channel == 17 and win.settings.value("showlink_judge_channel", type=int) == 17
    assert sp.showlink_table.rowCount() == 16 and sp.wifi_table.rowCount() == 14
    row17 = next(r for r in range(16) if sp.showlink_table.item(r, 0).text().startswith("17"))
    assert "★" in sp.showlink_table.item(row17, 0).text()
    assert 50 <= int(sp.showlink_table.item(row17, 2).text().rstrip("%")) <= 70       # Wi-Fi half the time, plus ShowLink
    assert sp.showlink_table.item(row17, 4).text() == "CONGESTED", sp.showlink_table.item(row17, 4).text()
    assert "POOR" in sp.verdict_lbl.text() and "Wi-Fi channel 6" in sp.verdict_lbl.text()
    assert sp.wifi_table.item(5, 2).text() == "50%"                   # row 5 is Wi-Fi 6
    assert "Wi-Fi" in sp.mix_lbl.text()
    assert "clear ShowLink channel" in sp.feas_lbl.text() and "Wi-Fi in use: ch 6" in sp.feas_lbl.text(), sp.feas_lbl.text()
    from PyQt6.QtWidgets import QApplication as _QA
    sp.copy_survey_btn.click()
    assert _QA.clipboard().text().startswith("ShowLink 2.4 GHz site survey"), _QA.clipboard().text()[:80]
    # Airtime run: zero span on the channel in use, three captures, then back to the sweep
    sent = []
    win.multi_device_manager.configure_det = lambda **kw: sent.append(kw)
    win.start_showlink_airtime()
    assert win._showlink_airtime is not None and sent[-1]["center_freq_hz"] == 2435e6 and not sp.airtime_btn.isEnabled()
    t = np.arange(0, 0.067, 1.024e-6)
    p = np.full(len(t), -100.0, dtype=np.float32)
    p[(t % 5e-3) < 1e-3] = -60
    for _ in range(3):
        win._on_det_data("slot_a", t * 1e9, p, {"center_freq": 2435e6, "sample_interval_ns": 1024.0})
    assert win._showlink_airtime is None and sp.airtime_btn.isEnabled()
    assert "Airtime on Ch 17: 2" in sp.airtime_lbl.text() and "busy over 3 × 67 ms" in sp.airtime_lbl.text(), sp.airtime_lbl.text()
    assert win._last_operating_mode == "SWP"
    win.close()


if __name__ == "__main__":
    for test in (test_classification, test_monitor_and_verdict, test_feasibility, test_airtime, test_panel_in_main_window):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All 2.4 GHz tests passed.")
