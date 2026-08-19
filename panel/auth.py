"""Authentication: PBKDF2 passwords, signed session cookies, TOTP 2FA,
brute-force throttling and IP allowlisting."""

import base64
import hashlib
import hmac
import ipaddress
import os
import secrets
import struct
import time

from . import db, settings

PBKDF2_ROUNDS = 240_000


# --------------------------------------------------------------------------
# passwords
# --------------------------------------------------------------------------
def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    )
    return digest.hex(), salt


def verify_password(password, pw_hash, salt):
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, pw_hash)


def create_user(username, password, role="admin"):
    pw_hash, salt = hash_password(password)
    return db.insert(
        "INSERT INTO users (username, pw_hash, pw_salt, role, created_at) "
        "VALUES (?,?,?,?,?)",
        (username.strip(), pw_hash, salt, role, int(time.time())),
    )


def set_password(user_id, password):
    pw_hash, salt = hash_password(password)
    db.execute(
        "UPDATE users SET pw_hash=?, pw_salt=? WHERE id=?", (pw_hash, salt, user_id)
    )
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))


def get_user(username):
    return db.one("SELECT * FROM users WHERE username=?", (username.strip(),))


def user_by_id(user_id):
    return db.one("SELECT * FROM users WHERE id=?", (user_id,))


def user_count():
    row = db.one("SELECT COUNT(*) AS c FROM users")
    return row["c"] if row else 0


# --------------------------------------------------------------------------
# TOTP (RFC 6238, SHA1 / 30s / 6 digits)
# --------------------------------------------------------------------------
def new_totp_secret():
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def totp_at(secret, timestamp=None, step=30, digits=6):
    padding = "=" * (-len(secret) % 8)
    key = base64.b32decode(secret.upper() + padding, casefold=True)
    counter = int((timestamp if timestamp is not None else time.time()) // step)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def verify_totp(secret, code, window=1):
    if not secret:
        return True
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit():
        return False
    now = time.time()
    for drift in range(-window, window + 1):
        if hmac.compare_digest(totp_at(secret, now + drift * 30), code):
            return True
    return False


def totp_uri(username, secret, issuer="sni-spoof"):
    from urllib.parse import quote

    return "otpauth://totp/%s:%s?secret=%s&issuer=%s&algorithm=SHA1&digits=6&period=30" % (
        quote(issuer),
        quote(username),
        secret,
        quote(issuer),
    )


# --------------------------------------------------------------------------
# sessions
# --------------------------------------------------------------------------
def _sign(token):
    return hmac.new(settings.secret_key(), token.encode("ascii"), hashlib.sha256).hexdigest()


def create_session(user_id, ip="", ua=""):
    token = secrets.token_urlsafe(32)
    ttl = int(settings.get("panel", "session_ttl_min", 1440)) * 60
    now = int(time.time())
    db.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at, ip, ua) "
        "VALUES (?,?,?,?,?,?)",
        (token, user_id, now, now + ttl, ip, (ua or "")[:200]),
    )
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    return "%s.%s" % (token, _sign(token))


def resolve_session(cookie_value):
    if not cookie_value or "." not in cookie_value:
        return None
    token, _, signature = cookie_value.partition(".")
    if not hmac.compare_digest(_sign(token), signature):
        return None
    row = db.one("SELECT * FROM sessions WHERE token=?", (token,))
    if not row or row["expires_at"] < int(time.time()):
        return None
    user = user_by_id(row["user_id"])
    if not user or not user["enabled"]:
        return None
    return user


def destroy_session(cookie_value):
    if not cookie_value:
        return
    token = cookie_value.partition(".")[0]
    db.execute("DELETE FROM sessions WHERE token=?", (token,))


def destroy_user_sessions(user_id):
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))


# --------------------------------------------------------------------------
# throttling / allowlist
# --------------------------------------------------------------------------
def record_attempt(ip, username, ok):
    db.execute(
        "INSERT INTO login_attempts (ip, username, ts, ok) VALUES (?,?,?,?)",
        (ip, username or "", int(time.time()), 1 if ok else 0),
    )
    db.execute("DELETE FROM login_attempts WHERE ts < ?", (int(time.time()) - 86400,))


def is_throttled(ip):
    cfg = settings.get("panel")
    window = int(cfg.get("login_ban_minutes", 15)) * 60
    limit = int(cfg.get("login_max_attempts", 8))
    row = db.one(
        "SELECT COUNT(*) AS c FROM login_attempts WHERE ip=? AND ok=0 AND ts > ?",
        (ip, int(time.time()) - window),
    )
    return bool(row and row["c"] >= limit)


def clear_attempts(ip):
    db.execute("DELETE FROM login_attempts WHERE ip=?", (ip,))


def ip_allowed(ip):
    allow = settings.get("panel", "ip_allowlist", []) or []
    if not allow:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allow:
        entry = str(entry).strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False
