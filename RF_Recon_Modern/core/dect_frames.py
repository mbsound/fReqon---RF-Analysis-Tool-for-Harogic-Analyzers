"""
dect_frames.py - Antennas and active beltpacks on a DECT carrier, from a zero-span capture.

DECT (and Riedel Bolero, which is DECT) is TDMA/TDD: a 10 ms frame of 24 slots
of 416.67 us, each carrying one ~364 us burst. The first twelve slots are the
downlink (antenna to beltpack), the second twelve the uplink (beltpack to
antenna), and a call's uplink slot is exactly 12 slots (5 ms) after its
downlink slot. An antenna transmits a beacon in a downlink slot every frame
whether or not anyone is talking, at a steady level (it does not move); a
beltpack transmits only during a call, and its level wanders with distance,
orientation and the body in the way.

So a zero-span capture of a few frames tells, per carrier:

  * downlink bursts (every frame, steady level)  -> antennas, plus one per call
  * uplink bursts (5 ms after a downlink burst)   -> active beltpacks

Frame timing and carrier parameters are those of the DECT standard (ETSI EN 300 175).
"""

import numpy as np

FRAME_S = 10e-3
SLOTS = 24
SLOT_S = FRAME_S / SLOTS            # 416.67 us
BURST_S = 364e-6
HALF = SLOTS // 2                   # slots 0-11 downlink, 12-23 uplink

MIN_BURST_S = 120e-6                # shorter: a noise spike
MAX_BURST_S = 650e-6                # longer: bursts in adjacent slots run together (coarse sampling)
CONTINUOUS_S = HALF * SLOT_S        # above threshold for half a frame or more: not DECT at all
MERGE_GAP_S = 25e-6                 # dropouts inside a burst shorter than this are joined (the gap between slots is 52 us)
STEADY_PRESENCE = 0.9               # an antenna's beacon is in (nearly) every frame
STEADY_LEVEL_DB = 2.5               # ... at a level that does not wander more than this


def bursts(t_s, p_dbm, threshold_dbm):
    """
    Bursts above threshold_dbm: (start_s, end_s, peak_dbm) arrays, and whether the
    capture is dominated by a continuous signal (energy above threshold for longer
    than any DECT burst).
    """
    t = np.asarray(t_s, dtype=float)
    p = np.asarray(p_dbm, dtype=float)
    on = p >= threshold_dbm
    if not on.any():
        return np.zeros(0), np.zeros(0), np.zeros(0), False
    edges = np.diff(on.astype(np.int8))
    starts = list(np.nonzero(edges == 1)[0] + 1)
    ends = list(np.nonzero(edges == -1)[0] + 1)
    if on[0]:
        starts.insert(0, 0)
    if on[-1]:
        ends.append(len(on))
    # Join runs separated by a gap too short to be the space between slots
    merged = []
    for s, e in zip(starts, ends):
        if merged and t[s] - t[merged[-1][1] - 1] <= MERGE_GAP_S:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    out_s, out_e, out_p = [], [], []
    continuous = False
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.0
    for s, e in merged:
        length = t[e - 1] - t[s] + dt
        if length < MIN_BURST_S:
            continue
        if length >= CONTINUOUS_S:
            continuous = True
            continue
        if length > MAX_BURST_S:
            # Bursts in adjacent slots, with the 52 us gap between them lost to coarse
            # sampling: one burst per slot's worth
            n = int(round(length / SLOT_S))
            for k in range(n):
                a, b = t[s] + k * SLOT_S, t[s] + k * SLOT_S + BURST_S
                sel = (t >= a) & (t < b)
                out_s.append(a)
                out_e.append(b)
                out_p.append(float(p[sel].max()) if sel.any() else float(p[s:e].max()))
            continue
        out_s.append(t[s])
        out_e.append(t[e - 1] + dt)
        out_p.append(float(p[s:e].max()))
    return np.array(out_s), np.array(out_e), np.array(out_p), continuous


def analyse(t_s, p_dbm, threshold_dbm):
    """
    Antennas and active beltpacks on the carrier a zero-span capture was taken on.
    t_s: sample times in seconds, p_dbm: level per sample. Returns a dict:

      frames       whole 10 ms frames the capture covers (None result if under 2)
      slots        24 characters: "F" a downlink burst (antenna), "P" an uplink
                   burst (beltpack), "." empty; slot 0 is the first downlink slot
      antennas     downlink bursts not accounted for by calls (at least 1 if any)
      calls        uplink bursts: beltpacks on active calls
      bursts       bursts found
      continuous   energy above threshold for longer than any DECT burst: not DECT
      levels       {slot: median peak dBm}
    """
    t = np.asarray(t_s, dtype=float)
    if len(t) < 16:
        return None
    frames = int((t[-1] - t[0]) // FRAME_S)
    if frames < 2:
        return None
    s, e, pk, continuous = bursts(t, p_dbm, threshold_dbm)
    result = {"frames": frames, "slots": "." * SLOTS, "antennas": 0, "calls": 0,
              "bursts": int(len(s)), "continuous": continuous, "levels": {}}
    if len(s) == 0:
        return result
    centre = (s + e) / 2.0
    # Every burst sits on the same slot grid: its phase within a slot is shared.
    # The grid's phase is the circular mean of the burst phases.
    ph = (centre % SLOT_S) / SLOT_S * 2 * np.pi
    grid = (np.arctan2(np.sin(ph).mean(), np.cos(ph).mean()) / (2 * np.pi)) % 1.0 * SLOT_S
    idx = np.round((centre - grid) / SLOT_S).astype(int) % SLOTS      # slot within some frame rotation
    # Which bursts are antennas: present in (nearly) every frame at a steady level
    kind = {}
    for k in np.unique(idx):
        sel = idx == k
        present = sel.sum() / frames
        steady = present >= STEADY_PRESENCE and (sel.sum() < 2 or float(np.std(pk[sel])) <= STEADY_LEVEL_DB)
        kind[int(k)] = ("F" if steady else "P", float(np.median(pk[sel])))
    # A steady burst exactly 5 ms after another steady one is that call's uplink, not an
    # antenna: of the pair, the one whose level wanders less is the antenna
    for k in list(kind):
        mate = (k + HALF) % SLOTS
        if kind[k][0] == "F" and kind.get(mate, ("", 0))[0] == "F":
            spread = lambda j: float(np.std(pk[idx == j])) if (idx == j).sum() > 1 else 0.0
            loser = k if spread(k) > spread(mate) else mate
            kind[loser] = ("P", kind[loser][1])
    # Rotate the slot numbering so that antennas fall in the downlink half (0-11) and
    # beltpacks in the uplink half (12-23), the first antenna slot as low as possible
    best = None
    for r in range(SLOTS):
        score = sum(1 for k, (c, _l) in kind.items()
                    if (c == "F") == (((k - r) % SLOTS) < HALF))
        first_f = min([((k - r) % SLOTS) for k, (c, _l) in kind.items() if c == "F"], default=0)
        if best is None or (score, -first_f) > best[0]:
            best = ((score, -first_f), r)
    r = best[1]
    slots = ["."] * SLOTS
    levels = {}
    for k, (c, lvl) in kind.items():
        j = (k - r) % SLOTS
        slots[j] = c
        levels[j] = lvl
    n_f = slots.count("F")
    n_p = slots.count("P")
    result.update({"slots": "".join(slots), "calls": n_p,
                   "antennas": (max(1, n_f - n_p) if n_f else 0), "levels": levels})
    return result


def synth_capture(frames=3, dt_s=1.024e-6, fp_slots=(0,), pp_slots=(), noise_dbm=-100.0,
                  fp_dbm=-50.0, pp_dbm=-60.0, pp_wander_db=6.0, offset_s=1.3e-3, seed=0):
    """A synthetic zero-span capture of a DECT carrier, for tests and demos."""
    rng = np.random.default_rng(seed)
    n = int(round(frames * FRAME_S / dt_s)) + 1
    t = np.arange(n) * dt_s
    p = noise_dbm + rng.normal(0, 1.0, n)
    for f in range(frames + 1):
        for slot in fp_slots:
            start = offset_s + f * FRAME_S + slot * SLOT_S
            p[(t >= start) & (t < start + BURST_S)] = fp_dbm + rng.normal(0, 0.3)
        for slot in pp_slots:
            start = offset_s + f * FRAME_S + slot * SLOT_S
            p[(t >= start) & (t < start + BURST_S)] = pp_dbm + rng.normal(0, pp_wander_db)
    return t, p
