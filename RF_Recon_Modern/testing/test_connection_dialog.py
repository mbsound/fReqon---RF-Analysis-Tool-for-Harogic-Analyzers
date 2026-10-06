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


def test_saved_slots_come_back_at_launch():
    """The analyzer remembered for slot A (an Ethernet one here) is what the next launch connects to."""
    import json
    import tempfile
    from PyQt6.QtCore import QSettings
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    win.settings.setValue("multi_device_topology", "single")
    win.settings.setValue("multi_device_slots", json.dumps({
        "slot_a": {"enabled": True, "alias": "FOH", "interface": "network", "ip": "67-example.local", "port": 5000,
                   "usb_index": 0, "target_model": 67, "target_uid": 1234, "serial_port": None},
        "slot_b": {"enabled": False, "alias": "", "interface": "usb", "ip": "192.168.1.51", "port": 5000,
                   "usb_index": 1, "target_model": None, "target_uid": None, "serial_port": None}}))
    win._restore_slots()
    a, b = win.multi_device_manager.slots["slot_a"], win.multi_device_manager.slots["slot_b"]
    assert (a.interface_type, a.ip_address, a.port, a.target_model, a.target_uid, a.role_alias, a.is_enabled) == \
        ("network", "67-example.local", 5000, 67, 1234, "FOH", True), vars(a)
    assert (b.interface_type, b.is_enabled) == ("usb", False)
    # ... and the Connection dialog opens showing that, not the defaults
    from ui.dialogs.connection_dialog import ConnectionDialog
    ConnectionDialog.scan_usb = lambda self, *a, **k: None
    dlg = ConnectionDialog(manager=win.multi_device_manager, parent=win)
    assert dlg.card_a.btn_net.isChecked() and dlg.card_a.ip_edit.text() == "67-example.local"
    assert dlg.card_a.target_model == 67 and dlg.card_a.alias_edit.text() == "FOH"
    dlg.close()
    win.close()


def test_settings_page_buttons():
    """Each network slot card, and the selected scan result, open the analyzer's settings page."""
    app = QApplication.instance() or QApplication(sys.argv)
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtWidgets import QMessageBox
    from core import net_route
    from ui.dialogs.connection_dialog import ConnectionDialog
    ConnectionDialog.scan_usb = lambda self, *a, **k: None
    opened, asked, told = [], [], []
    QDesktopServices.openUrl = staticmethod(lambda url: opened.append(url.toString()) or True)
    QMessageBox.information = staticmethod(lambda *a, **k: told.append(a[2]))
    real = net_route.settings_page_url
    net_route.settings_page_url = lambda target, ifcs: (asked.append(target), ("http://127.0.0.1:5555/", "carried")
                                                         if target == "Stage-Left.local" else (None, "not reachable"))[1]
    try:
        dlg = ConnectionDialog()
        dlg._on_topology_button_clicked(4)
        card = dlg.cards["slot_b"]
        card.enable_cb.setChecked(True)               # a slot not in use has its controls greyed out
        card.btn_net.setChecked(True); card._on_intf_changed(1)
        card.ip_edit.setText("Stage-Left.local")

        def wait(n):
            end = time.monotonic() + 3
            while time.monotonic() < end and len(opened) + len(told) < n:
                app.processEvents(); time.sleep(0.02)
        card.web_btn.click(); wait(1)
        assert asked == ["Stage-Left.local"] and opened == ["http://127.0.0.1:5555/"], (asked, opened)
        assert "Opened http://127.0.0.1:5555/" in dlg.scan_status_lbl.text()
        # From the scan list: the selected row's name
        dlg.device_table.setRowCount(1)
        item = QTableWidgetItem("067")
        item.setData(Qt.ItemDataRole.UserRole, {"ip": "10.1.1.9", "hostname": "Elsewhere.local", "model": 67})
        dlg.device_table.setItem(0, 0, item); dlg.device_table.setCurrentCell(0, 0)
        dlg.web_selected_btn.click(); wait(2)
        assert asked[-1] == "Elsewhere.local" and told == ["not reachable"], (asked, told)
        dlg.close()
    finally:
        net_route.settings_page_url = real
    # An address typed in from another subnet is explained, not reported as "off"
    url, why = real("10.1.1.9", [{"name": "en7", "ip": "192.168.1.2", "mask": "255.255.255.0"}])
    assert url is None and "not on any of this computer's networks" in why and "name" in why


if __name__ == "__main__":
    for test in (test_assign_selector_follows_the_topology, test_saved_slots_come_back_at_launch,
                 test_settings_page_buttons):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All connection dialog tests passed.")
