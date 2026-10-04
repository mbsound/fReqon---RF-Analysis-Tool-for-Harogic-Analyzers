"""
device_caps.py - What a connected analyzer can do.

Every hardware process may send a "capabilities" message describing its
analyzer; the UI greys out whatever is missing. An analyzer that sends none
(the Harogic SDK process) is treated as fully featured. Capabilities are a
plain dict so they cross the process boundary as-is.
"""

FULL_CAPABILITIES = {
    "family": "harogic",
    "name": "Harogic analyzer",
    # Operating modes: swept spectrum, real-time, zero-span, IQ stream (demodulation
    # and audio), discrete channel scanning
    "modes": ["SWP", "RTA", "DET", "IQS", "MSCAN"],
    "freq_min_hz": 1e3,
    "freq_max_hz": 20e9,
    "rbw_hz": None,             # None: any RBW; otherwise the bandwidths the analyzer has
    "vbw": True,
    "atten_db": (0, 30, 10),    # (min, max, step); None: no adjustable attenuator
    "auto_atten": True,
    "preamp": "harogic",        # "harogic": the SDK's gain options, "lna": on/off, None: none
    "ifagc": True,
    "if_out": True,
    "sweep_time": True,
    "sweep_points": True,       # shows the sweep's trace point count
    "spur_rejection": True,
    # Spur rejection choices, by the index sent to the analyzer; None: the SDK's
    # (Bypass / Standard / Enhanced). spur_default is the one used until changed.
    "spur_options": None,
    "spur_default": 1,
    "window": True,
    "detector": True,
    "calibration_files": True,  # needs RF/IF calibration files (Calibration Manager)
    # Selectable RF inputs (separate connectors), each {"id", "label", "min_hz", "max_hz"}
    # and optionally "atten": {"kind": "range", "db": (min, max, step)} or
    # {"kind": "switch", "label": ...} for an input whose attenuator is a single pad that is
    # in or out; None: a single input
    "inputs": None,
    # Zero span, where it differs from the Harogic time-domain mode: {"sample_interval_ns",
    # "max_points", "trigger_sources": [(label, id)], "note"}; None: the SDK's options
    "det": None,
}


def resolve(caps) -> dict:
    """A complete capabilities dict: `caps` over the fully featured defaults."""
    out = dict(FULL_CAPABILITIES)
    if caps:
        out.update(caps)
    return out


def supports_mode(caps, mode: str) -> bool:
    return mode.upper() in resolve(caps)["modes"]


def covers(caps, lo_hz: float, hi_hz: float) -> bool:
    """True if the analyzer can tune the whole of lo_hz..hi_hz."""
    c = resolve(caps)
    return c["freq_min_hz"] <= lo_hz and hi_hz <= c["freq_max_hz"]
