"""
Top bar: with several analyzers online, each one's readouts are shown.
Run: python testing/test_top_bar.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from ui.widgets.top_bar import TopBar

POWER = {"port_v": 12.1, "port_a": 0.5, "usb_v": 5.0, "usb_a": 0.1}
BUS = {"port_v": 0.0, "port_a": 0.0, "usb_v": 5.0, "usb_a": 0.85}


def entry(slot, **kw):
    e = {"slot_id": slot, "tag": slot[-1].upper(), "name": "SAN-60", "interface": "USB Direct",
         "endorsements": {"uid": "ABCD", "mfw_ver": "0.55.109", "ffw_ver": "1"}, "temp_c": None, "power": None}
    e.update(kw)
    return e


def test_slot_readouts():
    app = QApplication.instance() or QApplication([])
    # In a window, as in the app (on its own the bar would be a window, sized by its content)
    from PyQt6.QtWidgets import QVBoxLayout, QWidget
    host = QWidget()
    bar = TopBar()
    box = QVBoxLayout(host)
    box.setContentsMargins(0, 0, 0, 0)
    box.addWidget(bar)
    box.addStretch()
    host.resize(2400, 120)      # room for everything: nothing is shortened
    host.show()
    app.processEvents()
    bar.set_device_temperature(48.0)
    bar.set_power_state(POWER)
    assert bar.temp_label.isVisible() and bar.power_label.isVisible()

    # Disconnected: no readings of an analyzer that is gone
    bar.set_device_status(False, "Disconnected")
    assert not bar.temp_label.isVisible() and not bar.power_label.isVisible()
    bar.set_device_status(True, "Analyzer")
    bar.set_device_temperature(48.0)
    bar.set_power_state(POWER)

    # One analyzer: the single labels stay
    bar.set_slot_readouts([entry("slot_a", temp_c=48.0, power=POWER)])
    assert not bar.slot_chip_frame.isVisible() and bar.temp_label.isVisible()

    # Two: one chip each, the single labels give way
    two = [entry("slot_a", temp_c=48.0, power=POWER),
           entry("slot_b", interface="Network (192.168.1.100)", temp_c=61.5, power=BUS)]
    bar.set_slot_readouts(two)
    assert bar.slot_chip_frame.isVisible()
    assert not bar.temp_label.isVisible() and not bar.power_label.isVisible()
    assert list(bar._slot_chips) == ["slot_a", "slot_b"]
    a, b = (bar._slot_chips[k] for k in ("slot_a", "slot_b"))
    assert "48.0" in a.text() and "USB" in a.text() and "6.5" in a.text()
    assert "61.5" in b.text() and "Net" in b.text()
    assert "Serial UID: 0xABCD" in a.toolTip() and "Power port" in a.toolTip()
    assert "DC input" in b.toolTip()

    # Updates for the focused analyzer do not bring the single labels back
    bar.set_device_temperature(49.0)
    bar.set_power_state(POWER)
    assert not bar.temp_label.isVisible() and not bar.power_label.isVisible()

    # The unit follows the temperature menu's choice
    bar.temp_unit = "F"
    bar._update_temp_display()
    assert "118.4" in a.text()
    bar.temp_unit = "C"

    # A narrow bar: the chips drop the interface word, and stay put as readings change
    host.resize(900, 120)
    app.processEvents()
    assert "USB" not in a.text() and "48°" in a.text() and "USB Direct" in a.toolTip()
    assert not bar.fps_label.isVisible() and bar.cal_btn.text().startswith("Cal ")
    width = a.width()
    bar.set_slot_readouts([entry("slot_a", temp_c=48.0, power=dict(POWER, port_a=0.3)), two[1]])
    app.processEvents()
    assert a.width() == width, "a chip does not shrink when its reading gets shorter"
    host.resize(2400, 120)
    app.processEvents()
    bar.set_slot_readouts(two)
    assert "USB" in a.text() and "48.0" in a.text() and bar.fps_label.isVisible()      # room again: all of it back
    assert bar.minimumSizeHint().width() <= 900, "the bar must not hold the window wider than the screen"

    # The view selector's list is wide enough for its longest entry
    from core.multi_device_manager import MultiDeviceTopology
    bar.set_multi_device_state(MultiDeviceTopology.DIVERSITY, {})
    fm = bar.focus_combo.fontMetrics()
    assert bar.focus_combo.view().minimumWidth() > fm.horizontalAdvance("Delta (A-B)") + 30
    vm = bar.view_mode_combo
    assert vm.findText(bar.DUAL_SPECTRUM) >= 0
    assert vm.view().minimumWidth() > vm.view().fontMetrics().horizontalAdvance(bar.DUAL_SPECTRUM) + 30

    # The connection dot: one colour for a single analyzer, a half per analyzer for two
    def halves():
        img = bar.status_dot.pixmap().toImage()
        y = img.height() // 2
        left, right = img.pixelColor(img.width() // 2 - 3, y), img.pixelColor(img.width() // 2 + 3, y)
        return tuple("green" if c.green() > c.red() else "red" for c in (left, right))
    bar.set_slot_connections(None)
    bar.set_device_status(True, "Analyzer")
    assert halves() == ("green", "green")
    bar.set_slot_connections((True, False))
    assert halves() == ("green", "red") and "analyzer B: not connected" in bar.status_dot.toolTip()
    bar.set_slot_connections((False, True))
    assert halves() == ("red", "green")
    bar.set_slot_connections((True, True))
    assert halves() == ("green", "green")
    bar.set_slot_connections((False, False))
    assert halves() == ("red", "red")
    bar.set_slot_connections(None)

    # An analyzer without readouts (a tinySA) still gets its chip
    bar.set_slot_readouts([two[0], entry("slot_b", name="tinySA", endorsements={})])
    assert "°" not in bar._slot_chips["slot_b"].text()

    # Back to one analyzer, then none
    bar.set_slot_readouts([two[0]])
    assert not bar.slot_chip_frame.isVisible() and not bar._slot_chips
    assert bar.temp_label.isVisible() and bar.power_label.isVisible()
    bar.set_slot_readouts([])
    assert not bar.slot_chip_frame.isVisible()
    print("ok  slot readouts")


if __name__ == "__main__":
    test_slot_readouts()
    print("All top bar tests passed")
