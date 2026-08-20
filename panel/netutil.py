"""Network helpers: DNS, Cloudflare detection, reachability probes, public IP."""

import ipaddress
import json
import re
import socket
import ssl
import time
import urllib.request

# Cloudflare's published IPv4 ranges (edge networks). Used only for hinting in
# the UI, so a slightly stale list is harmless.
CLOUDFLARE_V4 = [
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
]
_CF_NETS = [ipaddress.ip_network(n) for n in CLOUDFLARE_V4]

HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9\-_.]{0,251}[A-Za-z0-9])?$")


def is_ip(value):
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def is_cloudflare(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.version != 4:
        return False
    return any(addr in net for net in _CF_NETS)


def valid_host(value):
    value = (value or "").strip()
    if not value or len(value) > 253:
        return False
    return bool(is_ip(value) or HOST_RE.match(value))


def resolve(host, port=443, want_v4=True):
    """Return a de-duplicated list of resolved IPs for `host`."""
    if is_ip(host):
        return [host]
    family = socket.AF_INET if want_v4 else 0
    try:
        infos = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("DNS lookup failed for %s: %s" % (host, exc)) from exc
    seen, out = set(), []
    for info in infos:
        ip = info[4][0]
        if ip not in seen:
            seen.add(ip)
            out.append(ip)
    return out


def pick_upstream_ip(host, port=443):
    """Resolve and prefer a Cloudflare edge IP when one is present."""
    ips = resolve(host, port)
    if not ips:
        raise ValueError("no address for %s" % host)
    for ip in ips:
        if is_cloudflare(ip):
            return ip, ips
    return ips[0], ips


def tcp_probe(host, port, timeout=5.0):
    """Measure TCP connect latency. Returns (ok, milliseconds, error)."""
    started = time.time()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True, round((time.time() - started) * 1000, 1), ""
    except OSError as exc:
        return False, round((time.time() - started) * 1000, 1), str(exc)


def tls_probe(host, port, server_name, timeout=6.0):
    """Open a TLS session with a given SNI. Returns (ok, ms, error)."""
    started = time.time()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=server_name) as tls:
                tls.do_handshake()
                return True, round((time.time() - started) * 1000, 1), ""
    except (OSError, ssl.SSLError) as exc:
        return False, round((time.time() - started) * 1000, 1), str(exc)


def port_free(host, port):
    """True when nothing is currently bound on host:port."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, int(port)))
            return True
        except OSError:
            return False


def is_local_address(ip):
    """True when `ip` is assigned to an interface on this machine.

    Pointing a listener's upstream at one of our own addresses is fatal: the
    kernel routes that traffic internally instead of over a NIC, so the raw
    sniffer never sees the handshake and every connection dies with
    "timeout waiting for fake ACK". Binding is the cheapest reliable test —
    it only succeeds for locally configured addresses."""
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((ip, 0))
            return True
        except OSError:
            return False


def local_ip_for(dst="1.1.1.1"):
    """The source IP the kernel would use to reach `dst` (no packets sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect((dst, 53))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def http_get(url, timeout=8, proxy=None, headers=None):
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "sni-spoof-panel"})
    with opener.open(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def public_ip(proxy=None, timeout=10):
    """Fetch the egress IP, optionally through a local proxy, to prove the
    tunnel is live. Tries several providers so one outage is not fatal."""
    providers = [
        ("https://api.ipify.org?format=json", "ip"),
        ("https://ifconfig.co/json", "ip"),
        ("https://ipinfo.io/json", "ip"),
    ]
    errors = []
    for url, key in providers:
        try:
            body = http_get(url, timeout=timeout, proxy=proxy)
            data = json.loads(body)
            if data.get(key):
                return {
                    "ip": data[key],
                    "country": data.get("country") or data.get("country_iso") or "",
                    "org": data.get("org") or data.get("asn_org") or "",
                    "via": "proxy" if proxy else "direct",
                }
        except Exception as exc:  # network problems of every shape
            errors.append("%s: %s" % (url, exc))
    raise RuntimeError("; ".join(errors) or "no provider answered")


def socks5_connect(proxy_host, proxy_port, dest_host, dest_port, timeout=10,
                   username="", password=""):
    """Minimal SOCKS5 CONNECT. urllib cannot speak SOCKS, and we refuse to add
    a dependency, so the handshake is done by hand."""
    sock = socket.create_connection((proxy_host, int(proxy_port)), timeout=timeout)
    try:
        methods = b"\x00\x02" if username else b"\x00"
        sock.sendall(b"\x05" + bytes([len(methods)]) + methods)
        reply = _recv_exact(sock, 2)
        if reply[0] != 0x05:
            raise OSError("not a SOCKS5 proxy")
        if reply[1] == 0x02:
            if not username:
                raise OSError("proxy requires authentication")
            user = username.encode()
            pwd = password.encode()
            sock.sendall(
                b"\x01" + bytes([len(user)]) + user + bytes([len(pwd)]) + pwd
            )
            auth = _recv_exact(sock, 2)
            if auth[1] != 0x00:
                raise OSError("proxy authentication failed")
        elif reply[1] != 0x00:
            raise OSError("no acceptable SOCKS5 auth method")

        host_bytes = dest_host.encode("idna")
        sock.sendall(
            b"\x05\x01\x00\x03"
            + bytes([len(host_bytes)])
            + host_bytes
            + int(dest_port).to_bytes(2, "big")
        )
        resp = _recv_exact(sock, 4)
        if resp[1] != 0x00:
            raise OSError("SOCKS5 connect refused (code %d)" % resp[1])
        atyp = resp[3]
        if atyp == 0x01:
            _recv_exact(sock, 4)
        elif atyp == 0x03:
            _recv_exact(sock, _recv_exact(sock, 1)[0])
        elif atyp == 0x04:
            _recv_exact(sock, 16)
        _recv_exact(sock, 2)
        return sock
    except Exception:
        sock.close()
        raise


def _recv_exact(sock, count):
    buf = b""
    while len(buf) < count:
        chunk = sock.recv(count - len(buf))
        if not chunk:
            raise OSError("proxy closed the connection")
        buf += chunk
    return buf


def speaks_socks5(host, port, timeout=5):
    """Confirm a SOCKS5 server answers on this port. Wiring an app to the HTTP
    port instead shows up in the Xray log as
    `malformed HTTP request "\x05\x01\x00"` — that byte string is a SOCKS5
    greeting arriving at an HTTP inbound."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b"\x05\x01\x00")
            reply = sock.recv(8)      # enough to recognise an HTTP status line
    except OSError as exc:
        return False, str(exc)
    if len(reply) >= 1 and reply[0] == 0x05:
        return True, "socks5"
    if reply[:4] == b"HTTP":
        return False, "an HTTP proxy is listening here, not SOCKS5"
    return False, "unexpected reply %r" % reply


def speaks_http_proxy(host, port, timeout=6):
    """Confirm an HTTP proxy answers, using CONNECT to a well-known host."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(
                b"CONNECT api.ipify.org:443 HTTP/1.1\r\n"
                b"Host: api.ipify.org:443\r\n\r\n"
            )
            reply = sock.recv(64)
    except OSError as exc:
        return False, str(exc)
    if reply[:5] == b"HTTP/":
        line = reply.split(b"\r\n", 1)[0].decode("ascii", "replace")
        return line.split(" ")[1:2] == ["200"], line
    if len(reply) >= 1 and reply[0] == 0x05:
        return False, "a SOCKS5 server is listening here, not an HTTP proxy"
    return False, "unexpected reply %r" % reply[:16]


def public_ip_via_socks(proxy_host, proxy_port, timeout=12,
                        username="", password=""):
    """Ask an IP echo service for our egress address through a SOCKS5 proxy."""
    host, path = "api.ipify.org", "/?format=json"
    sock = socks5_connect(proxy_host, proxy_port, host, 443, timeout, username, password)
    ctx = ssl.create_default_context()
    try:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            tls.settimeout(timeout)
            tls.sendall(
                ("GET %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: sni-spoof-panel\r\n"
                 "Connection: close\r\n\r\n" % (path, host)).encode()
            )
            chunks = []
            while True:
                data = tls.recv(4096)
                if not data:
                    break
                chunks.append(data)
    finally:
        try:
            sock.close()
        except OSError:
            pass
    body = b"".join(chunks).split(b"\r\n\r\n", 1)[-1].decode("utf-8", "replace")
    start = body.find("{")
    if start < 0:
        raise RuntimeError("unexpected response through SOCKS proxy")
    return {"ip": json.loads(body[start:body.rfind("}") + 1]).get("ip", ""), "via": "socks5"}
