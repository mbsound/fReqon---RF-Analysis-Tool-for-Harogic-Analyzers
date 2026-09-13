"""
dect_analyzer.py - DECT & Riedel Bolero Intercom Capacity & Transceiver Analysis Engine
Provides real-time duty cycle time-occupancy, antenna beacon detection, beltpack transceiver estimation,
channel congestion ratings, and actionable clean channel recommendations across US DECT 6.0, EU DECT, and 2.4 GHz Bolero.
"""

import time
import numpy as np
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QGridLayout, QFrame, QWidget, QScrollArea, QProgressBar
)
from PyQt6.QtGui import QColor, QBrush, QPen, QPainter, QFont

# DECT Standard Carrier Frequencies & Band Definitions
DECT_BANDS = {
    "US DECT 6.0 (1920-1930 MHz)": {
        "start_mhz": 1920.0,
        "stop_mhz": 1930.0,
        "center_mhz": 1925.0,
        "span_mhz": 10.0,
        "channel_spacing_mhz": 1.728,
        "carriers": [
            {"ch": 0, "freq_mhz": 1928.448, "name": "US Ch 0 (1928.45 MHz)"},
            {"ch": 1, "freq_mhz": 1926.720, "name": "US Ch 1 (1926.72 MHz)"},
            {"ch": 2, "freq_mhz": 1925.000, "name": "US Ch 2 (1925.00 MHz)"},
            {"ch": 3, "freq_mhz": 1923.264, "name": "US Ch 3 (1923.26 MHz)"},
            {"ch": 4, "freq_mhz": 1921.536, "name": "US Ch 4 (1921.54 MHz)"}
        ]
    },
    "EU DECT (1880-1900 MHz)": {
        "start_mhz": 1880.0,
        "stop_mhz": 1900.0,
        "center_mhz": 1890.0,
        "span_mhz": 20.0,
        "channel_spacing_mhz": 1.728,
        "carriers": [
            {"ch": 0, "freq_mhz": 1897.344, "name": "EU Ch 0 (1897.34 MHz)"},
            {"ch": 1, "freq_mhz": 1895.616, "name": "EU Ch 1 (1895.62 MHz)"},
            {"ch": 2, "freq_mhz": 1893.888, "name": "EU Ch 2 (1893.89 MHz)"},
            {"ch": 3, "freq_mhz": 1892.160, "name": "EU Ch 3 (1892.16 MHz)"},
            {"ch": 4, "freq_mhz": 1890.432, "name": "EU Ch 4 (1890.43 MHz)"},
            {"ch": 5, "freq_mhz": 1888.704, "name": "EU Ch 5 (1888.70 MHz)"},
            {"ch": 6, "freq_mhz": 1886.976, "name": "EU Ch 6 (1886.98 MHz)"},
            {"ch": 7, "freq_mhz": 1885.248, "name": "EU Ch 7 (1885.25 MHz)"},
            {"ch": 8, "freq_mhz": 1883.520, "name": "EU Ch 8 (1883.52 MHz)"},
            {"ch": 9, "freq_mhz": 1881.792, "name": "EU Ch 9 (1881.79 MHz)"}
        ]
    },
    "2.4 GHz Bolero (2400-2483.5 MHz)": {
        "start_mhz": 2400.0,
        "stop_mhz": 2483.5,
        "center_mhz": 2441.75,
        "span_mhz": 83.5,
        "channel_spacing_mhz": 2.0,
        "carriers": [
            {"ch": i, "freq_mhz": 2404.0 + i * 4.0, "name": f"2.4G Ch {i} ({2404.0 + i * 4.0:.1f} MHz)"}
            for i in range(20)
        ]
    }
}

class DECTAnalyzerEngine(QObject):
    """
    Engine that analyzes live RF sweeps in DECT bands, tracks carrier duty cycle & time occupancy,
    estimates active antenna base stations & beltpack count, and provides actionable recommendations.
    """
    analysis_updated = pyqtSignal(dict) # Emits full analysis result dictionary

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_band_name = "US DECT 6.0 (1920-1930 MHz)"
        self.threshold_dbm = -85.0
        self.is_enabled = False
        
        # State tracking
        self.carrier_stats = {} # {cf: {"ch", "name", "peak_dbm", "avg_dbm", "duty_cycle_pct", "status", "color", "antennas", "beltpacks"}}
        self.duty_cycle_history = {} # {cf: deque(maxlen=40)} of bool (is_active in sweep)
        self.smoothed_rssi = {} # {cf: float} EMA smoothed RSSI
        self.slot_matrix = np.full((20, 24), -120.0) # Power per [carrier, timeslot]
        self.total_antennas_est = 0
        self.total_beltpacks_est = 0
        self.band_load_pct = 0.0
        self.recommended_carriers = []
        self._last_analysis_time = 0.0

    def set_band(self, band_name):
        if band_name in DECT_BANDS:
            self.active_band_name = band_name
            self.reset_data()

    def set_threshold(self, thresh_dbm):
        self.threshold_dbm = float(thresh_dbm)

    def set_enabled(self, enabled):
        self.is_enabled = bool(enabled)
        if not self.is_enabled:
            self.reset_data()

    def reset_data(self):
        self.carrier_stats.clear()
        self.duty_cycle_history.clear()
        self.smoothed_rssi.clear()
        self.total_antennas_est = 0
        self.total_beltpacks_est = 0
        self.band_load_pct = 0.0
        self.recommended_carriers.clear()
        band_info = DECT_BANDS.get(self.active_band_name, DECT_BANDS["US DECT 6.0 (1920-1930 MHz)"])
        num_carriers = len(band_info["carriers"])
        self.slot_matrix = np.full((max(num_carriers, 20), 24), -120.0)

    def process_sweep_data(self, freq_hz_array, power_dbm_array):
        """
        Processes real incoming RF sweep data from the spectrum analyzer.
        Calculates time-integrated duty cycle, estimates transceiver counts, and generates actionable metrics.
        """
        if not self.is_enabled or len(freq_hz_array) == 0 or len(power_dbm_array) == 0:
            return

        now = time.time()
        # Rate-limit analysis updates to 15 Hz max for smooth UI
        if now - self._last_analysis_time < 0.06:
            return
        self._last_analysis_time = now

        band_info = DECT_BANDS.get(self.active_band_name)
        if not band_info:
            return

        freq_mhz = np.asarray(freq_hz_array) / 1e6
        power_dbm = np.asarray(power_dbm_array)

        # Check if the sweep covers the DECT band
        band_start = band_info["start_mhz"]
        band_stop = band_info["stop_mhz"]
        if freq_mhz[-1] < band_start or freq_mhz[0] > band_stop:
            return

        carriers = band_info["carriers"]
        spacing = band_info["channel_spacing_mhz"]
        half_bw = spacing / 2.0

        total_antennas = 0
        total_beltpacks = 0
        sum_duty_cycle = 0.0

        for idx, c in enumerate(carriers):
            cf = c["freq_mhz"]
            ch_num = c["ch"]

            # Initialize history deques
            if cf not in self.duty_cycle_history:
                self.duty_cycle_history[cf] = deque(maxlen=40) # ~2.5s sliding integration window
                self.smoothed_rssi[cf] = -120.0

            # Slice real measured data within carrier bandwidth
            mask = (freq_mhz >= cf - half_bw) & (freq_mhz <= cf + half_bw)
            if not np.any(mask):
                continue

            c_powers = power_dbm[mask]
            peak_pwr = float(np.max(c_powers))
            avg_pwr = float(np.mean(c_powers))
            is_active_burst = peak_pwr >= self.threshold_dbm

            # Update sliding window for Duty Cycle measurement
            self.duty_cycle_history[cf].append(1 if is_active_burst else 0)
            hist = self.duty_cycle_history[cf]
            duty_cycle_pct = (sum(hist) / len(hist)) * 100.0
            sum_duty_cycle += duty_cycle_pct

            # Exponential Moving Average (EMA) for RSSI stabilization (eliminates flickering)
            if is_active_burst:
                if self.smoothed_rssi[cf] < -110.0:
                    self.smoothed_rssi[cf] = peak_pwr
                else:
                    self.smoothed_rssi[cf] = 0.7 * peak_pwr + 0.3 * self.smoothed_rssi[cf]
            else:
                self.smoothed_rssi[cf] = max(-120.0, self.smoothed_rssi[cf] - 1.5) # Gentle decay

            smoothed_pwr = self.smoothed_rssi[cf]

            # ----------------------------------------------------
            # Transceiver Estimation & Channel Health Calculation
            # ----------------------------------------------------
            # In DECT TDMA:
            # - Downlink Beacon (1 Antenna idle): ~4.17% to 8.33% duty cycle
            # - Each active duplex audio call: +8.33% duty cycle (1 DL slot + 1 UL slot)
            if duty_cycle_pct < 2.5:
                # Carrier Clean / Idle
                antennas = 0
                beltpacks = 0
                status = "🟢 CLEAR (0% Load)"
                color = "#00e676"
            elif 2.5 <= duty_cycle_pct <= 12.0:
                # Beacon only (1 Antenna active, idle audio)
                antennas = 1
                beltpacks = 0
                status = f"🟡 BEACON ONLY (1 Ant | {duty_cycle_pct:.0f}% Load)"
                color = "#ffb300"
            elif 12.0 < duty_cycle_pct <= 45.0:
                # Active conversation traffic
                antennas = 1
                # Each voice stream adds ~8.33% duty cycle beyond beacon
                beltpacks = max(1, int(round((duty_cycle_pct - 6.0) / 8.33)))
                status = f"🔵 ACTIVE TRAFFIC (1 Ant + {beltpacks} Packs | {duty_cycle_pct:.0f}%)"
                color = "#00bcd4"
            elif 45.0 < duty_cycle_pct <= 85.0:
                # Heavy channel loading / multiple antennas on carrier
                antennas = max(1, int(round(duty_cycle_pct / 40.0)))
                beltpacks = max(4, int(round((duty_cycle_pct - 8.0) / 8.33)))
                status = f"🔴 HEAVY LOAD ({antennas} Ant + {beltpacks} Packs | {duty_cycle_pct:.0f}%)"
                color = "#e53935"
            else:
                # Continuous RF energy (> 85% duty cycle) -> Non-DECT jammer or interference!
                antennas = 0
                beltpacks = 0
                status = f"⚠️ CONTINUOUS INTERFERENCE ({duty_cycle_pct:.0f}% Jam)"
                color = "#ff1744"

            total_antennas += antennas
            total_beltpacks += beltpacks

            self.carrier_stats[cf] = {
                "ch": ch_num,
                "name": c["name"],
                "freq_mhz": cf,
                "peak_dbm": peak_pwr,
                "smoothed_dbm": smoothed_pwr,
                "avg_dbm": avg_pwr,
                "duty_cycle_pct": duty_cycle_pct,
                "antennas": antennas,
                "beltpacks": beltpacks,
                "status": status,
                "color": color,
                "active": duty_cycle_pct >= 2.5
            }

            # Update Slot Matrix visualization
            if idx < self.slot_matrix.shape[0]:
                if duty_cycle_pct >= 2.5:
                    self.slot_matrix[idx, :] = smoothed_pwr
                else:
                    self.slot_matrix[idx, :] = np.maximum(self.slot_matrix[idx, :] - 5.0, -120.0)

        # Aggregate Network Metrics
        self.total_antennas_est = total_antennas
        self.total_beltpacks_est = total_beltpacks
        self.band_load_pct = sum_duty_cycle / max(1, len(carriers))

        # Rank Cleanest Carriers for Bolero Expansion
        sorted_clean = sorted(
            self.carrier_stats.values(),
            key=lambda x: (x["duty_cycle_pct"], x["smoothed_dbm"])
        )
        self.recommended_carriers = [
            c["name"] for c in sorted_clean if c["duty_cycle_pct"] < 5.0
        ]

        result = {
            "band_name": self.active_band_name,
            "carriers": self.carrier_stats,
            "slot_matrix": self.slot_matrix.copy(),
            "total_antennas": self.total_antennas_est,
            "total_beltpacks": self.total_beltpacks_est,
            "band_load_pct": self.band_load_pct,
            "recommended_carriers": self.recommended_carriers,
            "threshold_dbm": self.threshold_dbm,
            "timestamp": now
        }
        self.analysis_updated.emit(result)


class TDMATimeslotDialog(QDialog):
    """
    Actionable DECT & Riedel Bolero Intercom Capacity & Transceiver Dashboard.
    Visualizes real-time carrier duty cycle, active transceivers, and clean channel guidance.
    """
    def __init__(self, analyzer_engine, parent=None):
        super().__init__(parent)
        self.analyzer_engine = analyzer_engine
        self.setWindowTitle("DECT & Riedel Bolero Intercom Capacity Inspector")
        self.resize(920, 560)
        self.setStyleSheet("background-color: #181818; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Top Actionable Summary Dashboard
        self.dashboard_frame = QFrame()
        self.dashboard_frame.setStyleSheet("background-color: #222222; border: 1px solid #333333; border-radius: 6px; padding: 6px;")
        dash_layout = QVBoxLayout(self.dashboard_frame)

        self.title_label = QLabel("📻 DECT / Riedel Bolero Network Capacity & Transceiver Estimator")
        self.title_label.setStyleSheet("font-size: 11pt; font-weight: bold; color: #00bcd4;")
        dash_layout.addWidget(self.title_label)

        self.metrics_label = QLabel("Estimated Antennas: 0 | Estimated Beltpacks: 0 | Band Load: 0% (CLEAN)")
        self.metrics_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #ffffff;")
        dash_layout.addWidget(self.metrics_label)

        self.rec_label = QLabel("✨ Recommended Clean Channels for Expansion: Scanning Band...")
        self.rec_label.setStyleSheet("font-size: 9pt; color: #00e676; font-weight: bold;")
        dash_layout.addWidget(self.rec_label)

        layout.addWidget(self.dashboard_frame)

        # Carrier Capacity & Duty Cycle Table
        self.carrier_table = QTableWidget(0, 6)
        self.carrier_table.setHorizontalHeaderLabels([
            "Carrier", "Freq (MHz)", "RSSI (Peak)", "Duty Cycle (Occupancy)", "Estimated Transceivers", "Status"
        ])
        self.carrier_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.carrier_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.carrier_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.carrier_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.carrier_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.carrier_table.horizontalHeader().setStretchLastSection(True)
        self.carrier_table.verticalHeader().setVisible(False)
        self.carrier_table.setStyleSheet("background-color: #1e1e1e; gridline-color: #333333;")
        self.carrier_table.setMinimumHeight(240)
        layout.addWidget(self.carrier_table, 1)

        # Bottom Info Bar
        info_label = QLabel("💡 Note: Carrier duty cycle is calculated from real temporal RF energy integration. Beacon signals occupy ~4-8%, and active voice streams add ~8% per call.")
        info_label.setStyleSheet("font-size: 8pt; color: #888888;")
        layout.addWidget(info_label)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background-color: #333333; color: white; padding: 6px 18px; font-weight: bold; border-radius: 3px;")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        # Connect engine signal
        self.analyzer_engine.analysis_updated.connect(self.update_dashboard)

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'analyzer_engine') and self.analyzer_engine.carrier_stats:
            self.update_dashboard({
                "band_name": self.analyzer_engine.active_band_name,
                "carriers": self.analyzer_engine.carrier_stats,
                "total_antennas": self.analyzer_engine.total_antennas_est,
                "total_beltpacks": self.analyzer_engine.total_beltpacks_est,
                "band_load_pct": self.analyzer_engine.band_load_pct,
                "recommended_carriers": self.analyzer_engine.recommended_carriers
            })

    def update_dashboard(self, data):
        carriers = data.get("carriers", {})
        band_name = data.get("band_name", "")
        antennas = data.get("total_antennas", 0)
        beltpacks = data.get("total_beltpacks", 0)
        band_load = data.get("band_load_pct", 0.0)
        rec_channels = data.get("recommended_carriers", [])

        # Update Top Dashboard
        load_state = "CLEAN" if band_load < 5.0 else ("LIGHT" if band_load < 20.0 else ("MODERATE" if band_load < 45.0 else "CONGESTED"))
        self.metrics_label.setText(
            f"📻 Active Antennas: {antennas} | 🎙️ Active Beltpacks: ~{beltpacks} | 📊 Band Load: {band_load:.1f}% ({load_state})"
        )

        if rec_channels:
            clean_str = ", ".join(rec_channels[:3])
            self.rec_label.setText(f"✨ Recommended Clean Channels for Bolero Expansion: {clean_str}")
        else:
            self.rec_label.setText("⚠️ All DECT channels are currently congested or active.")

        # Update Table
        self.carrier_table.setRowCount(0)
        for cf, c in sorted(carriers.items(), key=lambda x: x[1]["ch"]):
            row = self.carrier_table.rowCount()
            self.carrier_table.insertRow(row)

            ch_item = QTableWidgetItem(f"Ch {c['ch']}")
            freq_item = QTableWidgetItem(f"{c['freq_mhz']:.2f} MHz")
            rssi_item = QTableWidgetItem(f"{c['smoothed_dbm']:.1f} dBm" if c['active'] else "—")
            
            # Progress bar for duty cycle
            duty_widget = QWidget()
            d_layout = QHBoxLayout(duty_widget)
            d_layout.setContentsMargins(4, 2, 4, 2)
            pbar = QProgressBar()
            pbar.setRange(0, 100)
            pbar.setValue(int(c["duty_cycle_pct"]))
            pbar.setFormat(f"{c['duty_cycle_pct']:.0f}%")
            pbar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pbar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {c['color']}; }} QProgressBar {{ text-align: center; color: white; background-color: #2b2b2b; border-radius: 2px; }}")
            d_layout.addWidget(pbar)

            tx_str = f"{c['antennas']} Ant, {c['beltpacks']} Packs" if c['active'] else "None"
            tx_item = QTableWidgetItem(tx_str)
            status_item = QTableWidgetItem(c["status"])
            status_item.setForeground(QColor(c["color"]))

            self.carrier_table.setItem(row, 0, ch_item)
            self.carrier_table.setItem(row, 1, freq_item)
            self.carrier_table.setItem(row, 2, rssi_item)
            self.carrier_table.setCellWidget(row, 3, duty_widget)
            self.carrier_table.setItem(row, 4, tx_item)
            self.carrier_table.setItem(row, 5, status_item)
