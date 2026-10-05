"""
Connection dialog: assigning a discovered analyzer to a slot.
Run: python testing/test_connection_dialog.py
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTableWidgetItem


def targets(dlg):
    return [dlg.assign_combo.itemData(i) for i in range(dlg.assign_combo.count())]


def test_assign_selector_follows_the_topology():
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.dialogs.connection_dialog import ConnectionDialog
    ConnectionDialog.scan_usb = lambda self, *a, **k: None       # no hardware here
    dlg = ConnectionDialog()
    dlg._on_topology_button_clicked(0)
    assert targets(dlg) == ["slot_a"]
    for btn_id in (1, 2, 3):
        dlg._on_topology_button_clicked(btn_id)
        assert targets(dlg) == ["slot_a", "slot_b"], (btn_id, targets(dlg))
    # A sensor network: every sensor, however many are added
    dlg._on_topology_button_clicked(4)
    assert targets(dlg) == ["slot_a", "slot_b"]
    dlg._add_extra_card()
    dlg._add_extra_card()
    assert targets(dlg) == ["slot_a", "slot_b", "slot_c", "slot_d"]
    assert dlg.assign_combo.itemText(2) == "Sensor C"
    dlg.cards["slot_b"].alias_edit.setText("Stage left")
    dlg._refresh_assign_targets()
    assert dlg.assign_combo.itemText(1) == "Sensor B (Stage left)"

    # Assigning the selected device fills that slot and moves the selector on
    dlg.device_table.setRowCount(1)
    item = QTableWidgetItem("067")
    item.setData(Qt.ItemDataRole.UserRole, {"ip": "192.168.1.100", "hostname": "67-example.local", "model": 67, "uid": 1234})
    dlg.device_table.setItem(0, 0, item)
    dlg.device_table.setCurrentCell(0, 0)
    dlg.assign_combo.setCurrentIndex(dlg.assign_combo.findData("slot_c"))
    dlg.assign_btn.click()
    card = dlg.cards["slot_c"]
    assert card.ip_edit.text() == "67-example.local" and card.btn_net.isChecked() and card.target_model == 67
    assert dlg.assign_combo.currentData() == "slot_d"

    dlg._remove_extra_card()
    assert targets(dlg) == ["slot_a", "slot_b", "slot_c"]
    # Leaving the sensor network: back to the two slots that topology has
    dlg._on_topology_button_clicked(2)
    assert targets(dlg) == ["slot_a", "slot_b"]
    assert not hasattr(dlg, "assign_a_btn") and not hasattr(dlg, "assign_extra_combo")


if __name__ == "__main__":
    t0 = time.monotonic()
    test_assign_selector_follows_the_topology()
    print(f"ok  test_assign_selector_follows_the_topology  ({time.monotonic() - t0:.1f} s)")
    print("All connection dialog tests passed.")
