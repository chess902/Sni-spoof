"""Fallback process supervisor for hosts without systemd (containers, WSL).

Keeps the same start/stop/restart/status surface as the systemd backend, using
pidfiles under RUN and a log file per service."""

import errno
import os
import signal
import subprocess
import time

from . import paths

STOP_GRACE_SEC = 8


def _pidfile(alias):
    return os.path.join(paths.RUN, "%s.pid" % alias)


def logfile(alias):
    return os.path.join(paths.LOG, "%s.log" % alias)


def command_for(alias):
    if alias == "core":
        return [paths.CORE_BIN, paths.CORE_CONFIG]
    if alias == "xray":
        return [paths.XRAY_BIN, "run", "-config", paths.XRAY_CONFIG]
    return None


def read_pid(alias):
    try:
        with open(_pidfile(alias), "r", encoding="utf-8") as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return 0


def alive(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        return exc.errno == errno.EPERM


def status(alias):
    pid = read_pid(alias)
    running = alive(pid)
    if not running and pid:
        _clear(alias)
    started = 0
    if running:
        try:
            started = int(os.stat("/proc/%d" % pid).st_ctime)
        except OSError:
            started = 0
    return {
        "unit": alias,
        "alias": alias,
        "active": running,
        "state": "active" if running else "inactive",
        "sub": "running" if running else "dead",
        "enabled": True,          # supervised in-process: always started with the panel
        "pid": pid if running else 0,
        "memory": 0,
        "since": started,
        "exists": command_for(alias) is not None,
        "backend": "process",
    }


def _clear(alias):
    try:
        os.unlink(_pidfile(alias))
    except OSError:
        pass


def start(alias):
    command = command_for(alias)
    if not command:
        return False, "%s is not supervised here" % alias
    if not os.path.exists(command[0]):
        return False, "%s is not installed" % os.path.basename(command[0])
    if status(alias)["active"]:
        return True, "already running"

    os.makedirs(paths.RUN, exist_ok=True)
    os.makedirs(paths.LOG, exist_ok=True)
    handle = open(logfile(alias), "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            command,
            stdout=handle, stderr=handle, stdin=subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "XRAY_LOCATION_ASSET": os.path.join(paths.DATA, "xray-assets")},
        )
    except OSError as exc:
        handle.close()
        return False, str(exc)
    finally:
        try:
            handle.close()
        except OSError:
            pass

    with open(_pidfile(alias), "w", encoding="utf-8") as pid_handle:
        pid_handle.write(str(proc.pid))

    time.sleep(0.4)
    if proc.poll() is not None:
        _clear(alias)
        return False, "%s exited immediately (see %s)" % (alias, logfile(alias))
    return True, "started (pid %d)" % proc.pid


def stop(alias):
    pid = read_pid(alias)
    if not alive(pid):
        _clear(alias)
        return True, "not running"
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        return False, str(exc)
    deadline = time.time() + STOP_GRACE_SEC
    while time.time() < deadline:
        if not alive(pid):
            _clear(alias)
            return True, "stopped"
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    _clear(alias)
    return True, "killed"


def restart(alias):
    stop(alias)
    return start(alias)


def action(alias, verb):
    if verb == "start":
        return start(alias)
    if verb == "stop":
        return stop(alias)
    if verb in ("restart", "reload"):
        return restart(alias)
    if verb in ("enable", "disable"):
        return True, "no boot-time units without systemd"
    return False, "unsupported verb: %s" % verb


def logs(alias, lines=200):
    path = logfile(alias)
    if not os.path.exists(path):
        return "no log file yet (%s)" % path
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            window = min(size, max(4096, lines * 200))
            handle.seek(size - window)
            data = handle.read().decode("utf-8", "replace")
    except OSError as exc:
        return str(exc)
    return "\n".join(data.splitlines()[-lines:])
