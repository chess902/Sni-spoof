"""Telegram notifications and backup delivery over the plain Bot API."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid

from . import settings

API = "https://api.telegram.org/bot%s/%s"


def configured():
    cfg = settings.get("telegram")
    return bool(cfg.get("enabled") and cfg.get("bot_token") and cfg.get("chat_id"))


def _call(method, payload, timeout=15):
    cfg = settings.get("telegram")
    url = API % (cfg["bot_token"], method)
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(text, force=False, parse_mode="HTML"):
    if not force and not configured():
        return {"ok": False, "reason": "telegram not configured"}
    cfg = settings.get("telegram")
    try:
        return _call(
            "sendMessage",
            {
                "chat_id": cfg["chat_id"],
                "text": text[:4000],
                "parse_mode": parse_mode,
                "disable_web_page_preview": "true",
            },
        )
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "reason": str(exc)}


def send_document(path, caption=""):
    """Multipart upload without any HTTP client dependency."""
    if not configured():
        return {"ok": False, "reason": "telegram not configured"}
    cfg = settings.get("telegram")
    boundary = uuid.uuid4().hex
    with open(path, "rb") as handle:
        payload = handle.read()

    def part(name, value):
        return (
            ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
             % (boundary, name, value)).encode("utf-8")
        )

    body = part("chat_id", cfg["chat_id"])
    if caption:
        body += part("caption", caption[:1000])
    body += (
        "--%s\r\nContent-Disposition: form-data; name=\"document\"; filename=\"%s\"\r\n"
        "Content-Type: application/gzip\r\n\r\n" % (boundary, os.path.basename(path))
    ).encode("utf-8")
    body += payload + ("\r\n--%s--\r\n" % boundary).encode("utf-8")

    request = urllib.request.Request(
        API % (cfg["bot_token"], "sendDocument"),
        data=body,
        headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "reason": str(exc)}


def notify(kind, text):
    """Send only if the operator enabled this notification kind."""
    cfg = settings.get("telegram")
    if not cfg.get("notify_%s" % kind, True):
        return {"ok": False, "reason": "muted"}
    return send_message(text)


def test():
    import socket

    result = send_message(
        "✅ <b>sni-spoof panel</b>\nTelegram notifications are working.\nHost: <code>%s</code>"
        % socket.gethostname(),
        force=True,
    )
    return result
