"""
geolocate.py - Where is a transmitter, given what several sensors see?

Two estimators, both working in a local east/north/up frame in metres:

  rss_locate   from the level each sensor receives (works on sweep data, no
               synchronisation; coarse, limited by propagation and multipath)
  tdoa_locate  from the time differences of arrival of synchronised IQ
               captures (needs GNSS-disciplined timestamps on every sensor)

plus the conversions between latitude/longitude and the local frame, and a
vote that merges the fingerprinter's device guesses from every sensor.
"""

from dataclasses import dataclass, field
import math

import numpy as np
from scipy.optimize import least_squares

C = 299_792_458.0
EARTH_R = 6_371_008.8


# --- coordinates ----------------------------------------------------------

def enu_from_latlon(lat, lon, alt, ref_lat, ref_lon, ref_alt=0.0):
    """Local east/north/up (m) of a point relative to a reference (small-area approximation)."""
    lat0 = math.radians(ref_lat)
    e = math.radians(lon - ref_lon) * EARTH_R * math.cos(lat0)
    n = math.radians(lat - ref_lat) * EARTH_R
    return e, n, (alt or 0.0) - (ref_alt or 0.0)


def latlon_from_enu(e, n, ref_lat, ref_lon):
    lat0 = math.radians(ref_lat)
    return (ref_lat + math.degrees(n / EARTH_R),
            ref_lon + math.degrees(e / (EARTH_R * math.cos(lat0))))


# --- results ----------------------------------------------------------------

@dataclass
class Fix:
    x: float                    # east, m
    y: float                    # north, m
    cov: np.ndarray             # 2x2 covariance of (x, y), m^2
    method: str                 # "rss", "tdoa", "centroid"
    residual_db: float = 0.0    # rss: RMS level residual; tdoa: RMS range residual (m)
    n_sensors: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def radius_m(self) -> float:
        """1-sigma error radius (geometric mean of the ellipse semi-axes)."""
        ev = np.linalg.eigvalsh(self.cov)
        ev = np.clip(ev, 0, None)
        return float(math.sqrt(math.sqrt(ev[0] * ev[1]))) if ev[1] > 0 else float("inf")

    def ellipse(self, n_sigma=1.0, points=48):
        """Outline of the n-sigma uncertainty ellipse as (xs, ys)."""
        ev, vec = np.linalg.eigh(self.cov)
        ev = np.clip(ev, 0, None)
        t = np.linspace(0, 2 * np.pi, points)
        circle = np.vstack((np.cos(t), np.sin(t)))
        pts = vec @ (np.sqrt(ev)[:, None] * circle) * n_sigma
        return pts[0] + self.x, pts[1] + self.y


# --- received-signal-strength multilateration ---------------------------------

def rss_locate(sensors, levels_dbm, path_loss_exp=3.0, level_sigma_db=4.0, bounds_m=None):
    """
    sensors: [(x, y)] metres; levels_dbm: level at each sensor, already
    corrected to the antenna (input chain) and the same antenna gain.
    Model: L_i = P0 - 10 n log10(d_i), with P0 unknown. Needs 3+ sensors.
    Returns a Fix, or None if the geometry cannot be solved.
    """
    S = np.asarray(sensors, dtype=float)
    L = np.asarray(levels_dbm, dtype=float)
    k = len(S)
    if k < 3:
        return None
    # Start from the level-weighted centroid: the strongest sensor is probably closest
    w = 10 ** ((L - L.max()) / 10.0)
    x0 = (S * w[:, None]).sum(0) / w.sum()

    def model(p):
        d = np.hypot(S[:, 0] - p[0], S[:, 1] - p[1])
        d = np.maximum(d, 1.0)
        return p[2] - 10.0 * path_loss_exp * np.log10(d)

    def resid(p):
        return (model(p) - L) / level_sigma_db

    span = max(np.ptp(S[:, 0]), np.ptp(S[:, 1]), 50.0)
    lo = [S[:, 0].min() - span, S[:, 1].min() - span, -200.0]
    hi = [S[:, 0].max() + span, S[:, 1].max() + span, 80.0]
    if bounds_m:
        lo[0], lo[1], hi[0], hi[1] = bounds_m[0], bounds_m[1], bounds_m[2], bounds_m[3]
    best = None
    # Several starts: the RSS surface has local minima near individual sensors
    starts = [np.array([x0[0], x0[1], L.max() + 10.0 * path_loss_exp * 1.0])]
    for i in range(k):
        starts.append(np.array([S[i, 0] + 5.0, S[i, 1] + 5.0, L[i] + 10.0 * path_loss_exp * 0.7]))
    for s0 in starts:
        s0 = np.clip(s0, lo, hi)
        try:
            r = least_squares(resid, s0, bounds=(lo, hi), method="trf")
        except ValueError:
            continue
        if best is None or r.cost < best.cost:
            best = r
    if best is None:
        return None
    J = best.jac
    dof = max(k - 3, 1)
    s2 = max(2.0 * best.cost / dof, 1.0)          # cost = 0.5 * sum(r^2); never claim better than 1 sigma unit
    try:
        cov_full = np.linalg.inv(J.T @ J) * s2   # residuals are normalised, so this is m^2 / dBm^2
    except np.linalg.LinAlgError:
        cov_full = np.full((3, 3), np.inf)
    cov = cov_full[:2, :2]
    rms = math.sqrt(2.0 * best.cost / k) * level_sigma_db
    return Fix(float(best.x[0]), float(best.x[1]), cov, "rss", residual_db=rms, n_sensors=k,
               extra={"p0_dbm": float(best.x[2]), "path_loss_exp": path_loss_exp})


def rss_centroid(sensors, levels_dbm):
    """Two sensors (or a degenerate solve): the level-weighted point between them."""
    S = np.asarray(sensors, dtype=float)
    L = np.asarray(levels_dbm, dtype=float)
    if len(S) == 0:
        return None
    w = 10 ** ((L - L.max()) / 10.0)
    c = (S * w[:, None]).sum(0) / w.sum()
    spread = max(float(np.sqrt(((S - c) ** 2).sum(1).max())), 10.0)
    return Fix(float(c[0]), float(c[1]), np.eye(2) * spread ** 2, "centroid", n_sensors=len(S))


# --- time difference of arrival ------------------------------------------------

def tdoa_locate(sensors, tdoa_s, ref_index=0, sigma_s=50e-9, x0=None):
    """
    sensors: [(x, y)] m; tdoa_s[i] = t_i - t_ref (s), one per sensor (the
    reference's own entry is ignored). Needs 3+ sensors. Returns a Fix.
    """
    S = np.asarray(sensors, dtype=float)
    k = len(S)
    if k < 3:
        return None
    idx = [i for i in range(k) if i != ref_index]
    d_meas = np.array([tdoa_s[i] for i in idx]) * C          # range differences, m
    ref = S[ref_index]

    def resid(p):
        d_ref = np.hypot(ref[0] - p[0], ref[1] - p[1])
        d = np.hypot(S[idx, 0] - p[0], S[idx, 1] - p[1])
        return (d - d_ref - d_meas) / (sigma_s * C)

    start = np.asarray(x0, dtype=float) if x0 is not None else S.mean(0)
    best = None
    span = max(np.ptp(S[:, 0]), np.ptp(S[:, 1]), 50.0)
    for s0 in [start] + [S.mean(0) + np.array([dx, dy]) * span for dx in (-1, 1) for dy in (-1, 1)]:
        r = least_squares(resid, s0, method="lm") if k - 1 >= 2 else None
        if r is not None and (best is None or r.cost < best.cost):
            best = r
    if best is None:
        return None
    J = best.jac
    dof = max(k - 1 - 2, 1)
    s2 = max(2.0 * best.cost / dof, 1.0)
    try:
        cov = np.linalg.inv(J.T @ J) * s2        # residuals are normalised, so this is m^2
    except np.linalg.LinAlgError:
        cov = np.full((2, 2), np.inf)
    rms_m = math.sqrt(2.0 * best.cost / max(k - 1, 1)) * sigma_s * C
    return Fix(float(best.x[0]), float(best.x[1]), cov, "tdoa", residual_db=rms_m, n_sensors=k)


def tdoa_from_iq(iq_ref, iq_other, sample_rate, max_lag_s=20e-6):
    """
    Time of arrival of iq_other relative to iq_ref (s, positive = later) from
    the cross-correlation peak, interpolated between samples. Both captures
    must start at the same instant (PPS-triggered). Returns (tdoa_s, quality)
    where quality is the peak-to-sidelobe ratio in dB.
    """
    a = np.asarray(iq_ref, dtype=np.complex64)
    b = np.asarray(iq_other, dtype=np.complex64)
    n = min(len(a), len(b))
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    max_lag = int(max_lag_s * sample_rate) + 1
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    A = np.fft.fft(a, nfft)
    B = np.fft.fft(b, nfft)
    xc = np.fft.ifft(B * np.conj(A))
    xc = np.concatenate((xc[-max_lag:], xc[:max_lag + 1]))   # lags -max_lag .. +max_lag
    mag = np.abs(xc)
    i = int(np.argmax(mag))
    lag = i - max_lag
    # Parabolic interpolation around the peak
    if 0 < i < len(mag) - 1:
        y0, y1, y2 = mag[i - 1], mag[i], mag[i + 1]
        denom = y0 - 2 * y1 + y2
        frac = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
    else:
        frac = 0.0
    # Sidelobe level outside the main peak (its width follows the signal bandwidth)
    half = mag[i] / 2
    lo = i
    while lo > 0 and mag[lo - 1] > half:
        lo -= 1
    hi = i
    while hi < len(mag) - 1 and mag[hi + 1] > half:
        hi += 1
    w = max(hi - lo, 1)
    side = np.delete(mag, slice(max(0, i - 2 * w), i + 2 * w + 1))
    quality = 20 * math.log10(mag[i] / (side.max() + 1e-12)) if len(side) else 0.0
    return (lag + frac) / sample_rate, float(quality)


# --- device vote ---------------------------------------------------------------

def vote_device(results):
    """
    Merge fingerprint results from several sensors. results: [(result dict,
    snr_db)] where result is CarrierFingerprinter.classify() output. Sensors
    that see the carrier better count for more. Returns (device, confidence,
    [(candidate, score)]) or None.
    """
    scores, conf_w, w_total = {}, 0.0, 0.0
    best_single = None
    for r, snr in results:
        if not r or r.get("confidence", 0) <= 0:
            continue
        w = max(0.0, min(snr, 40.0)) / 40.0 + 0.1
        w_total += w
        conf_w += w * r["confidence"]
        cands = r.get("candidates") or [(r["device"], 100)]
        for name, pct in cands:
            scores[name] = scores.get(name, 0.0) + w * pct
        if best_single is None or r["confidence"] > best_single[0]:
            best_single = (r["confidence"], r)
    if not scores or w_total == 0:
        return None
    ranked = sorted(((k, v / w_total) for k, v in scores.items()), key=lambda kv: -kv[1])
    device = ranked[0][0]
    r = best_single[1]
    # Names the fingerprinter gave the top candidate at the best sensor (ties, groups)
    if r["device"].startswith(device) or device in r["device"]:
        device = r["device"]
    return device, round(conf_w / w_total), [(k, round(v)) for k, v in ranked[:4]]
