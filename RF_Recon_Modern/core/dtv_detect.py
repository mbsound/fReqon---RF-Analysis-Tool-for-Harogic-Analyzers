"""
dtv_detect.py - Which TV channels are occupied, from a swept spectrum.

A digital TV signal (ATSC, DVB-T) fills its channel edge to edge with a flat,
noise-like block, well above the noise floor. That shape is what is detected,
rather than a level against a hand-set threshold:

  * the channel's level is the median of its points, so narrowband carriers in
    it (wireless microphones, intermod) do not count unless they fill more
    than half the channel;
  * the noise floor is estimated from the sweep itself, near each channel
    (the quietest blocks within +/- FLOOR_WINDOW_MHZ), so it follows the RBW,
    gain, input chain and any tilt or step across the band;
  * both halves of the channel must be raised alike, so carriers bunched in
    one half, or a signal that only overlaps the channel, are not taken for a
    TV station;
  * sweeps are averaged, and how far a channel must clear the margin depends
    on how noisy the (averaged) trace still is: a clear signal is reported
    from the first sweep, a marginal one once the average has settled, and
    noise is not reported at all;
  * an occupied channel is released only when it falls RELEASE_DB below the
    margin, so one near the margin does not flicker.

A channel only partly inside the sweep is not judged (it keeps its last
state), and neither is any channel when the sweep is under three channels
wide: there the floor cannot be told from a signal. (For the same reason a
sweep in which every channel is occupied at a similar level reads as empty;
sweep wider, or use a fixed threshold.) With a fixed threshold instead of the
automatic floor, the same shape tests apply against that level.
"""

import numpy as np

FLOOR_WINDOW_MHZ = 50.0     # the floor near a channel comes from this far either side of it
FLOOR_BLOCK_MHZ = 1.0       # granularity of the floor estimate...
FLOOR_BLOCK_POINTS = 12     # ...widened to hold this many points (up to half a channel)
FLOOR_QUANTILE = 0.10       # the quietest tenth of those blocks is the floor
MIN_FLOOR_SPAN_CHANNELS = 3 # the sweep must span this many channel widths for an automatic floor
MIN_COVERAGE = 0.9          # share of a channel that must be inside the sweep to judge it
MIN_POINTS = 6              # and at least this many sweep points inside it
EDGE_FRACTION = 0.08        # ignored at each channel edge (filter skirts, neighbours)
RELEASE_DB = 2.0            # hysteresis: an occupied channel clears this far below the margin
SMOOTHING = 0.5             # weight of the newest sweep in the averaged trace
CONFIDENCE = 2.0            # a channel must clear the margin by this many standard errors
HALF_SHARE = 0.5            # share of the channel's rise (dB) that its weaker half must keep


def _scatter(points) -> float:
    """Robust standard deviation of points (dB) about their median."""
    return 1.4826 * float(np.median(np.abs(points - np.median(points))))


class DTVOccupancyDetector:
    def __init__(self):
        self.reset()

    def reset(self):
        """Forget the history (new sweep range, new analyzer, detection restarted)."""
        self._avg = None        # sweeps averaged so far (dBm)
        self._occupied = {}     # channel id -> last decision
        self._grid = None

    def update(self, freq_mhz, power_dbm, channels, margin_db=6.0, threshold_dbm=None):
        """
        Judge the channels covered by one sweep.

        freq_mhz, power_dbm: the sweep (frequencies ascending).
        channels: [(id, start_mhz, stop_mhz)] to judge.
        margin_db: how far above the noise floor a channel must be (automatic mode).
        threshold_dbm: if given, a fixed level replaces the floor + margin.

        Returns {id: {"occupied", "level_dbm", "floor_dbm", "excess_db"}} for the
        channels inside the sweep; excess_db is the level above the noise floor
        (above the threshold in fixed mode), floor_dbm is None in fixed mode.
        """
        freq = np.asarray(freq_mhz, dtype=np.float64)
        power = np.asarray(power_dbm, dtype=np.float64)
        channels = [c for c in channels if c[2] > c[1]]
        if len(freq) < MIN_POINTS or len(freq) != len(power) or freq[-1] <= freq[0] or not channels:
            return {}
        grid = (len(freq), round(float(freq[0]), 3), round(float(freq[-1]), 3))
        if grid != self._grid:      # a different sweep: levels are not comparable with the history
            self.reset()
            self._grid = grid
        self._avg = power.copy() if self._avg is None else (1 - SMOOTHING) * self._avg + SMOOTHING * power
        power = self._avg

        automatic = threshold_dbm is None
        narrowest = min(c[2] - c[1] for c in channels)
        blocks = self._floor_blocks(freq, power, narrowest / 2.0)
        results = {}
        for ch_id, f_start, f_stop in channels:
            width = f_stop - f_start
            covered = min(f_stop, freq[-1]) - max(f_start, freq[0])
            if covered < MIN_COVERAGE * width:
                continue
            if automatic and freq[-1] - freq[0] < MIN_FLOOR_SPAN_CHANNELS * width:
                continue    # too narrow a sweep to tell the noise floor from a signal
            guard = EDGE_FRACTION * width
            i0, i1 = np.searchsorted(freq, (f_start + guard, f_stop - guard))
            if i1 - i0 < MIN_POINTS:
                continue
            pts = power[i0:i1]
            mid = len(pts) // 2
            level = float(np.median(pts))
            weaker_half = float(min(np.median(pts[:mid]), np.median(pts[mid:])))
            floor, floor_err, noise = self._floor_near(blocks, (f_start + f_stop) / 2.0, width)
            # Standard error of a median of n points: 1.2533 * sigma / sqrt(n). The
            # scatter is that of the trace nearby, not of this channel's points:
            # carriers in the channel would otherwise pass for uncertainty.
            level_err = 1.2533 * noise / np.sqrt(len(pts))

            if automatic:
                reference = floor + margin_db
                doubt = CONFIDENCE * float(np.hypot(level_err, floor_err))
            else:
                reference = float(threshold_dbm)
                doubt = CONFIDENCE * level_err
            # A TV signal is a flat block: its weaker half keeps at least half of
            # the channel's rise above the floor (in dB). Carriers bunched in one
            # half, or a signal that only overlaps the channel, do not.
            half_reference = floor + HALF_SHARE * (level - floor)
            half_doubt = CONFIDENCE * level_err * np.sqrt(2.0)

            if self._occupied.get(ch_id, False):
                occupied = level >= reference - RELEASE_DB and weaker_half >= half_reference - RELEASE_DB - half_doubt
            else:
                occupied = level >= reference + doubt and weaker_half >= half_reference - half_doubt
            self._occupied[ch_id] = bool(occupied)
            results[ch_id] = {
                "occupied": bool(occupied),
                "level_dbm": level,
                "floor_dbm": floor if automatic else None,
                "excess_db": level - (floor if automatic else reference),
            }
        return results

    @classmethod
    def noise_floor(cls, freq_mhz, power_dbm, channel_width_mhz=6.0):
        """The noise floor of a whole sweep (dBm), as the detector estimates it; None if it cannot."""
        freq = np.asarray(freq_mhz, dtype=np.float64)
        power = np.asarray(power_dbm, dtype=np.float64)
        if len(freq) < MIN_POINTS or len(freq) != len(power) or freq[-1] <= freq[0]:
            return None
        blocks = cls._floor_blocks(freq, power, channel_width_mhz / 2.0)
        return cls._floor_near(blocks, float(freq.mean()), float(freq[-1] - freq[0]))[0]

    @staticmethod
    def _floor_blocks(freq, power, max_block_mhz):
        """Consecutive blocks of the sweep: (centre MHz, median dBm, point scatter dB, points)."""
        span = freq[-1] - freq[0]
        mhz_per_point = span / (len(freq) - 1)
        block_mhz = min(max(FLOOR_BLOCK_MHZ, FLOOR_BLOCK_POINTS * mhz_per_point), max(max_block_mhz, FLOOR_BLOCK_MHZ))
        n_blocks = max(1, int(span / block_mhz))
        edges = np.searchsorted(freq, np.linspace(freq[0], freq[-1], n_blocks + 1))
        edges[-1] = len(freq)
        rows = [(float(freq[a:b].mean()), float(np.median(power[a:b])), _scatter(power[a:b]), b - a)
                for a, b in zip(edges[:-1], edges[1:]) if b - a >= 3]
        if not rows:
            rows = [(float(freq.mean()), float(np.median(power)), _scatter(power), len(power))]
        return tuple(np.array(col, dtype=np.float64) for col in zip(*rows))

    @staticmethod
    def _floor_near(blocks, centre_mhz, width_mhz):
        """(noise floor dBm, its standard error dB, point scatter dB) around centre_mhz."""
        centres, medians, scatters, counts = blocks
        near = np.abs(centres - centre_mhz) <= FLOOR_WINDOW_MHZ + width_mhz / 2.0
        if not near.any():
            near[:] = True
        # The quietest tenth of noisy block medians lies below the true floor by
        # about their standard error (1.28 of them if every block is empty, less
        # when few are); adding one back removes most of that bias.
        noise = float(np.median(scatters[near]))
        block_err = 1.2533 * noise / np.sqrt(float(np.median(counts[near])))
        return float(np.quantile(medians[near], FLOOR_QUANTILE)) + block_err, block_err, noise
