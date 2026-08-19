"""Fake-SNI scanner.

Probes candidate SNIs against a Cloudflare edge and reports which ones survive
the local DPI. Runs in a background thread pool; one job at a time, with live
progress for the UI. No root needed — these are ordinary outbound sockets."""

import json
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import db, paths, settings
from .tlshello import build_client_hello

BUNDLED_LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "scan-snis.txt")

_lock = threading.Lock()
_job = {
    "running": False,
    "scan_id": None,
    "total": 0,
    "done": 0,
    "ok": 0,
    "target": "",
    "started_at": 0,
    "finished_at": 0,
    "results": [],
    "cancel": False,
    "error": "",
}


def default_snis():
    """Candidate list: the operator's file first, then the bundled one."""
    for path in (paths.SNI_LIST, BUNDLED_LIST):
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                items = [
                    line.strip()
                    for line in handle
                    if line.strip() and not line.strip().startswith("#")
                ]
            if items:
                return items
    return ["security.vercel.com", "www.speedtest.net", "cloudflare.com"]


def save_sni_list(text):
    paths.ensure_dirs()
    with open(paths.SNI_LIST, "w", encoding="utf-8") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")
    return len(default_snis())


def probe(target_host, target_port, sni, timeout=6.0):
    """(ok, outcome, milliseconds) for a single SNI against one edge IP."""
    if len(sni) > 219:
        return False, "sni too long", 0.0
    started = time.time()
    sock = None
    try:
        sock = socket.create_connection((target_host, int(target_port)), timeout=timeout)
        sock.settimeout(timeout)
        sock.sendall(build_client_hello(sni))
        data = b""
        while len(data) < 5:
            chunk = sock.recv(5 - len(data))
            if not chunk:
                return False, "empty response", round((time.time() - started) * 1000, 1)
            data += chunk
        elapsed = round((time.time() - started) * 1000, 1)
        if data[0] == 0x16:
            return True, "ok", elapsed
        if data[0] == 0x15:
            return False, "tls alert", elapsed
        return False, "bad response: 0x%02x" % data[0], elapsed
    except socket.timeout:
        return False, "timeout", round((time.time() - started) * 1000, 1)
    except OSError as exc:
        return False, str(exc), round((time.time() - started) * 1000, 1)
    finally:
        if sock:
            try:
                sock.close()
            except OSError:
                pass


def status():
    with _lock:
        snapshot = dict(_job)
    snapshot["results"] = snapshot["results"][-500:]
    return snapshot


def cancel():
    with _lock:
        if not _job["running"]:
            return False
        _job["cancel"] = True
    return True


def start(target=None, snis=None, timeout=None, concurrency=None):
    """Kick off a scan. Raises RuntimeError when one is already running."""
    cfg = settings.get("scan")
    target = (target or cfg.get("target") or "104.18.4.130:443").strip()
    if ":" in target:
        host, _, port = target.rpartition(":")
    else:
        host, port = target, "443"
    try:
        port = int(port)
    except ValueError:
        raise ValueError("invalid scan target port") from None

    candidates = [s.strip() for s in (snis or default_snis()) if s.strip()]
    if not candidates:
        raise ValueError("no SNI candidates to scan")
    timeout = float(timeout or cfg.get("timeout_sec", 6))
    concurrency = max(1, min(200, int(concurrency or cfg.get("concurrency", 10))))

    with _lock:
        if _job["running"]:
            raise RuntimeError("a scan is already running")
        scan_id = db.insert(
            "INSERT INTO scans (ts, target, status, total) VALUES (?,?,?,?)",
            (int(time.time()), "%s:%d" % (host, port), "running", len(candidates)),
        )
        _job.update(
            {
                "running": True, "scan_id": scan_id, "total": len(candidates),
                "done": 0, "ok": 0, "target": "%s:%d" % (host, port),
                "started_at": int(time.time()), "finished_at": 0,
                "results": [], "cancel": False, "error": "",
            }
        )

    thread = threading.Thread(
        target=_run, args=(scan_id, host, port, candidates, timeout, concurrency),
        name="sni-scan", daemon=True,
    )
    thread.start()
    return scan_id


def _run(scan_id, host, port, candidates, timeout, concurrency):
    results = []
    try:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(probe, host, port, sni, timeout): sni for sni in candidates
            }
            for future in futures:
                if _job["cancel"]:
                    break
                sni = futures[future]
                try:
                    ok, outcome, ms = future.result()
                except Exception as exc:  # a probe must never kill the job
                    ok, outcome, ms = False, str(exc), 0.0
                entry = {"sni": sni, "ok": ok, "outcome": outcome, "ms": ms}
                results.append(entry)
                with _lock:
                    _job["done"] += 1
                    if ok:
                        _job["ok"] += 1
                        _job["results"].append(entry)
    except Exception as exc:
        with _lock:
            _job["error"] = str(exc)

    working = sorted(
        [r for r in results if r["ok"]], key=lambda r: r["ms"]
    )
    cancelled = _job["cancel"]
    db.execute(
        "UPDATE scans SET status=?, ok_count=?, results=? WHERE id=?",
        (
            "cancelled" if cancelled else "done",
            len(working),
            json.dumps(working[:500], ensure_ascii=False),
            scan_id,
        ),
    )
    db.log_event(
        "scan #%d finished: %d/%d SNIs passed" % (scan_id, len(working), len(results)),
        category="scan",
    )
    with _lock:
        _job["running"] = False
        _job["finished_at"] = int(time.time())
        _job["results"] = working


def recent(limit=10):
    rows = db.query(
        "SELECT id, ts, target, status, total, ok_count FROM scans ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]


def get_scan(scan_id):
    row = db.one("SELECT * FROM scans WHERE id=?", (scan_id,))
    if not row:
        return None
    item = dict(row)
    try:
        item["results"] = json.loads(item["results"])
    except (ValueError, TypeError):
        item["results"] = []
    return item
