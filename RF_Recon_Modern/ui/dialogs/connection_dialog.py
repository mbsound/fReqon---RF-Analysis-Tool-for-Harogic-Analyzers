"""
connection_dialog.py - Harogic Spectrum Analyzer Multi-Device Connection Manager Dialog.
Supports Single Analyzer, Split-Span Cooperative Sweep, Antenna Diversity, and Multi-Zone topologies.
Configures USB and Network/Ethernet slots, IP/Port, and subnet device assignment.
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QStackedWidget, QButtonGroup, QFrame,
    QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor
from core.device_controller import DeviceController
from core.multi_device_manager import MultiDeviceTopology

class NetworkScanThread(QThread):
    """
    Background worker thread to scan local network without blocking GUI.
    """
    scan_completed = pyqtSignal(list)

    def __init__(self, target_ip: str = None, target_mask: str = None, poll_all: bool = False, parent=None):
        super().__init__(parent)
        self.target_ip = target_ip
        self.target_mask = target_mask
        self.poll_all = poll_all

    def run(self):
        devices = DeviceController.scan_network_devices(
            target_ip=self.target_ip,
            target_mask=self.target_mask,
            poll_all=self.poll_all
        )
        self.scan_completed.emit(devices)


class UsbScanThread(QThread):
    """Lists the analyzers on USB without blocking the GUI (probing a serial port takes a moment)."""
    scan_completed = pyqtSignal(list)

    def run(self):
        self.scan_completed.emit(DeviceController.scan_usb_analyzers())


def usb_device_label(dev: dict) -> str:
    """One line for a scanned USB analyzer (see DeviceController.scan_usb_analyzers)."""
    if dev["kind"] == "harogic":
        ident = f"SN {dev['uid']:016x}" if dev.get("uid") else f"USB analyzer #{dev['usb_index'] + 1}"
        text = f"Harogic {dev['model']:03d} · {ident}"
    else:
        port = os.path.basename(dev["port"])
        if dev.get("error"):
            return f"{port} · cannot be opened"
        text = f"{dev.get('name') or 'Serial analyzer'} · {port}"
    if dev.get("in_use_by"):
        text += f"  (connected: {dev['in_use_by']})"
    elif dev.get("busy"):
        text += "  (in use by another program)"
    return text


class SlotConfigCard(QFrame):
    """
    Dedicated visual card for configuring an analyzer slot (USB or Ethernet).
    """
    rescanRequested = pyqtSignal()

    def __init__(self, slot_id: str, title: str, default_alias: str = "", is_default_enabled: bool = True, parent=None):
        super().__init__(parent)
        self.slot_id = slot_id
        self.setObjectName("cardFrame")
        self.setStyleSheet("""
            QFrame#cardFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Header Row
        header = QHBoxLayout()
        self.enable_cb = QCheckBox(title)
        self.enable_cb.setChecked(is_default_enabled)
        self.enable_cb.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 12px;")
        self.enable_cb.toggled.connect(self._on_enable_toggled)
        header.addWidget(self.enable_cb)
        
        header.addStretch()
        
        self.alias_edit = QLineEdit(default_alias)
        self.alias_edit.setPlaceholderText("Role Alias (e.g. UHF)")
        self.alias_edit.setMinimumWidth(180)
        self.alias_edit.setMaximumWidth(220)
        self.alias_edit.setFixedHeight(26)
        header.addWidget(self.alias_edit)
        layout.addLayout(header)
        
        # Body Container
        self.body_widget = QWidget()
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(6)
        
        # Interface Switcher
        intf_row = QHBoxLayout()
        intf_lbl = QLabel("Interface:")
        intf_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        intf_row.addWidget(intf_lbl)
        
        self.intf_group = QButtonGroup(self)
        self.btn_usb = QPushButton("USB Direct")
        self.btn_usb.setObjectName("pillBtn")
        self.btn_usb.setCheckable(True)
        self.btn_usb.setChecked(True if slot_id == "slot_a" else False)
        self.btn_usb.setFixedHeight(24)
        
        self.btn_net = QPushButton("Ethernet / IP")
        self.btn_net.setObjectName("pillBtn")
        self.btn_net.setCheckable(True)
        self.btn_net.setChecked(True if slot_id == "slot_b" else False)
        self.btn_net.setFixedHeight(24)
        
        self.intf_group.addButton(self.btn_usb, 0)
        self.intf_group.addButton(self.btn_net, 1)
        self.intf_group.idClicked.connect(self._on_intf_changed)
        
        intf_row.addWidget(self.btn_usb)
        intf_row.addWidget(self.btn_net)
        intf_row.addStretch()
        body_layout.addLayout(intf_row)
        
        # Details Stack
        self.details_stack = QStackedWidget()
        
        # USB Options: pick from the analyzers found on USB
        usb_w = QWidget()
        usb_v = QVBoxLayout(usb_w)
        usb_v.setContentsMargins(0, 0, 0, 0)
        usb_v.setSpacing(3)
        usb_l = QHBoxLayout()
        usb_l.setSpacing(6)
        usb_lbl = QLabel("Analyzer:")
        usb_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 500;")
        self.usb_combo = QComboBox()
        self.usb_combo.setMinimumWidth(180)
        self.usb_combo.setFixedHeight(26)
        self.usb_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.usb_combo.setToolTip("The analyzers found on USB: Harogic analyzers and tinySA / tinySA Ultra units.\n"
                                  "Automatic takes them in the order found (Harogic analyzers first).")
        self.usb_rescan_btn = QPushButton("Rescan")
        self.usb_rescan_btn.setFixedHeight(24)
        self.usb_rescan_btn.setToolTip("Look again for analyzers on USB")
        self.usb_rescan_btn.clicked.connect(self.rescanRequested.emit)
        usb_l.addWidget(usb_lbl)
        usb_l.addWidget(self.usb_combo, 1)
        usb_l.addWidget(self.usb_rescan_btn)
        usb_v.addLayout(usb_l)
        self.usb_status_lbl = QLabel("Looking for USB analyzers…")
        self.usb_status_lbl.setWordWrap(True)
        self.usb_status_lbl.setStyleSheet("color: #6e7681; font-size: 10px;")
        usb_v.addWidget(self.usb_status_lbl)
        self.details_stack.addWidget(usb_w)
        # What the slot is set to (kept while the scan runs, and when that analyzer is not plugged in)
        self._auto_index = 0 if slot_id == "slot_a" else 1
        self._usb_choice = None         # None: automatic; else the chosen device (as scanned)
        self._usb_devices = []
        self._usb_scanned = False
        self.usb_combo.addItem(self._auto_label(), None)
        self.usb_combo.activated.connect(self._on_usb_picked)
        
        # Network Options
        net_w = QWidget()
        net_l = QHBoxLayout(net_w)
        net_l.setContentsMargins(0, 0, 0, 0)
        net_l.setSpacing(6)
        
        ip_lbl = QLabel("IP / Host:")
        ip_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.ip_edit = QLineEdit("192.168.1.50" if slot_id == "slot_a" else "192.168.1.51")
        self.ip_edit.setPlaceholderText("IP Address or Hostname (e.g. nxe.local)")
        self.ip_edit.setMinimumWidth(140)
        self.ip_edit.setFixedHeight(26)
        
        port_lbl = QLabel("Port:")
        port_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(5000)
        self.port_spin.setFixedWidth(100)
        self.port_spin.setFixedHeight(26)
        self.port_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        net_l.addWidget(ip_lbl)
        net_l.addWidget(self.ip_edit)
        net_l.addWidget(port_lbl)
        net_l.addWidget(self.port_spin)
        self.details_stack.addWidget(net_w)
        
        body_layout.addWidget(self.details_stack)
        layout.addWidget(self.body_widget)
        
        # Target Hardware Metadata
        self.target_model = None
        self.target_uid = None
        
        # Set initial interface page
        self._on_intf_changed(0 if slot_id == "slot_a" else 1)
        self._on_enable_toggled(is_default_enabled)

    def _on_enable_toggled(self, enabled: bool):
        self.body_widget.setEnabled(enabled)
        self.alias_edit.setEnabled(enabled)

    def _on_intf_changed(self, btn_id: int):
        self.details_stack.setCurrentIndex(btn_id)

    # --- USB analyzer choice ---
    def _auto_label(self) -> str:
        return f"Automatic (USB analyzer #{self._auto_index + 1})"

    @staticmethod
    def _same_device(a: dict, b: dict) -> bool:
        if a["kind"] != b["kind"]:
            return False
        if a["kind"] == "tinysa":
            return a["port"] == b["port"]
        if a.get("uid") and b.get("uid"):
            return a["uid"] == b["uid"]
        return a["usb_index"] == b["usb_index"] and a.get("model") == b.get("model")

    def set_usb_devices(self, devices: list, status: str, scanned: bool = None):
        """Fill the list with what the scan found, keeping this slot's choice selected.
        scanned: a scan has finished (so a choice that is not in the list is missing)."""
        if scanned is not None:
            self._usb_scanned = scanned
        self._usb_devices = list(devices)
        combo = self.usb_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(self._auto_label(), None)
        chosen = 0
        for dev in devices:
            combo.addItem(usb_device_label(dev), dev)
            if dev.get("error"):
                combo.model().item(combo.count() - 1).setEnabled(False)
                combo.setItemData(combo.count() - 1, dev["error"], Qt.ItemDataRole.ToolTipRole)
            elif self._usb_choice and self._same_device(dev, self._usb_choice):
                chosen = combo.count() - 1
        if self._usb_choice and not chosen:
            missing = "  (not found)" if self._usb_scanned else ""
            combo.addItem(usb_device_label(self._usb_choice) + missing, self._usb_choice)
            chosen = combo.count() - 1
        combo.setCurrentIndex(chosen)
        combo.blockSignals(False)
        self.usb_status_lbl.setText(status)

    def _on_usb_picked(self, index: int):
        self._usb_choice = self.usb_combo.itemData(index)

    def set_config(self, enabled: bool, alias: str, intf: str, ip: str, port: int, usb_idx: int, model=None, uid=None,
                   serial_port=None):
        self.enable_cb.setChecked(enabled)
        self.alias_edit.setText(alias)
        if intf.lower() == "network":
            self.btn_net.setChecked(True)
            self._on_intf_changed(1)
        else:
            self.btn_usb.setChecked(True)
            self._on_intf_changed(0)
        self.ip_edit.setText(ip)
        self.port_spin.setValue(port)
        self.target_model = model
        self.target_uid = uid
        # The USB analyzer this slot is pinned to, if any
        self._usb_choice = None
        if intf.lower() == "tinysa" and serial_port:
            self._usb_choice = {"kind": "tinysa", "port": serial_port, "name": "tinySA", "tinysa_index": usb_idx}
        elif intf.lower() == "usb" and uid:
            self._usb_choice = {"kind": "harogic", "usb_index": usb_idx, "model": model or 0, "uid": uid}
        else:
            self._auto_index = usb_idx
        self.set_usb_devices(self._usb_devices, self.usb_status_lbl.text())

    def get_config(self) -> dict:
        cfg = {
            "slot_id": self.slot_id,
            "enabled": self.enable_cb.isChecked(),
            "alias": self.alias_edit.text().strip(),
            "interface": "network" if self.btn_net.isChecked() else "usb",
            "ip": self.ip_edit.text().strip(),
            "port": self.port_spin.value(),
            "usb_index": self._auto_index,
            "target_model": self.target_model,
            "target_uid": self.target_uid,
            "serial_port": None,
        }
        if cfg["interface"] == "usb":
            # Automatic: the n-th USB analyzer. Otherwise the chosen one: a Harogic
            # analyzer by serial number (by index if the SDK gives none), a tinySA by port.
            dev = self._usb_choice
            cfg["target_model"] = cfg["target_uid"] = None
            if dev and dev["kind"] == "tinysa":
                cfg.update(interface="tinysa", serial_port=dev["port"], usb_index=dev.get("tinysa_index") or 0)
            elif dev:
                cfg.update(usb_index=dev["usb_index"], target_model=dev.get("model"), target_uid=dev.get("uid"))
        return cfg


class ConnectionDialog(QDialog):
    """
    Hardware Interface & Multi-Device Topology Connection Modal.
    """
    def __init__(self, manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analyzer Connection & Multi-Device Manager")
        self.setModal(True)
        self.resize(720, 620)
        self.manager = manager
        self.scan_thread = None
        self.usb_scan_thread = None
        self._usb_devices, self._usb_status, self._usb_scanned = [], "Looking for USB analyzers…", False
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # --- 1. OPERATING TOPOLOGY MODE SELECTOR ---
        topo_frame = QFrame()
        topo_frame.setObjectName("cardFrame")
        topo_frame.setStyleSheet("""
            QFrame#cardFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        topo_layout = QVBoxLayout(topo_frame)
        topo_layout.setContentsMargins(8, 8, 8, 8)
        topo_layout.setSpacing(6)
        
        topo_hdr = QHBoxLayout()
        topo_lbl = QLabel("MULTI-ANALYZER OPERATING TOPOLOGY:")
        topo_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        topo_hdr.addWidget(topo_lbl)
        topo_hdr.addStretch()
        topo_layout.addLayout(topo_hdr)
        
        self.topo_btn_group = QButtonGroup(self)
        topo_btns_layout = QHBoxLayout()
        topo_btns_layout.setSpacing(6)
        
        self.btn_single = QPushButton("Single Analyzer")
        self.btn_single.setObjectName("pillBtn")
        self.btn_single.setCheckable(True)
        
        self.btn_split = QPushButton("Split Span (2x Speed)")
        self.btn_split.setObjectName("pillBtn")
        self.btn_split.setCheckable(True)
        
        self.btn_diversity = QPushButton("Antenna Diversity (A/B)")
        self.btn_diversity.setObjectName("pillBtn")
        self.btn_diversity.setCheckable(True)
        
        self.btn_multizone = QPushButton("Multi-Zone (Roles)")
        self.btn_multizone.setObjectName("pillBtn")
        self.btn_multizone.setCheckable(True)
        
        self.topo_btn_group.addButton(self.btn_single, 0)
        self.topo_btn_group.addButton(self.btn_split, 1)
        self.topo_btn_group.addButton(self.btn_diversity, 2)
        self.btn_sensors = QPushButton("Sensor Network (N)")
        self.btn_sensors.setObjectName("pillBtn")
        self.btn_sensors.setCheckable(True)
        self.topo_btn_group.addButton(self.btn_multizone, 3)
        self.topo_btn_group.addButton(self.btn_sensors, 4)
        self.topo_btn_group.idClicked.connect(self._on_topology_button_clicked)
        
        topo_btns_layout.addWidget(self.btn_single)
        topo_btns_layout.addWidget(self.btn_split)
        topo_btns_layout.addWidget(self.btn_diversity)
        topo_btns_layout.addWidget(self.btn_multizone)
        topo_btns_layout.addWidget(self.btn_sensors)
        topo_layout.addLayout(topo_btns_layout)
        
        self.topo_desc_lbl = QLabel("Single analyzer active for standard RF sweeping.")
        self.topo_desc_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-style: italic;")
        topo_layout.addWidget(self.topo_desc_lbl)
        
        main_layout.addWidget(topo_frame)
        
        # --- 2. DUAL DEVICE SLOTS ---
        slots_layout = QHBoxLayout()
        slots_layout.setSpacing(10)
        
        self.card_a = SlotConfigCard("slot_a", "ANALYZER SLOT A", "", True, self)
        self.card_b = SlotConfigCard("slot_b", "ANALYZER SLOT B", "", False, self)
        
        slots_layout.addWidget(self.card_a)
        slots_layout.addWidget(self.card_b)
        main_layout.addLayout(slots_layout)
        # Sensor networks: further analyzers (C, D, ...) in a second row
        self.cards = {"slot_a": self.card_a, "slot_b": self.card_b}
        self.extra_slots_layout = QHBoxLayout()
        self.extra_slots_layout.setSpacing(10)
        main_layout.addLayout(self.extra_slots_layout)
        self.extra_row = QHBoxLayout()
        self.add_slot_btn = QPushButton("+ Add analyzer")
        self.add_slot_btn.setFixedHeight(24)
        self.add_slot_btn.clicked.connect(lambda: self._add_extra_card())
        self.remove_slot_btn = QPushButton("− Remove last")
        self.remove_slot_btn.setFixedHeight(24)
        self.remove_slot_btn.clicked.connect(self._remove_extra_card)
        self.extra_row.addWidget(self.add_slot_btn)
        self.extra_row.addWidget(self.remove_slot_btn)
        self.extra_row.addStretch()
        main_layout.addLayout(self.extra_row)
        self._set_extra_visible(False)
        if manager is not None:
            for sid in sorted(manager.slots):
                if sid not in self.cards:
                    self._add_extra_card(sid)
        
        # --- 3. DISCOVERY SUBNET CARD ---
        disc_card = QFrame()
        disc_card.setObjectName("cardFrame")
        disc_card.setStyleSheet("""
            QFrame#cardFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        disc_card_layout = QVBoxLayout(disc_card)
        disc_card_layout.setContentsMargins(8, 8, 8, 8)
        disc_card_layout.setSpacing(6)
        
        disc_header = QHBoxLayout()
        disc_title = QLabel("LOCAL NETWORK DISCOVERY")
        disc_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        disc_header.addWidget(disc_title)
        disc_header.addStretch()
        
        # One selector for however many analyzers the topology has (A and B, or sensors A to P)
        assign_lbl = QLabel("Assign selected to:")
        assign_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
        disc_header.addWidget(assign_lbl)
        self.assign_combo = QComboBox()
        self.assign_combo.setMinimumWidth(150)
        self.assign_combo.setToolTip("The analyzer slot that takes the device selected in the list below")
        disc_header.addWidget(self.assign_combo)
        self.assign_btn = QPushButton("Assign")
        self.assign_btn.setObjectName("pillBtn")
        self.assign_btn.setFixedHeight(22)
        self.assign_btn.clicked.connect(lambda: self._assign_selected_to_slot(self.assign_combo.currentData()))
        disc_header.addWidget(self.assign_btn)
        disc_card_layout.addLayout(disc_header)

        # Interface Selector & Scan Controls Row
        iface_row = QHBoxLayout()
        iface_lbl = QLabel("NIC:")
        iface_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        iface_row.addWidget(iface_lbl)

        self.iface_combo = QComboBox()
        self.iface_combo.setMinimumWidth(260)
        self.iface_combo.setFixedHeight(24)
        self.iface_combo.setStyleSheet("""
            QComboBox {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #c9d1d9;
                font-size: 11px;
                padding: 2px 8px;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
        """)
        iface_row.addWidget(self.iface_combo, 1)

        self.refresh_iface_btn = QPushButton()
        self.refresh_iface_btn.setObjectName("iconBtn")
        self.refresh_iface_btn.setText("Refresh")
        self.refresh_iface_btn.setToolTip("Reload Host Network Interfaces")
        self.refresh_iface_btn.setFixedHeight(24)
        self.refresh_iface_btn.clicked.connect(self._populate_network_interfaces)
        iface_row.addWidget(self.refresh_iface_btn)

        self.scan_all_cb = QCheckBox("Poll All Interfaces")
        self.scan_all_cb.setToolTip("Sequentially query every active network interface on this machine")
        self.scan_all_cb.setStyleSheet("""
            QCheckBox {
                color: #8b949e;
                font-size: 11px;
                font-weight: 600;
            }
            QCheckBox:checked {
                color: #38bdf8;
            }
        """)
        self.scan_all_cb.toggled.connect(self._on_scan_all_toggled)
        iface_row.addWidget(self.scan_all_cb)

        self.scan_btn = QPushButton("Scan Subnet")
        self.scan_btn.setObjectName("primaryActionBtn")
        self.scan_btn.setFixedHeight(24)
        self.scan_btn.setMinimumWidth(90)
        self.scan_btn.clicked.connect(self._start_network_scan)
        iface_row.addWidget(self.scan_btn)
        disc_card_layout.addLayout(iface_row)
        
        # Discovered Devices Table
        self.device_table = QTableWidget(0, 7)
        self.device_table.setHorizontalHeaderLabels(["Model", "Serial Number", "Host / Alias", "IP Address", "Mask", "NIC", "Calibration"])
        self.device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.device_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.device_table.setFixedHeight(115)
        disc_card_layout.addWidget(self.device_table)
        
        self.scan_status_lbl = QLabel("Ready to scan local network.")
        self.scan_status_lbl.setStyleSheet("color: #6e7681; font-size: 10px;")
        disc_card_layout.addWidget(self.scan_status_lbl)
        
        main_layout.addWidget(disc_card)
        
        # --- 4. PERSISTENCE & ACTIONS ---
        btn_layout = QHBoxLayout()
        self.remember_cb = QCheckBox("Remember multi-device configuration")
        self.remember_cb.setChecked(True)
        btn_layout.addWidget(self.remember_cb)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.connect_btn = QPushButton("Connect All Active")
        self.connect_btn.setObjectName("primaryActionBtn")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        btn_layout.addWidget(self.connect_btn)
        
        main_layout.addLayout(btn_layout)
        
        # Initialize from existing Manager state if present
        self._load_from_manager()
        self._populate_network_interfaces()
        for card in (self.card_a, self.card_b):     # sensor cards are hooked up as they are added
            card.rescanRequested.connect(self.scan_usb)
        self.scan_usb()

    # --- USB analyzers ---
    def scan_usb(self):
        """Look for analyzers on USB (in the background) and offer them in every slot."""
        if self.usb_scan_thread is not None and self.usb_scan_thread.isRunning():
            return
        self._usb_status = "Looking for USB analyzers…"
        for card in self.cards.values():
            card.usb_status_lbl.setText(self._usb_status)
            card.usb_rescan_btn.setEnabled(False)
        self.usb_scan_thread = UsbScanThread(self)
        self.usb_scan_thread.scan_completed.connect(self._on_usb_scan_completed)
        self.usb_scan_thread.start()

    def _on_usb_scan_completed(self, devices: list):
        # Name the analyzers that connected slots already hold: a tinySA's port is
        # busy (it cannot be asked what it is), and it helps to see which is which
        for dev in devices:
            for slot_id, slot in (self.manager.slots.items() if self.manager else ()):
                if not slot.is_connected:
                    continue
                label = slot.role_alias.strip() or slot.name
                if dev["kind"] == "tinysa" and slot.device_description.get("port") == dev["port"]:
                    dev["in_use_by"] = label
                    dev["name"] = (slot.capabilities or {}).get("name", "tinySA")
                elif dev["kind"] == "harogic" and dev.get("uid") and dev["uid"] == slot.detected_uid:
                    dev["in_use_by"] = label
        usable = [d for d in devices if not d.get("error")]
        harogic = sum(d["kind"] == "harogic" for d in usable)
        tinysa = sum(d["kind"] == "tinysa" for d in usable)
        if usable:
            parts = ([f"{harogic} Harogic"] if harogic else []) + ([f"{tinysa} tinySA"] if tinysa else [])
            status = "Found on USB: " + ", ".join(parts) + "."
        else:
            status = "No USB analyzers found. Check the cable and power, then Rescan."
        errors = [d["error"] for d in devices if d.get("error")]
        if errors:
            status += " " + errors[0]
        self._usb_devices, self._usb_status, self._usb_scanned = devices, status, True
        for card in self.cards.values():
            card.set_usb_devices(devices, status, scanned=True)
            card.usb_rescan_btn.setEnabled(True)

    def done(self, result):
        if self.usb_scan_thread is not None:
            self.usb_scan_thread.wait(3000)     # a scan in progress must not outlive the dialog
        super().done(result)

    def _load_from_manager(self):
        if not self.manager:
            self.btn_single.setChecked(True)
            self._on_topology_button_clicked(0)
            return
            
        topo = self.manager.topology
        if topo == MultiDeviceTopology.SPLIT_SWEEP:
            self.btn_split.setChecked(True)
            self._on_topology_button_clicked(1)
        elif topo == MultiDeviceTopology.DIVERSITY:
            self.btn_diversity.setChecked(True)
            self._on_topology_button_clicked(2)
        elif topo == MultiDeviceTopology.INDEPENDENT:
            self.btn_multizone.setChecked(True)
            self._on_topology_button_clicked(3)
        elif topo == MultiDeviceTopology.SENSOR_NET:
            self.btn_sensors.setChecked(True)
            self._on_topology_button_clicked(4)
        else:
            self.btn_single.setChecked(True)
            self._on_topology_button_clicked(0)
            
        slot_a = self.manager.slots.get("slot_a")
        if slot_a:
            self.card_a.set_config(
                slot_a.is_enabled, slot_a.role_alias, slot_a.interface_type,
                slot_a.ip_address, slot_a.port, slot_a.usb_index,
                slot_a.target_model, slot_a.target_uid, slot_a.serial_port
            )
            
        slot_b = self.manager.slots.get("slot_b")
        if slot_b:
            self.card_b.set_config(
                slot_b.is_enabled, slot_b.role_alias, slot_b.interface_type,
                slot_b.ip_address, slot_b.port, slot_b.usb_index,
                slot_b.target_model, slot_b.target_uid, slot_b.serial_port
            )

    def _set_extra_visible(self, visible: bool):
        for sid, card in self.cards.items():
            if sid not in ("slot_a", "slot_b"):
                card.setVisible(visible)
        for w in (self.add_slot_btn, self.remove_slot_btn):
            w.setVisible(visible)

    def _add_extra_card(self, slot_id: str = None):
        if slot_id is None:
            n = len(self.cards)
            if n >= 16:
                return
            slot_id = f"slot_{chr(ord('a') + n)}"
        if slot_id in self.cards:
            return
        letter = slot_id.split("_")[-1].upper()
        card = SlotConfigCard(slot_id, f"SENSOR {letter}", "", True, self)
        card.btn_net.setChecked(True); card._on_intf_changed(1)
        card.ip_edit.setText(f"192.168.1.{50 + len(self.cards)}")
        if self.manager is not None:
            slot = self.manager.ensure_slot(slot_id)
            card.set_config(slot.is_enabled or True, slot.role_alias, slot.interface_type, slot.ip_address,
                            slot.port, slot.usb_index, slot.target_model, slot.target_uid, slot.serial_port)
        else:
            card._auto_index = len(self.cards)
        card.set_usb_devices(self._usb_devices, self._usb_status, scanned=self._usb_scanned)
        card.rescanRequested.connect(self.scan_usb)
        self.cards[slot_id] = card
        self.extra_slots_layout.addWidget(card)
        card.setVisible(getattr(self, "selected_topology", None) == MultiDeviceTopology.SENSOR_NET)
        self._refresh_assign_targets()

    def _remove_extra_card(self):
        extra = [sid for sid in self.cards if sid not in ("slot_a", "slot_b")]
        if not extra:
            return
        sid = sorted(extra)[-1]
        card = self.cards.pop(sid)
        self.extra_slots_layout.removeWidget(card); card.deleteLater()
        if self.manager is not None:
            self.manager.remove_slot(sid)
        self._refresh_assign_targets()

    def _refresh_assign_targets(self):
        """The slots a discovered analyzer can be assigned to: those the chosen topology uses."""
        combo = getattr(self, "assign_combo", None)
        if combo is None:
            return                          # the discovery card is built after the slot cards
        topo = getattr(self, "selected_topology", MultiDeviceTopology.SINGLE)
        if topo == MultiDeviceTopology.SINGLE:
            wanted = ["slot_a"]
        elif topo == MultiDeviceTopology.SENSOR_NET:
            wanted = sorted(self.cards)
        else:
            wanted = ["slot_a", "slot_b"]
        keep = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for sid in wanted:
            card = self.cards.get(sid)
            if card is None:
                continue
            label = card.enable_cb.text().title()
            alias = card.alias_edit.text().strip()
            combo.addItem(f"{label} ({alias})" if alias else label, sid)
        i = combo.findData(keep)
        if i < 0:
            # The first slot that has not been given a network analyzer yet, else the first
            i = next((k for k in range(combo.count())
                      if not self.cards[combo.itemData(k)].btn_net.isChecked()), 0)
        combo.setCurrentIndex(max(0, i))
        combo.blockSignals(False)

    def _on_topology_button_clicked(self, btn_id: int):
        self._set_extra_visible(btn_id == 4)
        if btn_id == 1:
            self.selected_topology = MultiDeviceTopology.SPLIT_SWEEP
            self.topo_desc_lbl.setText("Split Span: Automatically divides wide sweep spans across 2 analyzers on the same antenna, doubling sweep frame rate (2x speed).")
            self.card_a.enable_cb.setText("ANALYZER SLOT A")
            self.card_a.alias_edit.setPlaceholderText("Role Alias (e.g. Low Band)")
            self.card_a.enable_cb.setChecked(True)
            self.card_a.show()
            self.card_b.enable_cb.setText("ANALYZER SLOT B")
            self.card_b.alias_edit.setPlaceholderText("Role Alias (e.g. High Band)")
            self.card_b.enable_cb.setChecked(True)
            self.card_b.show()
            self.connect_btn.setText("Connect All Active")
        elif btn_id == 2:
            self.selected_topology = MultiDeviceTopology.DIVERSITY
            self.topo_desc_lbl.setText("Antenna Diversity: Sends identical frequency span to co-located analyzers on different antennas for instant A/B switching and Dual Overlay.")
            self.card_a.enable_cb.setText("ANALYZER SLOT A")
            self.card_a.alias_edit.setPlaceholderText("Role Alias (e.g. Ant Main)")
            self.card_a.enable_cb.setChecked(True)
            self.card_a.show()
            self.card_b.enable_cb.setText("ANALYZER SLOT B")
            self.card_b.alias_edit.setPlaceholderText("Role Alias (e.g. Ant Aux)")
            self.card_b.enable_cb.setChecked(True)
            self.card_b.show()
            self.connect_btn.setText("Connect All Active")
        elif btn_id == 4:
            self.selected_topology = MultiDeviceTopology.SENSOR_NET
            self.topo_desc_lbl.setText("Sensor Network: any number of analyzers sweep the same span from known "
                                       "positions; the Locate mode estimates where each carrier is and what it is.")
            for sid, card in self.cards.items():
                card.enable_cb.setText(f"SENSOR {sid.split('_')[-1].upper()}")
                card.alias_edit.setPlaceholderText("Sensor name (e.g. Stage Left)")
                card.show()
            self.card_a.enable_cb.setChecked(True)
            self.connect_btn.setText("Connect All Sensors")
        elif btn_id == 3:
            self.selected_topology = MultiDeviceTopology.INDEPENDENT
            self.topo_desc_lbl.setText("Multi-Zone Roles: Analyzers run completely independent frequency ranges and parameters, routing directly to bound analysis modules.")
            self.card_a.enable_cb.setText("ANALYZER SLOT A")
            self.card_a.alias_edit.setPlaceholderText("Role Alias (e.g. UHF)")
            self.card_a.enable_cb.setChecked(True)
            self.card_a.show()
            self.card_b.enable_cb.setText("ANALYZER SLOT B")
            self.card_b.alias_edit.setPlaceholderText("Role Alias (e.g. DECT / ShowLink)")
            self.card_b.enable_cb.setChecked(True)
            self.card_b.show()
            self.connect_btn.setText("Connect All Active")
        else:
            self.selected_topology = MultiDeviceTopology.SINGLE
            self.topo_desc_lbl.setText("Single Analyzer: Standard operation with one primary hardware analyzer.")
            self.card_a.enable_cb.setText("PRIMARY ANALYZER")
            self.card_a.alias_edit.setPlaceholderText("Optional Alias (e.g. Main Rx)")
            self.card_a.enable_cb.setChecked(True)
            self.card_a.show()
            self.card_b.enable_cb.setChecked(False)
            self.card_b.hide()
            self.connect_btn.setText("Connect Analyzer")
        self._refresh_assign_targets()

    def _populate_network_interfaces(self):
        """
        Query system for network interfaces and update iface_combo.
        """
        curr_selected = self.iface_combo.currentData()
        self.iface_combo.clear()
        
        interfaces = DeviceController.get_local_network_interfaces()
        
        if not interfaces:
            self.iface_combo.addItem("No active network interfaces detected", None)
            return

        # Sort interfaces: UP state first, then by name
        interfaces.sort(key=lambda x: (0 if x['state'].lower() == 'up' else 1, x['name']))

        for ifc in interfaces:
            # Display: enx207bd2942cf6 - 192.168.1.4 (UP)
            label = f"{ifc['name']} - {ifc['ip']} ({ifc['state'].upper()})"
            self.iface_combo.addItem(label, ifc)

        # Reselect if previously selected
        if curr_selected:
            for idx in range(self.iface_combo.count()):
                data = self.iface_combo.itemData(idx)
                if data and data.get('name') == curr_selected.get('name'):
                    self.iface_combo.setCurrentIndex(idx)
                    break

    def _on_scan_all_toggled(self, checked: bool):
        self.iface_combo.setEnabled(not checked)
        self.refresh_iface_btn.setEnabled(not checked)

    def _start_network_scan(self):
        self.scan_btn.setEnabled(False)
        self.device_table.setRowCount(0)
        
        poll_all = self.scan_all_cb.isChecked()
        target_ip = None
        target_mask = None
        
        if poll_all:
            self.scan_status_lbl.setText("Polling all active network interfaces for Harogic NX analyzers...")
        else:
            ifc = self.iface_combo.currentData()
            if ifc:
                target_ip = ifc.get('ip')
                target_mask = ifc.get('mask')
                self.scan_status_lbl.setText(f"Scanning {ifc.get('name')} ({target_ip}) for Harogic NX analyzers...")
            else:
                self.scan_status_lbl.setText("Scanning subnet for Harogic NX analyzers...")
                
        self.scan_status_lbl.setStyleSheet("color: #38bdf8; font-size: 10px;")
        
        self.scan_thread = NetworkScanThread(
            target_ip=target_ip,
            target_mask=target_mask,
            poll_all=poll_all,
            parent=self
        )
        self.scan_thread.scan_completed.connect(self._on_scan_completed)
        self.scan_thread.start()

    def _on_scan_completed(self, devices: list):
        self.scan_btn.setEnabled(True)
        self.device_table.setRowCount(len(devices))
        
        if not devices:
            if self.scan_all_cb.isChecked():
                self.scan_status_lbl.setText("No network analyzers discovered across all polled interfaces.")
            else:
                ifc = self.iface_combo.currentData()
                if_name = ifc.get('name') if ifc else "selected interface"
                self.scan_status_lbl.setText(f"No network analyzers discovered on {if_name}.")
            self.scan_status_lbl.setStyleSheet("color: #8b949e; font-size: 10px;")
            return
            
        self.scan_status_lbl.setText(f"Discovery complete. Found {len(devices)} network analyzer(s). Select a device to assign.")
        self.scan_status_lbl.setStyleSheet("color: #10b981; font-size: 10px;")
        
        for r_idx, dev in enumerate(devices):
            # Network scans can't identify the analyzer; it is read on connect
            m_item = QTableWidgetItem(f"Model {dev['model']:03d}" if dev.get('model') is not None else "Harogic")
            s_item = QTableWidgetItem(f"{dev['uid']:016x}" if dev.get('uid') is not None else "read on connect")
            h_text = dev.get('hostname') or dev.get('alias') or "--"
            h_item = QTableWidgetItem(h_text)
            ip_item = QTableWidgetItem(dev['ip'])
            mask_item = QTableWidgetItem(dev['mask'])
            nic_item = QTableWidgetItem(dev.get('interface', ''))
            
            is_cal = dev.get('is_calibrated', False)
            if is_cal is None:
                cal_item = QTableWidgetItem("Checked on connect")
                cal_item.setForeground(QColor("#8b949e"))
            elif is_cal:
                cal_item = QTableWidgetItem("[OK] Ready")
                cal_item.setForeground(QColor("#10b981"))
            else:
                cal_item = QTableWidgetItem("[!] Needs Cal")
                cal_item.setForeground(QColor("#f59e0b"))
                
            cal_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            nic_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            for it in (m_item, s_item, h_item, ip_item, mask_item, nic_item, cal_item):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
            m_item.setData(Qt.ItemDataRole.UserRole, dev)
            self.device_table.setItem(r_idx, 0, m_item)
            self.device_table.setItem(r_idx, 1, s_item)
            self.device_table.setItem(r_idx, 2, h_item)
            self.device_table.setItem(r_idx, 3, ip_item)
            self.device_table.setItem(r_idx, 4, mask_item)
            self.device_table.setItem(r_idx, 5, nic_item)
            self.device_table.setItem(r_idx, 6, cal_item)

    def _assign_selected_to_slot(self, target_slot_id: str):
        row = self.device_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Device", "Please select a discovered device from the table first.")
            return
            
        m_item = self.device_table.item(row, 0)
        if not m_item: return
        dev = m_item.data(Qt.ItemDataRole.UserRole)
        if not dev: return
        
        target_card = self.cards.get(target_slot_id)
        if target_card is None:
            return
        target_card.btn_net.setChecked(True)
        target_card._on_intf_changed(1)
        # Use hostname if available, else IP
        target_card.ip_edit.setText(dev.get('hostname') or dev['ip'])
        target_card.target_model = dev.get('model')
        target_card.target_uid = dev.get('uid')
        target_card.enable_cb.setChecked(True)
        
        assigned_name = dev.get('hostname') or dev['ip']
        what = f"Model {dev['model']:03d}" if dev.get('model') is not None else "analyzer"
        self.scan_status_lbl.setText(f"Assigned {what} ({assigned_name}) to {target_card.enable_cb.text()}.")
        self.scan_status_lbl.setStyleSheet("color: #38bdf8; font-size: 10px;")
        # Ready for the next one: the selector moves on to the following slot
        i = self.assign_combo.findData(target_slot_id)
        if 0 <= i < self.assign_combo.count() - 1:
            self.assign_combo.setCurrentIndex(i + 1)

    def _on_connect_clicked(self):
        self.accept()

    def get_multi_device_config(self) -> dict:
        return {
            "topology": getattr(self, "selected_topology", MultiDeviceTopology.SINGLE),
            "remember": self.remember_cb.isChecked(),
            "slots": {sid: card.get_config() for sid, card in self.cards.items()}
        }
