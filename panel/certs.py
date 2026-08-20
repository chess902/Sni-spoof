"""TLS certificates for the panel: self-signed generation, ACME issuance via
acme.sh, and expiry reporting. Everything shells out to tools that are already
on a normal server, so no Python crypto dependency is needed."""

import os
import shutil
import subprocess
import time

from . import db, paths, settings

ACME_HOME = os.path.join(paths.DATA, "acme")
ACME_SH = os.path.join(ACME_HOME, "acme.sh")


def _run(args, timeout=300, env=None):
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False,
            env={**os.environ, **(env or {})},
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except FileNotFoundError:
        return 127, "%s not found" % args[0]
    except subprocess.SubprocessError as exc:
        return 1, str(exc)


def paths_for(name="panel"):
    return (
        os.path.join(paths.CERT_DIR, "%s.crt" % name),
        os.path.join(paths.CERT_DIR, "%s.key" % name),
    )


def self_signed(common_name=None, days=3650, name="panel"):
    """Generate a self-signed certificate (browsers will warn; traffic is
    still encrypted, which is the point on a bare IP)."""
    if not shutil.which("openssl"):
        raise RuntimeError("openssl is not installed")
    paths.ensure_dirs()
    cert, key = paths_for(name)
    common_name = common_name or "sni-spoof-panel"
    code, output = _run(
        [
            "openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
            "-keyout", key, "-out", cert, "-days", str(int(days)),
            "-subj", "/CN=%s" % common_name,
            "-addext", "subjectAltName=DNS:%s,IP:127.0.0.1" % common_name,
        ]
    )
    if code != 0:
        # -addext is unavailable on very old OpenSSL; retry without it.
        code, output = _run(
            [
                "openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
                "-keyout", key, "-out", cert, "-days", str(int(days)),
                "-subj", "/CN=%s" % common_name,
            ]
        )
    if code != 0:
        raise RuntimeError("openssl failed: %s" % output[:500])
    os.chmod(key, 0o600)
    os.chmod(cert, 0o644)
    db.log_event("self-signed certificate generated for %s" % common_name, category="cert")
    return {"cert": cert, "key": key, "common_name": common_name}


def install_acme():
    if os.path.exists(ACME_SH):
        return True, "acme.sh already installed"
    if not shutil.which("curl"):
        return False, "curl is required to install acme.sh"
    os.makedirs(ACME_HOME, exist_ok=True)
    code, output = _run(
        ["sh", "-c",
         "curl -fsSL https://get.acme.sh | sh -s -- --home '%s' --nocron" % ACME_HOME],
        timeout=180,
    )
    if not os.path.exists(ACME_SH):
        return False, output[:500] or "acme.sh installation failed"
    return True, "acme.sh installed"


def issue_acme(domain, email, standalone_port=80, name="panel"):
    """Issue a Let's Encrypt certificate with the HTTP-01 standalone solver.
    Port 80 must be free and the domain must already point at this server."""
    ok, message = install_acme()
    if not ok:
        raise RuntimeError(message)

    cert, key = paths_for(name)
    paths.ensure_dirs()
    env = {"LE_WORKING_DIR": ACME_HOME}

    code, output = _run(
        [ACME_SH, "--home", ACME_HOME, "--register-account", "-m", email], env=env
    )
    code, output = _run(
        [
            ACME_SH, "--home", ACME_HOME, "--issue", "--standalone",
            "--httpport", str(int(standalone_port)), "-d", domain,
            "--server", "letsencrypt", "--force",
        ],
        timeout=420, env=env,
    )
    if code != 0 and "Cert success" not in output:
        raise RuntimeError("acme.sh issue failed: %s" % output[-800:])

    code, output = _run(
        [
            ACME_SH, "--home", ACME_HOME, "--install-cert", "-d", domain,
            "--key-file", key, "--fullchain-file", cert,
        ],
        env=env,
    )
    if code != 0:
        raise RuntimeError("acme.sh install-cert failed: %s" % output[-800:])
    os.chmod(key, 0o600)
    db.set_meta("acme_domain", domain)
    db.log_event("ACME certificate issued for %s" % domain, category="cert")
    return {"cert": cert, "key": key, "domain": domain}


def renew_acme():
    if not os.path.exists(ACME_SH):
        return False, "acme.sh is not installed"
    code, output = _run(
        [ACME_SH, "--home", ACME_HOME, "--cron"],
        timeout=420, env={"LE_WORKING_DIR": ACME_HOME},
    )
    return code == 0, output[-800:]


def info(cert_path=None):
    """Subject / issuer / validity of the configured certificate."""
    cert_path = cert_path or settings.get("panel", "tls", {}).get("cert") or paths_for()[0]
    if not cert_path or not os.path.exists(cert_path):
        return {"exists": False}
    if not shutil.which("openssl"):
        return {"exists": True, "path": cert_path, "error": "openssl not installed"}
    code, output = _run(
        ["openssl", "x509", "-in", cert_path, "-noout", "-subject", "-issuer", "-enddate"],
        timeout=15,
    )
    if code != 0:
        return {"exists": True, "path": cert_path, "error": output[:300]}
    data = {"exists": True, "path": cert_path}
    for line in output.splitlines():
        key, _, value = line.partition("=")
        key = key.strip().lower()
        if key == "notafter":
            data["not_after"] = value.strip()
            try:
                expires = time.mktime(time.strptime(value.strip(), "%b %d %H:%M:%S %Y %Z"))
                data["days_left"] = int((expires - time.time()) // 86400)
            except ValueError:
                pass
        elif key in ("subject", "issuer"):
            data[key] = value.strip()
    data["self_signed"] = data.get("subject", "") == data.get("issuer", "")
    return data


def enable_tls(cert, key):
    if not os.path.exists(cert) or not os.path.exists(key):
        raise FileNotFoundError("certificate or key not found")
    settings.update("panel", {"tls": {"enabled": True, "cert": cert, "key": key}})
    return True


def disable_tls():
    settings.update("panel", {"tls": {"enabled": False}})
    return True
