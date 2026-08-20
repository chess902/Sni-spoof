# Panel + core + Xray in one container. The panel supervises the core and Xray
# as child processes, so no init system is needed inside the image.
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 ca-certificates curl openssl iproute2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/sni-spoof
COPY panel/ ./panel/
COPY data/ ./data/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /etc/sni-spoof /var/lib/sni-spoof /var/log/sni-spoof /run/sni-spoof

ENV PYTHONPATH=/opt/sni-spoof \
    PYTHONUNBUFFERED=1 \
    PANEL_PORT=2095 \
    PANEL_USER=admin

# panel, SNI listener, Xray HTTP + SOCKS
EXPOSE 2095 40443 1080 1081
VOLUME ["/etc/sni-spoof", "/var/lib/sni-spoof"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python3 -c "import urllib.request,os,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/api/session' % os.environ.get('PANEL_PORT','2095'), timeout=4).status==200 else 1)"

ENTRYPOINT ["/entrypoint.sh"]
