# Setup guide · راهنمای راه‌اندازی

[English](#english) · [فارسی](#فارسی)

---

## English

### 1. Understand where each piece must run

This is the single most common source of failure. sni-spoof helps a machine
that sits **behind DPI** reach a Cloudflare-fronted server. It does nothing for
traffic arriving *at* your foreign server.

```
                    ┌─── DPI (the censored network) ───┐
                    │                                  │
  client / relay ───┼──▶ sni-spoof ──▶ Cloudflare edge ─┼──▶ your foreign server
  (inside Iran)     │    (must run HERE)               │    (3x-ui, marzban, …)
                    └──────────────────────────────────┘
```

| Where you run it | Does it help? |
|---|---|
| On an Iranian VPS relaying to your foreign Cloudflare-fronted server | **Yes** — this is the server use case |
| On your own PC/phone gateway inside the censored network | **Yes** — the desktop use case |
| On your foreign VPS (Contabo, Hetzner, …) that already hosts 3x-ui | **No** — there is no DPI on that hop |

**The upstream must be a remote Cloudflare edge IP.** Two upstreams that can
never work:

* an IP belonging to the same machine sni-spoof runs on — the kernel routes
  that traffic internally, the raw sniffer never sees the handshake, and every
  connection dies with `timeout waiting for fake ACK`;
* a direct origin IP that is not behind Cloudflare — the decoy SNI has nothing
  to hide behind.

The panel now refuses the first case at validation time and warns about the second.

### 2. Requirements before you start

* A config (`vless://`, `vmess://`, `trojan://`) whose **domain resolves to
  Cloudflare** — check with `dig +short your.domain.com`; you want an IP in
  `104.*`, `172.67.*`, `188.114.*`, `162.159.*`, `141.101.*`, `173.245.*`.
* Root on the machine that sits behind the DPI.

If your domain does not resolve to Cloudflare, put it behind Cloudflare first
(orange cloud on the DNS record). Nothing here will work otherwise.

### 3. Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/chess902/Sni-spoof/main/install.sh)
```

### 4. Add your config

```bash
sni-spoof                       # → Configs → Import config
```

or from the shell:

```bash
sni-spoof cli link import 'vless://uuid@your.domain.com:443?...' \
  --listen-host 0.0.0.0 --listen-port 40443 --fake-sni security.vercel.com
```

The panel resolves the Cloudflare edge IP for you and creates the listener.

### 5. Verify before touching any client

```bash
sni-spoof doctor
```

Everything must be green. The checks are ordered so the **first FAIL is the
real cause**; the rest are consequences.

| Doctor says | Meaning |
|---|---|
| `upstream … is an address of THIS server` | The listener points at itself — see step 1 |
| `upstream is a Cloudflare edge: FAIL` | Your domain is not behind Cloudflare |
| `listener … TCP ok but TLS failed` | The fake SNI is burned — `sni-spoof cli scan --apply` |
| `core service running: FAIL` | `sni-spoof log core` for the real error |

### 6. Point clients at it

```bash
sni-spoof cli link show --id 1 --host YOUR_SERVER_IP
```

This prints the rewritten link and a QR code. It is your original config with
only the address changed to `YOUR_SERVER_IP:40443`.

---

## Connecting 3x-ui to sni-spoof

Two ways. **Option A is simpler and faster** — use it unless you specifically
need a shared SOCKS proxy.

3x-ui must run on the machine *behind the DPI*, the same one running sni-spoof.

### Option A — outbound straight into the listener (recommended)

No Xray needed on the panel side. In **3x-ui → Panel Settings → Xray Configs**,
add this to `outbounds`. It is your original config with the address changed to
the local listener; every other field stays exactly as it was.

```json
{
  "tag": "sni-spoof",
  "protocol": "vless",
  "settings": {
    "vnext": [
      {
        "address": "127.0.0.1",
        "port": 40443,
        "users": [{ "id": "YOUR-UUID", "encryption": "none" }]
      }
    ]
  },
  "streamSettings": {
    "network": "ws",
    "security": "tls",
    "tlsSettings": {
      "serverName": "your.domain.com",
      "fingerprint": "chrome",
      "allowInsecure": false
    },
    "wsSettings": {
      "path": "/yourpath",
      "headers": { "Host": "your.domain.com" }
    }
  }
}
```

Keep `serverName`, `Host`, `path`, `network` and the UUID identical to your
original config — only `address` and `port` change. For `trojan` use
`"protocol": "trojan"` with `"servers": [{ "address": "127.0.0.1", "port": 40443,
"password": "…" }]`; for `xhttp` transport swap `wsSettings` for `xhttpSettings`.

### Option B — SOCKS outbound into the panel's Xray

Use this when several apps should share one tunnel.

First enable Xray in the panel:

```bash
sni-spoof cli xray install
sni-spoof cli settings set xray enabled true
sni-spoof cli settings set xray socks_udp true      # only if you need UDP
sni-spoof cli xray apply
sni-spoof cli ip --via socks                        # must show the FOREIGN IP
```

That last command is the proof the tunnel works. If it does not print your
foreign server's IP, stop here — adding it to 3x-ui will not help.

Then in **3x-ui → Panel Settings → Xray Configs → outbounds**:

```json
{
  "tag": "sni-spoof-socks",
  "protocol": "socks",
  "settings": {
    "servers": [
      {
        "address": "127.0.0.1",
        "port": 1081
      }
    ]
  }
}
```

If you set a proxy username/password in the panel, add them:

```json
"servers": [
  {
    "address": "127.0.0.1",
    "port": 1081,
    "users": [{ "user": "YOUR_USER", "pass": "YOUR_PASS" }]
  }
]
```

Then add a routing rule so traffic actually uses it — in `routing.rules`,
**before** any rule that sends traffic to `direct`:

```json
{
  "type": "field",
  "outboundTag": "sni-spoof-socks",
  "network": "tcp,udp"
}
```

Notes:

* SOCKS5 carries UDP only when `socks_udp` is enabled on both sides. Leave it
  off unless something needs it.
* Do not route the sni-spoof listener's own traffic back into the SOCKS
  outbound — that is a loop. Keep `geoip:private` on `direct`.
* Restart Xray from 3x-ui after editing, then confirm with
  `sni-spoof cli ip --via socks`.

---

## فارسی

### ۱. اول بدانید هر قطعه کجا باید اجرا شود

شایع‌ترین علت شکست همین است. sni-spoof به دستگاهی کمک می‌کند که **پشت DPI**
است تا به سروری که پشت کلادفلر است برسد. برای ترافیکی که *به* سرور خارجی شما
می‌رسد هیچ کاری نمی‌کند.

```
                    ┌─── DPI (شبکهٔ فیلترشده) ───┐
                    │                            │
  کلاینت / رله ─────┼──▶ sni-spoof ──▶ edge کلادفلر ─┼──▶ سرور خارجی شما
  (داخل ایران)      │    (باید اینجا باشد)        │    (3x-ui، مرزبان، …)
                    └────────────────────────────┘
```

| کجا اجرا می‌کنید | کمکی می‌کند؟ |
|---|---|
| روی VPS ایران که به سرور خارجیِ پشت کلادفلر رله می‌کند | **بله** — کاربرد سروری همین است |
| روی کامپیوتر/گیت‌وی خودتان داخل شبکهٔ فیلترشده | **بله** — کاربرد دسکتاپ |
| روی VPS خارجی خودتان (Contabo، Hetzner…) که 3x-ui رویش است | **نه** — روی آن مسیر DPI وجود ندارد |

**مقصد (upstream) حتماً باید یک IP از edge کلادفلر و راه‌دور باشد.** دو مقصدی که
هرگز کار نمی‌کنند:

* آدرسی که متعلق به همان ماشینی است که sni-spoof رویش اجرا می‌شود — کرنل آن
  ترافیک را داخلی مسیریابی می‌کند، اسنیفر خام هرگز هندشیک را نمی‌بیند و هر
  اتصال با `timeout waiting for fake ACK` می‌میرد؛
* یک IP مستقیم که پشت کلادفلر نیست — SNI جعلی چیزی برای پنهان شدن پشتش ندارد.

پنل حالا مورد اول را موقع اعتبارسنجی رد می‌کند و دربارهٔ مورد دوم هشدار می‌دهد.

### ۲. پیش‌نیازها

* یک کانفیگ (`vless://`، `vmess://`، `trojan://`) که **دامنه‌اش به کلادفلر
  resolve شود** — با `dig +short your.domain.com` بررسی کنید؛ باید IP در
  محدوده‌های `104.*`، `172.67.*`، `188.114.*`، `162.159.*`، `141.101.*` باشد.
* دسترسی root روی ماشینی که پشت DPI است.

اگر دامنه‌تان به کلادفلر resolve نمی‌شود، اول آن را پشت کلادفلر ببرید (ابر نارنجی
روی رکورد DNS). بدون این، هیچ‌چیز کار نخواهد کرد.

### ۳. نصب

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/chess902/Sni-spoof/main/install.sh)
```

### ۴. افزودن کانفیگ

```bash
sni-spoof                       # ← کانفیگ‌ها ← افزودن کانفیگ
```

یا از شل:

```bash
sni-spoof cli link import 'vless://uuid@your.domain.com:443?...' \
  --listen-host 0.0.0.0 --listen-port 40443 --fake-sni security.vercel.com
```

پنل خودش IP کلادفلر را پیدا و لیسنر را می‌سازد.

### ۵. قبل از دست‌زدن به کلاینت، تأیید بگیرید

```bash
sni-spoof doctor
```

همه باید سبز باشد. ترتیب بررسی‌ها طوری است که **اولین FAIL علت واقعی است** و
بقیه پیامد آن‌اند.

| doctor می‌گوید | یعنی |
|---|---|
| `upstream … is an address of THIS server` | لیسنر به خودش وصل شده — مرحلهٔ ۱ |
| `upstream is a Cloudflare edge: FAIL` | دامنه‌تان پشت کلادفلر نیست |
| `listener … TCP ok but TLS failed` | SNI جعلی سوخته — `sni-spoof cli scan --apply` |
| `core service running: FAIL` | برای خطای واقعی: `sni-spoof log core` |

### ۶. کلاینت‌ها را به آن وصل کنید

```bash
sni-spoof cli link show --id 1 --host IP_سرور_شما
```

لینک بازنویسی‌شده و QR را چاپ می‌کند — همان کانفیگ اصلی، فقط آدرسش
`IP_سرور_شما:40443` شده.

---

## وصل کردن 3x-ui به sni-spoof

دو راه دارد. **گزینهٔ الف ساده‌تر و سریع‌تر است** — مگر اینکه واقعاً به یک پروکسی
SOCKS مشترک نیاز داشته باشید.

3x-ui باید روی ماشینی باشد که *پشت DPI* است، همان ماشینی که sni-spoof رویش است.

### گزینهٔ الف — اوت‌باند مستقیم به لیسنر (پیشنهادی)

نیازی به Xray سمت پنل نیست. در **3x-ui ← تنظیمات پنل ← Xray Configs** این را به
`outbounds` اضافه کنید. این همان کانفیگ اصلی شماست که فقط آدرسش به لیسنر محلی
تغییر کرده؛ بقیهٔ فیلدها دقیقاً دست‌نخورده می‌مانند.

```json
{
  "tag": "sni-spoof",
  "protocol": "vless",
  "settings": {
    "vnext": [
      {
        "address": "127.0.0.1",
        "port": 40443,
        "users": [{ "id": "YOUR-UUID", "encryption": "none" }]
      }
    ]
  },
  "streamSettings": {
    "network": "ws",
    "security": "tls",
    "tlsSettings": {
      "serverName": "your.domain.com",
      "fingerprint": "chrome",
      "allowInsecure": false
    },
    "wsSettings": {
      "path": "/yourpath",
      "headers": { "Host": "your.domain.com" }
    }
  }
}
```

`serverName`، `Host`، `path`، `network` و UUID باید عیناً مثل کانفیگ اصلی بمانند؛
فقط `address` و `port` عوض می‌شوند. برای `trojan` از `"protocol": "trojan"` با
`"servers": [{ "address": "127.0.0.1", "port": 40443, "password": "…" }]` استفاده
کنید و برای ترنسپورت `xhttp` به‌جای `wsSettings` از `xhttpSettings` بگذارید.

### گزینهٔ ب — اوت‌باند SOCKS به Xray پنل

وقتی چند برنامه باید یک تونل مشترک داشته باشند.

اول Xray را در پنل فعال کنید:

```bash
sni-spoof cli xray install
sni-spoof cli settings set xray enabled true
sni-spoof cli settings set xray socks_udp true      # فقط اگر UDP لازم دارید
sni-spoof cli xray apply
sni-spoof cli ip --via socks                        # باید IP خارجی را نشان دهد
```

دستور آخر مدرکِ کارکردن تونل است. اگر IP سرور خارجی‌تان را چاپ نکرد، همین‌جا
متوقف شوید — اضافه کردنش به 3x-ui کمکی نمی‌کند.

بعد در **3x-ui ← تنظیمات پنل ← Xray Configs ← outbounds**:

```json
{
  "tag": "sni-spoof-socks",
  "protocol": "socks",
  "settings": {
    "servers": [
      {
        "address": "127.0.0.1",
        "port": 1081
      }
    ]
  }
}
```

اگر در پنل نام کاربری/رمز پروکسی گذاشته‌اید:

```json
"servers": [
  {
    "address": "127.0.0.1",
    "port": 1081,
    "users": [{ "user": "YOUR_USER", "pass": "YOUR_PASS" }]
  }
]
```

سپس یک قانون مسیریابی اضافه کنید تا ترافیک واقعاً از آن رد شود — در
`routing.rules` و **قبل از** هر قانونی که ترافیک را به `direct` می‌فرستد:

```json
{
  "type": "field",
  "outboundTag": "sni-spoof-socks",
  "network": "tcp,udp"
}
```

نکته‌ها:

* SOCKS5 فقط وقتی UDP را حمل می‌کند که `socks_udp` در هر دو طرف روشن باشد.
  اگر لازم ندارید خاموش بگذارید.
* ترافیک خودِ لیسنر sni-spoof را به اوت‌باند SOCKS برنگردانید — حلقه می‌شود.
  `geoip:private` را روی `direct` نگه دارید.
* بعد از ویرایش، Xray را از 3x-ui ری‌استارت کنید و با
  `sni-spoof cli ip --via socks` تأیید بگیرید.
