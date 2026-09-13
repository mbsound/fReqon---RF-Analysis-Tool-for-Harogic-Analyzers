import sys

with open('dialogs.py', 'r') as f:
    content = f.read()

target = """class SettingsDialog(QDialog):
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

"""

if target in content:
    content = content.replace(target, "")
    with open('dialogs.py', 'w') as f:
        f.write(content)

