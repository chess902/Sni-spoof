"""Background workers: metric sampling, health watchdog, scheduled backups and
upstream-IP refresh. One scheduler thread runs them all on their own cadence so
the panel stays a single process."""

import threading
import time
import traceback

from . import core, db, netutil, services, settings, stats, telegram

_stop = threading.Event()
_thread = None
_state = {
    "failures": {},
    "last_sample": 0,
    "last_watchdog": 0,
    "last_backup": 0,
    "last_refresh": 0,
    "health": {},
}


def health_check(listener, timeout=None):
    """TCP-connect to the listener and, when possible, complete a real TLS
    handshake through it — that proves the spoofed path actually works."""
    timeout = timeout or float(settings.get("watchdog", "tcp_timeout_sec", 5))
    host = listener["listen_host"]
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"

    ok, ms, error = netutil.tcp_probe(host, listener["listen_port"], timeout)
    result = {
        "listener_id": listener["id"],
        "port": listener["listen_port"],
        "tcp_ok": ok,
        "tcp_ms": ms,
        "tls_ok": None,
        "tls_ms": 0,
        "error": error,
        "ts": int(time.time()),
    }
    if not ok:
        return result

    server_name = listener["connect_host"] or listener["fake_sni"]
    tls_ok, tls_ms, tls_error = netutil.tls_probe(
        host, listener["listen_port"], server_name, timeout + 2
    )
    result.update({"tls_ok": tls_ok, "tls_ms": tls_ms})
    if not tls_ok:
        result["error"] = tls_error
    return result


def check_all(timeout=None):
    results = []
    for listener in core.list_listeners(enabled_only=True):
        results.append(health_check(listener, timeout))
    _state["health"] = {r["listener_id"]: r for r in results}
    return results


def last_health():
    return _state["health"]


def _watchdog_tick():
    cfg = settings.get("watchdog")
    if not cfg.get("enabled", True):
        return

    core_status = services.status("core")
    listeners = core.list_listeners(enabled_only=True)

    if listeners and services.has_systemd() and not core_status["active"]:
        _bump_failure("service")
        if _state["failures"]["service"] >= int(cfg.get("failures_before_restart", 3)):
            if cfg.get("restart_core", True):
                ok, message = services.action("core", "restart")
                db.log_event(
                    "watchdog restarted the core service (%s)" % (message or "ok"),
                    level="warn", category="watchdog",
                )
                telegram.notify(
                    "service_down",
                    "⚠️ <b>sni-spoof</b>\nCore service was down and has been restarted.",
                )
            _state["failures"]["service"] = 0
        return
    _state["failures"]["service"] = 0

    unhealthy = []
    for listener in listeners:
        result = health_check(listener)
        _state["health"][listener["id"]] = result
        key = "listener-%d" % listener["id"]
        if result["tcp_ok"]:
            _state["failures"][key] = 0
        else:
            _bump_failure(key)
            if _state["failures"][key] >= int(cfg.get("failures_before_restart", 3)):
                unhealthy.append(listener)
                _state["failures"][key] = 0

    if unhealthy and cfg.get("restart_core", True) and services.has_systemd():
        names = ", ".join("#%d:%d" % (l["id"], l["listen_port"]) for l in unhealthy)
        services.action("core", "restart")
        db.log_event(
            "watchdog restarted the core; unreachable listeners: %s" % names,
            level="warn", category="watchdog",
        )
        telegram.notify(
            "service_down",
            "⚠️ <b>sni-spoof</b>\nUnreachable listeners: <code>%s</code>\nCore restarted." % names,
        )


def _bump_failure(key):
    _state["failures"][key] = _state["failures"].get(key, 0) + 1


def _backup_tick():
    cfg = settings.get("backup")
    if not cfg.get("auto_enabled"):
        return
    interval = max(1, int(cfg.get("interval_hours", 24))) * 3600
    last = int(db.get_meta("last_auto_backup", "0") or 0)
    if time.time() - last < interval:
        return

    from . import backup

    path = backup.create("auto")
    db.set_meta("last_auto_backup", int(time.time()))
    if telegram.configured():
        telegram.notify("backup", "💾 Automatic backup created.")
        telegram.send_document(path, caption="sni-spoof automatic backup")


def _refresh_tick():
    hours = int(settings.get("core", "auto_refresh_ip_hours", 0) or 0)
    if hours <= 0:
        return
    last = int(db.get_meta("last_ip_refresh", "0") or 0)
    if time.time() - last < hours * 3600:
        return

    changed = []
    for listener in core.list_listeners(enabled_only=True):
        if not listener["connect_host"]:
            continue
        try:
            result = core.refresh_listener_ip(listener["id"])
        except Exception as exc:
            db.log_event(
                "IP refresh failed for listener #%d: %s" % (listener["id"], exc),
                level="warn", category="core",
            )
            continue
        if result["changed"]:
            changed.append(listener["id"])
    db.set_meta("last_ip_refresh", int(time.time()))
    if changed:
        core.apply(restart=True)
        db.log_event(
            "upstream IPs refreshed for listeners %s" % changed, category="core"
        )


def _loop():
    while not _stop.is_set():
        now = time.time()
        try:
            stats_cfg = settings.get("stats")
            if stats_cfg.get("enabled", True):
                interval = max(5, int(stats_cfg.get("sample_interval_sec", 20)))
                if now - _state["last_sample"] >= interval:
                    stats.sample_once()
                    _state["last_sample"] = now

            watchdog_interval = max(15, int(settings.get("watchdog", "interval_sec", 60)))
            if now - _state["last_watchdog"] >= watchdog_interval:
                _watchdog_tick()
                _state["last_watchdog"] = now

            if now - _state["last_backup"] >= 900:
                _backup_tick()
                _state["last_backup"] = now

            if now - _state["last_refresh"] >= 900:
                _refresh_tick()
                _state["last_refresh"] = now
        except Exception:
            db.log_event(
                "background task error: %s" % traceback.format_exc(limit=3)[-500:],
                level="error", category="tasks",
            )
        _stop.wait(5)
    db.close()


def start():
    global _thread
    if _thread and _thread.is_alive():
        return _thread
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="sni-spoof-tasks", daemon=True)
    _thread.start()
    return _thread


def stop():
    _stop.set()
    if _thread:
        _thread.join(timeout=8)
