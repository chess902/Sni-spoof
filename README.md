<div align="center">

# SNI Spoof Panel

**A management script and web panel for [sni-spoof-rs](https://github.com/therealaleph/sni-spoofing-rust) — DPI bypass via fake TLS ClientHello injection.**

اسکریپت مدیریت و پنل وب برای عبور از DPI با تزریق ClientHello جعلی

[English](#english) · [فارسی](#فارسی)

</div>

---

## English

### What this is

The [sni-spoof-rs](https://github.com/therealaleph/sni-spoofing-rust) core implements
[@patterniha's SNI-Spoofing](https://github.com/patterniha/SNI-Spoofing) technique: right after the TCP
handshake it injects a TLS ClientHello carrying a **decoy SNI** with a deliberately wrong sequence
number. Passive DPI reads the decoy and may whitelist the flow; the real server drops that packet
because it falls outside the receive window; your real TLS session then proceeds untouched.

This repository adds everything around that core so it can be run as a **server**:

* a one-line installer and a bilingual (فارسی/English) interactive management script,
* a dependency-free web panel — no pip, no Node, no CDN, just Python 3.8+ from your distro,
* systemd units, or a built-in process supervisor when systemd is unavailable.

```
client (phone / laptop)                     your VPS                          internet
        │                                       │
        │  vless://…@VPS_IP:40443  ────────────▶│ sni-spoof-rs listener
        │                                       │   ├─ injects fake ClientHello (decoy SNI)
        │                                       │   └─ relays the real TLS stream ─────▶ Cloudflare edge
        └───────────────────── panel :2095 ─────┤                                        → your real server
                                                └─ optional Xray → HTTP :1080 / SOCKS :1081
```

### Features

**Listeners**
* Full CRUD with validation that mirrors the Rust core (self-loop, port clash, SNI length).
* Automatic Cloudflare IP resolution from a domain, with a badge when the IP is a real CF edge.
* Scheduled re-resolution — Cloudflare rotates edge IPs, the panel can follow them.
* Live health checks: TCP reachability **and** a real TLS handshake through the listener.

**Configs and clients**
* Import `vless://`, `vmess://`, `trojan://` links or a whole base64 subscription blob.
* Every transport field (uuid, sni, host, path, fingerprint, alpn, reality keys…) is preserved.
* One click produces the rewritten client link plus a QR code rendered server-side.
* A subscription endpoint with a rotatable token, so clients update themselves.

**Fake-SNI scanner**
* Probes ~650 bundled candidate domains (editable in the panel) against a Cloudflare edge.
* Hand-built ClientHello, so no root is needed and results match the core's own scanner.
* Apply a working SNI to any subset of listeners in one action.

**Xray integration**
* Install/update the Xray binary, generate a config whose outbound is routed through a listener.
* HTTP and SOCKS5 inbounds with optional username/password, LAN sharing, `xray -test` validation.
* Egress IP check — direct, through HTTP, or through SOCKS — to prove the tunnel really works.

**Operations**
* Dashboard: CPU, RAM, disk, load, per-interface throughput, per-listener connection counts and charts.
* Watchdog that restarts the core when a listener stops answering.
* Backups (download, upload, restore, scheduled) and Telegram notifications/delivery.
* TLS for the panel: self-signed or Let's Encrypt via acme.sh; secret base path; IP allowlist.
* Two-factor authentication (TOTP), multiple panel users, brute-force throttling, audit log.
* Everything the web UI does is also available from the shell menu and a scriptable CLI.

### Requirements

| | |
|---|---|
| OS | Any Linux with systemd — Ubuntu, Debian, AlmaLinux, Rocky, CentOS, Fedora, Arch, Alpine |
| Python | 3.8 or newer (already present on virtually every distro) |
| Privileges | root — the core needs `CAP_NET_RAW` to sniff and inject packets |
| Architecture | x86_64 or aarch64 (prebuilt core binaries) |

No pip packages are installed. The panel uses only the Python standard library.

### Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/chess902/Sni-spoof/HEAD/install.sh)
```

The installer asks for a panel port, username and password, downloads the core binary and prints
your panel URL. Afterwards, open the management menu at any time with:

```bash
sni-spoof
```

> **Before anything else:** read [docs/SETUP.md](docs/SETUP.md). It explains
> where each piece must run and how to wire 3x-ui to it — the two things that
> account for almost every "it does not work".

### Quick start

1. `sni-spoof` → **Configs** → **Import config**, paste your `vless://` / `vmess://` / `trojan://` link.
   A listener is created automatically on `0.0.0.0:40443`, pointed at the resolved Cloudflare IP.
2. **Configs** → **Show client link + QR** and scan it with v2rayNG / Hiddify / Streisand.
   The link is identical to the original except the address is now `YOUR_VPS_IP:40443`.
3. If it does not connect, run **SNI scanner** and apply a working fake SNI.

Prefer the web panel? Open `http://YOUR_VPS_IP:2095/` and do the same in the UI.

### Command line

The manager script is fully scriptable — useful for automation and remote runs:

```bash
sni-spoof status                  # summary of services, listeners and versions
sni-spoof restart core            # start | stop | restart  [core|panel|xray|all]
sni-spoof log core                # follow journald (or the supervisor log)
sni-spoof scan                    # run the fake-SNI scanner
sni-spoof bbr                     # enable BBR + network tuning
sni-spoof backup                  # create a backup archive
sni-spoof update                  # update the panel and the core
```

Anything the panel can do is reachable through `sni-spoof cli …`:

```bash
sni-spoof cli listener add --name node1 --connect-host cf.example.com \
                           --listen-port 40443 --fake-sni security.vercel.com
sni-spoof cli listener test
sni-spoof cli link import 'vless://…' --listen-port 40443
sni-spoof cli link show --id 1 --host 203.0.113.10      # prints the link and an ASCII QR
sni-spoof cli scan --concurrency 40 --apply
sni-spoof cli subscription                              # subscription URL
sni-spoof cli cert acme --domain panel.example.com --email you@example.com
sni-spoof cli settings set core auto_refresh_ip_hours 6
sni-spoof cli --help
```

### Docker

```bash
git clone https://github.com/chess902/Sni-spoof && cd Sni-spoof
docker compose -f docker/docker-compose.yml up -d --build
```

The container needs `NET_RAW`/`NET_ADMIN` and host networking. Set `SHARE_LINK`, `FAKE_SNI` and
`XRAY_ENABLED=1` in `docker/docker-compose.yml` to have it configure itself on first boot. Without
systemd the panel supervises the core and Xray as child processes.

### Layout

| Path | Contents |
|---|---|
| `/opt/sni-spoof/panel` | the panel package |
| `/etc/sni-spoof/core.json` | generated core config (never edit by hand — the panel rewrites it) |
| `/etc/sni-spoof/xray.json` | generated Xray config |
| `/etc/sni-spoof/scan-snis.txt` | your fake-SNI candidate list |
| `/var/lib/sni-spoof/panel.db` | SQLite database (users, listeners, links, settings, metrics) |
| `/var/lib/sni-spoof/backups` | backup archives |
| `/usr/local/bin/sni-spoof-rs` | the core binary |
| `/usr/local/bin/sni-spoof` | this management script |

### Listener reference

| Field | Meaning |
|---|---|
| `listen` | Local address:port clients connect to. `0.0.0.0` to serve other devices. |
| `connect` | Upstream **IP**:port (a Cloudflare edge). The panel resolves it from a domain for you. |
| `fake_sni` | Decoy hostname placed in the injected ClientHello. Max 219 characters. |
| `conn_timeout_sec` | Upstream TCP connect timeout. |
| `handshake_timeout_sec` | How long to wait for the fake packet's ACK. |
| `keepalive_time_sec` / `keepalive_interval_sec` | TCP keepalive tuning. |
| `buffer_size` | Relay buffer in KiB (global). |
| `graceful_shutdown_sec` | Drain time on shutdown; `0` exits immediately (global). |

### Security notes

* Put the panel behind TLS (**Panel settings → certificate**) before exposing it to the internet.
* Set a secret base path and an IP allowlist if the panel must stay public.
* Turn on TOTP for every panel user.
* The panel service runs as root because it writes `/etc/sni-spoof` and drives `systemctl`.
  The core runs with only `CAP_NET_RAW`/`CAP_NET_ADMIN` under a hardened unit.
* Backups contain your configs and password hashes — treat the archives as secrets.

### Troubleshooting

| Symptom | What to check |
|---|---|
| Listener shows `down` | `sni-spoof log core`. Missing `CAP_NET_RAW` or a bad `connect` IP are the usual causes. |
| TLS test fails, TCP passes | The fake SNI is probably burned. Run the scanner and apply a fresh one. |
| Works, then dies after hours | Cloudflare rotated its edge IP. Set **auto refresh IP** to 6 hours. |
| Core download fails | GitHub may be blocked. Set a mirror in **Settings → Network** (e.g. `https://ghproxy.net/`). |
| Panel unreachable after a port change | The panel restarts itself; check the firewall for the new port. |
| Lost the password | `sni-spoof cli user passwd admin` prints a fresh random one. |

### Development

```bash
python3 -m unittest discover -s tests -v     # 26 unit tests, no dependencies
SNI_SPOOF_ETC=/tmp/x/etc SNI_SPOOF_DATA=/tmp/x/data python3 -m panel setup --port 8080
SNI_SPOOF_ETC=/tmp/x/etc SNI_SPOOF_DATA=/tmp/x/data python3 -m panel serve
```

Every path is overridable through `SNI_SPOOF_ETC`, `SNI_SPOOF_DATA`, `SNI_SPOOF_LOG`,
`SNI_SPOOF_BIN` and `SNI_SPOOF_RUN`, so the panel runs unprivileged during development.

---

## فارسی

### این پروژه چیست

هستهٔ [sni-spoof-rs](https://github.com/therealaleph/sni-spoofing-rust) روش
[SNI-Spoofing](https://github.com/patterniha/SNI-Spoofing) از [@patterniha](https://github.com/patterniha)
را پیاده کرده است: بلافاصله پس از هندشیک TCP، یک ClientHello با **SNI جعلی** و شمارهٔ ترتیب عمداً
اشتباه تزریق می‌شود. DPI غیرفعال همان SNI جعلی را می‌بیند و ممکن است مسیر را مجاز بشمارد؛ سرور واقعی
آن بسته را دور می‌اندازد چون خارج از پنجرهٔ دریافت است؛ و ترافیک TLS واقعی شما بدون دست‌کاری رد می‌شود.

این مخزن همهٔ چیزهایی را که برای اجرای آن روی **سرور** لازم است اضافه می‌کند:

* نصب تک‌خطی و یک اسکریپت مدیریت تعاملی دوزبانه (فارسی/English)
* پنل وب کاملاً بدون وابستگی — بدون pip، بدون Node، بدون CDN؛ فقط پایتون ۳.۸ به بالا
* سرویس‌های systemd، و در نبود systemd یک سوپروایزر داخلی برای مدیریت پروسه‌ها

### قابلیت‌ها

**لیسنرها**
* افزودن/ویرایش/حذف کامل با اعتبارسنجی مطابق هستهٔ Rust (حلقهٔ خودارجاع، تداخل پورت، طول SNI)
* پیدا کردن خودکار IP کلادفلر از روی دامنه، همراه با نشان‌دادن اینکه IP واقعاً edge کلادفلر است
* بروزرسانی زمان‌بندی‌شدهٔ IP — کلادفلر IPها را می‌چرخاند و پنل دنبالش می‌رود
* تست سلامت زنده: هم اتصال TCP و هم یک هندشیک واقعی TLS از داخل لیسنر

**کانفیگ‌ها و کلاینت‌ها**
* ایمپورت لینک‌های `vless://`، `vmess://`، `trojan://` یا یک ساب‌اسکریپشن base64 کامل
* همهٔ فیلدهای ترنسپورت (uuid، sni، host، path، fingerprint، alpn، کلیدهای reality و…) دست‌نخورده می‌مانند
* با یک کلیک، لینک بازنویسی‌شدهٔ کلاینت به‌همراه QR ساخته‌شده در سمت سرور
* آدرس ساب‌اسکریپشن با توکن قابل‌تعویض، تا کلاینت‌ها خودشان بروز شوند

**اسکنر SNI جعلی**
* آزمودن حدود ۶۵۰ دامنهٔ کاندید همراه پروژه (قابل ویرایش در پنل) روی یک edge کلادفلر
* ClientHello دست‌ساز، پس نیازی به root نیست و نتیجه با اسکنر خود هسته یکی است
* اعمال SNI سالم روی هر تعداد لیسنر که بخواهید، با یک عملیات

**یکپارچگی با Xray**
* نصب/بروزرسانی باینری Xray و ساخت کانفیگی که خروجی‌اش از داخل لیسنر عبور می‌کند
* اینباند HTTP و SOCKS5 با نام کاربری/رمز اختیاری، اشتراک‌گذاری در شبکهٔ محلی، و اعتبارسنجی `xray -test`
* بررسی IP خروجی — مستقیم، از HTTP، یا از SOCKS — برای اثبات اینکه تونل واقعاً کار می‌کند

**بهره‌برداری**
* داشبورد: پردازنده، حافظه، دیسک، بار سیستم، پهنای باند هر اینترفیس، تعداد اتصال هر لیسنر و نمودار
* نگهبان (watchdog) که اگر لیسنری جواب ندهد هسته را ری‌استارت می‌کند
* بکاپ (دانلود، آپلود، بازیابی، زمان‌بندی‌شده) و اعلان/ارسال از طریق تلگرام
* TLS برای پنل: self-signed یا Let's Encrypt با acme.sh؛ مسیر مخفی؛ محدودسازی به IP
* ورود دو مرحله‌ای (TOTP)، چند کاربر، محدودسازی تلاش ناموفق، و لاگ رویدادها
* هر کاری که رابط وب می‌کند، از منوی شل و CLI هم در دسترس است

### پیش‌نیازها

| | |
|---|---|
| سیستم‌عامل | هر لینوکسی با systemd — اوبونتو، دبیان، آلما، راکی، سنت‌اواس، فدورا، آرچ، آلپاین |
| پایتون | ۳.۸ یا بالاتر (روی تقریباً همهٔ توزیع‌ها از قبل هست) |
| دسترسی | root — هسته برای شنود و تزریق بسته به `CAP_NET_RAW` نیاز دارد |
| معماری | x86_64 یا aarch64 (باینری آماده) |

هیچ پکیج pip نصب نمی‌شود؛ پنل فقط از کتابخانهٔ استاندارد پایتون استفاده می‌کند.

### نصب

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/chess902/Sni-spoof/HEAD/install.sh)
```

نصب‌کننده پورت پنل، نام کاربری و رمز را می‌پرسد، باینری هسته را دانلود می‌کند و آدرس پنل را
چاپ می‌کند. بعد از آن هر وقت خواستید منوی مدیریت را باز کنید:

```bash
sni-spoof
```

> **قبل از هر کاری:** [docs/SETUP.md](docs/SETUP.md) را بخوانید. توضیح می‌دهد هر
> قطعه کجا باید اجرا شود و 3x-ui را چطور به آن وصل کنید — همان دو چیزی که تقریباً
> علت همهٔ «کار نمی‌کند»هاست.

### شروع سریع

1. `sni-spoof` → **کانفیگ‌ها** → **افزودن کانفیگ** و لینک `vless://` یا `vmess://` یا `trojan://` را بچسبانید.
   یک لیسنر روی `0.0.0.0:40443` ساخته می‌شود که به IP کلادفلرِ resolve شده وصل است.
2. **کانفیگ‌ها** → **نمایش لینک کلاینت + QR** و با v2rayNG / Hiddify / Streisand اسکنش کنید.
   لینک دقیقاً همان لینک اصلی است، فقط آدرسش `IP_سرور_شما:40443` شده.
3. اگر وصل نشد، **اسکنر SNI** را اجرا کنید و یک SNI سالم اعمال کنید.

اگر پنل وب را ترجیح می‌دهید، `http://IP_سرور:2095/` را باز کنید و همین کارها را در رابط انجام دهید.

### خط فرمان

```bash
sni-spoof status                  # خلاصهٔ سرویس‌ها، لیسنرها و نسخه‌ها
sni-spoof restart core            # start | stop | restart  [core|panel|xray|all]
sni-spoof log core                # دنبال کردن لاگ
sni-spoof scan                    # اجرای اسکنر SNI
sni-spoof bbr                     # فعال‌سازی BBR و بهینه‌سازی شبکه
sni-spoof backup                  # ساخت بکاپ
sni-spoof update                  # بروزرسانی پنل و هسته
```

هر کاری که پنل می‌کند از طریق `sni-spoof cli …` هم در دسترس است:

```bash
sni-spoof cli listener add --name node1 --connect-host cf.example.com \
                           --listen-port 40443 --fake-sni security.vercel.com
sni-spoof cli listener test
sni-spoof cli link import 'vless://…' --listen-port 40443
sni-spoof cli link show --id 1 --host 203.0.113.10      # لینک و QR متنی
sni-spoof cli scan --concurrency 40 --apply
sni-spoof cli subscription
sni-spoof cli cert acme --domain panel.example.com --email you@example.com
sni-spoof cli settings set core auto_refresh_ip_hours 6
```

### داکر

```bash
git clone https://github.com/chess902/Sni-spoof && cd Sni-spoof
docker compose -f docker/docker-compose.yml up -d --build
```

کانتینر به `NET_RAW`/`NET_ADMIN` و شبکهٔ host نیاز دارد. با تنظیم `SHARE_LINK`، `FAKE_SNI` و
`XRAY_ENABLED=1` در `docker/docker-compose.yml` خودش را در اولین اجرا کانفیگ می‌کند.

### مسیر فایل‌ها

| مسیر | محتوا |
|---|---|
| `/opt/sni-spoof/panel` | پکیج پنل |
| `/etc/sni-spoof/core.json` | کانفیگ تولیدشدهٔ هسته (دستی ویرایش نکنید؛ پنل بازنویسی‌اش می‌کند) |
| `/etc/sni-spoof/xray.json` | کانفیگ تولیدشدهٔ Xray |
| `/etc/sni-spoof/scan-snis.txt` | لیست کاندیدهای SNI جعلی |
| `/var/lib/sni-spoof/panel.db` | دیتابیس SQLite |
| `/var/lib/sni-spoof/backups` | بکاپ‌ها |
| `/usr/local/bin/sni-spoof-rs` | باینری هسته |
| `/usr/local/bin/sni-spoof` | همین اسکریپت مدیریت |

### مرجع فیلدهای لیسنر

| فیلد | معنی |
|---|---|
| `listen` | آدرس و پورت محلی که کلاینت‌ها به آن وصل می‌شوند. برای دستگاه‌های دیگر `0.0.0.0` بگذارید. |
| `connect` | **IP** و پورت مقصد (یک edge کلادفلر). پنل آن را از روی دامنه پیدا می‌کند. |
| `fake_sni` | دامنهٔ جعلی داخل ClientHello تزریقی. حداکثر ۲۱۹ کاراکتر. |
| `conn_timeout_sec` | مهلت اتصال TCP به مقصد. |
| `handshake_timeout_sec` | مهلت انتظار برای ACK بستهٔ جعلی. |
| `keepalive_time_sec` / `keepalive_interval_sec` | تنظیم keepalive در TCP. |
| `buffer_size` | بافر رله بر حسب کیلوبایت (سراسری). |
| `graceful_shutdown_sec` | مهلت تخلیه هنگام خاموشی؛ `0` یعنی خروج فوری (سراسری). |

### نکات امنیتی

* قبل از باز کردن پنل روی اینترنت، TLS را فعال کنید (**تنظیمات پنل ← گواهی**).
* اگر پنل باید عمومی بماند، مسیر مخفی و محدودسازی IP را تنظیم کنید.
* برای همهٔ کاربران پنل ورود دو مرحله‌ای را روشن کنید.
* سرویس پنل با دسترسی root اجرا می‌شود چون در `/etc/sni-spoof` می‌نویسد و `systemctl` را صدا می‌زند.
  هسته فقط با `CAP_NET_RAW`/`CAP_NET_ADMIN` و در یک یونیت سخت‌گیرانه اجرا می‌شود.
* بکاپ‌ها شامل کانفیگ‌ها و هش رمزها هستند؛ با آن‌ها مثل اطلاعات محرمانه رفتار کنید.

### رفع اشکال

| نشانه | چه چیزی را بررسی کنیم |
|---|---|
| لیسنر `down` است | `sni-spoof log core`. معمولاً نبود `CAP_NET_RAW` یا IP اشتباه در `connect`. |
| تست TCP سالم ولی TLS خطا | احتمالاً SNI جعلی سوخته؛ اسکنر را اجرا و یکی تازه اعمال کنید. |
| بعد از چند ساعت قطع می‌شود | کلادفلر IP را عوض کرده؛ **بروزرسانی خودکار IP** را روی ۶ ساعت بگذارید. |
| دانلود هسته ناموفق است | گیت‌هاب مسدود است؛ در **تنظیمات ← شبکه** یک میرور بگذارید (مثلاً `https://ghproxy.net/`). |
| بعد از تغییر پورت پنل باز نمی‌شود | پنل خودش ری‌استارت می‌شود؛ فایروال را برای پورت جدید بررسی کنید. |
| رمز را گم کرده‌اید | `sni-spoof cli user passwd admin` یک رمز تصادفی تازه چاپ می‌کند. |

---

## Credits

* DPI-bypass core: [therealaleph/sni-spoofing-rust](https://github.com/therealaleph/sni-spoofing-rust) (MIT)
* Original technique: [patterniha/SNI-Spoofing](https://github.com/patterniha/SNI-Spoofing)
* Xray-core: [XTLS/Xray-core](https://github.com/XTLS/Xray-core)

Licensed under the MIT License — see [LICENSE](LICENSE).
