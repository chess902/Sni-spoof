"""System / service / listener metrics, read straight from /proc so the panel
needs neither psutil nor iproute2."""

import os
import re
import shutil
import socket
import struct
import subprocess
import time

from . import db, paths, settings

_cpu_prev = {"total": 0, "idle": 0}
_net_prev = {"ts": 0.0, "rx": 0, "tx": 0}


def _read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return default


def cpu_percent():
    """CPU busy percentage since the previous call (0 on the first call)."""
    line = _read("/proc/stat").split("\n", 1)[0]
    fields = [int(x) for x in line.split()[1:] if x.isdigit()]
    if len(fields) < 4:
        return 0.0
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    total = sum(fields)
    delta_total = total - _cpu_prev["total"]
    delta_idle = idle - _cpu_prev["idle"]
    _cpu_prev["total"], _cpu_prev["idle"] = total, idle
    if delta_total <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (1 - delta_idle / delta_total) * 100)), 1)


def memory():
    info = {}
    for line in _read("/proc/meminfo").splitlines():
        key, _, rest = line.partition(":")
        value = rest.strip().split(" ")[0]
        if value.isdigit():
            info[key] = int(value) * 1024
    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", info.get("MemFree", 0))
    used = max(0, total - available)
    return {
        "total": total,
        "used": used,
        "available": available,
        "percent": round(used / total * 100, 1) if total else 0.0,
        "swap_total": info.get("SwapTotal", 0),
        "swap_used": max(0, info.get("SwapTotal", 0) - info.get("SwapFree", 0)),
    }


def disk(path="/"):
    try:
        st = os.statvfs(path)
    except OSError:
        return {"total": 0, "used": 0, "free": 0, "percent": 0.0}
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - st.f_bfree * st.f_frsize
    return {
        "total": total,
        "used": used,
        "free": free,
        "percent": round(used / total * 100, 1) if total else 0.0,
    }


def uptime():
    raw = _read("/proc/uptime").split()
    return float(raw[0]) if raw else 0.0


def loadavg():
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except OSError:
        return [0.0, 0.0, 0.0]


def net_totals():
    """Aggregate rx/tx bytes across physical interfaces plus current rate."""
    rx = tx = 0
    per_iface = {}
    for line in _read("/proc/net/dev").splitlines()[2:]:
        name, _, rest = line.partition(":")
        name = name.strip()
        if not rest or name == "lo" or name.startswith(("docker", "veth", "br-")):
            continue
        fields = rest.split()
        if len(fields) < 9:
            continue
        iface_rx, iface_tx = int(fields[0]), int(fields[8])
        per_iface[name] = {"rx": iface_rx, "tx": iface_tx}
        rx += iface_rx
        tx += iface_tx

    now = time.time()
    rate_rx = rate_tx = 0.0
    if _net_prev["ts"] and now > _net_prev["ts"]:
        span = now - _net_prev["ts"]
        rate_rx = max(0.0, (rx - _net_prev["rx"]) / span)
        rate_tx = max(0.0, (tx - _net_prev["tx"]) / span)
    _net_prev.update({"ts": now, "rx": rx, "tx": tx})
    return {
        "rx": rx, "tx": tx,
        "rx_rate": round(rate_rx, 1), "tx_rate": round(rate_tx, 1),
        "interfaces": per_iface,
    }


TCP_ESTABLISHED = "01"
TCP_LISTEN = "0A"


def _parse_proc_net_tcp(path):
    rows = []
    for line in _read(path).splitlines()[1:]:
        fields = line.split()
        if len(fields) < 4:
            continue
        local, remote, state = fields[1], fields[2], fields[3]
        try:
            local_port = int(local.rsplit(":", 1)[1], 16)
            remote_ip_hex = remote.rsplit(":", 1)[0]
        except (IndexError, ValueError):
            continue
        rows.append((local_port, state, remote_ip_hex))
    return rows


def _hex_to_ip(hex_ip):
    try:
        if len(hex_ip) == 8:
            return socket.inet_ntop(socket.AF_INET, struct.pack("<I", int(hex_ip, 16)))
        if len(hex_ip) == 32:
            groups = [hex_ip[i : i + 8] for i in range(0, 32, 8)]
            packed = b"".join(struct.pack("<I", int(g, 16)) for g in groups)
            return socket.inet_ntop(socket.AF_INET6, packed)
    except (ValueError, OSError):
        pass
    return ""


def connections_by_port(ports):
    """Established + listening socket counts for the given local ports."""
    wanted = {int(p) for p in ports}
    result = {p: {"established": 0, "listening": False, "peers": set()} for p in wanted}
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        for local_port, state, remote_hex in _parse_proc_net_tcp(path):
            if local_port not in wanted:
                continue
            if state == TCP_LISTEN:
                result[local_port]["listening"] = True
            elif state == TCP_ESTABLISHED:
                result[local_port]["established"] += 1
                peer = _hex_to_ip(remote_hex)
                if peer:
                    result[local_port]["peers"].add(peer)
    for port in result:
        result[port]["peers"] = sorted(result[port]["peers"])[:50]
        result[port]["unique_peers"] = len(result[port]["peers"])
    return result


def process_info(pid):
    if not pid or not os.path.isdir("/proc/%d" % pid):
        return {}
    status = _read("/proc/%d/status" % pid)
    info = {"pid": pid}
    for key, field in (("VmRSS", "rss"), ("Threads", "threads")):
        match = re.search(r"^%s:\s+(\d+)" % key, status, re.M)
        if match:
            info[field] = int(match.group(1)) * (1024 if key == "VmRSS" else 1)
    io_stats = _read("/proc/%d/io" % pid)
    for key, field in (("rchar", "read_bytes"), ("wchar", "write_bytes")):
        match = re.search(r"^%s:\s+(\d+)" % key, io_stats, re.M)
        if match:
            info[field] = int(match.group(1))
    fd_dir = "/proc/%d/fd" % pid
    try:
        info["open_fds"] = len(os.listdir(fd_dir))
    except OSError:
        info["open_fds"] = 0
    return info


# --------------------------------------------------------------------------
# optional per-listener byte accounting via iptables counters
# --------------------------------------------------------------------------
CHAIN_IN = "SNISPOOF_IN"
CHAIN_OUT = "SNISPOOF_OUT"


def _iptables(*args, timeout=10):
    binary = shutil.which("iptables")
    if not binary:
        return 127, "iptables not available"
    try:
        proc = subprocess.run(
            [binary] + list(args), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        return proc.returncode, (proc.stdout or proc.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def accounting_available():
    return shutil.which("iptables") is not None and os.geteuid() == 0


def setup_accounting(ports):
    """Create counter-only rules (ACCEPT-less, no policy change) per port."""
    if not accounting_available():
        return False, "iptables accounting unavailable (needs root)"
    for chain, hook, flag in ((CHAIN_IN, "INPUT", "--dport"), (CHAIN_OUT, "OUTPUT", "--sport")):
        _iptables("-N", chain)
        _iptables("-F", chain)
        code, _ = _iptables("-C", hook, "-j", chain)
        if code != 0:
            _iptables("-I", hook, "1", "-j", chain)
        for port in ports:
            _iptables("-A", chain, "-p", "tcp", flag, str(int(port)))
    return True, "accounting rules installed for %d port(s)" % len(ports)


def teardown_accounting():
    if not accounting_available():
        return False, "iptables accounting unavailable"
    for chain, hook in ((CHAIN_IN, "INPUT"), (CHAIN_OUT, "OUTPUT")):
        _iptables("-D", hook, "-j", chain)
        _iptables("-F", chain)
        _iptables("-X", chain)
    return True, "accounting rules removed"


def read_accounting():
    """{port: {"rx": bytes, "tx": bytes}} from the counter chains."""
    out = {}
    if not accounting_available():
        return out
    for chain, key, flag in ((CHAIN_IN, "rx", "dpt:"), (CHAIN_OUT, "tx", "spt:")):
        code, text = _iptables("-L", chain, "-n", "-v", "-x")
        if code != 0:
            continue
        for line in text.splitlines():
            match = re.search(r"^\s*(\d+)\s+(\d+)\s+.*%s(\d+)" % flag, line)
            if match:
                port = int(match.group(3))
                out.setdefault(port, {"rx": 0, "tx": 0})[key] = int(match.group(2))
    return out


# --------------------------------------------------------------------------
# sampling
# --------------------------------------------------------------------------
def sample_once():
    """Persist one traffic/connection datapoint per enabled listener."""
    from . import core

    listeners = core.list_listeners(enabled_only=True)
    if not listeners:
        return 0
    ports = [item["listen_port"] for item in listeners]
    conns = connections_by_port(ports)
    counters = read_accounting() if settings.get("stats", "count_traffic", False) else {}
    now = int(time.time())
    for item in listeners:
        port = item["listen_port"]
        counter = counters.get(port, {})
        db.insert(
            "INSERT INTO traffic (ts, listener_id, conns, rx, tx) VALUES (?,?,?,?,?)",
            (now, item["id"], conns.get(port, {}).get("established", 0),
             counter.get("rx", 0), counter.get("tx", 0)),
        )
    retention = int(settings.get("stats", "retention_hours", 168)) * 3600
    db.execute("DELETE FROM traffic WHERE ts < ?", (now - retention,))
    return len(listeners)


def history(listener_id=None, hours=6, buckets=120):
    """Downsampled series for the dashboard charts."""
    since = int(time.time()) - hours * 3600
    if listener_id:
        rows = db.query(
            "SELECT ts, conns, rx, tx FROM traffic WHERE listener_id=? AND ts>=? ORDER BY ts",
            (listener_id, since),
        )
    else:
        rows = db.query(
            "SELECT ts, SUM(conns) AS conns, SUM(rx) AS rx, SUM(tx) AS tx "
            "FROM traffic WHERE ts>=? GROUP BY ts ORDER BY ts",
            (since,),
        )
    points = [dict(r) for r in rows]
    if len(points) <= buckets:
        return points
    step = len(points) / buckets
    return [points[min(len(points) - 1, int(i * step))] for i in range(buckets)]


def snapshot():
    from . import core, services

    listeners = core.list_listeners()
    ports = [item["listen_port"] for item in listeners]
    conns = connections_by_port(ports) if ports else {}
    svc = services.status_all()
    core_proc = process_info(svc.get("core", {}).get("pid", 0))
    return {
        "cpu": cpu_percent(),
        "memory": memory(),
        "disk": disk("/"),
        "uptime": uptime(),
        "load": loadavg(),
        "net": net_totals(),
        "services": svc,
        "core_process": core_proc,
        "hostname": socket.gethostname(),
        "listeners": [
            {
                "id": item["id"],
                "name": item["name"],
                "port": item["listen_port"],
                "enabled": bool(item["enabled"]),
                "established": conns.get(item["listen_port"], {}).get("established", 0),
                "listening": conns.get(item["listen_port"], {}).get("listening", False),
                "unique_peers": conns.get(item["listen_port"], {}).get("unique_peers", 0),
            }
            for item in listeners
        ],
        "accounting": settings.get("stats", "count_traffic", False)
        and accounting_available(),
        "ts": int(time.time()),
    }
