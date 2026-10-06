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

Across subnets: when the analyzer's IPv4 address is not on any of this computer's
networks, it is reached by its IPv6 link-local address instead (link_local_route),
which every computer and analyzer has on the cable whatever their IPv4 settings.
Harogic's server listens on IPv4 only; the analyzer's network settings service
(a separate project, installed on the analyzer) relays IPv6 to it, and here LinkLocalForwarder carries the
SDK's IPv4 connection (to 127.0.0.1) over IPv6. Same cable or switch only.
"""

import ipaddress
import json
import re
import socket
import sys
import threading

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


HAROGIC_PORTS = (5000, 9000)    # the SDK server and Harogic's system server, on every network analyzer


def serves_harogic(ip: str, timeout: float = 0.3) -> bool:
    """Whether the host at ip answers on the ports a Harogic network analyzer serves."""
    for port in HAROGIC_PORTS:
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                pass
        except OSError:
            return False
    return True


# --- Across subnets: IPv6 link-local -------------------------------------------------------
INFO_PORT = 8080        # the analyzer's network settings page: /harogic-info says what the unit is


def link_local_v6(host: str):
    """(IPv6 socket address with its scope, interface name) for a name's link-local address, or None."""
    try:
        for info in socket.getaddrinfo(host, None, socket.AF_INET6, socket.SOCK_STREAM):
            sa = info[4]
            if sa[0].lower().startswith("fe80") and len(sa) > 3 and sa[3]:
                try:
                    ifname = socket.if_indextoname(sa[3])
                except OSError:
                    ifname = ""
                return sa, ifname
    except (OSError, socket.gaierror):
        pass
    return None


def v6_answers(sockaddr, port: int, timeout: float = 0.8) -> bool:
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        s.settimeout(timeout)
        s.connect((sockaddr[0], int(port), 0, sockaddr[3]))
        return True
    except OSError:
        return False
    finally:
        s.close()


def harogic_info(address, timeout: float = 0.8):
    """What the analyzer's settings service says it is ({"device_id", "name"}), or None.
    address: an IPv4 address, or an IPv6 socket address."""
    if isinstance(address, tuple):
        family, sa = socket.AF_INET6, (address[0], INFO_PORT, 0, address[3])
    else:
        family, sa = socket.AF_INET, (address, INFO_PORT)
    s = socket.socket(family, socket.SOCK_STREAM)
    try:
        s.settimeout(timeout)
        s.connect(sa)
        s.sendall(b"GET /harogic-info HTTP/1.0\r\nHost: analyzer\r\n\r\n")
        data = b""
        while len(data) < 16384:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        info = json.loads(data.split(b"\r\n\r\n", 1)[1])
        return info if info.get("harogic") else None
    except (OSError, ValueError, IndexError):
        return None
    finally:
        s.close()


def on_local_subnet(ip: str, interfaces: list) -> bool:
    try:
        addr = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    for ifc in interfaces:
        try:
            if addr in ipaddress.IPv4Network(f"{ifc['ip']}/{ifc.get('mask') or '255.255.255.0'}", strict=False):
                return True
        except (ValueError, KeyError):
            continue
    return False


def link_local_route(target: str, port: int, interfaces: list, ipv4: str = None, force: bool = False):
    """
    The way to an analyzer named target over IPv6 link-local ({"sockaddr", "interface"}),
    when its IPv4 address (ipv4, None if the name has none) is not on any of this computer's
    networks and the analyzer relays its port over IPv6; else None. Names only: an address
    typed in is used as it is. force: take this way whenever it exists (tests, diagnosis).
    """
    if is_ipv4(target) or (ipv4 and on_local_subnet(ipv4, interfaces) and not force):
        return None
    found = link_local_v6(target)
    if found is None or not v6_answers(found[0], port):
        return None
    return {"sockaddr": found[0], "interface": found[1]}


class LinkLocalForwarder:
    """
    Listens on 127.0.0.1 and carries every connection made to it to an IPv6 socket
    address: the SDK, which only speaks IPv4, connects here.
    """

    def __init__(self, sockaddr, port: int):
        self.target = (sockaddr[0], int(port), 0, sockaddr[3])
        self.server = None

    def start(self) -> int:
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(8)
        threading.Thread(target=self._accept, daemon=True).start()
        return self.server.getsockname()[1]

    def _accept(self):
        while True:
            try:
                client, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._carry, args=(client,), daemon=True).start()

    def _carry(self, client):
        upstream = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        try:
            upstream.settimeout(5)
            upstream.connect(self.target)
            upstream.settimeout(None)
        except OSError:
            client.close()
            upstream.close()
            return
        for s in (client, upstream):
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        threading.Thread(target=_pump, args=(client, upstream), daemon=True).start()
        _pump(upstream, client)

    def close(self):
        if self.server is not None:
            self.server.close()


def _pump(src, dst):
    try:
        while True:
            data = src.recv(262144)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        src.close()


_page_forwarders = {}      # (address, scope) -> LinkLocalForwarder carrying a settings page


def settings_page_url(target: str, interfaces: list):
    """
    (URL to open in a browser, note) for an analyzer's network settings page, or (None, why).
    On one of this computer's networks the page is opened directly (by name if it has one, so
    the bookmark survives address changes); on another subnet it is carried over IPv6
    link-local through a forwarder on 127.0.0.1, which any browser can open (browsers do not
    take link-local addresses in URLs). The forwarder lasts as long as this program.
    """
    target = target.strip().rstrip("/")
    if not target:
        return None, "No address or name is set for this analyzer."
    try:
        ipv4 = target if is_ipv4(target) else socket.gethostbyname(target)
    except OSError:
        ipv4 = None
    if is_ipv4(target) and not on_local_subnet(target, interfaces):
        return None, (f"{target} is not on any of this computer's networks. Use the analyzer's name "
                      "(e.g. its-name.local, as listed by Scan) to reach it over the cable instead.")
    if ipv4 and (is_ipv4(target) or on_local_subnet(ipv4, interfaces)):
        if harogic_info(ipv4) is None:
            return None, (f"{target} does not answer with a settings page on port {INFO_PORT}: "
                          "it is off, or the network settings service is not installed on it.")
        return f"http://{target}:{INFO_PORT}/", ""
    found = None if is_ipv4(target) else link_local_v6(target)
    if found is None:
        return None, (f"{target} is not reachable from this computer: "
                      + ("its address is on another network and it has no IPv6 link-local address on this cable."
                         if ipv4 else "the name is not found on this computer's networks."))
    sockaddr, ifname = found
    if harogic_info(sockaddr) is None:
        return None, (f"{target} answers over IPv6 but has no settings page on port {INFO_PORT} "
                      "(the network settings service is not installed on it).")
    key = (sockaddr[0], sockaddr[3])
    fwd = _page_forwarders.get(key)
    if fwd is None:
        fwd = LinkLocalForwarder(sockaddr, INFO_PORT)
        fwd.port = fwd.start()
        _page_forwarders[key] = fwd
    return (f"http://127.0.0.1:{fwd.port}/",
            f"{target} is on another subnet ({ipv4 or 'no IPv4'}); its page is carried over IPv6 on {ifname or 'the cable'}.")


def identify(instance: str, ifname: str = "", resolve=None, probe=None, resolve6=None, probe6=None, info=None):
    """
    An announced mDNS name as an analyzer, or None if it is not one:
    {"hostname", "model", "uid", "interface", "ip", "via"}. The factory name ("67-<serial>")
    says the model and serial; any other name (an owner can rename the unit) counts when its
    address serves the Harogic ports, or, on another subnet, when it relays them over IPv6
    link-local ("via": "ipv6"). The settings service, where it runs, says the model and serial.
    """
    resolve = resolve or (lambda host: socket.gethostbyname(host))
    probe = probe or serves_harogic
    resolve6 = resolve6 or link_local_v6
    probe6 = probe6 or (lambda sa: v6_answers(sa, HAROGIC_PORTS[0]))
    info = info or harogic_info
    parsed = parse_hostname(instance)
    host = hostname_for(*parsed) if parsed else f"{instance.rstrip('.').removesuffix('.local')}.local"
    try:
        ip = resolve(host)
    except OSError:
        ip = ""
    via, where = None, None
    if ip and probe(ip):
        via, where = "ipv4", ip
    else:
        v6 = resolve6(host)
        if v6 is not None and probe6(v6[0]):
            via, where = "ipv6", v6[0]
            ifname = ifname or v6[1]
    if parsed is None and via is None:
        return None                       # some other computer announcing itself
    model, uid = (parsed if parsed else (None, None))
    if model is None and where is not None:
        about = info(where)
        ids = parse_hostname(str((about or {}).get("device_id", "")))
        if ids:
            model, uid = ids
    return {"hostname": host, "model": model, "uid": uid, "interface": ifname, "ip": ip, "via": via or "ipv4"}


def browse_mdns(timeout: float = 1.5) -> list:
    """
    Analyzers announcing themselves on the local links: [{"hostname", "model", "uid",
    "interface", "ip"}], whatever name they were given (identify). Uses the system's mDNS
    browser (dns-sd on macOS, avahi-browse on Linux); an empty list if there is none or
    nothing answers.
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
    for instance, ifname in dict.fromkeys(names):
        entry = identify(instance, ifname)
        if entry is not None:
            found[entry["hostname"]] = entry
    return list(found.values())
