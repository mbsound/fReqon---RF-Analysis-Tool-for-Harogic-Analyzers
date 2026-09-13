"""
threats_panel.py - Intruder Alerts, Soundbase JSON & Marker Hierarchy Panel.
Manages automated threat detection against unknown RF transmitters,
Soundbase frequency coordination JSON imports, and active channel markers.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QCheckBox, QDoubleSpinBox, QTableWidget, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QFrame, QScrollArea, QTableWidgetItem
)
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtCore import Qt, pyqtSignal

class NumericTableWidgetItem(QTableWidgetItem):
    """
    QTableWidgetItem subclass that sorts numerically based on UserRole data.
    """
    def __init__(self, text: str, sort_value: float):
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, float(sort_value))

    def __lt__(self, other):
        if other is not None:
            v1 = self.data(Qt.ItemDataRole.UserRole)
            v2 = other.data(Qt.ItemDataRole.UserRole)
            if v1 is not None and v2 is not None:
                try:
                    return float(v1) < float(v2)
                except (ValueError, TypeError):
                    pass
        return super().__lt__(other)

class ThreatsPanel(QWidget):
    """
    Intruder alert monitoring, Soundbase coordination file import, and marker management panel.
    """
    intruderAlertToggled = pyqtSignal(bool)
    intruderThresholdChanged = pyqtSignal(float)
    showThresholdToggled = pyqtSignal(bool)
    clearIntrudersClicked = pyqtSignal()
    addIntruderToMarkersClicked = pyqtSignal()
    loadSoundbaseClicked = pyqtSignal()
    markerItemChanged = pyqtSignal(object, int)
    carrierSelected = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        scroll.setWidget(container)
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        
        # Primary Action Button: Enable Intruder Detection
        self.enable_btn = QPushButton("Enable Intruder Detection")
        self.enable_btn.setObjectName("triggerBtn")
        self.enable_btn.setFixedHeight(34)
        self.enable_btn.setCheckable(True)
        self.enable_btn.setChecked(False)
        self._update_enable_btn_style()
        self.enable_btn.toggled.connect(self._on_enable_toggled)
        layout.addWidget(self.enable_btn)
        
        # Backward-compatible alias for any code checking .intruder_enable_cb
        self.intruder_enable_cb = self.enable_btn
        
        # --- 1. INTRUDER ALERT & THREATS CARD ---
        intr_card = self._create_card("INTRUDER THREAT DETECTION", layout)
        
        t_layout = QHBoxLayout()
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(6)
        
        t_lbl = QLabel("Threshold:")
        t_lbl.setStyleSheet("font-size: 11px;")
        
        self.show_thresh_cb = QCheckBox()
        self.show_thresh_cb.setChecked(True)
        self.show_thresh_cb.setToolTip("Display Threshold Line on Spectrum")
        self.show_thresh_cb.toggled.connect(self.showThresholdToggled.emit)
        
        self.intruder_thresh_spin = QDoubleSpinBox()
        self.intruder_thresh_spin.setRange(-150.0, 20.0)
        self.intruder_thresh_spin.setValue(-80.0)
        self.intruder_thresh_spin.setSuffix(" dBm")
        self.intruder_thresh_spin.valueChanged.connect(self.intruderThresholdChanged.emit)
        
        t_layout.addWidget(t_lbl)
        t_layout.addWidget(self.show_thresh_cb)
        t_layout.addWidget(self.intruder_thresh_spin, 1)
        intr_card.layout().addLayout(t_layout)
        
        self.intruder_table = QTableWidget(0, 3)
        self.intruder_table.setHorizontalHeaderLabels(["Freq (MHz)", "Power", "Signature"])
        self.intruder_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.intruder_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.intruder_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.intruder_table.setColumnWidth(0, 78)
        self.intruder_table.setColumnWidth(1, 78)
        self.intruder_table.verticalHeader().setVisible(False)
        self.intruder_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.intruder_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.intruder_table.setSortingEnabled(True)
        self.intruder_table.horizontalHeader().setSortIndicatorShown(True)
        self.intruder_table.horizontalHeader().setSortIndicator(1, Qt.SortOrder.DescendingOrder)
        self.intruder_table.setMinimumHeight(200)
        self.intruder_table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                gridline-color: #21262d;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                font-weight: 700;
                font-size: 10px;
                border: none;
                border-bottom: 1px solid #30363d;
                padding: 3px 2px;
            }
            QHeaderView::section:hover {
                background-color: #21262d;
                color: #f0f6fc;
            }
            QTableWidget::item {
                padding: 2px 3px;
            }
            QTableWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        intr_card.layout().addWidget(self.intruder_table)
        
        btn_layout = QHBoxLayout()
        self.clear_intr_btn = QPushButton("Clear Threats")
        self.clear_intr_btn.clicked.connect(self.clearIntrudersClicked.emit)
        
        self.add_marker_btn = QPushButton("Add to Markers...")
        self.add_marker_btn.clicked.connect(self.addIntruderToMarkersClicked.emit)
        
        btn_layout.addWidget(self.clear_intr_btn)
        btn_layout.addWidget(self.add_marker_btn)
        intr_card.layout().addLayout(btn_layout)
        
        # --- 2. SOUNDBASE JSON IMPORTS CARD ---
        json_card = self._create_card("FREQUENCY COORDINATION IMPORT", layout)
        
        self.btn_soundbase_json = QPushButton("Import Soundbase Site JSON")
        self.btn_soundbase_json.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                font-weight: 600;
                padding: 6px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #f0f6fc;
            }
        """)
        self.btn_soundbase_json.clicked.connect(self.loadSoundbaseClicked.emit)
        json_card.layout().addWidget(self.btn_soundbase_json)
        
        self.soundbase_status_lbl = QLabel("No coordination file active")
        self.soundbase_status_lbl.setStyleSheet("color: #6e7681; font-size: 10px; margin-top: 2px;")
        json_card.layout().addWidget(self.soundbase_status_lbl)
        
        # --- 3. MARKERS & CHANNELS CARD ---
        markers_card = self._create_card("MARKERS & CHANNEL MASKS", layout)
        
        self.markers_tree = QTreeWidget()
        self.markers_tree.setColumnCount(2)
        self.markers_tree.setHeaderLabels(["Item / Channel", "Freq (MHz)"])
        self.markers_tree.setHeaderHidden(False)
        self.markers_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.markers_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.markers_tree.setColumnWidth(1, 80)
        self.markers_tree.setIndentation(14)
        self.markers_tree.setMinimumHeight(240)
        self.markers_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                font-size: 11px;
                color: #c9d1d9;
            }
            QTreeWidget::item {
                padding: 2px 2px;
            }
            QTreeWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QTreeWidget::item:hover {
                background-color: #161b22;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                font-weight: 700;
                font-size: 10px;
                border: none;
                border-bottom: 1px solid #30363d;
                padding: 3px 4px;
            }
        """)
        self.markers_tree.itemChanged.connect(self._on_tree_item_changed)
        self.markers_tree.itemClicked.connect(self._on_tree_item_clicked)
        markers_card.layout().addWidget(self.markers_tree)
        
        layout.addStretch()

    def _create_card(self, title: str, parent_layout: QVBoxLayout) -> QFrame:
        card = QFrame()
        card.setObjectName("cardFrame")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8b949e; letter-spacing: 0.5px;")
        card_layout.addWidget(title_lbl)
        
        parent_layout.addWidget(card)
        return card

    def set_soundbase_active(self, filename: str, count: int):
        self.btn_soundbase_json.setText("Soundbase JSON Loaded")
        self.btn_soundbase_json.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                font-weight: 600;
                padding: 6px;
                border: 1px solid #2ea043;
                border-radius: 4px;
            }
        """)
        self.soundbase_status_lbl.setText(f"{filename} ({count} channels active)")
        self.soundbase_status_lbl.setStyleSheet("color: #10b981; font-size: 10px;")

    def _update_enable_btn_style(self):
        if self.enable_btn.isChecked():
            self.enable_btn.setText("Pause Intruder Detection")
            self.enable_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0969da;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    border-radius: 6px;
                    border: 1px solid #218bff;
                }
                QPushButton:hover {
                    background-color: #1f7bf2;
                }
                QPushButton:pressed {
                    background-color: #054da7;
                }
            """)
        else:
            self.enable_btn.setText("Enable Intruder Detection")
            self.enable_btn.setStyleSheet("""
                QPushButton {
                    background-color: #238636;
                    color: #ffffff;
                    font-size: 12px;
                    font-weight: 700;
                    border-radius: 6px;
                    border: 1px solid #2ea043;
                }
                QPushButton:hover {
                    background-color: #2ea043;
                }
                QPushButton:pressed {
                    background-color: #1a7f37;
                }
            """)

    def _on_enable_toggled(self, checked: bool):
        self._update_enable_btn_style()
        self.intruderAlertToggled.emit(checked)

    def set_detection_active(self, active: bool):
        self.enable_btn.setChecked(active)

    def populate_soundbase_tree(self, soundbase_data: dict):
        """
        Populates the markers_tree with hierarchical Sites, Zones, Groups, and Carriers.
        """
        self.markers_tree.blockSignals(True)
        self.markers_tree.clear()
        
        sites = soundbase_data.get("sites", [])
        for site in sites:
            total_site_ch = sum(len(g['carriers']) for z in site.get('zones', []) for g in z.get('groups', []))
            s_item = QTreeWidgetItem([site["name"], f"{total_site_ch} ch"])
            s_item.setCheckState(0, Qt.CheckState.Checked)
            font = s_item.font(0)
            font.setBold(True)
            s_item.setFont(0, font)
            s_item.setForeground(0, QBrush(QColor("#f0f6fc")))
            s_item.setForeground(1, QBrush(QColor("#8b949e")))
            self.markers_tree.addTopLevelItem(s_item)
            
            for zone in site.get("zones", []):
                z_ch_count = sum(len(g['carriers']) for g in zone.get('groups', []))
                z_item = QTreeWidgetItem([zone["name"], f"{z_ch_count} ch"])
                z_item.setCheckState(0, Qt.CheckState.Checked)
                z_font = z_item.font(0)
                z_font.setBold(True)
                z_item.setFont(0, z_font)
                z_item.setForeground(0, QBrush(QColor("#c9d1d9")))
                z_item.setForeground(1, QBrush(QColor("#8b949e")))
                s_item.addChild(z_item)
                
                for group in zone.get("groups", []):
                    g_color = group.get("color", "#38bdf8")
                    g_item = QTreeWidgetItem([group["name"], f"{len(group['carriers'])} ch"])
                    g_item.setCheckState(0, Qt.CheckState.Checked)
                    g_item.setForeground(0, QBrush(QColor(g_color)))
                    g_item.setForeground(1, QBrush(QColor("#8b949e")))
                    z_item.addChild(g_item)
                    
                    for carrier in group.get("carriers", []):
                        c_freq = carrier["freq_mhz"]
                        c_name = carrier["name"]
                        c_bw = carrier["bandwidth_mhz"] * 1000
                        c_model = carrier.get("model", "")
                        c_color = carrier.get("color", g_color)
                        
                        c_item = QTreeWidgetItem([c_name, f"{c_freq:.3f}"])
                        c_item.setCheckState(0, Qt.CheckState.Checked)
                        c_item.setData(0, Qt.ItemDataRole.UserRole, c_freq)
                        c_item.setData(0, Qt.ItemDataRole.UserRole + 1, str(carrier["id"]))
                        c_item.setForeground(0, QBrush(QColor(c_color)))
                        c_item.setForeground(1, QBrush(QColor("#f0f6fc")))
                        
                        tooltip = (
                            f"Channel: {c_name}\n"
                            f"Frequency: {c_freq:.3f} MHz\n"
                            f"Bandwidth: {c_bw:.0f} kHz\n"
                            f"Model: {c_model}\n"
                            f"Group: {group['name']}\n"
                            f"Zone: {zone['name']}"
                        )
                        c_item.setToolTip(0, tooltip)
                        c_item.setToolTip(1, tooltip)
                        g_item.addChild(c_item)
                        
            s_item.setExpanded(True)
            for i in range(s_item.childCount()):
                s_item.child(i).setExpanded(True)
                
        self.markers_tree.blockSignals(False)

    def _on_tree_item_changed(self, item, col):
        if col != 0:
            return
        state = item.checkState(0)
        self.markers_tree.blockSignals(True)
        try:
            def apply_to_children(parent, s):
                for i in range(parent.childCount()):
                    ch = parent.child(i)
                    ch.setCheckState(0, s)
                    apply_to_children(ch, s)
            apply_to_children(item, state)
        finally:
            self.markers_tree.blockSignals(False)
            
        self.markerItemChanged.emit(item, col)

    def _on_tree_item_clicked(self, item, col):
        freq = item.data(0, Qt.ItemDataRole.UserRole)
        if freq is not None:
            self.carrierSelected.emit(float(freq))


