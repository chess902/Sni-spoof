#!/usr/bin/env bash
# One-line installer:
#   bash <(curl -fsSL https://raw.githubusercontent.com/chess902/Sni-spoof/main/install.sh)
#
# Optional environment overrides:
#   SNI_SPOOF_REPO=owner/repo   SNI_SPOOF_BRANCH=main   PANEL_PORT=2095
set -euo pipefail

REPO="${SNI_SPOOF_REPO:-chess902/Sni-spoof}"
BRANCH="${SNI_SPOOF_BRANCH:-main}"
PORT="${PANEL_PORT:-2095}"

RED=$'\e[31m'; GRN=$'\e[32m'; BLU=$'\e[36m'; RST=$'\e[0m'
info() { printf '%s→ %s%s\n' "$BLU" "$1" "$RST"; }
die()  { printf '%s✖ %s%s\n' "$RED" "$1" "$RST" >&2; exit 1; }

[[ "$(id -u)" -eq 0 ]] || die "Please run as root (sudo bash ...)"
[[ "$(uname -s)" == "Linux" ]] || die "This installer targets Linux servers"

info "Installing prerequisites…"
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3 curl tar openssl ca-certificates >/dev/null
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y -q python3 curl tar openssl ca-certificates >/dev/null
elif command -v yum >/dev/null 2>&1; then
  yum install -y -q python3 curl tar openssl ca-certificates >/dev/null
elif command -v apk >/dev/null 2>&1; then
  apk add --no-cache python3 curl tar openssl ca-certificates bash >/dev/null
elif command -v pacman >/dev/null 2>&1; then
  pacman -Sy --noconfirm python curl tar openssl ca-certificates >/dev/null
else
  info "Unknown package manager — make sure python3, curl and tar are installed"
fi

command -v python3 >/dev/null 2>&1 || die "python3 is required"
python3 - <<'PY' || die "Python 3.8 or newer is required"
import sys
raise SystemExit(0 if sys.version_info >= (3, 8) else 1)
PY

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

info "Downloading $REPO ($BRANCH)…"
curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" -o "$TMP/src.tar.gz" \
  || die "Download failed — check the network or set SNI_SPOOF_REPO"
tar -xzf "$TMP/src.tar.gz" -C "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -mindepth 1 -type d | head -1)"
[[ -d "$SRC/panel" ]] || die "Unexpected archive layout"

chmod +x "$SRC/scripts/sni-spoof"
SNI_SPOOF_REPO="$REPO" SNI_SPOOF_BRANCH="$BRANCH" "$SRC/scripts/sni-spoof" install "$PORT"

printf '%s✓ Done. Run "sni-spoof" for the management menu.%s\n' "$GRN" "$RST"
