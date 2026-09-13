"""
cal_dialogs.py - Calibration Management Workstation & Dialogs for Freqon.
Provides per-device Serial-Number-linked calibration library browsing, file inspection,
drag-and-drop ingestion, manual file mapping, alias renaming, and active staging.
Strict zero-emoji professional industrial test & measurement aesthetic.
"""

import os
import shutil
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QInputDialog,
    QSplitter, QWidget, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor

from core.calibration_manager import CalibrationManager


class MissingCalDialog(QDialog):
    """
    Prompt shown when an attached analyzer lacks calibration files.
    """
    def __init__(self, model: int, uid: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration Files Required")
        self.setModal(True)
        self.resize(460, 200)
        self.result_action = "cancel"
        
        try:
            model_str = f"{int(model):03d}"
        except Exception:
            model_str = str(model)
        try:
            uid_str = f"{int(uid):016x}"
        except Exception:
            uid_str = str(uid)
            
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(8)
        
        title_lbl = QLabel("CALIBRATION REQUIRED")
        title_lbl.setStyleSheet("color: #f59e0b; font-size: 13px; font-weight: 700; letter-spacing: 1px;")
        card_layout.addWidget(title_lbl)
        
        desc_lbl = QLabel(
            f"Connected Analyzer has no calibration files in persistent storage.\n\n"
            f"Model: {model_str}   •   Serial: {uid_str}"
        )
        desc_lbl.setStyleSheet("color: #f0f6fc; font-size: 12px; line-height: 1.4;")
        desc_lbl.setWordWrap(True)
        card_layout.addWidget(desc_lbl)
        
        layout.addWidget(card)
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        open_mgr_btn = QPushButton("Open Calibration Manager")
        open_mgr_btn.setObjectName("primaryActionBtn")
        open_mgr_btn.clicked.connect(self.on_open_manager)
        
        continue_btn = QPushButton("Continue (Uncalibrated)")
        continue_btn.clicked.connect(self.on_continue)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(continue_btn)
        btn_layout.addWidget(open_mgr_btn)
        layout.addLayout(btn_layout)
        
    def on_open_manager(self):
        self.result_action = "open_manager"
        self.accept()
        
    def on_continue(self):
        self.result_action = "continue"
        self.accept()


class DropZoneFrame(QFrame):
    """
    Drag and drop target area for Harogic calibration files.
    """
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #30363d;
                border-radius: 8px;
                background-color: #161b22;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.label = QLabel("Drag && Drop Calibration Files Here\n(*_rfacal.txt, *_ifacal.txt, *_config.txt, *ampcomp.txt, *.lic)")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("border: none; background: transparent; color: #8b949e; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.label)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame {
                    border: 2px dashed #38bdf8;
                    border-radius: 8px;
                    background-color: rgba(56, 189, 248, 0.08);
                }
            """)
            
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #30363d;
                border-radius: 8px;
                background-color: #161b22;
            }
        """)
        
    def dropEvent(self, event: QDropEvent):
        self.dragLeaveEvent(None)
        urls = event.mimeData().urls()
        files = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if files:
            self.files_dropped.emit(files)


class CalibrationManagerDialog(QDialog):
    """
    Comprehensive Calibration Manager Workstation Dialog.
    Allows browsing, inspecting, importing, renaming, and staging per-analyzer calibrations.
    """
    def __init__(self, selected_model=None, selected_uid=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration File Workstation")
        self.setModal(True)
        self.resize(980, 680)
        
        self.cal_manager = CalibrationManager()
        self.target_model = selected_model
        self.target_uid = selected_uid
        self.selected_device = None
        
        self._init_ui()
        self._populate_devices_table()
        
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)
        
        # Header Banner
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_lbl = QLabel("CALIBRATION FILE MANAGER")
        title_lbl.setStyleSheet("color: #38bdf8; font-size: 15px; font-weight: 700; letter-spacing: 1.5px;")
        sub_lbl = QLabel("Manage, inspect, and deploy per-analyzer calibration sets linked to hardware Serial Numbers.")
        sub_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header_layout.addLayout(title_box)
        header_layout.addStretch()
        
        import_dir_btn = QPushButton("+ Import Cal Folder")
        import_dir_btn.clicked.connect(self._on_import_directory)
        header_layout.addWidget(import_dir_btn)
        main_layout.addLayout(header_layout)
        
        # Splitter Layout: Left Device Library | Right Calibration Inspector
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #21262d; width: 2px; }")
        
        # Left Panel (Analyzer Library)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)
        
        lib_title = QLabel("REGISTERED ANALYZERS")
        lib_title.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
        left_layout.addWidget(lib_title)
        
        self.devices_table = QTableWidget(0, 3)
        self.devices_table.setHorizontalHeaderLabels(["Alias / Model", "Serial Number (UID)", "Status"])
        self.devices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.devices_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.devices_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.devices_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.devices_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.devices_table.verticalHeader().setVisible(False)
        self.devices_table.setShowGrid(False)
        self.devices_table.itemSelectionChanged.connect(self._on_device_selection_changed)
        left_layout.addWidget(self.devices_table)
        
        # Left action toolbar
        left_btn_bar = QHBoxLayout()
        left_btn_bar.setSpacing(6)
        
        self.rename_btn = QPushButton("Rename Alias")
        self.rename_btn.clicked.connect(self._on_rename_alias)
        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self._on_export_calibration)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.clicked.connect(self._on_delete_calibration)
        
        left_btn_bar.addWidget(self.rename_btn)
        left_btn_bar.addWidget(self.export_btn)
        left_btn_bar.addWidget(self.delete_btn)
        left_layout.addLayout(left_btn_bar)
        
        splitter.addWidget(left_widget)
        
        # Right Panel (Calibration Inspector & Drop Zone)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(12)
        
        # Device Header Card
        self.dev_header_card = QFrame()
        self.dev_header_card.setObjectName("cardFrame")
        dev_h_layout = QVBoxLayout(self.dev_header_card)
        dev_h_layout.setContentsMargins(14, 12, 14, 12)
        dev_h_layout.setSpacing(4)
        
        self.dev_title_lbl = QLabel("Select an Analyzer")
        self.dev_title_lbl.setStyleSheet("color: #f0f6fc; font-size: 14px; font-weight: 700;")
        self.dev_uid_lbl = QLabel("UID: --")
        self.dev_uid_lbl.setStyleSheet("color: #38bdf8; font-family: monospace; font-size: 12px;")
        self.dev_status_pill = QLabel("STATUS: --")
        self.dev_status_pill.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        
        dev_h_layout.addWidget(self.dev_title_lbl)
        dev_h_layout.addWidget(self.dev_uid_lbl)
        dev_h_layout.addWidget(self.dev_status_pill)
        right_layout.addWidget(self.dev_header_card)
        
        # Component Cards
        # 1. RF Amplitude Calibration Card
        self.rf_card = self._create_component_card(
            title="RF Amplitude Calibration (*_rfacal.txt)",
            cal_key="rfacal",
            desc="Broadband RF frontend flatness & gain correction table.",
            replace_slot=lambda: self._on_assign_file("rfacal")
        )
        right_layout.addWidget(self.rf_card)
        
        # 2. IF Amplitude Calibration Card
        self.if_card = self._create_component_card(
            title="IF Amplitude Calibration (*_ifacal.txt)",
            cal_key="ifacal",
            desc="Intermediate frequency analog filter shape compensation.",
            replace_slot=lambda: self._on_assign_file("ifacal")
        )
        right_layout.addWidget(self.if_card)
        
        # 3. Hardware Configuration Card
        self.cfg_card = self._create_component_card(
            title="Hardware Configuration (*_config.txt)",
            cal_key="config",
            desc="External amplitude compensation and active module linkage map.",
            replace_slot=lambda: self._on_assign_file("config")
        )
        right_layout.addWidget(self.cfg_card)
        
        # 4. Compensation & Licenses Card
        self.aux_card = QFrame()
        self.aux_card.setObjectName("cardFrame")
        aux_layout = QVBoxLayout(self.aux_card)
        aux_layout.setContentsMargins(12, 10, 12, 10)
        aux_layout.setSpacing(6)
        
        aux_header = QHBoxLayout()
        aux_title = QLabel("Auxiliary Files (*ampcomp.txt, *.lic)")
        aux_title.setStyleSheet("color: #f0f6fc; font-size: 12px; font-weight: 600;")
        self.aux_count_lbl = QLabel("0 files")
        self.aux_count_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        aux_header.addWidget(aux_title)
        aux_header.addStretch()
        aux_header.addWidget(self.aux_count_lbl)
        aux_layout.addLayout(aux_header)
        
        self.aux_list_lbl = QLabel("No auxiliary files attached.")
        self.aux_list_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        aux_layout.addWidget(self.aux_list_lbl)
        right_layout.addWidget(self.aux_card)
        
        # Drop Zone
        self.drop_zone = DropZoneFrame(self)
        self.drop_zone.setMinimumHeight(80)
        self.drop_zone.files_dropped.connect(self._on_files_dropped)
        right_layout.addWidget(self.drop_zone)
        
        right_layout.addStretch()
        right_scroll.setWidget(right_widget)
        splitter.addWidget(right_scroll)
        
        splitter.setSizes([380, 560])
        main_layout.addWidget(splitter)
        
        # Bottom Controls
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)
        
        self.status_msg_lbl = QLabel("Ready")
        self.status_msg_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        footer_layout.addWidget(self.status_msg_lbl)
        footer_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        
        self.stage_btn = QPushButton("Deploy && Stage for Hardware")
        self.stage_btn.setObjectName("primaryActionBtn")
        self.stage_btn.clicked.connect(self._on_stage_active)
        
        footer_layout.addWidget(close_btn)
        footer_layout.addWidget(self.stage_btn)
        main_layout.addLayout(footer_layout)

    def _create_component_card(self, title: str, cal_key: str, desc: str, replace_slot) -> QFrame:
        card = QFrame()
        card.setObjectName("cardFrame")
        card.setProperty("cal_key", cal_key)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        header = QHBoxLayout()
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("color: #f0f6fc; font-size: 12px; font-weight: 600;")
        status_badge = QLabel("[MISSING]")
        status_badge.setObjectName("badge_missing")
        status_badge.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700;")
        header.addWidget(t_lbl)
        header.addStretch()
        header.addWidget(status_badge)
        layout.addLayout(header)
        
        d_lbl = QLabel(desc)
        d_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(d_lbl)
        
        detail_box = QHBoxLayout()
        info_lbl = QLabel("File: Not Loaded")
        info_lbl.setObjectName("info_label")
        info_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-family: monospace;")
        assign_btn = QPushButton("Assign File...")
        assign_btn.setMaximumWidth(120)
        assign_btn.clicked.connect(replace_slot)
        detail_box.addWidget(info_lbl)
        detail_box.addStretch()
        detail_box.addWidget(assign_btn)
        layout.addLayout(detail_box)
        
        setattr(self, f"{cal_key}_badge", status_badge)
        setattr(self, f"{cal_key}_info", info_lbl)
        return card

    def _populate_devices_table(self):
        self.devices_table.setRowCount(0)
        devices = self.cal_manager.get_all_devices()
        
        selected_row = -1
        for row, dev in enumerate(devices):
            self.devices_table.insertRow(row)
            
            alias_item = QTableWidgetItem(f"{dev['alias']} (Model {dev['model_str']})")
            uid_item = QTableWidgetItem(dev['uid_str'])
            uid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            st = dev['status']
            if st == "calibrated":
                status_text = "[OK] Calibrated"
                status_color = QColor("#10b981")
            elif st == "incomplete":
                status_text = "[!] Incomplete"
                status_color = QColor("#f59e0b")
            else:
                status_text = "[-] Missing Cal"
                status_color = QColor("#f43f5e")
                
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(status_color)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            alias_item.setData(Qt.ItemDataRole.UserRole, dev)
            self.devices_table.setItem(row, 0, alias_item)
            self.devices_table.setItem(row, 1, uid_item)
            self.devices_table.setItem(row, 2, status_item)
            
            # Check if this matches target
            if self.target_uid is not None:
                t_uid_str = f"{int(self.target_uid):016x}" if isinstance(self.target_uid, (int, str)) and str(self.target_uid).isdigit() else str(self.target_uid).lower()
                if dev['uid_str'].lower() == t_uid_str:
                    selected_row = row
                    
        if selected_row >= 0:
            self.devices_table.selectRow(selected_row)
        elif self.devices_table.rowCount() > 0:
            self.devices_table.selectRow(0)
        else:
            self._clear_inspector()

    def _on_device_selection_changed(self):
        selected_rows = self.devices_table.selectionModel().selectedRows()
        if not selected_rows:
            self._clear_inspector()
            return
            
        row = selected_rows[0].row()
        item = self.devices_table.item(row, 0)
        if item:
            dev = item.data(Qt.ItemDataRole.UserRole)
            self.selected_device = dev
            self._update_inspector(dev)

    def _clear_inspector(self):
        self.selected_device = None
        self.dev_title_lbl.setText("No Analyzer Selected")
        self.dev_uid_lbl.setText("UID: --")
        self.dev_status_pill.setText("STATUS: --")
        self.dev_status_pill.setStyleSheet("color: #8b949e; font-size: 11px;")
        
        for key in ("rfacal", "ifacal", "config"):
            badge = getattr(self, f"{key}_badge", None)
            info = getattr(self, f"{key}_info", None)
            if badge:
                badge.setText("[MISSING]")
                badge.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700;")
            if info:
                info.setText("File: Not Loaded")
                info.setStyleSheet("color: #8b949e; font-size: 11px;")
                
        self.aux_count_lbl.setText("0 files")
        self.aux_list_lbl.setText("No auxiliary files attached.")
        self.stage_btn.setEnabled(False)

    def _update_inspector(self, dev: dict):
        self.dev_title_lbl.setText(f"{dev['alias']} (Model {dev['model_str']})")
        self.dev_uid_lbl.setText(f"Serial Number: {dev['uid_str']}")
        
        st = dev['status']
        if st == "calibrated":
            self.dev_status_pill.setText("STATUS: [OK] FULLY CALIBRATED")
            self.dev_status_pill.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 700;")
            self.stage_btn.setEnabled(True)
        elif st == "incomplete":
            self.dev_status_pill.setText("STATUS: [!] PARTIAL / INCOMPLETE CALIBRATION")
            self.dev_status_pill.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: 700;")
            self.stage_btn.setEnabled(True)
        else:
            self.dev_status_pill.setText("STATUS: [-] MISSING CALIBRATION FILES")
            self.dev_status_pill.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700;")
            self.stage_btn.setEnabled(False)

        # Update RF Card
        rf = dev.get("rfacal", {})
        if rf.get("present"):
            self.rfacal_badge.setText("[LOADED]")
            self.rfacal_badge.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 700;")
            kb = rf['size_bytes'] / 1024.0
            self.rfacal_info.setText(f"{rf['filename']} ({rf['points']} points, {kb:.1f} KB)")
            self.rfacal_info.setStyleSheet("color: #f0f6fc; font-size: 11px; font-family: monospace;")
        else:
            self.rfacal_badge.setText("[MISSING]")
            self.rfacal_badge.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700;")
            self.rfacal_info.setText("File: Not Loaded")
            self.rfacal_info.setStyleSheet("color: #8b949e; font-size: 11px;")

        # Update IF Card
        ifa = dev.get("ifacal", {})
        if ifa.get("present"):
            self.ifacal_badge.setText("[LOADED]")
            self.ifacal_badge.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 700;")
            kb = ifa['size_bytes'] / 1024.0
            self.ifacal_info.setText(f"{ifa['filename']} ({ifa['points']} points, {kb:.1f} KB)")
            self.ifacal_info.setStyleSheet("color: #f0f6fc; font-size: 11px; font-family: monospace;")
        else:
            self.ifacal_badge.setText("[MISSING]")
            self.ifacal_badge.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700;")
            self.ifacal_info.setText("File: Not Loaded")
            self.ifacal_info.setStyleSheet("color: #8b949e; font-size: 11px;")

        # Update Config Card
        cfg = dev.get("config", {})
        if cfg.get("present"):
            self.config_badge.setText("[LOADED]")
            self.config_badge.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 700;")
            amp_str = ", ".join(cfg['ampcomp_links']) if cfg.get('ampcomp_links') else "Standard"
            self.config_info.setText(f"{cfg['filename']} (AmpComp: {amp_str})")
            self.config_info.setStyleSheet("color: #f0f6fc; font-size: 11px; font-family: monospace;")
        else:
            self.config_badge.setText("[MISSING]")
            self.config_badge.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: 700;")
            self.config_info.setText("File: Not Loaded (Default fallback used)")
            self.config_info.setStyleSheet("color: #8b949e; font-size: 11px;")

        # Update Aux files
        aux_files = dev.get("ampcomp_files", []) + dev.get("license_files", []) + dev.get("other_files", [])
        self.aux_count_lbl.setText(f"{len(aux_files)} files")
        if aux_files:
            names = [f"{af['filename']} ({af['size_bytes']/1024.0:.1f} KB)" for af in aux_files]
            self.aux_list_lbl.setText(" • ".join(names))
            self.aux_list_lbl.setStyleSheet("color: #f0f6fc; font-size: 11px;")
        else:
            self.aux_list_lbl.setText("No auxiliary ampcomp or license files attached.")
            self.aux_list_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")

    def _on_import_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Calibration Directory")
        if d:
            count, files = self.cal_manager.import_from_directory(d)
            if count > 0:
                self.status_msg_lbl.setText(f"Successfully imported {count} calibration file(s).")
                self._populate_devices_table()
            else:
                QMessageBox.warning(self, "No Calibration Files", "No recognized calibration files found in selected directory.")

    def _on_assign_file(self, cal_type: str):
        if not self.selected_device:
            QMessageBox.information(self, "Select Analyzer", "Please select or create an analyzer first.")
            return
            
        fn, _ = QFileDialog.getOpenFileName(self, f"Select {cal_type.upper()} Calibration File", "", "Calibration Files (*.txt *.lic);;All Files (*)")
        if fn:
            m = self.selected_device["model"]
            u = self.selected_device["uid"]
            ok = self.cal_manager.import_single_file_as(fn, cal_type, m, u)
            if ok:
                self.status_msg_lbl.setText(f"Updated {cal_type.upper()} calibration file.")
                self._refresh_selected_device()
            else:
                QMessageBox.critical(self, "Import Error", f"Failed to save {cal_type} calibration file.")

    def _on_files_dropped(self, file_paths: list):
        if self.selected_device:
            m = self.selected_device["model"]
            u = self.selected_device["uid"]
            ok, msg = self.cal_manager.import_files_for_device(file_paths, m, u)
            self.status_msg_lbl.setText(msg)
            self._refresh_selected_device()
        else:
            # Try auto-importing across library
            count = 0
            for fp in file_paths:
                p = Path(fp)
                if p.is_dir():
                    c, _ = self.cal_manager.import_from_directory(str(p))
                    count += c
                elif p.is_file():
                    c, _ = self.cal_manager.import_from_directory(str(p.parent))
                    count += c
                    break
            self.status_msg_lbl.setText(f"Imported {count} file(s) into calibration library.")
            self._populate_devices_table()

    def _refresh_selected_device(self):
        if not self.selected_device:
            self._populate_devices_table()
            return
        m = self.selected_device["model"]
        u = self.selected_device["uid"]
        self.target_uid = u
        self._populate_devices_table()

    def _on_rename_alias(self):
        if not self.selected_device:
            return
        current_alias = self.selected_device.get("alias", "")
        new_alias, ok = QInputDialog.getText(self, "Rename Analyzer Alias", "Enter custom alias for this analyzer:", text=current_alias)
        if ok and new_alias.strip():
            m = self.selected_device["model"]
            u = self.selected_device["uid"]
            self.cal_manager.set_device_alias(m, u, new_alias)
            self._refresh_selected_device()

    def _on_export_calibration(self):
        if not self.selected_device:
            return
        d = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if d:
            m = self.selected_device["model"]
            u = self.selected_device["uid"]
            ok, msg = self.cal_manager.export_calibration(m, u, d)
            if ok:
                QMessageBox.information(self, "Export Complete", msg)
            else:
                QMessageBox.warning(self, "Export Failed", msg)

    def _on_delete_calibration(self):
        if not self.selected_device:
            return
        alias = self.selected_device.get("alias", "Analyzer")
        uid_str = self.selected_device.get("uid_str", "")
        reply = QMessageBox.critical(
            self,
            "Confirm Calibration Deletion",
            f"Permanently delete all calibration data for '{alias}' (SN: {uid_str})?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            m = self.selected_device["model"]
            u = self.selected_device["uid"]
            self.cal_manager.delete_calibration(m, u)
            self._populate_devices_table()

    def _on_stage_active(self):
        if not self.selected_device:
            return
        m = self.selected_device["model"]
        u = self.selected_device["uid"]
        ok = self.cal_manager.deploy_cal_files(m, u)
        if ok:
            self.status_msg_lbl.setText(f"Calibration staged to active runtime stage for Analyzer {m:03d}_{u:016x}.")
            self.accept()
        else:
            QMessageBox.warning(self, "Staging Failed", "Failed to stage calibration files.")


class DragDropCalDialog(QDialog):
    """
    Ingestion dialog for backward compatibility.
    """
    def __init__(self, model=None, uid=None, parent=None):
        super().__init__(parent)
        self.mgr_dlg = CalibrationManagerDialog(selected_model=model, selected_uid=uid, parent=parent)
        
    def exec(self):
        return self.mgr_dlg.exec()


class ClearCalDialog(QDialog):
    """
    Clear calibration dialog for backward compatibility.
    """
    def __init__(self, calibrations, parent=None):
        super().__init__(parent)
        self.mgr_dlg = CalibrationManagerDialog(parent=parent)
        
    def exec(self):
        return self.mgr_dlg.exec()

