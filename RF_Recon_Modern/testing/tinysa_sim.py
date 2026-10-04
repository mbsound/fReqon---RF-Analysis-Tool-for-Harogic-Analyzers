"""
tinysa_sim.py - A simulated tinySA / tinySA Ultra on a pseudo-terminal.

Speaks the part of the tinySA shell that fReqon uses (see core/tinysa_device.py),
for testing without the hardware. Run it and point fReqon at the port it prints:

    python testing/tinysa_sim.py [ultra|ultra_plus|basic]
    FREQON_TINYSA_PORT=<port> python main.py

(With no Harogic analyzer on USB, slot A then connects to the simulated tinySA.)
"""

import math
import os
import select
import struct
import sys
import threading
import time

VERSIONS = {
    "ultra": "tinySA4_v1.4-143-g864bb27\r\nHW Version:V0.4.5.1 \r\n",
    "ultra_plus": "tinySA4_v1.4-199-gde12ba2\r\nHW Version:V0.5.4 max2871\r\n",
    "basic": "tinySA_v1.4-143-g864bb27\r\n",
    "nanovna": "1.2.27\r\n",        # same USB IDs and prompt, not a tinySA
}


class TinySASim:
    def __init__(self, variant="ultra", carriers=((500e6, -40.0),), noise_dbm=-100.0, point_s=0.0002):
        self.variant = variant
        self.carriers = list(carriers)      # (frequency Hz, level dBm)
        self.noise_dbm = noise_dbm
        self.point_s = point_s              # time per measured point
        self.is_ultra = variant.startswith("ultra")
        self.zero = 174 if self.is_ultra else 128
        self.rbw_khz = 100.0
        self.mode = "low"
        self.ultra_on = False
        self.atten, self.lna, self.spur = "auto", "off", "off"
        self.paused = False
        self.keyed = None                   # (frequency Hz, period, on time) in samples: keyed on and off, seen in zero span
        # The device's own sweep and trigger (zero span with "sweep cw")
        self.own_sweep = [470000000, 608000000]
        self.sweeptime = 0.003
        self.trig_level, self.trig_mode, self._armed_at = None, "auto", None
        self.trace = [noise_dbm] * 290
        self._scans = 0
        self.log = []                       # every command line received
        self._master, self._slave = os.openpty()
        self.port = os.ttyname(self._slave)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def close(self):
        """Unplug: the port goes away."""
        self._stop.set()
        self._thread.join(timeout=2)
        for fd in (self._master, self._slave):
            try:
                os.close(fd)
            except OSError:
                pass

    # -- the device ------------------------------------------------------------

    def level(self, f_hz: float, bw_hz: float) -> float:
        """Level a receiver of bandwidth bw_hz reads at f_hz, in dBm."""
        if self.is_ultra:
            limit = 5.3e9 if self.variant == "ultra" else 7.3e9
            normal = 800e6 if self.variant == "ultra" else 900e6
            reachable = f_hz <= (limit if self.ultra_on else normal)
        elif self.mode == "low":
            reachable = f_hz <= 350e6
        else:
            reachable = 240e6 <= f_hz <= 960e6
        if not reachable:
            return -120.0
        mw = 10 ** (self.noise_dbm / 10)
        for fc, dbm in self.carriers:
            mw += 10 ** (dbm / 10) * math.exp(-0.5 * ((f_hz - fc) / (0.5 * bw_hz)) ** 2)
        return 10 * math.log10(mw)

    def _scanraw(self, args):
        start, stop, points = int(args[0]), int(args[1]), int(args[2])
        if start > stop:
            return b"frequency range is invalid\r\n"
        step = (stop - start) // points
        bw = max(self.rbw_khz * 1e3, step)      # the device fills in between coarse steps
        out = bytearray(b"{")
        self._scans += 1
        off = None
        if step == 0 and self.keyed and abs(start - self.keyed[0]) < bw:
            # Zero span on the keyed carrier: each scan starts somewhere else in its cycle
            kept, self.carriers = self.carriers, [c for c in self.carriers if c[0] != self.keyed[0]]
            off = int(round((self.level(start, bw) + self.zero) * 32))
            self.carriers = kept
        for i in range(points):
            if off is not None and (i + 137 * self._scans) % self.keyed[1] >= self.keyed[2]:
                value = off
            else:
                value = int(round((self.level(start + step * i, bw) + self.zero) * 32))
            out += b"x" + struct.pack("<H", max(0, min(0xFFFF, value)))
        out += b"}"
        time.sleep(self.point_s * points)
        return bytes(out)

    def _own_trace(self) -> bytes:
        """
        "data 2". Asking interrupts the wait for the trigger; an armed single sweep whose
        level a signal at the frequency crosses (a keyed carrier keying on, or a steady
        one) is captured once a window has passed, with the crossing mid-trace.
        """
        f = self.own_sweep[0]
        bw = self.rbw_khz * 1e3
        now = time.monotonic()
        if self.trig_mode == "single" and self._armed_at is not None and not self.paused \
                and self.own_sweep[0] == self.own_sweep[1] and now - self._armed_at >= self.sweeptime:
            on = self.level(f, bw)
            keyed = bool(self.keyed) and abs(f - self.keyed[0]) < bw
            if on >= self.trig_level:
                kept, off = self.carriers, on
                if keyed:
                    self.carriers = [c for c in kept if c[0] != self.keyed[0]]
                    off = self.level(f, bw)
                    self.carriers = kept
                per_point = self.sweeptime / 290 / self.point_s      # the carrier's samples per trace point
                self._scans += 1
                ripple = 0.125 * (self._scans % 5)                    # no two captures are the same
                self.trace = [(on if not keyed or (i >= 145 and ((i - 145) * per_point) % self.keyed[1] < self.keyed[2])
                               else off) + ripple for i in range(290)]
                self._armed_at = None
        if self._armed_at is not None:
            self._armed_at = now
        return "".join(f"{v:.6f}\r\n" for v in self.trace).encode()

    def _execute(self, line: str) -> bytes:
        self.log.append(line)
        parts = line.split()
        if not parts:
            return b"?\r\n"
        cmd, args = parts[0], parts[1:]
        if cmd == "version":
            return VERSIONS[self.variant].encode()
        if self.variant == "nanovna":
            return f"{cmd}?\r\n".encode()
        if cmd == "zero":
            if args:
                self.zero = int(args[0])
                return b""
            return f"usage: zero {{level}}\r\n{self.zero}dBm\r\n".encode()
        if cmd == "pause":
            self.paused = True
        elif cmd == "resume":
            self.paused = False
        elif cmd == "sweep":
            if not args:
                return f"{self.own_sweep[0]} {self.own_sweep[1]} 290\r\n".encode()
            if args[0] == "cw":
                self.own_sweep = [int(args[1]), int(args[1])]
            elif args[0] in ("start", "stop"):
                self.own_sweep[args[0] == "stop"] = int(args[1])
        elif cmd == "sweeptime" and args:
            self.sweeptime = float(args[0])
        elif cmd == "trigger" and args:
            if args[0] in ("auto", "normal", "single"):
                self.trig_mode = args[0]
                self._armed_at = time.monotonic() if args[0] == "single" else None
            else:
                self.trig_level = float(args[0])
        elif cmd == "data" and args:
            return self._own_trace()
        elif cmd == "mode" and len(args) == 2:
            self.mode = args[0]
            self.rbw_khz, self.atten, self.spur = 100.0, "auto", "off"   # a mode change resets settings
        elif cmd == "rbw" and args:
            self.rbw_khz = 100.0 if args[0] == "auto" else float(args[0])
        elif cmd == "attenuate" and args:
            self.atten = args[0]
        elif cmd == "spur" and args:
            self.spur = args[0]
        elif cmd == "lna" and args and self.is_ultra:
            self.lna = args[0]
        elif cmd == "ultra" and args and self.is_ultra:
            self.ultra_on = args[0] == "on"
        elif cmd == "scanraw" and len(args) >= 3:
            return self._scanraw(args)
        elif cmd == "abort":
            pass
        else:
            return f"{cmd}?\r\n".encode()
        return b""

    def _run(self):
        line = bytearray()
        while not self._stop.is_set():
            ready, _, _ = select.select([self._master], [], [], 0.05)
            if not ready:
                continue
            try:
                data = os.read(self._master, 4096)
            except OSError:
                return
            for byte in data:
                if byte == 0x0D:
                    reply = self._execute(line.decode("ascii", "replace"))
                    line.clear()
                    self._send(b"\r\n" + reply + b"ch> ")
                elif byte >= 0x20:
                    line.append(byte)
                    self._send(bytes([byte]))       # echo

    def _send(self, data: bytes):
        try:
            os.write(self._master, data)
        except OSError:
            pass


if __name__ == "__main__":
    sim = TinySASim(sys.argv[1] if len(sys.argv) > 1 else "ultra",
                    carriers=((482.0e6, -45.0), (518.3e6, -62.0), (566.875e6, -38.0), (2440e6, -55.0)),
                    point_s=0.001)
    print(f"Simulated {sim.variant} tinySA on {sim.port}")
    print(f"  FREQON_TINYSA_PORT={sim.port} python main.py")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sim.close()
