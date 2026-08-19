"""Optional Xray integration: install the binary, generate a config whose
outbound is routed through a local sni-spoof listener, and expose the result
as HTTP/SOCKS proxies plus a client subscription."""

import io
import json
import os
import time
import zipfile

from . import db, download, paths, services, settings, share

ASSETS = {
    "amd64": "Xray-linux-64.zip",
    "arm64": "Xray-linux-arm64-v8a.zip",
    "arm": "Xray-linux-arm32-v7a.zip",
}
ASSET_DIR = os.path.join(paths.DATA, "xray-assets")


def is_installed():
    return download.executable(paths.XRAY_BIN)


def installed_version():
    return db.get_meta("xray_version", "") or ""


def install(version=None):
    repo = settings.get("xray", "release_repo", "XTLS/Xray-core")
    asset = ASSETS.get(download.arch())
    if not asset:
        raise RuntimeError("no Xray build for architecture %s" % download.arch())

    release = download.latest_release(repo)
    if version:
        url = "https://github.com/%s/releases/download/%s/%s" % (repo, version, asset)
        tag = version
    else:
        url = download.asset_url(repo, asset, release)
        tag = release.get("tag") or "latest"

    payload = download.fetch(url)
    os.makedirs(ASSET_DIR, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        member = "xray" if "xray" in names else next(
            (n for n in names if n.rsplit("/", 1)[-1] == "xray"), None
        )
        if not member:
            raise RuntimeError("xray binary not found inside %s" % asset)
        tmp = paths.XRAY_BIN + ".tmp"
        with open(tmp, "wb") as handle:
            handle.write(archive.read(member))
        os.chmod(tmp, 0o755)
        os.replace(tmp, paths.XRAY_BIN)
        for extra in ("geoip.dat", "geosite.dat"):
            if extra in names:
                with open(os.path.join(ASSET_DIR, extra), "wb") as handle:
                    handle.write(archive.read(extra))

    db.set_meta("xray_version", tag)
    db.set_meta("xray_installed_at", int(time.time()))
    db.log_event("xray %s installed" % tag, category="xray")
    return {"version": tag, "path": paths.XRAY_BIN, "assets": ASSET_DIR}


def check_update():
    repo = settings.get("xray", "release_repo", "XTLS/Xray-core")
    release = download.latest_release(repo)
    current = installed_version()
    latest = release.get("tag", "")
    return {
        "current": current,
        "latest": latest,
        "update_available": bool(latest and current and latest != current),
        "error": release.get("error", ""),
    }


# --------------------------------------------------------------------------
# config generation
# --------------------------------------------------------------------------
def _stream_settings(item, sni_override=None):
    network = (item.get("network") or "tcp").lower()
    security = (item.get("security") or ("tls" if item.get("tls") else "none")).lower()
    stream = {"network": network, "security": security if security else "none"}

    if security in ("tls", "xtls"):
        tls = {
            "serverName": sni_override or item.get("sni") or item.get("http_host") or "",
            "fingerprint": item.get("fingerprint") or "chrome",
            "allowInsecure": bool(item.get("allow_insecure")),
        }
        if item.get("alpn"):
            tls["alpn"] = [a for a in str(item["alpn"]).split(",") if a]
        stream["tlsSettings"] = tls
    elif security == "reality":
        stream["realitySettings"] = {
            "serverName": sni_override or item.get("sni") or "",
            "fingerprint": item.get("fingerprint") or "chrome",
            "publicKey": item.get("public_key", ""),
            "shortId": item.get("short_id", ""),
            "spiderX": item.get("spider_x", ""),
        }

    if network == "ws":
        stream["wsSettings"] = {
            "path": item.get("path") or "/",
            "headers": {"Host": item.get("http_host") or item.get("sni") or ""},
        }
    elif network == "xhttp":
        stream["xhttpSettings"] = {
            "path": item.get("path") or "/",
            "host": item.get("http_host") or item.get("sni") or "",
            "mode": item.get("mode") or "auto",
        }
    elif network == "grpc":
        stream["grpcSettings"] = {
            "serviceName": item.get("service_name") or item.get("path") or ""
        }
    elif network in ("http", "h2"):
        stream["httpSettings"] = {
            "path": item.get("path") or "/",
            "host": [h for h in [item.get("http_host")] if h],
        }
    elif network == "httpupgrade":
        stream["httpupgradeSettings"] = {
            "path": item.get("path") or "/",
            "host": item.get("http_host") or "",
        }
    return stream


def _outbound(item, dial_host, dial_port):
    protocol = item["protocol"]
    stream = _stream_settings(item)

    if protocol == "vless":
        user = {"id": item["user_id"], "encryption": item.get("encryption") or "none"}
        if item.get("flow"):
            user["flow"] = item["flow"]
        settings_block = {"vnext": [{"address": dial_host, "port": int(dial_port), "users": [user]}]}
    elif protocol == "vmess":
        settings_block = {
            "vnext": [
                {
                    "address": dial_host,
                    "port": int(dial_port),
                    "users": [
                        {
                            "id": item["user_id"],
                            "alterId": int(item.get("aid") or 0),
                            "security": item.get("encryption") or "auto",
                        }
                    ],
                }
            ]
        }
    elif protocol == "trojan":
        settings_block = {
            "servers": [
                {"address": dial_host, "port": int(dial_port), "password": item["user_id"]}
            ]
        }
    else:
        raise ValueError("unsupported protocol for Xray outbound: %s" % protocol)

    return {
        "tag": "proxy",
        "protocol": protocol,
        "settings": settings_block,
        "streamSettings": stream,
    }


def build_config(link_raw, dial_host="127.0.0.1", dial_port=40443):
    cfg = settings.get("xray")
    item = share.parse(link_raw)

    inbounds = []
    http_inbound = {
        "tag": "http-in",
        "listen": cfg.get("listen", "127.0.0.1"),
        "port": int(cfg.get("http_port", 1080)),
        "protocol": "http",
        "settings": {},
    }
    socks_inbound = {
        "tag": "socks-in",
        "listen": cfg.get("listen", "127.0.0.1"),
        "port": int(cfg.get("socks_port", 1081)),
        "protocol": "socks",
        "settings": {"auth": "noauth", "udp": bool(cfg.get("socks_udp", False))},
    }
    if cfg.get("auth_user"):
        accounts = [{"user": cfg["auth_user"], "pass": cfg.get("auth_pass", "")}]
        http_inbound["settings"] = {"accounts": accounts, "allowTransparent": False}
        socks_inbound["settings"] = {
            "auth": "password",
            "accounts": accounts,
            "udp": bool(cfg.get("socks_udp", False)),
        }
    inbounds.extend([http_inbound, socks_inbound])

    config = {
        "log": {"loglevel": cfg.get("log_level", "warning")},
        "dns": {"servers": cfg.get("dns") or ["1.1.1.1", "8.8.8.8"]},
        "inbounds": inbounds,
        "outbounds": [
            _outbound(item, dial_host, dial_port),
            {"tag": "direct", "protocol": "freedom", "settings": {}},
            {"tag": "block", "protocol": "blackhole", "settings": {}},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [{"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"}],
        },
    }
    return config


def write_config(link_raw=None, dial_host="127.0.0.1", dial_port=None):
    """Render xray.json for the active link routed through its listener."""
    from . import core

    cfg = settings.get("xray")
    link_id = cfg.get("active_link_id")
    row = None
    if link_raw is None:
        if not link_id:
            raise ValueError("no active Xray link selected")
        row = db.one("SELECT * FROM links WHERE id=?", (link_id,))
        if not row:
            raise ValueError("active link not found")
        link_raw = row["raw"]

    if dial_port is None:
        listener = None
        if row and row["listener_id"]:
            listener = core.get_listener(row["listener_id"])
        if not listener:
            enabled = core.list_listeners(enabled_only=True)
            listener = enabled[0] if enabled else None
        if not listener:
            raise ValueError("no enabled listener to route Xray through")
        dial_port = listener["listen_port"]
        if listener["listen_host"] not in ("0.0.0.0", "::"):
            dial_host = listener["listen_host"]

    config = build_config(link_raw, dial_host, dial_port)
    paths.ensure_dirs()
    tmp = paths.XRAY_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, paths.XRAY_CONFIG)
    return paths.XRAY_CONFIG, config


def apply(restart=True):
    path, config = write_config()
    result = {"path": path, "restarted": False, "message": ""}
    if not settings.get("xray", "enabled", False):
        services.action("xray", "stop")
        result["message"] = "xray is disabled in settings"
        return result
    if not is_installed():
        result["message"] = "xray binary is not installed"
        return result
    if restart and services.has_systemd():
        ok, message = services.action("xray", "restart")
        result["restarted"] = ok
        result["message"] = message or ("restarted" if ok else "restart failed")
    return result


def test_config():
    """Run `xray run -test` so a broken config is caught before restarting."""
    import subprocess

    if not is_installed():
        return False, "xray is not installed"
    try:
        proc = subprocess.run(
            [paths.XRAY_BIN, "run", "-test", "-config", paths.XRAY_CONFIG],
            capture_output=True, text=True, timeout=20, check=False,
            env={**os.environ, "XRAY_LOCATION_ASSET": ASSET_DIR},
        )
        return proc.returncode == 0, (proc.stdout + proc.stderr).strip()[:4000]
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
