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


def test_renamed_analyzers_are_found():
    """Discovery goes by what a unit serves, not by its name: an owner may rename it."""
    addresses = {"67-0123456789abcdef.local": "192.168.1.100", "Stage-Left.local": "192.168.2.100",
                 "mattbook.local": "192.168.2.50", "Other-Subnet.local": "10.9.8.7"}
    resolve = lambda host: addresses[host] if host in addresses else (_ for _ in ()).throw(OSError("unknown"))
    harogic = {"192.168.1.100", "192.168.2.100"}                 # answer on the Harogic ports over IPv4
    sa6 = ("fe80::1", 0, 0, 7)
    v6 = {"Other-Subnet.local": (sa6, "en7"), "mattbook.local": (("fe80::2", 0, 0, 7), "en7")}
    kw = dict(resolve=resolve, probe=lambda ip: ip in harogic, resolve6=lambda h: v6.get(h),
              probe6=lambda sa: sa == sa6, info=lambda where: {"harogic": True, "device_id": "67-00000000000000aa"}
              if where == sa6 else None)
    # The factory name: model and serial from the name
    e = net_route.identify("67-0123456789abcdef", "en7", **kw)
    assert e == {"hostname": "67-0123456789abcdef.local", "model": 67, "uid": 0x0123456789abcdef,
                 "interface": "en7", "ip": "192.168.1.100", "via": "ipv4"}, e
    # A renamed unit: found by its ports; model and serial read later, on connecting
    e = net_route.identify("Stage-Left", "en7", **kw)
    assert e == {"hostname": "Stage-Left.local", "model": None, "uid": None, "interface": "en7",
                 "ip": "192.168.2.100", "via": "ipv4"}, e
    assert net_route.identify("Stage-Left.local.", "en7", **kw)["hostname"] == "Stage-Left.local"
    # A renamed unit on another subnet: found over IPv6 link-local, and it says what it is
    e = net_route.identify("Other-Subnet", "", **kw)
    assert e == {"hostname": "Other-Subnet.local", "model": 67, "uid": 0xaa, "interface": "en7",
                 "ip": "10.9.8.7", "via": "ipv6"}, e
    # Another computer announcing itself, or a name that does not resolve: not an analyzer
    assert net_route.identify("mattbook", "en7", **kw) is None
    assert net_route.identify("gone-away", "en7", **kw) is None


def test_link_local_forwarder():
    """The SDK's IPv4 connection to 127.0.0.1 is carried over IPv6, both ways, intact."""
    import threading
    echo = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    echo.bind(("::1", 0)); echo.listen(2)
    eport = echo.getsockname()[1]
    def serve():
        c, _ = echo.accept()
        while True:
            d = c.recv(65536)
            if not d: break
            c.sendall(d)
        c.close()
    threading.Thread(target=serve, daemon=True).start()
    fwd = net_route.LinkLocalForwarder(("::1", 0, 0, 0), eport)
    lport = fwd.start()
    c = socket.create_connection(("127.0.0.1", lport), timeout=5)
    blob = os.urandom(2_000_000)
    got = bytearray()
    def reader():
        while len(got) < len(blob):
            d = c.recv(262144)
            if not d: break
            got.extend(d)
    t = threading.Thread(target=reader); t.start()
    c.sendall(blob); t.join(10)
    assert bytes(got) == blob
    c.close(); fwd.close()
    # An address typed in is used as it is; a name on a local subnet takes the normal way
    ifcs = [{"name": "en7", "ip": "192.168.2.2", "mask": "255.255.255.0"}]
    assert net_route.link_local_route("192.168.9.9", 5000, ifcs) is None
    assert net_route.link_local_route("x.local", 5000, ifcs, ipv4="192.168.2.100") is None
    assert net_route.on_local_subnet("192.168.2.100", ifcs) and not net_route.on_local_subnet("192.168.1.100", ifcs)


if __name__ == "__main__":
    for test in (test_names, test_interface_choice, test_renamed_analyzers_are_found, test_link_local_forwarder):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All network route tests passed.")
