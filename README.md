# fReqon - RF Analysis Tool for Harogic Analyzers

**fReqon** is a high-performance Python and Qt-based RF Spectrum Analysis, Signal Intelligence, and Monitoring suite built specifically for Harogic Spectrum Analyzers (SAN, SAM, SAE series).

---

## Key Features

- **Real-Time Spectrum Analysis (RTSA)**: High-speed real-time persistence and DPX spectrum display.
- **Continuous Sweep & Waterfall**: Dynamic sweeping, multi-row waterfall heatmaps, and customizable colormaps.
- **Audio Demodulation Engine**: High-fidelity demodulation for AM, FM, WFM, LSB, and USB signals with bandpass filtering and low-latency audio playback.
- **Digital Signal Analyzers**:
  - **DECT Analysis**: Channel occupancy, timeslot analysis, and frame decoding.
  - **ShowLink & CRMX Wireless**: Wireless DMX and stage transmitter tracking and interference detection.
- **Regulatory Database Integration**: Integrated FCC and OFCOM digital TV database lookups to identify broadcast station carriers and guard bands.
- **Multi-Device Support**: Unified control, device switching, and calibration management for Harogic hardware.

---

## Project Structure

```
├── RF_Recon_Modern/          # Modern modular application architecture
│   ├── main.py               # Application entry point
│   ├── core/                 # Drivers, DSP engines, API wrappers, and analyzers
│   └── ui/                   # PySide6 Qt GUI widgets, dialogs, and themes
├── RF_Recon_App/             # Legacy standalone application build
├── API/                      # Harogic Linux API, SDK drivers, and examples
├── CalFile/                  # Hardware calibration tables
```

---

## Requirements & Installation

1. **Python 3.10+**
2. Install Python dependencies:
   ```bash
   pip install -r RF_Recon_App/requirements.txt
   ```
3. Install Harogic API libraries:
   Run the installation script in `API/Linux_API-SAN-828/Linux_API/install_htraapi_lib.sh` (or follow vendor driver instructions).

---

## Launching fReqon

To run the modern application:
```bash
python3 RF_Recon_Modern/main.py
```
