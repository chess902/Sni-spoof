"""Filesystem layout. Every location can be overridden with an env var so the
panel can run unprivileged (tests, containers, per-user installs)."""

import os

ETC = os.environ.get("SNI_SPOOF_ETC", "/etc/sni-spoof")
DATA = os.environ.get("SNI_SPOOF_DATA", "/var/lib/sni-spoof")
LOG = os.environ.get("SNI_SPOOF_LOG", "/var/log/sni-spoof")
BIN = os.environ.get("SNI_SPOOF_BIN", "/usr/local/bin")
RUN = os.environ.get("SNI_SPOOF_RUN", "/run/sni-spoof")

DB_FILE = os.path.join(DATA, "panel.db")
CORE_CONFIG = os.path.join(ETC, "core.json")
XRAY_CONFIG = os.path.join(ETC, "xray.json")
CERT_DIR = os.path.join(DATA, "certs")
BACKUP_DIR = os.path.join(DATA, "backups")
SNI_LIST = os.path.join(ETC, "scan-snis.txt")

CORE_BIN = os.path.join(BIN, "sni-spoof-rs")
XRAY_BIN = os.path.join(BIN, "xray")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

CORE_SERVICE = "sni-spoof-core"
PANEL_SERVICE = "sni-spoof-panel"
XRAY_SERVICE = "sni-spoof-xray"


def ensure_dirs():
    for d in (ETC, DATA, LOG, CERT_DIR, BACKUP_DIR):
        os.makedirs(d, exist_ok=True)
    try:
        os.chmod(CERT_DIR, 0o700)
    except OSError:
        pass
