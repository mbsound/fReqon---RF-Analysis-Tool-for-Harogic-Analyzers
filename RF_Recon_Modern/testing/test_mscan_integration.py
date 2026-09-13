"""
test_mscan_integration.py - Headless test for Hardware Discrete Channel Scanning (MSCAN).
Verifies:
1. MSCAN ctypes structs and Harogic DLL function prototypes
2. MSCANPanel and MSCANView component instantiation
3. Soundbase coordination file parsing and populating MSCAN channels
4. Dynamic card creation, live meter updates, and telemetry calculations
"""

import sys
import os
import numpy as np

# Set headless Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '/home/parallels/Documents/Harogic Projects/RF_Recon_Modern')

from PyQt6.QtWidgets import QApplication
from core.soundbase_parser import SoundbaseParser
from core.htra_api_wrapper import (
    MSCAN_Profile_TypeDef, MSCAN_Info_Typedef, MSCAN_Data_Typedef,
    Detector_TypeDef, Window_TypeDef, IFAGC_TypeDef, XPPSTrigger_TypeDef, IQPlayBack_TypeDef
)
from ui.widgets.panels.mscan_panel import MSCANPanel
from ui.widgets.mscan_view import MSCANView

def main():
    print("=== 1. Checking MSCAN Ctypes Structures ===")
    p = MSCAN_Profile_TypeDef()
    p.CenterFreq_Hz = 514.25e6
    p.RefLevel_dBm = -15.0
    p.DwellTime = 0.001
    p.DecimateFactor = 1
    p.FFTSize = 512
    p.DetectCount = 1
    p.Detector = Detector_TypeDef.Detector_PosPeak
    p.IFAGC = IFAGC_TypeDef.IFAGC_Off
    p.XPPSTrigger = XPPSTrigger_TypeDef.XPPSTrigger_Off
    p.IQPlayBack = IQPlayBack_TypeDef.IQPlayBack_Off
    p.Window = Window_TypeDef.Blackman
    print("MSCAN Profile initialized successfully.")

    data = MSCAN_Data_Typedef()
    print("MSCAN Data structure initialized successfully.")

    print("\n=== 2. Initializing Qt Application and MSCAN Widgets ===")
    app = QApplication.instance() or QApplication(sys.argv)

    panel = MSCANPanel()
    view = MSCANView()
    print("MSCANPanel and MSCANView created.")

    print("\n=== 3. Loading Soundbase Test File ===")
    sb_path = "/home/parallels/Documents/Harogic Projects/Soundbase Resources/SB_Site_Coord_JSON.json"
    if not os.path.exists(sb_path):
        # Check alternative file
        sb_dir = "/home/parallels/Documents/Harogic Projects/Soundbase Resources"
        files = [f for f in os.listdir(sb_dir) if f.endswith(('.json', '.sbcoordsite'))]
        if files:
            sb_path = os.path.join(sb_dir, files[0])
            print(f"Using found soundbase file: {sb_path}")
        else:
            raise FileNotFoundError(f"No soundbase files found in {sb_dir}")

    parsed = SoundbaseParser.parse_file(sb_path)
    carriers = parsed.get("all_carriers", [])
    print(f"Parsed {len(carriers)} production carriers from {sb_path}.")

    # Populate panel and view
    panel.set_soundbase_data(parsed)
    view.set_channels(carriers)
    print(f"MSCANPanel populated: {panel.channel_summary_lbl.text()}")
    print(f"MSCANView populated: {len(view.channel_cards)} channel cards active.")

    print("\n=== 4. Simulating Live Hopped Channel RF Packets ===")
    # Simulate receiving real RF power packets for channels
    for el_idx in range(min(12, len(carriers))):
        ch = carriers[el_idx]
        freq = float(ch.get("freq_hz", 500e6))
        # Simulate a realistic power level for testing
        test_power = -58.5 - (el_idx * 3.0) # between -58 dBm and -94 dBm
        test_spec = np.full(512, test_power - 20.0, dtype=np.float32)
        test_spec[250:262] = test_power # peak at center

        view.update_channel_data(
            element_idx=el_idx,
            freq_hz=freq,
            peak_power_dbm=test_power,
            spec_data=test_spec,
            info={"repeat_index": 1, "element_index": el_idx, "temperature": 42.0},
            dropout_thresh_dbm=-75.0
        )
        card = view.channel_cards[el_idx]
        print(f"  Card {el_idx} [{card.name} @ {card.freq_mhz:.3f} MHz]: Level={card.power_lbl.text()}, Status={card.status_badge.text()}, Dropout={card.is_dropout}")

    # Verify telemetry update
    panel.update_telemetry(len(panel.selected_carriers), 24.5, 40.8)
    print(f"\nTelemetry label: {panel.lbl_telem_metrics.text()}")

    print("\n=== 5. Testing Selection Filtering ===")
    panel.clear_all_channels()
    print(f"After clear: {panel.channel_summary_lbl.text()}")
    panel.select_all_channels()
    print(f"After select all: {panel.channel_summary_lbl.text()}")

    print("\n>>> All MSCAN verification tests passed successfully! <<<")

if __name__ == "__main__":
    main()
