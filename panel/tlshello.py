"""A hand-built TLS ClientHello.

The scanner needs to send one ClientHello carrying an arbitrary SNI and look at
the server's first response byte. Python's `ssl` module would work but performs
a full handshake and rejects odd hostnames, so the record is assembled by hand
exactly like the Rust core does."""

import os
import struct

CIPHER_SUITES = [
    0x1301, 0x1302, 0x1303,          # TLS 1.3
    0xC02B, 0xC02F, 0xC02C, 0xC030,  # ECDHE-ECDSA/RSA AES-GCM
    0xCCA9, 0xCCA8,                  # CHACHA20-POLY1305
    0xC013, 0xC014, 0x009C, 0x009D,
    0x002F, 0x0035,
]
SUPPORTED_GROUPS = [0x001D, 0x0017, 0x0018, 0x0019]  # x25519, secp256r1/384/521
SIG_ALGS = [
    0x0403, 0x0804, 0x0401, 0x0503, 0x0805, 0x0501,
    0x0806, 0x0601, 0x0201,
]


def _ext(ext_type, body):
    return struct.pack(">HH", ext_type, len(body)) + body


def _sni_ext(hostname):
    host = hostname.encode("idna") if hostname.isascii() else hostname.encode("utf-8")
    entry = b"\x00" + struct.pack(">H", len(host)) + host
    return _ext(0x0000, struct.pack(">H", len(entry)) + entry)


def build_client_hello(sni, tls13=True):
    """Return the full TLS record bytes for a ClientHello advertising `sni`."""
    body = b"\x03\x03"                       # legacy_version = TLS 1.2
    body += os.urandom(32)                   # random
    session_id = os.urandom(32)
    body += bytes([len(session_id)]) + session_id

    suites = b"".join(struct.pack(">H", c) for c in CIPHER_SUITES)
    body += struct.pack(">H", len(suites)) + suites
    body += b"\x01\x00"                      # compression: null only

    extensions = b""
    extensions += _sni_ext(sni)
    extensions += _ext(0x0017, b"")          # extended_master_secret
    extensions += _ext(0x0023, b"")          # session_ticket
    groups = b"".join(struct.pack(">H", g) for g in SUPPORTED_GROUPS)
    extensions += _ext(0x000A, struct.pack(">H", len(groups)) + groups)
    extensions += _ext(0x000B, b"\x01\x00")  # ec_point_formats: uncompressed
    sigs = b"".join(struct.pack(">H", s) for s in SIG_ALGS)
    extensions += _ext(0x000D, struct.pack(">H", len(sigs)) + sigs)
    alpn_protos = b"\x02h2\x08http/1.1"
    extensions += _ext(0x0010, struct.pack(">H", len(alpn_protos)) + alpn_protos)
    if tls13:
        extensions += _ext(0x002B, b"\x04\x03\x04\x03\x03")   # supported_versions
        key_share = b"\x00\x1d" + struct.pack(">H", 32) + os.urandom(32)
        extensions += _ext(0x0033, struct.pack(">H", len(key_share)) + key_share)
        extensions += _ext(0x002D, b"\x01\x01")               # psk_key_exchange_modes

    body += struct.pack(">H", len(extensions)) + extensions

    handshake = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + struct.pack(">H", len(handshake)) + handshake
