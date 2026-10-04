"""
tinysa_device.py - tinySA and tinySA Ultra support.

A tinySA is a USB serial (CDC) device with a text shell: commands end in CR, the
device echoes them, prints its reply and then the prompt "ch> ". Sweeps use

    scanraw {start Hz} {stop Hz} {points}

which measures `points` frequencies from start in steps of (stop - start) / points
(stop itself is not measured) and replies '{' + points * ('x' + uint16 LE) + '}'.
A level is value / 32 - zero dBm, where zero is the device's `zero` setting
(128 on the tinySA, 174 on the Ultra).

tinysa_process() is the counterpart of device_controller.hardware_process(): it
takes the same commands and sends the same messages, so the rest of fReqon
treats a tinySA like any analyzer. What it cannot do is declared in its
capabilities (see device_caps.py) and greyed out by the UI.

This module does not need the Harogic SDK. Serial I/O uses termios, so it is
POSIX only (macOS, Linux), as is the rest of fReqon.
"""

import math
import multiprocessing
import os
import queue
import re
import select
import sys
import time
import zlib

import numpy as np

try:
    import fcntl
    import termios
except ImportError:          # Windows
    fcntl = termios = None

try:
    from .device_caps import FULL_CAPABILITIES
except ImportError:
    from device_caps import FULL_CAPABILITIES

PROMPT = b"ch> "
# STMicroelectronics virtual COM port. NanoVNAs use the same IDs, so a port is
# only a tinySA once it has answered `version`.
USB_IDS = ((0x0483, 0x5740),)
# Explicit port(s) to use instead of USB enumeration (os.pathsep separated)
ENV_PORTS = "FREQON_TINYSA_PORT"

LOW_BAND_MAX_HZ = 350e6       # tinySA (basic) low input: 100 kHz - 350 MHz
HIGH_BAND_MIN_HZ = 240e6      # tinySA (basic) high input: 240 - 960 MHz

AUTO_MAX_POINTS = 1500        # automatic RBW: the finest that sweeps the span in this many points
MIN_POINTS = 101
MAX_POINTS = 4000
# A scan can't be interrupted, so sweeps are scanned in pieces this long. (On
# firmware v1.3 every scan was measured to take a multiple of 0.1 s, so shorter
# pieces waste time.)
CHUNK_TARGET_S = 0.5
SCAN_OVERHEAD_S = 0.1         # allowance for that fixed cost when estimating the scan rate
FIRST_CHUNK_POINTS = 32       # until the scan rate is known
MSCAN_POINTS = 32             # spectrum points per monitored channel
# Zero span: a scan with start = stop samples one frequency over time. Measured on a
# tinySA (firmware v1.3): 58 us a sample at every RBW, up to 16000 samples a scan, plus
# 0.2-0.3 s fixed per scan. The interval is measured on each analyzer when first used.
ZERO_SPAN_DEFAULT_S = 58e-6
ZERO_SPAN_SCAN_POINTS = 16000
# The first samples of a scan are not usable: on the high input a few around the 30th
# read as no signal at all while the receiver settles. They are captured and dropped.
ZERO_SPAN_LEAD = 64
ZERO_SPAN_MAX_POINTS = ZERO_SPAN_SCAN_POINTS - ZERO_SPAN_LEAD
ZERO_SPAN_LENGTHS = (512, 1024, 2048, 4096, 8192, ZERO_SPAN_MAX_POINTS)
TRIG_FREE, TRIG_LEVEL = 2, 3  # as the Harogic trigger source ids: bus (free run), level
# Armed: the tinySA's own triggered zero-span sweep. It waits for the level for as long
# as it takes and puts the crossing mid-trace, but a trace is only 290 points, and
# asking the device whether it has fired interrupts the wait for about 0.1 s.
TRIG_ARMED = 4
ARMED_MIN_SWEEP_S = 0.017     # 290 points at the receiver's fastest rate
ARMED_POLL_EXTRA_S = 0.4      # between checks for a capture, on top of the window
# Channel monitor span for the Harogic decimation factors (397 kHz at 256)
MSCAN_SPAN_NUMERATOR_HZ = 101.5625e6


class TinySAError(Exception):
    """The device did something unexpected; the connection may still be usable."""


class TinySATimeout(TinySAError):
    pass


class TinySALinkLost(TinySAError):
    """The serial port is gone (unplugged)."""


class TinySABusy(TinySAError):
    """The serial port is open elsewhere."""


class TinySAOpenError(TinySAError):
    """The serial port exists but cannot be opened (e.g. no permission)."""


class SerialLink:
    """Raw, non-blocking access to a serial port with a receive buffer."""

    def __init__(self, path: str):
        if termios is None:
            raise TinySAError("tinySA support needs a POSIX serial port (macOS or Linux).")
        self.path = path
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        except OSError as e:
            if e.errno == 16:   # EBUSY: opened exclusively by another process
                raise TinySABusy(f"{path} is in use.") from e
            raise TinySAOpenError(f"Cannot open {path}: {e.strerror}") from e
        try:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as e:
                raise TinySABusy(f"{path} is in use.") from e
            attrs = termios.tcgetattr(self.fd)
            attrs[0] = 0                                                 # input: raw
            attrs[1] = 0                                                 # output: raw
            attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL      # 8N1, no modem control
            attrs[3] = 0                                                 # no echo, no line editing
            attrs[6][termios.VMIN] = 0
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
            fcntl.ioctl(self.fd, termios.TIOCEXCL)
        except TinySAError:
            os.close(self.fd)
            raise
        except (OSError, termios.error) as e:
            os.close(self.fd)
            raise TinySAError(f"Cannot configure {path}: {e}") from e
        self._buf = bytearray()

    def close(self):
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, termios.TIOCNXCL)
            except OSError:
                pass
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def write(self, data: bytes):
        view = memoryview(data)
        deadline = time.monotonic() + 3.0
        while view:
            try:
                view = view[os.write(self.fd, view):]
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise TinySATimeout(f"{self.path} does not accept data.")
                select.select([], [self.fd], [], 0.2)
            except OSError as e:
                raise TinySALinkLost(f"{self.path}: {e.strerror}") from e

    def _fill(self, timeout: float) -> bool:
        """Wait up to `timeout` for more data; False if none came."""
        try:
            ready, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
            if not ready:
                return False
            data = os.read(self.fd, 65536)
        except BlockingIOError:
            return False
        except (OSError, ValueError) as e:
            raise TinySALinkLost(f"{self.path}: {getattr(e, 'strerror', None) or e}") from e
        if not data:
            raise TinySALinkLost(f"{self.path} closed.")
        self._buf += data
        return True

    def read_until_any(self, tokens, timeout: float):
        """Receive up to and including the first of `tokens`: (data, token)."""
        deadline = time.monotonic() + timeout
        while True:
            hits = [(i, t) for t in tokens for i in [self._buf.find(t)] if i >= 0]
            if hits:
                i, t = min(hits)
                out = bytes(self._buf[:i + len(t)])
                del self._buf[:i + len(t)]
                return out, t
            left = deadline - time.monotonic()
            if left <= 0 or not self._fill(left):
                if time.monotonic() >= deadline:
                    raise TinySATimeout(f"No reply from {self.path}.")

    def read_until(self, token: bytes, timeout: float) -> bytes:
        return self.read_until_any((token,), timeout)[0]

    def read_exact(self, n: int, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        while len(self._buf) < n:
            left = deadline - time.monotonic()
            if left <= 0 or not self._fill(left):
                if time.monotonic() >= deadline:
                    raise TinySATimeout(f"{self.path} stopped sending ({len(self._buf)} of {n} bytes).")
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    def drain(self, quiet_s: float = 0.15, max_s: float = 2.0) -> bool:
        """Discard input until the line has been quiet for quiet_s; False if it never was."""
        deadline = time.monotonic() + max_s
        while time.monotonic() < deadline:
            if not self._fill(quiet_s):
                self._buf.clear()
                return True
        self._buf.clear()
        return False


class TinySA:
    """One tinySA or tinySA Ultra on a serial port."""

    def __init__(self, port: str, usb_serial: str = ""):
        self.port = port
        self.link = SerialLink(port)
        self._sent = {}          # last command sent per setting (commands are sent only on change)
        self._band = None
        try:
            self._identify()
        except Exception:
            self.link.close()
            raise
        self.uid = (0x7453 << 32) | zlib.crc32(f"{usb_serial}|{port}".encode())

    # -- shell ---------------------------------------------------------------

    def sync(self):
        """Get to a clean prompt, stopping anything the device was left doing."""
        for line in (b"\r", b"abort\r"):
            self.link.drain(quiet_s=0.05, max_s=1.0)
            self.link.write(line)
            try:
                self.link.read_until(PROMPT, 2.0)
            except TinySATimeout:
                continue
            if self.link.drain(quiet_s=0.1, max_s=2.0):
                return
        raise TinySAError(f"No tinySA shell on {self.port}.")

    def command(self, text: str, timeout: float = 3.0) -> str:
        """Run a shell command and return its reply (without echo and prompt)."""
        self.link.write(text.encode("ascii") + b"\r")
        raw = self.link.read_until(PROMPT, timeout)[:-len(PROMPT)]
        lines = raw.decode("ascii", "replace").replace("\r", "").split("\n")
        if lines and lines[0].strip() == text.strip():
            lines = lines[1:]
        return "\n".join(lines).strip()

    def _identify(self):
        self.sync()
        version = self.command("version")
        if "tinysa" not in version.lower():
            raise TinySAError(f"The device on {self.port} is not a tinySA "
                              f"(it answered {version[:40]!r} to 'version').")
        self.firmware = version.splitlines()[0].strip()
        hw = re.search(r"HW Version:\s*(\S+)", version)
        self.hw_version = hw.group(1) if hw else ""
        self.is_ultra = self.firmware.lower().startswith("tinysa4")
        # RF inputs (separate connectors) and what each can tune; {} for a single input
        self.inputs = {}
        if not self.is_ultra:
            self.name = "tinySA"
            self.freq_min_hz, self.freq_max_hz = 100e3, 960e6
            self.normal_max_hz = None
            self.rbw_list = [3e3, 10e3, 30e3, 100e3, 300e3, 600e3]
            self.inputs = {"low": (self.freq_min_hz, LOW_BAND_MAX_HZ), "high": (HIGH_BAND_MIN_HZ, self.freq_max_hz)}
            # Spur removal (low input only; it roughly halves the sweep speed): (label, `spur` argument)
            self.spur_choices, self.spur_default = (("Off", "off"), ("On", "on")), 0
        else:
            # Above normal_max_hz the Ultra needs its "ultra" mode; freq_max_hz is
            # where fundamental mixing ends (harmonic mode beyond it is not used).
            if self.hw_version.startswith("V0.5"):
                self.name, self.freq_max_hz, self.normal_max_hz = "tinySA Ultra+ (ZS407)", 7.3e9, 900e6
            elif self.hw_version.startswith("V0.4.6"):
                self.name, self.freq_max_hz, self.normal_max_hz = "tinySA Ultra+ (ZS406)", 5.4e9, 900e6
            else:
                self.name, self.freq_max_hz, self.normal_max_hz = "tinySA Ultra", 5.3e9, 800e6
            self.freq_min_hz = 100e3
            self.rbw_list = [200.0, 1e3, 3e3, 10e3, 30e3, 100e3, 300e3, 600e3, 850e3]
            self.spur_choices, self.spur_default = (("Off", "off"), ("Auto", "auto"), ("On", "on")), 1
        zero = re.search(r"(-?\d+)\s*dBm", self.command("zero"))
        self.zero_level = float(zero.group(1)) if zero else (174.0 if self.is_ultra else 128.0)

    def close(self, resume: bool = True):
        if self.link.fd is None:
            return
        if resume:
            try:
                self.command("resume", timeout=1.0)   # hand the screen back to the device's own sweep
            except TinySAError:
                pass
        self.link.close()

    # -- description -----------------------------------------------------------

    def capabilities(self) -> dict:
        caps = dict(FULL_CAPABILITIES)
        caps.update({
            "family": "tinysa",
            "name": self.name,
            "modes": ["SWP", "MSCAN", "DET"],   # MSCAN: channels stepped one at a time; DET: zero span
            "freq_min_hz": self.freq_min_hz,
            "freq_max_hz": self.freq_max_hz,
            "rbw_hz": list(self.rbw_list),
            "vbw": False,
            "atten_db": (0, 31, 1),
            "auto_atten": True,
            "preamp": "lna" if self.is_ultra else None,
            "ifagc": False,
            "if_out": False,
            "sweep_time": False,
            "sweep_points": False,
            "spur_rejection": True,
            "spur_options": [label for label, _arg in self.spur_choices],
            "spur_default": self.spur_default,
            "window": False,
            "detector": False,
            "calibration_files": False,
            # The low input has the 0-31 dB step attenuator; the high input only a pad
            # (25-40 dB depending on frequency) that is in or out: any attenuation above
            # 0 dB switches it in, and automatic leaves it out.
            "inputs": [{"id": name, "label": name.capitalize(), "min_hz": lo, "max_hz": hi,
                        "atten": ({"kind": "switch", "label": "25–40 dB pad"} if name == "high"
                                  else {"kind": "range", "db": (0, 31, 1)})}
                       for name, (lo, hi) in self.inputs.items()] or None,
            "det": {
                "sample_interval_ns": ZERO_SPAN_DEFAULT_S * 1e9,
                "max_points": ZERO_SPAN_MAX_POINTS,
                "lengths": list(ZERO_SPAN_LENGTHS),
                "trigger_sources": [("Free run", TRIG_FREE), ("Level, in each capture", TRIG_LEVEL),
                                    ("Level, armed (290 points)", TRIG_ARMED)],
                "trigger_level": True,
                "note": "One frequency sampled over time at the RBW set in RF & Sweep (Auto: the widest). "
                        "Armed waits for the level and puts the crossing mid-window; the window is "
                        "then 290 points whatever its length.",
            },
        })
        return caps

    def describe(self) -> dict:
        """Device details for the top bar's hardware menu."""
        return {
            "title": self.name.upper(),
            "model": self.name,
            "hw_ver": self.hw_version or "-",
            "uid": f"{self.uid:016x}",
            "full_uid": f"{self.uid:016x}",
            "firmware": self.firmware,
            "port": self.port,
            "interface": f"USB serial ({self.port})",
            "licenses": None,
            "hardware_features": [
                f"{self.freq_min_hz / 1e3:g} kHz - {self.freq_max_hz / 1e6:g} MHz",
                "RBW " + ", ".join(f"{r / 1e3:g}" for r in self.rbw_list) + " kHz",
            ] + (["Switchable LNA"] if self.is_ultra else ["Low (to 350 MHz) and high (240-960 MHz) inputs"]),
        }

    # -- measurement -----------------------------------------------------------

    def input_range(self, rf_input: str = "auto"):
        """(lowest, highest) frequency reachable with `rf_input` selected ("auto": any input)."""
        return self.inputs.get(rf_input, (self.freq_min_hz, self.freq_max_hz))

    def band_for(self, lo_hz: float, hi_hz: float, rf_input: str = "auto"):
        """
        The input a tinySA (basic) uses for lo..hi: the selected one, or with
        "auto" the one that covers it ("split": low below 350 MHz, high above).
        None on the Ultra (one input).
        """
        if not self.inputs:
            return None
        if rf_input in self.inputs:
            return rf_input
        if hi_hz <= LOW_BAND_MAX_HZ:
            return "low"            # the better input (filtered, with the attenuator) where it reaches
        return "high" if lo_hz >= HIGH_BAND_MIN_HZ else "split"

    def segments(self, freq: np.ndarray, rf_input: str = "auto"):
        """A sweep as (band, first index, end index) runs, one per input used."""
        band = self.band_for(freq[0], freq[-1], rf_input)
        if band != "split":
            return [(band, 0, len(freq))]
        cut = int(np.searchsorted(freq, LOW_BAND_MAX_HZ))
        return [("low", 0, cut), ("high", cut, len(freq))]

    def _set(self, key: str, command: str):
        if self._sent.get(key) != command:
            self.command(command)
            self._sent[key] = command

    def apply(self, band, rbw_hz: float, atten: int, lna: bool, spur: int, top_hz: float):
        """Program the receiver; only settings that changed are sent."""
        band = band or "low"
        if band != self._band:
            self.command(f"mode {band} input")
            self._band = band
            self._sent.clear()              # changing the mode resets the device's settings
        if self.normal_max_hz and top_hz > self.normal_max_hz:
            self._set("ultra", "ultra on")
        self._set("rbw", f"rbw {rbw_hz / 1e3:g}")
        if self.is_ultra:
            self._set("lna", "lna on" if lna else "lna off")
        self._set("attenuate", "attenuate auto" if atten < 0 else f"attenuate {min(31, int(atten))}")
        # spur: index into spur_choices (the options this analyzer gives the UI)
        spur_arg = self.spur_choices[min(len(self.spur_choices) - 1, max(0, int(spur)))][1]
        self._set("spur", f"spur {spur_arg}")

    def own_sweep(self):
        """The device's own sweep range, (start Hz, stop Hz), or None if it does not say."""
        m = re.match(r"\s*(\d+)\s+(\d+)", self.command("sweep"))
        return (int(m.group(1)), int(m.group(2))) if m else None

    def read_trace(self) -> np.ndarray:
        """The device's own measured trace, in dBm."""
        try:
            return np.array([float(v) for v in self.command("data 2", 5.0).split()], dtype=np.float32)
        except ValueError:
            raise TinySAError("the trace could not be read.")

    def scan_raw(self, start_hz: int, step_hz: int, points: int, timeout: float) -> np.ndarray:
        """Levels in dBm at start_hz + i * step_hz, i = 0..points-1."""
        stop_hz = int(start_hz) + int(step_hz) * int(points)
        self.link.write(f"scanraw {int(start_hz)} {stop_hz} {int(points)}\r".encode("ascii"))
        head, token = self.link.read_until_any((b"{", PROMPT), timeout)
        if token != b"{":
            reply = head[:-len(PROMPT)].decode("ascii", "replace").strip().splitlines()
            raise TinySAError(f"scanraw refused: {reply[-1] if reply else 'no data'}")
        raw = self.link.read_exact(3 * points + 1, timeout)
        self.link.read_until(PROMPT, 3.0)
        rec = np.frombuffer(raw, dtype=np.uint8, count=3 * points).reshape(points, 3)
        if raw[-1:] != b"}" or not np.all(rec[:, 0] == ord("x")):
            raise TinySAError("scanraw data is out of step.")
        value = rec[:, 1].astype(np.uint16) | (rec[:, 2].astype(np.uint16) << 8)
        return value.astype(np.float32) / 32.0 - self.zero_level


def list_tinysa_ports() -> list:
    """Serial ports that may be a tinySA: [{"port", "serial"}], in a stable order."""
    explicit = os.environ.get(ENV_PORTS)
    if explicit:
        return [{"port": p, "serial": ""} for p in explicit.split(os.pathsep) if p]
    ports = []
    try:
        from PyQt6.QtSerialPort import QSerialPortInfo
    except ImportError:
        QSerialPortInfo = None
    if QSerialPortInfo is not None:
        for info in QSerialPortInfo.availablePorts():
            if (info.vendorIdentifier(), info.productIdentifier()) not in USB_IDS:
                continue
            path = info.systemLocation()
            if sys.platform == "darwin" and os.path.basename(path).startswith("tty."):
                continue        # macOS lists each port twice; cu.* opens without waiting for carrier
            ports.append({"port": path, "serial": info.serialNumber()})
    elif sys.platform.startswith("linux"):
        import glob
        for dev in glob.glob("/sys/class/tty/ttyACM*"):
            try:
                usb = os.path.realpath(os.path.join(dev, "device", ".."))
                with open(os.path.join(usb, "idVendor")) as f:
                    vid = int(f.read(), 16)
                with open(os.path.join(usb, "idProduct")) as f:
                    pid = int(f.read(), 16)
            except (OSError, ValueError):
                continue
            if (vid, pid) in USB_IDS:
                ports.append({"port": "/dev/" + os.path.basename(dev), "serial": ""})
    return sorted(ports, key=lambda p: p["port"])


def scan_tinysas() -> list:
    """
    Every tinySA on USB, for choosing one in the Connection dialog. Each entry
    has "kind": "tinysa", "port", "serial" (the USB serial string) and
    "tinysa_index" (its place in the order find_tinysa uses), plus either
    "name" and "firmware" (it answered), "busy": True (the port is open
    elsewhere, e.g. by a connected slot), or "error" (it cannot be opened).
    Serial devices that answer but are not tinySAs are left out.
    """
    found = []
    for cand in list_tinysa_ports():
        entry = {"kind": "tinysa", "port": cand["port"], "serial": cand["serial"], "tinysa_index": len(found)}
        try:
            sa = TinySA(cand["port"], cand["serial"])
        except TinySABusy:
            entry["busy"] = True
        except TinySAOpenError as e:
            if isinstance(e.__cause__, FileNotFoundError):
                continue                    # unplugged since it was listed
            entry["error"] = str(e)
            if isinstance(e.__cause__, PermissionError) and sys.platform.startswith("linux"):
                entry["error"] += " (add your user to the 'dialout' group, then log in again)"
        except TinySAError:
            continue                        # gone again, or not a tinySA (e.g. a NanoVNA)
        else:
            entry.update(name=sa.name, firmware=sa.firmware)
            sa.close(resume=False)
        found.append(entry)
    return found


def find_tinysa(index: int = 0):
    """
    Open the index-th tinySA on USB (0 = first). Returns None if there are fewer
    than index + 1 units; raises TinySAError if that unit is in use.
    """
    n = 0
    for cand in list_tinysa_ports():
        try:
            sa = TinySA(cand["port"], cand["serial"])
        except TinySABusy:
            sa = None                       # another slot's tinySA: it still counts
        except TinySAOpenError as e:
            if isinstance(e.__cause__, FileNotFoundError):
                continue                    # unplugged since it was listed
            sa = None                       # a port that cannot be opened is listed by scan_tinysas too
        except TinySAError:
            continue                        # gone again, or not a tinySA (e.g. a NanoVNA)
        if n == index:
            if sa is None:
                raise TinySAError(f"The tinySA on {cand['port']} is in use or cannot be opened.")
            return sa
        n += 1
        if sa is not None:
            sa.close(resume=False)
    return None


def _snap_up(values, want):
    """The smallest of the sorted `values` that is >= want (the largest if none is)."""
    return next((v for v in values if v >= want), values[-1])


def _snap_nearest(values, want):
    return min(values, key=lambda v: abs(math.log(v / max(want, 1e-9))))


class TinySAWorker:
    """
    The analyzer loop for one tinySA: applies fReqon's commands and produces
    sweeps (and channel-monitor readings) as hardware_process does.
    """

    def __init__(self, sa: TinySA, data_queue, start_hz, stop_hz, atten=-1, preamp=0x00):
        self.sa = sa
        self.out = data_queue
        self.start_hz, self.stop_hz = float(start_hz), float(stop_hz)
        self.rbw_mode, self.rbw_hz = 1, 0.0          # automatic
        self.atten = int(atten)
        self.lna = self._lna_for(preamp)
        self.spur = sa.spur_default
        self.rf_input = "auto"                       # or one of sa.inputs: use only that connector
        self.comp = ([], [])                         # input-chain correction table (Hz, dB)
        self.mode = "SWP"
        self.running = False
        self.plan = None
        self.plan_dirty = True
        self.rate = None                             # measured scan speed, points/s
        self._range_note = None
        self.mscan_channels = []
        self.mscan_span_hz = MSCAN_SPAN_NUMERATOR_HZ / 256
        self.mscan_i = 0
        self.mscan_round = 0
        self.det = None                              # zero span: {"freq", "points", "ref", "trigger"}
        self.zs_dt = None                            # measured seconds per zero-span sample
        self._armed = None                           # the device's own triggered sweep, while in use

    @staticmethod
    def _lna_for(preamp) -> bool:
        # The Harogic options are Auto (0), Off (1) and three gains (2-4); the
        # Ultra's LNA is on for an explicit gain choice only (it bypasses the attenuator)
        return int(preamp or 0) >= 0x02

    # -- commands ----------------------------------------------------------------

    def handle(self, cmd) -> bool:
        """Apply one command from the GUI; False means shut down."""
        name, args = (cmd[0], cmd[1] if len(cmd) > 1 else None) if isinstance(cmd, tuple) else (cmd, None)
        if name in ("stop", "close"):
            return False
        if name == "start":
            self.running = True
        elif name == "pause":
            self.running = False
        elif name == "stop_mscan":
            if self.mode == "MSCAN":
                self._to_sweep("Channel monitor stopped, returning to Swept Spectrum")
        elif name == "set_mode":
            target = str(args[0]).upper()
            if target == "SWP":
                self._to_sweep("Switched to Swept Spectrum (SWP) mode")
                self.running = True
            elif target == "MSCAN":
                if self.mode != "MSCAN":
                    self.mode = "MSCAN"             # scanning starts with the channel list
                    self.mscan_channels = []
                self.running = True
            elif target == "DET":
                self.mode = "DET"
                self.running = True
            else:
                self._unsupported({"RTA": "real-time spectrum",
                                   "IQS": "IQ streaming (demodulation and audio)"}.get(target, target))
        elif name == "config":
            # Reference level, IF AGC and IF output have no tinySA equivalent.
            # Attenuation and LNA take effect on the next scan; only a new range
            # restarts the sweep.
            start, stop, _ref, atten, preamp = args[:5]
            if (float(start), float(stop)) != (self.start_hz, self.stop_hz):
                self.start_hz, self.stop_hz = float(start), float(stop)
                self.plan_dirty = True
            self.atten, self.lna = int(atten), self._lna_for(preamp)
        elif name == "bw_config":
            if (int(args[0]), float(args[1])) != (self.rbw_mode, self.rbw_hz):
                self.rbw_mode, self.rbw_hz = int(args[0]), float(args[1])
                self.plan_dirty = True
        elif name == "sweep_config":
            self.spur = int(args[3])
        elif name == "rf_input":
            choice = str(args).lower() if str(args).lower() in self.sa.inputs else "auto"
            if choice != self.rf_input:
                self.rf_input = choice
                self.plan_dirty = True
        elif name == "mscan_config":
            # Dwell, detector and gain settings are the Harogic MSCAN's; the
            # channel monitor here uses the sweep's attenuation and LNA settings.
            channels = list(args[0])
            decimate = args[6] if len(args) >= 7 else 256
            self.mscan_channels = channels
            self.mscan_span_hz = MSCAN_SPAN_NUMERATOR_HZ / (decimate if decimate in (64, 128, 256, 512, 1024) else 256)
            self.mscan_i = self.mscan_round = 0
            self.rate = None
            if channels:
                self.mode, self.running = "MSCAN", True
                self.out.put(("status", f"Channel monitor active: {len(channels)} channels, stepped one at a time"))
            else:
                self.out.put(("status", "Channel monitor stopped: channel list empty"))
        elif name == "freq_comp":
            freqs, vals = args
            self.comp = (list(freqs), list(vals))
            if self.plan is not None:
                self.plan["comp"] = self._comp_at(self.plan["freq"])
            self.out.put(("freq_comp", (0, len(self.comp[0]))))
        elif name == "rta_config":
            self._unsupported("real-time spectrum")
        elif name == "det_config":
            # (centre, decimation, reference level, trigger source, trigger mode, length):
            # the tinySA has one sample rate, so the decimation is not used
            c_freq, _dec, ref, trig_src, _trig_mode, length = args[:6]
            self.det = {"freq": float(c_freq), "ref": float(ref), "trigger": int(trig_src),
                        "level": float(args[6]) if len(args) > 6 and args[6] is not None else None,
                        # its own attenuation and LNA; None: the sweep's
                        "atten": int(args[7]) if len(args) > 7 and args[7] is not None else None,
                        "lna": self._lna_for(args[8]) if len(args) > 8 and args[8] is not None else None,
                        "points": int(min(max(int(length), 64), ZERO_SPAN_MAX_POINTS))}
            self.mode, self.running = "DET", True
            self.out.put(("status", f"Zero span at {c_freq / 1e6:.3f} MHz, {self.det['points']} samples"))
        elif name == "iqs_config":
            self._unsupported("IQ streaming (demodulation and audio)")
        # detect_config, fan_config: nothing to set on a tinySA
        return True

    def _to_sweep(self, message: str):
        if self.mode != "SWP":
            self.mode = "SWP"
            self.plan_dirty = True
            self.out.put(("status", message))

    def _unsupported(self, what: str):
        self.out.put(("status", f"The {self.sa.name} has no {what} mode; staying in Swept Spectrum."))

    def _comp_at(self, freq):
        """Input-chain correction (dB) at freq, or None when there is none."""
        f, v = self.comp
        if not f:
            return None
        return np.interp(freq, f, v).astype(np.float32)

    # -- swept spectrum ------------------------------------------------------------

    def _pick_rbw(self, span_hz: float) -> float:
        rbws = self.sa.rbw_list
        if self.rbw_mode == 1:
            return _snap_up(rbws, span_hz / (AUTO_MAX_POINTS / 2))
        if self.rbw_mode == 2:
            return _snap_nearest(rbws, span_hz * 0.001)
        if self.rbw_mode == 3:
            return _snap_nearest(rbws, span_hz * 0.01)
        return _snap_nearest(rbws, self.rbw_hz) if self.rbw_hz > 0 else _snap_up(rbws, span_hz / (AUTO_MAX_POINTS / 2))

    def _build_plan(self):
        sa = self.sa
        self.plan_dirty = False
        self.plan = None
        # The sweep is limited to what the analyzer (or the selected input) can tune
        lo, hi = sa.input_range(self.rf_input)
        whose = f"{sa.name}'s {self.rf_input.capitalize()} input" if self.rf_input in sa.inputs else sa.name
        start = min(max(self.start_hz, lo), hi)
        stop = min(max(self.stop_hz, lo), hi)
        note = None
        if self.stop_hz - self.start_hz < 1e3:
            note = "The sweep span is under 1 kHz: nothing to sweep."
        elif stop - start < 1e3:
            note = (f"{self.start_hz / 1e6:g} - {self.stop_hz / 1e6:g} MHz is outside the range of the {whose} "
                    f"({lo / 1e6:g} - {hi / 1e6:g} MHz).")
        elif (start, stop) != (self.start_hz, self.stop_hz):
            note = (f"Sweep limited to {start / 1e6:g} - {stop / 1e6:g} MHz, the range of the {whose}.")
        if note and note != self._range_note:
            self.out.put(("status", note))
        self._range_note = note
        if stop - start < 1e3:
            self.out.put(("sweep_plan", {"rf_input": self.rf_input, "inputs": [], "note": note}))
            return
        span = stop - start
        rbw = self._pick_rbw(span)
        # Two points per RBW; with fewer the tinySA itself fills in between points
        points = int(min(MAX_POINTS, max(MIN_POINTS, math.ceil(span / (rbw / 2)) + 1)))
        step = max(1, int(round(span / (points - 1))))
        freq = int(start) + step * np.arange(points, dtype=np.float64)
        self.plan = {
            "start": int(start), "step": step, "points": points, "rbw": rbw, "freq": freq,
            "segments": sa.segments(freq, self.rf_input), "comp": self._comp_at(freq),
            "power": np.full(points, -120.0, dtype=np.float32), "seg": 0, "pos": 0,
        }
        self.rate = None
        self.out.put(("trace_points", points))
        self.out.put(("hw_rbw_updated", (float(rbw), float(rbw))))
        # Which input(s) this sweep uses: they are separate connectors, so the user needs to know
        self.out.put(("sweep_plan", {"rf_input": self.rf_input, "note": note,
                                     "inputs": [band for band, _, _ in self.plan["segments"] if band]}))

    def _chunk(self, remaining: int) -> int:
        """How many points to scan next: about CHUNK_TARGET_S worth, so commands are answered promptly."""
        if self.rate is None:
            n = FIRST_CHUNK_POINTS
        else:
            n = max(8, int(self.rate * CHUNK_TARGET_S))
        return remaining if remaining <= n * 1.5 else n

    def _scan(self, start_hz, step_hz, n) -> np.ndarray:
        timeout = 20.0 + n if self.rate is None else max(3.0, 6.0 * n / self.rate + 3.0)
        t0 = time.monotonic()
        levels = self.sa.scan_raw(start_hz, step_hz, n, timeout)
        # The rate is that of the measurement alone: counting a scan's fixed cost
        # would make short scans look slow, and the pieces would never grow
        measuring_s = max(time.monotonic() - t0 - SCAN_OVERHEAD_S, 0.05)
        self.rate = n / measuring_s if self.rate is None else 0.5 * self.rate + 0.5 * n / measuring_s
        return levels

    def _sweep_step(self) -> bool:
        if self.plan_dirty:
            self._build_plan()
        p = self.plan
        if p is None:
            return False
        band, _first, end = p["segments"][p["seg"]]
        self.sa.apply(band, p["rbw"], self.atten, self.lna, self.spur, p["freq"][-1])
        n = self._chunk(end - p["pos"])
        p["power"][p["pos"]:p["pos"] + n] = self._scan(p["start"] + p["step"] * p["pos"], p["step"], n)
        p["pos"] += n
        if p["pos"] >= end:
            p["seg"] += 1
        if p["seg"] >= len(p["segments"]):
            power = p["power"] if p["comp"] is None else p["power"] + p["comp"]
            try:
                self.out.put_nowait(("data", (p["freq"].copy(), power.astype(np.float32, copy=True))))
            except queue.Full:
                pass
            p["seg"] = p["pos"] = 0
        return True

    # -- channel monitor -------------------------------------------------------------

    def _mscan_step(self) -> bool:
        """
        One channel of the channel monitor. The tinySA has no hardware channel
        scan, so each channel gets a short sweep across its bandwidth; the
        result is reported like a Harogic MSCAN hop.
        """
        if not self.mscan_channels:
            return False
        sa = self.sa
        idx = self.mscan_i
        ch = self.mscan_channels[idx]
        info = ch if isinstance(ch, dict) else {}
        fc = float(ch.get("freq_hz", ch.get("freq", 0.0))) if isinstance(ch, dict) else float(ch)
        step = max(1, int(self.mscan_span_hz / MSCAN_POINTS))
        span = step * MSCAN_POINTS
        start = int(fc - span / 2 + step / 2)            # bin centres, as an MSCAN spectrum has
        last = start + step * (MSCAN_POINTS - 1)
        spec, peak = None, -130.0
        lo, hi = sa.input_range(self.rf_input)
        if lo <= start and last <= hi:
            band = sa.band_for(start, last, self.rf_input)
            if band == "split":
                band = "low" if fc < LOW_BAND_MAX_HZ else "high"
            sa.apply(band, _snap_up(sa.rbw_list, 2 * step), self.atten, self.lna, self.spur, last)
            spec = self._scan(start, step, MSCAN_POINTS)
            comp = self._comp_at(np.array([fc]))
            if comp is not None:
                spec = spec + comp[0]
            freq = start + step * np.arange(MSCAN_POINTS)
            in_channel = np.abs(freq - fc) <= 100e3      # a wireless microphone channel
            peak = float(spec[in_channel].max() if in_channel.any() else spec.max())
        self.out.put(("mscan_data", (idx, fc, peak, spec, {
            "repeat_index": self.mscan_round,
            "element_index": idx,
            "channel_info": info,
            "temperature": 0.0,
            "timestamp": time.time(),
            "span_hz": float(span) if spec is not None else 0.0,
            "points": MSCAN_POINTS if spec is not None else 0,
        })))
        self.mscan_i = (idx + 1) % len(self.mscan_channels)
        if self.mscan_i == 0:
            self.mscan_round += 1
        return spec is not None

    # -- zero span -------------------------------------------------------------------

    def _measure_zero_span_rate(self, freq_hz: int):
        """Seconds per sample of a single-frequency scan, from two scans of different
        length (each scan also costs a fixed 0.2-0.3 s, which cancels out)."""
        times = []
        sizes = (500, 4000)
        for n in sizes:
            t0 = time.monotonic()
            self.sa.scan_raw(freq_hz, 0, n, 30.0)
            times.append(time.monotonic() - t0)
        dt = (times[1] - times[0]) / (sizes[1] - sizes[0])
        if not 2e-6 <= dt <= 5e-3:
            dt = ZERO_SPAN_DEFAULT_S
        self.zs_dt = dt
        self.out.put(("status", f"Zero span: {dt * 1e6:.0f} µs per sample ({1 / dt / 1e3:.1f} kS/s)"))

    def _det_step(self) -> bool:
        """One zero-span capture: the level at one frequency over time."""
        d = self.det
        if not d:
            return False
        sa = self.sa
        f = int(d["freq"])
        lo, hi = sa.input_range(self.rf_input)
        if not lo <= f <= hi:
            if self._range_note != ("det", f):
                self._range_note = ("det", f)
                self.out.put(("status", f"{f / 1e6:g} MHz is outside the range of the {sa.name} "
                                        f"({lo / 1e6:g} - {hi / 1e6:g} MHz)."))
            return False
        band = sa.band_for(f, f, self.rf_input)
        if band == "split":
            band = "low" if f < LOW_BAND_MAX_HZ else "high"
        # The RBW is the detection bandwidth: the one set by hand, else the widest (fastest to respond)
        rbw = _snap_nearest(sa.rbw_list, self.rbw_hz) if self.rbw_mode == 0 and self.rbw_hz > 0 else max(sa.rbw_list)
        atten = self.atten if d.get("atten") is None else d["atten"]
        sa.apply(band, rbw, atten, self.lna if d.get("lna") is None else d["lna"], self.spur, f)
        if self.zs_dt is None:
            self._measure_zero_span_rate(f)
        n = d["points"]
        if d["trigger"] == TRIG_ARMED and d["level"] is not None:
            return self._det_armed_step(d, f, band, rbw, atten)
        # Level trigger: capture extra, then start the window just before the first rising edge
        total = min(ZERO_SPAN_MAX_POINTS, int(n * 1.5)) if d["trigger"] == TRIG_LEVEL else n
        levels = sa.scan_raw(f, 0, total + ZERO_SPAN_LEAD, 10.0 + 4.0 * total * self.zs_dt)[ZERO_SPAN_LEAD:]
        comp = self._comp_at(np.array([float(f)]))
        if comp is not None:
            levels = levels + comp[0]
        n = min(n, total)
        start = 0
        if total > n:
            threshold = d["level"] if d["level"] is not None else float(levels.max()) - 10.0
            rising = np.nonzero((levels[1:] >= threshold) & (levels[:-1] < threshold))[0] + 1
            pre = n // 10
            usable = rising[(rising >= pre) & (rising - pre + n <= total)]
            if len(usable):
                start = int(usable[0]) - pre
        power = levels[start:start + n].astype(np.float32)
        dt_ns = self.zs_dt * 1e9
        self.out.put(("det_data", (np.arange(n, dtype=np.float64) * dt_ns, power, {
            "center_freq": float(f), "decimate": 1, "sample_interval_ns": dt_ns,
            "trigger_length": n, "ref_level": d["ref"], "rbw_hz": float(rbw),
        })))
        return True

    def _det_armed_step(self, d, f, band, rbw, atten) -> bool:
        """Zero span with the tinySA's own trigger: arm it, then look now and then for a capture."""
        sa = self.sa
        comp = self._comp_at(np.array([float(f)]))
        offset = float(comp[0]) if comp is not None else 0.0
        window = min(60.0, max(ARMED_MIN_SWEEP_S, d["points"] * self.zs_dt))
        level = int(round(d["level"] - offset))          # as the analyzer reads it
        key = (f, band, rbw, atten, d.get("lna"), round(window, 4), level)
        now = time.monotonic()
        a = self._armed
        if a is None or a["key"] != key:
            saved = a["saved"] if a else sa.own_sweep()
            for c in (f"sweep cw {f}", f"sweeptime {window:.4g}", f"trigger {level}"):
                sa.command(c)
            self._armed = a = {"key": key, "saved": saved}
            self._arm(a, window)
            self.out.put(("status", f"Zero span armed at {f / 1e6:.3f} MHz: waiting for {d['level']:.0f} dBm"))
            return True
        if now < a["next_poll"]:
            return False
        trace = sa.read_trace()
        if len(trace) != len(a["base"]) or np.array_equal(trace, a["base"]):
            a["next_poll"] = time.monotonic() + window + ARMED_POLL_EXTRA_S     # still waiting
            return True
        # A capture has the crossing mid-trace. A changed trace without it was cut short by
        # this very check: armed again, nothing shown.
        mid = len(trace) // 2
        if float(trace[max(0, mid - 8):mid + 8].max()) >= level - 1.0:
            dt_ns = window / len(trace) * 1e9
            self.out.put(("det_data", (np.arange(len(trace), dtype=np.float64) * dt_ns, trace + np.float32(offset), {
                "center_freq": float(f), "decimate": 1, "sample_interval_ns": dt_ns,
                "trigger_length": len(trace), "ref_level": d["ref"], "rbw_hz": float(rbw),
                "trigger_level_dbm": d["level"], "trigger_time_ns": mid * dt_ns,
            })))
        self._arm(a, window)
        return True

    def _arm(self, a, window):
        sa = self.sa
        sa.command("trigger single")
        sa.command("resume")
        a["base"] = sa.read_trace()                  # what the screen holds until the trigger fires
        a["next_poll"] = time.monotonic() + window + ARMED_POLL_EXTRA_S

    def leave_armed(self):
        """Give the analyzer's own sweep back its settings and stop it again."""
        a, self._armed = self._armed, None
        if a is None:
            return
        cmds = ["trigger auto", "sweeptime 0.003"]
        if a["saved"]:
            cmds += [f"sweep start {a['saved'][0]}", f"sweep stop {a['saved'][1]}"]
        for c in cmds + ["pause"]:
            try:
                self.sa.command(c)
            except TinySAError:
                break

    def step(self) -> bool:
        """Do one piece of work; False if there was nothing to do."""
        if self._armed and not (self.running and self.mode == "DET" and self.det
                                and self.det["trigger"] == TRIG_ARMED):
            self.leave_armed()
        if not self.running:
            return False
        if self.mode == "MSCAN":
            return self._mscan_step()
        if self.mode == "DET":
            return self._det_step()
        return self._sweep_step()


def tinysa_process(command_queue, data_queue, start_freq_hz, stop_freq_hz, port=None, index=0,
                   atten=-1, preamp=0x00, probe_only=False, device=None):
    """
    Hardware process for a tinySA: the counterpart of hardware_process().
    `device` is an already opened TinySA; otherwise `port` is opened, or the
    index-th tinySA found on USB.
    """
    sa = device
    try:
        if sa is None and port:
            if os.path.exists(port):
                sa = TinySA(port)
            else:
                # Port names can change between plug-ins (Linux numbers them in
                # the order they appear): use the tinySA that is there
                sa = find_tinysa(0)
                if sa is None:
                    raise TinySAError(f"No tinySA on {port}, and none found on another port.")
                data_queue.put(("status", f"No device on {port}; using the tinySA on {sa.port}."))
        elif sa is None:
            sa = find_tinysa(index)
        if sa is None:
            raise TinySAError(f"tinySA #{index + 1} not found. Check the USB connection.")
    except TinySAError as e:
        data_queue.put(("error", str(e)))
        data_queue.put(("connected", False))
        return

    data_queue.put(("capabilities", sa.capabilities()))
    data_queue.put(("device_info", (0, sa.uid)))     # model 0: not a Harogic model number
    if probe_only:
        sa.close(resume=False)
        return
    data_queue.put(("hw_endorsements", sa.describe()))

    worker = TinySAWorker(sa, data_queue, start_freq_hz, stop_freq_hz, atten, preamp)
    parent = multiprocessing.parent_process()
    failures = 0
    try:
        sa.command("pause")                          # stop the device's own sweep; fReqon drives it
        data_queue.put(("connected", True))
        data_queue.put(("status", f"{sa.name} connected ({sa.port}, firmware {sa.firmware})."))
        while True:
            if parent is not None and not parent.is_alive():
                # Nobody will read our queues again
                data_queue.cancel_join_thread()
                command_queue.cancel_join_thread()
                break
            try:
                while True:
                    if not worker.handle(command_queue.get_nowait()):
                        return
            except queue.Empty:
                pass
            try:
                busy = worker.step()
                failures = 0
            except TinySALinkLost:
                raise
            except TinySAError as e:
                failures += 1
                if failures >= 3:
                    raise TinySALinkLost(f"{sa.name} stopped responding ({e})") from e
                data_queue.put(("status", f"{sa.name}: {e} Retrying…"))
                sa.sync()
                sa._sent.clear()
                worker.plan_dirty = True
                busy = True
            if not busy:
                time.sleep(0.02)
    except TinySAError as e:
        data_queue.put(("error", f"{sa.name} disconnected: {e}"))
        data_queue.put(("connected", False))
    finally:
        worker.leave_armed()
        sa.close()
