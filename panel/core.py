"""The sni-spoof-rs core: listener CRUD, config.json generation, binary
install/upgrade. Validation mirrors the Rust side so a bad config is rejected
in the panel instead of crash-looping the service."""

import ipaddress
import json
import os
import time

from . import db, download, netutil, paths, services, settings

CORE_ASSETS = {
    ("amd64", False): "sni-spoof-rs-linux-amd64",
    ("amd64", True): "sni-spoof-rs-linux-amd64-musl",
    ("arm64", False): "sni-spoof-rs-linux-arm64",
    ("arm64", True): "sni-spoof-rs-linux-arm64",
}

LISTENER_FIELDS = (
    "name", "enabled", "listen_host", "listen_port", "connect_host", "connect_ip",
    "connect_port", "fake_sni", "conn_timeout_sec", "handshake_timeout_sec",
    "keepalive_time_sec", "keepalive_interval_sec", "remark",
)

DEFAULT_FAKE_SNI = "security.vercel.com"


class ValidationError(ValueError):
    pass


# --------------------------------------------------------------------------
# listeners
# --------------------------------------------------------------------------
def list_listeners(enabled_only=False):
    sql = "SELECT * FROM listeners"
    if enabled_only:
        sql += " WHERE enabled=1"
    sql += " ORDER BY listen_port ASC, id ASC"
    return [dict(r) for r in db.query(sql)]


def get_listener(listener_id):
    row = db.one("SELECT * FROM listeners WHERE id=?", (listener_id,))
    return dict(row) if row else None


def _as_int(value, field, minimum=None, maximum=None):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError("%s must be a number" % field) from None
    if minimum is not None and number < minimum:
        raise ValidationError("%s must be >= %d" % (field, minimum))
    if maximum is not None and number > maximum:
        raise ValidationError("%s must be <= %d" % (field, maximum))
    return number


def normalize(data, listener_id=None):
    """Coerce and validate one listener payload coming from the API/CLI."""
    out = {}
    out["name"] = (data.get("name") or "").strip()[:80]
    out["enabled"] = 1 if data.get("enabled", True) in (True, 1, "1", "true", "on") else 0
    out["remark"] = (data.get("remark") or "").strip()[:500]

    listen_host = (data.get("listen_host") or "127.0.0.1").strip()
    try:
        ipaddress.ip_address(listen_host)
    except ValueError:
        raise ValidationError("listen_host must be an IP address") from None
    out["listen_host"] = listen_host
    out["listen_port"] = _as_int(data.get("listen_port"), "listen_port", 1, 65535)

    connect_host = (data.get("connect_host") or "").strip()
    connect_ip = (data.get("connect_ip") or "").strip()
    if not connect_ip:
        if not connect_host:
            raise ValidationError("connect_ip or connect_host is required")
        connect_ip, _ = netutil.pick_upstream_ip(
            connect_host, int(data.get("connect_port") or 443)
        )
    try:
        ipaddress.ip_address(connect_ip)
    except ValueError:
        raise ValidationError("connect_ip must be an IP address, not a hostname") from None
    out["connect_host"] = connect_host
    out["connect_ip"] = connect_ip
    out["connect_port"] = _as_int(data.get("connect_port") or 443, "connect_port", 1, 65535)

    fake_sni = (data.get("fake_sni") or DEFAULT_FAKE_SNI).strip().rstrip(".")
    if not fake_sni:
        raise ValidationError("fake_sni is required")
    if len(fake_sni) > 219:
        raise ValidationError("fake_sni must be 219 characters or fewer")
    if not netutil.valid_host(fake_sni):
        raise ValidationError("fake_sni is not a valid hostname")
    out["fake_sni"] = fake_sni

    out["conn_timeout_sec"] = _as_int(data.get("conn_timeout_sec", 5), "conn_timeout_sec", 1, 300)
    out["handshake_timeout_sec"] = _as_int(
        data.get("handshake_timeout_sec", 2), "handshake_timeout_sec", 1, 300
    )
    out["keepalive_time_sec"] = _as_int(
        data.get("keepalive_time_sec", 11), "keepalive_time_sec", 1, 3600
    )
    out["keepalive_interval_sec"] = _as_int(
        data.get("keepalive_interval_sec", 2), "keepalive_interval_sec", 1, 3600
    )

    _reject_self_loop(out)
    _reject_duplicate_port(out, listener_id)
    return out


def _reject_self_loop(item):
    """Same rule as the Rust config validator: never forward into ourselves."""
    listen_ip = ipaddress.ip_address(item["listen_host"])
    connect_ip = ipaddress.ip_address(item["connect_ip"])
    if listen_ip == connect_ip and item["listen_port"] == item["connect_port"]:
        raise ValidationError("listener would connect to itself")
    if (
        item["connect_port"] == item["listen_port"]
        and connect_ip.is_loopback
        and (listen_ip.is_loopback or listen_ip.is_unspecified)
    ):
        raise ValidationError("listener would connect to itself")


def _reject_duplicate_port(item, listener_id):
    rows = db.query(
        "SELECT id, listen_host, listen_port FROM listeners WHERE listen_port=?",
        (item["listen_port"],),
    )
    for row in rows:
        if listener_id and row["id"] == listener_id:
            continue
        same_host = row["listen_host"] == item["listen_host"]
        wildcard = "0.0.0.0" in (row["listen_host"], item["listen_host"])
        if same_host or wildcard:
            raise ValidationError(
                "port %d is already used by listener #%d" % (item["listen_port"], row["id"])
            )


def create_listener(data):
    item = normalize(data)
    now = int(time.time())
    columns = list(item.keys()) + ["created_at", "updated_at"]
    values = list(item.values()) + [now, now]
    listener_id = db.insert(
        "INSERT INTO listeners (%s) VALUES (%s)"
        % (", ".join(columns), ", ".join("?" * len(columns))),
        values,
    )
    db.log_event("listener #%d created (%s:%d)" % (listener_id, item["listen_host"], item["listen_port"]), category="core")
    return get_listener(listener_id)


def update_listener(listener_id, data):
    existing = get_listener(listener_id)
    if not existing:
        raise ValidationError("listener not found")
    merged = dict(existing)
    merged.update({k: v for k, v in data.items() if k in LISTENER_FIELDS})
    if data.get("connect_host") and not data.get("connect_ip"):
        merged["connect_ip"] = ""  # force re-resolve when only the host changed
    item = normalize(merged, listener_id=listener_id)
    item["updated_at"] = int(time.time())
    assignments = ", ".join("%s=?" % k for k in item)
    db.execute(
        "UPDATE listeners SET %s WHERE id=?" % assignments,
        list(item.values()) + [listener_id],
    )
    db.log_event("listener #%d updated" % listener_id, category="core")
    return get_listener(listener_id)


def delete_listener(listener_id):
    db.execute("UPDATE links SET listener_id=NULL WHERE listener_id=?", (listener_id,))
    db.execute("DELETE FROM listeners WHERE id=?", (listener_id,))
    db.execute("DELETE FROM traffic WHERE listener_id=?", (listener_id,))
    db.log_event("listener #%d deleted" % listener_id, category="core")


def toggle_listener(listener_id, enabled):
    db.execute(
        "UPDATE listeners SET enabled=?, updated_at=? WHERE id=?",
        (1 if enabled else 0, int(time.time()), listener_id),
    )
    return get_listener(listener_id)


def refresh_listener_ip(listener_id):
    """Re-resolve the upstream domain; Cloudflare rotates edge IPs."""
    item = get_listener(listener_id)
    if not item:
        raise ValidationError("listener not found")
    if not item["connect_host"]:
        raise ValidationError("this listener has no upstream hostname to resolve")
    new_ip, candidates = netutil.pick_upstream_ip(item["connect_host"], item["connect_port"])
    changed = new_ip != item["connect_ip"]
    if changed:
        db.execute(
            "UPDATE listeners SET connect_ip=?, updated_at=? WHERE id=?",
            (new_ip, int(time.time()), listener_id),
        )
        db.log_event(
            "listener #%d upstream IP %s -> %s" % (listener_id, item["connect_ip"], new_ip),
            category="core",
        )
    return {"changed": changed, "ip": new_ip, "candidates": candidates}


# --------------------------------------------------------------------------
# core config.json
# --------------------------------------------------------------------------
def build_config():
    core = settings.get("core")
    listeners = []
    for item in list_listeners(enabled_only=True):
        listeners.append(
            {
                "listen": "%s:%d" % (item["listen_host"], item["listen_port"]),
                "connect": "%s:%d" % (item["connect_ip"], item["connect_port"]),
                "fake_sni": item["fake_sni"],
                "conn_timeout_sec": item["conn_timeout_sec"],
                "handshake_timeout_sec": item["handshake_timeout_sec"],
                "keepalive_time_sec": item["keepalive_time_sec"],
                "keepalive_interval_sec": item["keepalive_interval_sec"],
            }
        )
    config = {
        "buffer_size": int(core.get("buffer_size", 8)),
        "graceful_shutdown_sec": int(core.get("graceful_shutdown_sec", 0)),
        "listeners": listeners,
    }
    idle = core.get("idle_timeout")
    config["idle_timeout"] = int(idle) if idle not in (None, "", 0) else None
    return config


def write_config():
    """Render config.json. Returns (path, listener_count)."""
    config = build_config()
    paths.ensure_dirs()
    tmp = paths.CORE_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, paths.CORE_CONFIG)
    return paths.CORE_CONFIG, len(config["listeners"])


def apply(restart=True):
    """Write the config and reconcile the service with it. With no enabled
    listeners the core cannot start at all, so it is stopped instead."""
    _, count = write_config()
    result = {"listeners": count, "restarted": False, "stopped": False, "message": ""}
    if count == 0:
        ok, message = services.action("core", "stop")
        result["stopped"] = True
        result["message"] = message or "no enabled listeners; core stopped"
        return result
    if restart:
        ok, message = services.action("core", "restart")
        result["restarted"] = ok
        result["message"] = message or ("restarted" if ok else "restart failed")
    return result


# --------------------------------------------------------------------------
# binary management
# --------------------------------------------------------------------------
def installed_version():
    return db.get_meta("core_version", "") or ""


def is_installed():
    return download.executable(paths.CORE_BIN)


def install(version=None):
    repo = settings.get("core", "release_repo", "therealaleph/sni-spoofing-rust")
    asset = CORE_ASSETS.get((download.arch(), download.is_musl()))
    if not asset:
        raise RuntimeError("no prebuilt core for architecture %s" % download.arch())

    release = download.latest_release(repo)
    if version:
        url = "https://github.com/%s/releases/download/%s/%s" % (repo, version, asset)
        tag = version
    else:
        url = download.asset_url(repo, asset, release)
        tag = release.get("tag") or "latest"

    _, source = download.install_binary(
        url, paths.CORE_BIN, fallback_urls=(download.raw_fallback_url(repo, asset),)
    )
    download.grant_net_raw(paths.CORE_BIN)
    db.set_meta("core_version", tag)
    db.set_meta("core_installed_at", int(time.time()))
    db.log_event("core %s installed from %s" % (tag, source), category="core")
    return {"version": tag, "source": source, "path": paths.CORE_BIN}


def check_update():
    repo = settings.get("core", "release_repo", "therealaleph/sni-spoofing-rust")
    release = download.latest_release(repo)
    current = installed_version()
    latest = release.get("tag", "")
    return {
        "current": current,
        "latest": latest,
        "update_available": bool(latest and current and latest != current),
        "error": release.get("error", ""),
        "html_url": release.get("html_url", ""),
    }
