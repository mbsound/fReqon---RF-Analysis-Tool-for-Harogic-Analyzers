import os
import sys

content = """
from PyQt6.QtWidgets import QTabWidget, QGridLayout, QLineEdit, QDoubleSpinBox, QWidget

class SettingsDialog(QDialog):
    def __init__(self, current_region, available_regions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 300)
        
        self.selected_region = current_region
        
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.region_tab = QWidget()
        region_layout = QFormLayout(self.region_tab)
        
        self.region_combo = QComboBox()
        self.region_combo.addItems(available_regions)
        self.region_combo.setCurrentText(current_region)
        region_layout.addRow("Active Region:", self.region_combo)
        
        self.tabs.addTab(self.region_tab, "Region")
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
    def accept_changes(self):
        self.selected_region = self.region_combo.currentText()
        self.accept()

class QuickSettingsDialog(QDialog):
    def __init__(self, region_name, buttons_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Quick Settings ({region_name})")
        self.setModal(True)
        
        self.buttons_data = [] # List of dicts
        
        layout = QVBoxLayout(self)
        
        grid = QGridLayout()
        grid.addWidget(QLabel("Name"), 0, 0)
        grid.addWidget(QLabel("Start (MHz)"), 0, 1)
        grid.addWidget(QLabel("Stop (MHz)"), 0, 2)
        
        self.rows = []
        for i in range(6):
            data = buttons_data[i] if i < len(buttons_data) else {"name": "Empty", "start": 100.0, "stop": 200.0}
            name_edit = QLineEdit(data["name"])
            
            start_spin = QDoubleSpinBox()
            start_spin.setRange(0.1, 20000.0)
            start_spin.setDecimals(1)
            start_spin.setValue(float(data["start"]))
            start_spin.setSuffix(" MHz")
            
            stop_spin = QDoubleSpinBox()
            stop_spin.setRange(0.1, 20000.0)
            stop_spin.setDecimals(1)
            stop_spin.setValue(float(data["stop"]))
            stop_spin.setSuffix(" MHz")
            
            grid.addWidget(name_edit, i+1, 0)
            grid.addWidget(start_spin, i+1, 1)
            grid.addWidget(stop_spin, i+1, 2)
            
            self.rows.append((name_edit, start_spin, stop_spin))
            
        layout.addLayout(grid)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
    def accept_changes(self):
        for name_edit, start_spin, stop_spin in self.rows:
            self.buttons_data.append({
                "name": name_edit.text(),
                "start": start_spin.value(),
                "stop": stop_spin.value()
            })
        self.accept()
"""

with open("dialogs.py", "a") as f:
    f.write(content)

print("Dialogs appended to dialogs.py")
