"""
band24.py - What is on the 2.4 GHz band, and how much of it lands on a ShowLink channel.

Shure ShowLink (the AD610 access point and the transmitters it manages) is IEEE
802.15.4 (the Zigbee radio): 2 MHz wide, on channels 11-26 at 2405 + 5 (k - 11)
MHz, short packets (up to about 4 ms) with the channel idle in between. What it
shares the band with, and how each looks on a sweep:

  * Wi-Fi: 20 MHz (or 40 MHz) wide, flat-topped, bursty; channels 1-13 at
    2412 + 5 (n - 1) MHz (14 at 2484 MHz), so each one covers four Zigbee channels
  * Bluetooth (Classic and LE), CRMX / W-DMX and other frequency hoppers: 1 MHz
    wide, a different frequency every sweep
  * continuous wideband energy: a microwave oven (2450-2460 MHz), a video sender

A sweep is split into the segments above threshold, each segment is classified
by its width and position, and a sliding window of sweeps gives, per Zigbee
channel, how often it is busy and what with. A zero-span capture of one channel
gives its airtime directly (see airtime()).
"""

from collections import deque

import numpy as np

ZIGBEE_CHANNELS = {k: 2405.0 + 5.0 * (k - 11) for k in range(11, 27)}
ZIGBEE_WIDTH_MHZ = 2.0
WIFI_CHANNELS = {n: 2412.0 + 5.0 * (n - 1) for n in range(1, 14)}
WIFI_CHANNELS[14] = 2484.0
WIFI_WIDTH_MHZ = 20.0
BLE_ADVERTISING = {37: 2402.0, 38: 2426.0, 39: 2480.0}
BAND_LO_MHZ, BAND_HI_MHZ = 2400.0, 2483.5

KINDS = ("wifi", "zigbee", "hop", "wide", "continuous")
KIND_LABEL = {"wifi": "Wi-Fi", "zigbee": "Zigbee / ShowLink", "hop": "hopping (Bluetooth, CRMX)",
              "wide": "wideband", "continuous": "continuous"}


def segments(freq_mhz, power_dbm, threshold_dbm, min_points=2):
    """Contiguous stretches above threshold: [(lo_mhz, hi_mhz, peak_dbm, centre_mhz)]."""
    f = np.asarray(freq_mhz, dtype=float)
    p = np.asarray(power_dbm, dtype=float)
    on = p >= threshold_dbm
    if not on.any():
        return []
    edges = np.diff(on.astype(np.int8))
    starts = list(np.nonzero(edges == 1)[0] + 1)
    ends = list(np.nonzero(edges == -1)[0] + 1)
    if on[0]:
        starts.insert(0, 0)
    if on[-1]:
        ends.append(len(on))
    step = float(np.median(np.diff(f))) if len(f) > 1 else 0.0
    out = []
    for s, e in zip(starts, ends):
        if e - s < min_points:
            continue
        seg = p[s:e]
        w = 10.0 ** (seg / 10.0)
        centre = float((f[s:e] * w).sum() / w.sum())
        out.append((float(f[s]) - step / 2, float(f[e - 1]) + step / 2, float(seg.max()), centre))
    return out


def classify(seg):
    """The kind of signal a segment looks like, from its width and where it sits."""
    lo, hi, _peak, centre = seg
    width = hi - lo
    if width >= 14.0:
        return "wifi"
    if width <= 1.4:
        return "hop"
    if width <= 4.5:
        nearest = min(ZIGBEE_CHANNELS.values(), key=lambda c: abs(c - centre))
        return "zigbee" if abs(nearest - centre) <= 0.8 else "hop"
    return "wide"


def wifi_channel_for(seg):
    """The Wi-Fi channel a Wi-Fi-sized segment is centred on, or None."""
    _lo, _hi, _peak, centre = seg
    n = min(WIFI_CHANNELS, key=lambda n: abs(WIFI_CHANNELS[n] - centre))
    return n if abs(WIFI_CHANNELS[n] - centre) <= 4.0 else None


class Band24Monitor:
    """A sliding window of sweeps of the 2.4 GHz band."""

    def __init__(self, window_sweeps=50):
        self.window = window_sweeps
        self.reset()

    def reset(self):
        self._sweeps = deque(maxlen=self.window)     # per sweep: {"zigbee": {ch: (busy, peak, kinds)}, "wifi": {n: (busy, peak)}, "kinds": {kind: count}}

    def update(self, freq_mhz, power_dbm, threshold_dbm):
        f = np.asarray(freq_mhz, dtype=float)
        p = np.asarray(power_dbm, dtype=float)
        if len(f) < 8 or f[-1] < BAND_LO_MHZ or f[0] > BAND_HI_MHZ:
            return None
        segs = segments(f, p, threshold_dbm)
        kinds = [classify(s) for s in segs]
        sweep = {"zigbee": {}, "wifi": {}, "kinds": {k: 0 for k in KINDS}, "segments": list(zip(segs, kinds))}
        for k in kinds:
            sweep["kinds"][k] += 1
        for ch, cf in ZIGBEE_CHANNELS.items():
            sel = (f >= cf - ZIGBEE_WIDTH_MHZ / 2) & (f <= cf + ZIGBEE_WIDTH_MHZ / 2)
            if not sel.any():
                continue
            peak = float(p[sel].max())
            on = {k for (lo, hi, _pk, _c), k in zip(segs, kinds) if lo < cf + ZIGBEE_WIDTH_MHZ / 2 and hi > cf - ZIGBEE_WIDTH_MHZ / 2}
            sweep["zigbee"][ch] = (peak >= threshold_dbm, peak, on)
        for n, cf in WIFI_CHANNELS.items():
            sel = (f >= cf - WIFI_WIDTH_MHZ / 2) & (f <= cf + WIFI_WIDTH_MHZ / 2)
            if not sel.any():
                continue
            peak = float(p[sel].max())
            # Busy with Wi-Fi: a Wi-Fi-sized segment centred on this channel
            wifi_here = any(k == "wifi" and wifi_channel_for(s) == n for s, k in zip(segs, kinds))
            sweep["wifi"][n] = (wifi_here, peak)
        self._sweeps.append(sweep)
        return sweep

    @property
    def sweeps(self):
        return len(self._sweeps)

    def summary(self):
        """
        {"zigbee": {ch: {"freq_mhz", "busy_pct", "interference_pct" (busy with anything but
         Zigbee-shaped traffic), "peak_dbm", "kinds": {kind: pct}, "wifi": [n...]}},
         "wifi": {n: {"center_mhz", "busy_pct", "peak_dbm"}},
         "mix": {kind: pct of busy sightings}, "sweeps": n}
        """
        n = len(self._sweeps)
        out = {"zigbee": {}, "wifi": {}, "mix": {k: 0.0 for k in KINDS}, "sweeps": n}
        if not n:
            return out
        for ch, cf in ZIGBEE_CHANNELS.items():
            rows = [s["zigbee"][ch] for s in self._sweeps if ch in s["zigbee"]]
            if not rows:
                continue
            busy = sum(1 for b, _p, _k in rows if b)
            # Busy with something other than Zigbee-shaped traffic: what ShowLink has to live with
            other = sum(1 for b, _p, ks in rows if b and (ks - {"zigbee"}))
            # ... and with something other than Zigbee or Wi-Fi: what would remain if the
            # venue switched its Wi-Fi off on the channels over it
            non_wifi = sum(1 for b, _p, ks in rows if b and (ks - {"zigbee", "wifi"}))
            kinds = {k: 100.0 * sum(1 for _b, _p, ks in rows if k in ks) / len(rows) for k in KINDS}
            out["zigbee"][ch] = {"freq_mhz": cf, "busy_pct": 100.0 * busy / len(rows),
                                 "interference_pct": 100.0 * other / len(rows),
                                 "non_wifi_pct": 100.0 * non_wifi / len(rows),
                                 "peak_dbm": max(pk for _b, pk, _k in rows),
                                 "mean_peak_dbm": float(np.mean([pk for _b, pk, _k in rows])),
                                 "kinds": kinds,
                                 "wifi": [w for w, wc in WIFI_CHANNELS.items() if abs(wc - cf) < (WIFI_WIDTH_MHZ + ZIGBEE_WIDTH_MHZ) / 2]}
        for w, wc in WIFI_CHANNELS.items():
            rows = [s["wifi"][w] for s in self._sweeps if w in s["wifi"]]
            if not rows:
                continue
            out["wifi"][w] = {"center_mhz": wc, "busy_pct": 100.0 * sum(1 for b, _p in rows if b) / len(rows),
                              "peak_dbm": max(pk for _b, pk in rows)}
        totals = {k: sum(s["kinds"][k] for s in self._sweeps) for k in KINDS}
        all_sightings = sum(totals.values())
        if all_sightings:
            out["mix"] = {k: 100.0 * v / all_sightings for k, v in totals.items()}
        return out


def showlink_channel(summary, min_pct=5.0):
    """
    The channel ShowLink is on, as far as the sweeps show: the Zigbee channel with
    Zigbee-shaped traffic in the largest share of sweeps (at least min_pct), or None.
    The AD610 chooses its channel itself and moves when interfered with, so this
    is read off the air rather than configured.
    """
    best = max(summary["zigbee"].items(), key=lambda kv: kv[1]["kinds"].get("zigbee", 0.0), default=None)
    if best is None or best[1]["kinds"].get("zigbee", 0.0) < min_pct:
        return None
    return best[0]


def assess(summary, ch):
    """
    How a ShowLink channel is doing, from a summary(): {"verdict": "GOOD" | "MARGINAL" | "POOR",
    "busy_pct" (with anything but Zigbee-shaped traffic, which is ShowLink itself), "reasons": [...],
    "alternatives": [ch, ...] (quietest first, counting everything)}.
    """
    z = summary["zigbee"].get(ch)
    if not z:
        return {"verdict": "UNKNOWN", "busy_pct": None, "reasons": ["not in the sweep yet"], "alternatives": []}
    reasons = []
    busy = z["interference_pct"]
    for w in z["wifi"]:
        ws = summary["wifi"].get(w)
        if ws and ws["busy_pct"] >= 10.0:
            reasons.append(f"Wi-Fi channel {w} on top of it, busy {ws['busy_pct']:.0f}% ({ws['peak_dbm']:.0f} dBm)")
    if z["kinds"]["hop"] >= 10.0:
        reasons.append(f"hopping traffic (Bluetooth, CRMX) hits it in {z['kinds']['hop']:.0f}% of sweeps")
    if z["kinds"]["wide"] + z["kinds"]["continuous"] >= 10.0:
        reasons.append("wideband energy on it (a microwave oven, a video sender?)")
    if z["kinds"]["zigbee"] >= 5.0:
        reasons.append(f"Zigbee-shaped traffic in {z['kinds']['zigbee']:.0f}% of sweeps: ShowLink itself (not counted "
                       f"as interference), unless another 802.15.4 system shares the channel")
    verdict = "GOOD" if busy < 10.0 else "MARGINAL" if busy < 35.0 else "POOR"
    # Alternatives: least busy, then not under a busy Wi-Fi channel, then higher (farther from Wi-Fi 1/6/11 use)
    def rank(item):
        c, s = item
        under_wifi = any(summary["wifi"].get(w, {}).get("busy_pct", 0) >= 10.0 for w in s["wifi"])
        return (round(s["busy_pct"] / 5.0), under_wifi, s["mean_peak_dbm"])
    alternatives = [c for c, _s in sorted(summary["zigbee"].items(), key=rank) if c != ch]
    return {"verdict": verdict, "busy_pct": busy, "reasons": reasons, "alternatives": alternatives[:3]}


CLEAR_PCT = 10.0            # a ShowLink channel with interference under this is usable
WIFI_BUSY_PCT = 10.0        # a Wi-Fi channel in use this often counts as occupied


def feasibility(summary):
    """
    Can ShowLink run in this venue? The access point needs one clear channel (it picks
    it itself and moves if that one goes bad, so more than one is better). From a summary():

      clear         ShowLink channels with interference under CLEAR_PCT
      verdict       "FEASIBLE" (3+ clear), "MARGINAL" (1-2), "NOT WITHOUT CHANGES" (none),
                    "UNKNOWN" (no sweeps)
      wifi_in_use   Wi-Fi channels busy at least WIFI_BUSY_PCT of the time, busiest first
      disable       [(wifi channel, [ShowLink channels it would free])], most useful first:
                    what to ask the venue to switch off, if anything
    """
    z = summary["zigbee"]
    if not z:
        return {"clear": [], "verdict": "UNKNOWN", "wifi_in_use": [], "disable": []}
    clear = [ch for ch, s in sorted(z.items()) if s["interference_pct"] < CLEAR_PCT]
    wifi_in_use = [w for w, ws in sorted(summary["wifi"].items(), key=lambda kv: -kv[1]["busy_pct"])
                   if ws["busy_pct"] >= WIFI_BUSY_PCT]
    disable = []
    for w in wifi_in_use:
        freed = []
        for ch, s in sorted(z.items()):
            if ch in clear or w not in s["wifi"] or s["non_wifi_pct"] >= CLEAR_PCT:
                continue
            others = [v for v in s["wifi"] if v != w and v in wifi_in_use]
            if not others:          # under no other busy Wi-Fi channel
                freed.append(ch)
        if freed:
            disable.append((w, freed))
    disable.sort(key=lambda d: -len(d[1]))
    verdict = "FEASIBLE" if len(clear) >= 3 else "MARGINAL" if clear else "NOT WITHOUT CHANGES"
    return {"clear": clear, "verdict": verdict, "wifi_in_use": wifi_in_use, "disable": disable}


def survey_text(summary, feas, detected=None, where=""):
    """A plain-text survey summary, for the venue or the show file."""
    lines = [f"ShowLink 2.4 GHz site survey{(' - ' + where) if where else ''}",
             f"{summary['sweeps']} sweeps analysed. ShowLink verdict: {feas['verdict']}.",
             f"Clear ShowLink channels (interference under {CLEAR_PCT:.0f}% of the time): "
             + (", ".join(f"{c} ({ZIGBEE_CHANNELS[c]:.0f} MHz)" for c in feas["clear"]) or "none")]
    if feas["wifi_in_use"]:
        lines.append("Wi-Fi channels in use: " + ", ".join(
            f"{w} ({summary['wifi'][w]['busy_pct']:.0f}% busy, peak {summary['wifi'][w]['peak_dbm']:.0f} dBm)" for w in feas["wifi_in_use"]))
    else:
        lines.append("No Wi-Fi channel in use above the threshold.")
    if feas["disable"]:
        lines.append("Freeing ShowLink channels: " + "; ".join(
            f"switching off Wi-Fi channel {w} would free ShowLink {', '.join(map(str, freed))}" for w, freed in feas["disable"]))
    mix = summary.get("mix") or {}
    parts = [f"{KIND_LABEL[k]} {v:.0f}%" for k, v in sorted(mix.items(), key=lambda kv: -kv[1]) if v >= 1.0]
    if parts:
        lines.append("Signals seen, by shape: " + ", ".join(parts))
    if detected:
        lines.append(f"A ShowLink (802.15.4) network is on the air on channel {detected}.")
    return "\n".join(lines)


def airtime(t_s, p_dbm, threshold_dbm):
    """
    From a zero-span capture of one channel: the share of time above threshold and
    the bursts making it up. Zigbee packets run 0.35-4.3 ms, Bluetooth slots 0.37 /
    1.6 / 2.9 ms, Wi-Fi frames from tens of microseconds to a few ms, so the
    durations suggest rather than prove what is there.
    """
    t = np.asarray(t_s, dtype=float)
    p = np.asarray(p_dbm, dtype=float)
    if len(t) < 2:
        return None
    dt = float(np.median(np.diff(t)))
    on = p >= threshold_dbm
    busy_pct = 100.0 * on.mean()
    edges = np.diff(on.astype(np.int8))
    starts = list(np.nonzero(edges == 1)[0] + 1)
    ends = list(np.nonzero(edges == -1)[0] + 1)
    if on[0]:
        starts.insert(0, 0)
    if on[-1]:
        ends.append(len(on))
    durations = np.array([(e - s) * dt for s, e in zip(starts, ends)])
    durations = durations[durations >= 3 * dt]
    span = t[-1] - t[0] + dt
    return {"busy_pct": busy_pct, "bursts": int(len(durations)), "span_s": span,
            "median_us": float(np.median(durations) * 1e6) if len(durations) else 0.0,
            "longest_us": float(durations.max() * 1e6) if len(durations) else 0.0,
            "continuous": bool(len(durations) and durations.max() >= 0.5 * span)}
