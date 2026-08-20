"""Parsing and rewriting of vless / vmess / trojan share links.

Port of the Rust `xray.rs` logic, plus a rewriter that repoints a link at a
local sni-spoof listener while leaving every crypto/transport field alone."""

import base64
import json
from urllib.parse import parse_qsl, quote, unquote, urlsplit, urlunsplit

SUPPORTED = ("vless", "trojan", "vmess")


class ShareError(ValueError):
    pass


def _b64decode(payload):
    cleaned = "".join(payload.split())
    padded = cleaned + "=" * (-len(cleaned) % 4)
    try:
        return base64.b64decode(padded)
    except Exception:
        try:
            return base64.urlsafe_b64decode(padded)
        except Exception as exc:
            raise ShareError("invalid base64 payload") from exc


def _is_local(host):
    host = (host or "").strip().lower()
    if host in ("localhost", "0.0.0.0", "::", ""):
        return True
    return host.startswith("127.") or host == "::1"


def parse(link):
    """Return a normalized dict describing one share link."""
    text = (link or "").strip()
    if not text:
        raise ShareError("empty link")
    scheme = text.split("://", 1)[0].lower()
    if text.lower().startswith("v2rayn://"):
        raise ShareError(
            "v2rayN wrapped links are not supported; paste the plain vless:// / "
            "trojan:// / vmess:// link instead"
        )
    if scheme == "vmess":
        return _parse_vmess(text)
    if scheme in ("vless", "trojan"):
        return _parse_url_style(text, scheme)
    raise ShareError("unsupported link type: %s" % scheme)


def _parse_url_style(text, scheme):
    parts = urlsplit(text)
    host = parts.hostname
    if not host:
        raise ShareError("link has no host")
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    tls = (query.get("security", "").lower() in ("tls", "reality", "xtls"))
    port = parts.port or (443 if tls else 80)

    return _finish(
        {
            "protocol": scheme,
            "name": unquote(parts.fragment or "").strip(),
            "user_id": unquote(parts.username or ""),
            "host": host,
            "port": int(port),
            "security": query.get("security", "tls" if tls else ""),
            "encryption": query.get("encryption", ""),
            "sni": query.get("sni", "").rstrip("."),
            "http_host": query.get("host", ""),
            "network": query.get("type", ""),
            "fingerprint": query.get("fp", ""),
            "path": unquote(query.get("path", "")),
            "mode": query.get("mode", ""),
            "service_name": query.get("serviceName", ""),
            "flow": query.get("flow", ""),
            "alpn": query.get("alpn", ""),
            "public_key": query.get("pbk", ""),
            "short_id": query.get("sid", ""),
            "spider_x": query.get("spx", ""),
            "allow_insecure": query.get("allowInsecure", query.get("insecure", "0"))
            in ("1", "true", "True"),
            "tls": tls,
            "extra": query.get("extra", ""),
            "raw": text,
            "query": query,
        }
    )


def _parse_vmess(text):
    payload = text.split("://", 1)[1]
    data = json.loads(_b64decode(payload).decode("utf-8", "replace"))
    tls = str(data.get("tls", "")).lower() in ("tls", "reality")
    try:
        port = int(data.get("port") or (443 if tls else 80))
    except (TypeError, ValueError):
        raise ShareError("invalid vmess port") from None
    return _finish(
        {
            "protocol": "vmess",
            "name": data.get("ps", ""),
            "user_id": data.get("id", ""),
            "host": data.get("add", ""),
            "port": port,
            "security": data.get("tls", ""),
            "encryption": data.get("scy", "auto"),
            "sni": (data.get("sni") or "").rstrip("."),
            "http_host": data.get("host", ""),
            "network": data.get("net", ""),
            "fingerprint": data.get("fp", ""),
            "path": data.get("path", ""),
            "mode": "",
            "service_name": data.get("path", "") if data.get("net") == "grpc" else "",
            "flow": "",
            "alpn": data.get("alpn", ""),
            "allow_insecure": str(data.get("allowInsecure", "")) in ("1", "true"),
            "tls": tls,
            "aid": int(data.get("aid") or 0),
            "raw": text,
            "vmess": data,
        }
    )


def _finish(item):
    if not item.get("host"):
        raise ShareError("link has no host")
    item.setdefault("query", {})
    item["local_endpoint"] = _is_local(item["host"])
    if item["local_endpoint"]:
        # Already repointed at a local forwarder: the true upstream lives in
        # host= or sni=.
        upstream = item.get("http_host") or item.get("sni") or item["host"]
        item["upstream_host"] = upstream
        item["upstream_port"] = 443 if item["tls"] else 80
    else:
        item["upstream_host"] = item["host"]
        item["upstream_port"] = item["port"]
    item["label"] = item.get("name") or item["host"]
    return item


def rewrite(link, new_host, new_port, new_name=None):
    """Return the same config pointed at `new_host:new_port`."""
    item = parse(link)
    if item["protocol"] == "vmess":
        data = dict(item["vmess"])
        data["add"] = new_host
        data["port"] = str(new_port)
        if new_name:
            data["ps"] = new_name
        payload = base64.b64encode(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        return "vmess://" + payload

    parts = urlsplit(item["raw"])
    userinfo = quote(item["user_id"], safe="")
    netloc = "%s@%s:%d" % (userinfo, new_host, int(new_port))
    fragment = quote(new_name if new_name is not None else item["name"], safe="")
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, fragment))


def choose_upstream(item, resolver=None):
    """Pick the host the listener should dial, and say why.

    Panels such as 3x-ui hand out links whose address is the *origin* IP, with
    the Cloudflare-proxied domain only present in `sni=` / `host=`. Dialing that
    origin bypasses Cloudflare entirely, which defeats the whole technique: the
    decoy SNI has nothing to hide behind and DPI simply resets the real
    ClientHello. So when the link's address is not a Cloudflare edge but the
    config carries a domain that is, prefer the domain.

    Returns (host, port, ip, note).
    """
    from . import netutil

    resolve = resolver or netutil.pick_upstream_ip
    port = int(item["upstream_port"])
    primary = item["upstream_host"]

    primary_ip, primary_error = None, None
    try:
        primary_ip, _ = resolve(primary, port)
        if netutil.is_cloudflare(primary_ip):
            return primary, port, primary_ip, ""
    except ValueError as exc:
        primary_error = str(exc)

    for domain in (item.get("sni"), item.get("http_host")):
        if not domain or domain == primary or netutil.is_ip(domain):
            continue
        try:
            ip, _ = resolve(domain, port)
        except ValueError:
            continue
        if netutil.is_cloudflare(ip):
            return domain, port, ip, (
                "the link address %s is not a Cloudflare edge; using %s from the "
                "config's sni/host instead, which resolves to the Cloudflare edge %s"
                % (primary, domain, ip)
            )

    if primary_ip is None:
        raise ValueError(primary_error or "could not resolve %s" % primary)
    return primary, port, primary_ip, ""


def to_listener_payload(item, listen_host="0.0.0.0", listen_port=40443, fake_sni=None,
                        resolver=None):
    """Turn a parsed link into the listener payload that fronts it."""
    host, port, upstream_ip, note = choose_upstream(item, resolver)
    remark = "imported from %s link" % item["protocol"]
    if note:
        remark = "%s — %s" % (remark, note)
    return {
        "name": item["label"][:80],
        "enabled": True,
        "listen_host": listen_host,
        "listen_port": int(listen_port),
        "connect_host": host,
        "connect_ip": upstream_ip,
        "connect_port": port,
        "fake_sni": fake_sni or "security.vercel.com",
        "remark": remark[:500],
    }


def summary(item):
    """Small dict safe to hand to the UI (no raw credentials echoed back)."""
    return {
        "protocol": item["protocol"],
        "label": item["label"],
        "host": item["host"],
        "port": item["port"],
        "upstream_host": item["upstream_host"],
        "upstream_port": item["upstream_port"],
        "network": item.get("network", ""),
        "security": item.get("security", ""),
        "sni": item.get("sni", ""),
        "http_host": item.get("http_host", ""),
        "path": item.get("path", ""),
        "fingerprint": item.get("fingerprint", ""),
        "tls": item.get("tls", False),
        "local_endpoint": item.get("local_endpoint", False),
    }


def parse_many(text):
    """Parse a blob of links (one per line, or a base64 subscription body)."""
    blob = (text or "").strip()
    if blob and "://" not in blob:
        try:
            blob = _b64decode(blob).decode("utf-8", "replace")
        except ShareError:
            pass
    parsed, errors = [], []
    for line in blob.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parsed.append(parse(line))
        except ShareError as exc:
            errors.append({"line": line[:120], "error": str(exc)})
    return parsed, errors


def subscription(links):
    """Base64 subscription body, the format every client understands."""
    body = "\n".join(links)
    return base64.b64encode(body.encode("utf-8")).decode("ascii")
