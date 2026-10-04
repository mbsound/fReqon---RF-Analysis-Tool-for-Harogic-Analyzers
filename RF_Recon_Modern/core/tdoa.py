"""
tdoa.py - Locating a transmitter from when its signal arrives at each sensor.

Every sensor captures the same stretch of IQ at the carrier's frequency,
starting on the same GPS second (the analyzer's GNSS 1PPS trigger). The
captures are cross-correlated against one reference sensor; the lag of each
correlation peak is how much later the signal reached that sensor, and three
or more such differences give a position (core/geolocate.tdoa_locate).

What limits it, in order:

  * each analyzer's 1PPS edge wanders against true GPS time by tens of
    nanoseconds with a good sky view and a few hundred with a poor one
    (30 ns is 9 m), independently on every sensor, so one second's answer
    is rough and the session takes the median over several seconds;
  * indoors the strongest arrival is often a reflection, which puts the
    answer metres to tens of metres off however good the timing is;
  * the analyzers' reference oscillators differ by a few tenths of a ppm
    (each reports its own error against GNSS), which at UHF is a hundred
    hertz or so: enough to smear a 17 ms correlation unless it is removed.
    The reported errors are taken out first and a small frequency search
    mops up what is left.

A narrow carrier is not an obstacle in itself (a 200 kHz carrier correlated
over 17 ms resolves a few nanoseconds in clean conditions); timing and
multipath are.
"""

import math

import numpy as np

from .geolocate import tdoa_locate, Fix

C = 299_792_458.0
PPS_TRIGGER = 9                 # IQS trigger source: the analyzer's own GNSS 1PPS
MIN_QUALITY_DB = 6.0            # correlation peak over the highest sidelobe: below this, no usable peak


def decimation_for(bandwidth_hz: float, base_rate_hz: float = 125e6) -> int:
    """Power-of-two decimation giving a sample rate of about four times the carrier's bandwidth."""
    want = base_rate_hz / max(4.0 * float(bandwidth_hz), 1.0)
    return int(min(256, max(2, 2 ** int(math.floor(math.log2(max(want, 2.0)))))))


def gps_second(info: dict) -> int:
    """The GPS second a PPS-triggered capture started on (its timestamp sits ~100 ns before the second)."""
    return int(round(int(info["ns_since_epoch"]) / 1e9))


def correlate(iq_ref, iq_other, sample_rate, freq_offset_hz=0.0, search_hz=150.0, max_lag_s=10e-6):
    """
    How much later the signal arrives in iq_other than in iq_ref: (delay s,
    quality dB, frequency offset found Hz). freq_offset_hz is the expected
    frequency of iq_other relative to iq_ref (from the analyzers' reported
    reference errors); a search of +-search_hz around it finds the rest.
    Quality is the correlation peak over the highest sidelobe.
    """
    a = np.asarray(iq_ref, dtype=np.complex64)
    b = np.asarray(iq_other, dtype=np.complex64)
    n = min(len(a), len(b))
    a = a[:n] - a[:n].mean()
    b = b[:n] - b[:n].mean()
    max_lag = int(max_lag_s * sample_rate) + 2
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    A = np.conj(np.fft.fft(a, nfft))
    t = np.arange(n) / sample_rate
    step = 0.5 * sample_rate / n                    # half the correlation's frequency resolution
    trials = freq_offset_hz + np.arange(-math.ceil(search_hz / step), math.ceil(search_hz / step) + 1) * step
    def at(f):
        xc = np.fft.ifft(np.fft.fft(b * np.exp(-2j * np.pi * f * t).astype(np.complex64), nfft) * A)
        return np.abs(np.concatenate((xc[-max_lag:], xc[:max_lag + 1])))    # lags -max_lag .. +max_lag

    peaks = [float(at(f).max()) for f in trials]
    k = int(np.argmax(peaks))
    f_found = float(trials[k])
    # Refine between the grid's steps: a frequency error of ten hertz moves the correlation
    # peak by tens of nanoseconds, so the grid alone is not fine enough
    for _ in range(2):
        lo, mid, hi = (float(at(f_found + d).max()) for d in (-step / 2, 0.0, step / 2))
        denom = lo - 2 * mid + hi
        if denom >= 0:
            break
        f_found += 0.5 * (lo - hi) / denom * (step / 2)
        step /= 4
    mag = at(f_found)
    i = int(np.argmax(mag))
    frac = 0.0
    if 0 < i < len(mag) - 1:                        # parabola through the peak and its neighbours
        y0, y1, y2 = mag[i - 1], mag[i], mag[i + 1]
        denom = y0 - 2 * y1 + y2
        frac = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
    half = mag[i] / 2
    lo = i
    while lo > 0 and mag[lo - 1] > half:
        lo -= 1
    hi = i
    while hi < len(mag) - 1 and mag[hi + 1] > half:
        hi += 1
    w = max(hi - lo, 1)
    # Sidelobes: the correlation away from the peak, over the whole capture (the lag
    # window itself is narrower than the peak for a narrow carrier)
    full = np.abs(np.fft.ifft(np.fft.fft(b * np.exp(-2j * np.pi * f_found * t).astype(np.complex64), nfft) * A))
    keep = np.ones(nfft, dtype=bool)
    centre = (i - max_lag) % nfft
    guard = 4 * w + 4
    keep[np.arange(centre - guard, centre + guard + 1) % nfft] = False
    side = float(full[keep].max()) if keep.any() else 0.0
    quality = 20 * math.log10(mag[i] / (side + 1e-20))
    return (i - max_lag + frac) / sample_rate, float(quality), f_found


class TDOASession:
    """
    One location attempt: captures from every sensor over several GPS seconds.

    sensors: {sensor id: (x m, y m)}; delays_s: {sensor id: fixed extra delay of
    that sensor's antenna cable and receiver}, taken off its arrival times.
    """

    def __init__(self, sensors: dict, freq_hz: float, delays_s: dict = None):
        self.sensors = dict(sensors)
        self.freq_hz = float(freq_hz)
        self.delays_s = dict(delays_s or {})
        self.captures = {}          # GPS second -> {sensor id: (iq, info)}
        self.rounds = []            # per solved second: {"second", "ref", "tdoa": {sid: s}, "quality": {sid: dB}}

    def add_capture(self, sensor_id, iq, info: dict):
        """A capture from one sensor. Returns the round it completed, if it completed one."""
        if iq is None or not info.get("ok") or sensor_id not in self.sensors:
            return None
        sec = gps_second(info)
        group = self.captures.setdefault(sec, {})
        group[sensor_id] = (np.asarray(iq), info)
        if len(group) == len(self.sensors):
            return self._solve_second(sec)
        return None

    def _solve_second(self, sec):
        group = self.captures.pop(sec)
        # The reference is the sensor that hears the carrier best
        power = {sid: float(np.mean(np.abs(iq) ** 2)) for sid, (iq, _i) in group.items()}
        ref = max(power, key=power.get)
        iq_ref, info_ref = group[ref]
        rnd = {"second": sec, "ref": ref, "tdoa": {ref: 0.0}, "quality": {ref: 99.0}, "freq_offset": {ref: 0.0}}
        for sid, (iq, info) in group.items():
            if sid == ref:
                continue
            # iq of each sensor is offset by its own reference error: f = -carrier * ppm
            expect = -self.freq_hz * (info.get("ref_offset_ppm", 0.0) - info_ref.get("ref_offset_ppm", 0.0)) * 1e-6
            sr = float(info["sample_rate"])
            delay, quality, f_found = correlate(iq_ref, iq, sr, expect)
            delay -= self.delays_s.get(sid, 0.0) - self.delays_s.get(ref, 0.0)
            rnd["tdoa"][sid], rnd["quality"][sid], rnd["freq_offset"][sid] = delay, quality, f_found
        self.rounds.append(rnd)
        return rnd

    def discard_incomplete(self, older_than_second=None):
        """Drop seconds that not every sensor answered (one caught the next second's edge)."""
        for sec in [s for s in self.captures if older_than_second is None or s < older_than_second]:
            del self.captures[sec]

    def good_rounds(self):
        return [r for r in self.rounds if all(q >= MIN_QUALITY_DB for q in r["quality"].values())]

    def result(self):
        """
        {"fix": Fix or None, "rounds": n used, "tdoa_ns": {sensor: median}, "spread_ns":
        {sensor: scatter between seconds}, "quality_db": {sensor: median}, "ref": sensor,
        "note": why there is no fix, if there is none}
        """
        rounds = self.good_rounds()
        out = {"fix": None, "rounds": len(rounds), "rounds_taken": len(self.rounds), "tdoa_ns": {}, "spread_ns": {},
               "quality_db": {}, "ref": None, "note": ""}
        if not rounds:
            out["note"] = ("No second gave a clear correlation peak on every sensor: the carrier is too weak "
                           "at one of them, or it stopped transmitting." if self.rounds else
                           "No complete set of captures: the sensors did not all capture the same GPS second.")
            return out
        # Use the reference most rounds chose, and re-express the others against it
        ref = max({r["ref"] for r in rounds}, key=lambda s: sum(1 for r in rounds if r["ref"] == s))
        out["ref"] = ref
        ids = sorted(self.sensors)
        per = {sid: [] for sid in ids}
        for r in rounds:
            base = r["tdoa"][ref]
            for sid in ids:
                per[sid].append(r["tdoa"][sid] - base)
        med = {sid: float(np.median(v)) for sid, v in per.items()}
        spread = {sid: (float(1.4826 * np.median(np.abs(np.asarray(v) - med[sid]))) if len(v) > 1 else 0.0)
                  for sid, v in per.items()}
        out["tdoa_ns"] = {sid: med[sid] * 1e9 for sid in ids}
        out["spread_ns"] = {sid: spread[sid] * 1e9 for sid in ids}
        out["quality_db"] = {sid: float(np.median([r["quality"][sid] for r in rounds])) for sid in ids}
        if len(ids) < 3:
            d = med[[s for s in ids if s != ref][0]] * C if len(ids) == 2 else 0.0
            out["note"] = (f"Two sensors give a line, not a point: the transmitter is {abs(d):.0f} m "
                           f"{'nearer to' if d > 0 else 'farther from'} {ref} than the other sensor. A third sensor is needed.")
            return out
        # How uncertain each time difference is: its scatter over the seconds, shrunk by
        # averaging, and never taken as better than 20 ns (the PPS edges are not that good)
        n = len(rounds)
        sigmas = [max(spread[sid] / math.sqrt(n), 20e-9) for sid in ids if sid != ref]
        sigma = float(np.sqrt(np.mean(np.square(sigmas))))
        fix = tdoa_locate([self.sensors[sid] for sid in ids], [med[sid] for sid in ids],
                          ref_index=ids.index(ref), sigma_s=sigma)
        if fix is None or not np.all(np.isfinite([fix.x, fix.y])):
            out["note"] = "The time differences do not meet at a point (sensors in a line, or a reflection dominating)."
            return out
        fix.extra = {"sigma_ns": sigma * 1e9, "rounds": n}
        out["fix"] = fix
        return out


def synth_captures(sensors: dict, tx_xy, sample_rate=1.953125e6, n=32768, bandwidth_hz=200e3, snr_db=25.0,
                   ppm=None, pps_jitter_s=0.0, second=1_791_055_076, freq_hz=540e6, delays_s=None, seed=0,
                   multipath=None):
    """
    Captures as PPS-triggered analyzers would deliver them for one transmitter, for tests:
    {sensor id: (iq, info)}. ppm: {sensor: reference error}; pps_jitter_s: RMS error of each
    sensor's trigger; multipath: {sensor: (extra delay s, relative amplitude)}.
    """
    rng = np.random.default_rng(seed)
    nfft = 1 << int(np.ceil(np.log2(n + 4096)))
    f = np.fft.fftfreq(nfft, 1 / sample_rate)
    spec = (rng.normal(size=nfft) + 1j * rng.normal(size=nfft)) * (np.abs(f) <= bandwidth_hz / 2)
    out = {}
    t = np.arange(n) / sample_rate
    for sid, (x, y) in sensors.items():
        delay = math.hypot(x - tx_xy[0], y - tx_xy[1]) / C + (delays_s or {}).get(sid, 0.0)
        delay -= rng.normal(0, pps_jitter_s) if pps_jitter_s else 0.0     # a late trigger sees the signal early
        s = spec * np.exp(-2j * np.pi * f * delay)
        if multipath and sid in multipath:
            extra, amp = multipath[sid]
            s = s + amp * spec * np.exp(-2j * np.pi * f * (delay + extra))
        sig = np.fft.ifft(s)[2048:2048 + n]
        sig = sig / np.sqrt(np.mean(np.abs(sig) ** 2))
        p = (ppm or {}).get(sid, 0.0)
        sig = sig * np.exp(-2j * np.pi * freq_hz * p * 1e-6 * t)
        noise = (rng.normal(size=n) + 1j * rng.normal(size=n)) / np.sqrt(2) * 10 ** (-snr_db / 20)
        info = {"ok": True, "ns_since_epoch": second * 10**9 - 104, "sample_rate": sample_rate,
                "ref_offset_ppm": p, "center_freq": freq_hz, "samples": n}
        out[sid] = ((sig + noise).astype(np.complex64) * 1e-4, info)
    return out
