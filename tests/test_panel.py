"""Unit tests for the panel. Run with: python3 -m unittest discover -s tests"""

import json
import os
import shutil
import sys
import tempfile
import unittest

_TMP = tempfile.mkdtemp(prefix="sni-spoof-test-")
os.environ.setdefault("SNI_SPOOF_ETC", os.path.join(_TMP, "etc"))
os.environ.setdefault("SNI_SPOOF_DATA", os.path.join(_TMP, "data"))
os.environ.setdefault("SNI_SPOOF_LOG", os.path.join(_TMP, "log"))
os.environ.setdefault("SNI_SPOOF_BIN", os.path.join(_TMP, "bin"))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from urllib.parse import quote  # noqa: E402

from panel import auth, core, db, paths, qrcode, settings, share, tlshello  # noqa: E402


def setUpModule():
    paths.ensure_dirs()
    db.init()


def tearDownModule():
    db.close()
    shutil.rmtree(_TMP, ignore_errors=True)


class ShareLinkTests(unittest.TestCase):
    VLESS = ("vless://uuid-1@cf.example.com:443?encryption=none&security=tls"
             "&sni=cf.example.com&fp=chrome&type=ws&host=cf.example.com&path=%2Fws#Node")
    LOCAL = ("vless://uuid@127.0.0.1:40443?mode=auto&path=%2FGoOgLe&security=tls"
             "&encryption=none&host=tom.example.net&fp=chrome&type=xhttp"
             "&sni=tom.example.net#NET_SPOOF")
    TROJAN = "trojan://secret@srv.example.com:443?security=tls&type=ws&path=%2Fx#T"

    def test_parses_vless(self):
        item = share.parse(self.VLESS)
        self.assertEqual(item["protocol"], "vless")
        self.assertEqual(item["user_id"], "uuid-1")
        self.assertEqual(item["network"], "ws")
        self.assertEqual(item["path"], "/ws")
        self.assertTrue(item["tls"])

    def test_local_endpoint_resolves_real_upstream(self):
        item = share.parse(self.LOCAL)
        self.assertTrue(item["local_endpoint"])
        self.assertEqual(item["upstream_host"], "tom.example.net")
        self.assertEqual(item["upstream_port"], 443)

    def test_rewrite_keeps_every_transport_field(self):
        rewritten = share.rewrite(self.VLESS, "1.2.3.4", 40443, "Renamed")
        item = share.parse(rewritten)
        self.assertEqual(item["host"], "1.2.3.4")
        self.assertEqual(item["port"], 40443)
        self.assertEqual(item["name"], "Renamed")
        self.assertEqual(item["sni"], "cf.example.com")
        self.assertEqual(item["path"], "/ws")
        self.assertEqual(item["user_id"], "uuid-1")

    def test_rewrite_vmess_roundtrip(self):
        import base64
        payload = json.dumps({
            "v": "2", "ps": "n", "id": "u", "add": "a.example.com", "port": "443",
            "net": "ws", "host": "h.example.com", "path": "/", "tls": "tls",
        })
        link = "vmess://" + base64.b64encode(payload.encode()).decode()
        item = share.parse(share.rewrite(link, "5.6.7.8", 40443))
        self.assertEqual(item["host"], "5.6.7.8")
        self.assertEqual(item["port"], 40443)
        self.assertEqual(item["http_host"], "h.example.com")

    def test_rejects_unsupported(self):
        with self.assertRaises(share.ShareError):
            share.parse("ss://whatever")
        with self.assertRaises(share.ShareError):
            share.parse("")

    def test_parse_many_accepts_base64_subscription(self):
        import base64
        blob = base64.b64encode(("%s\n%s" % (self.VLESS, self.TROJAN)).encode()).decode()
        parsed, errors = share.parse_many(blob)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(errors, [])


class UpstreamSelectionTests(unittest.TestCase):
    """Panels like 3x-ui emit links whose address is the origin IP; the
    Cloudflare domain only shows up in sni=/host=. Dialing the origin bypasses
    Cloudflare and the technique cannot work."""

    CF = "104.18.4.130"

    def _resolver(self, table):
        def resolve(host, port):
            if host not in table:
                raise ValueError("no DNS for %s" % host)
            return table[host], [table[host]]
        return resolve

    def test_prefers_cloudflare_domain_over_origin_ip(self):
        link = ("vless://u@144.91.68.34:443?security=tls&sni=cdn.example.com"
                "&type=ws&host=cdn.example.com#node")
        host, port, ip, note = share.choose_upstream(
            share.parse(link),
            self._resolver({"144.91.68.34": "144.91.68.34", "cdn.example.com": self.CF}),
        )
        self.assertEqual(host, "cdn.example.com")
        self.assertEqual(ip, self.CF)
        self.assertIn("not a Cloudflare edge", note)

    def test_keeps_address_when_it_is_already_cloudflare(self):
        link = "vless://u@cdn.example.com:443?security=tls&sni=cdn.example.com&type=ws#n"
        host, _, ip, note = share.choose_upstream(
            share.parse(link), self._resolver({"cdn.example.com": self.CF})
        )
        self.assertEqual(host, "cdn.example.com")
        self.assertEqual(ip, self.CF)
        self.assertEqual(note, "")

    def test_keeps_origin_when_no_cloudflare_alternative_exists(self):
        link = ("vless://u@144.91.68.34:443?security=tls&sni=plain.example.com"
                "&type=ws#n")
        host, _, ip, note = share.choose_upstream(
            share.parse(link),
            self._resolver({"144.91.68.34": "144.91.68.34",
                            "plain.example.com": "203.0.113.9"}),
        )
        self.assertEqual(host, "144.91.68.34")
        self.assertEqual(note, "")

    def test_payload_records_why_the_upstream_changed(self):
        link = ("vless://u@144.91.68.34:443?security=tls&sni=cdn.example.com"
                "&type=ws&host=cdn.example.com#node")
        payload = share.to_listener_payload(
            share.parse(link), "0.0.0.0", 40443, "security.vercel.com",
            resolver=self._resolver({"144.91.68.34": "144.91.68.34",
                                     "cdn.example.com": self.CF}),
        )
        self.assertEqual(payload["connect_host"], "cdn.example.com")
        self.assertEqual(payload["connect_ip"], self.CF)
        self.assertIn("Cloudflare", payload["remark"])

    def test_unresolvable_link_raises(self):
        link = "vless://u@nope.invalid:443?security=tls&type=ws#n"
        with self.assertRaises(ValueError):
            share.choose_upstream(share.parse(link), self._resolver({}))


class ListenerValidationTests(unittest.TestCase):
    def setUp(self):
        db.execute("DELETE FROM listeners")

    def _payload(self, **over):
        base = {
            "name": "t", "listen_host": "127.0.0.1", "listen_port": 40443,
            "connect_ip": "104.18.4.130", "connect_port": 443,
            "fake_sni": "security.vercel.com",
        }
        base.update(over)
        return base

    def test_creates_and_renders_config(self):
        core.create_listener(self._payload())
        config = core.build_config()
        self.assertEqual(len(config["listeners"]), 1)
        self.assertEqual(config["listeners"][0]["listen"], "127.0.0.1:40443")
        self.assertEqual(config["listeners"][0]["connect"], "104.18.4.130:443")

    def test_rejects_duplicate_port(self):
        core.create_listener(self._payload())
        with self.assertRaises(core.ValidationError):
            core.create_listener(self._payload(connect_ip="1.1.1.1"))

    def test_rejects_wildcard_port_clash(self):
        core.create_listener(self._payload())
        with self.assertRaises(core.ValidationError):
            core.create_listener(self._payload(listen_host="0.0.0.0", connect_ip="1.1.1.1"))

    def test_rejects_self_loop(self):
        with self.assertRaises(core.ValidationError):
            core.create_listener(self._payload(connect_ip="127.0.0.1", connect_port=40443))

    def test_rejects_hostname_as_connect_ip(self):
        with self.assertRaises(core.ValidationError):
            core.create_listener(self._payload(connect_ip="not-an-ip"))

    def test_rejects_overlong_sni(self):
        with self.assertRaises(core.ValidationError):
            core.create_listener(self._payload(fake_sni="a" * 220 + ".com"))

    def test_disabled_listeners_are_left_out(self):
        item = core.create_listener(self._payload())
        core.toggle_listener(item["id"], False)
        self.assertEqual(core.build_config()["listeners"], [])


class XrayOutboundTests(unittest.TestCase):
    def test_ws_outbound_dials_the_listener_and_keeps_transport(self):
        from panel import xray
        link = ("vless://uuid@cf.example.com:443?encryption=none&security=tls"
                "&sni=cf.example.com&fp=chrome&type=ws&host=edge.example.com"
                "&path=%2Fws#n")
        config = xray.build_config(link, "127.0.0.1", 40443)
        outbound = config["outbounds"][0]
        vnext = outbound["settings"]["vnext"][0]
        self.assertEqual(vnext["address"], "127.0.0.1")
        self.assertEqual(vnext["port"], 40443)
        stream = outbound["streamSettings"]
        self.assertEqual(stream["tlsSettings"]["serverName"], "cf.example.com")
        self.assertEqual(stream["wsSettings"]["path"], "/ws")
        self.assertEqual(stream["wsSettings"]["headers"]["Host"], "edge.example.com")

    def test_xhttp_extra_becomes_download_settings(self):
        from panel import xray
        extra = json.dumps({"downloadSettings": {
            "network": "xhttp",
            "xhttpSettings": {"path": "/dl", "host": "dl.example.com", "mode": "auto"},
        }})
        link = ("vless://uuid@cf.example.com:443?encryption=none&security=tls"
                "&sni=cf.example.com&type=xhttp&mode=auto&host=cf.example.com"
                "&path=%2Fup&extra=" + quote(extra) + "#n")
        stream = xray.build_config(link, "127.0.0.1", 40443)["outbounds"][0]["streamSettings"]
        download = stream["downloadSettings"]
        self.assertEqual(download["address"], "127.0.0.1")
        self.assertEqual(download["port"], 40443)
        self.assertEqual(download["xhttpSettings"]["path"], "/dl")
        self.assertEqual(download["tlsSettings"]["serverName"], "cf.example.com")

    def test_no_extra_means_no_download_settings(self):
        from panel import xray
        link = "vless://uuid@cf.example.com:443?security=tls&sni=cf.example.com&type=ws#n"
        stream = xray.build_config(link, "127.0.0.1", 40443)["outbounds"][0]["streamSettings"]
        self.assertNotIn("downloadSettings", stream)

    def test_routing_needs_no_geodata_files(self):
        from panel import xray
        link = "vless://uuid@cf.example.com:443?security=tls&sni=cf.example.com&type=ws#n"
        rules = xray.build_config(link, "127.0.0.1", 40443)["routing"]["rules"]
        flat = json.dumps(rules)
        self.assertNotIn("geoip:", flat)
        self.assertNotIn("geosite:", flat)


class AuthTests(unittest.TestCase):
    def test_password_roundtrip(self):
        pw_hash, salt = auth.hash_password("correct horse")
        self.assertTrue(auth.verify_password("correct horse", pw_hash, salt))
        self.assertFalse(auth.verify_password("wrong horse", pw_hash, salt))

    def test_totp_accepts_current_code_only(self):
        secret = auth.new_totp_secret()
        self.assertTrue(auth.verify_totp(secret, auth.totp_at(secret)))
        self.assertFalse(auth.verify_totp(secret, "000000"))
        self.assertFalse(auth.verify_totp(secret, "not-a-code"))

    def test_session_requires_valid_signature(self):
        db.execute("DELETE FROM users")
        user_id = auth.create_user("tester", "hunter2hunter2")
        cookie = auth.create_session(user_id, "10.0.0.1")
        self.assertIsNotNone(auth.resolve_session(cookie))
        token = cookie.split(".")[0]
        self.assertIsNone(auth.resolve_session(token + ".deadbeef"))
        auth.destroy_session(cookie)
        self.assertIsNone(auth.resolve_session(cookie))

    def test_ip_allowlist(self):
        settings.update("panel", {"ip_allowlist": ["10.0.0.0/8", "1.2.3.4"]})
        self.assertTrue(auth.ip_allowed("10.9.9.9"))
        self.assertTrue(auth.ip_allowed("1.2.3.4"))
        self.assertFalse(auth.ip_allowed("8.8.8.8"))
        settings.update("panel", {"ip_allowlist": []})
        self.assertTrue(auth.ip_allowed("8.8.8.8"))


class QrTests(unittest.TestCase):
    def test_reed_solomon_matches_reference_vector(self):
        data = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]
        expected = [196, 35, 39, 119, 235, 215, 231, 226, 93, 23]
        self.assertEqual(qrcode._rs_ecc(data, 10), expected)

    def test_matrix_dimensions_grow_with_payload(self):
        self.assertEqual(len(qrcode.encode("hi", "M")), 21)
        big = qrcode.encode("x" * 300, "L")
        self.assertEqual(len(big), len(big[0]))
        self.assertGreater(len(big), 21)

    def test_finder_patterns_are_present(self):
        matrix = qrcode.encode("finder", "M")
        for row, col in ((0, 0), (0, len(matrix) - 7), (len(matrix) - 7, 0)):
            self.assertEqual(matrix[row][col], 1)
            self.assertEqual(matrix[row + 1][col + 1], 0)
            self.assertEqual(matrix[row + 3][col + 3], 1)

    def test_svg_is_self_contained(self):
        svg = qrcode.to_svg("https://example.com", scale=4)
        self.assertTrue(svg.startswith("<svg"))
        self.assertNotIn("http://www.w3.org/1999/xlink", svg)
        self.assertIn("</svg>", svg)

    def test_oversized_payload_is_rejected(self):
        with self.assertRaises(qrcode.QRError):
            qrcode.encode("x" * 5000, "L")


class ClientHelloTests(unittest.TestCase):
    def test_record_header_and_sni_are_present(self):
        hello = tlshello.build_client_hello("example.org")
        self.assertEqual(hello[0], 0x16)              # handshake record
        self.assertEqual(hello[1:3], b"\x03\x01")     # legacy record version
        self.assertEqual(hello[5], 0x01)              # ClientHello
        self.assertIn(b"example.org", hello)
        length = int.from_bytes(hello[3:5], "big")
        self.assertEqual(len(hello), 5 + length)

    def test_length_prefixes_are_consistent(self):
        hello = tlshello.build_client_hello("a-very-long-name.example.test")
        handshake_len = int.from_bytes(hello[6:9], "big")
        self.assertEqual(len(hello) - 9, handshake_len)


class SettingsTests(unittest.TestCase):
    def test_defaults_are_merged_not_replaced(self):
        settings.update("watchdog", {"interval_sec": 42})
        watchdog = settings.get("watchdog")
        self.assertEqual(watchdog["interval_sec"], 42)
        self.assertIn("failures_before_restart", watchdog)

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(KeyError):
            settings.update("nope", {"a": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
