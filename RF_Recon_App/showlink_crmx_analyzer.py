"""
showlink_crmx_analyzer.py - 2.4 GHz ShowLink & Wireless DMX (CRMX / W-DMX) Coexistence Engine
Provides real-time ShowLink channel health ratings, Wi-Fi 1/6/11 footprint mapping,
and CRMX / FHSS hopping density analysis for live entertainment RF coordination.
"""

import time
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QGridLayout, QFrame, QWidget, QScrollArea, QProgressBar
)
from PyQt6.QtGui import QColor, QBrush, QPen, QPainter, QFont

SHOWLINK_CHANNELS = {
    11: {"freq_mhz": 2405.0, "wifi_overlap": "Wi-Fi 1"},
    12: {"freq_mhz": 2410.0, "wifi_overlap": "Wi-Fi 1"},
    13: {"freq_mhz": 2415.0, "wifi_overlap": "Wi-Fi 1"},
    14: {"freq_mhz": 2420.0, "wifi_overlap": "Wi-Fi 1"},
    15: {"freq_mhz": 2425.0, "wifi_overlap": "None (Clean Gap 1-6)"},
    16: {"freq_mhz": 2430.0, "wifi_overlap": "Wi-Fi 6"},
    17: {"freq_mhz": 2435.0, "wifi_overlap": "Wi-Fi 6"},
    18: {"freq_mhz": 2440.0, "wifi_overlap": "Wi-Fi 6"},
    19: {"freq_mhz": 2445.0, "wifi_overlap": "Wi-Fi 6"},
    20: {"freq_mhz": 2450.0, "wifi_overlap": "None (Clean Gap 6-11)"},
    21: {"freq_mhz": 2455.0, "wifi_overlap": "Wi-Fi 11"},
    22: {"freq_mhz": 2460.0, "wifi_overlap": "Wi-Fi 11"},
    23: {"freq_mhz": 2465.0, "wifi_overlap": "Wi-Fi 11"},
    24: {"freq_mhz": 2470.0, "wifi_overlap": "Wi-Fi 11"},
    25: {"freq_mhz": 2475.0, "wifi_overlap": "None (Upper Edge)"},
    26: {"freq_mhz": 2480.0, "wifi_overlap": "None (Top Edge / Best)"}
}

WIFI_2G_CHANNELS = {
    1: {"name": "Wi-Fi Ch 1", "center_mhz": 2412.0, "start_mhz": 2401.0, "stop_mhz": 2423.0},
    6: {"name": "Wi-Fi Ch 6", "center_mhz": 2437.0, "start_mhz": 2426.0, "stop_mhz": 2448.0},
    11: {"name": "Wi-Fi Ch 11", "center_mhz": 2462.0, "start_mhz": 2451.0, "stop_mhz": 2473.0}
}

class ShowLinkCRMXEngine(QObject):
    """
    Engine that analyzes 2.4 GHz spectrum sweeps to evaluate Shure ShowLink channels,
    Wi-Fi congestion footprints, and Wireless DMX (CRMX/W-DMX) hopping activity.
    """
    analysis_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_enabled = False
        self.threshold_dbm = -80.0
        self.channel_stats = {} # {ch: {"freq_mhz": float, "peak_dbm": float, "avg_dbm": float, "status": str, "color": str}}
        self.wifi_stats = {} # {wifi_ch: {"peak_dbm": float, "avg_dbm": float, "active": bool}}
        self.crmx_activity_pct = 0.0
        self.best_channels = []
        self._last_time = 0.0

    def set_enabled(self, enabled):
        self.is_enabled = bool(enabled)
        if not self.is_enabled:
            self.reset_data()

    def set_threshold(self, threshold_dbm):
        self.threshold_dbm = float(threshold_dbm)

    def reset_data(self):
        self.channel_stats.clear()
        self.wifi_stats.clear()
        self.crmx_activity_pct = 0.0
        self.best_channels.clear()

    def process_sweep_data(self, freq_hz_array, power_dbm_array):
        """
        Analyzes real incoming 2.4 GHz sweep data.
        """
        if not self.is_enabled or len(freq_hz_array) == 0 or len(power_dbm_array) == 0:
            return

        now = time.time()
        if now - self._last_time < 0.08:
            return
        self._last_time = now

        freq_mhz = np.asarray(freq_hz_array) / 1e6
        power_dbm = np.asarray(power_dbm_array)

        # Ensure sweep covers 2.4 GHz band
        if freq_mhz[-1] < 2400.0 or freq_mhz[0] > 2483.5:
            return

        # 1. Analyze Wi-Fi 1, 6, 11 Power Footprints
        for w_ch, w_info in WIFI_2G_CHANNELS.items():
            mask = (freq_mhz >= w_info["start_mhz"]) & (freq_mhz <= w_info["stop_mhz"])
            if np.any(mask):
                w_pwr = power_dbm[mask]
                w_peak = float(np.max(w_pwr))
                w_avg = float(np.mean(w_pwr))
                self.wifi_stats[w_ch] = {
                    "name": w_info["name"],
                    "peak_dbm": w_peak,
                    "avg_dbm": w_avg,
                    "active": w_peak >= self.threshold_dbm
                }

        # 2. Analyze all 16 ShowLink Channels (Ch 11–26, 2 MHz BW each)
        for ch, s_info in SHOWLINK_CHANNELS.items():
            cf = s_info["freq_mhz"]
            mask = (freq_mhz >= cf - 1.0) & (freq_mhz <= cf + 1.0)
            if not np.any(mask):
                continue

            c_pwr = power_dbm[mask]
            peak_val = float(np.max(c_pwr))
            avg_val = float(np.mean(c_pwr))
            overlap = s_info["wifi_overlap"]

            # Determine Health Status
            if peak_val >= self.threshold_dbm:
                if "Wi-Fi" in overlap:
                    status = "🔴 CONGESTED (Wi-Fi Overlap)"
                    color = "#e53935"
                else:
                    status = "🟡 ACTIVE RF / CRMX Hopping"
                    color = "#fbc02d"
            elif peak_val >= self.threshold_dbm - 10.0:
                status = "🟡 MODERATE NOISE"
                color = "#ffb300"
            else:
                if "None" in overlap:
                    status = "🟢 EXCELLENT (Clean Gap)"
                    color = "#00e676"
                else:
                    status = "🟢 CLEAR (Low Traffic)"
                    color = "#66bb6a"

            self.channel_stats[ch] = {
                "ch": ch,
                "freq_mhz": cf,
                "peak_dbm": peak_val,
                "avg_dbm": avg_val,
                "overlap": overlap,
                "status": status,
                "color": color
            }

        # 3. Detect CRMX / Frequency-Hopping Spread Spectrum Activity
        # CRMX causes uniform intermittent energy bursts across the entire 2.4 GHz band
        in_band_mask = (freq_mhz >= 2402.0) & (freq_mhz <= 2480.0)
        if np.any(in_band_mask):
            band_pwr = power_dbm[in_band_mask]
            active_bins = np.sum(band_pwr >= self.threshold_dbm)
            total_bins = len(band_pwr)
            self.crmx_activity_pct = min(100.0, float((active_bins / max(1, total_bins)) * 100.0 * 2.5))

        # 4. Rank Best ShowLink Channels (Lowest peak power + non-overlapping Wi-Fi preferred)
        ranked = sorted(
            self.channel_stats.values(),
            key=lambda x: (x["peak_dbm"], 0 if "None" in x["overlap"] else 1)
        )
        self.best_channels = [c["ch"] for c in ranked[:3]]

        result = {
            "channels": self.channel_stats,
            "wifi": self.wifi_stats,
            "crmx_activity_pct": self.crmx_activity_pct,
            "best_channels": self.best_channels,
            "threshold_dbm": self.threshold_dbm,
            "timestamp": now
        }
        self.analysis_updated.emit(result)


class ShowlinkMapDialog(QDialog):
    """
    Visual 2.4 GHz ShowLink & Wireless DMX Spectrum Coexistence Map.
    Visualizes Wi-Fi 1/6/11 channel domes, 16 ShowLink Zigbee channels, and CRMX hopping density.
    """
    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("2.4 GHz ShowLink & CRMX / DMX Spectrum Map")
        self.resize(820, 480)
        self.setStyleSheet("background-color: #1a1a1a; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Title & Recommendation Header
        header = QHBoxLayout()
        title = QLabel("<span style='font-size: 13pt; font-weight: bold; color: #00e676;'>Shure ShowLink (2.4 GHz Zigbee) & CRMX Spectrum Map</span>")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Recommendation Banner
        self.rec_banner = QLabel("Recommended ShowLink Channels: Scanning 2.4 GHz Band...")
        self.rec_banner.setStyleSheet("background-color: #004d40; color: #a7ffeb; font-weight: bold; font-size: 10pt; padding: 8px; border-radius: 4px; border: 1px solid #00bfa5;")
        layout.addWidget(self.rec_banner)

        # Wi-Fi 1, 6, 11 Footprint Row
        wifi_group = QGroupBox("Primary 2.4 GHz Wi-Fi Activity (802.11 b/g/n)")
        wifi_group.setStyleSheet("QGroupBox { font-weight: bold; color: #ffb74d; border: 1px solid #444; border-radius: 4px; margin-top: 6px; padding-top: 10px; }")
        wifi_layout = QHBoxLayout(wifi_group)
        self.wifi_labels = {}
        for ch, name in [(1, "Wi-Fi Ch 1 (2412 MHz)"), (6, "Wi-Fi Ch 6 (2437 MHz)"), (11, "Wi-Fi Ch 11 (2462 MHz)")]:
            box = QFrame()
            box.setStyleSheet("background-color: #252525; border: 1px solid #333; border-radius: 4px; padding: 6px;")
            b_layout = QVBoxLayout(box)
            lbl_title = QLabel(f"<b>{name}</b>")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_status = QLabel("Signal: -- dBm | Idle")
            lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_status.setStyleSheet("color: #888888; font-size: 8.5pt;")
            b_layout.addWidget(lbl_title)
            b_layout.addWidget(lbl_status)
            wifi_layout.addWidget(box)
            self.wifi_labels[ch] = lbl_status
        layout.addWidget(wifi_group)

        # ShowLink Channels 11-26 Grid
        sl_group = QGroupBox("ShowLink Zigbee Channels 11 - 26 (IEEE 802.15.4)")
        sl_group.setStyleSheet("QGroupBox { font-weight: bold; color: #80d8ff; border: 1px solid #444; border-radius: 4px; margin-top: 6px; padding-top: 10px; }")
        sl_grid = QGridLayout(sl_group)
        sl_grid.setSpacing(6)
        
        self.sl_cards = {} # ch -> (frame, pwr_lbl, status_lbl)
        for idx, (ch, s_info) in enumerate(SHOWLINK_CHANNELS.items()):
            row = idx // 8
            col = idx % 8
            card = QFrame()
            card.setStyleSheet("background-color: #222; border: 1px solid #383838; border-radius: 3px; padding: 4px;")
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(4, 4, 4, 4)
            c_lay.setSpacing(2)
            
            c_title = QLabel(f"<b>Ch {ch}</b> ({s_info['freq_mhz']:.0f})")
            c_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_title.setStyleSheet("font-size: 8pt; color: #ffffff;")
            
            c_pwr = QLabel("-- dBm")
            c_pwr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_pwr.setStyleSheet("font-size: 8pt; color: #00bcd4; font-weight: bold;")
            
            c_stat = QLabel(s_info['wifi_overlap'].split(' ')[0])
            c_stat.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c_stat.setStyleSheet("font-size: 7pt; color: #888888;")
            
            c_lay.addWidget(c_title)
            c_lay.addWidget(c_pwr)
            c_lay.addWidget(c_stat)
            
            sl_grid.addWidget(card, row, col)
            self.sl_cards[ch] = (card, c_pwr, c_stat)
            
        layout.addWidget(sl_group)

        # Wireless DMX / CRMX Hopping Activity Bar
        crmx_layout = QHBoxLayout()
        crmx_lbl = QLabel("<b>Wireless DMX / CRMX Hopping Density:</b>")
        self.crmx_bar = QProgressBar()
        self.crmx_bar.setRange(0, 100)
        self.crmx_bar.setValue(0)
        self.crmx_bar.setTextVisible(True)
        self.crmx_bar.setFormat("%v% RF Activity")
        self.crmx_bar.setStyleSheet("""
            QProgressBar {
                background-color: #222;
                border: 1px solid #444;
                border-radius: 3px;
                text-align: center;
                color: white;
                font-weight: bold;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00e676, stop:0.6 #ffb300, stop:1 #f44336);
                border-radius: 2px;
            }
        """)
        crmx_layout.addWidget(crmx_lbl)
        crmx_layout.addWidget(self.crmx_bar, 1)
        layout.addLayout(crmx_layout)

        # Close button
        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background-color: #333; color: white; font-weight: bold; padding: 6px 16px; border-radius: 3px;")
        close_btn.clicked.connect(self.close)
        btn_lay.addWidget(close_btn)
        layout.addLayout(btn_lay)

        # Connect engine updates
        self.engine.analysis_updated.connect(self.update_view)

    def update_view(self, data):
        # Update Wi-Fi
        wifi_data = data.get("wifi", {})
        for ch, status_lbl in self.wifi_labels.items():
            if ch in wifi_data:
                w = wifi_data[ch]
                color = "#f44336" if w["active"] else "#66bb6a"
                act_str = "ACTIVE HIGH CONGESTION" if w["active"] else "Low / Clear"
                status_lbl.setText(f"Peak: <b>{w['peak_dbm']:.1f} dBm</b> | {act_str}")
                status_lbl.setStyleSheet(f"color: {color}; font-size: 8.5pt;")

        # Update ShowLink Cards
        channels = data.get("channels", {})
        for ch, (card, pwr_lbl, stat_lbl) in self.sl_cards.items():
            if ch in channels:
                info = channels[ch]
                pwr_lbl.setText(f"{info['peak_dbm']:.1f} dBm")
                stat_lbl.setText(info["overlap"])
                card.setStyleSheet(f"background-color: #222; border: 2px solid {info['color']}; border-radius: 4px; padding: 4px;")

        # Update CRMX
        crmx_pct = int(data.get("crmx_activity_pct", 0))
        self.crmx_bar.setValue(crmx_pct)

        # Update Recommendation Banner
        best_chs = data.get("best_channels", [])
        if best_chs:
            best_str = ", ".join([f"<b>Ch {c} ({SHOWLINK_CHANNELS[c]['freq_mhz']:.0f} MHz)</b>" for c in best_chs])
            self.rec_banner.setText(f"🎯 Recommended Clean ShowLink Channels: {best_str} | Cleanest Gaps outside Wi-Fi 1/6/11")

ShowLinkMapDialog = ShowlinkMapDialog
