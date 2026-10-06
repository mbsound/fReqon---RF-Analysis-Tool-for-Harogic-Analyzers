"""
sensor_net.py - Several analyzers watching the same band from known places.

Each sensor (one analyzer slot) sweeps the band; this module keeps, per sensor,
the carriers it sees and their levels plus a fingerprinter, merges the carriers
across sensors, and for each one estimates where the transmitter is
(core.geolocate) and what it is (a vote over the sensors' fingerprints).

Sensor positions come from the analyzer's GNSS fix when it has one, or are
entered by hand (lat/lon, or metres on a venue drawing). Everything is solved
in a local east/north frame in metres.
"""

from dataclasses import dataclass, field
import math
import time

import numpy as np
from scipy import signal

from .carrier_fingerprint import CarrierFingerprinter
from .geolocate import rss_locate, rss_centroid, vote_device, enu_from_latlon, latlon_from_enu, Fix

MATCH_HZ = 150e3            # a carrier seen by two sensors within this is the same carrier
STALE_S = 10.0              # a sensor's sighting counts for this long
TDOA_FRESH_S = 300.0        # a time-difference fix is shown this long (the transmitter may move)
MEASURE_PERIOD_S = 0.1      # fingerprint measurements per sensor per carrier
SOLVE_PERIOD_S = 1.0        # position/device refresh
# Carriers are looked for in the average of the last sweeps, not in single sweeps: one sweep
# of noise alone has points 10 dB and more above its floor, somewhere different every time,
# and each of those used to be listed (and given a device name). Averaged, the noise is
# within a few dB of flat and what stands out of it is there sweep after sweep.
AVG_SWEEPS = 16             # sweeps in the running average
MIN_AVG_SWEEPS = 8          # nothing is detected before this many
MIN_PROMINENCE_DB = 6.0     # a carrier stands this far out of what is around it (ripple on a TV channel does not)
# A GNSS fix on a weak signal or few satellites can be tens of metres out, steadily: flagged
WEAK_FIX_SNR_DBHZ = 25      # average signal of the satellites in use, below this
WEAK_FIX_SATS = 6           # satellites in use, fewer than this
IDENTIFY_MIN_SNR_DB = 20.0  # below this over the floor, at the best sensor, a carrier is listed but not named


@dataclass
class Sensor:
    slot_id: str
    name: str = ""
    # position: "gnss" uses the analyzer's fix; "manual" uses lat/lon or x/y below
    position_source: str = "gnss"
    lat: float = None
    lon: float = None
    alt: float = 0.0
    x_m: float = None            # manual local coordinates (venue drawing), east/north metres
    y_m: float = None
    gnss: dict = field(default_factory=dict)      # latest from the analyzer
    # A sensor stands still, and single fixes wander by metres: the position used is the
    # mean of the fixes so far (started again if the sensor is moved)
    fix_n: int = 0
    fix_lat: float = 0.0
    fix_lon: float = 0.0
    fix_alt: float = 0.0
    fix_var_m2: float = 0.0       # mean squared distance of the fixes from their mean
    gain_db: float = 0.0         # antenna gain relative to the other sensors, if not in an input chain
    fingerprinter: CarrierFingerprinter = field(default_factory=CarrierFingerprinter)
    sightings: dict = field(default_factory=dict)   # carrier key (Hz, rounded) -> (level, floor, last_seen)
    last_sweep: tuple = None
    last_measure: float = 0.0
    floor_dbm: float = -120.0
    avg_mw: object = None        # running average of the sweeps (linear power), and how many are in it
    avg_n: int = 0
    avg_span: tuple = None

    def has_fix(self) -> bool:
        g = self.gnss
        # (The first report after connecting can say "locked" with no satellites and a
        # height of zero: values from before any data arrived. That is not a fix.)
        return bool(g) and bool(g.get("lock")) and g.get("lat") not in (None, 0.0) and g.get("sats", 1) != 0

    MOVED_M = 40.0                # a fix this far from the mean: the sensor has been moved
    MAX_FIXES = 720               # the mean follows slow drift (an hour of fixes at 5 s)

    def add_fix(self, info: dict):
        """Take a GNSS report from the analyzer; locked fixes go into the mean position."""
        self.gnss = dict(info)
        if not self.has_fix():
            return
        lat, lon, alt = float(info["lat"]), float(info["lon"]), float(info.get("alt") or 0.0)
        if self.fix_n:
            d = math.hypot((lat - self.fix_lat) * 111320.0,
                           (lon - self.fix_lon) * 111320.0 * math.cos(math.radians(self.fix_lat)))
            if d > self.MOVED_M:
                self.fix_n = 0
        if not self.fix_n:
            self.fix_n, self.fix_lat, self.fix_lon, self.fix_alt, self.fix_var_m2 = 1, lat, lon, alt, 0.0
            return
        n = min(self.fix_n + 1, self.MAX_FIXES)
        self.fix_var_m2 += (d * d - self.fix_var_m2) / n
        self.fix_lat += (lat - self.fix_lat) / n
        self.fix_lon += (lon - self.fix_lon) / n
        self.fix_alt += (alt - self.fix_alt) / n
        self.fix_n = n

    def fix_spread_m(self):
        """How far single fixes fall from the mean (RMS, metres); None with fewer than two."""
        return math.sqrt(self.fix_var_m2) if self.fix_n >= 2 else None

    def gnss_summary(self) -> str:
        """One line on the GNSS receiver: fix, satellites, signal, altitude, time, reference."""
        g = self.gnss
        if not g:
            return "No GNSS data from this analyzer."
        if not self.has_fix():
            seen = f", {g['sats_in_view']} satellites in view" if g.get("sats_in_view") else ""
            return f"Waiting for a GNSS fix{seen}."
        parts = [f"{self.fix_lat:.6f}, {self.fix_lon:.6f}"]
        spread = self.fix_spread_m()
        parts.append(f"mean of {self.fix_n} fixes" + (f", ±{spread:.1f} m" if spread is not None else ""))
        sats = f"{g.get('sats_used', g.get('sats', '?'))} satellites"
        if g.get("sats_in_view"):
            sats += f" of {g['sats_in_view']} in view"
        if g.get("snr_avg"):
            sats += f", signal {g['snr_avg']} dB-Hz"
            if g.get("snr_min") and g.get("snr_max"):
                sats += f" ({g['snr_min']} to {g['snr_max']})"
        parts.append(sats)
        parts.append(f"altitude {self.fix_alt:.0f} m")
        t = g.get("time")
        if t and t[0]:
            parts.append(f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d} UTC")
        off = g.get("ref_offset_ppm")
        off_txt = f"{off:+.2f} ppm from GNSS" if off is not None else ""
        if g.get("docxo_lock"):
            ref = "reference locked to GNSS" + (f" ({off_txt})" if off_txt else "")
        elif g.get("ocxo_type") == 0:
            # No oscillator to discipline in this analyzer: the reference runs free, and its
            # error against GNSS is measured instead
            ref = "reference free-running" + (f", measured {off_txt}" if off_txt else " (no disciplined oscillator)")
        else:
            ref = ("reference not locked to GNSS" + (" (holding)" if g.get("docxo_mode") == "hold" else "")
                   + (f", {off_txt}" if off_txt else ""))
        parts.append(ref)
        return " · ".join(parts)

    def latlon(self):
        if self.position_source == "gnss" and self.has_fix():
            if self.fix_n:
                return self.fix_lat, self.fix_lon, self.fix_alt
            return self.gnss["lat"], self.gnss["lon"], self.gnss.get("alt") or 0.0
        if self.lat is not None and self.lon is not None:
            return self.lat, self.lon, self.alt or 0.0
        return None

    def gnss_rows(self):
        """
        The GNSS receiver's state as [(label, value)] (what the analyzer's own software
        lists: lock, position, height, satellites, signal, time, reference), or a sentence
        when there is nothing to tabulate.
        """
        g = self.gnss
        if not g:
            return "No GNSS data from this analyzer."
        if not self.has_fix():
            n = g.get("sats_in_view") or 0
            seen = f"{n} satellite{'' if n == 1 else 's'} in view" if n else "no satellites in view yet"
            return [("Lock", "<span style='color:#f59e0b'>Searching</span>"), ("Satellites", seen)]
        spread = self.fix_spread_m()
        weak = self.weak_fix()
        rows = [("Lock", "<span style='color:#10b981'>Locked</span>")]
        if weak:
            rows = [("Lock", "<span style='color:#f59e0b'>Locked, weak fix</span>"),
                    ("", f"<span style='color:#f59e0b'>Position unreliable ({weak}): it can be tens of metres out</span>")]
        rows += [("Position", f"{self.fix_lat:.6f}, {self.fix_lon:.6f}"),
                ("", f"mean of {self.fix_n} fixes" + (f", ±{spread:.1f} m" if spread is not None else "")),
                ("Height", f"{self.fix_alt:.0f} m")]
        used = g.get('sats_used', g.get('sats', '?'))
        sats = f"{used} used"
        if g.get("sats_in_view"):
            sats += f" of {g['sats_in_view']} in view"
            unused = g["sats_in_view"] - (used if isinstance(used, int) else 0)
            if unused > 0 and g.get("snr_unused_avg"):
                sats += f" ({unused} tracked but not used, {g['snr_unused_avg']} dB-Hz)"
        rows.append(("Satellites", sats))
        if g.get("snr_avg"):
            rows.append(("Signal", f"{g['snr_avg']} dB-Hz average"
                         + (f" ({g['snr_min']} to {g['snr_max']})" if g.get("snr_min") and g.get("snr_max") else "")))
        t = g.get("time")
        if t and t[0]:
            rows.append(("Time", f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d} UTC"))
        off = g.get("ref_offset_ppm")
        off_txt = f"{off:+.2f} ppm" if off is not None else ""
        if g.get("docxo_lock"):
            ref = "locked to GNSS" + (f" ({off_txt})" if off_txt else "")
        elif g.get("ocxo_type") == 0:
            ref = "free-running" + (f", {off_txt} from GNSS" if off_txt else "")
        else:
            ref = "not locked to GNSS" + (f", {off_txt}" if off_txt else "")
        rows.append(("Reference", ref))
        return rows

    def weak_fix(self):
        """Why the present fix should not be trusted for the sensor's position ("signal 9 dB-Hz,
        4 satellites"), or None when it is sound or there is no fix."""
        if self.position_source != "gnss" or not self.has_fix():
            return None
        g = self.gnss
        why = []
        snr = g.get("snr_avg")
        if snr and snr < WEAK_FIX_SNR_DBHZ:
            why.append(f"signal {snr} dB-Hz")
        used = g.get("sats_used", g.get("sats"))
        if used is not None and used < WEAK_FIX_SATS:
            why.append(f"{used} satellite{'' if used == 1 else 's'}")
        return ", ".join(why) or None

    def restart_average(self):
        """Forget the fixes averaged so far (the antenna was moved, or they were taken on a weak signal)."""
        self.fix_n, self.fix_var_m2 = 0, 0.0

    def went_offline(self):
        """The analyzer is disconnected: its last GNSS report no longer describes it. (The mean
        of its fixes is kept: reconnected in the same place, it carries on from there.)"""
        self.gnss = {}

    def table_fields(self) -> dict:
        """What the sensor table shows besides the position: height, satellites, lock."""
        g = self.gnss or {}
        fix = self.has_fix()
        if self.position_source == "gnss":
            lock = ("Weak fix" if self.weak_fix() else "Locked") if fix else ("Searching" if g else "No GNSS")
        else:
            lock = "Manual" if (self.x_m is not None or self.lat is not None) else "No position"
        ll = self.latlon()
        height = f"{ll[2]:.0f} m" if (ll and self.position_source == "gnss") else ""
        used, view = g.get("sats_used", g.get("sats")), g.get("sats_in_view")
        if not g:
            sats = ""
        elif fix and used:
            sats = f"{used}/{view}" if view else f"{used}"
        else:
            sats = f"0/{view}" if view else "0"
        return {"height": height, "sats": sats, "lock": lock, "has_fix": fix, "weak": self.weak_fix() or ""}

    def status(self) -> str:
        if self.position_source == "gnss":
            if self.has_fix():
                return f"GNSS fix ({self.gnss.get('sats', '?')} sats)"
            return "waiting for GNSS fix" if self.gnss else "no GNSS data"
        if self.x_m is not None and self.y_m is not None:
            return "manual (x/y)"
        if self.lat is not None:
            return "manual (lat/lon)"
        return "no position"


@dataclass
class CarrierEstimate:
    freq_hz: float
    levels: dict                 # slot_id -> level dBm (recent sightings)
    device: str = "Analyzing…"
    confidence: int = 0
    candidates: list = field(default_factory=list)
    fix: Fix = None
    latlon: tuple = None
    first_seen: float = 0.0
    last_seen: float = 0.0

    @property
    def strongest(self):
        return max(self.levels.items(), key=lambda kv: kv[1]) if self.levels else (None, None)


class SensorNet:
    def __init__(self):
        self.sensors: dict[str, Sensor] = {}
        self.path_loss_exp = 3.0        # 2.0 free space, ~2.5 outdoors, 3-3.5 inside a venue
        self.margin_db = 12.0           # detection threshold above each sensor's floor
        self.level_sigma_db = 4.0
        self.estimates: dict[int, CarrierEstimate] = {}
        self.tdoa_fixes = {}             # carrier Hz -> (Fix, time found, session result)
        self._last_solve = 0.0
        self.origin = None              # (lat, lon) of the local frame when positions are geographic

    # --- sensors ---------------------------------------------------------
    def ensure_sensor(self, slot_id: str, name: str = "") -> Sensor:
        s = self.sensors.get(slot_id)
        if s is None:
            s = Sensor(slot_id, name or slot_id)
            self.sensors[slot_id] = s
        elif name:
            s.name = name
        return s

    def remove_sensor(self, slot_id: str):
        self.sensors.pop(slot_id, None)

    def set_gnss(self, slot_id: str, info: dict):
        self.ensure_sensor(slot_id).add_fix(info)

    def positions_xy(self):
        """{slot_id: (x, y)} in the local frame for every sensor with a position."""
        out = {}
        manual_xy = {sid: (s.x_m, s.y_m) for sid, s in self.sensors.items()
                     if s.position_source == "manual" and s.x_m is not None and s.y_m is not None}
        geo = {sid: s.latlon() for sid, s in self.sensors.items() if s.latlon() is not None
               and not (s.position_source == "manual" and sid in manual_xy)}
        if geo:
            if self.origin is None or self.origin[0] is None:
                lats = [v[0] for v in geo.values()]; lons = [v[1] for v in geo.values()]
                self.origin = (float(np.mean(lats)), float(np.mean(lons)))
            for sid, (lat, lon, alt) in geo.items():
                e, n, _ = enu_from_latlon(lat, lon, alt, self.origin[0], self.origin[1])
                out[sid] = (e, n)
        out.update(manual_xy)
        return out

    # --- sweeps ----------------------------------------------------------
    def update_sweep(self, slot_id: str, freq_hz, power_dbm, rbw_hz=None):
        s = self.sensors.get(slot_id)
        if s is None:
            return
        f = np.asarray(freq_hz, dtype=float)
        p = np.asarray(power_dbm, dtype=float)
        if len(f) < 10:
            return
        now = time.time()
        s.last_sweep = (f, p)
        # The running average (in linear power), started again when the sweep's range changes
        span = (len(f), float(f[0]), float(f[-1]))
        mw = np.power(10.0, np.clip(p, -200.0, 60.0) / 10.0)
        if s.avg_mw is None or s.avg_span != span:
            s.avg_mw, s.avg_n, s.avg_span = mw, 1, span
            s.sightings.clear()
        else:
            s.avg_n = min(s.avg_n + 1, AVG_SWEEPS)
            s.avg_mw = s.avg_mw + (mw - s.avg_mw) / s.avg_n
        raw = p
        p = 10.0 * np.log10(np.maximum(s.avg_mw, 1e-20))
        floor = float(np.median(p))
        s.floor_dbm = floor
        if s.avg_n < MIN_AVG_SWEEPS:
            return
        thresh = floor + self.margin_db
        peaks, _ = signal.find_peaks(p, height=thresh, prominence=MIN_PROMINENCE_DB, distance=3)
        seen = {}
        for i in peaks[np.argsort(-p[peaks])]:
            fk = self._key(f[i])
            if any(abs(fk - k) <= MATCH_HZ for k in seen):
                continue
            seen[fk] = float(p[i])
        for fk, lvl in seen.items():
            # fold into an existing sighting within the match tolerance
            key = next((k for k in s.sightings if abs(k - fk) <= MATCH_HZ), fk)
            s.sightings[key] = (lvl, floor, now)
        # carriers other sensors see: record this sensor's level there too (maybe below threshold)
        for key in list(self.estimates):
            if key not in s.sightings or now - s.sightings[key][2] > 1.0:
                sel = np.abs(f - key) <= MATCH_HZ
                if sel.any():
                    lvl = float(p[sel].max())
                    if lvl >= floor + 6:
                        s.sightings[key] = (lvl, floor, now)
        if now - s.last_measure >= MEASURE_PERIOD_S:
            s.last_measure = now
            recent = [k for k, (lvl, fl, t) in s.sightings.items() if now - t < STALE_S and lvl >= fl + 8]
            if recent:
                s.fingerprinter.update_sweep(f, raw, recent, rbw_hz)      # single sweeps: how it behaves in time
        for k in [k for k, v in s.sightings.items() if now - v[2] > STALE_S * 3]:
            del s.sightings[k]
            s.fingerprinter.forget(k)
        if now - self._last_solve >= SOLVE_PERIOD_S:
            self._last_solve = now
            self.solve()

    @staticmethod
    def _key(f_hz: float) -> float:
        return round(f_hz / 25e3) * 25e3

    # --- fusion ----------------------------------------------------------
    def solve(self):
        now = time.time()
        # union of carriers across sensors
        keys = []
        for s in self.sensors.values():
            for k, (lvl, fl, t) in s.sightings.items():
                if now - t < STALE_S and lvl >= fl + self.margin_db and not any(abs(k - kk) < MATCH_HZ for kk in keys):
                    keys.append(k)
        pos = self.positions_xy()
        new = {}
        for k in keys:
            est = next((e for kk, e in self.estimates.items() if abs(kk - k) < MATCH_HZ), None)
            levels, fps = {}, []
            for sid, s in self.sensors.items():
                sk = next((kk for kk in s.sightings if abs(kk - k) < MATCH_HZ), None)
                if sk is None:
                    continue
                lvl, fl, t = s.sightings[sk]
                if now - t < STALE_S:
                    levels[sid] = lvl - s.gain_db
                    r = s.fingerprinter.classify(sk)
                    fps.append((r, lvl - fl))
            if est is None:
                est = CarrierEstimate(k, levels, first_seen=now)
            est.freq_hz = k
            est.levels = levels
            est.last_seen = now
            v = vote_device(fps)
            if fps and max(snr for _r, snr in fps) < IDENTIFY_MIN_SNR_DB:
                est.device, est.confidence, est.candidates = "Too weak to identify", 0, []
            elif v:
                est.device, est.confidence, est.candidates = v
            # position from the sensors that both see it and know where they are
            usable = [(pos[sid], lvl) for sid, lvl in levels.items() if sid in pos]
            tdoa = next((v for kk, v in self.tdoa_fixes.items() if abs(kk - k) < MATCH_HZ), None)
            if tdoa is not None and now - tdoa[1] <= TDOA_FRESH_S:
                est.fix = tdoa[0]                 # a time-difference fix stands over the power-based one
            elif len(usable) >= 3:
                est.fix = rss_locate([u[0] for u in usable], [u[1] for u in usable],
                                     self.path_loss_exp, self.level_sigma_db)
            elif len(usable) == 2:
                est.fix = rss_centroid([u[0] for u in usable], [u[1] for u in usable])
            else:
                est.fix = None
            if est.fix is not None and self.origin and self.origin[0] is not None:
                est.latlon = latlon_from_enu(est.fix.x, est.fix.y, self.origin[0], self.origin[1])
            else:
                est.latlon = None
            new[k] = est
        # keep recently seen carriers (greyed by the UI) for a while
        for k, e in self.estimates.items():
            if k not in new and now - e.last_seen < STALE_S * 3 and not any(abs(k - kk) < MATCH_HZ for kk in new):
                new[k] = e
        self.estimates = new
        return self.estimates
