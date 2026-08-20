#!/bin/sh
set -e

PANEL_PORT="${PANEL_PORT:-2095}"
PANEL_USER="${PANEL_USER:-admin}"

echo "→ preparing sni-spoof panel"
SETUP_ARGS="--username $PANEL_USER --port $PANEL_PORT --host 0.0.0.0"
[ -n "$PANEL_PASSWORD" ] && SETUP_ARGS="$SETUP_ARGS --password $PANEL_PASSWORD"
[ -n "$PANEL_LANGUAGE" ] && SETUP_ARGS="$SETUP_ARGS --language $PANEL_LANGUAGE"

# Only seed credentials the first time; a mounted volume keeps them afterwards.
if [ ! -f /var/lib/sni-spoof/panel.db ]; then
    # shellcheck disable=SC2086
    python3 -m panel setup $SETUP_ARGS
else
    echo "→ existing database found, keeping current credentials"
    python3 -m panel settings set panel port "$PANEL_PORT" >/dev/null
fi

if [ ! -x /usr/local/bin/sni-spoof-rs ]; then
    echo "→ downloading the sni-spoof-rs core"
    python3 -m panel core install || echo "!! core download failed; install it later from the panel"
fi

if [ -n "$SHARE_LINK" ]; then
    echo "→ importing SHARE_LINK"
    printf '%s' "$SHARE_LINK" | python3 -m panel link import - \
        --listen-host 0.0.0.0 \
        --listen-port "${LISTEN_PORT:-40443}" \
        --fake-sni "${FAKE_SNI:-security.vercel.com}" || true
fi

if [ "${XRAY_ENABLED:-0}" = "1" ]; then
    echo "→ installing Xray"
    python3 -m panel xray install || true
    python3 -m panel settings set xray enabled true >/dev/null
    python3 -m panel settings set xray listen '"0.0.0.0"' >/dev/null
    python3 -m panel xray apply || true
fi

python3 -m panel service core start || true
echo "→ panel starting on port ${PANEL_PORT}"
exec python3 -m panel serve
