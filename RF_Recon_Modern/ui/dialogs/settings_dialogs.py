"""
settings_dialogs.py - Configuration & Preferences Dialogs for RF Recon Modern.
Provides editors for Quick Band Presets, Launch Defaults, Waterfall History, and Marker Opacity.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QFormLayout, QGroupBox, QDoubleSpinBox, QGridLayout, QCheckBox,
    QLineEdit, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal

class WaterfallSettingsDialog(QDialog):
    """
    Spectrogram / Waterfall History Depth Configuration.
    """
    def __init__(self, current_depth: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spectrogram History Settings")
        self.setModal(True)
        self.resize(320, 140)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        form = QFormLayout()
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(10, 2000)
        self.depth_spin.setValue(current_depth)
        self.depth_spin.setSuffix(" Sweeps")
        self.depth_spin.setSingleStep(25)
        form.addRow("History Buffer Depth:", self.depth_spin)
        layout.addLayout(form)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("primaryActionBtn")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
    def get_settings(self) -> int:
        return self.depth_spin.value()


class QuickSettingsDialog(QDialog):
    """
    Quick Band Preset Editor for adding, editing, and reordering regional frequency presets.
    """
    def __init__(self, region_name: str, buttons_data: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Band Presets - {region_name}")
        self.setModal(True)
        self.resize(480, 420)
        
        self.buttons_data = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        
        grid = QGridLayout()
        grid.addWidget(QLabel("Preset Name"), 0, 0)
        grid.addWidget(QLabel("Start Frequency"), 0, 1)
        grid.addWidget(QLabel("Stop Frequency"), 0, 2)
        
        self.rows = []
        num_rows = max(len(buttons_data), 10)
        for i in range(num_rows):
            data = buttons_data[i] if i < len(buttons_data) else {"name": "", "start": 470.0, "stop": 608.0}
            name_edit = QLineEdit(data.get("name", ""))
            
            start_spin = QDoubleSpinBox()
            start_spin.setRange(0.1, 20000.0)
            start_spin.setDecimals(1)
            start_spin.setValue(float(data.get("start", 470.0)))
            start_spin.setSuffix(" MHz")
            
            stop_spin = QDoubleSpinBox()
            stop_spin.setRange(0.1, 20000.0)
            stop_spin.setDecimals(1)
            stop_spin.setValue(float(data.get("stop", 608.0)))
            stop_spin.setSuffix(" MHz")
            
            grid.addWidget(name_edit, i + 1, 0)
            grid.addWidget(start_spin, i + 1, 1)
            grid.addWidget(stop_spin, i + 1, 2)
            self.rows.append((name_edit, start_spin, stop_spin))
            
        layout.addLayout(grid)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Save Presets")
        ok_btn.setObjectName("primaryActionBtn")
        ok_btn.clicked.connect(self.accept_changes)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
    def accept_changes(self):
        self.buttons_data = []
        for name_edit, start_spin, stop_spin in self.rows:
            name = name_edit.text().strip()
            if name:
                self.buttons_data.append({
                    "name": name,
                    "start": start_spin.value(),
                    "stop": stop_spin.value()
                })
        self.accept()


class LaunchSettingsDialog(QDialog):
    """
    Startup Defaults & Launch State Preference Dialog, and the spectrum export.
    """
    exportRequested = pyqtSignal(list)      # names of the traces to export as CSV

    def __init__(self, region_configs: dict, current_region="North America",
                 sweep_start=470.0, sweep_stop=608.0, sweep_anchors=None,
                 view_start=470.0, view_stop=608.0, view_anchors=None,
                 link_view=True, export_traces=None, parent=None):
        """export_traces: [(trace name, label, why it cannot be exported or "")], in the order shown."""
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(600, 600)
        
        self.region_configs = region_configs
        self.current_region = current_region
        self._sweep_anchors = set(tuple(a) for a in sweep_anchors) if sweep_anchors else set()
        self._view_anchors = set(tuple(a) for a in view_anchors) if view_anchors else set()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 1. Startup Region
        reg_group = QGroupBox("Region")
        reg_group.setToolTip("The region whose TV channels, band presets and transmitter lookup are used, "
                             "now and at startup")
        reg_layout = QVBoxLayout(reg_group)
        self.region_combo = QComboBox()
        self.region_combo.addItems(list(region_configs.keys()))
        idx = self.region_combo.findText(current_region)
        if idx >= 0:
            self.region_combo.setCurrentIndex(idx)
        reg_layout.addWidget(self.region_combo)
        layout.addWidget(reg_group)
        
        # 2. Startup Sweep Frequencies
        freq_group = QGroupBox("Startup Hardware Sweep Range")
        freq_form = QFormLayout(freq_group)
        
        self.sweep_start_spin = QDoubleSpinBox()
        self.sweep_start_spin.setRange(0.1, 20000.0)
        self.sweep_start_spin.setDecimals(1)
        self.sweep_start_spin.setValue(float(sweep_start))
        self.sweep_start_spin.setSuffix(" MHz")
        
        self.sweep_stop_spin = QDoubleSpinBox()
        self.sweep_stop_spin.setRange(0.1, 20000.0)
        self.sweep_stop_spin.setDecimals(1)
        self.sweep_stop_spin.setValue(float(sweep_stop))
        self.sweep_stop_spin.setSuffix(" MHz")
        
        freq_form.addRow("Sweep Start:", self.sweep_start_spin)
        freq_form.addRow("Sweep Stop:", self.sweep_stop_spin)
        layout.addWidget(freq_group)
        
        # 3. View Link
        view_group = QGroupBox("Startup Viewport Settings")
        view_layout = QVBoxLayout(view_group)
        self.link_view_cb = QCheckBox("Automatically link Viewport Span to Hardware Sweep on startup")
        self.link_view_cb.setChecked(link_view)
        view_layout.addWidget(self.link_view_cb)
        layout.addWidget(view_group)

        # 4. Spectrum export (acts at once; it is not one of the saved preferences)
        exp_group = QGroupBox("Export Spectrum to CSV")
        exp_group.setToolTip("The traces as they are now, in the layout SAStudio4 exports: four header lines, then\n"
                             "one \"frequency in Hz, level in dBm\" row per point. One file per trace.\n"
                             "In Soundbase, import them with the SAN-60 importer.")
        exp_layout = QVBoxLayout(exp_group)
        row = QHBoxLayout()
        row.setSpacing(18)
        self.export_checks = {}
        for name, label, why_not in (export_traces or []):
            cb = QCheckBox(label)
            cb.setEnabled(not why_not)
            cb.setChecked(not why_not)
            cb.setToolTip(why_not or f"Export the {label} trace")
            cb.toggled.connect(self._sync_export_btn)
            self.export_checks[name] = cb
            row.addWidget(cb)
        row.addStretch()
        self.export_btn = QPushButton("Export CSV…")
        self.export_btn.clicked.connect(lambda: self.exportRequested.emit(self.export_selection()))
        row.addWidget(self.export_btn)
        exp_layout.addLayout(row)
        self.export_note = QLabel("One file per trace, named fReqon_<date>_<time>_<trace>.csv, "
                                  "for example fReqon_20261005_155043_MaxHold.csv.")
        self.export_note.setWordWrap(True)
        self.export_note.setStyleSheet("color: #8b949e; font-size: 11px;")
        exp_layout.addWidget(self.export_note)
        # (Stays put: the line above is replaced by the result of an export)
        self.export_hint = QLabel("To bring a file into Soundbase, use Soundbase's <b>SAN-60</b> importer: "
                                  "the files are in that analyzer's export layout.")
        self.export_hint.setWordWrap(True)
        self.export_hint.setTextFormat(Qt.TextFormat.RichText)
        self.export_hint.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        exp_layout.addWidget(self.export_hint)
        layout.addWidget(exp_group)
        self._sync_export_btn()
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Preferences")
        save_btn.setObjectName("primaryActionBtn")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def export_selection(self) -> list:
        return [name for name, cb in self.export_checks.items() if cb.isEnabled() and cb.isChecked()]

    def _sync_export_btn(self, *_):
        self.export_btn.setEnabled(bool(self.export_selection()))

    def set_export_result(self, text: str, ok: bool = True):
        """Say under the export controls what was written, or why nothing was."""
        self.export_note.setText(text)
        self.export_note.setStyleSheet(f"color: {'#10b981' if ok else '#f59e0b'}; font-size: 11px;")

    def get_settings(self):
        return {
            "default_region": self.region_combo.currentText(),
            "sweep_start": self.sweep_start_spin.value(),
            "sweep_stop": self.sweep_stop_spin.value(),
            "link_view": self.link_view_cb.isChecked()
        }


class MarkerSettingsDialog(QDialog):
    """
    Marker Opacity & Display Preferences.
    """
    def __init__(self, current_opacity: float = 0.8, show_labels: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Marker Display Preferences")
        self.setModal(True)
        self.resize(360, 180)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        form = QFormLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(current_opacity * 100))
        form.addRow("Marker Opacity:", self.opacity_slider)
        
        self.labels_cb = QCheckBox("Show Channel Number Labels")
        self.labels_cb.setChecked(show_labels)
        form.addRow(self.labels_cb)
        
        layout.addLayout(form)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryActionBtn")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    def get_opacity(self) -> float:
        return self.opacity_slider.value() / 100.0

    def get_show_labels(self) -> bool:
        return self.labels_cb.isChecked()
