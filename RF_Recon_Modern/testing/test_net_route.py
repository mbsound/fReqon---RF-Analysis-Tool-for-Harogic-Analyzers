"""
test_net_route.py - Which interface a network analyzer is on, and its mDNS name
(no network or analyzer needed).

    python testing/test_net_route.py
"""

import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core import net_route

ETH = {"name": "en7", "ip": "192.168.1.2", "mask": "255.255.255.0"}
WIFI_OTHER = {"name": "en0", "ip": "10.0.0.23", "mask": "255.255.255.0"}
WIFI_CLASH = {"name": "en0", "ip": "192.168.1.57", "mask": "255.255.255.0"}


def test_names():
    assert net_route.parse_hostname("67-0123456789abcdef.local") == (67, 0x0123456789abcdef)
    assert net_route.parse_hostname("67-0123456789abcdef") == (67, 0x0123456789abcdef)
    assert net_route.parse_hostname("066-00112233445566ff.local.") == (66, 0x00112233445566ff)
    assert net_route.parse_hostname("mattbook.local") is None and net_route.parse_hostname("192.168.1.100") is None
    assert net_route.hostname_for(67, 0x0123456789abcdef) == "67-0123456789abcdef.local"
    assert net_route.is_ipv4("192.168.1.100") and not net_route.is_ipv4("67-0123456789abcdef.local")


def test_interface_choice():
    # One interface on the analyzer's subnet: that one
    assert net_route.resolve("192.168.1.100", 5000, [WIFI_OTHER, ETH]) == ("192.168.1.100", "en7", "")
    # None: leave it to the system
    assert net_route.resolve("172.16.0.9", 5000, [WIFI_OTHER, ETH]) == ("172.16.0.9", None, "")
    # Wi-Fi on the same subnet as the analyzer's adapter: the one the analyzer answers through
    tried = []
    real = net_route._answers_on
    net_route._answers_on = lambda ip, port, ifname, timeout: (tried.append(ifname), ifname == "en7")[1]
    platform = sys.platform
    sys.platform = "darwin"
    try:
        ip, ifname, note = net_route.resolve("192.168.1.100", 5000, [WIFI_CLASH, ETH])
        assert (ip, ifname) == ("192.168.1.100", "en7") and tried == ["en0", "en7"] and "answers on en7" in note, (ifname, note)
        net_route._answers_on = lambda *a: False
        ip, ifname, note = net_route.resolve("192.168.1.100", 5000, [WIFI_CLASH, ETH])
        assert ifname is None and "did not answer" in note
    finally:
        net_route._answers_on = real
        sys.platform = platform
    # A .local name: the interface it was answered on, whatever the subnets say
    real_gh, real_if = socket.gethostbyname, net_route._interface_from_mdns
    socket.gethostbyname = lambda name: "192.168.1.100"
    net_route._interface_from_mdns = lambda host: "en7"
    try:
        ip, ifname, note = net_route.resolve("67-0123456789abcdef.local", 5000, [WIFI_CLASH, ETH])
        assert (ip, ifname) == ("192.168.1.100", "en7") and "answered on en7" in note
    finally:
        socket.gethostbyname, net_route._interface_from_mdns = real_gh, real_if


if __name__ == "__main__":
    for test in (test_names, test_interface_choice):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All network route tests passed.")
