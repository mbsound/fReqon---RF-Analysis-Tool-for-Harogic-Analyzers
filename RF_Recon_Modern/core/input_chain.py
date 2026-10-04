"""
input_chain.py - What sits between the air and the analyzer's RF input.

A show antenna system is an antenna, coax, often an inline or antenna-mounted
amplifier, sometimes a filter or splitter. Each changes the level the analyzer
sees. An input chain lists those elements; its correction (dB added to every
reading) is the sum of their losses minus their gains, so levels read as they
would at the reference plane: the antenna's output terminals, or, with antenna
gain included, an isotropic (0 dBi) antenna - the same number a receiver
manufacturer's sensitivity figure refers to.

Elements are described one of three ways:
    flat    a fixed gain or loss in dB (amplifier, attenuator, splitter)
    cable   a loss quoted at one frequency, scaled with sqrt(f) like coax
    table   a measured frequency response: CSV (frequency, dB) or a Harogic
            *_ampcomp.txt file (#Freq_Hz / #Value_dB)

The correction is applied by the SDK (Devcie_SetFreqResponseCompensation), so
sweep, MSCAN and RTA levels all include it.
"""

from dataclasses import dataclass, field, asdict
import json
import math
import re
from pathlib import Path

import numpy as np

KINDS = ("antenna", "cable", "amplifier", "attenuator", "filter", "splitter", "other")
KIND_LABEL = {
    "antenna": "Antenna", "cable": "Cable", "amplifier": "Amplifier", "attenuator": "Attenuator",
    "filter": "Filter", "splitter": "Splitter / combiner", "other": "Other",
}
MODES = ("flat", "cable", "table")

# Frequencies the SDK table is sampled on: dense through the wireless bands,
# sparser above. Table elements' own points are added so measured detail is kept.
_GRID_HZ = np.unique(np.concatenate([
    np.arange(0, 30e6, 5e6),
    np.arange(30e6, 1.5e9, 2e6),
    np.arange(1.5e9, 3e9, 10e6),
    np.arange(3e9, 9.5e9, 50e6),
]))
MAX_SDK_POINTS = 20000


@dataclass
class Element:
    kind: str = "cable"
    label: str = ""
    mode: str = "flat"           # flat | cable | table
    gain_db: float = 0.0         # flat: + is gain, - is loss; cable: loss (positive number) at ref_mhz
    ref_mhz: float = 600.0       # cable: frequency the loss is quoted at
    table: list = field(default_factory=list)   # [(freq_hz, gain_db), ...] (+ is gain)
    source: str = ""             # table: file it was imported from
    enabled: bool = True

    def gain(self, f_hz: np.ndarray) -> np.ndarray:
        """Gain of this element in dB (negative for a loss) at each frequency."""
        f_hz = np.asarray(f_hz, dtype=float)
        if self.mode == "cable":
            ref = max(self.ref_mhz, 1e-3) * 1e6
            return -abs(self.gain_db) * np.sqrt(np.maximum(f_hz, 0.0) / ref)
        if self.mode == "table" and self.table:
            t = sorted(self.table)
            fx = np.array([p[0] for p in t], dtype=float)
            gx = np.array([p[1] for p in t], dtype=float)
            return np.interp(f_hz, fx, gx)    # held flat beyond the measured range
        if self.mode == "table":
            return np.zeros_like(f_hz)
        return np.full_like(f_hz, float(self.gain_db))

    def describe(self) -> str:
        name = self.label or KIND_LABEL.get(self.kind, self.kind)
        if self.mode == "cable":
            return f"{name}: {abs(self.gain_db):.1f} dB loss at {self.ref_mhz:g} MHz"
        if self.mode == "table":
            src = Path(self.source).name if self.source else "measured"
            return f"{name}: {len(self.table)}-point table ({src})"
        return f"{name}: {self.gain_db:+.1f} dB"


@dataclass
class InputChain:
    name: str = "New input chain"
    elements: list = field(default_factory=list)
    include_antenna: bool = False   # refer levels to a 0 dBi antenna (removes antenna gain too)
    notes: str = ""

    def active(self):
        return [e for e in self.elements
                if e.enabled and (self.include_antenna or e.kind != "antenna")]

    def gain(self, f_hz) -> np.ndarray:
        """Net gain from the reference plane to the analyzer input (dB)."""
        f_hz = np.asarray(f_hz, dtype=float)
        total = np.zeros_like(f_hz)
        for e in self.active():
            total = total + e.gain(f_hz)
        return total

    def correction(self, f_hz) -> np.ndarray:
        """dB added to analyzer readings: undoes the chain's net gain."""
        return -self.gain(f_hz)

    def sdk_table(self):
        """(frequencies Hz, correction dB) for the SDK, or ([], []) for no correction."""
        act = self.active()
        if not act:
            return [], []
        extra = [p[0] for e in act if e.mode == "table" for p in e.table]
        f = np.unique(np.concatenate([_GRID_HZ, np.asarray(extra, dtype=float)])) if extra else _GRID_HZ
        if len(f) > MAX_SDK_POINTS:
            f = f[np.linspace(0, len(f) - 1, MAX_SDK_POINTS).astype(int)]
        c = self.correction(f)
        if np.all(np.abs(c) < 1e-3):
            return [], []
        return [float(x) for x in f], [float(round(x, 3)) for x in c]

    def summary(self, f_mhz=(470.0, 550.0, 608.0)) -> str:
        c = self.correction(np.asarray(f_mhz) * 1e6)
        return ", ".join(f"{v:+.1f} dB @ {f:g} MHz" for f, v in zip(f_mhz, c))

    # --- persistence ---
    def to_dict(self) -> dict:
        d = asdict(self)
        for e in d["elements"]:
            e["table"] = [list(p) for p in e["table"]]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "InputChain":
        els = []
        for e in d.get("elements", []):
            known = {k: e[k] for k in Element.__dataclass_fields__ if k in e}
            known["table"] = [tuple(p) for p in known.get("table", [])]
            els.append(Element(**known))
        return cls(name=d.get("name", "Input chain"), elements=els,
                   include_antenna=bool(d.get("include_antenna", False)), notes=d.get("notes", ""))


class InputChainStore:
    """Named chains plus which one each analyzer slot uses, kept in QSettings as JSON."""

    KEY = "input_chains"

    def __init__(self, settings=None):
        self.settings = settings
        self.chains: dict = {}
        self.assignment: dict = {}     # slot_id -> chain name
        self.load()

    def load(self):
        raw = self.settings.value(self.KEY, "") if self.settings is not None else ""
        try:
            d = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            d = {}
        self.chains = {}
        for c in d.get("chains", []):
            try:
                ch = InputChain.from_dict(c)
                self.chains[ch.name] = ch
            except (TypeError, ValueError):
                continue
        self.assignment = {k: v for k, v in d.get("assignment", {}).items() if v in self.chains}

    def save(self):
        if self.settings is None:
            return
        self.settings.setValue(self.KEY, json.dumps({
            "chains": [c.to_dict() for c in self.chains.values()],
            "assignment": self.assignment,
        }))

    def for_slot(self, slot_id: str):
        name = self.assignment.get(slot_id)
        return self.chains.get(name) if name else None


# --- table import ---

def load_response_file(path) -> list:
    """
    Read a frequency response: a Harogic *_ampcomp.txt file or a CSV/TXT of
    frequency and dB pairs (header lines are skipped; frequencies under 100 000
    are taken as MHz). Returns [(freq_hz, db), ...] sorted by frequency.
    Values are returned as found: the caller decides whether they are gain or loss.
    """
    path = Path(path)
    text = path.read_text(errors="replace")
    if "#Freq_Hz" in text and "#Value_dB" in text:
        lines = [ln.strip() for ln in text.splitlines()]
        f = [float(x) for x in lines[lines.index("#Freq_Hz") + 1].split()]
        v = [float(x) for x in lines[lines.index("#Value_dB") + 1].split()]
        if len(f) != len(v) or not f:
            raise ValueError("Freq_Hz and Value_dB lists differ in length")
        pts = list(zip(f, v))
    else:
        pts = []
        for line in text.splitlines():
            nums = []
            for cell in re.split(r"[,;\t ]+", line.strip()):
                try:
                    nums.append(float(cell))
                except ValueError:
                    pass
            if len(nums) >= 2 and math.isfinite(nums[0]) and math.isfinite(nums[1]):
                pts.append((nums[0], nums[1]))
        if not pts:
            raise ValueError("No frequency/dB pairs found")
        if max(p[0] for p in pts) < 1e5:
            pts = [(f * 1e6, v) for f, v in pts]
    pts.sort()
    return pts
