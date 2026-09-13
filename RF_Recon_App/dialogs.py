from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox, QComboBox,
    QSpinBox, QFormLayout, QGroupBox, QDoubleSpinBox, QGridLayout, QWidget, QCheckBox, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

class MissingCalDialog(QDialog):
    def __init__(self, model: int, uid: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration Files Missing")
        self.setModal(True)
        self.resize(400, 150)
        
        self.result_action = "cancel" # can be "import", "continue", "cancel"
        
        layout = QVBoxLayout(self)
        
        msg_label = QLabel(
            f"<b>No Calibration Files found for Harogic Analyzer</b><br><br>"
            f"Model: {model:03d}<br>"
            f"SN: {uid:016x}"
        )
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg_label)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        
        import_btn = QPushButton("Import Calibration Files")
        import_btn.clicked.connect(self.on_import)
        import_btn.setStyleSheet("font-weight: bold; padding: 5px;")
        
        continue_btn = QPushButton("Continue Without Calibration")
        continue_btn.clicked.connect(self.on_continue)
        continue_btn.setStyleSheet("padding: 5px;")
        
        btn_layout.addWidget(import_btn)
        btn_layout.addWidget(continue_btn)
        
        layout.addLayout(btn_layout)
        
    def on_import(self):
        self.result_action = "import"
        self.accept()
        
    def on_continue(self):
        self.result_action = "continue"
        self.accept()

class DropZoneFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f0f0f0;
            }
        """)
        layout = QVBoxLayout(self)
        label = QLabel("Drag and Drop Calibration Files Here")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("border: none; background: transparent; color: #555; font-size: 16px;")
        layout.addWidget(label)
        self.parent_dialog = parent
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame {
                    border: 2px dashed #4CAF50;
                    border-radius: 10px;
                    background-color: #e8f5e9;
                }
            """)
            
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f0f0f0;
            }
        """)
        
    def dropEvent(self, event: QDropEvent):
        self.dragLeaveEvent(None) # reset style
        urls = event.mimeData().urls()
        files = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if self.parent_dialog:
            self.parent_dialog.handle_dropped_files(files)

class ClearCalDialog(QDialog):
    def __init__(self, calibrations, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clear Calibration Files")
        self.setModal(True)
        self.resize(350, 150)
        
        self.selected_model = None
        self.selected_uid = None
        
        layout = QVBoxLayout(self)
        
        label = QLabel("Select the Analyzer to wipe calibration data for:")
        layout.addWidget(label)
        
        self.combo = QComboBox()
        for (model, uid) in calibrations:
            self.combo.addItem(f"Model: {model:03d} | SN: {uid:016x}", userData=(model, uid))
        layout.addWidget(self.combo)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("color: white; background-color: #d32f2f; font-weight: bold;")
        clear_btn.clicked.connect(self.on_clear)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
    def on_clear(self):
        if self.combo.currentIndex() >= 0:
            self.selected_model, self.selected_uid = self.combo.currentData()
            
            # Show critical confirmation
            reply = QMessageBox.critical(
                self, 
                "Confirm Irreparable Action", 
                f"Are you sure? This is an irreparable action and will permanently delete the calibration data for Analyzer SN: {self.selected_uid:016x}.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.accept()

class DragDropCalDialog(QDialog):
    def __init__(self, model=None, uid=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Calibration Files")
        self.setModal(True)
        self.resize(500, 400)
        
        self.model = model
        self.uid = uid
        self.dropped_files = []
        self.is_ready = False
        
        self.req_rfacal = False
        self.req_ifacal = False
        self.req_config = False
        self.req_base_amp = False
        self.req_mod_amp = False
        
        layout = QVBoxLayout(self)
        
        self.info_label = QLabel()
        if self.model is not None and self.uid is not None:
            self.info_label.setText(f"<b>Target Analyzer SN:</b> {self.uid:016x}")
        else:
            self.info_label.setText("<b>Target Analyzer SN:</b> <i>Waiting for files...</i>")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        
        self.drop_zone = DropZoneFrame(self)
        self.drop_zone.setMinimumHeight(120)
        layout.addWidget(self.drop_zone)
        
        self.checklist_layout = QVBoxLayout()
        self.lbl_rfacal = QLabel("☐ RF Amplitude Calibration (*_rfacal.txt)")
        self.lbl_ifacal = QLabel("☐ IF Amplitude Calibration (*_ifacal.txt)")
        self.lbl_config = QLabel("☐ Hardware Configuration (*_config.txt)")
        self.lbl_base_amp = QLabel("☐ Base Amplitude Compensation (*_ampcomp.txt)")
        self.lbl_mod_amp = QLabel("☐ Module Amplitude Compensation (*ampcomp.txt, non-base)")
        
        self.checklist_layout.addWidget(self.lbl_rfacal)
        self.checklist_layout.addWidget(self.lbl_ifacal)
        self.checklist_layout.addWidget(self.lbl_config)
        self.checklist_layout.addWidget(self.lbl_base_amp)
        self.checklist_layout.addWidget(self.lbl_mod_amp)
        
        layout.addLayout(self.checklist_layout)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save & Apply")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def handle_dropped_files(self, files):
        import re
        import os
        # If we don't have a model/uid, auto-detect it from the first matching file
        if self.model is None or self.uid is None:
            pattern = re.compile(r"^(\d{3})_([a-fA-F0-9]{16})_.*\.txt$")
            for f in files:
                name = os.path.basename(f)
                match = pattern.match(name)
                if match:
                    try:
                        self.model = int(match.group(1))
                        self.uid = int(match.group(2), 16)
                        self.info_label.setText(f"<b>Target Analyzer SN:</b> {self.uid:016x}")
                        break
                    except ValueError:
                        continue
        
        # If still none, none of the files matched the expected UID format
        if self.model is None or self.uid is None:
            QMessageBox.warning(self, "Invalid Files", "Could not detect a valid Target Analyzer Serial Number from the dropped files.")
            return

        model_str = f"{self.model:03d}"
        uid_str = f"{self.uid:016x}"
        
        for f in files:
            name = os.path.basename(f).lower()
            
            # Check requirements
            if f"{model_str}_{uid_str}_rfacal.txt" in name:
                self.req_rfacal = True
                self.lbl_rfacal.setText("✅ RF Amplitude Calibration")
                self.lbl_rfacal.setStyleSheet("color: green; font-weight: bold;")
                if f not in self.dropped_files: self.dropped_files.append(f)
                
            elif f"{model_str}_{uid_str}_ifacal.txt" in name:
                self.req_ifacal = True
                self.lbl_ifacal.setText("✅ IF Amplitude Calibration")
                self.lbl_ifacal.setStyleSheet("color: green; font-weight: bold;")
                if f not in self.dropped_files: self.dropped_files.append(f)
                
            elif f"{model_str}_{uid_str}_config.txt" in name:
                self.req_config = True
                self.lbl_config.setText("✅ Hardware Configuration")
                self.lbl_config.setStyleSheet("color: green; font-weight: bold;")
                if f not in self.dropped_files: self.dropped_files.append(f)
                
            elif f"{model_str}_ampcomp.txt" in name:
                self.req_base_amp = True
                self.lbl_base_amp.setText("✅ Base Amplitude Compensation")
                self.lbl_base_amp.setStyleSheet("color: green; font-weight: bold;")
                if f not in self.dropped_files: self.dropped_files.append(f)
                
            elif "ampcomp.txt" in name and not name.startswith(model_str):
                self.req_mod_amp = True
                self.lbl_mod_amp.setText(f"✅ Module Amplitude Compensation ({name})")
                self.lbl_mod_amp.setStyleSheet("color: green; font-weight: bold;")
                if f not in self.dropped_files: self.dropped_files.append(f)
                
        # If all 5 are satisfied, enable save
        if self.req_rfacal and self.req_ifacal and self.req_config and self.req_base_amp and self.req_mod_amp:
            self.save_btn.setEnabled(True)
            self.is_ready = True

class WaterfallSettingsDialog(QDialog):
    def __init__(self, current_depth, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Waterfall Settings")
        self.setModal(True)
        self.resize(300, 100)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(10, 5000)
        self.depth_spin.setValue(current_depth)
        self.depth_spin.setSuffix(" Sweeps")
        
        form.addRow("History Depth:", self.depth_spin)
        
        layout.addLayout(form)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
    def get_settings(self):
        return self.depth_spin.value()

from PyQt6.QtWidgets import QTabWidget, QGridLayout, QLineEdit, QDoubleSpinBox, QWidget

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
        num_rows = max(len(buttons_data), 8)
        for i in range(num_rows):
            data = buttons_data[i] if i < len(buttons_data) else {"name": "", "start": 100.0, "stop": 200.0}
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
    Launch Settings configuration dialog.
    Allows configuring:
    - Default Region (e.g. North America, UK, Spain, etc.)
    - Default Analyzer Sweep frequency span & quick-setting buttons
    - Default Spectrum View frequency span & view quick-setting buttons (or linked to sweep)
    - Instant 'Grab Current Live App State'
    """
    def __init__(self, region_configs, current_region="North America",
                 sweep_start=470.0, sweep_stop=608.0, sweep_anchors=None,
                 view_start=470.0, view_stop=608.0, view_anchors=None,
                 link_view=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Launch Settings (Startup Defaults)")
        self.setModal(True)
        self.resize(660, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444444;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #5cafff;
            }
            QDoubleSpinBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 3px 6px;
                font-weight: bold;
            }
            QPushButton#quickSettingBtn {
                background-color: #2b2b2b;
                color: #cccccc;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 5px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton#quickSettingBtn:hover {
                background-color: #383838;
                color: #ffffff;
            }
            QPushButton#quickSettingBtn:checked {
                background-color: #0078d7;
                color: #ffffff;
                border: 1px solid #29b6f6;
            }
        """)
        
        self.parent_app = parent
        self.region_configs = region_configs
        self.current_region = current_region if current_region in region_configs else list(region_configs.keys())[0]
        
        self._sweep_anchors = set(tuple(a) for a in sweep_anchors) if sweep_anchors else set()
        self._view_anchors = set(tuple(a) for a in view_anchors) if view_anchors else set()
        self._updating_sweep = False
        self._updating_view = False
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # 1. Header
        header = QLabel("<b>Configure Application Startup Defaults</b><br>"
                        "<span style='color: #888888; font-size: 11px;'>Configure the default region, hardware sweep span, and spectrum view preset loaded upon application launch.</span>")
        main_layout.addWidget(header)
        
        # 2. Region selection
        region_box = QGroupBox("Default Region")
        reg_layout = QHBoxLayout(region_box)
        
        reg_lbl = QLabel("Startup Region:")
        self.region_combo = QComboBox()
        self.region_combo.addItems(list(self.region_configs.keys()))
        self.region_combo.setCurrentText(self.current_region)
        self.region_combo.currentTextChanged.connect(self._on_region_changed)
        self.region_combo.setStyleSheet("background-color: #2b2b2b; color: white; padding: 5px; border: 1px solid #555; border-radius: 4px;")
        
        reg_layout.addWidget(reg_lbl)
        reg_layout.addWidget(self.region_combo, 1)
        main_layout.addWidget(region_box)
        
        # 3. Sweep Group Box
        self.sweep_box = QGroupBox("Default Analyzer Sweep (Hardware)")
        sweep_layout = QVBoxLayout(self.sweep_box)
        
        sweep_qs_lbl = QLabel("Quick Setting Buttons:")
        sweep_qs_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        sweep_layout.addWidget(sweep_qs_lbl)
        
        self.sweep_btn_layout = QGridLayout()
        self.sweep_btn_layout.setHorizontalSpacing(4)
        self.sweep_btn_layout.setVerticalSpacing(4)
        self.sweep_btns = []
        sweep_layout.addLayout(self.sweep_btn_layout)
        
        sweep_spin_layout = QHBoxLayout()
        s_lbl = QLabel("Start:")
        self.sweep_start_spin = QDoubleSpinBox()
        self.sweep_start_spin.setRange(0.1, 20000.0)
        self.sweep_start_spin.setDecimals(1)
        self.sweep_start_spin.setValue(float(sweep_start))
        self.sweep_start_spin.setSuffix(" MHz")
        self.sweep_start_spin.valueChanged.connect(self._on_sweep_spin_changed)
        
        e_lbl = QLabel("Stop:")
        self.sweep_stop_spin = QDoubleSpinBox()
        self.sweep_stop_spin.setRange(0.1, 20000.0)
        self.sweep_stop_spin.setDecimals(1)
        self.sweep_stop_spin.setValue(float(sweep_stop))
        self.sweep_stop_spin.setSuffix(" MHz")
        self.sweep_stop_spin.valueChanged.connect(self._on_sweep_spin_changed)
        
        sweep_spin_layout.addWidget(s_lbl)
        sweep_spin_layout.addWidget(self.sweep_start_spin)
        sweep_spin_layout.addSpacing(15)
        sweep_spin_layout.addWidget(e_lbl)
        sweep_spin_layout.addWidget(self.sweep_stop_spin)
        sweep_spin_layout.addStretch()
        sweep_layout.addLayout(sweep_spin_layout)
        
        main_layout.addWidget(self.sweep_box)
        
        # 4. View Group Box
        self.view_box = QGroupBox("Default Spectrum View (Display)")
        view_layout = QVBoxLayout(self.view_box)
        
        from PyQt6.QtWidgets import QCheckBox
        self.link_view_cb = QCheckBox("🔗 Link View to Analyzer Sweep (View matches Sweep bounds)")
        self.link_view_cb.setChecked(link_view)
        self.link_view_cb.toggled.connect(self._on_link_view_toggled)
        self.link_view_cb.setStyleSheet("font-weight: bold; color: #4fc3f7; margin-bottom: 6px;")
        view_layout.addWidget(self.link_view_cb)
        
        self.view_qs_container = QWidget()
        view_qs_sublayout = QVBoxLayout(self.view_qs_container)
        view_qs_sublayout.setContentsMargins(0, 0, 0, 0)
        
        view_qs_lbl = QLabel("View Quick Setting Buttons:")
        view_qs_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        view_qs_sublayout.addWidget(view_qs_lbl)
        
        self.view_btn_layout = QGridLayout()
        self.view_btn_layout.setHorizontalSpacing(4)
        self.view_btn_layout.setVerticalSpacing(4)
        self.view_btns = []
        view_qs_sublayout.addLayout(self.view_btn_layout)
        
        view_spin_layout = QHBoxLayout()
        vs_lbl = QLabel("View Start:")
        self.view_start_spin = QDoubleSpinBox()
        self.view_start_spin.setRange(0.1, 20000.0)
        self.view_start_spin.setDecimals(1)
        self.view_start_spin.setValue(float(view_start))
        self.view_start_spin.setSuffix(" MHz")
        self.view_start_spin.valueChanged.connect(self._on_view_spin_changed)
        
        ve_lbl = QLabel("View Stop:")
        self.view_stop_spin = QDoubleSpinBox()
        self.view_stop_spin.setRange(0.1, 20000.0)
        self.view_stop_spin.setDecimals(1)
        self.view_stop_spin.setValue(float(view_stop))
        self.view_stop_spin.setSuffix(" MHz")
        self.view_stop_spin.valueChanged.connect(self._on_view_spin_changed)
        
        view_spin_layout.addWidget(vs_lbl)
        view_spin_layout.addWidget(self.view_start_spin)
        view_spin_layout.addSpacing(15)
        view_spin_layout.addWidget(ve_lbl)
        view_spin_layout.addWidget(self.view_stop_spin)
        view_spin_layout.addStretch()
        view_qs_sublayout.addLayout(view_spin_layout)
        
        view_layout.addWidget(self.view_qs_container)
        main_layout.addWidget(self.view_box)
        
        # Populate buttons
        self._rebuild_quick_buttons()
        self._on_link_view_toggled(link_view)
        
        # 5. Bottom Buttons (Grab Current & OK / Cancel)
        bottom_layout = QHBoxLayout()
        self.grab_btn = QPushButton("📥 Grab Current Live App State")
        self.grab_btn.setStyleSheet("background-color: #37474f; color: #80d8ff; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        self.grab_btn.clicked.connect(self._grab_parent_state)
        bottom_layout.addWidget(self.grab_btn)
        
        bottom_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("padding: 6px 14px; background-color: #424242; border-radius: 4px; color: white;")
        self.cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("Save Launch Defaults")
        self.save_btn.setStyleSheet("padding: 6px 16px; background-color: #0288d1; font-weight: bold; color: white; border-radius: 4px;")
        self.save_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(bottom_layout)

    def _on_region_changed(self, new_region):
        self.current_region = new_region
        self._sweep_anchors.clear()
        self._view_anchors.clear()
        self._rebuild_quick_buttons()

    def _rebuild_quick_buttons(self):
        # Clear existing
        for btn in self.sweep_btns:
            self.sweep_btn_layout.removeWidget(btn)
            btn.deleteLater()
        self.sweep_btns.clear()

        for btn in self.view_btns:
            self.view_btn_layout.removeWidget(btn)
            btn.deleteLater()
        self.view_btns.clear()

        buttons_data = self.region_configs.get(self.current_region, [])
        for i, b_data in enumerate(buttons_data):
            # Sweep button
            s_btn = QPushButton(b_data["name"])
            s_btn.setObjectName("quickSettingBtn")
            s_btn.setCheckable(True)
            s_btn.setProperty("start_freq", float(b_data["start"]))
            s_btn.setProperty("stop_freq", float(b_data["stop"]))
            s_btn.clicked.connect(self._on_sweep_btn_toggled)
            self.sweep_btns.append(s_btn)
            self.sweep_btn_layout.addWidget(s_btn, i // 2, i % 2)

            # View button
            v_btn = QPushButton(b_data["name"])
            v_btn.setObjectName("quickSettingBtn")
            v_btn.setCheckable(True)
            v_btn.setProperty("start_freq", float(b_data["start"]))
            v_btn.setProperty("stop_freq", float(b_data["stop"]))
            v_btn.clicked.connect(self._on_view_btn_toggled)
            self.view_btns.append(v_btn)
            self.view_btn_layout.addWidget(v_btn, i // 2, i % 2)

        self._sync_sweep_buttons()
        self._sync_view_buttons()

    def _on_sweep_btn_toggled(self):
        if self._updating_sweep: return
        self._updating_sweep = True
        try:
            clicked_btn = self.sender()
            if clicked_btn:
                b_start = clicked_btn.property("start_freq")
                b_stop = clicked_btn.property("stop_freq")
                if b_start is not None and b_stop is not None:
                    key = (float(b_start), float(b_stop))
                    if clicked_btn.isChecked():
                        self._sweep_anchors.add(key)
                    else:
                        self._sweep_anchors.discard(key)

            if self._sweep_anchors:
                min_s = min(a[0] for a in self._sweep_anchors)
                max_e = max(a[1] for a in self._sweep_anchors)
                self.sweep_start_spin.blockSignals(True)
                self.sweep_stop_spin.blockSignals(True)
                self.sweep_start_spin.setValue(min_s)
                self.sweep_stop_spin.setValue(max_e)
                self.sweep_start_spin.blockSignals(False)
                self.sweep_stop_spin.blockSignals(False)
            self._sync_sweep_buttons()

            if self.link_view_cb.isChecked():
                self._view_anchors = set(self._sweep_anchors)
                self.view_start_spin.blockSignals(True)
                self.view_stop_spin.blockSignals(True)
                self.view_start_spin.setValue(self.sweep_start_spin.value())
                self.view_stop_spin.setValue(self.sweep_stop_spin.value())
                self.view_start_spin.blockSignals(False)
                self.view_stop_spin.blockSignals(False)
                self._sync_view_buttons()
        finally:
            self._updating_sweep = False

    def _on_view_btn_toggled(self):
        if self._updating_view: return
        self._updating_view = True
        try:
            clicked_btn = self.sender()
            if clicked_btn:
                b_start = clicked_btn.property("start_freq")
                b_stop = clicked_btn.property("stop_freq")
                if b_start is not None and b_stop is not None:
                    key = (float(b_start), float(b_stop))
                    if clicked_btn.isChecked():
                        self._view_anchors.add(key)
                    else:
                        self._view_anchors.discard(key)

            if self._view_anchors:
                min_s = min(a[0] for a in self._view_anchors)
                max_e = max(a[1] for a in self._view_anchors)
                self.view_start_spin.blockSignals(True)
                self.view_stop_spin.blockSignals(True)
                self.view_start_spin.setValue(min_s)
                self.view_stop_spin.setValue(max_e)
                self.view_start_spin.blockSignals(False)
                self.view_stop_spin.blockSignals(False)
            self._sync_view_buttons()
        finally:
            self._updating_view = False

    def _on_sweep_spin_changed(self):
        if self._updating_sweep: return
        self._sync_sweep_buttons()
        if self.link_view_cb.isChecked():
            self.view_start_spin.blockSignals(True)
            self.view_stop_spin.blockSignals(True)
            self.view_start_spin.setValue(self.sweep_start_spin.value())
            self.view_stop_spin.setValue(self.sweep_stop_spin.value())
            self.view_start_spin.blockSignals(False)
            self.view_stop_spin.blockSignals(False)
            self._sync_view_buttons()

    def _on_view_spin_changed(self):
        if self._updating_view: return
        self._sync_view_buttons()

    def _sync_sweep_buttons(self):
        start_val = self.sweep_start_spin.value()
        stop_val = self.sweep_stop_spin.value()
        for btn in self.sweep_btns:
            btn.blockSignals(True)
            bs = btn.property("start_freq")
            be = btn.property("stop_freq")
            if bs is not None and be is not None:
                if (start_val <= bs + 0.5) and (stop_val >= be - 0.5):
                    btn.setChecked(True)
                else:
                    btn.setChecked(False)
            btn.blockSignals(False)

    def _sync_view_buttons(self):
        start_val = self.view_start_spin.value()
        stop_val = self.view_stop_spin.value()
        for btn in self.view_btns:
            btn.blockSignals(True)
            bs = btn.property("start_freq")
            be = btn.property("stop_freq")
            if bs is not None and be is not None:
                if (start_val <= bs + 0.5) and (stop_val >= be - 0.5):
                    btn.setChecked(True)
                else:
                    btn.setChecked(False)
            btn.blockSignals(False)

    def _on_link_view_toggled(self, checked):
        self.view_qs_container.setEnabled(not checked)
        if checked:
            self._view_anchors = set(self._sweep_anchors)
            self.view_start_spin.setValue(self.sweep_start_spin.value())
            self.view_stop_spin.setValue(self.sweep_stop_spin.value())
            self._sync_view_buttons()

    def _grab_parent_state(self):
        if not self.parent_app: return
        p = self.parent_app
        if hasattr(p, 'current_region') and p.current_region in self.region_configs:
            self.region_combo.setCurrentText(p.current_region)
        if hasattr(p, 'start_spin') and hasattr(p, 'stop_spin'):
            self.sweep_start_spin.setValue(p.start_spin.value())
            self.sweep_stop_spin.setValue(p.stop_spin.value())
        if hasattr(p, '_explicit_quick_anchors'):
            self._sweep_anchors = set(p._explicit_quick_anchors)
        if hasattr(p, 'link_view_check'):
            self.link_view_cb.setChecked(p.link_view_check.isChecked())
        if hasattr(p, 'view_start_spin') and hasattr(p, 'view_stop_spin'):
            self.view_start_spin.setValue(p.view_start_spin.value())
            self.view_stop_spin.setValue(p.view_stop_spin.value())
        if hasattr(p, '_explicit_view_quick_anchors'):
            self._view_anchors = set(p._explicit_view_quick_anchors)
        self._sync_sweep_buttons()
        self._sync_view_buttons()

    def get_settings(self):
        return {
            "region": self.region_combo.currentText(),
            "sweep_start": self.sweep_start_spin.value(),
            "sweep_stop": self.sweep_stop_spin.value(),
            "sweep_anchors": list(self._sweep_anchors),
            "view_start": self.view_start_spin.value(),
            "view_stop": self.view_stop_spin.value(),
            "view_anchors": list(self._view_anchors),
            "link_view": self.link_view_cb.isChecked()
        }
