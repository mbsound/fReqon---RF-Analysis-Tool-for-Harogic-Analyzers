"""
antenna_source.py - Which analyzer a detector's readings come from, with two connected.

Diversity: both analyzers sweep the same span on different antennas, and the detector can
use either one: a choice of antenna. Split sweep: there is no choice (each analyzer covers
half of the span), so the row says where the readings come from. Otherwise it is hidden.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from core.multi_device_manager import MultiDeviceTopology


class AntennaSourceRow(QFrame):
    changed = pyqtSignal(str)       # "A" or "B"

    def __init__(self, split_note: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self._split_note = split_note
        self.setStyleSheet("AntennaSourceRow { background: transparent; border: none; }")
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 4)
        box.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.label = QLabel("Antenna:")
        self.label.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 600;")
        self.combo = QComboBox()
        self.combo.addItem("Antenna A", "A")
        self.combo.addItem("Antenna B", "B")
        self.combo.setToolTip(tooltip or "Which antenna's analyzer these readings are taken from.")
        self.combo.currentIndexChanged.connect(lambda _i: self.changed.emit(self.choice()))
        row.addWidget(self.label)
        row.addWidget(self.combo, 1)
        box.addLayout(row)
        self.note = QLabel(split_note)
        self.note.setWordWrap(True)
        self.note.setStyleSheet("font-size: 10px; color: #f59e0b;")
        box.addWidget(self.note)
        self.set_topology(MultiDeviceTopology.SINGLE)

    def choice(self) -> str:
        """The antenna to read from: "A" unless antenna B is chosen in diversity."""
        return self.combo.currentData() if self._diversity else "A"

    def set_topology(self, topology: str):
        self._diversity = topology == MultiDeviceTopology.DIVERSITY
        split = topology == MultiDeviceTopology.SPLIT_SWEEP
        self.label.setVisible(self._diversity)
        self.combo.setVisible(self._diversity)
        self.note.setVisible(split)
        self.setVisible(self._diversity or split)
