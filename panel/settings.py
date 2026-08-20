"""Panel settings: defaults, deep-merge on read, validation on write."""

import copy
import secrets

from . import db

DEFAULTS = {
    "panel": {
        "host": "0.0.0.0",
        "port": 2095,
        "base_path": "/",
        "language": "fa",
        "theme": "dark",
        "session_ttl_min": 1440,
        "ip_allowlist": [],
        "login_max_attempts": 8,
        "login_ban_minutes": 15,
        "tls": {"enabled": False, "cert": "", "key": ""},
    },
    "core": {
        "auto_start": True,
        "buffer_size": 8,
        "idle_timeout": None,
        "graceful_shutdown_sec": 0,
        "log_level": "warn",
        "auto_refresh_ip_hours": 0,
        "release_repo": "therealaleph/sni-spoofing-rust",
    },
    "xray": {
        "enabled": False,
        "http_port": 1080,
        "socks_port": 1081,
        "listen": "127.0.0.1",
        "auth_user": "",
        "auth_pass": "",
        "socks_udp": False,
        "log_level": "warning",
        "dns": ["1.1.1.1", "8.8.8.8"],
        "active_link_id": None,
        "release_repo": "XTLS/Xray-core",
    },
    "watchdog": {
        "enabled": True,
        "interval_sec": 60,
        "tcp_timeout_sec": 5,
        "failures_before_restart": 3,
        "restart_core": True,
    },
    "stats": {
        "enabled": True,
        "sample_interval_sec": 20,
        "retention_hours": 168,
        "count_traffic": False,
    },
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
        "notify_service_down": True,
        "notify_login": True,
        "notify_backup": True,
    },
    "backup": {
        "auto_enabled": False,
        "interval_hours": 24,
        "keep": 10,
    },
    "network": {
        "github_mirror": "",
        "connect_timeout_sec": 20,
    },
    "scan": {
        "target": "104.18.4.130:443",
        "timeout_sec": 6,
        "concurrency": 10,
    },
}


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def get_all():
    stored = db.all_settings()
    merged = {}
    for section, defaults in DEFAULTS.items():
        merged[section] = _deep_merge(defaults, stored.get(section, {}))
    for section, value in stored.items():
        if section not in merged:
            merged[section] = value
    return merged


def get(section, key=None, default=None):
    data = get_all().get(section, {})
    if key is None:
        return data
    return data.get(key, default)


def update(section, values):
    """Merge `values` into a settings section and persist it."""
    if section not in DEFAULTS:
        raise KeyError(section)
    current = get_all()[section]
    merged = _deep_merge(current, values)
    db.set_setting(section, merged)
    return merged


def replace(section, values):
    db.set_setting(section, values)
    return values


def secret_key():
    """Server-side HMAC key for session tokens; generated on first use."""
    value = db.get_meta("secret_key")
    if not value:
        value = secrets.token_hex(32)
        db.set_meta("secret_key", value)
    return value.encode("utf-8")


def rotate_secret_key():
    value = secrets.token_hex(32)
    db.set_meta("secret_key", value)
    db.execute("DELETE FROM sessions")
    return value


def panel_url(host_hint=None):
    cfg = get("panel")
    scheme = "https" if cfg["tls"]["enabled"] else "http"
    host = host_hint or cfg["host"]
    if host in ("0.0.0.0", "::", ""):
        host = "SERVER_IP"
    base = cfg.get("base_path", "/") or "/"
    if not base.startswith("/"):
        base = "/" + base
    base = base.rstrip("/")
    return "%s://%s:%s%s/" % (scheme, host, cfg["port"], base)
