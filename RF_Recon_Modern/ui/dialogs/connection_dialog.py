"""
connection_dialog.py - Harogic Spectrum Analyzer Multi-Device Connection Manager Dialog.
Supports Single Analyzer, Split-Span Cooperative Sweep, Antenna Diversity, and Multi-Zone topologies.
Configures USB and Network/Ethernet slots, IP/Port, and subnet device assignment.
"""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QLineEdit, QSpinBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QStackedWidget, QButtonGroup,
    QFrame, QComboBox, QMessageBox, QTabWidget, QGroupBox
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


class SlotConfigCard(QFrame):
    """
    Dedicated visual card for configuring an analyzer slot (USB or Ethernet).
    """
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
        
        # USB Options
        usb_w = QWidget()
        usb_l = QHBoxLayout(usb_w)
        usb_l.setContentsMargins(0, 0, 0, 0)
        usb_l.setSpacing(8)
        u_idx_lbl = QLabel("USB Device Index:")
        u_idx_lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 500;")
        self.usb_index_spin = QSpinBox()
        self.usb_index_spin.setRange(0, 15)
        self.usb_index_spin.setValue(0 if slot_id == "slot_a" else 1)
        self.usb_index_spin.setFixedWidth(100)
        self.usb_index_spin.setFixedHeight(26)
        self.usb_index_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        usb_l.addWidget(u_idx_lbl)
        usb_l.addWidget(self.usb_index_spin)
        usb_l.addStretch()
        self.details_stack.addWidget(usb_w)
        
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

    def set_config(self, enabled: bool, alias: str, intf: str, ip: str, port: int, usb_idx: int, model=None, uid=None):
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
        self.usb_index_spin.setValue(usb_idx)
        self.target_model = model
        self.target_uid = uid

    def get_config(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "enabled": self.enable_cb.isChecked(),
            "alias": self.alias_edit.text().strip(),
            "interface": "network" if self.btn_net.isChecked() else "usb",
            "ip": self.ip_edit.text().strip(),
            "port": self.port_spin.value(),
            "usb_index": self.usb_index_spin.value(),
            "target_model": self.target_model,
            "target_uid": self.target_uid
        }


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
        self.topo_btn_group.addButton(self.btn_multizone, 3)
        self.topo_btn_group.idClicked.connect(self._on_topology_button_clicked)
        
        topo_btns_layout.addWidget(self.btn_single)
        topo_btns_layout.addWidget(self.btn_split)
        topo_btns_layout.addWidget(self.btn_diversity)
        topo_btns_layout.addWidget(self.btn_multizone)
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
        
        self.assign_a_btn = QPushButton("Assign to Slot A")
        self.assign_a_btn.setObjectName("pillBtn")
        self.assign_a_btn.setFixedHeight(22)
        self.assign_a_btn.clicked.connect(lambda: self._assign_selected_to_slot("slot_a"))
        disc_header.addWidget(self.assign_a_btn)
        
        self.assign_b_btn = QPushButton("Assign to Slot B")
        self.assign_b_btn.setObjectName("pillBtn")
        self.assign_b_btn.setFixedHeight(22)
        self.assign_b_btn.clicked.connect(lambda: self._assign_selected_to_slot("slot_b"))
        disc_header.addWidget(self.assign_b_btn)
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
        else:
            self.btn_single.setChecked(True)
            self._on_topology_button_clicked(0)
            
        slot_a = self.manager.slots.get("slot_a")
        if slot_a:
            self.card_a.set_config(
                slot_a.is_enabled, slot_a.role_alias, slot_a.interface_type,
                slot_a.ip_address, slot_a.port, slot_a.usb_index,
                slot_a.target_model, slot_a.target_uid
            )
            
        slot_b = self.manager.slots.get("slot_b")
        if slot_b:
            self.card_b.set_config(
                slot_b.is_enabled, slot_b.role_alias, slot_b.interface_type,
                slot_b.ip_address, slot_b.port, slot_b.usb_index,
                slot_b.target_model, slot_b.target_uid
            )

    def _on_topology_button_clicked(self, btn_id: int):
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
            self.assign_a_btn.setText("Assign to Slot A")
            self.assign_a_btn.show()
            self.assign_b_btn.setText("Assign to Slot B")
            self.assign_b_btn.show()
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
            self.assign_a_btn.setText("Assign to Slot A")
            self.assign_a_btn.show()
            self.assign_b_btn.setText("Assign to Slot B")
            self.assign_b_btn.show()
            self.connect_btn.setText("Connect All Active")
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
            self.assign_a_btn.setText("Assign to Slot A")
            self.assign_a_btn.show()
            self.assign_b_btn.setText("Assign to Slot B")
            self.assign_b_btn.show()
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
            self.assign_a_btn.setText("Assign to Analyzer")
            self.assign_a_btn.show()
            self.assign_b_btn.hide()
            self.connect_btn.setText("Connect Analyzer")

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
            m_item = QTableWidgetItem(f"Model {dev['model']:03d}")
            s_item = QTableWidgetItem(f"{dev['uid']:016x}")
            h_text = dev.get('hostname') or dev.get('alias') or "--"
            h_item = QTableWidgetItem(h_text)
            ip_item = QTableWidgetItem(dev['ip'])
            mask_item = QTableWidgetItem(dev['mask'])
            nic_item = QTableWidgetItem(dev.get('interface', ''))
            
            is_cal = dev.get('is_calibrated', False)
            if is_cal:
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
        
        target_card = self.card_a if target_slot_id == "slot_a" else self.card_b
        target_card.btn_net.setChecked(True)
        target_card._on_intf_changed(1)
        # Use hostname if available, else IP
        target_card.ip_edit.setText(dev.get('hostname') or dev['ip'])
        target_card.target_model = dev.get('model')
        target_card.target_uid = dev.get('uid')
        target_card.enable_cb.setChecked(True)
        
        assigned_name = dev.get('hostname') or dev['ip']
        self.scan_status_lbl.setText(f"Assigned Model {dev['model']:03d} ({assigned_name}) to {target_card.enable_cb.text()}.")
        self.scan_status_lbl.setStyleSheet("color: #38bdf8; font-size: 10px;")

    def _on_connect_clicked(self):
        self.accept()

    def get_multi_device_config(self) -> dict:
        return {
            "topology": getattr(self, "selected_topology", MultiDeviceTopology.SINGLE),
            "remember": self.remember_cb.isChecked(),
            "slots": {
                "slot_a": self.card_a.get_config(),
                "slot_b": self.card_b.get_config()
            }
        }
