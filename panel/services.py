"""systemd helpers. Everything degrades to a clear error instead of raising
when systemd is unavailable (containers, unit tests)."""

import os
import shutil
import subprocess

from . import paths, procs

MANAGED = {
    "core": paths.CORE_SERVICE,
    "panel": paths.PANEL_SERVICE,
    "xray": paths.XRAY_SERVICE,
}


def has_systemd():
    """True only when systemd is really PID 1. `systemctl` is often present in
    containers where it cannot talk to any bus, and acting on that leads to a
    watchdog that restarts nothing in a loop."""
    return os.path.isdir("/run/systemd/system") and shutil.which("systemctl") is not None


def _run(args, timeout=25):
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "systemctl not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def unit_for(alias):
    return MANAGED.get(alias, alias)


def status(alias):
    if not has_systemd() and alias != "panel":
        return procs.status(alias)
    unit = unit_for(alias)
    info = {
        "unit": unit,
        "alias": alias,
        "active": False,
        "state": "unknown",
        "sub": "",
        "enabled": False,
        "pid": 0,
        "memory": 0,
        "since": 0,
        "exists": False,
    }
    if not has_systemd():
        info["state"] = "no-systemd"
        info["backend"] = "none"
        return info

    code, out, _ = _run(
        [
            "systemctl",
            "show",
            unit,
            "--property=ActiveState",
            "--property=SubState",
            "--property=UnitFileState",
            "--property=ExecMainPID",
            "--property=MemoryCurrent",
            "--property=ActiveEnterTimestampMonotonic",
            "--property=LoadState",
        ]
    )
    if code != 0:
        return info

    props = {}
    for line in out.splitlines():
        key, _, value = line.partition("=")
        props[key] = value

    info["exists"] = props.get("LoadState") in ("loaded", "masked")
    info["state"] = props.get("ActiveState", "unknown")
    info["sub"] = props.get("SubState", "")
    info["active"] = info["state"] == "active"
    info["enabled"] = props.get("UnitFileState", "") in ("enabled", "enabled-runtime")
    try:
        info["pid"] = int(props.get("ExecMainPID") or 0)
    except ValueError:
        info["pid"] = 0
    mem = props.get("MemoryCurrent", "")
    info["memory"] = int(mem) if mem.isdigit() else 0
    try:
        info["since"] = int(props.get("ActiveEnterTimestampMonotonic") or 0) // 1_000_000
    except ValueError:
        info["since"] = 0
    return info


def status_all():
    return {alias: status(alias) for alias in MANAGED}


def action(alias, verb):
    if verb not in ("start", "stop", "restart", "reload", "enable", "disable"):
        raise ValueError("unsupported verb: %s" % verb)
    if not has_systemd():
        if alias == "panel":
            return False, "the panel supervises itself here; restart it manually"
        return procs.action(alias, verb)
    unit = unit_for(alias)
    args = ["systemctl", verb, unit]
    if verb == "enable":
        args = ["systemctl", "enable", "--now", unit]
    code, out, err = _run(args, timeout=40)
    return code == 0, (err or out or "").strip()


def daemon_reload():
    if not has_systemd():
        return False, "systemd is not available"
    code, out, err = _run(["systemctl", "daemon-reload"])
    return code == 0, err or out


def logs(alias, lines=200, since=None):
    if not has_systemd():
        return procs.logs(alias, lines)
    unit = unit_for(alias)
    if shutil.which("journalctl") is None:
        return "journalctl is not available on this host"
    args = ["journalctl", "-u", unit, "-n", str(int(lines)), "--no-pager", "-o", "short-iso"]
    if since:
        args += ["--since", str(since)]
    code, out, err = _run(args, timeout=30)
    return out if code == 0 else (err or "no logs")


def is_active(alias):
    return status(alias)["active"]
