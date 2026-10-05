"""
Spectrum export: CSV files in the layout SAStudio4 writes.
Run: python testing/test_spectrum_export.py
"""
import os
import sys
import tempfile
import time
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from core import spectrum_export as se

# The start of a file SAStudio4 exported (its header and first rows, as written)
SASTUDIO = ("Mode:,SWP\nData:\nTrace Name:,T1,\nFrequency(Hz),Amplitude(dBm),\n"
            "168556.3,-88.4926757813\n2487892.2,-81.0962371826\n4807228.1,-91.8970184326\n"
            "7126564,-91.199798584\n9013107863.7,-99.5944671631\n")


def test_layout_matches_sastudio():
    f = [168556.3, 2487892.2, 4807228.1, 7126564.0, 9013107863.7]
    p = [-88.4926757813, -81.0962371826, -91.8970184326, -91.199798584, -99.5944671631]
    assert se.csv_text(f, p) == SASTUDIO
    # ... and reads back, ours or theirs
    folder = tempfile.mkdtemp()
    path = se.write_csv(folder, "Max. Hold", f, p, when=datetime(2026, 10, 5, 15, 50, 43))
    assert path.name == "fReqon_20261005_155043_MaxHold.csv"
    assert path.read_bytes() == SASTUDIO.encode("ascii"), "line feeds, no byte-order mark"
    mode, name, f2, p2 = se.read_csv(path)
    assert (mode, name) == ("SWP", "T1") and np.allclose(f2, f) and np.allclose(p2, p)
    assert [se.file_name(t, datetime(2026, 1, 2, 3, 4, 5)) for t in ("Real-Time", "Min. Hold", "Average")] == [
        "fReqon_20260102_030405_Live.csv", "fReqon_20260102_030405_MinHold.csv", "fReqon_20260102_030405_Average.csv"]
    # A point without a reading is left out rather than written as "nan"
    assert "nan" not in se.csv_text([1.0, 2.0, 3.0], [-90.0, float("nan"), -80.0])
    assert se.csv_text([1.0, 2.0, 3.0], [-90.0, float("nan"), -80.0]).count("\n") == 6


def test_export_from_the_settings_dialog():
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication, QFileDialog
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    from ui.dialogs.settings_dialogs import LaunchSettingsDialog
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    rows = win.sweep_panel.trace_rows

    # Nothing swept yet: nothing to export, and the dialog says why
    assert win._exportable_traces() == {}
    assert all(why for _n, _l, why in win._export_choices({}))

    # Three sweeps with max hold and average on, min hold off
    rows["Real-Time"]["cb"].setChecked(True)
    rows["Max. Hold"]["cb"].setChecked(True)
    rows["Average"]["cb"].setChecked(True)
    rows["Min. Hold"]["cb"].setChecked(False)
    win.sweep_panel.avg_sweeps_spin.setValue(8)
    win.sweep_panel.amp_offset_spin.setValue(0.0)
    win.is_sweeping = win.is_connected = True
    f = np.linspace(470e6, 608e6, 801)
    for level in (-90.0, -70.0, -80.0):
        win._on_sweep_data(f, np.full(801, level, dtype=np.float32))
    traces = win._exportable_traces()
    assert sorted(traces) == ["Average", "Max. Hold", "Real-Time"], sorted(traces)

    choices = [(n, l, "" if n in traces else why) for n, l, why in win._export_choices(traces)]
    dlg = LaunchSettingsDialog(win.region_configs, win.current_region, export_traces=choices, parent=win)
    dlg.exportRequested.connect(lambda names: win._export_spectrum_csv(names, dlg))
    assert not dlg.export_checks["Min. Hold"].isEnabled() and "switched off" in dlg.export_checks["Min. Hold"].toolTip()
    assert dlg.export_selection() == ["Real-Time", "Max. Hold", "Average"]
    dlg.export_checks["Real-Time"].setChecked(False)

    folder = tempfile.mkdtemp()
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: folder)
    dlg.export_btn.click()
    files = sorted(os.listdir(folder))
    assert len(files) == 2 and files[0].endswith("_Average.csv") and files[1].endswith("_MaxHold.csv"), files
    assert files[0][:-len("Average.csv")] == files[1][:-len("MaxHold.csv")], "one time stamp for the set"
    assert files[0].startswith("fReqon_") and len(files[0].split("_")) == 4
    _m, _n, f_max, p_max = se.read_csv(os.path.join(folder, files[1]))
    _m, _n, _f, p_avg = se.read_csv(os.path.join(folder, files[0]))
    assert len(f_max) == 801 and abs(f_max[0] - 470e6) < 1 and abs(f_max[-1] - 608e6) < 1
    assert np.allclose(p_max, -70.0) and np.allclose(p_avg, -80.0)
    assert "Exported 2 files" in dlg.export_note.text()
    assert "SAN-60" in dlg.export_hint.text() and not dlg.export_hint.isHidden(), "still told which Soundbase importer to use"
    assert win.settings.value("export_folder") == folder

    # A change of bandwidth restarts the held traces: an export after it is of the new setting
    win._on_bandwidth_updated("slot_a", 50e3, 500e3)             # as first reported: nothing to restart
    assert win.max_hold_data is not None
    win._on_bandwidth_updated("slot_a", 50e3, 500e3)             # re-armed, unchanged
    assert win.max_hold_data is not None and len(win.avg_history) == 3
    win._on_bandwidth_updated("slot_a", 50e3, 5e3)               # the VBW is narrowed
    assert win.max_hold_data is None and win.avg_history == []
    for level in (-101.0, -100.0):
        win._on_sweep_data(f, np.full(801, level, dtype=np.float32))
    after = win._exportable_traces()
    assert np.allclose(after["Max. Hold"][1], -100.0) and np.allclose(after["Average"][1], -100.5), "no trace of the -70 dBm sweep"
    # ... and so does a change of detector, once the analyzer has re-armed with it
    win.is_connected = True
    win.apply_detect_settings()
    win.sweep_panel.detector_combo.setCurrentIndex((win.sweep_panel.detector_combo.currentIndex() + 1) % win.sweep_panel.detector_combo.count())
    win.apply_detect_settings()
    assert win.max_hold_data is not None, "not before the analyzer has taken the change"
    win._on_bandwidth_updated("slot_a", 50e3, 5e3)
    assert win.max_hold_data is None

    # Cancelling the folder choice writes nothing
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
    assert win._export_spectrum_csv(["Real-Time"], dlg) == []
    dlg.close()
    win.close()


if __name__ == "__main__":
    for test in (test_layout_matches_sastudio, test_export_from_the_settings_dialog):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All spectrum export tests passed.")
