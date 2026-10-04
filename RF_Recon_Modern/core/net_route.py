"""
net_route.py - Which network interface a network analyzer is on.

A network analyzer has a fixed address (192.168.1.100 from the factory) and is
usually on its own Ethernet adapter. If the Wi-Fi network happens to use the
same subnet, the operating system has two interfaces that both claim to reach
that address and picks one by its own priorities, not necessarily the adapter
the analyzer is plugged into. The answer is to pin the connection to the right
interface (the macOS SDK port does this for HTRAAPI_NET_IF).

The analyzer also announces a name on its link by mDNS: "<model>-<serial>.local"
(e.g. 67-0123456789abcdef.local). The name resolves to the same IPv4 address,
so it does not get round a subnet clash by itself, but it does say which
interface the analyzer answered on, and it keeps working if the analyzer's
address is changed.
"""

import ipaddress
import re
import socket
import sys

IP_BOUND_IF = 25            # macOS: setsockopt(IPPROTO_IP, IP_BOUND_IF, interface index)
HOSTNAME_RE = re.compile(r"^(\d{2,3})-([0-9a-fA-F]{16})(\.local\.?)?$")


def is_ipv4(text: str) -> bool:
    try:
        ipaddress.IPv4Address(text.strip())
        return True
    except ValueError:
        return False


def parse_hostname(name: str):
    """(model, uid) from an analyzer's mDNS name such as '67-0123456789abcdef.local', or None."""
    m = HOSTNAME_RE.match(name.strip())
    return (int(m.group(1)), int(m.group(2), 16)) if m else None


def hostname_for(model: int, uid: int) -> str:
    """The mDNS name an analyzer announces."""
    return f"{int(model)}-{int(uid):016x}.local"


def _interface_from_mdns(host: str):
    """The interface a .local name was answered on (from its link-local IPv6 address), or None."""
    try:
        for info in socket.getaddrinfo(host, None, socket.AF_INET6, socket.SOCK_STREAM):
            scope = info[4][3] if len(info[4]) > 3 else 0
            if scope:
                return socket.if_indextoname(scope)
    except (OSError, socket.gaierror):
        pass
    return None


def _answers_on(ip: str, port: int, ifname: str, timeout: float) -> bool:
    """True if ip:port accepts a TCP connection made through ifname (macOS)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF, socket.if_nametoindex(ifname))
        s.settimeout(timeout)
        s.connect((ip, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def resolve(target: str, port: int, interfaces: list, timeout: float = 0.8):
    """
    (IPv4 address, interface name or None, note) for an analyzer given as an address or
    a name. interfaces: [{"name", "ip", "mask"}] of this computer.

    The interface is the one a .local name was answered on; else the only interface
    whose subnet holds the address; else, when several do (the clash this exists for),
    the one through which the analyzer actually answers. None: let the system choose.
    """
    target = target.strip()
    ifname = None
    if is_ipv4(target):
        ip = target
    else:
        ip = socket.gethostbyname(target)           # raises if the name is unknown
        if target.lower().rstrip(".").endswith(".local"):
            ifname = _interface_from_mdns(target)
    if ifname:
        return ip, ifname, f"{target} answered on {ifname}"
    addr = ipaddress.IPv4Address(ip)
    on_subnet = []
    for ifc in interfaces:
        try:
            net = ipaddress.IPv4Network(f"{ifc['ip']}/{ifc.get('mask') or '255.255.255.0'}", strict=False)
        except (ValueError, KeyError):
            continue
        if addr in net and ifc.get("name"):
            on_subnet.append(ifc["name"])
    if len(on_subnet) == 1:
        return ip, on_subnet[0], ""
    if len(on_subnet) > 1 and sys.platform == "darwin":
        for name in on_subnet:
            if _answers_on(ip, port, name, timeout):
                return ip, name, (f"{len(on_subnet)} interfaces are on {ip}'s subnet "
                                  f"({', '.join(on_subnet)}); the analyzer answers on {name}")
        return ip, None, f"{ip} did not answer on any of {', '.join(on_subnet)}"
    return ip, None, ""


def browse_mdns(timeout: float = 1.5) -> list:
    """
    Analyzers announcing themselves on the local links: [{"hostname", "model", "uid",
    "interface", "ip"}]. Uses the system's mDNS browser (dns-sd on macOS, avahi-browse on
    Linux); an empty list if there is none or nothing answers.
    """
    import subprocess
    names = []            # (instance name, interface name or "")
    try:
        if sys.platform == "darwin":
            proc = subprocess.Popen(["dns-sd", "-B", "_workstation._tcp", "local."],
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            try:
                out, _ = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, _ = proc.communicate()
            for line in out.splitlines():
                m = re.search(r"\sAdd\s+\d+\s+(\d+)\s+\S+\s+_workstation\._tcp\.\s+(\S+)", line)
                if m:
                    try:
                        ifname = socket.if_indextoname(int(m.group(1)))
                    except OSError:
                        ifname = ""
                    names.append((m.group(2), ifname))
        else:
            out = subprocess.run(["avahi-browse", "-tp", "_workstation._tcp"], capture_output=True, text=True,
                                 timeout=timeout + 2).stdout
            for line in out.splitlines():
                parts = line.split(";")
                if len(parts) > 3 and parts[0] == "+":
                    names.append((parts[3].split("\\032")[0].split(" ")[0], parts[1]))
    except (OSError, subprocess.SubprocessError):
        return []
    found = {}
    for instance, ifname in names:
        parsed = parse_hostname(instance)
        if not parsed:
            continue                      # some other computer announcing itself
        host = hostname_for(*parsed)
        try:
            ip = socket.gethostbyname(host)
        except OSError:
            ip = ""
        found[host] = {"hostname": host, "model": parsed[0], "uid": parsed[1], "interface": ifname, "ip": ip}
    return list(found.values())
