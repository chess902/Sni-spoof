"""Backup and restore: config files, the panel database and settings, packed
into a single tar.gz that can be downloaded or shipped to Telegram."""

import io
import json
import os
import shutil
import sqlite3
import tarfile
import time

from . import core, db, paths, settings

MANIFEST = "manifest.json"


def _manifest():
    from . import __version__

    return {
        "created_at": int(time.time()),
        "panel_version": __version__,
        "core_version": db.get_meta("core_version", ""),
        "xray_version": db.get_meta("xray_version", ""),
        "hostname": os.uname().nodename,
    }


def create(label=None):
    """Write a new backup archive and return its path."""
    paths.ensure_dirs()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = "sni-spoof-%s%s.tar.gz" % (stamp, ("-" + label) if label else "")
    target = os.path.join(paths.BACKUP_DIR, name)

    snapshot = os.path.join(paths.BACKUP_DIR, ".panel-snapshot.db")
    _snapshot_db(snapshot)

    with tarfile.open(target, "w:gz") as archive:
        payload = json.dumps(_manifest(), indent=2).encode("utf-8")
        info = tarfile.TarInfo(MANIFEST)
        info.size = len(payload)
        info.mtime = int(time.time())
        archive.addfile(info, io.BytesIO(payload))

        archive.add(snapshot, arcname="panel.db")
        for path, arcname in (
            (paths.CORE_CONFIG, "core.json"),
            (paths.XRAY_CONFIG, "xray.json"),
            (paths.SNI_LIST, "scan-snis.txt"),
        ):
            if os.path.exists(path):
                archive.add(path, arcname=arcname)

    os.unlink(snapshot)
    os.chmod(target, 0o600)
    prune()
    db.log_event("backup created: %s" % name, category="backup")
    return target


def _snapshot_db(target):
    """Consistent copy of a live WAL database."""
    source = db.connect()
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()


def prune():
    keep = int(settings.get("backup", "keep", 10))
    files = sorted(
        (f for f in os.listdir(paths.BACKUP_DIR) if f.endswith(".tar.gz")),
        reverse=True,
    )
    for stale in files[keep:]:
        try:
            os.unlink(os.path.join(paths.BACKUP_DIR, stale))
        except OSError:
            pass


def listing():
    if not os.path.isdir(paths.BACKUP_DIR):
        return []
    items = []
    for name in sorted(os.listdir(paths.BACKUP_DIR), reverse=True):
        if not name.endswith(".tar.gz"):
            continue
        full = os.path.join(paths.BACKUP_DIR, name)
        stat = os.stat(full)
        items.append({"name": name, "size": stat.st_size, "mtime": int(stat.st_mtime)})
    return items


def path_for(name):
    """Resolve a backup name safely inside the backup directory."""
    safe = os.path.basename(name)
    if not safe.endswith(".tar.gz"):
        raise ValueError("not a backup archive")
    full = os.path.join(paths.BACKUP_DIR, safe)
    if not os.path.isfile(full):
        raise FileNotFoundError(safe)
    return full


def delete(name):
    os.unlink(path_for(name))
    return True


def restore(archive_path, restart=True):
    """Replace configuration and database from an archive."""
    if not tarfile.is_tarfile(archive_path):
        raise ValueError("not a valid backup archive")

    staging = os.path.join(paths.BACKUP_DIR, ".restore-%d" % int(time.time()))
    os.makedirs(staging, exist_ok=True)
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                if member.name != os.path.basename(member.name) or not member.isfile():
                    raise ValueError("unexpected entry in archive: %s" % member.name)
            archive.extractall(staging)

        restored = []
        db_file = os.path.join(staging, "panel.db")
        if os.path.exists(db_file):
            db.close()
            for suffix in ("-wal", "-shm"):
                stale = paths.DB_FILE + suffix
                if os.path.exists(stale):
                    os.unlink(stale)
            shutil.copy2(db_file, paths.DB_FILE)
            os.chmod(paths.DB_FILE, 0o600)
            db.init()
            restored.append("panel.db")

        for arcname, target in (
            ("core.json", paths.CORE_CONFIG),
            ("xray.json", paths.XRAY_CONFIG),
            ("scan-snis.txt", paths.SNI_LIST),
        ):
            source = os.path.join(staging, arcname)
            if os.path.exists(source):
                shutil.copy2(source, target)
                restored.append(arcname)

        if restart:
            core.apply(restart=True)
        db.log_event("backup restored from %s" % os.path.basename(archive_path), category="backup")
        return {"restored": restored}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def export_settings():
    """Human-readable export (settings + listeners + links), for support."""
    return {
        "manifest": _manifest(),
        "settings": settings.get_all(),
        "listeners": core.list_listeners(),
        "links": [dict(r) for r in db.query("SELECT * FROM links ORDER BY id")],
    }
