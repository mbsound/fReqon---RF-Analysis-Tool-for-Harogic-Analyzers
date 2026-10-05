"""
spectrum_export.py - A spectrum trace as a CSV file in the layout SAStudio4 exports.

SAStudio4's spectrum export is four header lines and then one "frequency,amplitude" row
per trace point:

    Mode:,SWP
    Data:
    Trace Name:,T1,
    Frequency(Hz),Amplitude(dBm),
    168556.3,-88.4926757813
    2487892.2,-81.0962371826

Frequencies are in Hz and levels in dBm, both written with up to twelve significant digits
and no padding (7126564, not 7126564.0), lines end with a line feed, and there is one trace
per file. Files written here follow that exactly, so that whatever reads a SAStudio4 export
reads these.
"""

from datetime import datetime
from pathlib import Path

import numpy as np

# The traces fReqon can export, and the word each gets in its file name
TRACE_TAGS = {"Real-Time": "Live", "Max. Hold": "MaxHold", "Min. Hold": "MinHold", "Average": "Average"}


def file_name(trace: str, when: datetime = None) -> str:
    """fReqon_<date>_<time>_<trace>.csv, e.g. fReqon_20261005_155043_MaxHold.csv."""
    when = when or datetime.now()
    tag = TRACE_TAGS.get(trace) or "".join(ch for ch in trace if ch.isalnum()) or "Trace"
    return f"fReqon_{when:%Y%m%d_%H%M%S}_{tag}.csv"


def _number(x: float) -> str:
    return format(float(x), ".12g")


def csv_text(freq_hz, power_dbm, trace_name: str = "T1", mode: str = "SWP") -> str:
    """The file's contents for one trace."""
    f = np.asarray(freq_hz, dtype=float)
    p = np.asarray(power_dbm, dtype=float)
    if len(f) != len(p):
        raise ValueError(f"{len(f)} frequencies for {len(p)} levels")
    keep = np.isfinite(f) & np.isfinite(p)          # a point with no reading is left out, not written as nan
    lines = [f"Mode:,{mode}", "Data:", f"Trace Name:,{trace_name},", "Frequency(Hz),Amplitude(dBm),"]
    lines += [f"{_number(a)},{_number(b)}" for a, b in zip(f[keep], p[keep])]
    return "\n".join(lines) + "\n"


def write_csv(folder, trace: str, freq_hz, power_dbm, when: datetime = None) -> Path:
    """Write one trace into folder under its fReqon name; returns the file's path."""
    path = Path(folder) / file_name(trace, when)
    path.write_text(csv_text(freq_hz, power_dbm), encoding="ascii", newline="\n")
    return path


def read_csv(path):
    """(mode, trace name, frequencies Hz, levels dBm) from a file in this layout (ours or SAStudio4's)."""
    lines = Path(path).read_text(encoding="ascii").splitlines()
    mode = lines[0].split(",")[1] if lines and lines[0].startswith("Mode:") else ""
    name = next((ln.split(",")[1] for ln in lines[:4] if ln.startswith("Trace Name:")), "")
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Frequency(Hz)")) + 1
    rows = [ln.split(",") for ln in lines[start:] if ln.strip()]
    return mode, name, np.array([float(r[0]) for r in rows]), np.array([float(r[1]) for r in rows])
