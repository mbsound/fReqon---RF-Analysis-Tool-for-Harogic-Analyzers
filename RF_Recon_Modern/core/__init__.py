"""
Core RF Engine & Database Modules

Package-level names are resolved lazily, so importing one core module (e.g. a
file parser) does not pull in the hardware layer and load the SDK library.
"""
import importlib

_EXPORTS = {
    "constants": (
        "TV_CHANNEL_STANDARDS", "DEFAULT_REGIONS", "DEFAULT_NORTH_AMERICA_ACTIVE",
        "DEFAULT_EUROPE_ACTIVE", "WATERFALL_COLORMAPS", "SWT_MODES",
        "SPUR_REJECTION_MODES", "WINDOW_FUNCTIONS", "DETECTOR_TYPES",
        "TRACE_DETECTOR_TYPES", "RBW_MODES", "VBW_MODES", "PREAMP_OPTIONS",
    ),
    "device_controller": ("DeviceController",),
    "calibration_manager": ("CalibrationManager",),
    "fcc_database": ("FCCDatabaseManager",),
    "ofcom_database": ("OfcomDatabaseManager",),
    "dect_analyzer": ("DECTAnalyzerEngine", "DECT_BANDS", "TDMATimeslotDialog"),
    "showlink_crmx_analyzer": ("ShowLinkCRMXEngine", "SHOWLINK_CHANNELS", "ShowlinkMapDialog"),
    "carrier_fingerprint": ("CarrierFingerprinter",),
}
_MODULE_OF = {name: module for module, names in _EXPORTS.items() for name in names}

__all__ = sorted(_MODULE_OF)


def __getattr__(name):
    module = _MODULE_OF.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f".{module}", __name__), name)
    globals()[name] = value  # cache for subsequent lookups
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
