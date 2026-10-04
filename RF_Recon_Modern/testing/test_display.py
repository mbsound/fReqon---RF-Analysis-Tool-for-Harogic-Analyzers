"""
test_display.py - Spectrum display behaviour of the main window (no analyzer needed).

    python testing/test_display.py
"""

import os
import sys
import tempfile
import time

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def test_auto_ref_level():
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.is_sweeping = True
    sp, sv = win.sweep_panel, win.spectrum_view

    def y_range():
        lo, hi = sv.plot_widget.getViewBox().viewRange()[1]
        return round(lo, 3), round(hi, 3)

    def feed(peak_dbm):
        f = np.linspace(470e6, 608e6, 1000)
        p = np.full(1000, -105.0, dtype=np.float32)
        p[400:420] = peak_dbm
        win._last_render_time = 0.0
        win._on_sweep_data(f, p)

    # Nothing swept yet: the button says so and leaves the level alone
    assert sp.ref_level_spin.value() == 0.0 and sp.scale_div == 10.0
    sp.auto_ref_btn.click()
    assert sp.ref_level_spin.value() == 0.0
    assert "no sweep" in win.top_bar.dev_label.fullText()

    # With only the live trace shown (Max Hold off, as at startup) the button works:
    # the top of the axis goes to the graticule line above the peak, with headroom
    feed(-38.0)
    assert not sp.trace_rows["Max. Hold"]["cb"].isChecked()
    sp.auto_ref_btn.click()
    assert sp.ref_level_spin.value() == -30.0, sp.ref_level_spin.value()
    assert y_range() == (-130.0, -30.0), y_range()
    assert sv.ref_level == -30.0

    # A peak right under a graticule line still gets half a division of headroom
    feed(-31.0)
    sp.auto_ref_btn.click()
    assert sp.ref_level_spin.value() == -20.0

    # Changing Scale / Div runs it: the signal stays in view, just below the top
    feed(-38.0)
    for index, div, ref in ((1, 5.0, -35.0), (2, 2.0, -36.0), (3, 1.0, -37.0), (0, 10.0, -30.0)):
        sp.scale_div_combo.setCurrentIndex(index)
        assert sp.scale_div == div and sp.ref_level_spin.value() == ref, (div, sp.ref_level_spin.value())
        assert y_range() == (ref - 10 * div, ref), y_range()
        assert ref - div <= -38.0 < ref, "the peak is inside the top division, not on the line"

    # While Max Hold is shown, its peaks count too
    sp.scale_div_combo.setCurrentIndex(0)
    sp.trace_rows["Max. Hold"]["cb"].setChecked(True)
    feed(-12.0)
    feed(-60.0)
    sp.auto_ref_btn.click()
    assert sp.ref_level_spin.value() == 0.0, "the held -12 dBm peak stays in view, half a division clear of the top"
    sp.trace_rows["Max. Hold"]["cb"].setChecked(False)
    sp.auto_ref_btn.click()
    assert sp.ref_level_spin.value() == -50.0
    win.close()


def test_quick_band_presets():
    """Inclusive by default (the span covers every selected band); Solo: one band at a time."""
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    sp = win.sweep_panel
    sp.solo_qs_btn.setChecked(False)
    win.region_configs[win.current_region] = [
        {"name": "VHF", "start": 174.0, "stop": 216.0}, {"name": "UHF", "start": 470.0, "stop": 608.0},
        {"name": "STL", "start": 941.0, "stop": 960.0}]
    win._update_region_ui()
    vhf, uhf, stl = sp.quick_btns[:3]
    span = lambda: (sp.start_spin.value(), sp.stop_spin.value())
    checked = sp.checked_quick_settings

    # Inclusive: lowest start to highest stop of everything selected
    uhf.click()
    assert span() == (470.0, 608.0) and checked() == [1]
    stl.click()
    assert span() == (470.0, 960.0) and checked() == [1, 2]
    vhf.click()
    assert span() == (174.0, 960.0)
    vhf.click()                                 # deselecting one narrows the span again
    assert span() == (470.0, 960.0) and checked() == [1, 2]
    # A span typed by hand leaves the selection alone here
    sp.start_spin.setValue(500.0)
    sp.start_spin.editingFinished.emit()
    assert span() == (500.0, 960.0) and checked() == [1, 2]
    uhf.click()                                 # the next click goes back to the selected bands
    assert checked() == [2] and span() == (941.0, 960.0)
    stl.click()                                 # nothing selected: the span stays
    assert checked() == [] and span() == (941.0, 960.0)

    # Turning Solo on keeps the band clicked last
    uhf.click(); stl.click()
    sp.solo_qs_btn.click()
    assert checked() == [2] and span() == (941.0, 960.0) and win.settings.value("quick_band_solo", type=bool)
    # Solo: one at a time
    uhf.click()
    assert checked() == [1] and span() == (470.0, 608.0)
    vhf.click()
    assert checked() == [0] and span() == (174.0, 216.0)
    # ... and a span typed by hand deselects the band (leaving a field unchanged does not)
    sp.stop_spin.editingFinished.emit()
    assert checked() == [0]
    sp.stop_spin.setValue(230.0)
    sp.stop_spin.editingFinished.emit()
    assert checked() == [] and span() == (174.0, 230.0)
    uhf.click(); uhf.click()                    # clicking the selected band again deselects it
    assert checked() == [] and span() == (470.0, 608.0)

    # Back to inclusive: selections add up again
    sp.solo_qs_btn.click()
    uhf.click(); vhf.click()
    assert span() == (174.0, 608.0) and checked() == [0, 1]
    win.close()


def test_intermod_overlay_levels():
    """Products are drawn at estimated levels below the carriers, one colour per order."""
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from core.intermod import Transmitter, Product, estimate_level
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here

    a, b, c = Transmitter(500e6, "A"), Transmitter(501e6, "B"), Transmitter(503e6, "C")
    lv = {a: -40.0, b: -50.0, c: -45.0}.get
    assert estimate_level(Product(499e6, 3, (a, b), 2e5), lv, 30.0) == (2 * -40 + -50) / 3 - 30
    assert estimate_level(Product(498e6, 5, (a, b), 2e5), lv, 30.0) == (3 * -40 + 2 * -50) / 5 - 45
    assert estimate_level(Product(498e6, 33, (a, b, c), 2e5), lv, 30.0) == -45.0 - 30 + 6
    assert estimate_level(Product(499e6, 3, (a, Transmitter(600e6)), 2e5), lv, 30.0) is None

    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.is_sweeping = True
    tp, sv = win.threats_panel, win.spectrum_view
    win.coord_carriers = [{"freq_hz": f, "bw_hz": 2e5, "name": n, "zone": "z", "spare": False}
                          for f, n in ((500e6, "A"), (501e6, "B"))]
    tp.im_overlay_cb.setChecked(True)
    tp.im_source_combo.setCurrentIndex(1)                    # all coordinated carriers
    f = np.linspace(470e6, 608e6, 2000)
    p = np.full(2000, -105.0, dtype=np.float32)
    p[np.abs(f - 500e6) < 1e5] = -40.0                       # A on air, B silent
    win._last_render_time = win._fp_last_refresh = 0.0
    win._on_sweep_data(f, p)
    win._rebuild_intermod(force=True)
    stems = [it for it in sv.intermod_items if hasattr(it, "xData") and len(it.xData)]
    assert stems, "the products are drawn"
    xs, ys = np.concatenate([it.xData for it in stems]), np.concatenate([it.yData for it in stems])
    tops = ys[1::2]
    # IM3 at 499 and 502 MHz: B is silent, so it is assumed as strong as A: -40 - 30 dB
    im3 = {round(x, 3): y for x, y in zip(xs[1::2], tops) if abs(y - -70.0) < 0.01}
    assert 499.0 in im3 and 502.0 in im3, im3
    assert all(y < 0 for y in tops) and not any(y == 100.0 for y in tops), "no full-height lines"
    im5 = [y for y in tops if abs(y - -85.0) < 0.01]
    assert im5, "IM5 15 dB below IM3"
    # Raising the margin lowers every product
    tp.im_dbc_spin.setValue(40.0)
    stems = [it for it in sv.intermod_items if hasattr(it, "xData") and len(it.xData)]
    tops2 = np.concatenate([it.yData for it in stems])[1::2]
    assert abs(min(tops2) - (min(tops) - 10)) < 0.01 and abs(max(tops2) - (max(tops) - 10)) < 0.01
    win.close()


def test_disconnect_clears_the_display():
    """With no analyzer connected nothing on screen looks like a live measurement."""
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.is_sweeping = win.is_connected = True
    sv, wv = win.spectrum_view, win.waterfall_view
    win.sweep_panel.trace_rows["Max. Hold"]["cb"].setChecked(True)
    f = np.linspace(470e6, 608e6, 1000)
    p = np.full(1000, -100.0, dtype=np.float32)
    p[400:420] = -60.0

    def feed():
        win._last_render_time = 0.0
        win._on_sweep_data(f, p)

    def shown(curve):
        x, _y = curve.getData()
        return 0 if x is None else len(x)

    for _ in range(3):
        feed()
    assert shown(sv.curves["Real-Time"]) == 1000 and shown(sv.curves["Max. Hold"]) == 1000
    assert wv.waterfall_img.image is not None and win.max_hold_data is not None and win._last_sweep is not None
    # Pausing the sweep keeps the picture; losing the analyzer does not
    win.is_sweeping = False
    assert shown(sv.curves["Real-Time"]) == 1000
    win._on_all_connection_status(False)
    assert all(shown(c) == 0 for c in sv.curves.values()), {n: shown(c) for n, c in sv.curves.items()}
    assert wv.waterfall_img.image is None
    assert shown(win.demod_view.spectrum_view.curves["Real-Time"]) == 0 and win.demod_view.waterfall_view.waterfall_img.image is None
    assert win.max_hold_data is None and win.last_power is None and win._last_sweep is None and not win.avg_history
    assert float(win.waterfall_buffer.max()) == -130.0
    # Reconnecting starts afresh: the held trace is the new sweep, not the old one
    win.is_connected = win.is_sweeping = True
    p[400:420] = -80.0
    feed()
    assert shown(sv.curves["Real-Time"]) == 1000 and float(win.max_hold_data.max()) == -80.0
    assert wv.waterfall_img.image is not None
    win.close()


def test_linked_view_retunes_the_sweep():
    """View linked to the sweep: zooming or dragging a plot by hand moves the analyzer sweep too."""
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    sp = win.sweep_panel

    def by_hand(plot, lo, hi):
        vb = plot.getViewBox()
        vb.setXRange(lo, hi, padding=0)
        vb.sigRangeChangedManually.emit(vb.state["mouseEnabled"])
        end = time.monotonic() + 0.6                         # the gesture comes to rest
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)

    def sweep():
        return round(sp.start_spin.value(), 3), round(sp.stop_spin.value(), 3)

    sp.link_view_check.setChecked(True)
    sp.start_spin.setValue(470.0)
    sp.stop_spin.setValue(608.0)
    sp.frequenciesChanged.emit()
    by_hand(win.spectrum_view.plot_widget, 500.0, 540.0)
    assert sweep() == (500.0, 540.0), sweep()
    by_hand(win.waterfall_view.waterfall_widget, 510.0, 520.0)      # the waterfall shares the X axis
    assert sweep() == (510.0, 520.0), sweep()

    # A view moved by the program (a click on a TV channel) leaves the sweep alone
    sp.view_start_spin.setValue(512.0)
    sp.view_stop_spin.setValue(514.0)
    win.apply_view_frequencies()
    app.processEvents()
    assert sweep() == (510.0, 520.0), sweep()

    # Unlinked: the view moves on its own
    sp.link_view_check.setChecked(False)
    by_hand(win.spectrum_view.plot_widget, 480.0, 490.0)
    assert sweep() == (510.0, 520.0), sweep()
    assert round(sp.view_start_spin.value(), 3) == 480.0


def test_dual_spectrum_in_diversity():
    """Diversity: the Dual Spectrum layout shows antenna A and antenna B each in a spectrum view."""
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    from core.multi_device_manager import MultiDeviceTopology
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.show()
    bar, combo = win.top_bar, win.top_bar.view_mode_combo
    assert combo.findText(bar.DUAL_SPECTRUM) < 0, "only offered in diversity"

    win.multi_device_manager.topology = MultiDeviceTopology.DIVERSITY
    bar.set_multi_device_state(MultiDeviceTopology.DIVERSITY, {})
    assert combo.findText(bar.DUAL_SPECTRUM) >= 0
    win.is_sweeping = win.is_connected = True
    combo.setCurrentText(bar.DUAL_SPECTRUM)
    app.processEvents()
    a, b = win.spectrum_view, win.spectrum_view_b
    assert a.isVisible() and b.isVisible() and not win.waterfall_view.isVisible()
    assert not bar.focus_combo.isEnabled()

    f = np.linspace(470e6, 608e6, 500)
    pa, pb = np.full(500, -90.0), np.full(500, -80.0)
    win._last_div_render_time = 0.0
    win._on_diversity_sweep_data(f, pa, pb, pa - pb)
    assert a.curves["Trace A"].isVisible() and not a.curves["Trace B"].isVisible()
    assert abs(a.curves["Trace A"].getData()[1][0] + 90.0) < 1e-6
    assert b.curves["Trace B"].isVisible() and abs(b.curves["Trace B"].getData()[1][0] + 80.0) < 1e-6

    # Both views share the frequency axis and the amplitude scale
    win.sweep_panel.ref_level_spin.setValue(-20.0)
    app.processEvents()
    assert b.ref_level == a.ref_level == -20.0
    a.set_view_range(500.0, 520.0)
    app.processEvents()
    lo, hi = b.plot_widget.viewRange()[0]
    assert abs(lo - 500.0) < 0.01 and abs(hi - 520.0) < 0.01

    # Channel masks and coordinated-carrier masks are on both views
    win.spectrum_view.set_soundbase_masks([{"id": "c1", "name": "Vox 1", "f_start_mhz": 522.3, "f_stop_mhz": 522.5,
                                            "color": "#22c55e", "model": "Axient Digital"}])
    assert set(a.soundbase_masks) == set(b.soundbase_masks) and len(b.soundbase_masks) == 1, b.soundbase_masks
    win.spectrum_view.set_soundbase_mask_visible(next(iter(a.soundbase_masks)), False)
    assert not next(iter(b.soundbase_masks.values())).isVisible()
    win.spectrum_view.set_soundbase_mask_visible(next(iter(a.soundbase_masks)), True)
    assert set(a.channel_masks) == set(b.channel_masks)

    # The ETSI mask of a carrier hangs on the level each antenna receives it at
    f = np.linspace(520e6, 525e6, 2001)
    pa, pb = np.full(2001, -100.0), np.full(2001, -100.0)
    on = np.abs(f - 522.4e6) <= 100e3
    pa[on], pb[on] = -40.0, -60.0
    win._last_sweep = (f, pa)
    win._last_div_render_time = 0.0
    win._on_diversity_sweep_data(f, pa, pb, pa - pb)
    win._mask_draw_time = 0.0
    win._draw_carrier_masks()
    top = lambda view: max(float(np.nanmax(item.getData()[1])) for item in view._emission_mask_items.values()
                           if item.isVisible() and item.getData()[1] is not None and len(item.getData()[1]))
    assert abs((top(a) - top(b)) - 20.0) < 0.5, (top(a), top(b))

    # Max hold, min hold and average: antenna B has its own, on its own view
    rows = win.sweep_panel.trace_rows
    for name in ("Max. Hold", "Min. Hold", "Average"):
        rows[name]["cb"].setChecked(True)
    win.sweep_panel.avg_sweeps_spin.setValue(4)
    win._reset_b_holds()
    f = np.linspace(470e6, 608e6, 500)
    quiet = np.full(500, -100.0)
    for n, level_b in enumerate((-80.0, -70.0, -90.0)):
        win.multi_device_manager.slots["slot_b"].last_update_time = 100.0 + n      # a new sweep from B
        win._last_div_render_time = 0.0
        win._on_diversity_sweep_data(f, quiet, np.full(500, level_b), quiet - level_b)
    got = lambda name: float(b.curves[name].getData()[1][0])
    assert b.curves["Max. Hold"].isVisible() and abs(got("Max. Hold") + 70.0) < 1e-6, got("Max. Hold")
    assert abs(got("Min. Hold") + 90.0) < 1e-6 and abs(got("Average") + 80.0) < 1e-6, (got("Min. Hold"), got("Average"))
    rows["Max. Hold"]["cb"].setChecked(False)
    assert not b.curves["Max. Hold"].isVisible()

    # Intruders: what only antenna B hears is listed too, and says so
    win.spectrum_view.set_soundbase_masks([])
    win.threats_panel.intruder_thresh_spin.setValue(-75.0)
    win.intruders.clear()
    pa, pb = np.full(500, -100.0), np.full(500, -100.0)
    ia, ib, iab = 100, 250, 400
    pa[ia], pb[ib] = -50.0, -55.0
    pa[iab], pb[iab] = -60.0, -45.0
    win._last_div_render_time = 0.0
    win._on_diversity_sweep_data(f, pa, pb, pa - pb)
    win._process_intruder_sweep(f, pa)
    by_ant = {e["antenna"]: (k, e["power"]) for k, e in win.intruders.items()}
    assert set(by_ant) == {"A", "B", "B>A"}, win.intruders
    assert abs(by_ant["B"][0] - f[ib] / 1e6) < 0.01 and abs(by_ant["B"][1] + 55.0) < 1e-6
    assert abs(by_ant["B>A"][1] + 45.0) < 1e-6, "listed at the level of the antenna that hears it best"
    win.intruders.clear()

    # DECT, ShowLink and Broadcast / DTV each read the antenna chosen in their panel
    win._refresh_antenna_sources()
    for panel in (win.dect_panel, win.showlink_panel, win.dtv_panel):
        row = panel.antenna_row
        assert not row.isHidden() and not row.combo.isHidden() and row.note.isHidden() and row.choice() == "A"
    win._last_div_render_time = 0.0
    win._on_diversity_sweep_data(f, pa, pb, pa - pb)
    assert win._detector_sweep(win.dect_panel, f, pa)[1][ia] == -50.0
    win.dect_panel.antenna_row.combo.setCurrentIndex(1)
    assert win.dect_panel.antenna_row.choice() == "B"
    assert win._detector_sweep(win.dect_panel, f, pa)[1][ib] == -55.0, "DECT reads antenna B"
    assert win._detector_sweep(win.dtv_panel, f, pa)[1][ia] == -50.0, "the others keep their own choice"
    # ... and so do its zero-span captures, once analyzer B is there to take them
    assert win._detector_slot(win.dect_panel) is None
    win.multi_device_manager.slots["slot_b"].is_connected = True
    assert win._detector_slot(win.dect_panel) == "slot_b" and win._detector_slot(win.showlink_panel) is None
    win.multi_device_manager.slots["slot_b"].is_connected = False

    # Split sweep: no choice, a note on where the readings come from
    win.multi_device_manager.topology = MultiDeviceTopology.SPLIT_SWEEP
    win._refresh_antenna_sources()
    row = win.dect_panel.antenna_row
    assert not row.isHidden() and row.combo.isHidden() and not row.note.isHidden() and "analyzer A" in row.note.text()
    assert row.choice() == "A" and win._detector_sweep(win.dect_panel, f, pa)[1] is pa
    win.multi_device_manager.topology = MultiDeviceTopology.SINGLE
    win._refresh_antenna_sources()
    assert win.dect_panel.antenna_row.isHidden()
    win.multi_device_manager.topology = MultiDeviceTopology.DIVERSITY
    win._refresh_antenna_sources()

    # Back to the usual layout, and out of diversity the choice is gone
    combo.setCurrentText("Dual View")
    app.processEvents()
    assert not b.isVisible() and win.waterfall_view.isVisible() and bar.focus_combo.isEnabled()
    combo.setCurrentText(bar.DUAL_SPECTRUM)
    bar.set_multi_device_state(MultiDeviceTopology.SINGLE, {})
    app.processEvents()
    assert combo.findText(bar.DUAL_SPECTRUM) < 0 and not b.isVisible() and win.waterfall_view.isVisible()


if __name__ == "__main__":
    for test in (test_auto_ref_level, test_quick_band_presets, test_intermod_overlay_levels,
                 test_disconnect_clears_the_display, test_linked_view_retunes_the_sweep,
                 test_dual_spectrum_in_diversity):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All display tests passed.")
