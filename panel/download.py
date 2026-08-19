"""GitHub release downloads with mirror support (useful where github.com is
throttled) and atomic install of binaries."""

import json
import os
import platform
import shutil
import stat
import subprocess
import tempfile
import urllib.error
import urllib.request

from . import settings

UA = {"User-Agent": "sni-spoof-panel", "Accept": "application/vnd.github+json"}


def arch():
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    if machine.startswith("armv7") or machine == "armv6l":
        return "arm"
    return machine


def is_musl():
    if os.path.exists("/etc/alpine-release"):
        return True
    try:
        out = subprocess.run(
            ["ldd", "--version"], capture_output=True, text=True, timeout=5, check=False
        )
        return "musl" in (out.stdout + out.stderr).lower()
    except (OSError, subprocess.SubprocessError):
        return False


def mirrored(url):
    mirror = (settings.get("network", "github_mirror", "") or "").strip()
    if not mirror:
        return url
    return mirror.rstrip("/") + "/" + url


def fetch(url, timeout=None, binary=True):
    timeout = timeout or int(settings.get("network", "connect_timeout_sec", 20))
    request = urllib.request.Request(mirrored(url), headers=UA)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read()
    return data if binary else data.decode("utf-8", "replace")


def latest_release(repo):
    """Release metadata for `repo`, or a minimal stub when the API is blocked."""
    api = "https://api.github.com/repos/%s/releases/latest" % repo
    try:
        data = json.loads(fetch(api, binary=False))
        return {
            "tag": data.get("tag_name", ""),
            "name": data.get("name", ""),
            "published_at": data.get("published_at", ""),
            "assets": {a["name"]: a["browser_download_url"] for a in data.get("assets", [])},
            "html_url": data.get("html_url", ""),
        }
    except (urllib.error.URLError, ValueError, KeyError, OSError) as exc:
        return {"tag": "", "assets": {}, "error": str(exc)}


def asset_url(repo, asset, release=None):
    """Prefer the API-provided URL, fall back to the stable `latest/download`
    path, then to the repo's committed `releases/` folder."""
    if release and release.get("assets", {}).get(asset):
        return release["assets"][asset]
    return "https://github.com/%s/releases/latest/download/%s" % (repo, asset)


def raw_fallback_url(repo, asset, branch="main"):
    return "https://raw.githubusercontent.com/%s/%s/releases/%s" % (repo, branch, asset)


def install_binary(url, dest, fallback_urls=(), mode=0o755):
    """Download to a temp file and move it into place; never leave a half
    written binary at `dest`."""
    errors = []
    for candidate in (url,) + tuple(fallback_urls):
        try:
            payload = fetch(candidate)
        except Exception as exc:
            errors.append("%s -> %s" % (candidate, exc))
            continue
        if len(payload) < 1024:
            errors.append("%s -> suspiciously small (%d bytes)" % (candidate, len(payload)))
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dest), prefix=".dl-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.chmod(tmp, mode)
            os.replace(tmp, dest)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return True, candidate
    raise RuntimeError("download failed: " + " | ".join(errors))


def extract_from_zip(url, member, dest, fallback_urls=(), mode=0o755):
    """Download a zip (Xray ships this way) and install one member."""
    import io
    import zipfile

    errors = []
    for candidate in (url,) + tuple(fallback_urls):
        try:
            payload = fetch(candidate)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = archive.namelist()
                if member not in names:
                    matches = [n for n in names if n.rsplit("/", 1)[-1] == member]
                    if not matches:
                        raise KeyError("%s not in archive" % member)
                    member_name = matches[0]
                else:
                    member_name = member
                data = archive.read(member_name)
        except Exception as exc:
            errors.append("%s -> %s" % (candidate, exc))
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dest), prefix=".dl-")
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, dest)
        return True, candidate
    raise RuntimeError("download failed: " + " | ".join(errors))


def grant_net_raw(path):
    """Best-effort CAP_NET_RAW so the core can sniff without full root."""
    setcap = shutil.which("setcap")
    if not setcap or not os.path.exists(path):
        return False
    try:
        proc = subprocess.run(
            [setcap, "cap_net_raw,cap_net_admin+eip", path],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK) and (
        os.stat(path).st_mode & stat.S_IXUSR
    )
