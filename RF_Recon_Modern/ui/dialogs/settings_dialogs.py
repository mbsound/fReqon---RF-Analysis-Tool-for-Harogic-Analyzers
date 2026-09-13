"""
settings_dialogs.py - Configuration & Preferences Dialogs for RF Recon Modern.
Provides editors for Quick Band Presets, Launch Defaults, Waterfall History, and Marker Opacity.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QFormLayout, QGroupBox, QDoubleSpinBox, QGridLayout, QWidget,
    QCheckBox, QLineEdit, QSlider
)
from PyQt6.QtCore import Qt

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
    Startup Defaults & Launch State Preference Dialog.
    """
    def __init__(self, region_configs: dict, current_region="North America",
                 sweep_start=470.0, sweep_stop=608.0, sweep_anchors=None,
                 view_start=470.0, view_stop=608.0, view_anchors=None,
                 link_view=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Launch Settings & Startup Defaults")
        self.setModal(True)
        self.resize(600, 480)
        
        self.region_configs = region_configs
        self.current_region = current_region
        self._sweep_anchors = set(tuple(a) for a in sweep_anchors) if sweep_anchors else set()
        self._view_anchors = set(tuple(a) for a in view_anchors) if view_anchors else set()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 1. Startup Region
        reg_group = QGroupBox("Startup Default Region")
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
