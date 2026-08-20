"""The panel's HTTP server: threading stdlib server, optional TLS, cookie
sessions, static files and a tiny JSON routing layer."""

import json
import mimetypes
import os
import re
import ssl
import traceback
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from . import auth, db, i18n, paths, settings

COOKIE_NAME = "snispoof_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "sni-spoof-panel"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; font-src 'self' data:; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
}


class ApiError(Exception):
    def __init__(self, message, status=400, key=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.key = key


class Request:
    def __init__(self, handler, path, query, body):
        self.handler = handler
        self.path = path
        self.query = query
        self.body = body
        self.headers = handler.headers
        self.method = handler.command
        self.client_ip = handler.client_ip
        self.user = None
        self.lang = "fa"
        self.params = {}

    def json(self):
        if not self.body:
            return {}
        try:
            data = json.loads(self.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError("malformed JSON body", 400) from None
        if not isinstance(data, dict):
            raise ApiError("expected a JSON object", 400)
        return data

    def q(self, key, default=None):
        values = self.query.get(key)
        return values[0] if values else default

    def q_int(self, key, default=0):
        try:
            return int(self.q(key, default))
        except (TypeError, ValueError):
            return default


class Response:
    def __init__(self, body=b"", status=200, content_type="application/json; charset=utf-8",
                 headers=None):
        self.body = body
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}

    @classmethod
    def json(cls, payload, status=200, headers=None):
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        return cls(body, status, "application/json; charset=utf-8", headers)

    @classmethod
    def text(cls, text, status=200, content_type="text/plain; charset=utf-8"):
        return cls(text.encode("utf-8"), status, content_type)


ROUTES = []


def route(method, pattern, auth_required=True, csrf=True):
    """Register a handler. `pattern` may contain <name> placeholders."""
    regex = re.compile(
        "^" + re.sub(r"<(\w+)>", r"(?P<\1>[^/]+)", pattern) + "$"
    )

    def decorator(func):
        ROUTES.append(
            {
                "method": method.upper(),
                "regex": regex,
                "handler": func,
                "auth": auth_required,
                "csrf": csrf,
            }
        )
        return func

    return decorator


def _match(method, path):
    allowed = False
    for entry in ROUTES:
        match = entry["regex"].match(path)
        if not match:
            continue
        if entry["method"] != method:
            allowed = True
            continue
        return entry, match.groupdict()
    return (None, None) if not allowed else ("405", None)


class Handler(BaseHTTPRequestHandler):
    server_version = "sni-spoof-panel"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # ---------------------------------------------------------------- helpers
    @property
    def client_ip(self):
        return self.client_address[0] if self.client_address else ""

    def log_message(self, fmt, *args):
        pass  # journald already records what matters

    def _send(self, response, extra_cookie=None):
        body = response.body or b""
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        for key, value in response.headers.items():
            self.send_header(key, value)
        if extra_cookie:
            self.send_header("Set-Cookie", extra_cookie)
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _error(self, message, status=400, key=None):
        self._send(Response.json({"ok": False, "error": message, "key": key}, status))

    def _cookies(self):
        raw = self.headers.get("Cookie", "")
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:
            return {}
        return {k: v.value for k, v in jar.items()}

    # ---------------------------------------------------------------- routing
    def do_GET(self):
        self._handle()

    def do_HEAD(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def do_PATCH(self):
        self._handle()

    def _handle(self):
        try:
            self._dispatch()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            db.log_event(
                "unhandled request error: %s" % traceback.format_exc(limit=4)[-800:],
                level="error", category="http",
            )
            try:
                self._error("internal server error", 500)
            except OSError:
                pass

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return b""
        if length > 64 * 1024 * 1024:
            raise ApiError("request body too large", 413)
        return self.rfile.read(length)

    def _dispatch(self):
        base = self.server.base_path
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if base != "/" and not (path == base.rstrip("/") or path.startswith(base)):
            self._send(Response.text("not found", 404))
            return
        if base != "/":
            path = path[len(base.rstrip("/")):] or "/"

        if not auth.ip_allowed(self.client_ip):
            self._send(Response.text("forbidden", 403))
            return

        query = parse_qs(parsed.query, keep_blank_values=True)
        body = self._read_body()
        request = Request(self, path, query, body)
        request.lang = (
            self.headers.get("X-Panel-Lang")
            or settings.get("panel", "language", "fa")
        )
        if request.lang not in i18n.LANGS:
            request.lang = i18n.DEFAULT_LANG

        cookie = self._cookies().get(COOKIE_NAME, "")
        request.user = auth.resolve_session(cookie) if cookie else None
        request.cookie_value = cookie

        entry, params = _match(self.command, path)
        if entry == "405":
            self._error("method not allowed", 405)
            return
        if entry is None:
            self._serve_static(path)
            return

        request.params = params or {}

        if entry["auth"] and request.user is None:
            self._error(i18n.t("unauthorized", request.lang), 401, "unauthorized")
            return
        if entry["csrf"] and self.command not in ("GET", "HEAD"):
            if self.headers.get(CSRF_HEADER, "").lower() != CSRF_VALUE:
                self._error("missing CSRF header", 403, "csrf")
                return

        try:
            result = entry["handler"](request)
        except ApiError as exc:
            self._error(exc.message, exc.status, exc.key)
            return
        except FileNotFoundError as exc:
            self._error(str(exc) or "not found", 404)
            return
        except (ValueError, KeyError) as exc:
            self._error(str(exc), 400)
            return

        cookie_header = getattr(request, "set_cookie", None)
        if isinstance(result, Response):
            self._send(result, cookie_header)
        else:
            payload = result if isinstance(result, dict) else {"data": result}
            payload.setdefault("ok", True)
            self._send(Response.json(payload), cookie_header)

    # ---------------------------------------------------------------- static
    def _serve_static(self, path):
        if path.startswith("/api/"):
            self._error("unknown endpoint", 404)
            return
        if path in ("/", ""):
            path = "/index.html"
        candidate = os.path.normpath(os.path.join(paths.STATIC_DIR, path.lstrip("/")))
        if not candidate.startswith(os.path.realpath(paths.STATIC_DIR)):
            self._send(Response.text("forbidden", 403))
            return
        if not os.path.isfile(candidate):
            # single-page app: unknown paths fall back to the shell
            candidate = os.path.join(paths.STATIC_DIR, "index.html")
            if not os.path.isfile(candidate):
                self._send(Response.text("not found", 404))
                return

        ctype = mimetypes.guess_type(candidate)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(candidate, "rb") as handle:
            data = handle.read()
        headers = {"Cache-Control": "no-store"} if candidate.endswith(".html") else {
            "Cache-Control": "public, max-age=300"
        }
        self._send(Response(data, 200, ctype, headers))


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64

    def __init__(self, address, base_path="/"):
        self.base_path = base_path if base_path.startswith("/") else "/" + base_path
        super().__init__(address, Handler)


def make_cookie(value, secure, max_age):
    parts = [
        "%s=%s" % (COOKIE_NAME, value),
        "Path=/",
        "HttpOnly",
        "SameSite=Strict",
        "Max-Age=%d" % max_age,
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_cookie(secure):
    return make_cookie("", secure, 0)


def serve(host=None, port=None):
    """Build and start the server (blocking)."""
    from . import api  # noqa: F401  (registers routes)

    cfg = settings.get("panel")
    host = host or cfg.get("host", "0.0.0.0")
    port = int(port or cfg.get("port", 2095))
    base_path = cfg.get("base_path", "/") or "/"

    server = PanelServer((host, port), base_path)

    tls = cfg.get("tls", {})
    if tls.get("enabled") and tls.get("cert") and tls.get("key"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(tls["cert"], tls["key"])
        server.socket = context.wrap_socket(server.socket, server_side=True)

    scheme = "https" if tls.get("enabled") else "http"
    db.log_event("panel listening on %s://%s:%d%s" % (scheme, host, port, base_path))
    return server
