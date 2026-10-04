"""
test_iberia.py - Spain (area plan) and Portugal (transmitter list) television lookups,
and the two regions in the main window (no network, no analyzer).

    python testing/test_iberia.py
"""

import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.iberia_tv import SpainTDTPlan, PortugalTDT, _name_keys
from core.propagation import worth_masking


def test_spain_plan():
    es = SpainTDTPlan()
    d = es.data
    assert len(d["areas"]) == 75 and len(d["municipalities"]) > 8000 and len({k[:2] for k in d["municipalities"]}) == 52
    # Real Decreto 391/2019, annex II
    assert d["areas"]["MADRID"]["channels"] == {"RGE1": 33, "RGE2": 41, "MPE1": 32, "MPE2": 34, "MPE3": 25,
                                                "MPE4": 26, "MPE5": 22, "MAUT": 38}
    assert d["areas"]["BARCELONA"]["channels"]["MAUT"] == 44 and d["areas"]["ZARAGOZA SUR"]["channels"]["RGE1"] == 39
    assert all(len(a["channels"]) == 8 and all(21 <= c <= 48 for c in a["channels"].values()) for a in d["areas"].values())
    assert d["municipalities"]["28079"] == ["Madrid", "MADRID"] and d["municipalities"]["48020"][1] == "BIZKAIA OESTE"
    # Names as the plan and a postcode directory write them
    assert _name_keys("Gineta (La)") & _name_keys("La Gineta") and _name_keys("Palmas de Gran Canaria (Las)") & _name_keys("Las Palmas de Gran Canaria")
    assert _name_keys("Bóveda de Toro, La") & _name_keys("La Bóveda de Toro")

    # A province that is one area needs no name; one split in two needs the municipality
    SpainTDTPlan._place_names = staticmethod(lambda pc: [])                 # no geocoder
    st, info = es.query_by_postcode("28013")
    assert info == {"areas": ["Madrid"], "exact": True} and sorted(s["channel"] for s in st) == [22, 25, 26, 32, 33, 34, 38, 41]
    assert all(s["distance_km"] == 0.0 and s["erp"] is None for s in st) and st[0]["call_sign"].endswith("(Madrid)")
    st, info = es.query_by_postcode("04001")                                # Almería: north or south?
    assert not info["exact"] and len(info["areas"]) >= 2 and len({s["channel"] for s in st}) > 8
    SpainTDTPlan._place_names = staticmethod(lambda pc: ["Almería"])
    st, info = es.query_by_postcode("04001")
    assert info == {"areas": ["Almería Sur"], "exact": True} and len(st) == 8
    assert es.query_by_postcode("99999")[0] == [] and es.query_by_postcode("abc")[0] == []
    # Every channel of the area gets a mask: it is in use there by definition
    assert all(worth_masking(s["erp"], s["distance_km"], s["channel"], low_power_class=False)[0] for s in st)


def test_portugal_list():
    pt = PortugalTDT()
    tx = pt.data["transmitters"]
    assert len(tx) > 250 and all(21 <= t["channel"] <= 48 for t in tx) and not any("�" in t["site"] for t in tx)
    assert all(30.0 < t["lat"] < 43.0 and -32.0 < t["lon"] < -6.0 for t in tx)
    lisbon = pt.query_near(38.7167, -9.1333, 60)
    assert lisbon[0]["site_name"].startswith("Lisboa") and lisbon[0]["distance_km"] < 2 and lisbon[0]["channel"] == 35
    assert abs(lisbon[0]["erp"] - 4.8) < 0.01                               # kW
    assert pt.query_near(32.65, -16.91, 30)[0]["site_name"].startswith("Funchal")
    assert pt.query_near(48.0, 2.0, 80) == []
    # A relay of a few kW a few km away blocks its channel; the US low-power rule would have let it through
    near = lisbon[0]
    assert worth_masking(near["erp"], near["distance_km"], near["channel"], low_power_class=False)[0]
    assert not worth_masking(1.4, 5.0, 35, low_power_class=True)[0] and worth_masking(1.4, 5.0, 35, low_power_class=False)[0]
    assert not worth_masking(0.05, 60.0, 35, low_power_class=False)[0]


def test_regions_in_main_window():
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.main_window import MainWindow
    MainWindow.connect_analyzer = lambda self: None          # never touch real hardware here
    win = MainWindow()
    win.settings = QSettings(os.path.join(tempfile.mkdtemp(), "t.ini"), QSettings.Format.IniFormat)
    assert {"Spain", "Portugal"} <= set(win.region_configs)
    dp = win.dtv_panel

    win.change_region("Spain")
    assert "National plan" in dp.lookup_status_lbl.text() and dp.update_uk_btn.isHidden()
    SpainTDTPlan._place_names = staticmethod(lambda pc: [])
    stations, plan = win.spain_tv.query_by_postcode("28013")
    win._on_station_lookup_finished(stations, {"source": "spain_plan", "fetched_at": None, "plan": plan, "error": None})
    assert "8 multiplex channels planned for the Madrid area" in dp.lookup_status_lbl.text(), dp.lookup_status_lbl.text()
    on = sorted(ch for ch in range(21, 49) if win.active_channels.get(ch))
    assert on == [22, 25, 26, 32, 33, 34, 38, 41], on

    win.change_region("Portugal")
    assert "Transmitter list" in dp.lookup_status_lbl.text()
    assert [c for c, _a, _b in win._tv_channels()][:2] == [21, 22]
    stations = win.portugal_tv.query_near(38.7167, -9.1333, 80)
    win._on_station_lookup_finished(stations, {"source": "portugal", "fetched_at": None, "dated": "", "error": None})
    assert "transmitters within 80 km" in dp.lookup_status_lbl.text()
    on = sorted(ch for ch in range(21, 49) if win.active_channels.get(ch))
    assert 35 in on and len(on) <= 4, on                                    # Lisbon's SFN channel, not every channel listed
    win.close()


if __name__ == "__main__":
    for test in (test_spain_plan, test_portugal_list, test_regions_in_main_window):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All Spain and Portugal tests passed.")
