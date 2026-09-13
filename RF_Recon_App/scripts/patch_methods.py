import sys

with open('gui.py', 'r') as f:
    content = f.read()

# Modify on_start_stop_changed
target1 = """    def on_start_stop_changed(self):
        if self._updating_freqs: return
        self._updating_freqs = True
        center = (self.start_spin.value() + self.stop_spin.value()) / 2.0
        self.center_spin.setValue(center)
        self._updating_freqs = False
"""
replacement1 = target1 + "        self.sync_quick_buttons_state()\n"

if target1 in content:
    content = content.replace(target1, replacement1)

# Add new methods at the end of the class
target2 = """    def closeEvent(self, event):"""
new_methods = """
    def open_settings_dialog(self):
        dialog = SettingsDialog(self.current_region, list(self.region_configs.keys()), self)
        if dialog.exec():
            self.current_region = dialog.selected_region
            self.settings.setValue("current_region", self.current_region)
            self.update_quick_settings_ui()
            
    def open_quick_settings_dialog(self):
        buttons_data = self.region_configs.get(self.current_region, [])
        dialog = QuickSettingsDialog(self.current_region, buttons_data, self)
        if dialog.exec():
            self.region_configs[self.current_region] = dialog.buttons_data
            self.settings.setValue("regions", json.dumps(self.region_configs))
            self.update_quick_settings_ui()
            
    def update_quick_settings_ui(self):
        self._updating_freqs = True # Prevent circular triggers during setup
        buttons_data = self.region_configs.get(self.current_region, [])
        for i, btn in enumerate(self.quick_btns):
            if i < len(buttons_data):
                btn.setText(buttons_data[i]["name"])
                btn.setProperty("start_freq", buttons_data[i]["start"])
                btn.setProperty("stop_freq", buttons_data[i]["stop"])
                btn.setVisible(True)
            else:
                btn.setVisible(False)
        self._updating_freqs = False
        self.sync_quick_buttons_state()
        
    def on_quick_btn_toggled(self):
        if self._updating_freqs: return
        
        # Calculate inclusive min start and max stop
        min_start = None
        max_stop = None
        for btn in self.quick_btns:
            if btn.isVisible() and btn.isChecked():
                btn_start = btn.property("start_freq")
                btn_stop = btn.property("stop_freq")
                if min_start is None or btn_start < min_start:
                    min_start = btn_start
                if max_stop is None or btn_stop > max_stop:
                    max_stop = btn_stop
                    
        if min_start is not None and max_stop is not None:
            self._updating_freqs = True
            self.start_spin.setValue(min_start)
            self.stop_spin.setValue(max_stop)
            center = (min_start + max_stop) / 2.0
            self.center_spin.setValue(center)
            self._updating_freqs = False
            self.apply_frequencies()

    def sync_quick_buttons_state(self):
        if getattr(self, '_updating_freqs', False): return
        
        start_val = self.start_spin.value()
        stop_val = self.stop_spin.value()
        
        # Block signals briefly so setting checked doesn't trigger on_quick_btn_toggled
        for btn in self.quick_btns:
            btn.blockSignals(True)
            if btn.isVisible():
                btn_start = btn.property("start_freq")
                btn_stop = btn.property("stop_freq")
                
                # Check if button range is entirely on-screen (within current start/stop)
                if start_val <= btn_start and stop_val >= btn_stop:
                    btn.setChecked(True)
                else:
                    btn.setChecked(False)
            btn.blockSignals(False)

"""

if "def open_settings_dialog" not in content:
    content = content.replace(target2, new_methods + target2)

with open('gui.py', 'w') as f:
    f.write(content)

