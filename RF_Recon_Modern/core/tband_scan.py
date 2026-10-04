"""
tband_scan.py - What is in each T-Band TV channel (470-512 MHz, channels 14-20).

In US metro areas the T-Band is shared between television and land mobile
radio (public safety and business two-way radio), and which channels carry
which differs from city to city. The two look nothing alike on a sweep:

  * a TV station fills its 6 MHz channel edge to edge (found with the same
    detector as Auto DTV Detect);
  * land mobile radio is narrow carriers (12.5 / 25 kHz) that key on for a
    second or two and vanish, so a channel is held as LMR for a while after
    its last transmission, and carriers are remembered across sweeps.

Wider carriers (wireless microphones are ~200 kHz) and frequencies the caller
says to ignore (coordinated carriers) do not count as land mobile radio.
"""

import time

import numpy as np
from scipy.signal import find_peaks, peak_widths

from .dtv_detect import DTVOccupancyDetector

HOLD_S = 60.0               # a channel stays "LMR" this long after its last transmission
MAX_LMR_WIDTH_MHZ = 0.11    # at half prominence; an LMR carrier through a 50 kHz RBW is ~0.05-0.07
MIN_ABOVE_FLOOR_DB = 12.0   # peak-detected noise spikes reach ~10 dB over the floor
SURE_ABOVE_FLOOR_DB = 18.0  # this strong, one sighting is enough
CONFIRM_S = 3.0             # otherwise the carrier must be seen twice within this time
CARRIER_GRID_MHZ = 0.0125   # LMR channel raster, for counting distinct carriers
MIN_COVERAGE = 0.9          # of a channel's width that the sweep must cover for it to be judged
# A filled channel: TV is steady, packed land mobile traffic keys on and off. The
# sweep is averaged in blocks; a point whose block averages differ this much is traffic.
BLOCK_SWEEPS = 10
BLOCKS_KEPT = 12
KEYED_RANGE_DB = 12.0       # noise-like TV averaged over a block varies by ~5 dB between blocks
KEYED_POINTS = 3            # points of the channel that must show it


class TBandScanner:
    def __init__(self):
        self.reset()

    def reset(self):
        self._tv = DTVOccupancyDetector()
        self._last_lmr = {}      # channel -> time of the last narrow carrier
        self._carriers = {}      # channel -> {carrier MHz (on the raster): (last seen, peak dBm)}
        self._pending = {}       # channel -> {carrier MHz: first sighting}: seen once, not yet confirmed
        self._packed = {}        # channel -> found to be packed with keyed traffic (stays so while it is heard)
        self._grid = None
        self._blk_sum, self._blk_n, self._blocks = None, 0, []

    def update(self, freq_mhz, power_dbm, channels, margin_db=6.0, ignore=(), now=None,
               rbw_mhz=None, known_lmr=()):
        """
        channels: [(channel, start MHz, stop MHz)]; ignore: [(lo MHz, hi MHz)]
        ranges whose carriers are accounted for; rbw_mhz: the analyzer's
        resolution bandwidth when known (a carrier cannot look narrower);
        known_lmr: channels a transmitter lookup lists land mobile radio on.
        Returns {channel: {"kind": "tv" | "lmr" | "clear", "live": transmitting
        in this sweep, "carriers": distinct carriers heard recently (None when
        too closely packed to count), "peak_dbm", "last_heard_s"}} for every
        channel the sweep covers.

        A channel packed with land mobile carriers, seen through a coarse RBW,
        fills up like a TV channel. It is told apart by its traffic keying
        on and off where TV is steady (which takes some seconds to see), and
        is taken as land mobile radio outright where a lookup says so.
        """
        now = time.time() if now is None else now
        f = np.asarray(freq_mhz, dtype=float)
        p = np.asarray(power_dbm, dtype=float)
        if len(f) < 16:
            return {}
        step = float(np.median(np.diff(f)))
        grid = (len(f), round(float(f[0]), 3), round(float(f[-1]), 3))
        if grid != self._grid:
            self._grid, self._blk_sum, self._blk_n, self._blocks = grid, None, 0, []
        lin = 10.0 ** (p / 10.0)
        self._blk_sum = lin if self._blk_sum is None else self._blk_sum + lin
        self._blk_n += 1
        if self._blk_n >= BLOCK_SWEEPS:
            self._blocks = (self._blocks + [10.0 * np.log10(self._blk_sum / self._blk_n)])[-BLOCKS_KEPT:]
            self._blk_sum, self._blk_n = None, 0
        swing = (np.max(self._blocks, axis=0) - np.min(self._blocks, axis=0)) if len(self._blocks) >= 3 else None
        floor_all = DTVOccupancyDetector.noise_floor(f, p)
        if floor_all is None:
            floor_all = float(np.percentile(p, 20))
        tv = self._tv.update(f, p, channels, margin_db=margin_db)
        results = {}
        for ch, f0, f1 in channels:
            if min(f1, f[-1]) - max(f0, f[0]) < MIN_COVERAGE * (f1 - f0):
                continue                      # mostly outside the sweep: not judged
            sel = (f >= f0) & (f <= f1)
            if sel.sum() < 8:
                continue
            r = tv.get(ch)
            floor = r["floor_dbm"] if r and r.get("floor_dbm") is not None else floor_all
            filled = bool(r and r.get("occupied")) or float(np.median(p[sel])) >= floor + max(6.0, margin_db)
            if filled:
                keyed = swing is not None and int((swing[sel] > KEYED_RANGE_DB).sum()) >= KEYED_POINTS
                if ch in known_lmr or keyed or (now - self._last_lmr.get(ch, -1e9) <= HOLD_S and self._packed.get(ch)):
                    self._packed[ch] = True
                    self._last_lmr[ch] = now
                    results[ch] = {"kind": "lmr", "live": True, "carriers": None,
                                   "peak_dbm": float(p[sel].max()), "last_heard_s": 0.0}
                else:
                    results[ch] = {"kind": "tv", "live": True, "carriers": 0,
                                   "peak_dbm": float(p[sel].max()), "last_heard_s": 0.0}
                continue
            seg, fs = p[sel], f[sel]
            peaks, _ = find_peaks(seg, height=floor + max(MIN_ABOVE_FLOOR_DB, margin_db + 4.0), prominence=6.0)
            # Narrow means narrower than a wireless microphone, as far as the
            # sweep's point spacing can tell
            max_w = max(MAX_LMR_WIDTH_MHZ, 2.2 * step, 1.6 * (rbw_mhz or 0.0))
            seen = self._carriers.setdefault(ch, {})
            pending = self._pending.setdefault(ch, {})
            live = []
            if len(peaks):
                widths = peak_widths(seg, peaks, rel_height=0.5)[0] * step
                for i, w in zip(peaks, widths):
                    fc, lvl = float(fs[i]), float(seg[i])
                    if w > max_w or any(lo <= fc <= hi for lo, hi in ignore):
                        continue
                    key = round(fc / CARRIER_GRID_MHZ) * CARRIER_GRID_MHZ
                    # the sweep's points are coarser than the raster: fold onto a carrier already known nearby
                    known = next((k for k in seen if abs(k - key) <= 2 * step), None)
                    if known is None and lvl < floor + SURE_ABOVE_FLOOR_DB:
                        # A single noise spike does not repeat at the same frequency
                        first = next((k for k in pending if abs(k - key) <= 2 * step), None)
                        if first is None:
                            pending[key] = now
                            continue
                        del pending[first]
                    k = known if known is not None else key
                    seen[k] = (now, max(lvl, seen.get(k, (0, -999.0))[1]))
                    live.append((fc, lvl))
            for k in [k for k, t in pending.items() if now - t > CONFIRM_S]:
                del pending[k]
            for k in [k for k, (t, _l) in seen.items() if now - t > HOLD_S]:
                del seen[k]
            if live:
                self._last_lmr[ch] = now
            last = self._last_lmr.get(ch)
            held = last is not None and now - last <= HOLD_S
            results[ch] = {"kind": "lmr" if held else "clear", "live": bool(live), "carriers": len(seen),
                           "peak_dbm": max((l for _f, l in live), default=float(seg.max())),
                           "last_heard_s": (now - last) if last is not None else None}
        return results
