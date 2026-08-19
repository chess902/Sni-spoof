"""SQLite storage. Single connection per thread, WAL for concurrent readers."""

import json
import os
import sqlite3
import threading
import time

from . import paths

SCHEMA_VERSION = 3

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL UNIQUE,
    pw_hash      TEXT NOT NULL,
    pw_salt      TEXT NOT NULL,
    totp_secret  TEXT DEFAULT '',
    role         TEXT NOT NULL DEFAULT 'admin',
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   INTEGER NOT NULL,
    last_login   INTEGER DEFAULT 0,
    last_ip      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    ip         TEXT DEFAULT '',
    ua         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listeners (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    name                   TEXT NOT NULL DEFAULT '',
    enabled                INTEGER NOT NULL DEFAULT 1,
    listen_host            TEXT NOT NULL DEFAULT '127.0.0.1',
    listen_port            INTEGER NOT NULL,
    connect_host           TEXT NOT NULL DEFAULT '',
    connect_ip             TEXT NOT NULL,
    connect_port           INTEGER NOT NULL DEFAULT 443,
    fake_sni               TEXT NOT NULL,
    conn_timeout_sec       INTEGER NOT NULL DEFAULT 5,
    handshake_timeout_sec  INTEGER NOT NULL DEFAULT 2,
    keepalive_time_sec     INTEGER NOT NULL DEFAULT 11,
    keepalive_interval_sec INTEGER NOT NULL DEFAULT 2,
    remark                 TEXT DEFAULT '',
    created_at             INTEGER NOT NULL,
    updated_at             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    listener_id INTEGER,
    name        TEXT DEFAULT '',
    protocol    TEXT NOT NULL,
    raw         TEXT NOT NULL,
    parsed      TEXT NOT NULL DEFAULT '{}',
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS traffic (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    listener_id INTEGER NOT NULL,
    conns       INTEGER NOT NULL DEFAULT 0,
    rx          INTEGER NOT NULL DEFAULT 0,
    tx          INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS traffic_ts ON traffic (ts);
CREATE INDEX IF NOT EXISTS traffic_listener ON traffic (listener_id, ts);

CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       INTEGER NOT NULL,
    level    TEXT NOT NULL DEFAULT 'info',
    category TEXT NOT NULL DEFAULT 'panel',
    message  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);

CREATE TABLE IF NOT EXISTS scans (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        INTEGER NOT NULL,
    target    TEXT NOT NULL,
    status    TEXT NOT NULL DEFAULT 'running',
    total     INTEGER NOT NULL DEFAULT 0,
    ok_count  INTEGER NOT NULL DEFAULT 0,
    results   TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ip       TEXT NOT NULL,
    username TEXT DEFAULT '',
    ts       INTEGER NOT NULL,
    ok       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS login_attempts_ip ON login_attempts (ip, ts);
"""


def connect():
    conn = getattr(_local, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(paths.DB_FILE), exist_ok=True)
        conn = sqlite3.connect(paths.DB_FILE, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        _local.conn = conn
    return conn


def close():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


def init():
    conn = connect()
    conn.executescript(SCHEMA)
    current = int(get_meta("schema_version", "0"))
    if current < SCHEMA_VERSION:
        set_meta("schema_version", str(SCHEMA_VERSION))
    try:
        os.chmod(paths.DB_FILE, 0o600)
    except OSError:
        pass
    return conn


def query(sql, args=()):
    return connect().execute(sql, args).fetchall()


def one(sql, args=()):
    return connect().execute(sql, args).fetchone()


def execute(sql, args=()):
    return connect().execute(sql, args)


def insert(sql, args=()):
    cur = connect().execute(sql, args)
    return cur.lastrowid


def get_meta(key, default=None):
    row = one("SELECT value FROM meta WHERE key=?", (key,))
    return row["value"] if row else default


def set_meta(key, value):
    execute(
        "INSERT INTO meta (key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def get_setting(key, default=None):
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):
        return default


def set_setting(key, value):
    execute(
        "INSERT INTO settings (key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )


def all_settings():
    out = {}
    for row in query("SELECT key, value FROM settings"):
        try:
            out[row["key"]] = json.loads(row["value"])
        except (ValueError, TypeError):
            pass
    return out


def log_event(message, level="info", category="panel"):
    try:
        insert(
            "INSERT INTO events (ts, level, category, message) VALUES (?,?,?,?)",
            (int(time.time()), level, category, str(message)[:2000]),
        )
        execute(
            "DELETE FROM events WHERE id NOT IN "
            "(SELECT id FROM events ORDER BY id DESC LIMIT 5000)"
        )
    except sqlite3.Error:
        pass


def rows_to_dicts(rows):
    return [dict(r) for r in rows]
