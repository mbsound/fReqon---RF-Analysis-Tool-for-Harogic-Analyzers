# Harogic Network Analyzer Setup & Fix Guide

This document details the root causes and persistent resolutions for connection timeouts (`10060 APIRETVAL_ERROR_ETHTimeOut`) and bus open failures (`-1 APIRETVAL_ERROR_BusOpenFailed`) when connecting to Harogic Ethernet/Network spectrum analyzers (such as the Raspberry Pi Compute Module 5 based Model 67).

---

## 1. Symptoms & Failure Modes

When attempting to connect to a Harogic network analyzer at `192.168.1.100:5000`:
1. Subnet scanning successfully discovers the analyzer IP and ports 5000 / 9000.
2. Initiating a connection via `Device_Open()` either:
   - **Hangs for several seconds and returns error `10060`** (`APIRETVAL_ERROR_ETHTimeOut`), or
   - **Immediately returns error `-1`** (`APIRETVAL_ERROR_BusOpenFailed`).

---

## 2. Root Cause Analysis

### A. The `10060` Timeout: `ETH_server` Daemon Segfault
- When a client connects to TCP port 5000, `/opt/Function/ETH_Server/ETH_server-0.55.89` accepts the connection and invokes `Write_Command(device_local&)`.
- The daemon parses `/etc/device/sys.json` where `"PowerSourceType": "1"`.
- Under `PowerSourceType == 1`, `ETH_server` called `device_local::set_device_powersupply_usbport()`, which attempts to write to an external Cypress FX3 USB control pipe.
- On embedded Raspberry Pi Compute Module 5 (CM5) units, no external FX3 USB control pipe exists; the control pipe pointer is NULL, causing an immediate `SIGSEGV` (`SEGV_MAPERR` at memory address `0x4`).
- With `ETH_server` crashed, the TCP socket is closed abruptly. Host `libhtraapi.so` hangs awaiting response packets until timing out with `10060`.

### B. The `-1` Bus Open Error: Early Boot Power & USB Enumeration
- The embedded analyzer module communicates with the Raspberry Pi CM5 over an internal USB 3.0 SuperSpeed link.
- In `/boot/firmware/config.txt`, the `[cm5]` section originally drove `gpio=10,7,13=op,dl` (drive low).
- **GPIO 7 controls the power/enable rail** for the Harogic RF module's USB 3.0 interface.
- Because GPIO 7 was driven low during boot, the kernel's `xhci-hcd.1` host controller encountered USB port configuration timeouts:
  ```
  [   1.070555] usb usb5-port1: config error
  [  16.983253] xhci-hcd xhci-hcd.1: Abort failed to stop command ring: -110
  [  17.003423] xhci-hcd xhci-hcd.1: xHCI host controller not responding, assume dead
  [  17.003428] xhci-hcd xhci-hcd.1: HC died; cleaning up
  ```
- The companion service `/etc/systemd/system/init_gpios.service` failed because it called `raspi-gpio` (unsupported on Raspberry Pi 5 / CM5) rather than `pinctrl`.
- As a result, the analyzer hardware was disconnected (`lsusb` showed no device `367f:0001`), and `Bus_Phy_Open` returned status `-1`.

### C. Wildcard Globbing in Startup Scripts
- `/opt/Function/Restart/restart_server.sh` originally executed `sudo $ETH_Server &` with `ETH_Server="/opt/Function/ETH_Server/ETH_server*"`. If backup copies (e.g. `ETH_server-0.55.89.orig`) resided in the folder, the shell passed the backup binary path as an argument to the server.

---

## 3. Step-by-Step Resolution

### 1. Patch `ETH_server-0.55.89` Binary
Disassemble `/opt/Function/ETH_Server/ETH_server-0.55.89` and locate virtual address `0x4102b8` (file offset `0x102b8`):
```assembly
0x4102b0: ldr  w0, [sp, #8168]   ; loads PowerSourceType
0x4102b4: cmp  w0, #0x1
0x4102b8: b.eq 0x410ecc          ; branch to set_device_powersupply_usbport()
```
Replace the branch instruction at `0x102b8` with a `NOP` (`1f 20 03 d5` in little-endian AArch64):
```python
with open('/opt/Function/ETH_Server/ETH_server-0.55.89', 'r+b') as f:
    f.seek(0x102b8)
    f.write(b'\x1f\x20\x03\xd5')
```
Move any backup files outside `/opt/Function/ETH_Server/` (e.g. to `/root/`).

### 2. Configure Bootloader GPIO Power Rail
Edit `/boot/firmware/config.txt` under `[cm5]` so GPIO 7 is driven **HIGH** (`op,dh`) at initial power-up:
```ini
[cm5]
dtoverlay=dwc2,dr_mode=host
gpio=20,11,21,24,18,12,7=op,dh
dtoverlay=i2c3,pins_22_23
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
gpio=10,13=op,dl
dtoverlay=uart0,txd0_pin=14,rxd0_pin=15
enable_uart=1
dtoverlay=goodix,i2c1,interrupt-gpio=4,reset-gpio=17
[all]
```

### 3. Update `init_gpios.sh` for Raspberry Pi 5
Edit `/usr/local/bin/init_gpios.sh` to use `pinctrl` instead of deprecated `raspi-gpio`:
```bash
#!/bin/bash
pinctrl set 7 op dh
pinctrl set 20 op dh
pinctrl set 11 op dh
pinctrl set 21 op dh
pinctrl set 24 op dh
pinctrl set 18 op dh
pinctrl set 2 op dh
pinctrl set 3 op dh
```

### 4. Update `restart_server.sh`
In `/opt/Function/Restart/restart_server.sh`, implement a hardware enumeration check and safe single-binary launch:
```sh
start_eth_server() {
    ETH_RUN=$(ps -ef | grep ETH_server | grep -v grep | awk '{print $2}')
    if [ -n "$ETH_RUN" ]; then
        sleep 0.1
    else
        # Verify physical USB enumeration; rebind host controller if needed
        if ! lsusb -d 367f:0001 >/dev/null 2>&1; then
            pinctrl set 7 op dh 2>/dev/null || true
            echo xhci-hcd.1 > /sys/bus/platform/drivers/xhci-hcd/unbind 2>/dev/null || true
            sleep 0.5
            echo xhci-hcd.1 > /sys/bus/platform/drivers/xhci-hcd/bind 2>/dev/null || true
            sleep 1
        fi
        for server in $ETH_Server; do
            [ -x "$server" ] || continue
            sudo "$server" &
            break
        done
    fi
}
```

---

## 4. Verification

1. Verify hardware is detected:
   ```bash
   lsusb
   # Bus 005 Device 002: ID 367f:0001 Manufacturer Spectrum Analyzer
   ```
2. Verify local self-test:
   ```bash
   /opt/Function/SystemRead/SystemRead
   # Output: Device Open Success, Model = 67, BusSpeed = 3
   ```
3. In **fReqon**, open the Connection Dialog, scan the local subnet, and connect to `192.168.1.100:5000`. Real RF spectrum sweeps will stream continuously.
