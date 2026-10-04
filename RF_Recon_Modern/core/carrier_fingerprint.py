"""
carrier_fingerprint.py - Identify wireless-audio transmitters from their spectra.

Signatures come from manufacturer spec sheets and FCC emission designators (see
docs/carrier_fingerprints.md); none have been confirmed against real units yet.

Each carrier is measured on every sweep (widths, occupied bandwidth, edge
steepness, top flatness, stereo pilot, level) and tracked over time, because
analog FM and TDMA systems only reveal themselves through how the spectrum
changes. Measurements from the main sweep are coarse (fReqon's default scan has
~35 kHz per point); MSCAN spectra (~1 kHz) can be added for the same carriers and
are preferred when present.

classify() returns the best match, ranked alternatives, the evidence used, and a
confidence limited by the resolution available. Systems that cannot be told apart
from the spectrum are reported together (e.g. ADPSM in Axient Digital mode).
"""

from collections import deque
from dataclasses import dataclass, field
import math
import time

import numpy as np

# ---------------------------------------------------------------------------
# Signatures (widths are 99 % occupied bandwidth in kHz)
# ---------------------------------------------------------------------------

DIGITAL, OFDM, SINGLE_CARRIER, ANALOG_MONO, ANALOG_STEREO, TDMA_BLOCK = (
    "digital", "ofdm", "single-carrier", "analog-mono", "analog-stereo", "tdma-block")


@dataclass(frozen=True)
class Signature:
    name: str           # shown to the user
    family: str         # manufacturer / system
    kind: str           # one of the kinds above
    width_khz: float    # expected 99 % occupied bandwidth
    tol_khz: float      # uncertainty of that figure (larger where unpublished)
    color: str
    note: str = ""


SIGNATURES = [
    Signature("Shure Axient Digital", "Shure", SINGLE_CARRIER, 182, 8, "#0288d1",
              "Standard mode (FCC 180-183 kHz). ADPSM in AD Standard/PTP or SC Narrowband "
              "mode looks the same."),
    Signature("Shure Axient Digital HD", "Shure", SINGLE_CARRIER, 100, 22, "#29b6f6",
              "High Density mode (125 kHz spacing; bandwidth not published, ~100 kHz estimated)."),
    Signature("Shure ADPSM Narrowband (OFDM)", "Shure", OFDM, 182, 12, "#7e57c2",
              "Flat-topped OFDM with steep edges."),
    Signature("Shure ADPSM Multi-Channel Wideband", "Shure", OFDM, 650, 150, "#ab47bc",
              "WMAS carrier (FCC 600 kHz; Shure quotes ~800 kHz)."),
    Signature("Shure ADPSM Analog FM / PSM1000", "Shure", ANALOG_STEREO, 110, 35, "#ff9800",
              "Stereo FM with 19 kHz pilot, +/-34 kHz deviation (FCC 96-126 kHz)."),
    Signature("Sony DWX", "Sony", SINGLE_CARRIER, 192, 10, "#00897b",
              "Digital (FCC 192 kHz)."),
    Signature("Sennheiser Digital 6000", "Sennheiser", SINGLE_CARRIER, 172, 10, "#fbc02d",
              "Long Range mode (Digital 9000 transmission, FCC 171-172 kHz)."),
    Signature("Wisycom IEM (MTK982)", "Wisycom", ANALOG_STEREO, 160, 45, "#e91e63",
              "Stereo FM with 19 kHz pilot, +/-48 kHz deviation."),
    Signature("Wisycom transmitter (wideband)", "Wisycom", ANALOG_MONO, 150, 25, "#ff5722",
              "Mono FM, +/-56 kHz peak (Wisycom: ~150 kHz)."),
    Signature("Wisycom transmitter (narrowband)", "Wisycom", ANALOG_MONO, 100, 20, "#ff7043",
              "Mono FM, +/-35 kHz peak (Wisycom: ~100 kHz)."),
    Signature("Sennheiser Spectera", "Sennheiser", TDMA_BLOCK, 5500, 2200, "#8e24aa",
              "WMAS block filling a 6 MHz (US) or 8 MHz (EU) channel, TDMA."),
]

TRACK_TOL_STEPS = 6          # 6 x 25 kHz = 150 kHz, the threat table's matching tolerance

# Wide blocks above this width are WMAS or TV, never single wireless channels
WIDE_BLOCK_KHZ = 3000.0
MIN_HISTORY = 4             # sweeps before analog/digital/TDMA calls are made
MEASURE_WINDOW_HZ = 16e6    # slice of a wide sweep examined around one carrier
PILOT_OFFSET_KHZ = 19.0
PILOT_MAX_RES_KHZ = 3.0     # finer than this is needed to see a 19 kHz pilot
SHAPE_MAX_RES_FRACTION = 0.08   # edge shape is only measurable with bins < 8 % of the width


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

@dataclass
class Measurement:
    t: float
    source: str             # "sweep" or "mscan"
    res_khz: float          # spacing of the spectrum points
    peak_dbm: float
    floor_dbm: float
    w6_khz: float           # width at -6 dB below the top
    w20_khz: float
    w26_khz: float
    obw_khz: float          # 99 % occupied bandwidth
    top_ripple_db: float    # spread of the top (within 3 dB of peak)
    centroid_khz: float     # power centroid relative to the nominal centre
    pilot: bool | None      # stereo pilot seen; None when not resolvable
    lo_hz: float            # extent of the signal (for merging duplicate peaks)
    hi_hz: float
    block_khz: float = 0.0  # gap-tolerant extent (TDMA blocks look ragged when swept)
    holes: float = 0.0      # fraction of that extent >10 dB below the top (TDMA dropouts)
    hole_bits: int = 0      # where those dropouts are: the block in 32 bins, one bit each

    @property
    def snr_db(self) -> float:
        return self.peak_dbm - self.floor_dbm


def _crossing(f, p, i_from, i_to, level):
    """Frequency where p crosses `level` between neighbouring points (linear interp)."""
    if p[i_from] == p[i_to]:
        return f[i_to]
    frac = (p[i_from] - level) / (p[i_from] - p[i_to])
    return f[i_from] + frac * (f[i_to] - f[i_from])


def _width_at(f, p, ipk, level):
    """Width of the contiguous region around ipk that stays above `level`."""
    n = len(p)
    i = ipk
    while i > 0 and p[i - 1] >= level:
        i -= 1
    lo = _crossing(f, p, i, i - 1, level) if i > 0 else f[0]
    j = ipk
    while j < n - 1 and p[j + 1] >= level:
        j += 1
    hi = _crossing(f, p, j, j + 1, level) if j < n - 1 else f[-1]
    return lo, hi


def measure(freq_hz, power_dbm, center_hz, source="sweep", search_khz=None, rbw_khz=None):
    """
    Measure the carrier nearest center_hz in a spectrum. Returns None when there
    is no usable signal (below 10 dB SNR or too few points). rbw_khz is the
    analyzer's resolution bandwidth when known (else the point spacing is used).
    """
    f = np.asarray(freq_hz, dtype=np.float64)
    p = np.asarray(power_dbm, dtype=np.float64)
    if len(f) < 8:
        return None
    edge_lo, edge_hi = float(f[0]), float(f[-1])
    # Everything measured here lies within a few MHz of the carrier (the floor
    # window is +/-12 MHz), so work on that slice of a wide sweep, not all of it
    if edge_hi - edge_lo > 2 * MEASURE_WINDOW_HZ:
        i0, i1 = np.searchsorted(f, (center_hz - MEASURE_WINDOW_HZ, center_hz + MEASURE_WINDOW_HZ))
        f, p = f[i0:i1], p[i0:i1]
        if len(f) < 8:
            return None
    res_khz = max(float(np.median(np.diff(f))) / 1e3, rbw_khz or 0.0)
    # Look for the peak close to the requested centre (a carrier's own top)
    search = (search_khz or max(60.0, 3 * res_khz)) * 1e3
    near = np.where(np.abs(f - center_hz) <= search)[0]
    if len(near) == 0:
        return None
    ipk = int(near[np.argmax(p[near])])
    peak = float(p[ipk])
    # Noise floor: low percentile over a window wider than any single carrier
    # (Spectera/TV blocks are up to 8 MHz wide), or the whole spectrum
    win = np.where(np.abs(f - f[ipk]) <= max(12e6, 40 * res_khz * 1e3))[0]
    floor = float(np.percentile(p[win], 10))
    if peak - floor < 10:
        return None
    # A plateau's "top" is better described by a high percentile than the
    # single highest point (spikes, ripple)
    lo6, hi6 = _width_at(f, p, ipk, peak - 6)
    top = p[(f >= lo6) & (f <= hi6)]
    ref = float(np.percentile(top, 90)) if len(top) > 3 else peak
    lo6, hi6 = _width_at(f, p, ipk, ref - 6)
    lo20, hi20 = _width_at(f, p, ipk, max(ref - 20, floor + 3))
    lo26, hi26 = _width_at(f, p, ipk, max(ref - 26, floor + 3))
    # 99 % occupied bandwidth over the region above the floor
    lo_e, hi_e = _width_at(f, p, ipk, floor + 3)
    sel = (f >= lo_e) & (f <= hi_e)
    lin = 10 ** ((p[sel] - floor) / 10.0) - 1.0
    lin = np.clip(lin, 0, None)
    obw = hi_e - lo_e
    if lin.sum() > 0:
        c = np.cumsum(lin) / lin.sum()
        fs = f[sel]
        obw = float(np.interp(0.995, c, fs) - np.interp(0.005, c, fs))
        centroid = float((fs * lin).sum() / lin.sum()) - center_hz
    else:
        centroid = 0.0
    top3 = p[(f >= lo6) & (f <= hi6) & (p >= ref - 3)]
    ripple = float(np.std(top3)) if len(top3) >= 3 else 0.0
    # Stereo pilot: FM with a 19 kHz pilot shows narrow lines 19 kHz either side
    # of the carrier. Require both sides to stand clear of the spectrum just
    # inside and outside them (one-sided bumps are noise or programme).
    pilot = None
    if res_khz <= PILOT_MAX_RES_KHZ:
        # The pilot sits in the multiplex guard gap (15-23 kHz), so compare it
        # with the spectrum just beside it, inside that gap.
        hits = 0
        for sign in (-1, 1):
            fp = f[ipk] + sign * PILOT_OFFSET_KHZ * 1e3
            d = np.abs(f - fp)
            line = np.where(d <= max(1.2e3, 0.6 * res_khz * 1e3))[0]
            below = np.where((d > 2.5e3) & (d <= 4e3) & (np.abs(f - f[ipk]) < PILOT_OFFSET_KHZ * 1e3))[0]
            above = np.where((d > 2.5e3) & (d <= 4e3) & (np.abs(f - f[ipk]) > PILOT_OFFSET_KHZ * 1e3))[0]
            if len(line) and len(below) and len(above):
                if p[line].max() - max(np.median(p[below]), np.median(p[above])) >= 3.0:
                    hits += 1
        pilot = hits == 2
    # Gap-tolerant extent: a swept analyzer sees a TDMA block piecewise (some
    # points land in silent slots), so close gaps of up to ~300 kHz before
    # measuring how wide the occupied region is.
    # Only points within 25 dB of the surrounding top count, so faint skirts or
    # a neighbouring signal can't be chained in. (The surrounding level, not this
    # point's: inside a ragged TDMA block the nearest peak may be a dropout.)
    near3 = np.abs(f - f[ipk]) <= 3e6
    top_level = max(ref, float(np.percentile(p[near3], 95)))
    above = p >= max(floor + 6, top_level - 25)
    gap = max(3, int(round(300.0 / max(res_khz, 1e-3))))
    closed = np.convolve(above.astype(float), np.ones(2 * gap + 1), mode="same") > 0
    i, j = ipk, ipk
    while i > 0 and closed[i - 1]:
        i -= 1
    while j < len(p) - 1 and closed[j + 1]:
        j += 1
    # A real block is mostly occupied and clearly above the floor; scattered
    # noise points chained by the gap tolerance are neither.
    occupied = above[i:j + 1].mean() if j > i else 1.0
    level_ok = j > i and float(np.median(p[i:j + 1])) >= floor + 8
    block_khz = (f[j] - f[i]) / 1e3 if (occupied > 0.6 and level_ok) else 0.0
    # Inner 80 % of the block, so the sloping edges don't count as holes
    k0, k1 = i + (j - i) // 10, j - (j - i) // 10
    holes = float((p[k0:k1 + 1] < ref - 10).mean()) if (k1 > k0 and block_khz > 0) else 0.0
    hole_bits = 0
    if holes > 0:
        for b, seg in enumerate(np.array_split(p[k0:k1 + 1] < ref - 10, 32)):
            if len(seg) and seg.mean() > 0.5:
                hole_bits |= 1 << b
    # A signal running off the edge of the spectrum can't be measured
    clipped = lo_e <= edge_lo or hi_e >= edge_hi
    if clipped and source == "mscan":
        return None
    return Measurement(
        t=time.time(), source=source, res_khz=res_khz, peak_dbm=peak, floor_dbm=floor,
        w6_khz=(hi6 - lo6) / 1e3, w20_khz=(hi20 - lo20) / 1e3, w26_khz=(hi26 - lo26) / 1e3,
        obw_khz=obw / 1e3, top_ripple_db=ripple, centroid_khz=centroid / 1e3, pilot=pilot,
        lo_hz=float(min(lo_e, f[i])), hi_hz=float(max(hi_e, f[j])), block_khz=float(block_khz),
        holes=holes, hole_bits=hole_bits)


def corrected_width(m: Measurement) -> float:
    """
    Occupied bandwidth with the spectrum's own resolution removed. A spectrum
    point at spacing r smears edges by about r, which widens narrow carriers a
    lot at coarse resolution (fit against synthetic carriers in the tests).
    """
    w, r = m.obw_khz, m.res_khz
    # Flat-topped carriers smear by ~3.2 points; peaked (FM) spectra by about half
    k = 3.2 if m.w26_khz / max(m.w6_khz, 1e-6) < 1.8 else 1.6
    return math.sqrt(max(w * w - (k * r) ** 2, (0.5 * w) ** 2))


# ---------------------------------------------------------------------------
# Tracking and classification
# ---------------------------------------------------------------------------

@dataclass
class Track:
    center_hz: float
    sweeps: deque = field(default_factory=lambda: deque(maxlen=24))
    mscan: deque = field(default_factory=lambda: deque(maxlen=24))


class CarrierFingerprinter:
    """Keeps per-carrier measurement history and classifies on demand."""

    def __init__(self):
        self.tracks: dict[int, Track] = {}
        # Wide blocks are tracked by the block's centre (their strongest point
        # jumps around); carrier keys inside a block alias to the block track.
        self.block_tracks: dict[int, Track] = {}
        self.aliases: dict[int, int] = {}

    @staticmethod
    def _key(center_hz: float) -> int:
        return int(round(center_hz / 25e3))  # 25 kHz tuning raster

    def _track(self, center_hz: float) -> Track:
        k = self._key(center_hz)
        if k in self.aliases and self.aliases[k] in self.block_tracks:
            return self.block_tracks[self.aliases[k]]
        # A carrier's estimated centre wanders by tens of kHz between coarse
        # sweeps, so match an existing track within the threat table's own
        # 150 kHz tolerance, nearest first.
        for dk in sorted(range(-TRACK_TOL_STEPS, TRACK_TOL_STEPS + 1), key=abs):
            if k + dk in self.tracks:
                return self.tracks[k + dk]
        self.tracks[k] = Track(center_hz)
        return self.tracks[k]

    def forget(self, center_hz: float):
        k = self._key(center_hz)
        for dk in sorted(range(-TRACK_TOL_STEPS, TRACK_TOL_STEPS + 1), key=abs):
            if k + dk in self.tracks:
                self.tracks.pop(k + dk)
                break
        self.aliases.pop(k, None)

    def clear(self):
        self.tracks.clear()
        self.block_tracks.clear()
        self.aliases.clear()

    def _block_track(self, m: "Measurement") -> Track:
        """Track for a wide block, keyed by its centre on a 500 kHz grid."""
        centre = (m.lo_hz + m.hi_hz) / 2
        bk = int(round(centre / 500e3))
        for dk in (0, -1, 1, -2, 2):
            if bk + dk in self.block_tracks:
                return self.block_tracks[bk + dk]
        self.block_tracks[bk] = Track(centre)
        return self.block_tracks[bk]

    def update_sweep(self, freq_hz, power_dbm, centers_hz, rbw_hz=None):
        """Measure each carrier centre in one sweep. Returns {centre: Measurement}."""
        out = {}
        t_sweep = time.time()
        for c in centers_hz:
            m = measure(freq_hz, power_dbm, c, "sweep", rbw_khz=(rbw_hz or 0) / 1e3)
            if m is not None:
                m.t = t_sweep      # one time per sweep: a block seen from several peaks is kept once
                if m.block_khz >= WIDE_BLOCK_KHZ:
                    t = self._block_track(m)
                    self.aliases[self._key(c)] = int(round(t.center_hz / 500e3))
                    # one entry per sweep, whichever peak inside the block measured it
                    if not t.sweeps or t.sweeps[-1].t != m.t:
                        t.sweeps.append(m)
                else:
                    self._track(c).sweeps.append(m)
                out[c] = m
        return out

    def update_mscan(self, center_hz, span_hz, spec_dbm):
        """Add one MSCAN spectrum (spec_dbm spans center +/- span/2)."""
        spec = np.asarray(spec_dbm, dtype=np.float64)
        if len(spec) < 16 or span_hz <= 0:
            return None
        freq = center_hz - span_hz / 2 + (np.arange(len(spec)) + 0.5) * span_hz / len(spec)
        m = measure(freq, spec, center_hz, "mscan", search_khz=min(span_hz / 4e3, 120))
        if m is not None:
            self._track(center_hz).mscan.append(m)
        return m

    # -- evidence ------------------------------------------------------------

    @staticmethod
    def _behaviour(ms):
        """Analog / digital / TDMA evidence from how the spectrum changes over time."""
        if len(ms) < MIN_HISTORY:
            return None
        res = float(np.median([m.res_khz for m in ms]))
        widths = np.array([m.w20_khz for m in ms])
        peaks = np.array([m.peak_dbm for m in ms])
        cents = np.array([m.centroid_khz for m in ms])
        w = float(np.median(widths))
        # Widths are interpolated between points, so even at coarse resolution a
        # digital carrier's width holds to ~0.5 %; FM moves 4-20 % with the audio.
        width_cv = float(np.std(widths) / max(w, 1e-6))
        level_sd = float(np.std(peaks))
        wander = float(np.std(cents))
        ripple = float(np.median([m.top_ripple_db for m in ms]))
        holes = float(np.median([m.holes for m in ms]))
        holes_sd = float(np.std([m.holes for m in ms]))
        # Fraction of the block whose dropout state changes from one sweep to the next
        pairs = [(a.hole_bits, b.hole_bits) for a, b in zip(ms[:-1], ms[1:])]
        churn = float(np.mean([bin(a ^ b).count("1") for a, b in pairs])) / 32.0 if pairs else 0.0
        return {
            "width_cv": width_cv, "level_sd": level_sd, "wander_khz": wander,
            "res_khz": res, "n": len(ms), "ripple_db": ripple, "holes": holes,
            "varies": width_cv > 0.035 or wander > max(4.0, 0.5 * res),
            "steady": width_cv < 0.015 and wander < max(3.0, 0.4 * res),
            # TDMA: a swept analyzer catches different devices (or silence) at
            # different points, so the block is ragged and changes each sweep
            # TDMA (WMAS) shows as dropouts inside the block that move from sweep
            # to sweep. Level spread and ripple alone are not evidence: a TV
            # signal seen through multipath has several dB of both.
            # (Fixed notches from multipath are dropouts too, but they stay where
            # they are; TDMA dropouts land somewhere else on every sweep.)
            "flicker": holes > 0.05 and churn > 0.08,
            "holes_sd": holes_sd, "hole_churn": churn,
        }

    @staticmethod
    def _shape(ms):
        """
        Spectral shape. Peakedness (width at -26 dB over width at -6 dB) works at
        any resolution: FM has a strong central carrier line (2.4-9) while digital
        carriers are flat-topped (1.0-1.75 even at 35 kHz per point). Telling OFDM
        (vertical edges, ~1.04) from single-carrier digital (~1.15) needs ~2 kHz.
        """
        if len(ms) < 2:
            return None
        sf = float(np.median([m.w26_khz / max(m.w6_khz, 1e-6) for m in ms]))
        # Coarse resolution rounds every edge: a digital carrier measures about
        # 1.10 + 1.8 x (resolution / width); FM sits above that line.
        res_ratio = float(np.median([m.res_khz / max(m.w6_khz, 1e-6) for m in ms]))
        expected_digital = 1.10 + 1.8 * res_ratio
        fine = [m for m in ms if m.res_khz <= 2.0 and m.res_khz <= SHAPE_MAX_RES_FRACTION * m.w6_khz]
        sf_fine = float(np.median([m.w26_khz / max(m.w6_khz, 1e-6) for m in fine])) if len(fine) >= 2 else None
        ripple = float(np.median([m.top_ripple_db for m in ms]))
        return {"shape_factor": sf, "expected_digital": expected_digital, "ripple_db": ripple,
                "rounded": sf > expected_digital + 0.15,
                "flat": sf < expected_digital + 0.08,
                "brickwall": None if sf_fine is None else sf_fine < 1.10}

    # -- classification ------------------------------------------------------

    def classify(self, center_hz: float) -> dict:
        t = self._track(center_hz)
        hi_res = list(t.mscan)
        sweeps = list(t.sweeps)
        ms = hi_res if len(hi_res) >= 2 else sweeps
        if not ms:
            return _result("Unknown carrier", "RF carrier", 0, [], ["No measurable signal yet"])
        best_res = min(m.res_khz for m in ms)
        widths = [max(corrected_width(m), m.block_khz if m.block_khz >= WIDE_BLOCK_KHZ else 0.0) for m in ms]
        width = float(np.median(widths))
        width_peak = float(np.percentile(widths, 90))
        # Temporal behaviour uses whichever source has history (sweeps usually do)
        beh = self._behaviour(hi_res) if len(hi_res) >= MIN_HISTORY else self._behaviour(sweeps)
        shape = self._shape(ms)
        # The pilot only shows as a line in quiet passages (heavy programme
        # smears it into the FM sidebands), so a few sightings are enough and
        # never seeing it proves nothing.
        pilots = [m.pilot for m in ms if m.pilot is not None]
        seen = sum(1 for x in pilots if x)
        pilot = True if seen >= max(2, 0.15 * len(pilots)) else None

        evidence = [f"Width ~{width:.0f} kHz (99 %), resolution {best_res:.1f} kHz"
                    + (" from MSCAN" if ms is hi_res else " from sweep")]
        extent = (min(m.lo_hz for m in ms[-3:]), max(m.hi_hz for m in ms[-3:]))

        # 1. Wide blocks: WMAS or TV
        if width >= WIDE_BLOCK_KHZ:
            flicker = beh and beh["flicker"]
            if beh:
                evidence.append(f"Level spread {beh['level_sd']:.1f} dB over {beh['n']} sweeps; "
                                f"{beh['holes'] * 100:.0f} % of the block in dropouts")
            if flicker:
                return _result("Sennheiser Spectera", "WMAS (TDMA)", 70,
                               [("Sennheiser Spectera", 70)], evidence + ["Level flickers between sweeps (TDMA)"],
                               "#8e24aa", digital=True, extent=extent)
            if beh and not flicker:
                return _result("Wideband block (TV or WMAS)", "Wideband", 45,
                               [("Digital TV", 50), ("Sennheiser Spectera", 35)],
                               evidence + ["Steady level: more like TV than TDMA WMAS"],
                               "#9e9e9e", digital=True, extent=extent)
            return _result("Wideband block", "Wideband", 25, [("Digital TV", 40), ("Sennheiser Spectera", 40)],
                           evidence + ["Watching level over time"], "#9e9e9e", digital=True, extent=extent)

        # 2. Too narrow to be wireless audio, or narrower than the resolution
        w6 = float(np.median([m.w6_khz for m in ms]))
        # (A large 99 % width with a narrow -6 dB core is a noisy skirt, not a
        # resolved signal; a 99 % width within ~1 bin of the resolution is unresolved.)
        if best_res > 5 and ((w6 < 1.5 * best_res and width < 3 * best_res) or width <= 1.2 * best_res):
            return _result(f"Narrow carrier (< ~{1.5 * best_res:.0f} kHz)", "Unresolved", 20, [],
                           evidence + [f"No wider than the {best_res:.0f} kHz resolution"],
                           "#9e9e9e", extent=extent,
                           suggestion="Fingerprint with MSCAN or narrow the span to resolve it")
        if width < 20:
            return _result(f"Narrowband carrier (~{max(width, best_res):.0f} kHz)", "Not wireless audio", 60, [],
                           evidence + ["Far narrower than any wireless microphone or IEM "
                                       "(e.g. unmodulated carrier, telemetry, oscillator leakage)"],
                           "#9e9e9e", extent=extent)

        # 3. Analog vs digital
        analog_votes, digital_votes = 0.0, 0.0
        if beh:
            evidence.append(f"Width variation {beh['width_cv'] * 100:.1f} %, "
                            f"centre wander {beh['wander_khz']:.1f} kHz over {beh['n']} measurements")
            if beh["varies"]:
                analog_votes += 1.0
            elif beh["steady"]:
                digital_votes += 1.0
        if shape:
            evidence.append(f"Peakedness {shape['shape_factor']:.2f} (-26/-6 dB width; "
                            f"digital would be ~{shape['expected_digital']:.2f} at this resolution)")
            if shape["rounded"]:
                analog_votes += 1.5
            elif shape["flat"]:
                digital_votes += 1.5
            if shape["brickwall"] is not None:
                evidence.append("Vertical edges (OFDM)" if shape["brickwall"] else "Rounded edges (single carrier)")
        if pilot is True:
            evidence.append(f"19 kHz stereo pilot seen in {seen} of {len(pilots)} spectra")
            analog_votes += 2.0
        elif pilots:
            evidence.append("No 19 kHz pilot seen yet (it only shows in quiet passages)")
        if analog_votes == 0 and digital_votes == 0:
            nature = None
        else:
            nature = "analog" if analog_votes > digital_votes else "digital"

        # 4. Score signatures by width, filtered by nature and shape. FM only
        # reaches its full bandwidth on loud passages, so analog signatures are
        # compared with the widest recent measurements (like max-hold).
        sigma_meas = max(3.0, 0.6 * best_res, 0.04 * width)
        scores = []
        for s in SIGNATURES:
            if s.kind == TDMA_BLOCK:
                continue
            w_obs = width_peak if s.kind in (ANALOG_MONO, ANALOG_STEREO) else width
            z = (w_obs - s.width_khz) / math.sqrt(s.tol_khz ** 2 + sigma_meas ** 2)
            sc = math.exp(-0.5 * z * z)
            is_analog = s.kind in (ANALOG_MONO, ANALOG_STEREO)
            if nature == "analog":
                sc *= 1.0 if is_analog else 0.15
            elif nature == "digital":
                sc *= 0.15 if is_analog else 1.0
            if s.kind == ANALOG_STEREO and pilot is False:
                sc *= 0.2
            if s.kind == ANALOG_MONO and pilot is True:
                sc *= 0.2
            if shape and shape["brickwall"] is not None and s.kind == OFDM and s.width_khz < 400:
                sc *= 1.0 if shape["brickwall"] else 0.2
            if shape and shape["brickwall"] is not None and s.kind == SINGLE_CARRIER:
                sc *= 0.2 if shape["brickwall"] else 1.0
            scores.append((s, sc))
        scores.sort(key=lambda x: -x[1])
        total = sum(sc for _, sc in scores) or 1.0
        best, best_sc = scores[0]
        ranked = [(s.name, round(100 * sc / total)) for s, sc in scores[:4] if sc / total >= 0.05]

        kind_word = "analog" if nature == "analog" else "digital" if nature == "digital" else None
        if best_sc < 0.08:
            name = f"Unknown {kind_word or 'carrier'}"
            return _result(name, "Unidentified", 30, ranked, evidence + [
                f"No known system is ~{width:.0f} kHz wide"], "#9e9e9e", digital=nature == "digital",
                extent=extent)

        # At coarse resolution several digital systems of similar width are
        # equally plausible; name the group instead of picking one.
        digital_kinds = (SINGLE_CARRIER, OFDM)
        if best_res > 20 and best.kind in digital_kinds and best.width_khz < 400:
            group = [s for s, sc in scores if s.kind in digital_kinds and sc >= 0.5 * best_sc]
            if len(group) >= 3:
                names = ", ".join(dict.fromkeys(s.name.replace("Shure ", "").replace("Sennheiser ", "")
                                                for s in group))
                return _result(f"Digital wireless ~{width:.0f} kHz", "Digital (system not resolved)",
                               min(45, round(100 * sum(sc for s, sc in scores if s in group) / total)),
                               ranked, evidence + [f"At {best_res:.0f} kHz resolution this could be: {names}"],
                               "#0288d1", digital=True, extent=extent,
                               suggestion="Fingerprint with MSCAN to identify the system",
                               details=f"Candidates: {names}.")

        conf = 100.0 * best_sc / total
        # Limits: what this resolution and history can support
        cap = 90
        if best_res > 10:
            cap = 55
        elif best_res > 4:
            cap = 70
        if nature is None:
            cap = min(cap, 50)
        conf = min(conf, cap)
        suggestion = ""
        if best_res > 4 and best.kind != ANALOG_STEREO:
            suggestion = "Fingerprint with MSCAN for a firmer identification"
        name = best.name
        same_width_twins = best.name == "Shure Axient Digital"
        details = best.note
        # Close runners-up can't be ruled out at this resolution: name them together
        if len(scores) > 1 and scores[1][1] >= 0.75 * best_sc:
            second = scores[1][0]
            name = f"{best.name} or {second.name.replace(best.family + ' ', '')}"
            details = f"{best.note} Indistinguishable here from {second.name}: {second.note}"
            same_width_twins = False
        res = _result(name, best.family + (" (digital)" if kind_word == "digital" else
                                           " (analog)" if kind_word == "analog" else ""),
                      round(conf), ranked, evidence, best.color, digital=best.kind not in
                      (ANALOG_MONO, ANALOG_STEREO), extent=extent, suggestion=suggestion,
                      details=details)
        if same_width_twins:
            res["details"] += " Cannot be separated from those modes by spectrum alone."
        return res


def _result(device, category, confidence, candidates, evidence, color="#9e9e9e",
            digital=None, extent=None, suggestion="", details=""):
    return {
        "device": device,
        "category": category,
        "confidence": int(confidence),
        "candidates": candidates,
        "evidence": evidence,
        "details": details or "; ".join(evidence[:2]),
        "color": color,
        "is_digital": digital,
        "extent_hz": extent,
        "suggestion": suggestion,
    }
