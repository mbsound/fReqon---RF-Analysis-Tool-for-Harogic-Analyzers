"""
showlink_crmx_analyzer.py - 2.4 GHz ShowLink & Wireless DMX (CRMX / W-DMX) coexistence engine.
Per ShowLink (802.15.4) channel: how busy, with what (Wi-Fi, hopping, wideband), and
how the channel in use is doing; all 13 Wi-Fi channels; airtime from zero span.
The analysis itself is core/band24.py.
"""

import time
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QFrame, QProgressBar
)

from . import band24

# ShowLink (802.15.4 / Zigbee) channels 11-26 and which Wi-Fi channels of the usual
# three (1, 6, 11) sit on top of each; the monitor itself looks at all 13 Wi-Fi channels
def _overlap_label(cf):
    for n in (1, 6, 11):
        if abs(band24.WIFI_CHANNELS[n] - cf) < 11.0:
            return f"Wi-Fi {n}"
    return {2425.0: "None (Clean Gap 1-6)", 2450.0: "None (Clean Gap 6-11)",
            2475.0: "None (Upper Edge)", 2480.0: "None (Top Edge / Best)"}.get(cf, "None")


SHOWLINK_CHANNELS = {k: {"freq_mhz": cf, "wifi_overlap": _overlap_label(cf)} for k, cf in band24.ZIGBEE_CHANNELS.items()}

WIFI_2G_CHANNELS = {n: {"name": f"Wi-Fi Ch {n}", "center_mhz": cf, "start_mhz": cf - 10.0, "stop_mhz": cf + 10.0}
                    for n, cf in band24.WIFI_CHANNELS.items()}


class ShowLinkCRMXEngine(QObject):
    """
    What is on the 2.4 GHz band (core/band24.py): per ShowLink channel how often it
    is busy and with what (Wi-Fi, hopping, wideband, Zigbee), per Wi-Fi channel how
    busy it is, how the chosen ShowLink channel is doing, and the airtime of a
    channel from a zero-span capture.
    """
    analysis_updated = pyqtSignal(dict)

    WINDOW_SWEEPS = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_enabled = False
        self.threshold_dbm = -80.0
        self.my_channel = None               # the ShowLink channel to judge; None: the one seen on the air
        self.detected_channel = None         # where Zigbee-shaped traffic is seen most
        self.monitor = band24.Band24Monitor(self.WINDOW_SWEEPS)
        self.channel_stats = {}              # {ch: {...}} as the panel and map show them
        self.wifi_stats = {}                 # {n: {"name", "center_mhz", "peak_dbm", "busy_pct", "active"}}
        self.mix = {}
        self.assessment = None
        self.feasibility = {"clear": [], "verdict": "UNKNOWN", "wifi_in_use": [], "disable": []}
        self.survey_text = ""
        self.airtime = {}                    # {ch: {"busy_pct", "bursts", "median_us", "longest_us", "time"}}
        self.crmx_activity_pct = 0.0
        self.best_channels = []
        self._last_time = 0.0

    def set_enabled(self, enabled):
        self.is_enabled = bool(enabled)
        if not self.is_enabled:
            self.reset_data()

    def set_threshold(self, threshold_dbm):
        self.threshold_dbm = float(threshold_dbm)

    def set_my_channel(self, ch):
        """ch: a ShowLink channel 11-26 to judge, or None / 0 for the one detected on the air."""
        self.my_channel = int(ch) if ch else None
        if self.monitor.sweeps:
            self._publish(time.time())

    @property
    def judged_channel(self):
        return self.my_channel or self.detected_channel

    def reset_data(self):
        self.monitor.reset()
        self.channel_stats.clear()
        self.wifi_stats.clear()
        self.airtime.clear()
        self.mix = {}
        self.assessment = None
        self.crmx_activity_pct = 0.0
        self.best_channels.clear()

    def process_sweep_data(self, freq_hz_array, power_dbm_array):
        if not self.is_enabled or len(freq_hz_array) == 0 or len(power_dbm_array) == 0:
            return
        now = time.time()
        if now - self._last_time < 0.08:
            return
        self._last_time = now
        if self.monitor.update(np.asarray(freq_hz_array) / 1e6, power_dbm_array, self.threshold_dbm) is None:
            return
        self._publish(now)

    def process_zero_span(self, center_freq_hz, time_ns, power_dbm):
        """Airtime of the ShowLink channel a zero-span capture was taken on; None if off any."""
        ch = min(band24.ZIGBEE_CHANNELS, key=lambda c: abs(band24.ZIGBEE_CHANNELS[c] * 1e6 - center_freq_hz))
        if abs(band24.ZIGBEE_CHANNELS[ch] * 1e6 - center_freq_hz) > 1.5e6:
            return None
        a = band24.airtime(np.asarray(time_ns, dtype=float) * 1e-9, power_dbm, self.threshold_dbm)
        if a is None:
            return None
        prev = self.airtime.get(ch)
        if prev and time.time() - prev["time"] < 10.0:
            # Several captures in a row: average the airtime, keep the longest burst
            n = prev["captures"] + 1
            a["busy_pct"] = (prev["busy_pct"] * prev["captures"] + a["busy_pct"]) / n
            a["bursts"] += prev["bursts"]
            a["longest_us"] = max(a["longest_us"], prev["longest_us"])
            a["captures"] = n
        else:
            a["captures"] = 1
        a["time"] = time.time()
        a["ch"] = ch
        self.airtime[ch] = a
        self._publish(time.time())
        return a

    def _publish(self, now):
        s = self.monitor.summary()
        self.mix = s["mix"]
        self.channel_stats = {}
        for ch, z in s["zigbee"].items():
            busy, other = z["busy_pct"], z["interference_pct"]
            kinds = {k: v for k, v in z["kinds"].items() if v >= 2.0}
            what = ", ".join(band24.KIND_LABEL[k] for k, _v in sorted(kinds.items(), key=lambda kv: -kv[1]))
            if z["kinds"].get("continuous", 0) + z["kinds"].get("wide", 0) >= 20.0:
                status, color = f"🔴 WIDEBAND ENERGY {busy:.0f}%", "#e53935"
            elif other >= 35.0:
                status, color = f"🔴 CONGESTED {other:.0f}% ({what})", "#e53935"
            elif other >= 10.0:
                status, color = f"🟡 MODERATE {other:.0f}% ({what})", "#ffb300"
            elif busy >= 10.0:
                status, color = f"🔵 ZIGBEE {busy:.0f}%", "#38bdf8"
            elif "None" in SHOWLINK_CHANNELS[ch]["wifi_overlap"]:
                status, color = f"🟢 EXCELLENT {busy:.0f}%", "#00e676"
            else:
                status, color = f"🟢 CLEAR {busy:.0f}%", "#66bb6a"
            self.channel_stats[ch] = {
                "ch": ch, "freq_mhz": z["freq_mhz"], "peak_dbm": z["peak_dbm"], "avg_dbm": z["mean_peak_dbm"],
                "busy_pct": busy, "interference_pct": other, "kinds": z["kinds"], "what": what,
                "wifi_channels": z["wifi"], "overlap": SHOWLINK_CHANNELS[ch]["wifi_overlap"],
                "status": status, "color": color, "airtime": self.airtime.get(ch),
            }
        self.wifi_stats = {n: {"name": f"Wi-Fi Ch {n}", "center_mhz": w["center_mhz"], "peak_dbm": w["peak_dbm"],
                               "avg_dbm": w["peak_dbm"], "busy_pct": w["busy_pct"], "active": w["busy_pct"] >= 10.0}
                           for n, w in s["wifi"].items()}
        self.crmx_activity_pct = s["mix"].get("hop", 0.0)
        self.detected_channel = band24.showlink_channel(s)
        judged = self.judged_channel
        self.assessment = band24.assess(s, judged) if judged else None
        self.feasibility = band24.feasibility(s)
        self.survey_text = band24.survey_text(s, self.feasibility, self.detected_channel)
        self.best_channels = (list(self.assessment["alternatives"]) if self.assessment
                              else [c for c, _s in sorted(s["zigbee"].items(), key=lambda kv: kv[1]["busy_pct"])][:3])
        self.analysis_updated.emit({
            "channels": self.channel_stats, "wifi": self.wifi_stats, "mix": self.mix,
            "my_channel": judged, "detected_channel": self.detected_channel, "assessment": self.assessment,
            "feasibility": self.feasibility, "survey_text": self.survey_text,
            "crmx_activity_pct": self.crmx_activity_pct, "best_channels": self.best_channels,
            "sweeps": s["sweeps"], "threshold_dbm": self.threshold_dbm, "timestamp": now,
        })


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
