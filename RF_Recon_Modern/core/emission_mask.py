"""
emission_mask.py - ETSI transmit masks around coordinated carriers.

A coordinated carrier is allowed its channel and, outside it, skirts that fall
away as ETSI EN 300 422-1 (V2.2.1, clause 4.2.4.2.2) lays down, relative to the
transmitter's power and with B the declared channel bandwidth:

    analogue (figure 1)   0 dB to +-B/2, -60 dB at +-B/2, -80 dB at +-B,     -80 dB to +-2.5B
    digital  (figure 2)   0 dB to +-B/2, -30 dB at +-B/2, -80 dB at +-1.75B, -80 dB to +-2.5B
    WMAS     (figure 3)   0 dB to +-B/2, -40 dB at +-B/2, -60 dB at +-B,     -60 dB to +-2.5B

Drawn around each known carrier at the level it is received, the mask is what
that carrier may put next to itself. Anything above it is not that carrier: a
hotter transmitter a little off its centre lifts one skirt through the mask
even though its peak sits inside the channel, where it cannot be told from the
carrier itself.

Two adjustments make the test usable on a sweep (the standard measures with a
1 kHz RBW and an RMS detector):

  * the analyzer's resolution filter smears the carrier, so the mask is moved
    outwards by a pad of a few RBW (and never drawn finer than the sweep's points);
  * the mask stops at the detection threshold: below that nothing is flagged anyway.
"""

import re

import numpy as np

# (offset from the carrier in units of B, level in dB relative to the carrier), outwards
MASKS = {
    "analogue": ((0.5, 0.0), (0.5, -60.0), (1.0, -80.0), (2.5, -80.0)),
    "digital": ((0.5, 0.0), (0.5, -30.0), (1.75, -80.0), (2.5, -80.0)),
    "wmas": ((0.5, 0.0), (0.5, -40.0), (1.0, -60.0), (2.5, -60.0)),
}
MASK_LABEL = {"analogue": "ETSI analogue", "digital": "ETSI digital", "wmas": "ETSI WMAS"}
EXTENT_B = 2.5
PAD_RBW = 2.0               # the mask is moved outwards by this many RBW (or sweep points)
WMAS_MIN_BW_HZ = 1e6        # a declared bandwidth this wide is a WMAS carrier

# Analogue (FM) products by name; everything else coordinated today is digital.
# In-ear monitor transmitters are FM whatever the microphone range next to them is.
_ANALOGUE = re.compile(
    r"\b(psm ?\d+|p10t|p9t|p3t|p6t|ur[1245]\w*|uhf-?r|ulx(?!d)\w*|slx(?!d)\w*|blx\w*|glx\w*|pgx\w*|"
    r"sr ?(iem|2000|2050|300)\w*|ew ?(iem|g[1234]|[135]00|300)\w*|sk ?\d+|skm ?\d+|em ?\d+|"
    r"2000|3000|5000|iem|in-?ear|fm)\b", re.IGNORECASE)


def mask_kind(device: str = "", bandwidth_hz: float = 200e3, is_wmas: bool = False) -> str:
    """Which ETSI mask a coordinated carrier gets, from what the coordination says about it."""
    if is_wmas or bandwidth_hz >= WMAS_MIN_BW_HZ:
        return "wmas"
    return "analogue" if _ANALOGUE.search(device or "") else "digital"


def template_db(kind: str, offset_b):
    """
    Mask level in dB relative to the carrier at |offset| / B. 0 inside the channel;
    -inf beyond the mask's extent (no limit from this carrier there).
    """
    x = np.abs(np.asarray(offset_b, dtype=float))
    pts = MASKS[kind]
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    # the step at B/2: just outside the channel the level is the lower of the two points there
    out = np.interp(x, xs[1:], ys[1:])
    out = np.where(x <= xs[0], 0.0, out)
    return np.where(x > EXTENT_B, -np.inf, out)


def limit_line(freq_hz, power_dbm, carriers, threshold_dbm, margin_db=6.0, rbw_hz=None, force_kind=None,
               idle_top_dbm=None):
    """
    The level above which a point of the sweep is not accounted for by the known carriers.

    carriers: [{"freq_hz", "bw_hz", "name", "kind" (or "device" / "is_wmas" to work it out)}]
    Returns (limit, masks):
      limit   array like power_dbm: +inf inside every carrier's channel (what is in the
              channel is taken as the carrier), each carrier's mask at its received level
              plus margin_db around it, threshold_dbm everywhere else
      masks   per carrier with a signal in its channel: {"carrier", "kind", "ref_dbm",
              "x_hz", "y_dbm" (the mask as drawn), "excess_db", "at_hz" (worst point over
              the mask, None when nothing breaks it), "peak_hz" (strongest point in channel),
              "on_air": True}
              With idle_top_dbm, a carrier that is not on the air is included too, as
              {"on_air": False, ...}: its mask's shape with the top at idle_top_dbm, to show
              what it will claim (it sets no limit: there is no level to hang it on yet).
    """
    f = np.asarray(freq_hz, dtype=float)
    p = np.asarray(power_dbm, dtype=float)
    limit = np.full(len(f), float(threshold_dbm))
    if len(f) < 4:
        return limit, []
    step = float(np.median(np.diff(f)))
    pad = PAD_RBW * max(float(rbw_hz or 0.0), step)
    in_channel = np.zeros(len(f), dtype=bool)
    work = []
    idle = []
    for c in carriers:
        fc, b = float(c["freq_hz"]), max(float(c.get("bw_hz") or 200e3), 1.0)
        if fc + EXTENT_B * b + pad < f[0] or fc - EXTENT_B * b - pad > f[-1]:
            continue
        off = np.abs(f - fc)
        chan = off <= b / 2 + pad
        if not chan.any():
            chan = off <= off.min()                 # the sweep is coarser than the channel: its nearest point
        in_channel |= chan
        ref = float(p[chan].max())
        kind = force_kind or c.get("kind") or mask_kind(c.get("device", ""), b, c.get("is_wmas", False))
        near = off <= EXTENT_B * b + pad
        if ref < threshold_dbm:
            # Carrier not on the air: no level to hang a mask on
            if idle_top_dbm is not None:
                xs = f[near]
                ys = np.where(chan[near], idle_top_dbm,
                              idle_top_dbm + template_db(kind, np.maximum(off[near] - pad, 0.0) / b))
                idle.append({"carrier": c, "kind": kind, "ref_dbm": None, "x_hz": xs, "y_dbm": ys,
                             "excess_db": 0.0, "at_hz": None, "peak_hz": None, "on_air": False})
            continue
        level = ref + margin_db + template_db(kind, np.maximum(off[near] - pad, 0.0) / b)
        level = np.maximum(level, threshold_dbm)
        limit[near] = np.maximum(limit[near], level)
        work.append((c, kind, ref, fc, b, near, chan))
    limit[in_channel] = np.inf
    masks = []
    for c, kind, ref, fc, b, near, chan in work:
        skirt = near & ~in_channel
        excess, at = 0.0, None
        if skirt.any():
            over = p[skirt] - limit[skirt]
            k = int(np.argmax(over))
            if over[k] > 0:
                excess, at = float(over[k]), float(f[skirt][k])
        # The mask as drawn: flat top over the channel, the skirts on both sides
        xs = f[near]
        ys = np.where(chan[near], ref + margin_db,
                      np.maximum(ref + margin_db + template_db(kind, np.maximum(np.abs(xs - fc) - pad, 0.0) / b), threshold_dbm))
        masks.append({"carrier": c, "kind": kind, "ref_dbm": ref, "x_hz": xs, "y_dbm": ys, "on_air": True,
                      "excess_db": excess, "at_hz": at, "peak_hz": float(f[chan][int(np.argmax(p[chan]))])})
    return limit, masks + idle
