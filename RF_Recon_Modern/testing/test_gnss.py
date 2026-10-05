"""
test_gnss.py - A sensor's GNSS fix: averaging, the readout, and the Locate panel
(no analyzer needed).

    python testing/test_gnss.py
"""

import os
import sys
import tempfile
import time

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.sensor_net import Sensor


def fix(lat, lon, **kw):
    g = {"lat": lat, "lon": lon, "alt": 62.0, "sats": 14, "lock": True, "docxo_lock": False, "docxo_mode": "lock",
         "antenna": "external", "time": (2026, 10, 3, 18, 55, 37), "sats_in_view": 21, "sats_used": 14,
         "snr_avg": 38, "snr_max": 46, "snr_min": 24}
    g.update(kw)
    return g


def test_fix_averaging():
    s = Sensor("slot_a", "Analyzer A")
    assert not s.has_fix() and s.latlon() is None and "No GNSS data" in s.gnss_summary()
    s.add_fix(fix(0.0, 0.0, lock=False))
    assert not s.has_fix() and "Waiting for a GNSS fix, 21 satellites in view" in s.gnss_summary()
    # Fixes scattered a few metres around a point: the mean is closer than any one of them
    rng = np.random.default_rng(0)
    lat0, lon0 = 41.000500, -74.000500
    for _ in range(200):
        s.add_fix(fix(lat0 + rng.normal(0, 4.0) / 111320.0, lon0 + rng.normal(0, 4.0) / (111320.0 * 0.744)))
    lat, lon, alt = s.latlon()
    err_m = np.hypot((lat - lat0) * 111320.0, (lon - lon0) * 111320.0 * 0.744)
    assert s.fix_n == 200 and err_m < 1.0 and alt == 62.0, (s.fix_n, err_m)
    assert 4.0 < s.fix_spread_m() < 8.0, s.fix_spread_m()
    text = s.gnss_summary()
    assert "41.000" in text and "mean of 200 fixes, ±" in text and "14 satellites of 21 in view" in text
    assert "signal 38 dB-Hz (24 to 46)" in text and "altitude 62 m" in text and "2026-10-03 18:55:37 UTC" in text
    assert "reference not locked to GNSS" in text
    s.add_fix(fix(lat0, lon0, docxo_lock=True))
    assert "reference locked to GNSS" in s.gnss_summary()
    # An analyzer with no disciplined oscillator (the SAN-60 here): its measured error is shown instead
    s.add_fix(fix(lat0, lon0, ocxo_type=0, docxo_mode="hold", ref_offset_ppm=-0.2925))
    assert "reference free-running, measured -0.29 ppm from GNSS" in s.gnss_summary(), s.gnss_summary()
    # Moved: the mean starts again at the new place
    s.add_fix(fix(lat0 + 0.01, lon0))
    assert s.fix_n == 1 and abs(s.latlon()[0] - (lat0 + 0.01)) < 1e-9
    # Losing the fix keeps nothing stale as the position
    s.add_fix(fix(0.0, 0.0, lock=False))
    assert s.latlon() is None
    # A manual position is not touched by fixes
    m = Sensor("slot_b", "B", position_source="manual", lat=51.5, lon=-0.1)
    m.add_fix(fix(lat0, lon0))
    assert m.latlon()[:2] == (51.5, -0.1)


def test_stale_first_report_is_not_a_fix():
    """Right after connecting an analyzer can report "locked" with no satellites and zero height."""
    s = Sensor("slot_a", "A")
    s.add_fix(fix(41.0005, -74.0005, alt=0.0, sats=0, sats_used=0))
    assert not s.has_fix() and s.fix_n == 0
    for alt in (37.0, 38.0, 39.0):
        s.add_fix(fix(41.0005, -74.0005, alt=alt))
    assert s.fix_n == 3 and abs(s.fix_alt - 38.0) < 1e-6, s.fix_alt
    assert ("Height", "38 m") in s.gnss_rows()


def test_weak_fix_is_flagged():
    """A lock on a weak signal or few satellites is said to be unreliable; a sound one is not."""
    s = Sensor("slot_a", "A")
    s.add_fix(fix(41.0005, -74.0005))
    assert s.weak_fix() is None and s.table_fields()["lock"] == "Locked"
    s.add_fix(fix(41.0005, -74.0005, snr_avg=9, snr_max=11, snr_min=9, sats=4, sats_used=4, sats_in_view=8))
    assert s.weak_fix() == "signal 9 dB-Hz, 4 satellites", s.weak_fix()
    assert s.table_fields()["lock"] == "Weak fix"
    text = " | ".join(f"{label}: {value}" for label, value in s.gnss_rows())
    assert "Locked, weak fix" in text and "Position unreliable (signal 9 dB-Hz, 4 satellites)" in text, text
    s.add_fix(fix(41.0005, -74.0005, snr_avg=23, sats=13, sats_used=13))
    assert s.weak_fix() == "signal 23 dB-Hz"
    s.add_fix(fix(41.0005, -74.0005, snr_avg=33, sats=5, sats_used=5))
    assert s.weak_fix() == "5 satellites"
    # A manual position has no GNSS fix to doubt
    s.position_source = "manual"
    assert s.weak_fix() is None
    # Restarting the average forgets the fixes so far
    s.position_source = "gnss"
    assert s.fix_n == 4
    s.restart_average()
    s.add_fix(fix(41.0010, -74.0005))
    assert s.fix_n == 1 and abs(s.fix_lat - 41.0010) < 1e-6


def test_locate_panel_readout():
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.nav_rail.set_active_mode(9)
    win.multi_device_manager.slots["slot_a"].is_connected = True
    win.sensor_net.ensure_sensor("slot_a").position_source = "gnss"
    for _ in range(5):
        win._on_gnss_updated("slot_a", fix(41.000500, -74.000500))
    lp = win.locate_panel
    assert not lp.gnss_lbl.isHidden() and "41.000500, -74.000500" in lp.gnss_lbl.text(), lp.gnss_lbl.text()
    assert "mean of 5 fixes" in lp.gnss_lbl.text() and "14 used of 21 in view" in lp.gnss_lbl.text()
    assert "Height" in lp.gnss_lbl.text() and "62 m" in lp.gnss_lbl.text() and "Locked" in lp.gnss_lbl.text()
    row = next(r for r in range(lp.sensor_table.rowCount()) if lp.sensor_table.item(r, 0).data(0x0100) == "slot_a")
    assert lp.sensor_table.item(row, 2).text() == "41.00050" and lp.sensor_table.item(row, 3).text() == "-74.00050"
    cell = lambda c: lp.sensor_table.item(row, c).text()
    assert cell(4) == "Locked", cell(4)
    # The periodic refresh shows the same position (it used to blank it until the next GNSS report)
    selector = lp.sensor_table.cellWidget(row, 1)
    win._refresh_locate(force=True)
    assert cell(2) == "41.00050" and cell(3) == "-74.00050"
    # A new fix rewrites the text and leaves the GNSS / Manual selector alone
    win._on_gnss_updated("slot_a", fix(41.000800, -74.000500))
    assert lp.sensor_table.cellWidget(row, 1) is selector and cell(2) != "41.00050"
    # An analyzer without a fix says so
    win.multi_device_manager.slots["slot_b"].is_connected = True
    win.sensor_net.ensure_sensor("slot_b").position_source = "gnss"
    win._on_gnss_updated("slot_b", dict(fix(0.0, 0.0), lock=False, sats=0, sats_used=0, sats_in_view=3))
    row_b = next(r for r in range(lp.sensor_table.rowCount()) if lp.sensor_table.item(r, 0).data(0x0100) == "slot_b")
    assert lp.sensor_table.item(row_b, 4).text() == "Searching" and lp.sensor_table.item(row_b, 2).text() == ""
    assert "3 satellites in view" in lp.gnss_lbl.text()
    # A weak fix shows in the table, and the button starts the averages again
    win._on_gnss_updated("slot_a", fix(41.000500, -74.000500, snr_avg=12, sats=4, sats_used=4))
    assert cell(4) == "Weak fix" and "tens of metres" in lp.sensor_table.item(row, 4).toolTip()
    assert "Position unreliable" in lp.gnss_lbl.text()
    assert win.sensor_net.sensors["slot_a"].fix_n > 5
    lp.restart_btn.click()
    assert win.sensor_net.sensors["slot_a"].fix_n == 0
    for _ in range(6):
        win._on_gnss_updated("slot_a", fix(41.000500, -74.000500))
    assert cell(4) == "Locked"

    # An analyzer that is unplugged is "Disconnected", not still "Searching" or "Locked"
    mdm = win.multi_device_manager
    for sid in ("slot_a", "slot_b"):
        mdm.slots[sid].is_enabled = True
        mdm._on_slot_connection(sid, False)
    win._on_all_connection_status(False)
    assert cell(4) == "Disconnected" and lp.sensor_table.item(row_b, 4).text() == "Disconnected", cell(4)
    assert cell(2) == "" and cell(3) == "", "no live position from an analyzer that is gone"
    text = lp.gnss_lbl.text()
    assert "disconnected" in text and "Searching" not in text and "Locked" not in text, text
    # Plugged back in where it was: it carries on from the mean of its earlier fixes
    mdm.slots["slot_a"].is_connected = True
    win._on_gnss_updated("slot_a", fix(41.000500, -74.000500))
    assert cell(4) == "Locked" and win.sensor_net.sensors["slot_a"].fix_n > 5
    win.close()


if __name__ == "__main__":
    for test in (test_fix_averaging, test_stale_first_report_is_not_a_fix, test_weak_fix_is_flagged,
                 test_locate_panel_readout):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All GNSS tests passed.")
