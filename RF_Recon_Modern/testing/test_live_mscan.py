"""
test_live_mscan.py - Live Hardware Verification of MSCAN mode at 192.168.1.100.
Connects to physical Harogic analyzer, loads real Soundbase production channels,
activates hardware MSCAN list scanning, and measures physical RF powers & hop rates.
CRITICAL RULE: Zero synthetic data.
"""

import sys, os, time
from PyQt6.QtCore import QCoreApplication
sys.path.insert(0, '/home/parallels/Documents/Harogic Projects/RF_Recon_Modern')

from core.device_controller import DeviceController
from core.soundbase_parser import SoundbaseParser

app = QCoreApplication(sys.argv)
ctrl = DeviceController()

# Load real Soundbase file
sb_path = "/home/parallels/Documents/Harogic Projects/Soundbase Resources/New York, NY 10023.sbcoordsite"
parsed = SoundbaseParser.parse_file(sb_path)
carriers = parsed.get("all_carriers", [])
print(f"Loaded {len(carriers)} real Soundbase carriers from {sb_path}")

# Pick first 16 production channels to scan
test_channels = carriers[:16]
for idx, ch in enumerate(test_channels):
    print(f"  Channel {idx}: {ch.get('name')} @ {ch.get('freq_mhz'):.3f} MHz ({ch.get('group_name')})")

packets_received = []
start_time = None
configured = False

def on_status(msg):
    print(f"[STATUS] {msg}", flush=True)

def on_conn(connected):
    global configured, start_time
    print(f"[CONNECTION] is_connected={connected}", flush=True)
    if connected and not configured:
        configured = True
        print("[TEST] Connected to analyzer! Activating Hardware MSCAN...", flush=True)
        start_time = time.time()
        ctrl.configure_mscan(
            channels=test_channels,
            dwell_time=0.002, # 2 ms dwell time
            detector=1,       # MaxPeak
            ref_level=-10.0,
            preamp=0,
            atten=0
        )

def on_mscan_data(el_idx, ch_freq, peak_power, spec_data, info):
    global packets_received
    now = time.time()
    packets_received.append((el_idx, ch_freq, peak_power, now))
    ch_name = test_channels[el_idx].get('name') if el_idx < len(test_channels) else f"Ch {el_idx}"
    print(f"--> [MSCAN LIVE #{len(packets_received)}] Ch {el_idx:02d} ({ch_name} @ {ch_freq/1e6:.3f} MHz): Peak={peak_power:.1f} dBm, Temp={info.get('temperature', 0):.1f}C", flush=True)
    
    if len(packets_received) >= 48: # 3 full cycles of 16 channels
        elapsed = now - start_time
        hop_rate = len(packets_received) / elapsed
        cycle_time_ms = (16.0 / hop_rate) * 1000.0
        print(f"\n==========================================", flush=True)
        print(f"LIVE HARDWARE MSCAN TEST PASSED!", flush=True)
        print(f"Packets received: {len(packets_received)}", flush=True)
        print(f"Elapsed: {elapsed:.2f} s", flush=True)
        print(f"Hop Rate: {hop_rate:.1f} hops/second", flush=True)
        print(f"Full 16-channel cycle time: {cycle_time_ms:.1f} ms", flush=True)
        print(f"==========================================\n", flush=True)
        app.quit()

ctrl.status_message.connect(on_status)
ctrl.connection_status.connect(on_conn)
ctrl.mscan_data_ready.connect(on_mscan_data)

print("\nConnecting to Harogic Network Analyzer at 192.168.1.100:5000...", flush=True)
ctrl.connect_device(
    start_freq_hz=470e6,
    stop_freq_hz=608e6,
    interface_type='network',
    ip_address='192.168.1.100',
    port=5000,
    target_model=67,
    target_uid=0x54305002003b0035
)

app.exec()
print("Cleaning up and disconnecting device...", flush=True)
ctrl.disconnect_device()
print("Test completed successfully.", flush=True)
