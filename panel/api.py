"""JSON API. Every route returns a dict (serialised as JSON) or a Response."""

import json
import os
import secrets
import time

from . import (
    __version__, auth, backup, certs, core, db, download, i18n, netutil, paths,
    qrcode, scanner, services, settings, share, stats, tasks, telegram, xray,
)
from .httpd import ApiError, Response, clear_cookie, make_cookie, route

PUBLIC = dict(auth_required=False)


def _lang(request):
    return request.lang


def _tls_on():
    return bool(settings.get("panel", "tls", {}).get("enabled"))


def _bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes", "on")


# ==========================================================================
# session
# ==========================================================================
@route("POST", "/api/login", **PUBLIC)
def login(request):
    data = request.json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    totp = (data.get("totp") or "").strip()
    lang = _lang(request)

    if auth.is_throttled(request.client_ip):
        raise ApiError(i18n.t("too_many_attempts", lang), 429, "throttled")

    user = auth.get_user(username) if username else None
    if not user or not user["enabled"] or not auth.verify_password(
        password, user["pw_hash"], user["pw_salt"]
    ):
        auth.record_attempt(request.client_ip, username, False)
        raise ApiError(i18n.t("bad_credentials", lang), 401, "bad_credentials")

    if user["totp_secret"]:
        if not totp:
            raise ApiError(i18n.t("totp_required", lang), 401, "totp_required")
        if not auth.verify_totp(user["totp_secret"], totp):
            auth.record_attempt(request.client_ip, username, False)
            raise ApiError(i18n.t("totp_invalid", lang), 401, "totp_invalid")

    auth.record_attempt(request.client_ip, username, True)
    auth.clear_attempts(request.client_ip)
    token = auth.create_session(
        user["id"], request.client_ip, request.headers.get("User-Agent", "")
    )
    db.execute(
        "UPDATE users SET last_login=?, last_ip=? WHERE id=?",
        (int(time.time()), request.client_ip, user["id"]),
    )
    request.set_cookie = make_cookie(
        token, _tls_on(), int(settings.get("panel", "session_ttl_min", 1440)) * 60
    )
    db.log_event("login: %s from %s" % (username, request.client_ip), category="auth")
    telegram.notify("login", i18n.t("login_success", "en", request.client_ip))
    return {"user": {"username": user["username"], "role": user["role"]}}


@route("POST", "/api/logout", csrf=False)
def logout(request):
    auth.destroy_session(request.cookie_value)
    request.set_cookie = clear_cookie(_tls_on())
    return {"message": "signed out"}


@route("GET", "/api/session", **PUBLIC)
def session_info(request):
    panel = settings.get("panel")
    payload = {
        "authenticated": request.user is not None,
        "version": __version__,
        "language": panel.get("language", "fa"),
        "theme": panel.get("theme", "dark"),
        "tls": _tls_on(),
        "needs_setup": auth.user_count() == 0,
    }
    if request.user:
        payload["user"] = {
            "id": request.user["id"],
            "username": request.user["username"],
            "role": request.user["role"],
            "totp": bool(request.user["totp_secret"]),
        }
    return payload


@route("POST", "/api/password")
def change_password(request):
    data = request.json()
    current = data.get("current") or ""
    new = data.get("new") or ""
    if len(new) < 8:
        raise ApiError("the new password must be at least 8 characters", 400)
    user = request.user
    if not auth.verify_password(current, user["pw_hash"], user["pw_salt"]):
        raise ApiError(i18n.t("bad_credentials", _lang(request)), 403)
    auth.set_password(user["id"], new)
    db.log_event("password changed for %s" % user["username"], category="auth")
    return {"message": "password updated; sign in again"}


@route("POST", "/api/2fa/setup")
def totp_setup(request):
    secret = auth.new_totp_secret()
    uri = auth.totp_uri(request.user["username"], secret)
    return {"secret": secret, "uri": uri, "qr": qrcode.to_svg(uri, "M", scale=5)}


@route("POST", "/api/2fa/enable")
def totp_enable(request):
    data = request.json()
    secret = (data.get("secret") or "").strip()
    code = (data.get("code") or "").strip()
    if not secret or not auth.verify_totp(secret, code):
        raise ApiError(i18n.t("totp_invalid", _lang(request)), 400, "totp_invalid")
    db.execute("UPDATE users SET totp_secret=? WHERE id=?", (secret, request.user["id"]))
    db.log_event("2FA enabled for %s" % request.user["username"], category="auth")
    return {"message": "two-factor authentication enabled"}


@route("POST", "/api/2fa/disable")
def totp_disable(request):
    data = request.json()
    if not auth.verify_password(
        data.get("password") or "", request.user["pw_hash"], request.user["pw_salt"]
    ):
        raise ApiError(i18n.t("bad_credentials", _lang(request)), 403)
    db.execute("UPDATE users SET totp_secret='' WHERE id=?", (request.user["id"],))
    return {"message": "two-factor authentication disabled"}


@route("GET", "/api/users")
def list_users(request):
    rows = db.query(
        "SELECT id, username, role, enabled, created_at, last_login, last_ip, "
        "CASE WHEN totp_secret='' THEN 0 ELSE 1 END AS totp FROM users ORDER BY id"
    )
    return {"users": [dict(r) for r in rows]}


@route("POST", "/api/users")
def create_user(request):
    data = request.json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if len(username) < 3 or len(password) < 8:
        raise ApiError("username must be 3+ chars and password 8+ chars", 400)
    if auth.get_user(username):
        raise ApiError("that username already exists", 409)
    user_id = auth.create_user(username, password, data.get("role") or "admin")
    db.log_event("panel user created: %s" % username, category="auth")
    return {"id": user_id}


@route("DELETE", "/api/users/<user_id>")
def delete_user(request):
    user_id = int(request.params["user_id"])
    if user_id == request.user["id"]:
        raise ApiError("you cannot delete the account you are signed in with", 400)
    if auth.user_count() <= 1:
        raise ApiError("at least one panel user must remain", 400)
    auth.destroy_user_sessions(user_id)
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    return {"message": "user removed"}


# ==========================================================================
# dashboard
# ==========================================================================
@route("GET", "/api/status")
def status(request):
    snapshot = stats.snapshot()
    snapshot["versions"] = {
        "panel": __version__,
        "core": core.installed_version(),
        "core_installed": core.is_installed(),
        "xray": xray.installed_version(),
        "xray_installed": xray.is_installed(),
    }
    snapshot["health"] = tasks.last_health()
    snapshot["systemd"] = services.has_systemd()
    return snapshot


@route("GET", "/api/history")
def history(request):
    listener_id = request.q_int("listener_id", 0) or None
    hours = max(1, min(720, request.q_int("hours", 6)))
    return {"points": stats.history(listener_id, hours)}


@route("GET", "/api/events")
def events(request):
    limit = max(1, min(500, request.q_int("limit", 100)))
    rows = db.query(
        "SELECT id, ts, level, category, message FROM events ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return {"events": [dict(r) for r in rows]}


@route("GET", "/api/logs/<alias>")
def logs(request):
    alias = request.params["alias"]
    if alias not in services.MANAGED:
        raise ApiError("unknown service", 404)
    lines = max(10, min(2000, request.q_int("lines", 200)))
    return {"text": services.logs(alias, lines)}


@route("POST", "/api/service/<alias>/<verb>")
def service_action(request):
    alias, verb = request.params["alias"], request.params["verb"]
    if alias not in services.MANAGED:
        raise ApiError("unknown service", 404)
    if alias == "panel" and verb in ("stop", "disable"):
        raise ApiError("stopping the panel from the panel is not allowed", 400)
    ok, message = services.action(alias, verb)
    db.log_event("service %s %s -> %s" % (alias, verb, "ok" if ok else message),
                 level="info" if ok else "warn", category="service")
    return {"ok": ok, "message": message or verb}


# ==========================================================================
# listeners
# ==========================================================================
@route("GET", "/api/listeners")
def listeners(request):
    items = core.list_listeners()
    ports = [i["listen_port"] for i in items]
    conns = stats.connections_by_port(ports) if ports else {}
    health = tasks.last_health()
    for item in items:
        info = conns.get(item["listen_port"], {})
        item["established"] = info.get("established", 0)
        item["listening"] = info.get("listening", False)
        item["health"] = health.get(item["id"])
        item["cloudflare"] = netutil.is_cloudflare(item["connect_ip"])
    return {"listeners": items}


@route("POST", "/api/listeners")
def add_listener(request):
    try:
        item = core.create_listener(request.json())
    except core.ValidationError as exc:
        raise ApiError(str(exc), 400) from None
    result = core.apply(restart=True)
    return {"listener": item, "apply": result}


@route("PUT", "/api/listeners/<listener_id>")
def edit_listener(request):
    try:
        item = core.update_listener(int(request.params["listener_id"]), request.json())
    except core.ValidationError as exc:
        raise ApiError(str(exc), 400) from None
    return {"listener": item, "apply": core.apply(restart=True)}


@route("DELETE", "/api/listeners/<listener_id>")
def remove_listener(request):
    core.delete_listener(int(request.params["listener_id"]))
    return {"apply": core.apply(restart=True)}


@route("POST", "/api/listeners/<listener_id>/toggle")
def toggle(request):
    data = request.json()
    item = core.toggle_listener(int(request.params["listener_id"]), _bool(data.get("enabled"), True))
    return {"listener": item, "apply": core.apply(restart=True)}


@route("POST", "/api/listeners/<listener_id>/refresh-ip")
def refresh_ip(request):
    try:
        result = core.refresh_listener_ip(int(request.params["listener_id"]))
    except core.ValidationError as exc:
        raise ApiError(str(exc), 400) from None
    if result["changed"]:
        result["apply"] = core.apply(restart=True)
    return result


@route("POST", "/api/listeners/<listener_id>/test")
def test_listener(request):
    item = core.get_listener(int(request.params["listener_id"]))
    if not item:
        raise ApiError(i18n.t("not_found", _lang(request)), 404)
    result = tasks.health_check(item, timeout=8)
    upstream_ok, upstream_ms, upstream_error = netutil.tcp_probe(
        item["connect_ip"], item["connect_port"], 8
    )
    result["upstream"] = {"ok": upstream_ok, "ms": upstream_ms, "error": upstream_error}
    return result


@route("POST", "/api/listeners/apply")
def apply_config(request):
    return {"apply": core.apply(restart=True)}


@route("GET", "/api/core/config")
def core_config(request):
    return {"config": core.build_config(), "path": paths.CORE_CONFIG}


@route("GET", "/api/core/update")
def core_update(request):
    return core.check_update()


@route("POST", "/api/core/install")
def core_install(request):
    version = (request.json().get("version") or "").strip() or None
    result = core.install(version)
    core.apply(restart=True)
    return result


# ==========================================================================
# share links
# ==========================================================================
@route("GET", "/api/links")
def list_links(request):
    rows = db.query("SELECT * FROM links ORDER BY id DESC")
    items = []
    for row in rows:
        item = dict(row)
        try:
            item["parsed"] = json.loads(item["parsed"])
        except (ValueError, TypeError):
            item["parsed"] = {}
        items.append(item)
    return {"links": items, "active_link_id": settings.get("xray", "active_link_id")}


@route("POST", "/api/links/parse")
def parse_link(request):
    text = request.json().get("link") or ""
    parsed, errors = share.parse_many(text)
    return {
        "parsed": [share.summary(item) for item in parsed],
        "errors": errors,
    }


@route("POST", "/api/links/import")
def import_links(request):
    data = request.json()
    parsed, errors = share.parse_many(data.get("links") or "")
    if not parsed:
        raise ApiError(errors[0]["error"] if errors else "no valid link found", 400)

    listen_host = (data.get("listen_host") or "127.0.0.1").strip()
    start_port = int(data.get("listen_port") or 40443)
    fake_sni = (data.get("fake_sni") or core.DEFAULT_FAKE_SNI).strip()
    make_listener = _bool(data.get("create_listener"), True)

    created, used_port = [], start_port
    for item in parsed:
        listener_id = None
        if make_listener:
            while any(l["listen_port"] == used_port for l in core.list_listeners()):
                used_port += 1
            try:
                payload = share.to_listener_payload(item, listen_host, used_port, fake_sni)
                listener = core.create_listener(payload)
            except (core.ValidationError, ValueError) as exc:
                # Keep the link even when the upstream cannot be resolved right
                # now; the operator can attach a listener later.
                errors.append({"line": item["label"], "error": str(exc)})
            else:
                listener_id = listener["id"]
                used_port += 1

        link_id = db.insert(
            "INSERT INTO links (listener_id, name, protocol, raw, parsed, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                listener_id, item["label"], item["protocol"], item["raw"],
                json.dumps(share.summary(item), ensure_ascii=False), int(time.time()),
            ),
        )
        created.append({"link_id": link_id, "listener_id": listener_id, "label": item["label"]})

    apply_result = core.apply(restart=True) if make_listener and created else None
    if created and settings.get("xray", "active_link_id") is None:
        settings.update("xray", {"active_link_id": created[0]["link_id"]})
    return {"created": created, "errors": errors, "apply": apply_result}


@route("DELETE", "/api/links/<link_id>")
def delete_link(request):
    link_id = int(request.params["link_id"])
    db.execute("DELETE FROM links WHERE id=?", (link_id,))
    if settings.get("xray", "active_link_id") == link_id:
        settings.update("xray", {"active_link_id": None})
    return {"message": "link removed"}


@route("POST", "/api/links/<link_id>/activate")
def activate_link(request):
    link_id = int(request.params["link_id"])
    if not db.one("SELECT id FROM links WHERE id=?", (link_id,)):
        raise ApiError(i18n.t("not_found", _lang(request)), 404)
    settings.update("xray", {"active_link_id": link_id})
    result = {}
    if settings.get("xray", "enabled", False) and xray.is_installed():
        result = xray.apply(restart=True)
    return {"active_link_id": link_id, "xray": result}


@route("GET", "/api/links/<link_id>/client")
def client_link(request):
    link_id = int(request.params["link_id"])
    row = db.one("SELECT * FROM links WHERE id=?", (link_id,))
    if not row:
        raise ApiError(i18n.t("not_found", _lang(request)), 404)

    host = request.q("host") or ""
    port = request.q_int("port", 0)
    if not host or not port:
        listener = core.get_listener(row["listener_id"]) if row["listener_id"] else None
        if not listener:
            enabled = core.list_listeners(enabled_only=True)
            listener = enabled[0] if enabled else None
        if not listener:
            raise ApiError("no listener is available to build a client link", 400)
        port = port or listener["listen_port"]
        host = host or (
            netutil.local_ip_for()
            if listener["listen_host"] in ("0.0.0.0", "::")
            else listener["listen_host"]
        )

    name = request.q("name") or (row["name"] or "sni-spoof")
    rewritten = share.rewrite(row["raw"], host, port, name)
    return {
        "link": rewritten,
        "qr": qrcode.to_svg(rewritten, "L", scale=5),
        "host": host,
        "port": port,
    }


@route("GET", "/api/subscription/token")
def subscription_token(request):
    token = db.get_meta("sub_token", "")
    if not token:
        token = secrets.token_urlsafe(18)
        db.set_meta("sub_token", token)
    panel = settings.get("panel")
    scheme = "https" if _tls_on() else "http"
    host = request.headers.get("Host") or "%s:%s" % (
        netutil.local_ip_for(), panel.get("port")
    )
    base = panel.get("base_path", "/").rstrip("/")
    return {"token": token, "url": "%s://%s%s/sub/%s" % (scheme, host, base, token)}


@route("POST", "/api/subscription/rotate")
def rotate_subscription(request):
    token = secrets.token_urlsafe(18)
    db.set_meta("sub_token", token)
    return {"token": token}


@route("GET", "/sub/<token>", **PUBLIC)
def subscription(request):
    token = db.get_meta("sub_token", "")
    if not token or request.params["token"] != token:
        return Response.text("not found", 404)

    host = request.q("host") or netutil.local_ip_for()
    links = []
    for row in db.query("SELECT * FROM links ORDER BY id"):
        listener = core.get_listener(row["listener_id"]) if row["listener_id"] else None
        if not listener or not listener["enabled"]:
            continue
        target = host
        if listener["listen_host"] not in ("0.0.0.0", "::"):
            target = listener["listen_host"]
        try:
            links.append(
                share.rewrite(row["raw"], target, listener["listen_port"], row["name"] or None)
            )
        except share.ShareError:
            continue
    return Response.text(share.subscription(links), 200, "text/plain; charset=utf-8")


# ==========================================================================
# xray
# ==========================================================================
@route("GET", "/api/xray")
def xray_status(request):
    cfg = settings.get("xray")
    return {
        "installed": xray.is_installed(),
        "version": xray.installed_version(),
        "settings": cfg,
        "service": services.status("xray"),
        "config_path": paths.XRAY_CONFIG,
    }


@route("POST", "/api/xray/install")
def xray_install(request):
    version = (request.json().get("version") or "").strip() or None
    return xray.install(version)


@route("GET", "/api/xray/update")
def xray_update(request):
    return xray.check_update()


@route("POST", "/api/xray/apply")
def xray_apply(request):
    if not xray.is_installed():
        raise ApiError(i18n.t("xray_missing", _lang(request)), 400, "xray_missing")
    result = xray.apply(restart=True)
    ok, output = xray.test_config()
    result["config_test"] = {"ok": ok, "output": output}
    return result


@route("GET", "/api/xray/config")
def xray_config(request):
    try:
        _, config = xray.write_config()
    except ValueError as exc:
        raise ApiError(str(exc), 400) from None
    return {"config": config, "path": paths.XRAY_CONFIG}


# ==========================================================================
# scanner
# ==========================================================================
@route("POST", "/api/scan/start")
def scan_start(request):
    data = request.json()
    snis = data.get("snis")
    if isinstance(snis, str):
        snis = [line.strip() for line in snis.splitlines() if line.strip()]
    try:
        scan_id = scanner.start(
            target=data.get("target"),
            snis=snis or None,
            timeout=data.get("timeout"),
            concurrency=data.get("concurrency"),
        )
    except RuntimeError as exc:
        raise ApiError(str(exc), 409) from None
    return {"scan_id": scan_id}


@route("GET", "/api/scan/status")
def scan_status(request):
    return scanner.status()


@route("POST", "/api/scan/cancel")
def scan_cancel(request):
    return {"cancelled": scanner.cancel()}


@route("GET", "/api/scan/list")
def scan_list(request):
    return {"scans": scanner.recent(20), "candidates": len(scanner.default_snis())}


@route("GET", "/api/scan/<scan_id>")
def scan_detail(request):
    item = scanner.get_scan(int(request.params["scan_id"]))
    if not item:
        raise ApiError(i18n.t("not_found", _lang(request)), 404)
    return item


@route("GET", "/api/scan-list")
def get_sni_list(request):
    path = paths.SNI_LIST if os.path.exists(paths.SNI_LIST) else scanner.BUNDLED_LIST
    text = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    return {"text": text, "path": paths.SNI_LIST, "count": len(scanner.default_snis())}


@route("PUT", "/api/scan-list")
def put_sni_list(request):
    count = scanner.save_sni_list(request.json().get("text") or "")
    return {"count": count}


@route("POST", "/api/scan/apply")
def scan_apply(request):
    """Set a working SNI on one or more listeners."""
    data = request.json()
    sni = (data.get("sni") or "").strip()
    if not sni:
        raise ApiError("sni is required", 400)
    ids = data.get("listener_ids") or [l["id"] for l in core.list_listeners()]
    updated = []
    for listener_id in ids:
        try:
            core.update_listener(int(listener_id), {"fake_sni": sni})
            updated.append(int(listener_id))
        except core.ValidationError as exc:
            raise ApiError(str(exc), 400) from None
    return {"updated": updated, "apply": core.apply(restart=True)}


# ==========================================================================
# settings, certificates, tools
# ==========================================================================
@route("GET", "/api/settings")
def get_settings(request):
    data = settings.get_all()
    data["telegram"] = dict(data["telegram"])
    if data["telegram"].get("bot_token"):
        data["telegram"]["bot_token"] = "********"
    return {"settings": data, "defaults": settings.DEFAULTS}


@route("PUT", "/api/settings/<section>")
def put_settings(request):
    section = request.params["section"]
    if section not in settings.DEFAULTS:
        raise ApiError("unknown settings section", 404)
    values = request.json()
    if section == "telegram" and values.get("bot_token") == "********":
        values.pop("bot_token")
    merged = settings.update(section, values)
    db.log_event("settings section '%s' updated" % section, category="settings")

    followups = {}
    if section == "core":
        followups["core"] = core.apply(restart=True)
    elif section == "xray":
        if merged.get("enabled") and xray.is_installed():
            try:
                followups["xray"] = xray.apply(restart=True)
            except ValueError as exc:
                followups["xray"] = {"message": str(exc)}
        else:
            services.action("xray", "stop")
    elif section == "stats" and merged.get("count_traffic"):
        ports = [l["listen_port"] for l in core.list_listeners(enabled_only=True)]
        ok, message = stats.setup_accounting(ports)
        followups["accounting"] = {"ok": ok, "message": message}
    elif section == "panel":
        followups["restart_required"] = True
    return {"settings": merged, "followups": followups}


@route("GET", "/api/cert")
def cert_info(request):
    return {"cert": certs.info(), "tls": settings.get("panel", "tls", {})}


@route("POST", "/api/cert/self-signed")
def cert_self_signed(request):
    data = request.json()
    result = certs.self_signed(data.get("common_name") or netutil.local_ip_for())
    if _bool(data.get("enable"), True):
        certs.enable_tls(result["cert"], result["key"])
        result["restart_required"] = True
    return result


@route("POST", "/api/cert/acme")
def cert_acme(request):
    data = request.json()
    domain = (data.get("domain") or "").strip()
    email = (data.get("email") or "").strip()
    if not domain or not email:
        raise ApiError("domain and email are required", 400)
    result = certs.issue_acme(domain, email, int(data.get("port") or 80))
    if _bool(data.get("enable"), True):
        certs.enable_tls(result["cert"], result["key"])
        result["restart_required"] = True
    return result


@route("POST", "/api/cert/disable")
def cert_disable(request):
    certs.disable_tls()
    return {"restart_required": True}


@route("GET", "/api/backups")
def list_backups(request):
    return {"backups": backup.listing()}


@route("POST", "/api/backups")
def make_backup(request):
    path = backup.create(request.json().get("label") or None)
    result = {"name": os.path.basename(path)}
    if _bool(request.json().get("telegram"), False) and telegram.configured():
        result["telegram"] = telegram.send_document(path, "sni-spoof backup")
    return result


@route("GET", "/api/backups/<name>/download")
def download_backup(request):
    path = backup.path_for(request.params["name"])
    with open(path, "rb") as handle:
        data = handle.read()
    return Response(
        data, 200, "application/gzip",
        {"Content-Disposition": 'attachment; filename="%s"' % os.path.basename(path)},
    )


@route("POST", "/api/backups/<name>/restore")
def restore_backup(request):
    path = backup.path_for(request.params["name"])
    return backup.restore(path)


@route("DELETE", "/api/backups/<name>")
def remove_backup(request):
    backup.delete(request.params["name"])
    return {"message": "backup removed"}


@route("POST", "/api/backups/upload")
def upload_backup(request):
    """Raw tar.gz body upload, then restore."""
    if not request.body:
        raise ApiError("empty upload", 400)
    paths.ensure_dirs()
    target = os.path.join(
        paths.BACKUP_DIR, "sni-spoof-upload-%d.tar.gz" % int(time.time())
    )
    with open(target, "wb") as handle:
        handle.write(request.body)
    try:
        result = backup.restore(target)
    except ValueError as exc:
        os.unlink(target)
        raise ApiError(str(exc), 400) from None
    result["name"] = os.path.basename(target)
    return result


@route("GET", "/api/export")
def export_settings(request):
    payload = json.dumps(backup.export_settings(), indent=2, ensure_ascii=False, default=str)
    return Response(
        payload.encode("utf-8"), 200, "application/json; charset=utf-8",
        {"Content-Disposition": 'attachment; filename="sni-spoof-export.json"'},
    )


@route("POST", "/api/telegram/test")
def telegram_test(request):
    result = telegram.test()
    if not result.get("ok"):
        raise ApiError(result.get("reason") or "telegram rejected the message", 400)
    return {"message": "test message sent"}


@route("POST", "/api/tools/resolve")
def resolve_host(request):
    host = (request.json().get("host") or "").strip()
    if not netutil.valid_host(host):
        raise ApiError(i18n.t("invalid_input", _lang(request)), 400)
    port = int(request.json().get("port") or 443)
    try:
        chosen, candidates = netutil.pick_upstream_ip(host, port)
    except ValueError as exc:
        raise ApiError(str(exc), 400) from None
    return {
        "ip": chosen,
        "candidates": candidates,
        "cloudflare": netutil.is_cloudflare(chosen),
    }


@route("GET", "/api/tools/ip")
def tools_ip(request):
    mode = request.q("via", "direct")
    try:
        if mode == "http":
            cfg = settings.get("xray")
            proxy = "http://%s:%s" % (
                "127.0.0.1" if cfg["listen"] in ("0.0.0.0", "::") else cfg["listen"],
                cfg["http_port"],
            )
            return netutil.public_ip(proxy=proxy)
        if mode == "socks":
            cfg = settings.get("xray")
            host = "127.0.0.1" if cfg["listen"] in ("0.0.0.0", "::") else cfg["listen"]
            return netutil.public_ip_via_socks(
                host, cfg["socks_port"],
                username=cfg.get("auth_user", ""), password=cfg.get("auth_pass", ""),
            )
        return netutil.public_ip()
    except (RuntimeError, OSError) as exc:
        raise ApiError(str(exc), 502) from None


@route("POST", "/api/tools/probe")
def tools_probe(request):
    data = request.json()
    host = (data.get("host") or "").strip()
    port = int(data.get("port") or 443)
    sni = (data.get("sni") or "").strip()
    if not netutil.valid_host(host):
        raise ApiError(i18n.t("invalid_input", _lang(request)), 400)
    tcp_ok, tcp_ms, tcp_error = netutil.tcp_probe(host, port, 8)
    result = {"tcp": {"ok": tcp_ok, "ms": tcp_ms, "error": tcp_error}}
    if tcp_ok and sni:
        tls_ok, tls_ms, tls_error = netutil.tls_probe(host, port, sni, 8)
        result["tls"] = {"ok": tls_ok, "ms": tls_ms, "error": tls_error}
    return result


@route("GET", "/api/tools/port-free")
def port_free(request):
    port = request.q_int("port", 0)
    host = request.q("host", "0.0.0.0")
    if not 1 <= port <= 65535:
        raise ApiError(i18n.t("invalid_input", _lang(request)), 400)
    return {"free": netutil.port_free(host, port)}


@route("GET", "/api/qr")
def qr(request):
    text = request.q("text", "")
    if not text:
        raise ApiError("text is required", 400)
    try:
        svg = qrcode.to_svg(text, request.q("ecl", "L"), scale=request.q_int("scale", 6))
    except qrcode.QRError as exc:
        raise ApiError(str(exc), 400) from None
    return Response(svg.encode("utf-8"), 200, "image/svg+xml")


@route("POST", "/api/health/check")
def health_check_all(request):
    return {"results": tasks.check_all(timeout=8)}


@route("GET", "/api/system")
def system_info(request):
    uname = os.uname()
    return {
        "hostname": uname.nodename,
        "kernel": uname.release,
        "arch": download.arch(),
        "musl": download.is_musl(),
        "python": "%d.%d.%d" % tuple(__import__("sys").version_info[:3]),
        "root": os.geteuid() == 0,
        "systemd": services.has_systemd(),
        "paths": {
            "etc": paths.ETC,
            "data": paths.DATA,
            "core_bin": paths.CORE_BIN,
            "xray_bin": paths.XRAY_BIN,
            "core_config": paths.CORE_CONFIG,
        },
        "accounting_available": stats.accounting_available(),
    }
