"""
test_dtv.py - Broadcast / DTV: occupied-channel detection, channel mask colours
and labels, and the transmitter lookup -> mask workflow in the main window.
No analyzer and no network are used.

    python testing/test_dtv.py
"""

import os
import sys
import time

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.dtv_detect import DTVOccupancyDetector

US_UHF = [(ch, 470.0 + (ch - 14) * 6.0, 476.0 + (ch - 14) * 6.0) for ch in range(14, 37)]
rng = np.random.default_rng(7)


def sweep(start=470.0, stop=608.0, points=921, floor=-105.0, stations=(), carriers=(), noisy=True, tilt_db=0.0):
    """
    A swept spectrum in dBm. stations: (channel, level dBm) noise-like blocks
    filling 5.4 of the channel's 6 MHz; carriers: (MHz, level dBm) narrowband.
    """
    f = np.linspace(start, stop, points)
    mw = 10 ** ((floor + tilt_db * (f - start) / (stop - start)) / 10)
    for ch, level in stations:
        f0 = 470.0 + (ch - 14) * 6.0
        mw = mw + np.where((f >= f0 + 0.3) & (f <= f0 + 5.7), 10 ** (level / 10), 0.0)
    if noisy:   # noise and noise-like signals: exponentially distributed power per point
        mw = mw * rng.exponential(1.0, points)
    for fc, level in carriers:
        mw = mw + 10 ** (level / 10) * np.exp(-0.5 * ((f - fc) / 0.08) ** 2)
    return f, 10 * np.log10(mw)


def test_lookup_prediction():
    from core.propagation import field_strength_dbuvm, worth_masking, is_low_power
    mask = lambda *a, **k: worth_masking(*a, **k)[0]
    # Full power: by power and distance
    assert mask(250.0, 5.0) and mask(57.8, 5.0) and mask(1000.0, 40.0)
    assert not mask(1000.0, 90.0) and not mask(655.0, 87.0), "a megawatt 55 miles out does not block a channel"
    assert not mask(20.0, 80.0)
    # Low power (at or under the low-power TV limit, whatever the licence class): only next door
    assert not mask(15.0, 5.0) and not mask(6.02, 5.0) and not mask(15.0, 14.0)
    assert not mask(10.0, 80.0), "10 kW at 50 miles"
    assert mask(15.0, 1.5) and mask(1.0, 1.0)
    assert is_low_power(15.0, 30) and not is_low_power(15.0, 9) and is_low_power(3.0, 9), "3 kW is the VHF limit"
    # Not on the air, and unknown power
    assert not mask(500.0, 5.0, 24, "APP") and mask(500.0, 5.0, 24, "LIC")
    assert mask("N/A", 20.0) and not mask(None, 45.0), "unknown power: by distance"
    assert worth_masking(100.0, None)[0]
    e = [field_strength_dbuvm(1.0, d) for d in (1, 3, 10, 30, 100, 300)]
    assert all(a > b for a, b in zip(e, e[1:])), "falls with distance"
    assert abs(field_strength_dbuvm(100.0, 20.0) - 80.0) < 0.1


def narrow_carrier(f, p, fc, level):
    """A land mobile carrier: narrower than the sweep's points resolve."""
    i = int(np.argmin(np.abs(f - fc)))
    p[i] = max(p[i], level)
    p[i + 1] = max(p[i + 1], level - 8.0)


def test_tband_scan():
    from core.tband_scan import TBandScanner
    tband = [c for c in US_UHF if 14 <= c[0] <= 20]

    def scene(keyed, points=4001):
        f, p = sweep(points=points, stations=((16, -70.0),), carriers=((497.0, -60.0),))   # TV on 16, a wireless mic in 18
        if keyed:
            for fc, lvl in ((471.3375, -78.0), (472.8125, -82.0), (478.5, -74.0)):
                narrow_carrier(f, p, fc, lvl)
        return f, p

    sc, t = TBandScanner(), 1000.0
    for i in range(3):
        r = sc.update(*scene(True), tband, now=t + 0.2 * i)
    assert r[16]["kind"] == "tv", "a station filling the channel is TV, not land mobile radio"
    assert r[14]["kind"] == "lmr" and r[14]["live"] and r[14]["carriers"] == 2, r[14]
    assert r[15]["kind"] == "lmr" and r[15]["carriers"] == 1
    assert r[18]["kind"] == "clear", "a wireless microphone is too wide to be land mobile radio"
    assert all(r[ch]["kind"] == "clear" for ch in (17, 19, 20))
    # Keyed off: the channel is held, then released
    r = sc.update(*scene(False), tband, now=t + 20)
    assert r[14]["kind"] == "lmr" and not r[14]["live"] and 19 < r[14]["last_heard_s"] < 21
    assert sc.update(*scene(False), tband, now=t + 90)[14]["kind"] == "clear"
    # Noise alone raises nothing, however long it runs
    sc = TBandScanner()
    for i in range(300):
        f, p = sweep(points=4001)
        r = sc.update(f, p, tband, now=t + 0.2 * i)
        assert all(v["kind"] == "clear" for v in r.values()), (i, r)
    # Coordinated carriers are not land mobile radio
    sc = TBandScanner()
    for i in range(3):
        r = sc.update(*scene(True), tband, ignore=[(471.2, 471.5), (472.7, 472.9)], now=t + 0.2 * i)
    assert r[14]["kind"] == "clear" and r[15]["kind"] == "lmr"
    # A sweep that does not cover the T-Band judges nothing; one that starts a little
    # inside channel 14 still judges it
    f, p = sweep(start=520.0, stop=608.0)
    assert TBandScanner().update(f, p, tband, now=t) == {}
    sc = TBandScanner()
    for i in range(3):
        f, p = sweep(start=470.3, stop=608.0, points=4001)
        narrow_carrier(f, p, 472.0, -75.0)
        r = sc.update(f, p, tband, now=t + 0.2 * i)
    assert r[14]["kind"] == "lmr", "channel 14 is judged although the sweep starts at 470.3"

    # A channel packed with land mobile carriers, through a coarse RBW, fills up like a TV
    # channel. Its traffic keys on and off where TV is steady, and it is taken as land
    # mobile outright where a lookup says so
    def coarse(k):
        on = [(470.2 + 0.23 * i, -62.0 - 3.0 * (i % 4)) for i in range(25) if ((k // 10) + i) % 3]   # a third keyed off, changing every 10 sweeps
        return sweep(points=461, stations=((16, -70.0),), carriers=on)                               # 0.3 MHz per point
    sc = TBandScanner()
    assert sc.update(*coarse(0), tband, now=t, known_lmr={14})[14]["kind"] == "lmr", "the lookup settles it at once"
    sc = TBandScanner()
    for k in range(60):
        r = sc.update(*coarse(k), tband, now=t + 0.2 * k)
        assert r[16]["kind"] == "tv", "a real TV station stays TV"
    assert r[14]["kind"] == "lmr" and r[14]["carriers"] is None, r[14]
    # TV through multipath is ragged but steady: still TV
    f0_, p0_ = sweep(points=461, stations=((16, -70.0),), noisy=False)
    ripple = 6.0 * np.sin(2 * np.pi * (f0_ - 482.0) / 1.3)
    sc = TBandScanner()
    for k in range(60):
        f, p = sweep(points=461, stations=((16, -70.0),))
        r = sc.update(f, np.where((f >= 482.3) & (f <= 487.7), p + ripple, p), tband, now=t + 0.2 * k)
    assert r[16]["kind"] == "tv", r[16]


def occupied(results):
    return sorted(ch for ch, r in results.items() if r["occupied"])


def after_sweeps(n, det=None, **kw):
    """The detector's answer after n sweeps of the same scene."""
    det = det or DTVOccupancyDetector()
    for _ in range(n):
        f, p = sweep(**kw)
        res = det.update(f, p, US_UHF)
    return res


def test_detects_stations_on_first_sweep():
    det = DTVOccupancyDetector()
    # 470-608 MHz: channel 36 ends exactly at the last sweep point (this crashed the old detector)
    f, p = sweep(stations=((22, -60.0), (26, -85.0), (36, -70.0), (14, -88.0)))
    res = det.update(f, p, US_UHF)
    assert len(res) == 23, "every channel inside the sweep is judged, including the last"
    assert occupied(res) == [14, 22, 26, 36], occupied(res)
    assert abs(res[22]["floor_dbm"] - -106.6) < 2.0          # median of noise is 1.6 dB under its mean
    assert 40 < res[22]["excess_db"] < 50 and res[22]["level_dbm"] > -65
    # A station only 10 dB above the noise needs a few sweeps' averaging, not a lower threshold
    assert occupied(after_sweeps(6, stations=((22, -60.0), (29, -95.0)))) == [22, 29]


def test_ignores_wireless_microphones_and_partial_signals():
    det = DTVOccupancyDetector()
    mics = [(500.2 + 0.4 * i, -50.0) for i in range(8)]       # eight strong carriers in channel 19
    f, p = sweep(stations=((30, -70.0),), carriers=mics)
    res = det.update(f, p, US_UHF)
    assert occupied(res) == [30], "narrowband carriers do not make a channel a TV channel"
    # A wideband signal over only the lower half of channel 20
    f, p = sweep()
    p = np.where((f >= 506.0) & (f <= 509.0), -70.0, p)
    assert 20 not in occupied(DTVOccupancyDetector().update(f, p, US_UHF))


def test_floor_follows_rbw_gain_and_tilt():
    # The same stations 30 dB lower overall (another RBW / attenuator / antenna): same answer
    for floor in (-80.0, -110.0, -125.0):
        res = after_sweeps(6, floor=floor, stations=((18, floor + 20), (31, floor + 11)))
        assert occupied(res) == [18, 31], floor
    # A noise floor that climbs 12 dB across the band does not read as occupied channels
    f, p = sweep(tilt_db=12.0, stations=((16, -80.0),))
    assert occupied(DTVOccupancyDetector().update(f, p, US_UHF)) == [16]
    # Fine and coarse sweeps
    for points in (300, 4001):
        f, p = sweep(points=points, stations=((25, -75.0),))
        assert occupied(DTVOccupancyDetector().update(f, p, US_UHF)) == [25], points
    # A smooth trace (peak detector, video averaging) needs no allowance for noise
    f, p = sweep(noisy=False, stations=((25, -98.0),))
    assert occupied(DTVOccupancyDetector().update(f, p, US_UHF)) == [25]


def test_no_false_alarms_and_stability():
    det = DTVOccupancyDetector()
    history = []
    for _ in range(40):
        f, p = sweep(stations=((21, -97.0),))                  # channel 21 about 8 dB up: borderline
        history.append(occupied(det.update(f, p, US_UHF)))
    assert all(set(h) <= {21} for h in history), "an empty channel is never reported occupied"
    flips = sum(a != b for a, b in zip(history, history[1:]))
    assert flips <= 4, f"a borderline channel should not flicker ({flips} changes in 40 sweeps)"


def test_partial_and_narrow_sweeps_are_not_judged():
    det = DTVOccupancyDetector()
    f, p = sweep(start=473.0, stop=605.0, stations=((14, -60.0), (36, -60.0)))
    res = det.update(f, p, US_UHF)
    assert 14 not in res and 36 not in res and len(res) == 21, "half-swept channels keep their last state"
    # One channel wide: the floor cannot be told from a signal
    f, p = sweep(start=500.0, stop=506.0, points=400, stations=((19, -60.0),))
    assert det.update(f, p, US_UHF) == {}
    # ...unless a fixed threshold is given
    res = det.update(f, p, US_UHF, threshold_dbm=-80.0)
    assert occupied(res) == [19] and res[19]["floor_dbm"] is None
    f, p = sweep(stations=((22, -60.0), (26, -90.0)))
    assert occupied(DTVOccupancyDetector().update(f, p, US_UHF, threshold_dbm=-80.0)) == [22]
    assert det.update(f[:3], p[:3], US_UHF) == {}


def test_styles_and_labels():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.widgets.channel_style import channel_kind, mask_brush_pen, channel_label_html

    assert channel_kind("dtv") == "dtv" and channel_kind("default") == "dtv"
    assert channel_kind("ch37") == "ch37" and channel_kind("lmr_smr") == "lmr"
    assert channel_kind("dtv", is_public_safety=True) == "lmr" and channel_kind("uplink") == "uplink"

    def rgb(kind):
        c = mask_brush_pen(kind)[0].color()
        return c.red(), c.green(), c.blue()

    r, g, b = rgb("lmr")
    assert r > 200 and g < 100 and b < 100, "LMR is red"
    r, g, b = rgb("dtv")
    assert b > 200 and r < 100, "TV channels are blue"
    r, g, b = rgb("ch37")
    assert abs(r - g) < 25 and abs(g - b) < 30, "Channel 37 is grey"

    info = {"call": "WGBH-TV", "place": "Boston, MA", "detail": "1000 kW · 9 mi", "more": 1}
    wide = channel_label_html(160, "dtv", "19", 500, 506, info)
    for text in ("DTV 19", "WGBH-TV +1", "Boston, MA", "1000 kW"):
        assert text in wide, text
    narrow = channel_label_html(30, "dtv", "19", 500, 506, info)
    assert "WGBH-TV" in narrow and "Boston" not in narrow, "a narrow mask keeps the call sign only"
    assert channel_label_html(15, "dtv", "19", 500, 506, info) == ""
    assert "500 - 506 MHz" in channel_label_html(160, "dtv", "19", 500, 506)
    assert "CH 37 - OFF LIMITS" in channel_label_html(160, "ch37", "37", 608, 614)
    assert "LMR 14" in channel_label_html(160, "lmr", "14", 470, 476)


STATIONS = [
    {"call_sign": "WGBH-TV", "channel": 19, "erp": 1000.0, "city": "Boston", "state": "MA", "distance_km": 14.5,
     "facility_id": "1", "is_public_safety": False},
    {"call_sign": "WLVI", "channel": 22, "erp": 550.0, "city": "Cambridge", "state": "MA", "distance_km": 16.0,
     "facility_id": "2", "is_public_safety": False},
    {"call_sign": "W22XX-D", "channel": 22, "erp": 0.015, "city": "Lowell", "state": "MA", "distance_km": 8.0,
     "facility_id": "3", "is_public_safety": False},
    {"call_sign": "WUNI", "channel": 27, "erp": 300.0, "city": "Marlborough", "state": "MA", "distance_km": 40.0,
     "facility_id": "4", "is_public_safety": False},
    {"call_sign": "LMR Boston, MA", "channel": 14, "erp": "N/A", "distance_km": 3.0, "is_public_safety": True},
    {"call_sign": "LMR Boston, MA", "channel": 16, "erp": "N/A", "distance_km": 3.0, "is_public_safety": True},
]


def test_lookup_masks_and_detection_in_main_window():
    import tempfile
    from PyQt6.QtCore import QSettings, Qt
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.is_sweeping = True
    if win.current_region != "North America":
        win.change_region("North America")
    panel, sv, table = win.dtv_panel, win.spectrum_view, win.dtv_panel.stations_table

    def mask_rgb(ch):
        c = sv.channel_masks[ch].brush.color()
        return c.red(), c.green(), c.blue()

    def shown(ch):
        return ch in sv.channel_masks and sv.channel_masks[ch].isVisible()

    def row_checked(row):
        return panel.mask_checkbox(row).isChecked()

    # Channel 37 is masked grey from the start: it is off limits in the US
    assert win.active_channels[37] and shown(37)
    r, g, b = mask_rgb(37)
    assert abs(r - g) < 25 and abs(g - b) < 30
    assert not shown(19)

    # A lookup masks every listed channel: TV blue with the station on it, LMR red
    win._on_station_lookup_finished(STATIONS, {"source": "live", "fetched_at": time.time(), "error": None})
    assert table.rowCount() == 6 and all(row_checked(r) for r in range(6))
    assert [shown(ch) for ch in (14, 16, 19, 22, 27)] == [True] * 5 and not shown(30)
    assert mask_rgb(19)[2] > 200 and mask_rgb(19)[0] < 100, "TV masks are blue"
    assert mask_rgb(14)[0] > 200 and mask_rgb(14)[2] < 100, "LMR masks are red"
    assert win.station_info[19] == {"call": "WGBH-TV", "place": "Boston, MA", "detail": "1000 kW · 9 mi", "more": 0}
    assert win.station_info[22]["call"] == "WLVI" and win.station_info[22]["more"] == 1, \
        "of two stations on a channel the mask names the stronger"
    assert win.station_info[14]["call"] == "PUBLIC SAFETY" and "Boston, MA" in win.station_info[14]["place"]
    assert [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())] == \
        ["Mask", "Ch", "Station", "Live", "Dist", "ERP"]
    assert table.item(0, panel.COL_STATION).text() == "WGBH-TV" and table.item(0, panel.COL_CH).text() == "19"
    assert table.item(0, panel.COL_DIST).text() == "9 mi" and table.item(0, panel.COL_ERP).text() == "1000 kW"
    assert table.item(4, panel.COL_STATION).text() == "LMR Boston"
    assert table.cellWidget(0, panel.COL_MASK) is not None, "every row has a Mask checkbox"
    sv.plot_widget.resize(1400, 400)
    sv.set_view_range(494.0, 512.0)                      # zoom in: the mask is wide enough for the details
    app.processEvents()
    sv._update_text_items()
    label = sv.channel_text_items[19].toHtml()
    assert "WGBH-TV" in label and "Boston, MA" in label and "DTV 19" in label, label

    # Toggle masks: a row's checkbox, both rows of a shared channel, and all at once
    panel.mask_checkbox(0).click()
    assert not shown(19) and not win.active_channels[19]
    panel.mask_checkbox(0).click()
    assert shown(19)
    panel.mask_checkbox(0).setChecked(False)
    panel.mask_checkbox(1).setChecked(False)                                # WLVI, channel 22
    assert not shown(22) and not row_checked(2), "the other station on channel 22 follows"
    panel.masks_off_btn.click()
    assert not any(shown(ch) for ch in (14, 16, 19, 22, 27)) and not any(row_checked(r) for r in range(6))
    assert shown(37), "Channel 37 is not one of the looked-up transmitters"
    panel.masks_on_btn.click()
    assert all(shown(ch) for ch in (14, 16, 19, 22, 27)) and all(row_checked(r) for r in range(6))
    win._on_channel_bar_clicked(27, 548.0, 554.0)                           # the channel bar toggles too
    assert not shown(27) and not row_checked(3)
    win._on_channel_bar_clicked(27, 548.0, 554.0)

    # Auto DTV Detect: of the listed stations only 19 and 22 are on the air here, and 30 is unlisted
    panel.dtv_detect_btn.setChecked(True)
    assert not sv.threshold_line.isVisible(), "the threshold line is shown only when its box is ticked"
    f, p = sweep(stations=((19, -62.0), (22, -80.0), (30, -75.0)), carriers=((471.5, -60.0), (483.2, -55.0)))
    win._process_dtv_detect(f * 1e6, p)
    # Automatic mode: the line shows the detector's own level, noise floor + margin;
    # dragging it sets the margin (the mode stays Automatic)
    assert panel.show_thresh_cb.isEnabled()
    panel.show_thresh_cb.setChecked(True)
    assert sv.threshold_line.isVisible() and sv.threshold_line.movable
    sv.thresholdChanged.emit(win._dtv_auto_floor + 14.2)                   # as dragging the line does
    assert panel.margin_spin.value() == 14.0 and panel.auto_threshold
    panel.margin_spin.setValue(6.0)
    win._dtv_last_run = 0.0
    win._process_dtv_detect(f * 1e6, p)
    win._sync_dtv_threshold_line()
    assert abs(sv.threshold_line.value() - (-106.6 + 6.0)) < 2.0, sv.threshold_line.value()
    assert sv.threshold_line.label.toPlainText().startswith("DTV: FLOOR + 6 dB: -10"), sv.threshold_line.label.toPlainText()
    panel.margin_spin.setValue(10.0)
    win._process_dtv_detect(f * 1e6, p)
    win._dtv_last_status_time = 0.0
    win._dtv_last_run = 0.0
    win._process_dtv_detect(f * 1e6, p)
    win._sync_dtv_threshold_line()
    assert abs(sv.threshold_line.value() - (-106.6 + 10.0)) < 2.0
    panel.margin_spin.setValue(6.0)
    win._dtv_last_run = 0.0
    win._process_dtv_detect(f * 1e6, p)
    panel.show_thresh_cb.setChecked(False)
    assert not sv.threshold_line.isVisible()
    assert [shown(ch) for ch in (19, 22, 30)] == [True] * 3 and not shown(27), "27 is listed but not received"
    assert shown(14) and shown(16), "LMR channels stay masked: they are not judged as TV channels"
    assert shown(37) and win.active_channels[37], "Channel 37 stays masked whatever is measured"
    assert row_checked(0) and not row_checked(3)
    assert "3 occupied" in panel.detect_status_lbl.text() and "noise floor" in panel.detect_status_lbl.text()
    assert table.item(0, panel.COL_LIVE).text().startswith("+") and table.item(3, panel.COL_LIVE).text() == "clear"
    assert "dBm" in table.item(0, panel.COL_LIVE).toolTip()
    # A mask set by hand while detecting is kept
    panel.mask_checkbox(0).setChecked(False)
    win._dtv_last_run = 0.0
    win._process_dtv_detect(f * 1e6, p)
    assert not shown(19)
    # The sweep handler itself runs the detector without errors (the old one raised on every sweep)
    win._dtv_last_run = 0.0
    win._on_sweep_data(f * 1e6, p.astype(np.float32))

    # Fixed threshold: the line is the level set, and dragging it sets the level
    panel.detect_mode_combo.setCurrentIndex(1)
    assert sv.threshold_line.isVisible() and sv.threshold_line.movable and sv.threshold_line.value() == -70.0
    assert sv.threshold_line.label.toPlainText() == "DTV THRESH: -70.0 dBm"
    assert panel.threshold_spin.isEnabled() and panel.margin_spin.isEnabled(), "both stay editable"
    panel.threshold_spin.setValue(-82.0)
    assert sv.threshold_line.value() == -82.0
    sv.thresholdChanged.emit(-64.0)                                        # as dragging the line does
    assert panel.threshold_spin.value() == -64.0
    panel.show_thresh_cb.setChecked(False)
    assert not sv.threshold_line.isVisible()
    panel.show_thresh_cb.setChecked(True)
    assert sv.threshold_line.isVisible()
    panel.dtv_detect_btn.setChecked(False)
    # With detection off, the automatic line is read off the latest sweep
    panel.detect_mode_combo.setCurrentIndex(0)
    assert sv.threshold_line.isVisible() and sv.threshold_line.movable
    assert abs(sv.threshold_line.value() - (-106.6 + 6.0)) < 2.0
    # Editing a value selects the mode it belongs to
    panel.threshold_spin.setValue(-75.0)
    assert not panel.auto_threshold and sv.threshold_line.value() == -75.0
    panel.margin_spin.setValue(9.0)
    assert panel.auto_threshold
    panel.margin_spin.setValue(6.0)
    panel.show_thresh_cb.setChecked(False)

    # A lookup masks the stations strong enough to block a channel, judged from the licence:
    # full power by power and distance, low power only next door, nothing unlicensed
    panel.dtv_detect_btn.setChecked(False)
    far = [{"call_sign": "WFAR", "channel": 30, "erp": 10.0, "distance_km": 80.0, "is_public_safety": False},
           {"call_sign": "WBIG", "channel": 33, "erp": 1000.0, "distance_km": 40.0, "is_public_safety": False},
           {"call_sign": "W35ZZ", "channel": 35, "erp": "N/A", "distance_km": 60.0, "is_public_safety": False},
           {"call_sign": "WLOW-LD", "channel": 31, "erp": 15.0, "distance_km": 5.0, "is_public_safety": False},
           {"call_sign": "WNEW", "channel": 34, "erp": 500.0, "distance_km": 5.0, "status": "APP", "is_public_safety": False}]
    win._on_station_lookup_finished(STATIONS + far, {"source": "live", "fetched_at": time.time(), "error": None})
    assert [shown(ch) for ch in (14, 16, 19, 22, 27, 33)] == [True] * 6, "strong stations and LMR"
    assert not any(shown(ch) for ch in (30, 31, 34, 35)), "far, low power, not licensed, unknown power"
    assert table.rowCount() == 11 and not row_checked(6) and row_checked(7), "listed all the same"
    assert "4 of 8" in panel.detect_status_lbl.text(), panel.detect_status_lbl.text()
    assert table.columnWidth(panel.COL_CH) >= 44, "wide enough for two digits"

    # Scan T-Band: land mobile radio (narrow carriers) is told from a TV station, and only
    # the land mobile channels go red
    win.lmr_stations, win.dtv_stations = {}, {}
    for ch in range(14, 21):
        win._set_channel_mask(ch, False)
    panel.tband_scan_btn.setChecked(True)
    assert not any(shown(ch) for ch in range(14, 21)), "nothing is flagged before anything is heard"
    for i in range(4):
        f2, p2 = sweep(points=4001, stations=((16, -70.0),))
        narrow_carrier(f2, p2, 471.3375, -78.0); narrow_carrier(f2, p2, 478.5, -74.0)
        win._tband_last_run = 0.0
        win._process_tband_scan(f2 * 1e6, p2)
    assert win._tband_lmr == {14, 15}, win._tband_lmr
    assert mask_rgb(14)[0] > 200 and mask_rgb(15)[0] > 200, "land mobile channels are red"
    assert not shown(16), "the scan reports the TV station but never touches a TV mask"
    assert not any(shown(ch) for ch in (17, 18, 19, 20))
    status = panel.tband_status_lbl.text()
    assert "land mobile radio on ch 14, 15" in status and "TV on ch 16" in status, status

    def scan_pass():
        f3, p3 = sweep(points=4001, stations=((16, -70.0),))
        narrow_carrier(f3, p3, 471.3375, -78.0); narrow_carrier(f3, p3, 478.5, -74.0)
        win._tband_last_run = 0.0
        win._process_tband_scan(f3 * 1e6, p3)
        return f3, p3
    # The last click wins: a mask unticked by hand stays off while the scan goes on hearing it
    win._on_channel_bar_clicked(14, 470.0, 476.0)
    scan_pass()
    assert not shown(14) and shown(15) and 14 in win._tband_lmr
    assert "ch 14 left unmasked as you set it" in panel.tband_status_lbl.text(), panel.tband_status_lbl.text()
    win._on_channel_bar_clicked(14, 470.0, 476.0)
    assert shown(14)
    # Auto DTV Detect alongside: it finds the TV station and leaves the flagged channels alone
    panel.dtv_detect_btn.setChecked(True)
    for _ in range(3):
        f3, p3 = scan_pass()
        win._dtv_last_run = 0.0
        win._process_dtv_detect(f3 * 1e6, p3)
    assert shown(16) and mask_rgb(16)[2] > 200, "the detector, not the scan, masks the TV station"
    assert shown(14) and shown(15) and mask_rgb(15)[0] > 200, "flagged channels are not judged as TV channels"
    # A lookup in the middle keeps the scan's flags, and detection keeps the TV masks
    win._on_station_lookup_finished(STATIONS[:2], {"source": "live", "fetched_at": time.time(), "error": None})
    assert shown(15) and mask_rgb(15)[0] > 200 and shown(16)
    win.lmr_stations, win.dtv_stations = {}, {}
    panel.dtv_detect_btn.setChecked(False)
    assert shown(16), "stopping detection leaves the masks as they are"
    win._set_channel_mask(16, False)
    panel.tband_scan_btn.setChecked(False)
    assert not shown(14) and not shown(15)

    # Columns of both tables can be resized and reordered, and the layout is remembered
    for tbl in (table, panel.zones_table):
        header = tbl.horizontalHeader()
        assert all(header.sectionResizeMode(c) == header.ResizeMode.Interactive for c in range(tbl.columnCount() - 1))
        assert header.sectionsMovable()
    table.setColumnWidth(panel.COL_STATION, 150)
    table.horizontalHeader().moveSection(panel.COL_ERP, 3)
    panel.zones_table.setColumnWidth(0, 95)
    win._save_table_columns()
    from ui.widgets.panels.dtv_panel import DTVPanel
    fresh = DTVPanel()
    assert fresh.stations_table.columnWidth(fresh.COL_STATION) != 150
    fresh.stations_table.horizontalHeader().restoreState(win.settings.value("dtv_station_columns_v2"))
    fresh.zones_table.horizontalHeader().restoreState(win.settings.value("dtv_zone_columns"))
    assert fresh.stations_table.columnWidth(fresh.COL_STATION) == 150
    assert fresh.stations_table.horizontalHeader().visualIndex(fresh.COL_ERP) == 3
    assert fresh.zones_table.columnWidth(0) == 95

    # Without a lookup the table lists the swept channels
    win.change_region("UK")
    assert table.rowCount() == 0 and 37 not in sv.channel_masks
    win.change_region("North America")
    assert shown(37)
    panel.detect_mode_combo.setCurrentIndex(0)
    panel.dtv_detect_btn.setChecked(True)
    win._process_dtv_detect(f * 1e6, p)
    assert table.rowCount() == 23 and table.item(5, panel.COL_CH).text() == "19" and row_checked(5)
    assert [shown(ch) for ch in (19, 22, 30)] == [True] * 3 and not shown(14)
    win.close()


if __name__ == "__main__":
    tests = [test_detects_stations_on_first_sweep, test_ignores_wireless_microphones_and_partial_signals,
             test_floor_follows_rbw_gain_and_tilt, test_no_false_alarms_and_stability,
             test_partial_and_narrow_sweeps_are_not_judged, test_styles_and_labels, test_tband_scan,
             test_lookup_prediction,
             test_lookup_masks_and_detection_in_main_window]
    only = sys.argv[1:]
    for test in tests:
        if only and test.__name__ not in only:
            continue
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All DTV tests passed.")
