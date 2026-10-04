"""
intermod.py - Intermodulation products of a set of transmitters.

Transmitters that share a space (the same Soundbase/WWB zone, the same IEM
combiner, a performer wearing two packs) mix in each other's output stages and
in receivers' front ends, creating products at predictable frequencies:

    2-tone 3rd order (IM3)   2*f1 - f2              strongest, most common
    2-tone 5th order (IM5)   3*f1 - 2*f2
    3-tone 3rd order         f1 + f2 - f3           many combinations, weaker
    2-tone 7th order (IM7)   4*f1 - 3*f2            optional

Coordination software avoids landing carriers on these; this module answers the
live questions: "is this unexpected carrier an intermod product of ours?" and
"which products are landing on our coordinated or spare frequencies right now?"
"""

from dataclasses import dataclass
import itertools

import numpy as np

ORDER_LABEL = {3: "IM3", 5: "IM5", 7: "IM7", 33: "3-tone IM3"}
# Rough relative strength used for ranking (higher = more likely to matter)
ORDER_WEIGHT = {3: 1.0, 33: 0.5, 5: 0.35, 7: 0.12}


@dataclass(frozen=True)
class Transmitter:
    freq_hz: float
    name: str = ""
    zone: str = ""          # transmitters only mix with others in the same zone
    bandwidth_hz: float = 200e3


@dataclass(frozen=True)
class Product:
    freq_hz: float
    order: int              # 3, 5, 7 or 33 (3-tone 3rd order)
    sources: tuple          # contributing Transmitter objects
    width_hz: float         # width of the product's core (energy concentrates within the
                            # widest contributor's bandwidth; the skirts spread further)

    @property
    def label(self) -> str:
        return ORDER_LABEL[self.order]

    def describe(self) -> str:
        # Names from coordination files are often model names, so always add the frequency
        n = [f"{s.name} ({s.freq_hz / 1e6:.3f})" if s.name and f"{s.freq_hz / 1e6:.3f}" not in s.name
             else (s.name or f"{s.freq_hz / 1e6:.3f}") for s in self.sources]
        if self.order == 3:
            return f"IM3 2×{n[0]} − {n[1]}"
        if self.order == 5:
            return f"IM5 3×{n[0]} − 2×{n[1]}"
        if self.order == 7:
            return f"IM7 4×{n[0]} − 3×{n[1]}"
        return f"3-tone {n[0]} + {n[1]} − {n[2]}"


# --- How strong a product is likely to be ------------------------------------
#
# Intermod made in transmitters standing close together (packs on a performer,
# an IEM rack) is a roughly fixed number of dB below the carriers as both reach
# the antenna from the same place, so the estimate is "the carriers' level,
# less a margin": IM3_DBC below for a 2-tone 3rd order product, about 15 dB more
# for 5th order, and 6 dB less for a 3-tone product (three equal contributors
# make a product 6 dB stronger than two). The contributing levels are weighted
# as in the product's formula: 2*f1 - f2 is driven twice as hard by f1.
# IM3_DBC itself depends on how close the transmitters are (20-25 dB for packs
# touching, 35-40 dB a metre apart), so it is a setting.
IM5_EXTRA_DB = 15.0
THREE_TONE_GAIN_DB = 6.0


def estimate_level(product, level_of, im3_dbc=30.0):
    """
    Estimated level in dBm of `product`, from level_of(transmitter) -> dBm (or
    None when the transmitter's level is not known: the estimate is then None).
    """
    levels = [level_of(t) for t in product.sources]
    if any(l is None for l in levels):
        return None
    if product.order == 33:
        return sum(levels) / 3.0 - im3_dbc + THREE_TONE_GAIN_DB
    a, b = {3: (2, 1), 5: (3, 2), 7: (4, 3)}[product.order]
    weighted = (a * levels[0] + b * levels[1]) / (a + b)
    return weighted - im3_dbc - ({5: IM5_EXTRA_DB, 7: 2 * IM5_EXTRA_DB}.get(product.order, 0.0))


def products(transmitters, orders=(3, 5, 33), max_three_tone=120, lo_hz=None, hi_hz=None):
    """
    All intermod products among transmitters, computed per zone. Products of a
    carrier with itself are excluded. 3-tone products are skipped for zones
    with more than max_three_tone transmitters (the count grows as N^3).
    """
    by_zone = {}
    for t in transmitters:
        by_zone.setdefault(t.zone, []).append(t)
    out = []
    for zone_txs in by_zone.values():
        txs = sorted(zone_txs, key=lambda t: t.freq_hz)
        n = len(txs)
        if n < 2:
            continue
        f = np.array([t.freq_hz for t in txs])
        bw = np.array([t.bandwidth_hz for t in txs])
        i, j = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        mask = i != j
        i, j = i[mask], j[mask]
        for order, (a, b) in ((3, (2, 1)), (5, (3, 2)), (7, (4, 3))):
            if order not in orders:
                continue
            pf = a * f[i] - b * f[j]
            pw = np.maximum(bw[i], bw[j])
            for k in np.nonzero(_in_range(pf, lo_hz, hi_hz))[0]:
                out.append(Product(float(pf[k]), order, (txs[i[k]], txs[j[k]]), float(pw[k])))
        if 33 in orders and n >= 3 and n <= max_three_tone:
            for x, y in itertools.combinations(range(n), 2):
                pf = f[x] + f[y] - f
                keep = _in_range(pf, lo_hz, hi_hz)
                keep[[x, y]] = False
                for z in np.nonzero(keep)[0]:
                    out.append(Product(float(pf[z]), 33, (txs[x], txs[y], txs[z]),
                                       float(max(bw[x], bw[y], bw[z]))))
    return out


def _in_range(pf, lo_hz, hi_hz):
    keep = np.ones(len(pf), dtype=bool)
    if lo_hz is not None:
        keep &= pf >= lo_hz
    if hi_hz is not None:
        keep &= pf <= hi_hz
    return keep


class IntermodMap:
    """Products indexed by frequency for fast "what lands here?" queries."""

    def __init__(self, transmitters, orders=(3, 5, 33), lo_hz=None, hi_hz=None):
        self.transmitters = list(transmitters)
        self.products = products(self.transmitters, orders, lo_hz=lo_hz, hi_hz=hi_hz)
        self.products.sort(key=lambda p: p.freq_hz)
        self._freqs = np.array([p.freq_hz for p in self.products])

    def near(self, freq_hz, bandwidth_hz=200e3, guard_hz=0.0, limit=None):
        """
        Products whose core overlaps a signal of the given bandwidth at freq_hz
        (half the product width + half the signal width + guard), most likely
        first: lower order, then closer.
        """
        if not self.products:
            return []
        reach = bandwidth_hz / 2 + guard_hz + 4e6   # covers the widest contributor (WMAS blocks)
        lo = np.searchsorted(self._freqs, freq_hz - reach)
        hi = np.searchsorted(self._freqs, freq_hz + reach)
        hits = []
        for p in self.products[lo:hi]:
            if any(abs(s.freq_hz - freq_hz) < 1e3 for s in p.sources):
                continue  # a carrier is not a product of itself
            if abs(p.freq_hz - freq_hz) <= p.width_hz / 2 + bandwidth_hz / 2 + guard_hz:
                hits.append(p)
        hits.sort(key=lambda p: (-ORDER_WEIGHT[p.order], abs(p.freq_hz - freq_hz)))
        return hits[:limit] if limit else hits

    def hits_on(self, targets, guard_hz=0.0):
        """For each target Transmitter, the products landing on it."""
        return {t: self.near(t.freq_hz, t.bandwidth_hz, guard_hz) for t in targets}


def analyzer_or_real(level_before_dbm, level_after_dbm, atten_step_db):
    """
    The attenuation test: raise the analyzer's input attenuation by
    atten_step_db. A signal that is really on the air drops by atten_step_db; an
    intermod product made inside the analyzer drops by about 3x (3rd order).
    Returns ("real" | "analyzer" | "unclear", observed drop in dB).
    """
    drop = level_before_dbm - level_after_dbm
    if abs(drop - atten_step_db) <= 0.35 * atten_step_db:
        return "real", drop
    if drop >= 2.2 * atten_step_db:
        return "analyzer", drop
    return "unclear", drop
