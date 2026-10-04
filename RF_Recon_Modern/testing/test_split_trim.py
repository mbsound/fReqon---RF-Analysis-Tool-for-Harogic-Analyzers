"""
Split sweep: per-analyzer level trim and lining the two halves up at the seam.
Run: python testing/test_split_trim.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PyQt6.QtWidgets import QApplication

from core.multi_device_manager import MultiDeviceManager, MultiDeviceTopology
from ui.widgets.panels.sweep_panel import SweepPanel


def split_manager():
    mdm = MultiDeviceManager()
    mdm.topology = MultiDeviceTopology.SPLIT_SWEEP
    a, b = mdm.slots["slot_a"], mdm.slots["slot_b"]
    a.is_connected = b.is_connected = True
    a.start_freq_hz, a.stop_freq_hz = 470e6, 539e6
    b.start_freq_hz, b.stop_freq_hz = 539e6, 608e6
    return mdm, a, b


def feed(mdm, floor_a=-100.0, floor_b=-106.0, seed=0):
    rng = np.random.default_rng(seed)
    fa = np.linspace(470e6, 539e6, 600)
    fb = np.linspace(539e6, 608e6, 600)
    pa = floor_a + rng.normal(0, 1.0, 600)
    pb = floor_b + rng.normal(0, 1.0, 600)
    pa[580:585] = -40.0          # a carrier right by the seam must not skew the comparison
    mdm._on_slot_sweep_data("slot_a", fa, pa)
    mdm._on_slot_sweep_data("slot_b", fb, pb)


def test_trim_and_seam():
    app = QApplication.instance() or QApplication([])
    mdm, a, b = split_manager()
    got = []
    mdm.composite_sweep_ready.connect(lambda f, p: got.append((f, p)))
    feed(mdm)
    step, slot_id = mdm.seam_step_db()
    assert slot_id == "slot_b" and abs(step - 6.0) < 0.5, step

    # The trim is added to that analyzer's sweeps, and so to the stitched trace
    b.level_trim_db = round(step, 1)
    feed(mdm)
    step2, _ = mdm.seam_step_db()
    assert abs(step2) < 0.5, step2
    f, p = got[-1]
    assert np.all(np.diff(f) > 0)
    assert abs(np.median(p[f >= 539e6]) - np.median(p[f < 539e6])) < 0.5

    # Not a split sweep, or one trace missing: nothing to line up
    mdm.topology = MultiDeviceTopology.DIVERSITY
    assert mdm.seam_step_db() is None
    mdm.topology = MultiDeviceTopology.SPLIT_SWEEP
    b.last_freq = None
    assert mdm.seam_step_db() is None
    print("ok  trim and seam step")


def test_panel_trims():
    app = QApplication.instance() or QApplication([])
    panel = SweepPanel()
    changes = []
    panel.levelTrimChanged.connect(lambda s, v: changes.append((s, v)))
    panel.set_level_trims([("slot_a", "A", 0.0), ("slot_b", "B", 5.5)], True)
    assert list(panel._trim_spins) == ["slot_a", "slot_b"]
    assert panel._trim_spins["slot_b"].value() == 5.5 and not changes      # showing a value is not a change
    assert not panel.align_btn.isHidden()
    panel._trim_spins["slot_a"].setValue(-2.0)
    assert changes == [("slot_a", -2.0)]
    panel.set_level_trims([("slot_a", "A", -2.0), ("slot_b", "B", 5.5)], False)
    assert panel.align_btn.isHidden()
    print("ok  panel trims")


if __name__ == "__main__":
    test_trim_and_seam()
    test_panel_trims()
    print("All split trim tests passed")
