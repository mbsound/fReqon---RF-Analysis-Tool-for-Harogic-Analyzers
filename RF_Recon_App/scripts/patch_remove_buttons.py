import sys

with open('gui.py', 'r') as f:
    content = f.read()

# Remove Amplitude apply button
target_amp = """        self.apply_amp_btn = QPushButton("Apply Amplitude")
        self.apply_amp_btn.clicked.connect(self.apply_amplitude)
        self.apply_amp_btn.setEnabled(False)"""
if target_amp in content:
    content = content.replace(target_amp, "")

target_amp_layout = "        amp_form.addRow(self.apply_amp_btn)"
if target_amp_layout in content:
    content = content.replace(target_amp_layout, "")

# Remove Bandwidth apply button
target_bw = """        self.apply_bw_btn = QPushButton("Apply Bandwidth")
        self.apply_bw_btn.clicked.connect(self.apply_bandwidth)
        self.apply_bw_btn.setEnabled(False)"""
if target_bw in content:
    content = content.replace(target_bw, "")

target_bw_layout = "        self.bw_section.content_layout.addWidget(self.apply_bw_btn)"
if target_bw_layout in content:
    content = content.replace(target_bw_layout, "")

# Remove all references to enabling/disabling these buttons
content = content.replace("self.apply_amp_btn.setEnabled(True)", "")
content = content.replace("self.apply_amp_btn.setEnabled(False)", "")
content = content.replace("self.apply_bw_btn.setEnabled(True)", "")
content = content.replace("self.apply_bw_btn.setEnabled(False)", "")

with open('gui.py', 'w') as f:
    f.write(content)
