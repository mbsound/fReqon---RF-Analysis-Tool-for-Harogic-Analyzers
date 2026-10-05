"""
Sensor network (Locate): what counts as a carrier.
Run: python testing/test_sensor_net.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from core import sensor_net
from core.sensor_net import SensorNet, MIN_AVG_SWEEPS


def sweeps(n, carriers=(), seed=0, points=4000):
    """n sweeps of receiver noise (as a sample detector shows it: 10 dB and more of spread)
    over 470-608 MHz, with carriers [(Hz, dBm, width Hz)] on top."""
    rng = np.random.default_rng(seed)
    f = np.linspace(470e6, 608e6, points)
    for _ in range(n):
        mw = 10 ** (-100.0 / 10) * rng.exponential(1.0, points)       # noise power, one look per point
        for fc, lvl, bw in carriers:
            mw += 10 ** (lvl / 10) * np.exp(-0.5 * ((f - fc) / (bw / 2.355)) ** 2)
        yield f, 10 * np.log10(mw)


def listed(carriers=(), n=40, **kw):
    net = SensorNet()
    net.ensure_sensor("slot_a", "A")
    first = None
    for i, (f, p) in enumerate(sweeps(n, carriers, **kw)):
        net.update_sweep("slot_a", f, p, 50e3)
        if first is None and net.sensors["slot_a"].sightings:
            first = i + 1
    net.solve()
    return sorted(net.estimates.values(), key=lambda e: e.freq_hz), first


def test_noise_is_not_a_carrier():
    """An empty band: single sweeps have points 10 dB over the floor; none of them is listed."""
    f, p = next(sweeps(1))
    assert p.max() - np.median(p) > 9.0, "the test's noise is as spiky as a real sweep's"
    for seed in range(5):
        ests, _first = listed(seed=seed)
        assert ests == [], [(e.freq_hz, e.device) for e in ests]


def test_carriers_are_found():
    ests, first = listed(((500.0e6, -70.0, 200e3), (575.0e6, -84.0, 200e3)))
    assert [round(e.freq_hz / 1e6, 1) for e in ests] == [500.0, 575.0], [e.freq_hz for e in ests]
    assert first == MIN_AVG_SWEEPS, first                    # as soon as the average is worth looking at
    strong, weak = ests
    assert abs(strong.strongest[1] + 70.0) < 2.0
    assert strong.device != "Too weak to identify"
    # Clear of the floor but not by much: listed, and not given a name it has not earned
    assert weak.device == "Too weak to identify" and weak.confidence == 0, weak.device
    # Under the detection margin: not listed
    ests, _ = listed(((520.0e6, -92.0, 200e3),))
    assert ests == []


def test_a_new_range_starts_again():
    net = SensorNet()
    net.ensure_sensor("slot_a", "A")
    for f, p in sweeps(20, ((500.0e6, -70.0, 200e3),)):
        net.update_sweep("slot_a", f, p, 50e3)
    assert net.sensors["slot_a"].sightings
    f2 = np.linspace(600e6, 700e6, 4000)
    net.update_sweep("slot_a", f2, np.full(4000, -100.0), 50e3)
    assert not net.sensors["slot_a"].sightings and net.sensors["slot_a"].avg_n == 1


if __name__ == "__main__":
    for test in (test_noise_is_not_a_carrier, test_carriers_are_found, test_a_new_range_starts_again):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All sensor network tests passed.")
