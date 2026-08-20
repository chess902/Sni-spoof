"""Command line interface. The bash manager script drives the panel through
these subcommands, so everything the web UI can do is scriptable too."""

import argparse
import getpass
import json
import os
import secrets
import sys
import time

from . import (
    __version__, auth, backup, certs, core, db, netutil, paths, qrcode, scanner,
    services, settings, share, stats, tasks, telegram, xray,
)


def _out(data, as_json=False):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, default=str, indent=2))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, default=str, indent=2))


def _human_bytes(value):
    value = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return "%.1f %s" % (value, unit)
        value /= 1024


def _bootstrap():
    paths.ensure_dirs()
    db.init()


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def cmd_serve(args):
    from . import httpd

    _bootstrap()
    if auth.user_count() == 0:
        username, password = ensure_admin()
        print("created initial admin: %s / %s" % (username, password), file=sys.stderr)

    if settings.get("core", "auto_start", True):
        try:
            core.write_config()
        except Exception as exc:  # never block startup on a config problem
            print("warning: could not write core config: %s" % exc, file=sys.stderr)

    tasks.start()
    server = httpd.serve(args.host, args.port)
    scheme = "https" if settings.get("panel", "tls", {}).get("enabled") else "http"
    print(
        "sni-spoof panel %s listening on %s://%s:%d%s"
        % (
            __version__, scheme,
            server.server_address[0], server.server_address[1],
            settings.get("panel", "base_path", "/"),
        ),
        file=sys.stderr,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        tasks.stop()
        server.server_close()
    return 0


def ensure_admin(username=None, password=None):
    username = username or "admin"
    password = password or secrets.token_urlsafe(12)
    existing = auth.get_user(username)
    if existing:
        auth.set_password(existing["id"], password)
    else:
        auth.create_user(username, password)
    return username, password


def cmd_setup(args):
    _bootstrap()
    username = args.username or "admin"
    password = args.password or secrets.token_urlsafe(12)
    ensure_admin(username, password)

    panel_settings = {}
    if args.port:
        panel_settings["port"] = int(args.port)
    if args.host:
        panel_settings["host"] = args.host
    if args.path:
        base = args.path if args.path.startswith("/") else "/" + args.path
        panel_settings["base_path"] = base
    if args.language:
        panel_settings["language"] = args.language
    if panel_settings:
        settings.update("panel", panel_settings)

    cfg = settings.get("panel")
    _out(
        {
            "username": username,
            "password": password,
            "port": cfg["port"],
            "base_path": cfg["base_path"],
            "url": settings.panel_url(netutil.local_ip_for()),
        },
        args.json,
    )
    return 0


def cmd_status(args):
    _bootstrap()
    snapshot = stats.snapshot()
    payload = {
        "panel_version": __version__,
        "core_version": core.installed_version(),
        "core_installed": core.is_installed(),
        "xray_version": xray.installed_version(),
        "services": snapshot["services"],
        "listeners": snapshot["listeners"],
        "cpu": snapshot["cpu"],
        "memory_percent": snapshot["memory"]["percent"],
        "url": settings.panel_url(netutil.local_ip_for()),
    }
    if args.json:
        _out(payload, True)
        return 0

    print("sni-spoof panel %s" % __version__)
    print("  panel URL   : %s" % payload["url"])
    print("  core binary : %s (%s)" % (
        core.installed_version() or "not installed",
        "present" if core.is_installed() else "missing",
    ))
    print("  xray binary : %s" % (xray.installed_version() or "not installed"))
    for alias, info in snapshot["services"].items():
        state = "active" if info["active"] else info["state"]
        print("  service %-6s: %-10s enabled=%s" % (alias, state, info["enabled"]))
    print("  cpu %.1f%%  mem %.1f%%  load %s" % (
        snapshot["cpu"], snapshot["memory"]["percent"], snapshot["load"]))
    if snapshot["listeners"]:
        print("  listeners:")
        for item in snapshot["listeners"]:
            print("    #%-3d %-18s port=%-6d listening=%-5s conns=%d" % (
                item["id"], (item["name"] or "-")[:18], item["port"],
                item["listening"], item["established"]))
    else:
        print("  listeners: none configured")
    return 0


def cmd_doctor(args):
    """Explain, in order, why the stack is not serving traffic."""
    _bootstrap()
    checks = []

    def check(name, ok, detail="", fix="", skipped=False):
        checks.append({
            "check": name, "ok": bool(ok), "detail": detail,
            "fix": fix, "skipped": bool(skipped),
        })

    check("core binary installed", core.is_installed(),
          paths.CORE_BIN if core.is_installed() else "missing",
          "sni-spoof cli core install")

    listeners = core.list_listeners()
    enabled = [l for l in listeners if l["enabled"]]
    check("listeners configured", bool(enabled),
          "%d total, %d enabled" % (len(listeners), len(enabled)),
          "sni-spoof cli link import 'vless://…'  (or the Configs page)")

    config_exists = os.path.exists(paths.CORE_CONFIG)
    check("core config written", config_exists, paths.CORE_CONFIG,
          "sni-spoof cli core apply")

    # Without listeners everything downstream is a consequence, not a cause;
    # report those as skipped so one actionable line stands out.
    if not enabled:
        check("core marked ready", True, "skipped — nothing to serve yet", skipped=True)
        check("core service running", True, "skipped — nothing to serve yet", skipped=True)
    else:
        check("core marked ready", os.path.exists(paths.CORE_READY),
              "flag gating the systemd unit", "sni-spoof cli core apply")
        svc = services.status("core")
        check("core service running", svc["active"],
              "%s/%s" % (svc["state"], svc["sub"] or "-"),
              "sni-spoof cli service core restart  ·  sni-spoof log core")

    for item in enabled:
        result = tasks.health_check(item, timeout=6)
        label = "listener #%d :%d" % (item["id"], item["listen_port"])
        if not result["tcp_ok"]:
            check(label, False, result["error"], "check the core log")
        elif result["tls_ok"] is False:
            check(label, False, "TCP ok but TLS failed: %s" % result["error"],
                  "the fake SNI is probably burned — run: sni-spoof cli scan --apply")
        else:
            check(label, True, "tcp %sms tls %sms" % (result["tcp_ms"], result["tls_ms"]))
        if netutil.is_local_address(item["connect_ip"]):
            check("  ↳ upstream %s" % item["connect_ip"], False,
                  "this is an address of THIS server — the sniffer can never "
                  "see the handshake",
                  "point the upstream at your config's Cloudflare edge IP, "
                  "not at this machine")
            continue
        upstream_ok, upstream_ms, upstream_err = netutil.tcp_probe(
            item["connect_ip"], item["connect_port"], 6
        )
        check("  ↳ upstream %s:%d" % (item["connect_ip"], item["connect_port"]),
              upstream_ok, upstream_err or "%sms" % upstream_ms,
              "sni-spoof cli listener refresh")
        if upstream_ok and not netutil.is_cloudflare(item["connect_ip"]):
            check("  ↳ upstream is a Cloudflare edge", False,
                  "%s is outside Cloudflare's published ranges" % item["connect_ip"],
                  "this technique only works against a Cloudflare edge — put "
                  "your domain behind Cloudflare and re-import the config")

    xray_cfg = settings.get("xray")
    if xray_cfg.get("enabled"):
        check("xray installed", xray.is_installed(), xray.installed_version() or "missing",
              "sni-spoof cli xray install")
        check("xray config written", os.path.exists(paths.XRAY_CONFIG), paths.XRAY_CONFIG,
              "sni-spoof cli xray apply")
        xsvc = services.status("xray")
        check("xray service running", xsvc["active"], xsvc["state"],
              "sni-spoof cli xray apply")

        host = xray_cfg["listen"]
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        http_port, socks_port = xray_cfg["http_port"], xray_cfg["socks_port"]
        if xsvc["active"]:
            ok_socks, detail = netutil.speaks_socks5(host, socks_port)
            check("SOCKS5 proxy on :%s" % socks_port, ok_socks, detail,
                  "point SOCKS clients at %s:%s (NOT the HTTP port)" % (host, socks_port))
            ok_http, detail = netutil.speaks_http_proxy(host, http_port)
            check("HTTP proxy on :%s" % http_port, ok_http, detail,
                  "point HTTP clients at %s:%s" % (host, http_port))
            if enabled:
                try:
                    egress = netutil.public_ip_via_socks(
                        host, socks_port, timeout=12,
                        username=xray_cfg.get("auth_user", ""),
                        password=xray_cfg.get("auth_pass", ""),
                    )
                    check("tunnel egress IP", bool(egress.get("ip")),
                          "%s (must be your FOREIGN server, not this one)" % egress.get("ip"))
                except Exception as exc:
                    check("tunnel egress IP", False, str(exc)[:110],
                          "the tunnel is not carrying traffic — fix the listener first")
        else:
            check("proxy ports", True, "skipped — xray is not running", skipped=True)

    panel_cfg = settings.get("panel")
    check("panel port free or ours", True, "port %s" % panel_cfg["port"])

    if args.json:
        _out(checks, True)
        return 0 if all(c["ok"] for c in checks) else 1

    print("sni-spoof doctor")
    print()
    failed = 0
    for item in checks:
        if item["skipped"]:
            mark = "\033[2m--  \033[0m"
        elif item["ok"]:
            mark = "\033[32mOK  \033[0m"
        else:
            mark = "\033[31mFAIL\033[0m"
        print("  [%s] %-34s %s" % (mark, item["check"], item["detail"]))
        if not item["ok"] and not item["skipped"]:
            failed += 1
            if item["fix"]:
                print("         \033[33m↳ %s\033[0m" % item["fix"])
    print()
    if failed:
        print("%d check(s) failed — the first FAIL above is usually the real cause." % failed)
    else:
        print("Everything checks out.")
    return 0 if not failed else 1


def cmd_url(args):
    _bootstrap()
    print(settings.panel_url(netutil.local_ip_for()))
    return 0


def cmd_user(args):
    _bootstrap()
    if args.action == "list":
        rows = db.query("SELECT id, username, role, enabled, last_login FROM users ORDER BY id")
        _out([dict(r) for r in rows], args.json)
    elif args.action == "add":
        password = args.password or getpass.getpass("password: ")
        if len(password) < 8:
            print("password must be at least 8 characters", file=sys.stderr)
            return 1
        user_id = auth.create_user(args.username, password)
        _out({"id": user_id, "username": args.username}, args.json)
    elif args.action == "passwd":
        user = auth.get_user(args.username)
        if not user:
            print("no such user", file=sys.stderr)
            return 1
        password = args.password or secrets.token_urlsafe(12)
        auth.set_password(user["id"], password)
        _out({"username": args.username, "password": password}, args.json)
    elif args.action == "delete":
        user = auth.get_user(args.username)
        if not user:
            print("no such user", file=sys.stderr)
            return 1
        if auth.user_count() <= 1:
            print("at least one user must remain", file=sys.stderr)
            return 1
        db.execute("DELETE FROM users WHERE id=?", (user["id"],))
        _out({"deleted": args.username}, args.json)
    return 0


def cmd_settings(args):
    _bootstrap()
    if args.action == "get":
        data = settings.get_all()
        if args.section:
            data = data.get(args.section, {})
            if args.key:
                data = data.get(args.key)
        _out(data, True)
    elif args.action == "set":
        try:
            value = json.loads(args.value)
        except ValueError:
            value = args.value
        settings.update(args.section, {args.key: value})
        _out(settings.get(args.section), True)
        if args.section == "core":
            core.apply(restart=True)
    return 0


def cmd_listener(args):
    _bootstrap()
    if args.action == "list":
        items = core.list_listeners()
        if args.json:
            _out(items, True)
        elif not items:
            print("no listeners configured")
        else:
            print("%-4s %-18s %-22s %-22s %-28s %s" % (
                "ID", "NAME", "LISTEN", "UPSTREAM", "FAKE SNI", "ON"))
            for item in items:
                print("%-4d %-18s %-22s %-22s %-28s %s" % (
                    item["id"], (item["name"] or "-")[:18],
                    "%s:%d" % (item["listen_host"], item["listen_port"]),
                    "%s:%d" % (item["connect_ip"], item["connect_port"]),
                    item["fake_sni"][:28], "yes" if item["enabled"] else "no"))
    elif args.action == "add":
        payload = {
            "name": args.name or "",
            "listen_host": args.listen_host,
            "listen_port": args.listen_port,
            "connect_host": args.connect_host or "",
            "connect_ip": args.connect_ip or "",
            "connect_port": args.connect_port,
            "fake_sni": args.fake_sni,
        }
        try:
            item = core.create_listener(payload)
        except core.ValidationError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 1
        core.apply(restart=True)
        _out(item, args.json)
    elif args.action == "delete":
        core.delete_listener(args.id)
        core.apply(restart=True)
        _out({"deleted": args.id}, args.json)
    elif args.action == "toggle":
        item = core.toggle_listener(args.id, args.enabled)
        core.apply(restart=True)
        _out(item, args.json)
    elif args.action == "apply":
        _out(core.apply(restart=True), args.json)
    elif args.action == "test":
        results = tasks.check_all(timeout=8)
        if args.json:
            _out(results, True)
        else:
            for item in results:
                print("listener #%d port %d: tcp=%s%s" % (
                    item["listener_id"], item["port"],
                    "ok" if item["tcp_ok"] else "FAIL",
                    "" if item["tls_ok"] is None else (
                        "  tls=%s" % ("ok" if item["tls_ok"] else "FAIL")),
                ))
                if item["error"]:
                    print("    %s" % item["error"])
    elif args.action == "refresh":
        for item in core.list_listeners(enabled_only=True):
            if not item["connect_host"]:
                continue
            try:
                result = core.refresh_listener_ip(item["id"])
                print("#%d %s -> %s%s" % (
                    item["id"], item["connect_host"], result["ip"],
                    "  (changed)" if result["changed"] else ""))
            except core.ValidationError as exc:
                print("#%d error: %s" % (item["id"], exc), file=sys.stderr)
        core.apply(restart=True)
    return 0


def cmd_link(args):
    _bootstrap()
    if args.action == "import":
        text = args.link
        if text == "-":
            text = sys.stdin.read()
        parsed, errors = share.parse_many(text)
        if not parsed:
            print("no valid link found: %s" % (errors[0]["error"] if errors else ""),
                  file=sys.stderr)
            return 1
        created = []
        port = args.listen_port
        for item in parsed:
            while any(l["listen_port"] == port for l in core.list_listeners()):
                port += 1
            try:
                payload = share.to_listener_payload(item, args.listen_host, port, args.fake_sni)
                listener = core.create_listener(payload)
            except (core.ValidationError, ValueError) as exc:
                print("skipped %s: %s" % (item["label"], exc), file=sys.stderr)
                continue
            link_id = db.insert(
                "INSERT INTO links (listener_id, name, protocol, raw, parsed, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (listener["id"], item["label"], item["protocol"], item["raw"],
                 json.dumps(share.summary(item), ensure_ascii=False), int(time.time())),
            )
            created.append({"link_id": link_id, "listener_id": listener["id"],
                            "label": item["label"], "port": listener["listen_port"]})
            port += 1
        core.apply(restart=True)
        if settings.get("xray", "active_link_id") is None and created:
            settings.update("xray", {"active_link_id": created[0]["link_id"]})
        _out({"created": created, "errors": errors}, args.json)
    elif args.action == "list":
        rows = db.query("SELECT id, listener_id, name, protocol, created_at FROM links ORDER BY id")
        if args.json:
            _out([dict(r) for r in rows], True)
        elif not rows:
            print("no links stored")
        else:
            print("%-4s %-10s %-24s %s" % ("ID", "PROTO", "NAME", "LISTENER"))
            for row in rows:
                print("%-4d %-10s %-24s %s" % (
                    row["id"], row["protocol"], (row["name"] or "-")[:24],
                    row["listener_id"] or "-"))
    elif args.action == "show":
        row = db.one("SELECT * FROM links WHERE id=?", (args.id,))
        if not row:
            print("no such link", file=sys.stderr)
            return 1
        listener = core.get_listener(row["listener_id"]) if row["listener_id"] else None
        host = args.host or netutil.local_ip_for()
        port = args.port or (listener["listen_port"] if listener else 40443)
        client = share.rewrite(row["raw"], host, port, row["name"] or None)
        if args.json:
            _out({"link": client}, True)
        else:
            print(client)
            print()
            print(qrcode.to_text(client, "L"))
    elif args.action == "delete":
        db.execute("DELETE FROM links WHERE id=?", (args.id,))
        _out({"deleted": args.id}, args.json)
    return 0


def cmd_scan(args):
    _bootstrap()
    snis = None
    if args.list:
        with open(args.list, "r", encoding="utf-8") as handle:
            snis = [l.strip() for l in handle if l.strip() and not l.startswith("#")]
    scanner.start(args.target, snis, args.timeout, args.concurrency)
    last = -1
    while True:
        state = scanner.status()
        if state["done"] != last and not args.json:
            print("\r  progress: %d/%d  (%d passed)" % (
                state["done"], state["total"], state["ok"]), end="", file=sys.stderr)
            last = state["done"]
        if not state["running"]:
            break
        time.sleep(0.4)
    if not args.json:
        print(file=sys.stderr)

    results = scanner.status()["results"]
    if args.json:
        _out(results, True)
    else:
        print("%d working SNIs:" % len(results))
        for item in results:
            print("  %-42s %6.1f ms" % (item["sni"], item["ms"]))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write("\n".join(item["sni"] for item in results) + "\n")
        print("wrote %s" % args.output, file=sys.stderr)
    if args.apply and results:
        best = results[0]["sni"]
        for item in core.list_listeners():
            core.update_listener(item["id"], {"fake_sni": best})
        core.apply(restart=True)
        print("applied fake_sni=%s to all listeners" % best, file=sys.stderr)
    return 0


def cmd_core(args):
    _bootstrap()
    if args.action == "install":
        _out(core.install(args.version), args.json)
        core.apply(restart=True)
    elif args.action == "update":
        _out(core.check_update(), True)
    elif args.action == "config":
        _out(core.build_config(), True)
    elif args.action == "apply":
        _out(core.apply(restart=True), args.json)
    return 0


def cmd_xray(args):
    _bootstrap()
    if args.action == "install":
        _out(xray.install(args.version), args.json)
    elif args.action == "update":
        _out(xray.check_update(), True)
    elif args.action == "apply":
        _out(xray.apply(restart=True), args.json)
    elif args.action == "config":
        _, config = xray.write_config()
        _out(config, True)
    elif args.action == "test":
        ok, output = xray.test_config()
        print(output)
        return 0 if ok else 1
    return 0


def cmd_backup(args):
    _bootstrap()
    if args.action == "create":
        path = backup.create(args.label)
        print(path)
        if args.telegram and telegram.configured():
            telegram.send_document(path, "sni-spoof backup")
    elif args.action == "list":
        items = backup.listing()
        if args.json:
            _out(items, True)
        elif not items:
            print("no backups yet")
        else:
            for item in items:
                print("%-46s %10s  %s" % (
                    item["name"], _human_bytes(item["size"]),
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(item["mtime"]))))
    elif args.action == "restore":
        path = args.path if os.path.isabs(args.path) else backup.path_for(args.path)
        _out(backup.restore(path), args.json)
    return 0


def cmd_cert(args):
    _bootstrap()
    if args.action == "self-signed":
        result = certs.self_signed(args.domain or netutil.local_ip_for())
        certs.enable_tls(result["cert"], result["key"])
        _out(result, args.json)
    elif args.action == "acme":
        result = certs.issue_acme(args.domain, args.email, args.port)
        certs.enable_tls(result["cert"], result["key"])
        _out(result, args.json)
    elif args.action == "disable":
        certs.disable_tls()
        _out({"tls": False}, args.json)
    elif args.action == "info":
        _out(certs.info(), True)
    elif args.action == "renew":
        ok, output = certs.renew_acme()
        print(output)
        return 0 if ok else 1
    return 0


def cmd_service(args):
    _bootstrap()
    ok, message = services.action(args.name, args.verb)
    print(message or ("ok" if ok else "failed"))
    return 0 if ok else 1


def cmd_qr(args):
    text = args.text
    if text == "-":
        text = sys.stdin.read().strip()
    print(qrcode.to_text(text, "L"))
    return 0


def cmd_ip(args):
    _bootstrap()
    if args.local:
        print(netutil.local_ip_for())
        return 0
    try:
        if args.via == "http":
            cfg = settings.get("xray")
            host = "127.0.0.1" if cfg["listen"] in ("0.0.0.0", "::") else cfg["listen"]
            result = netutil.public_ip(proxy="http://%s:%s" % (host, cfg["http_port"]))
        elif args.via == "socks":
            cfg = settings.get("xray")
            host = "127.0.0.1" if cfg["listen"] in ("0.0.0.0", "::") else cfg["listen"]
            result = netutil.public_ip_via_socks(
                host, cfg["socks_port"],
                username=cfg.get("auth_user", ""), password=cfg.get("auth_pass", ""),
            )
        else:
            result = netutil.public_ip()
    except Exception as exc:
        print("failed: %s" % exc, file=sys.stderr)
        return 1
    _out(result, args.json)
    return 0


def cmd_subscription(args):
    _bootstrap()
    token = db.get_meta("sub_token", "")
    if not token or args.rotate:
        token = secrets.token_urlsafe(18)
        db.set_meta("sub_token", token)
    cfg = settings.get("panel")
    scheme = "https" if cfg["tls"]["enabled"] else "http"
    host = args.host or netutil.local_ip_for()
    base = (cfg.get("base_path", "/") or "/").rstrip("/")
    print("%s://%s:%d%s/sub/%s" % (scheme, host, cfg["port"], base, token))
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(
        prog="sni-spoof-panel", description="sni-spoof panel management CLI"
    )
    parser.add_argument("--json", action="store_true", help="machine readable output")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the web panel")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.set_defaults(func=cmd_serve)

    setup = sub.add_parser("setup", help="create the first admin and panel settings")
    setup.add_argument("--username")
    setup.add_argument("--password")
    setup.add_argument("--port", type=int)
    setup.add_argument("--host")
    setup.add_argument("--path")
    setup.add_argument("--language", choices=("fa", "en"))
    setup.set_defaults(func=cmd_setup)

    sub.add_parser("status", help="show a summary").set_defaults(func=cmd_status)
    sub.add_parser("url", help="print the panel URL").set_defaults(func=cmd_url)
    sub.add_parser("doctor", help="diagnose why traffic is not flowing").set_defaults(
        func=cmd_doctor
    )

    user = sub.add_parser("user", help="manage panel users")
    user.add_argument("action", choices=("list", "add", "passwd", "delete"))
    user.add_argument("username", nargs="?")
    user.add_argument("--password")
    user.set_defaults(func=cmd_user)

    setting = sub.add_parser("settings", help="read or write settings")
    setting.add_argument("action", choices=("get", "set"))
    setting.add_argument("section", nargs="?")
    setting.add_argument("key", nargs="?")
    setting.add_argument("value", nargs="?")
    setting.set_defaults(func=cmd_settings)

    listener = sub.add_parser("listener", help="manage listeners")
    listener.add_argument(
        "action", choices=("list", "add", "delete", "toggle", "apply", "test", "refresh")
    )
    listener.add_argument("--id", type=int)
    listener.add_argument("--name")
    listener.add_argument("--listen-host", default="0.0.0.0")
    listener.add_argument("--listen-port", type=int, default=40443)
    listener.add_argument("--connect-host")
    listener.add_argument("--connect-ip")
    listener.add_argument("--connect-port", type=int, default=443)
    listener.add_argument("--fake-sni", default=core.DEFAULT_FAKE_SNI)
    listener.add_argument("--enabled", type=int, default=1)
    listener.set_defaults(func=cmd_listener)

    link = sub.add_parser("link", help="import and inspect share links")
    link.add_argument("action", choices=("import", "list", "show", "delete"))
    link.add_argument("link", nargs="?", default="-")
    link.add_argument("--id", type=int)
    link.add_argument("--host")
    link.add_argument("--port", type=int)
    link.add_argument("--listen-host", default="0.0.0.0")
    link.add_argument("--listen-port", type=int, default=40443)
    link.add_argument("--fake-sni", default=core.DEFAULT_FAKE_SNI)
    link.set_defaults(func=cmd_link)

    scan = sub.add_parser("scan", help="probe fake SNI candidates")
    scan.add_argument("--target")
    scan.add_argument("--timeout", type=float)
    scan.add_argument("--concurrency", type=int)
    scan.add_argument("--list")
    scan.add_argument("--output", "-o")
    scan.add_argument("--apply", action="store_true", help="apply the fastest hit")
    scan.set_defaults(func=cmd_scan)

    core_cmd = sub.add_parser("core", help="manage the sni-spoof-rs binary")
    core_cmd.add_argument("action", choices=("install", "update", "config", "apply"))
    core_cmd.add_argument("--version")
    core_cmd.set_defaults(func=cmd_core)

    xray_cmd = sub.add_parser("xray", help="manage Xray")
    xray_cmd.add_argument("action", choices=("install", "update", "apply", "config", "test"))
    xray_cmd.add_argument("--version")
    xray_cmd.set_defaults(func=cmd_xray)

    backup_cmd = sub.add_parser("backup", help="backup and restore")
    backup_cmd.add_argument("action", choices=("create", "list", "restore"))
    backup_cmd.add_argument("path", nargs="?")
    backup_cmd.add_argument("--label")
    backup_cmd.add_argument("--telegram", action="store_true")
    backup_cmd.set_defaults(func=cmd_backup)

    cert = sub.add_parser("cert", help="TLS certificates for the panel")
    cert.add_argument("action", choices=("self-signed", "acme", "disable", "info", "renew"))
    cert.add_argument("--domain")
    cert.add_argument("--email")
    cert.add_argument("--port", type=int, default=80)
    cert.set_defaults(func=cmd_cert)

    service = sub.add_parser("service", help="control systemd units")
    service.add_argument("name", choices=tuple(services.MANAGED))
    service.add_argument("verb", choices=("start", "stop", "restart", "enable", "disable"))
    service.set_defaults(func=cmd_service)

    qr = sub.add_parser("qr", help="render text as a QR code")
    qr.add_argument("text")
    qr.set_defaults(func=cmd_qr)

    ip = sub.add_parser("ip", help="show the egress IP")
    ip.add_argument("--via", choices=("direct", "http", "socks"), default="direct")
    ip.add_argument("--local", action="store_true", help="print the LAN address instead")
    ip.set_defaults(func=cmd_ip)

    subs = sub.add_parser("subscription", help="print the subscription URL")
    subs.add_argument("--host")
    subs.add_argument("--rotate", action="store_true")
    subs.set_defaults(func=cmd_subscription)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print("error: %s" % exc, file=sys.stderr)
        if os.environ.get("SNI_SPOOF_DEBUG"):
            raise
        return 1
