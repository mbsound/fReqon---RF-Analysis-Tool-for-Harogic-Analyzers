"""
test_emission_mask.py - ETSI transmit masks around coordinated carriers: the mask
shapes, which mask a device gets, what breaks a mask, and intruder detection in the
main window with the masks on (no analyzer needed).

    python testing/test_emission_mask.py
"""

import os
import sys
import tempfile
import time

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.emission_mask import template_db, mask_kind, limit_line

F = np.arange(498e6, 502e6, 5e3)
RNG = np.random.default_rng(0)


def carrier(fc, lvl, bw=200e3):
    """A digital carrier that stays well inside the ETSI digital mask."""
    x = np.abs(F - fc) / bw
    return lvl + np.where(x <= 0.45, 0.0, np.maximum(-80.0, -30.0 - (x - 0.45) * 60.0))


def add(*parts):
    return 10 * np.log10(sum(10 ** (p / 10) for p in parts))


def noise(level=-110.0):
    return level + RNG.normal(0, 1, len(F))


def test_mask_shapes():
    # EN 300 422-1 V2.2.1 figures 1-3: offset in units of B -> dB relative to the carrier
    assert list(template_db("analogue", [0.0, 0.5, 0.75, 1.0, 2.5])) == [0.0, 0.0, -70.0, -80.0, -80.0]
    assert list(template_db("digital", [0.0, 0.5, 1.125, 1.75, 2.5])) == [0.0, 0.0, -55.0, -80.0, -80.0]
    assert list(template_db("wmas", [0.5, 0.75, 1.0, 2.5])) == [0.0, -50.0, -60.0, -60.0]
    assert template_db("digital", [0.5001])[0] < -29.9 and template_db("analogue", [0.5001])[0] < -59.9
    assert np.isneginf(template_db("digital", [2.6])[0])
    for device, kind in (("Shure AD4Q-A", "digital"), ("Shure ULXD4", "digital"), ("Sennheiser EW-D", "digital"),
                         ("Shure ADX1", "digital"), ("Shure PSM1000 P10T", "analogue"), ("Shure UR4D", "analogue"),
                         ("Sennheiser SR 2050 IEM", "analogue"), ("Sennheiser EW 300 G4", "analogue")):
        assert mask_kind(device) == kind, (device, mask_kind(device))
    assert mask_kind("Sennheiser Spectera", 6e6) == "wmas" and mask_kind("x", 200e3, is_wmas=True) == "wmas"


def test_what_breaks_a_mask():
    cs = [{"freq_hz": 500e6, "bw_hz": 200e3, "name": "Lead", "device": "Shure AD4Q"}]
    own = add(carrier(500e6, -50), noise())
    limit, masks = limit_line(F, own, cs, -90.0, 6.0, 10e3)
    m = masks[0]
    assert m["kind"] == "digital" and abs(m["ref_dbm"] - -50.0) < 0.5 and m["at_hz"] is None, m
    assert np.isinf(limit[np.abs(F - 500e6) < 100e3]).all()            # the channel itself is the carrier's
    assert limit[np.abs(F - 501.5e6) < 1e3][0] == -90.0                 # far away: the plain threshold
    assert abs(limit[np.abs(F - 500.2e6) < 1e3][0] - (-50 + 6 - 30 - 50 * (0.1 - 0.02) / 0.25)) < 0.6   # on the skirt (20 kHz pad)
    # A hotter transmitter 120 kHz off the centre: its peak is inside the channel, its skirt is not
    limit, masks = limit_line(F, add(own, carrier(500.12e6, -42)), cs, -90.0, 6.0, 10e3)
    m = masks[0]
    assert m["excess_db"] > 20 and 500.1e6 < m["at_hz"] < 500.5e6, (m["excess_db"], m["at_hz"])
    assert 500.02e6 < m["peak_hz"] < 500.2e6, m["peak_hz"]            # the strongest point in the channel is off its centre
    # A weaker one whose spectrum stays inside the channel cannot be told from the carrier ...
    limit, masks = limit_line(F, add(own, carrier(500.02e6, -70)), cs, -90.0, 6.0, 10e3)
    assert masks[0]["at_hz"] is None
    # ... but 50 kHz off, its top pokes out past the channel edge, above the skirt allowed there
    limit, masks = limit_line(F, add(own, carrier(500.05e6, -70)), cs, -90.0, 6.0, 10e3)
    assert masks[0]["at_hz"] is not None and 500.12e6 <= masks[0]["at_hz"] <= 500.16e6, masks[0]["at_hz"]
    # A separate weak carrier beside it, above the mask's skirt there
    limit, masks = limit_line(F, add(own, carrier(500.35e6, -80, 25e3)), cs, -90.0, 6.0, 10e3)
    assert masks[0]["at_hz"] is not None and abs(masks[0]["at_hz"] - 500.35e6) < 30e3
    # The analogue mask is much tighter: the same digital carrier breaks it
    limit, masks = limit_line(F, own, cs, -100.0, 6.0, 10e3, force_kind="analogue")
    assert masks[0]["kind"] == "analogue" and masks[0]["at_hz"] is not None
    # A carrier that is off the air has no mask; its channel is still its own
    limit, masks = limit_line(F, noise(), cs, -90.0, 6.0, 10e3)
    assert masks == [] and np.isinf(limit[np.abs(F - 500e6) < 100e3]).all()
    # ... unless its shape is asked for, to show what it will claim (it limits nothing)
    limit2, masks = limit_line(F, noise(), cs, -90.0, 6.0, 10e3, idle_top_dbm=-20.0)
    assert len(masks) == 1 and not masks[0]["on_air"] and masks[0]["y_dbm"].max() == -20.0 and masks[0]["y_dbm"].min() == -100.0
    assert np.array_equal(limit, limit2)
    # Neighbours: each one's channel is exempt from the other's mask
    cs2 = cs + [{"freq_hz": 500.4e6, "bw_hz": 200e3, "name": "BV", "device": "Shure AD4Q"}]
    limit, masks = limit_line(F, add(own, carrier(500.4e6, -48), noise()), cs2, -90.0, 6.0, 10e3)
    assert len(masks) == 2 and all(m["at_hz"] is None for m in masks), [m["excess_db"] for m in masks]
    # A sweep coarser than the channel still gives a (wide) mask and no false break
    coarse = F[::30]
    limit, masks = limit_line(coarse, own[::30], cs, -90.0, 6.0, 150e3)
    assert len(masks) <= 1 and all(m["at_hz"] is None for m in masks)


def test_detection_in_main_window():
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.is_sweeping = True
    tp, sv = win.threats_panel, win.spectrum_view
    sv.set_soundbase_masks([{"id": "c1", "name": "Lead", "f_start_mhz": 499.9, "f_stop_mhz": 500.1,
                             "model": "AD4Q-A", "manufacturer": "Shure", "color": "#38bdf8"}])
    tp.intruder_thresh_spin.setValue(-90.0)
    # ETSI masks are the default, and are drawn before anything is swept or detection is on:
    # the shape of each carrier's mask, dashed, one division under the top of the plot
    # (the window starts from the user's saved settings: put the two mask settings back to their defaults)
    tp.carrier_mask_combo.setCurrentIndex(tp.carrier_mask_combo.findData("auto"))
    tp.carrier_mask_margin_spin.setValue(6.0)
    assert tp.carrier_mask_margin_spin.isEnabled() and "headroom" in tp.carrier_mask_margin_lbl.toolTip()
    win.is_sweeping = False
    win.sweep_panel.start_spin.setValue(498.0); win.sweep_panel.stop_spin.setValue(502.0)
    win._draw_carrier_masks()
    x, y = sv._emission_mask_items["idle"].getData()
    top = sv.ref_level - win.sweep_panel.scale_div
    assert x is not None and len(x) > 50 and abs(np.nanmax(y) - top) < 0.01, (None if x is None else len(x))
    edge = int(np.nanargmin(np.abs(x - 500.11)))                 # just outside the channel: the digital mask's -30 dB step
    assert -40.0 < y[edge] - top < -29.0, y[edge] - top
    assert abs(np.nanmin(y) - (top - 80.0)) < 0.01 and abs(np.nanmin(x) - 499.5) < 0.01 and abs(np.nanmax(x) - 500.5) < 0.01
    win.is_sweeping = True
    # While sweeping with detection off, the mask sits on the carrier
    win._mask_draw_time = 0.0
    win._draw_masks_without_detection(F.copy(), add(carrier(500e6, -50), noise()).astype(np.float32))
    x, y = sv._emission_mask_items[False].getData()
    assert x is not None and len(x) > 10 and abs(np.nanmax(y) - -44.0) < 1.0
    assert len(sv._emission_mask_items["idle"].getData()[0] or []) == 0
    tp.enable_btn.setChecked(True)
    win._rbw_by_slot[win.multi_device_manager.focused_slot_id] = 10e3

    def feed(power):
        win.intruders.clear()
        win._mask_breaks.clear()
        win._mask_draw_time = 0.0
        win._process_intruder_sweep(F.copy(), power.astype(np.float32))
        return sorted(win.intruders)

    own = add(carrier(500e6, -50), noise())
    # Channel only: the carrier's skirt beside its channel is above the threshold and gets listed
    tp.carrier_mask_combo.setCurrentIndex(tp.carrier_mask_combo.findData("channel"))
    assert feed(own) == [] or all(abs(k - 500.0) < 0.3 for k in feed(own))
    # ETSI: the carrier alone lists nothing, and its mask is drawn
    tp.carrier_mask_combo.setCurrentIndex(tp.carrier_mask_combo.findData("auto"))
    assert win.settings.value("carrier_mask") == "auto"
    assert feed(own) == [], win.intruders
    x, y = sv._emission_mask_items[False].getData()
    assert x is not None and len(x) > 10 and abs(np.nanmax(y) - -44.0) < 1.0        # carrier level + 6 dB
    assert sv._emission_mask_items[True].getData()[0] is None or len(sv._emission_mask_items[True].getData()[0]) == 0
    # An intruder 120 kHz off the centre: listed where it breaks the mask, with the reason
    keys = feed(add(own, carrier(500.12e6, -42)))
    assert len(keys) == 1 and 500.1 < keys[0] < 500.5, keys
    note = win._mask_break_note(keys[0], {"details": "x"})
    assert "Breaks the ETSI digital mask of Lead (500.000 MHz)" in note["details"] and "kHz off its centre" in note["details"], note
    assert len(sv._emission_mask_items[True].getData()[0]) > 10, "the broken mask is drawn in the alert colour"
    # A carrier well away from any mask is listed as before
    keys = feed(add(own, carrier(501.3e6, -70, 25e3)))
    assert len(keys) == 1 and abs(keys[0] - 501.3) < 0.02, keys
    # Back to channel only: the masks are taken off the plot
    tp.carrier_mask_combo.setCurrentIndex(tp.carrier_mask_combo.findData("channel"))
    assert not tp.carrier_mask_margin_spin.isEnabled(), "the margin belongs to the ETSI masks"
    feed(own)
    assert sv._emission_mask_items[False].getData()[0] is None or len(sv._emission_mask_items[False].getData()[0]) == 0
    win.close()


if __name__ == "__main__":
    for test in (test_mask_shapes, test_what_breaks_a_mask, test_detection_in_main_window):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All emission mask tests passed.")
