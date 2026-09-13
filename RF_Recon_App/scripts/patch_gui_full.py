import os
import sys

with open('gui.py', 'r') as f:
    content = f.read()

# 1. Add DEFAULT_REGIONS after imports
if "DEFAULT_REGIONS = {" not in content:
    import_end = content.find("class CustomMenuBar")
    default_regions = """DEFAULT_REGIONS = {
    "North America": [
        {"name": "VHF", "start": 174.0, "stop": 216.0},
        {"name": "UHF", "start": 470.0, "stop": 616.0},
        {"name": "Duplex Gap", "start": 653.0, "stop": 663.0},
        {"name": "ISM", "start": 902.0, "stop": 928.0},
        {"name": "STL", "start": 940.0, "stop": 960.0},
        {"name": "Custom", "start": 1000.0, "stop": 2000.0}
    ]
}

"""
    content = content[:import_end] + default_regions + content[import_end:]


# 2. Add region variables in __init__
init_target = "        self.settings = QSettings(\"Harogic\", \"RF_Recon\")\n"
if "self.region_configs" not in content:
    init_vars = """        self.region_configs = json.loads(self.settings.value("regions", json.dumps(DEFAULT_REGIONS)))
        self.current_region = self.settings.value("current_region", "North America")
        if self.current_region not in self.region_configs:
            self.current_region = list(self.region_configs.keys())[0]
"""
    content = content.replace(init_target, init_target + init_vars)


# 3. Add Preferences... to settings menu
prefs_target = "settings_menu.addAction(self.theme_action)\n"
if "Preferences..." not in content:
    prefs_code = """        
        preferences_action = QAction("Preferences...", self)
        preferences_action.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(preferences_action)
"""
    content = content.replace(prefs_target, prefs_target + prefs_code)

# 4. Add the quick-settings buttons UI in right panel
right_panel_target = "        self.spectrum_section.content_layout.addLayout(freq_form)\n"
if "self.quick_btn_layout" not in content:
    qs_code = """        
        # Quick-Settings Grid
        self.quick_settings_header = QHBoxLayout()
        qs_label = QLabel("Quick Settings")
        qs_label.setStyleSheet("color: #aaaaaa; font-weight: bold;")
        self.quick_settings_header.addWidget(qs_label)
        self.quick_settings_header.addStretch()
        self.edit_qs_btn = QPushButton("⚙️ Edit")
        self.edit_qs_btn.setStyleSheet("background: transparent; color: #5cafff; font-weight: bold;")
        self.edit_qs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_qs_btn.clicked.connect(self.open_quick_settings_dialog)
        self.quick_settings_header.addWidget(self.edit_qs_btn)
        
        self.spectrum_section.content_layout.addLayout(self.quick_settings_header)
        
        self.quick_btn_layout = QGridLayout()
        self.quick_btns = []
        for i in range(6):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.clicked.connect(self.on_quick_btn_toggled)
            self.quick_btns.append(btn)
            self.quick_btn_layout.addWidget(btn, i // 2, i % 2)
            
        self.spectrum_section.content_layout.addLayout(self.quick_btn_layout)
        self.update_quick_settings_ui()
"""
    content = content.replace(right_panel_target, qs_code + right_panel_target)

with open('gui.py', 'w') as f:
    f.write(content)

