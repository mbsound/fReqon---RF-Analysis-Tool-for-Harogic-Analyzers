"""
test_tinysa.py - tinySA / tinySA Ultra driver against the simulated device (tinysa_sim.py).

Covers identification, the scanraw protocol, the sweep and channel-monitor
engines, the hardware-process message protocol, and the UI capability gating.
No analyzer is needed (or touched).

    python testing/test_tinysa.py
"""

import os
import queue
import sys
import threading
import time

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import device_caps
from core.tinysa_device import (
    ENV_PORTS, TinySA, TinySAError, TinySAWorker, find_tinysa, tinysa_process,
)
from tinysa_sim import TinySASim

# These tests must never find (and drive) a real tinySA on this machine's USB:
# outside the tests that point it at simulated devices, the scan sees nothing.
NO_TINYSA = "/dev/no-tinysa-for-tests"
os.environ[ENV_PORTS] = NO_TINYSA


def run_worker(worker, until, timeout=10.0):
    """Step the worker until `until(message)` is true for a message it sent."""
    deadline = time.monotonic() + timeout
    seen = []
    while time.monotonic() < deadline:
        worker.step()
        while True:
            try:
                msg = worker.out.get_nowait()
            except queue.Empty:
                break
            seen.append(msg)
            if until(msg):
                return msg, seen
    raise AssertionError(f"worker never produced the expected message; saw {[m[0] for m in seen]}")


def is_type(kind):
    return lambda msg: msg[0] == kind


def test_identify():
    for variant, name, ultra, fmax in (("ultra", "tinySA Ultra", True, 5.3e9),
                                       ("ultra_plus", "tinySA Ultra+ (ZS407)", True, 7.3e9),
                                       ("basic", "tinySA", False, 960e6)):
        sim = TinySASim(variant)
        sa = TinySA(sim.port)
        assert (sa.name, sa.is_ultra, sa.freq_max_hz) == (name, ultra, fmax), (sa.name, sa.freq_max_hz)
        assert sa.zero_level == (174 if ultra else 128)
        caps = sa.capabilities()
        assert caps["modes"] == ["SWP", "MSCAN", "DET"] and not caps["calibration_files"]
        assert caps["preamp"] == ("lna" if ultra else None)
        assert set(caps) == set(device_caps.FULL_CAPABILITIES), "capability keys must match the defaults"
        sa.close()
        assert sim.log[-1] == "resume"
        sim.close()

    sim = TinySASim("nanovna")
    try:
        TinySA(sim.port)
        raise AssertionError("a NanoVNA must not be accepted as a tinySA")
    except TinySAError as e:
        assert "not a tinySA" in str(e)
    sim.close()


def test_scan_raw():
    sim = TinySASim("ultra", carriers=((500e6, -40.0),), noise_dbm=-100.0)
    sa = TinySA(sim.port)
    sa.apply(None, 100e3, 10, False, 1, 600e6)
    assert sim.log[-5:] == ["mode low input", "rbw 100", "lna off", "attenuate 10", "spur auto"], sim.log
    n_cmds = len(sim.log)
    sa.apply(None, 100e3, 10, False, 1, 600e6)
    assert len(sim.log) == n_cmds, "unchanged settings must not be sent again"

    levels = sa.scan_raw(499_000_000, 50_000, 41, timeout=5)
    assert sim.log[-1] == "scanraw 499000000 501050000 41"
    assert levels.dtype == np.float32 and len(levels) == 41
    expect = [sim.level(499e6 + 50e3 * i, 100e3) for i in range(41)]
    assert np.allclose(levels, expect, atol=1 / 32), "levels must decode to within one LSB"
    assert abs(levels[20] - -40.0) < 0.05 and int(np.argmax(levels)) == 20

    # Above 800 MHz the Ultra needs its ultra mode
    sa.apply(None, 100e3, -1, True, 2, 2.5e9)
    assert sim.log[-4:] == ["ultra on", "lna on", "attenuate auto", "spur on"], sim.log
    sa.close()
    sim.close()


def test_sweep():
    carriers = ((482e6, -45.0), (566.875e6, -38.0))
    sim = TinySASim("ultra", carriers=carriers, point_s=0.0005)
    sa = TinySA(sim.port)
    w = TinySAWorker(sa, queue.Queue(), 470e6, 608e6, atten=0, preamp=0)
    assert not w.step(), "nothing runs before 'start'"
    w.handle("start")
    (_, (freq, power)), seen = run_worker(w, is_type("data"))
    rbw = next(m[1][0] for m in seen if m[0] == "hw_rbw_updated")
    assert rbw == 300e3, rbw                       # finest RBW sweeping 138 MHz in <= 1500 points
    assert freq[0] == 470e6 and abs(freq[-1] - 608e6) < 1e3, (freq[0], freq[-1])
    assert len(freq) == len(power) == 921 and np.all(np.diff(freq) > 0)
    assert next(m[1] for m in seen if m[0] == "trace_points") == 921
    scans = [c for c in sim.log if c.startswith("scanraw")]
    assert len(scans) > 1, "a slow sweep is scanned in pieces so commands are answered promptly"
    assert sum(int(c.split()[3]) for c in scans) == 921
    for fc, dbm in carriers:
        i = int(np.argmin(np.abs(freq - fc)))
        assert abs(power[i - 2:i + 3].max() - dbm) < 1.0, (fc, power[i - 2:i + 3])
    assert abs(np.median(power) - -100.0) < 0.5

    # Manual RBW snaps to what the device has; settings reach the device
    w.handle(("bw_config", (0, 50e3, 1, 0.0)))
    w.handle(("config", (500e6, 520e6, 0.0, -1, 0x04, 1, -9.0, 0.01, 0)))
    w.handle(("sweep_config", (0, 0.0, 0, 2, 0)))
    (_, (freq, power)), seen = run_worker(w, is_type("data"))
    assert next(m[1][0] for m in seen if m[0] == "hw_rbw_updated") == 30e3
    assert freq[0] == 500e6 and abs(freq[-1] - 520e6) < 1e3 and len(freq) == 1335
    assert {"rbw 30", "lna on", "attenuate auto", "spur on"} <= set(sim.log)

    # Input-chain correction is applied to the levels
    w.handle(("freq_comp", ([400e6, 700e6], [6.0, 6.0])))
    assert w.out.get_nowait() == ("freq_comp", (0, 2))
    (_, (_, corrected)), _ = run_worker(w, is_type("data"))
    assert abs(np.median(corrected) - -94.0) < 0.5

    # Outside the analyzer's range: limited, or nothing to sweep
    w.handle(("freq_comp", ([], [])))
    w.handle(("config", (5.0e9, 6.0e9, 0.0, 0, 0, 1, -9.0, 0.01, 0)))
    (_, (freq, _)), seen = run_worker(w, is_type("data"))
    assert freq[0] == 5.0e9 and abs(freq[-1] - 5.3e9) < 1e6
    assert any(m[0] == "status" and "limited" in m[1] for m in seen)
    w.handle(("config", (5.5e9, 6.0e9, 0.0, 0, 0, 1, -9.0, 0.01, 0)))
    assert not w.step()
    assert "outside" in w.out.get_nowait()[1]
    sa.close()
    sim.close()


def test_basic_bands():
    sim = TinySASim("basic", carriers=((300e6, -50.0), (500e6, -60.0)))
    sa = TinySA(sim.port)
    w = TinySAWorker(sa, queue.Queue(), 470e6, 608e6, atten=0)
    w.handle("start")
    (_, (freq, power)), _ = run_worker(w, is_type("data"))
    assert "mode high input" in sim.log and "mode low input" not in sim.log
    assert abs(power[int(np.argmin(np.abs(freq - 500e6)))] - -60.0) < 1.0

    # Below 350 MHz the low input is used, even where the high input also reaches
    w.handle(("config", (250e6, 340e6, 0.0, 0, 0, 1, -9.0, 0.01, 0)))
    sim.log.clear()
    run_worker(w, is_type("data"))
    assert [c for c in sim.log if c.startswith("mode")] == ["mode low input"], sim.log

    # A sweep across 350 MHz uses the low input below it and the high input above
    w.handle(("config", (100e6, 550e6, 0.0, 0, 0, 1, -9.0, 0.01, 0)))
    sim.log.clear()
    (_, (freq, power)), seen = run_worker(w, is_type("data"))
    assert [c for c in sim.log if c.startswith("mode")] == ["mode high input"], sim.log   # already on low
    switch = sim.log.index("mode high input")
    low_scans = [int(c.split()[1]) for c in sim.log[:switch] if c.startswith("scanraw")]
    high_scans = [int(c.split()[1]) for c in sim.log[switch:] if c.startswith("scanraw")]
    assert low_scans and max(low_scans) < 350e6 and high_scans and min(high_scans) >= 350e6
    plan = [m[1] for m in seen if m[0] == "sweep_plan"][-1]
    assert plan == {"rf_input": "auto", "inputs": ["low", "high"], "note": None}, plan
    assert power.min() > -110.0, "every point must come from an input that covers it"
    for fc, dbm in sim.carriers:
        assert abs(power[int(np.argmin(np.abs(freq - fc)))] - dbm) < 1.5
    assert not any(c.startswith(("lna", "ultra")) for c in sim.log)

    def sweep_with(rf_input, start, stop):
        w.handle(("rf_input", rf_input))
        w.handle(("config", (start, stop, 0.0, 0, 0, 1, -9.0, 0.01, 0)))
        (_, (freq, _)), seen = run_worker(w, is_type("data"))
        return freq, [m[1] for m in seen if m[0] == "sweep_plan"][-1]

    # A selected input: only that connector is used, and the sweep is limited to what it tunes
    sim.log.clear()
    freq, plan = sweep_with("high", 100e6, 550e6)
    assert plan["inputs"] == ["high"] and "limited to 240 - 550 MHz" in plan["note"], plan
    assert freq[0] == 240e6 and "mode low input" not in sim.log
    freq, plan = sweep_with("low", 100e6, 550e6)
    assert plan["inputs"] == ["low"] and freq[0] == 100e6 and abs(freq[-1] - 350e6) < 1e6
    # 240-350 MHz is reachable on either input: Auto takes Low, the selection overrides it
    sim.log.clear()
    freq, plan = sweep_with("high", 250e6, 340e6)
    assert plan == {"rf_input": "high", "inputs": ["high"], "note": None} and sim.log[0] == "mode high input"
    # A range the selected input cannot reach: nothing is swept, and the reason is reported
    w.handle(("rf_input", "low"))
    w.handle(("config", (470e6, 608e6, 0.0, 0, 0, 1, -9.0, 0.01, 0)))
    assert not w.step()
    msgs = []
    while not w.out.empty():
        msgs.append(w.out.get_nowait())
    plan = [m[1] for m in msgs if m[0] == "sweep_plan"][-1]
    assert plan["inputs"] == [] and "outside the range of the tinySA's Low input" in plan["note"], plan
    freq, plan = sweep_with("auto", 470e6, 608e6)
    assert plan == {"rf_input": "auto", "inputs": ["high"], "note": None}
    sa.close()
    sim.close()


def test_channel_monitor():
    sim = TinySASim("ultra", carriers=((500.0e6, -42.0), (510.5e6, -70.0)))
    sa = TinySA(sim.port)
    w = TinySAWorker(sa, queue.Queue(), 470e6, 608e6, atten=0)
    w.handle("start")
    channels = [{"freq_hz": 500.0e6, "name": "Vox 1"}, {"freq_hz": 510.5e6, "name": "Vox 2"},
                {"freq_hz": 520.0e6, "name": "Spare"}]
    w.handle(("mscan_config", (channels, 0.001, 1, -10.0, 0, 0, 256)))
    hops = {}
    while len(hops) < 3:
        (_, (idx, fc, peak, spec, info)), _ = run_worker(w, is_type("mscan_data"))
        hops[idx] = (fc, peak, spec, info)
    assert abs(hops[0][1] - -42.0) < 1.0 and abs(hops[1][1] - -70.0) < 1.0 and hops[2][1] < -95.0
    fc, _, spec, info = hops[0]
    assert len(spec) == info["points"] == 32 and 390e3 < info["span_hz"] < 400e3
    assert info["channel_info"]["name"] == "Vox 1" and info["element_index"] == 0
    # The spectrum is centred on the channel, as the fingerprinter assumes
    f = fc - info["span_hz"] / 2 + (np.arange(32) + 0.5) * info["span_hz"] / 32
    assert abs(f[int(np.argmax(spec))] - fc) < info["span_hz"] / 32

    # Modes a tinySA does not have are refused and the sweep carries on
    w.handle("stop_mscan")
    for cmd in (("set_mode", ("RTA", {})), ("rta_config", (500e6, 1, 0.0, 2, 0, 0.05, 0, 0)),
                ("iqs_config", (500e6, 64, 0.0, 2, 16384, 0, 0))):
        w.handle(cmd)
    msg, seen = run_worker(w, is_type("data"))
    assert sum("staying in Swept Spectrum" in m[1] for m in seen if m[0] == "status") == 3
    assert w.mode == "SWP"
    sa.close()
    sim.close()


def collect(q, until, timeout=10.0):
    deadline = time.monotonic() + timeout
    seen = []
    while time.monotonic() < deadline:
        try:
            msg = q.get(timeout=0.1)
        except queue.Empty:
            continue
        seen.append(msg)
        if until(msg):
            return seen
    raise AssertionError(f"timed out; saw {[m[0] for m in seen]}")


def test_zero_span():
    """Zero span on a tinySA: one frequency sampled over time with single-frequency scans."""
    sim = TinySASim("basic", carriers=((300e6, -50.0), (500e6, -40.0)), point_s=0.00002)
    sa = TinySA(sim.port)
    caps = device_caps.resolve(sa.capabilities())
    assert "DET" in caps["modes"] and caps["det"]["max_points"] == 15936
    assert [k for _label, k in caps["det"]["trigger_sources"]] == [2, 3, 4] and caps["det"]["trigger_level"]
    atten = {i["id"]: i["atten"]["kind"] for i in caps["inputs"]}
    assert atten == {"low": "range", "high": "switch"}, atten

    w = TinySAWorker(sa, queue.Queue(), 470e6, 608e6, atten=0)
    w.handle("start")
    w.handle(("set_mode", ("DET",)))
    assert not w.step(), "nothing to capture until the frequency is set"
    w.handle(("det_config", (500e6, 2, -20.0, 2, 0, 2048)))
    (_, (t_ns, power, info)), seen = run_worker(w, is_type("det_data"))
    assert len(t_ns) == len(power) == 2048 and info["trigger_length"] == 2048
    assert abs(float(np.median(power)) - -40.0) < 1.0, np.median(power)
    assert "mode high input" in sim.log and "scanraw 500000000 500000000 2112" in sim.log   # 64 settling samples are dropped
    # The sample interval is measured on the device (the simulator: 20 us a sample plus overheads)
    assert 5e3 < info["sample_interval_ns"] < 200e3, info
    assert abs(t_ns[1] - t_ns[0] - info["sample_interval_ns"]) < 1.0 and info["ref_level"] == -20.0
    assert info["rbw_hz"] == max(sa.rbw_list)
    assert any(m[0] == "status" and "per sample" in m[1] for m in seen)

    # Zero span's own attenuation and LNA setting go with its settings; without them, the sweep's
    w.handle(("det_config", (500e6, 2, 0.0, 2, 0, 2048, None, 10, None)))
    sim.log.clear()
    run_worker(w, is_type("det_data"))
    assert "attenuate 10" in sim.log, sim.log
    w.handle(("det_config", (500e6, 2, 0.0, 2, 0, 2048, None, -1, None)))
    sim.log.clear()
    run_worker(w, is_type("det_data"))
    assert "attenuate auto" in sim.log, sim.log
    # The low input below 350 MHz, with the sweep's attenuation
    w.handle(("config", (470e6, 608e6, 0.0, 20, 0, 1, -9.0, 0.01, 0)))
    w.handle(("det_config", (300e6, 2, 0.0, 2, 0, 4096)))
    sim.log.clear()
    (_, (t_ns, power, info)), _ = run_worker(w, is_type("det_data"))
    assert len(power) == 4096 and abs(float(np.median(power)) - -50.0) < 1.0
    assert "mode low input" in sim.log and "attenuate 20" in sim.log, sim.log

    # Level trigger: a keyed carrier starts a tenth of the way into the window, whatever
    # part of its cycle each scan happened to start in
    sim.keyed = (500e6, 700, 200)
    w.handle(("det_config", (500e6, 2, 0.0, 3, 0, 2048, -60.0)))
    for _ in range(3):
        (_, (t_ns, power, info)), _ = run_worker(w, is_type("det_data"))
        assert len(power) == 2048
        assert power[204] > -45.0 and power[203] < -80.0, (power[200:208],)
    # Free run takes the scan as it comes
    w.handle(("det_config", (500e6, 2, 0.0, 2, 0, 2048)))
    starts = set()
    for _ in range(4):
        (_, (_t, power, _i)), _ = run_worker(w, is_type("det_data"))
        on = np.nonzero((power[1:] > -60) & (power[:-1] < -60))[0]
        starts.add(int(on[0]))
    assert len(starts) > 1, starts
    # Armed: the tinySA's own triggered sweep. It is set up once, a capture is 290 points
    # across the same window with the crossing in the middle, and it is armed again after each
    sim.log.clear()
    w.handle(("det_config", (500e6, 2, 0.0, 4, 0, 2048, -60.0)))
    for k in range(2):
        (_, (t_ns, power, info)), seen = run_worker(w, is_type("det_data"))
        assert len(power) == 290 and power[146] > -45.0 and power[140] < -80.0, power[138:150]
        assert abs(t_ns[-1] - 2048 * w.zs_dt * 1e9) < 0.01 * t_ns[-1] and info["trigger_level_dbm"] == -60.0
    assert sim.log.count("sweep cw 500000000") == 1 and sim.log.count("trigger -60") == 1
    assert sim.log.count("trigger single") >= 3 and not any(c.startswith("scanraw") for c in sim.log)
    # A level nothing reaches: it keeps waiting, and shows nothing
    w.handle(("det_config", (500e6, 2, 0.0, 4, 0, 2048, -20.0)))
    end = time.monotonic() + 1.5
    while time.monotonic() < end:
        w.step()
    msgs = []
    while not w.out.empty():
        msgs.append(w.out.get_nowait())
    assert not any(m[0] == "det_data" for m in msgs) and any("waiting for -20 dBm" in m[1] for m in msgs if m[0] == "status")
    # Leaving the armed trigger hands the analyzer's own sweep back as it was
    sim.log.clear()
    w.handle(("det_config", (500e6, 2, 0.0, 2, 0, 2048, -60.0)))
    run_worker(w, is_type("det_data"))
    assert sim.log[:5] == ["trigger auto", "sweeptime 0.003", "sweep start 470000000", "sweep stop 608000000", "pause"], sim.log[:6]
    assert sim.own_sweep == [470000000, 608000000] and sim.trig_mode == "auto"
    sim.keyed = None

    # More points than a scan can hold are limited; a frequency out of range is reported
    w.handle(("det_config", (500e6, 2, 0.0, 2, 0, 65536)))
    (_, (_t, power, _i)), _ = run_worker(w, is_type("det_data"), timeout=20)
    assert len(power) == 15936
    w.handle(("det_config", (1925e6, 2, 0.0, 2, 0, 2048)))
    assert not w.step()
    msgs = []
    while not w.out.empty():
        msgs.append(w.out.get_nowait())
    assert any(m[0] == "status" and "outside the range" in m[1] for m in msgs), msgs

    # Back to sweeping
    w.handle(("set_mode", ("SWP",)))
    (_, (freq, power)), _ = run_worker(w, is_type("data"))
    assert freq[0] == 470e6 and abs(power[int(np.argmin(np.abs(freq - 500e6)))] - -40.0) < 1.5
    sa.close()
    sim.close()


def test_zero_span_and_attenuation_ui():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.widgets.panels.det_panel import DETPanel
    from ui.widgets.panels.sweep_panel import SweepPanel
    sim = TinySASim("basic")
    sa = TinySA(sim.port)
    tiny = device_caps.resolve(sa.capabilities())
    sa.close()
    sim.close()
    full = device_caps.resolve(None)

    # Zero-span panel: the tinySA's sample rate, lengths and triggers; the Harogic ones come back
    dp = DETPanel()
    harogic_lengths = [dp.len_combo.itemData(i) for i in range(dp.len_combo.count())]
    dp.apply_capabilities(tiny)
    assert [dp.len_combo.itemData(i) for i in range(dp.len_combo.count())] == [512, 1024, 2048, 4096, 8192, 15936]
    assert dp.dec_combo.count() == 1 and not dp.dec_combo.isEnabled()
    assert [dp.trig_source_combo.itemData(i) for i in range(dp.trig_source_combo.count())] == [2, 3, 4]
    assert not dp.trig_level_spin.isHidden() and not dp.trig_level_spin.isEnabled()      # free run: no level
    dp.trig_source_combo.setCurrentIndex(2)
    dp.trig_level_spin.setValue(-70)
    assert dp.trig_level_spin.isEnabled() and dp.get_params()["trigger_level"] == -70.0
    assert dp.get_params()["trigger_source"] == 4
    dp.trig_source_combo.setCurrentIndex(0)
    assert dp.ref_spin.isEnabled()
    # Amplitude & Gain: what the tinySA has. No pre-amplifier; at 960 MHz (the High input)
    # the attenuator is a pad, in or out; on the Low input 0-31 dB or automatic
    items = lambda combo: [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]
    assert dp.preamp_combo.isHidden() and dp.preamp_lbl.isHidden()
    assert items(dp.att_combo) == [("Out (0 dB)", 0), ("In (25–40 dB pad)", 10)], items(dp.att_combo)
    assert "High input" in dp.gain_note_lbl.text()
    dp.att_combo.setCurrentIndex(1)
    assert dp.get_params()["atten"] == 10 and dp.get_params()["own_gain"]
    dp.cf_spin.setValue(100.0)
    assert items(dp.att_combo)[:3] == [("Auto", -1), ("0 dB", 0), ("1 dB", 1)] and dp.att_combo.count() == 33
    assert dp.att_combo.currentData() == 10 and dp.gain_note_lbl.isHidden()
    dp.set_gain(-1, None)
    assert dp.get_params()["atten"] == -1
    dp.cf_spin.setValue(300.0)                      # 240-350 MHz: Low unless High is the chosen input
    assert dp.att_combo.count() == 33
    dp.set_rf_input("high")
    assert dp.att_combo.count() == 2 and dp.att_combo.currentData() == 0     # automatic: the pad is out
    dp.set_gain(20, None)
    assert dp.att_combo.currentData() == 10
    dp.set_rf_input("auto")
    dp.cf_spin.setValue(960.0)
    # A tinySA Ultra: one input, 0-31 dB or automatic, and its LNA
    sim = TinySASim("ultra")
    sa = TinySA(sim.port)
    ultra = device_caps.resolve(sa.capabilities())
    sa.close()
    sim.close()
    dp.apply_capabilities(ultra)
    assert dp.att_combo.count() == 33 and items(dp.preamp_combo) == [("LNA Off", 0x01), ("LNA On", 0x04)]
    assert not dp.preamp_combo.isHidden() and "LNA bypasses" in dp.gain_note_lbl.text()
    dp.set_gain(5, 0x04)
    p = dp.get_params()
    assert (p["atten"], p["preamp"]) == (5, 0x04)
    dp.apply_capabilities(tiny)
    assert dp.preamp_combo.isHidden() and dp.att_combo.count() == 2
    assert dp.window_info_lbl.text() == "Window Span: 924.29 ms", dp.window_info_lbl.text()
    assert dp.cf_spin.maximum() == 960.0
    p = dp.get_params()
    assert p["trigger_length"] == 15936 and p["decimate_factor"] == 1 and p["trigger_source"] == 2
    dp.auto_fit_window(300e6)       # 300 ms
    assert dp.len_combo.currentData() == 8192
    dp.apply_capabilities(full)
    assert [dp.len_combo.itemData(i) for i in range(dp.len_combo.count())] == harogic_lengths
    assert dp.dec_combo.count() == 8 and dp.dec_combo.isEnabled() and dp.trig_source_combo.count() == 3
    assert dp.trig_level_spin.isHidden() and dp.get_params()["trigger_level"] is None
    assert dp.len_combo.currentData() == 16240 and dp.dec_combo.currentData() == 2 and dp.att_combo.isEnabled()
    assert items(dp.att_combo) == list(dp.HAROGIC_ATTEN) and items(dp.preamp_combo) == list(dp.HAROGIC_PREAMP)
    assert not dp.preamp_combo.isHidden() and not dp.get_params()["own_gain"] and dp.gain_note_lbl.isHidden()
    assert dp.window_info_lbl.text() == "Window Span: 259.8 us", dp.window_info_lbl.text()

    # Attenuation: a dB value on the Low input, a switch on the High input
    sp = SweepPanel()
    sp.apply_capabilities(tiny)
    changes = []
    sp.amplitudeChanged.connect(lambda: changes.append(sp.attenuation))
    sp.show_sweep_plan({"rf_input": "auto", "inputs": ["low"], "note": None})
    assert not sp.atten_spin.isHidden() and sp.atten_pad_check.isHidden() and sp.atten_note.text() == ""
    assert (sp.atten_spin.minimum(), sp.atten_spin.maximum()) == (0, 31)
    sp.show_sweep_plan({"rf_input": "auto", "inputs": ["high"], "note": None})
    assert sp.atten_spin.isHidden() and sp.auto_atten_check.isHidden() and not sp.atten_pad_check.isHidden()
    assert "25–40 dB pad" in sp.atten_pad_check.text() and "in or out" in sp.atten_note.text()
    assert not sp.atten_pad_check.isChecked() and sp.attenuation == 0
    sp.atten_pad_check.setChecked(True)
    assert sp.attenuation == 10 and changes[-1] == 10
    sp.atten_pad_check.setChecked(False)
    assert sp.attenuation == 0 and changes[-1] == 0
    # Automatic leaves the pad out; taking the switch turns automatic off
    sp.auto_atten_check.setChecked(True)
    assert sp.attenuation == -1 and not sp.atten_pad_check.isChecked()
    sp.atten_pad_check.setChecked(True)
    assert sp.attenuation == 10 and not sp.auto_atten_check.isChecked()
    # A sweep over both inputs: the dB value, with a note about the pad
    sp.show_sweep_plan({"rf_input": "auto", "inputs": ["low", "high"], "note": None})
    assert not sp.atten_spin.isHidden() and sp.atten_pad_check.isHidden()
    assert "above 0 dB" in sp.atten_note.text() and sp.atten_spin.value() == 10
    # An analyzer with one input: the plain control
    sp.apply_capabilities(full)
    assert not sp.atten_spin.isHidden() and sp.atten_pad_check.isHidden() and sp.atten_note.text() == ""


def test_process_protocol():
    sim = TinySASim("ultra")
    cmds, data = queue.Queue(), queue.Queue()
    t = threading.Thread(target=tinysa_process, args=(cmds, data, 470e6, 608e6, sim.port), daemon=True)
    t.start()
    seen = collect(data, lambda m: m == ("connected", True))
    kinds = [m[0] for m in seen]
    assert kinds == ["capabilities", "device_info", "hw_endorsements", "connected"], kinds
    assert seen[1][1][0] == 0 and seen[1][1][1] > 0
    assert seen[2][1]["title"] == "TINYSA ULTRA" and seen[2][1]["licenses"] is None
    assert "pause" in sim.log
    cmds.put("start")
    collect(data, is_type("data"))
    cmds.put("stop")
    t.join(timeout=5)
    assert not t.is_alive() and sim.log[-1] == "resume"

    # Unplugging the analyzer is reported and ends the process
    cmds, data = queue.Queue(), queue.Queue()
    t = threading.Thread(target=tinysa_process, args=(cmds, data, 470e6, 608e6, sim.port), daemon=True)
    t.start()
    collect(data, lambda m: m == ("connected", True))
    cmds.put("start")
    collect(data, is_type("data"))
    sim.close()
    seen = collect(data, lambda m: m == ("connected", False))
    assert any(m[0] == "error" and "disconnected" in m[1] for m in seen)
    t.join(timeout=5)
    assert not t.is_alive()

    # No device: on that port, or on any other
    data = queue.Queue()
    tinysa_process(queue.Queue(), data, 470e6, 608e6, "/dev/does-not-exist")
    kind, text = data.get_nowait()
    assert kind == "error" and "none found on another port" in text, text
    assert data.get_nowait() == ("connected", False)
    data = queue.Queue()
    tinysa_process(queue.Queue(), data, 470e6, 608e6)
    assert data.get_nowait() == ("error", "tinySA #1 not found. Check the USB connection.")


def test_find():
    a, b, nano = TinySASim("ultra"), TinySASim("basic"), TinySASim("nanovna")
    os.environ[ENV_PORTS] = os.pathsep.join((nano.port, a.port, b.port))
    try:
        first = find_tinysa(0)
        assert first.port == a.port, "devices that are not tinySAs are skipped"
        second = find_tinysa(1)                  # the first is in use: it still counts as #0
        assert second.port == b.port and not second.is_ultra
        assert find_tinysa(2) is None
        try:
            find_tinysa(0)
            raise AssertionError("an analyzer in use must not be opened twice")
        except TinySAError as e:
            assert "in use" in str(e)
        first.close()
        second.close()
        again = find_tinysa(0)
        assert again.port == a.port
        again.close()
    finally:
        os.environ[ENV_PORTS] = NO_TINYSA
        for sim in (a, b, nano):
            sim.close()


def test_usb_fallback():
    """'USB' slots: Harogic analyzers first, then tinySAs. Uses a fake SDK (no real analyzer is touched)."""
    import core.device_controller as dc

    class FakeSDK:
        def __init__(self, harogic_count):
            self.harogic_count = harogic_count

        def Device_List(self, profile, count, numbers, infos):
            count.contents.value = self.harogic_count
            return 0

        def Device_Open(self, *args):
            raise AssertionError("the Harogic SDK must not be opened for a tinySA slot")

    sim = TinySASim("ultra")
    os.environ[ENV_PORTS] = sim.port
    real_sdk = dc.dll
    try:
        # (Harogic analyzers on USB, slot's USB index) -> the first tinySA
        for harogic_count, usb_index in ((0, 0), (1, 1)):
            dc.dll = FakeSDK(harogic_count)
            cmds, data = queue.Queue(), queue.Queue()
            t = threading.Thread(target=dc.hardware_process, args=(cmds, data, 470e6, 608e6),
                                 kwargs={"interface_type": "usb", "usb_index": usb_index, "atten": 0}, daemon=True)
            t.start()
            seen = collect(data, lambda m: m == ("connected", True))
            assert seen[0][0] == "capabilities" and seen[0][1]["name"] == "tinySA Ultra"
            cmds.put("start")
            collect(data, is_type("data"))
            cmds.put("stop")
            t.join(timeout=5)
            assert not t.is_alive()

        # One Harogic, one tinySA: there is no third USB analyzer
        dc.dll = FakeSDK(1)
        data = queue.Queue()
        dc.hardware_process(queue.Queue(), data, 470e6, 608e6, interface_type="usb", usb_index=2)
        kind, text = data.get_nowait()
        assert kind == "error" and "USB analyzer #3 not found" in text, text
        assert data.get_nowait() == ("connected", False)
    finally:
        dc.dll = real_sdk
        os.environ[ENV_PORTS] = NO_TINYSA
        sim.close()


class ListingSDK:
    """A stand-in for the Harogic SDK that lists the given (model, serial) USB analyzers."""

    def __init__(self, analyzers):
        self.analyzers = analyzers

    def Device_List(self, profile, count, numbers, infos):
        count.contents.value = len(self.analyzers)
        for i, (model, uid) in enumerate(self.analyzers):
            numbers[i] = i
            infos[i].Model, infos[i].DeviceUID = model, uid
        return 0


def test_usb_scan_and_connection_dialog():
    """The Connection dialog lists the analyzers on USB and each slot picks from them."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    import core.device_controller as dc
    from core.multi_device_manager import MultiDeviceManager
    from ui.dialogs.connection_dialog import ConnectionDialog

    ultra, basic, nano = TinySASim("ultra"), TinySASim("basic"), TinySASim("nanovna")
    os.environ[ENV_PORTS] = os.pathsep.join((nano.port, ultra.port, basic.port))
    real_sdk = dc.dll
    dc.dll = ListingSDK([(66, 0x2034323752305000), (67, 0)])     # the second reports no serial number
    try:
        found = dc.DeviceController.scan_usb_analyzers()
        assert [d["kind"] for d in found] == ["harogic", "harogic", "tinysa", "tinysa"], found
        assert found[0] == {"kind": "harogic", "usb_index": 0, "model": 66, "uid": 0x2034323752305000}
        assert found[1]["uid"] is None and found[1]["usb_index"] == 1
        assert (found[2]["name"], found[2]["port"], found[2]["tinysa_index"]) == ("tinySA Ultra", ultra.port, 0)
        assert (found[3]["name"], found[3]["port"], found[3]["tinysa_index"]) == ("tinySA", basic.port, 1)
        assert "resume" not in ultra.log and "pause" not in ultra.log, "a scan only asks a tinySA what it is"

        def open_dialog(manager):
            dlg = ConnectionDialog(manager=manager)
            assert dlg.card_a.usb_status_lbl.text() == "Looking for USB analyzers…"
            assert "(not found)" not in dlg.card_a.usb_combo.currentText() + dlg.card_b.usb_combo.currentText()
            deadline = time.monotonic() + 10
            while "Looking" in dlg.card_a.usb_status_lbl.text() and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            return dlg

        def labels(card):
            return [card.usb_combo.itemText(i) for i in range(card.usb_combo.count())]

        mdm = MultiDeviceManager()
        dlg = open_dialog(mdm)
        a, b = dlg.card_a, dlg.card_b
        ultra_port, basic_port = os.path.basename(ultra.port), os.path.basename(basic.port)
        assert labels(a) == ["Automatic (USB analyzer #1)", "Harogic 066 · SN 2034323752305000",
                             "Harogic 067 · USB analyzer #2", f"tinySA Ultra · {ultra_port}",
                             f"tinySA · {basic_port}"], labels(a)
        assert labels(b)[0] == "Automatic (USB analyzer #2)" and labels(b)[1:] == labels(a)[1:]
        assert a.usb_status_lbl.text() == "Found on USB: 2 Harogic, 2 tinySA."

        # Automatic keeps the old behaviour: the slot's place in the order found
        cfg = a.get_config()
        assert (cfg["interface"], cfg["usb_index"], cfg["target_uid"], cfg["serial_port"]) == ("usb", 0, None, None)
        assert b.get_config()["usb_index"] == 1

        def pick(card, index):
            card.usb_combo.setCurrentIndex(index)
            card.usb_combo.activated.emit(index)
            return card.get_config()

        # A Harogic analyzer is pinned by its serial number; one without, by its index
        cfg = pick(a, 1)
        assert (cfg["interface"], cfg["target_model"], cfg["target_uid"]) == ("usb", 66, 0x2034323752305000)
        cfg = pick(a, 2)
        assert (cfg["interface"], cfg["usb_index"], cfg["target_model"], cfg["target_uid"]) == ("usb", 1, 67, None)
        # A tinySA is pinned by its port
        cfg_b = pick(b, 4)
        assert (cfg_b["interface"], cfg_b["serial_port"]) == ("tinysa", basic.port)
        cfg_a = pick(a, 1)
        dlg.done(0)

        # The choices are what the slots are then connected with, and the dialog shows them next time
        for slot, cfg in ((mdm.slots["slot_a"], cfg_a), (mdm.slots["slot_b"], cfg_b)):
            slot.interface_type, slot.usb_index = cfg["interface"], cfg["usb_index"]
            slot.target_model, slot.target_uid, slot.serial_port = cfg["target_model"], cfg["target_uid"], cfg["serial_port"]
        dlg = open_dialog(mdm)
        assert dlg.card_a.usb_combo.currentText() == "Harogic 066 · SN 2034323752305000"
        assert dlg.card_b.usb_combo.currentText() == f"tinySA · {basic_port}"
        assert dlg.card_b.get_config() == dict(cfg_b), "an untouched dialog changes nothing"
        dlg.done(0)

        # A connected slot holds its tinySA's port, so the scan cannot ask it what it is:
        # the dialog names it from the slot
        held = TinySA(basic.port)
        slot_b = mdm.slots["slot_b"]
        slot_b.is_connected, slot_b.capabilities = True, held.capabilities()
        slot_b.device_description = held.describe()
        dlg = open_dialog(mdm)
        assert dlg.card_b.usb_combo.currentText() == f"tinySA · {basic_port}  (connected: Analyzer B)"
        assert labels(dlg.card_a)[4] == f"tinySA · {basic_port}  (connected: Analyzer B)"
        dlg.done(0)
        slot_b.is_connected = False
        dlg = open_dialog(mdm)
        assert labels(dlg.card_a)[4] == f"Serial analyzer · {basic_port}  (in use by another program)"
        dlg.done(0)
        held.close()

        # The pinned analyzer is unplugged: it stays the slot's choice, marked as missing
        basic.close()
        os.environ[ENV_PORTS] = os.pathsep.join((nano.port, ultra.port))
        dlg = open_dialog(mdm)
        assert dlg.card_b.usb_combo.currentText() == f"tinySA · {basic_port}  (not found)"
        assert dlg.card_b.get_config()["serial_port"] == basic.port
        assert dlg.card_a.usb_status_lbl.text() == "Found on USB: 2 Harogic, 1 tinySA."
        dlg.done(0)

        # Connecting to a port that has gone uses the tinySA that is there, and says so
        cmds, data = queue.Queue(), queue.Queue()
        t = threading.Thread(target=tinysa_process, args=(cmds, data, 470e6, 608e6, basic.port), daemon=True)
        t.start()
        seen = collect(data, lambda m: m == ("connected", True))
        assert seen[0] == ("status", f"No device on {basic.port}; using the tinySA on {ultra.port}."), seen[0]
        assert seen[1][0] == "capabilities" and seen[1][1]["name"] == "tinySA Ultra"
        cmds.put("stop")
        t.join(timeout=5)

        # Nothing on USB at all
        dc.dll = ListingSDK([])
        os.environ[ENV_PORTS] = nano.port
        dlg = open_dialog(MultiDeviceManager())
        assert labels(dlg.card_a) == ["Automatic (USB analyzer #1)"]
        assert dlg.card_a.usb_status_lbl.text().startswith("No USB analyzers found")
        dlg.done(0)
    finally:
        dc.dll = real_sdk
        os.environ[ENV_PORTS] = NO_TINYSA
        for sim in (ultra, basic, nano):
            sim.close()


def tinysa_description(variant):
    """(capabilities, hardware description) of a simulated tinySA."""
    sim = TinySASim(variant)
    sa = TinySA(sim.port)
    described = sa.capabilities(), sa.describe()
    sa.close()
    sim.close()
    return described


def test_ui_gating():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None      # never touch real hardware here
    win = MainWindow()
    for _slot in win.multi_device_manager.slots.values():
        _slot.role_alias = ""      # (the machine's saved settings may name the slots)
    import tempfile
    from PyQt6.QtCore import QSettings
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "test.ini"), QSettings.Format.IniFormat)
    mdm, rail, sp = win.multi_device_manager, win.nav_rail, win.sweep_panel
    sp.set_rf_input("auto")
    mdm.set_rf_input("auto")
    slot = mdm.slots["slot_a"]

    def connect(caps):
        mdm._set_slot_capabilities("slot_a", caps)
        slot.is_connected = True
        mdm.capabilities_changed.emit("slot_a")

    def enabled_modes():
        return [i for i in range(len(rail.buttons)) if rail.is_mode_enabled(i)]

    assert enabled_modes() == list(range(10))

    def rows_shown():
        """Labels of the visible rows of the amplitude, bandwidth and sweep cards."""
        shown = []
        for form in (sp._amp_form, sp._bw_form, sp._adv_form):
            for r in range(form.rowCount()):
                label = form.itemAt(r, form.ItemRole.LabelRole)
                if label is not None and form.isRowVisible(r) and label.widget().text():
                    shown.append(label.widget().text().rstrip(":"))
        return shown

    all_rows = ["Ref. Level", "Scale / Div", "Attenuation", "Pre-Amplifier", "Amp. Offset", "Enable IFAGC",
                "IFAGC Target", "IFAGC Period", "Enable IF Out", "RBW Mode", "RBW Value", "VBW Mode", "VBW Value",
                "SWT Mode", "Sweep Time", "Trace Points", "Spur Rejection", "Window", "Detector", "Trace Detector"]
    assert rows_shown() == all_rows, rows_shown()

    ultra_caps, ultra_info = tinysa_description("ultra")
    connect(ultra_caps)
    assert enabled_modes() == [0, 1, 2, 4, 6, 7, 8, 9], enabled_modes()   # no RTSA or demodulation
    assert "tinySA Ultra" in rail.buttons[3].toolTip()
    assert not win.top_bar.audio_btn.isEnabled()
    assert sp.start_spin.maximum() == 5300.0 and sp.start_spin.minimum() == 0.1
    items = sp.rbw_mode_combo.model()
    off = [sp.rbw_presets[i][0] for i in range(len(sp.rbw_presets)) if not items.item(i).isEnabled()]
    assert off == ["50 kHz", "1 MHz", "3 MHz"], off
    assert [sp.preamp_combo.itemText(i) for i in range(sp.preamp_combo.count())] == ["LNA Off", "LNA On"]
    assert sp.atten_spin.maximum() == 31
    assert not sp._sweep_form.isRowVisible(sp.rf_input_combo), "the Ultra has one input: no selector"
    # Only the settings a tinySA Ultra has are shown: its LNA, and spur rejection with its own choices
    assert rows_shown() == ["Ref. Level", "Scale / Div", "Attenuation", "Pre-Amplifier", "Amp. Offset",
                            "RBW Mode", "RBW Value", "Spur Rejection"], rows_shown()
    assert [sp.spur_combo.itemText(i) for i in range(sp.spur_combo.count())] == ["Off", "Auto", "On"]
    assert sp.spur_combo.currentText() == "Auto" and not sp._adv_card.isHidden()
    # Zero span is offered, with the tinySA's own options
    win._on_spectrum_trigger_zero_span(500.0)
    assert rail.btn_group.checkedId() == 4 and win.det_panel.len_combo.currentData() == 15936
    assert not win.det_panel.dec_combo.isEnabled()
    rail.set_active_mode(0)
    # Shortcuts into the missing modes are refused, not half-entered
    win.inspect_rtsa_carrier(500.0)
    win.open_audio_demod_dialog()
    assert rail.btn_group.checkedId() == 0 and win.audio_demod_dialog is None
    # No calibration files are asked for, and the device menu describes the tinySA
    win._on_slot_info_received("slot_a", 0, 12345)
    win._on_hw_endorsements("slot_a", ultra_info)
    win.multi_device_manager.slots["slot_a"].role_alias = ""     # (the machine's saved settings may name slot A)
    win._on_all_connection_status(True)
    assert win.top_bar._identity_text == "tinySA Ultra", win.top_bar._identity_text
    win.top_bar._show_endorsements_menu()
    texts = [a.text() for a in win.top_bar._active_endorsements_menu.actions()]
    assert texts[0].startswith("TINYSA ULTRA") and not any("LICENSE" in t for t in texts), texts
    win.top_bar._active_endorsements_menu.close()

    # A tinySA (basic) stops at 960 MHz: no DECT or 2.4 GHz either
    basic, _ = tinysa_description("basic")
    rail.set_active_mode(8)
    connect(basic)
    assert enabled_modes() == [0, 1, 2, 4, 6, 9], enabled_modes()
    assert rail.btn_group.checkedId() == 0, "leaving a mode that just became unavailable"
    assert sp.stop_spin.maximum() == 960.0
    # A tinySA has no pre-amplifier, IF AGC or IF output, and of the sweep settings only spur removal
    assert rows_shown() == ["Ref. Level", "Scale / Div", "Attenuation", "Amp. Offset",
                            "RBW Mode", "RBW Value", "Spur Rejection"], rows_shown()
    assert [sp.spur_combo.itemText(i) for i in range(sp.spur_combo.count())] == ["Off", "On"]
    assert sp.spur_combo.currentText() == "Off"
    assert sp.target_card.isHidden(), "one analyzer: nothing to choose between"

    # The tinySA's two inputs: a selector, and a readout of the input in use
    combo = sp.rf_input_combo
    assert sp._sweep_form.isRowVisible(combo)
    assert [combo.itemData(i) for i in range(combo.count())] == ["auto", "low", "high"]
    assert combo.itemText(2) == "High  (240 – 960 MHz)" and combo.currentData() == "auto"
    mdm.sweep_plan_changed.emit("slot_a", {"rf_input": "auto", "inputs": ["high"], "note": None})
    assert sp.rf_input_note.text() == "High input in use"
    assert win.top_bar.dev_label.fullText() == "tinySA: High input in use"
    mdm.sweep_plan_changed.emit("slot_a", {"rf_input": "auto", "inputs": ["low", "high"], "note": None})
    assert sp.rf_input_note.text().startswith("Low input below 350 MHz, High input above")
    mdm.sweep_plan_changed.emit("slot_a", {"rf_input": "low", "inputs": [], "note": "470 - 608 MHz is outside."})
    assert sp.rf_input_note.text() == "470 - 608 MHz is outside."
    combo.setCurrentIndex(2)
    assert mdm.rf_input == "high" and sp.rf_input == "high" and win.settings.value("rf_input") == "high"
    connect(basic)                      # reconnecting keeps the selection
    assert combo.currentData() == "high"

    # Disconnecting (or a fully featured analyzer) restores everything
    slot.is_connected = False
    mdm._on_slot_connection("slot_a", False)
    assert enabled_modes() == list(range(10)) and win.top_bar.audio_btn.isEnabled()
    assert sp.start_spin.maximum() == 20000.0 and sp.atten_spin.maximum() == 30
    assert all(items.item(i).isEnabled() for i in range(len(sp.rbw_presets)))
    assert sp.preamp_combo.count() == 5 and rows_shown() == all_rows
    assert [sp.spur_combo.itemText(i) for i in range(sp.spur_combo.count())] == ["Bypass", "Standard", "Enhanced"]
    assert sp.spur_combo.currentText() == "Standard"
    assert not sp._sweep_form.isRowVisible(combo) and sp.rf_input == "high"
    win.close()


class Recorder:
    """Stands in for a slot's DeviceController: records what it is told."""

    def __init__(self):
        self.calls = []
        self.process = object()

    def __getattr__(self, name):
        return lambda *args, **kw: self.calls.append((name, args))

    def last(self, name):
        return next((args for n, args in reversed(self.calls) if n == name), None)


def test_per_analyzer_settings():
    """Two different analyzers: each keeps its own settings, and the panel shows one at a time."""
    import tempfile
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None
    win = MainWindow()
    for _slot in win.multi_device_manager.slots.values():
        _slot.role_alias = ""      # (the machine's saved settings may name the slots)
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "test.ini"), QSettings.Format.IniFormat)
    mdm, sp = win.multi_device_manager, win.sweep_panel
    sp.set_rf_input("auto")
    mdm.set_rf_input("auto")
    basic, _ = tinysa_description("basic")
    a, b = mdm.slots["slot_a"], mdm.slots["slot_b"]
    a.controller, b.controller = Recorder(), Recorder()
    a.detected_model = 66

    def connect(slot_id, caps):
        mdm._set_slot_capabilities(slot_id, caps)
        mdm.slots[slot_id].is_connected = True
        mdm.capabilities_changed.emit(slot_id)

    def targets():
        c = sp.settings_target_combo
        return [(c.itemData(i), c.itemText(i)) for i in range(c.count())]

    # A Harogic analyzer on slot A, then a tinySA on slot B
    connect("slot_a", None)
    win.is_connected = True
    assert sp.target_card.isHidden() and win._settings_target() is None
    sp.atten_spin.setValue(20)                   # with one analyzer, as before: applied to it
    assert a.controller.last("configure")[3] == 20
    connect("slot_b", basic)
    assert not sp.target_card.isHidden()
    assert targets() == [("slot_a", "Analyzer A · Harogic model 066"), ("slot_b", "Analyzer B · tinySA")], targets()
    assert sp.settings_target_combo.currentData() == "slot_a" and win._settings_target() == "slot_a"
    assert sp._amp_form.isRowVisible(sp.ifagc_check) and sp.detector_combo.isVisibleTo(sp) is not None

    # Changes go to the analyzer shown, and only to it
    b.controller.calls.clear()
    sp.atten_spin.setValue(10)
    sp.rbw_mode_combo.setCurrentIndex(sp.rbw_mode_combo.findText("50 kHz"))
    sp.detector_combo.setCurrentIndex(2)
    assert a.controller.last("configure")[3] == 10 and a.controller.last("update_bandwidth")[:2] == (0, 50e3)
    assert a.controller.last("configure_detect")[0] == 2
    assert b.controller.calls == [], b.controller.calls

    # The tinySA's settings: only what it has, with its own values
    sp.settings_target_combo.setCurrentIndex(1)
    assert win._settings_target() == "slot_b" and b.controller.calls == [], "looking at an analyzer sends it nothing"
    assert not sp._amp_form.isRowVisible(sp.ifagc_check) and not sp._amp_form.isRowVisible(sp.preamp_combo)
    assert not sp._adv_form.isRowVisible(sp.detector_combo) and sp._adv_form.isRowVisible(sp.spur_combo)
    assert sp._sweep_form.isRowVisible(sp.rf_input_combo)
    assert sp.atten_spin.value() == 20 and sp.atten_spin.maximum() == 31, \
        "the tinySA has what it was connected with (20 dB, set while one analyzer was connected), not A's 10 dB"
    assert sp.rbw_mode_combo.currentText() == "Auto", "50 kHz is not a tinySA bandwidth"
    a.controller.calls.clear()
    sp.atten_spin.setValue(7)
    sp.spur_combo.setCurrentIndex(1)
    sp.rf_input_combo.setCurrentIndex(2)
    assert b.controller.last("configure")[3] == 7 and b.controller.last("configure_sweep")[3] == 1
    assert b.controller.last("set_rf_input") == ("high",)
    assert a.controller.calls == [], a.controller.calls
    assert a.rf_input == "auto" and b.rf_input == "high"

    # Back to the Harogic analyzer: its settings are as they were left
    sp.settings_target_combo.setCurrentIndex(0)
    assert sp.atten_spin.value() == 10 and sp.atten_spin.maximum() == 30
    assert sp.rbw_mode_combo.currentText() == "50 kHz" and sp.detector_combo.currentIndex() == 2
    assert sp.spur_combo.currentText() == "Standard" and sp._amp_form.isRowVisible(sp.if_out_check)
    assert a.controller.calls == [] and not sp._sweep_form.isRowVisible(sp.rf_input_combo)
    sp.settings_target_combo.setCurrentIndex(1)
    assert sp.atten_spin.value() == 7 and sp.spur_combo.currentText() == "On" and sp.rf_input == "high"

    # The tinySA drops out and comes back: it gets its settings again
    b.is_connected = False
    mdm._on_slot_connection("slot_b", False)
    assert sp.target_card.isHidden() and win._settings_target() is None
    assert sp.atten_spin.value() == 10 and sp._amp_form.isRowVisible(sp.ifagc_check), "the remaining analyzer's"
    b.controller.calls.clear()
    connect("slot_b", basic)
    assert b.controller.last("configure")[3] == 7 and b.controller.last("configure_sweep")[3] == 1
    assert b.controller.last("set_rf_input") == ("high",)

    # Two analyzers of the same model can also be set together
    connect("slot_b", None)
    b.detected_model = 66
    mdm.capabilities_changed.emit("slot_b")
    assert [t[0] for t in targets()] == [None, "slot_a", "slot_b"] and targets()[0][1] == "All analyzers"
    sp.settings_target_combo.setCurrentIndex(0)
    a.controller.calls.clear()
    b.controller.calls.clear()
    sp.atten_spin.setValue(30)
    assert a.controller.last("configure")[3] == 30 and b.controller.last("configure")[3] == 30
    win.close()


def test_controller_end_to_end():
    """The real DeviceController and hardware process, against the simulator."""
    import multiprocessing
    from PyQt6.QtWidgets import QApplication
    from core.device_controller import DeviceController
    app = QApplication.instance() or QApplication(sys.argv)
    multiprocessing.set_start_method("spawn", force=True)
    sim = TinySASim("ultra", carriers=((500e6, -40.0),))
    ctl = DeviceController(staging_name="test_tinysa")
    got = {}
    ctl.capabilities_received.connect(lambda c: got.setdefault("caps", c))
    ctl.connection_status.connect(lambda ok: got.setdefault("connected", ok))
    ctl.spectrum_data_ready.connect(lambda f, p: got.setdefault("sweep", (f, p)))
    ctl.connect_device(470e6, 608e6, interface_type="tinysa", serial_port=sim.port, atten=0)
    ctl.start()
    deadline = time.monotonic() + 30
    while "sweep" not in got and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    try:
        assert got.get("connected") is True and got["caps"]["name"] == "tinySA Ultra", got.keys()
        freq, power = got["sweep"]
        assert abs(power[int(np.argmin(np.abs(freq - 500e6)))] - -40.0) < 1.0
    finally:
        ctl.disconnect_device()
        sim.close()
        # connect_device made this slot a (here unused) calibration staging folder
        from core.calibration_manager import CalibrationManager
        stage = CalibrationManager.staging_root("test_tinysa")
        for folder in (stage / "CalFile", stage):
            try:
                folder.rmdir()
            except OSError:
                pass
    assert "resume" in sim.log, "the analyzer is handed back on disconnect"


if __name__ == "__main__":
    tests = [test_identify, test_scan_raw, test_sweep, test_basic_bands, test_channel_monitor,
             test_zero_span, test_zero_span_and_attenuation_ui,
             test_process_protocol, test_find, test_usb_fallback, test_usb_scan_and_connection_dialog,
             test_ui_gating, test_per_analyzer_settings,
             test_controller_end_to_end]
    only = sys.argv[1:]
    for test in tests:
        if only and test.__name__ not in only:
            continue
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All tinySA tests passed.")
