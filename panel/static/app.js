/* sni-spoof panel - vanilla JS single page app (no build step, no CDN) */
(function () {
"use strict";

// ---------------------------------------------------------------- i18n
var I18N = {
  fa: {
    "login.title": "ورود به پنل", "login.sub": "مدیریت SNI Spoof",
    "login.username": "نام کاربری", "login.password": "رمز عبور",
    "login.totp": "کد دو مرحله‌ای", "login.submit": "ورود",
    "nav.dashboard": "داشبورد", "nav.listeners": "لیسنرها", "nav.links": "کانفیگ‌ها",
    "nav.xray": "Xray", "nav.scanner": "اسکنر SNI", "nav.logs": "لاگ‌ها",
    "nav.backup": "بکاپ", "nav.settings": "تنظیمات", "nav.users": "کاربران",
    "nav.language": "زبان", "nav.theme": "تم", "nav.logout": "خروج",
    "common.add": "افزودن", "common.edit": "ویرایش", "common.delete": "حذف",
    "common.save": "ذخیره", "common.cancel": "انصراف", "common.refresh": "بازخوانی",
    "common.test": "تست", "common.apply": "اعمال", "common.close": "بستن",
    "common.copy": "کپی", "common.copied": "کپی شد", "common.none": "موردی نیست",
    "common.enabled": "فعال", "common.disabled": "غیرفعال", "common.yes": "بله",
    "common.no": "خیر", "common.status": "وضعیت", "common.actions": "عملیات",
    "common.name": "نام", "common.port": "پورت", "common.host": "هاست",
    "common.confirm": "مطمئنی؟", "common.loading": "در حال بارگذاری…",
    "common.install": "نصب", "common.update": "بروزرسانی", "common.start": "شروع",
    "common.stop": "توقف", "common.restart": "ری‌استارت", "common.download": "دانلود",
    "common.upload": "آپلود", "common.restore": "بازیابی", "common.create": "ساخت",
    "common.optional": "اختیاری", "common.error": "خطا",
    "dash.cpu": "پردازنده", "dash.memory": "حافظه", "dash.disk": "دیسک",
    "dash.uptime": "آپ‌تایم", "dash.network": "شبکه", "dash.services": "سرویس‌ها",
    "dash.listeners": "وضعیت لیسنرها", "dash.traffic": "اتصال‌ها و ترافیک",
    "dash.events": "رویدادهای اخیر", "dash.system": "اطلاعات سیستم",
    "dash.checkall": "تست همه", "dash.conns": "اتصال‌ها",
    "lis.title": "لیسنرها", "lis.listen": "آدرس شنود", "lis.upstream": "مقصد",
    "lis.fakesni": "SNI جعلی", "lis.add": "لیسنر جدید", "lis.host": "دامنه یا IP مقصد",
    "lis.refreship": "بروزرسانی IP", "lis.hint": "دامنهٔ کلادفلر را وارد کنید تا IP خودکار پیدا شود",
    "lis.timeouts": "تایم‌اوت‌ها", "lis.applied": "کانفیگ اعمال شد",
    "lis.conns": "اتصال", "lis.cf": "کلادفلر",
    "lnk.title": "کانفیگ‌ها", "lnk.import": "افزودن کانفیگ",
    "lnk.paste": "لینک‌های vless / vmess / trojan را وارد کنید (هر خط یکی)",
    "lnk.createlistener": "ساخت خودکار لیسنر برای هر لینک",
    "lnk.client": "لینک کلاینت", "lnk.activate": "انتخاب برای Xray",
    "lnk.active": "فعال", "lnk.sub": "لینک ساب‌اسکریپشن", "lnk.rotate": "توکن جدید",
    "lnk.clienthost": "آدرسی که کلاینت‌ها به آن وصل می‌شوند",
    "xr.title": "Xray", "xr.install": "نصب Xray", "xr.httpport": "پورت HTTP",
    "xr.socksport": "پورت SOCKS", "xr.listen": "آدرس شنود",
    "xr.auth": "نام کاربری/رمز پروکسی", "xr.enable": "فعال بودن Xray",
    "xr.config": "پیش‌نمایش کانفیگ", "xr.ipcheck": "بررسی IP خروجی",
    "xr.direct": "مستقیم", "xr.viahttp": "از طریق HTTP", "xr.viasocks": "از طریق SOCKS",
    "sc.title": "اسکنر SNI", "sc.target": "IP هدف", "sc.timeout": "تایم‌اوت (ثانیه)",
    "sc.concurrency": "همزمانی", "sc.start": "شروع اسکن", "sc.cancel": "لغو",
    "sc.results": "نتایج", "sc.applysni": "اعمال روی لیسنرها", "sc.list": "لیست کاندیدها",
    "sc.savelist": "ذخیره لیست", "sc.running": "در حال اسکن…", "sc.passed": "قبول‌شده",
    "sc.history": "اسکن‌های قبلی", "sc.latency": "تأخیر",
    "lg.title": "لاگ‌ها", "lg.lines": "تعداد خط", "lg.auto": "بروزرسانی خودکار",
    "bk.title": "بکاپ", "bk.create": "ساخت بکاپ", "bk.size": "حجم", "bk.date": "تاریخ",
    "bk.upload": "بازیابی از فایل", "bk.export": "خروجی تنظیمات (JSON)",
    "bk.telegram": "ارسال به تلگرام",
    "st.panel": "پنل", "st.core": "هسته", "st.watchdog": "نگهبان",
    "st.stats": "آمار", "st.telegram": "تلگرام", "st.backup": "بکاپ خودکار",
    "st.tls": "گواهی TLS", "st.network": "شبکه",
    "st.restartneeded": "برای اعمال، سرویس پنل را ری‌استارت کنید",
    "st.selfsigned": "ساخت گواهی self-signed", "st.acme": "دریافت گواهی Let's Encrypt",
    "st.disabletls": "غیرفعال کردن TLS", "st.testtg": "ارسال پیام تست",
    "us.title": "کاربران", "us.add": "کاربر جدید", "us.password": "رمز عبور",
    "us.changepw": "تغییر رمز", "us.current": "رمز فعلی", "us.new": "رمز جدید",
    "us.2fa": "ورود دو مرحله‌ای", "us.enable2fa": "فعال‌سازی", "us.disable2fa": "غیرفعال‌سازی",
    "us.scanqr": "این QR را در Google Authenticator اسکن کنید",
    "us.lastlogin": "آخرین ورود"
  },
  en: {
    "login.title": "Panel sign in", "login.sub": "SNI Spoof management",
    "login.username": "Username", "login.password": "Password",
    "login.totp": "Two-factor code", "login.submit": "Sign in",
    "nav.dashboard": "Dashboard", "nav.listeners": "Listeners", "nav.links": "Configs",
    "nav.xray": "Xray", "nav.scanner": "SNI scanner", "nav.logs": "Logs",
    "nav.backup": "Backup", "nav.settings": "Settings", "nav.users": "Users",
    "nav.language": "Language", "nav.theme": "Theme", "nav.logout": "Sign out",
    "common.add": "Add", "common.edit": "Edit", "common.delete": "Delete",
    "common.save": "Save", "common.cancel": "Cancel", "common.refresh": "Refresh",
    "common.test": "Test", "common.apply": "Apply", "common.close": "Close",
    "common.copy": "Copy", "common.copied": "Copied", "common.none": "Nothing here yet",
    "common.enabled": "Enabled", "common.disabled": "Disabled", "common.yes": "Yes",
    "common.no": "No", "common.status": "Status", "common.actions": "Actions",
    "common.name": "Name", "common.port": "Port", "common.host": "Host",
    "common.confirm": "Are you sure?", "common.loading": "Loading…",
    "common.install": "Install", "common.update": "Update", "common.start": "Start",
    "common.stop": "Stop", "common.restart": "Restart", "common.download": "Download",
    "common.upload": "Upload", "common.restore": "Restore", "common.create": "Create",
    "common.optional": "optional", "common.error": "Error",
    "dash.cpu": "CPU", "dash.memory": "Memory", "dash.disk": "Disk",
    "dash.uptime": "Uptime", "dash.network": "Network", "dash.services": "Services",
    "dash.listeners": "Listener health", "dash.traffic": "Connections & traffic",
    "dash.events": "Recent events", "dash.system": "System",
    "dash.checkall": "Test all", "dash.conns": "Connections",
    "lis.title": "Listeners", "lis.listen": "Listen on", "lis.upstream": "Upstream",
    "lis.fakesni": "Fake SNI", "lis.add": "New listener", "lis.host": "Upstream domain or IP",
    "lis.refreship": "Refresh IP", "lis.hint": "Enter the Cloudflare domain and the IP is resolved automatically",
    "lis.timeouts": "Timeouts", "lis.applied": "Configuration applied",
    "lis.conns": "conns", "lis.cf": "Cloudflare",
    "lnk.title": "Configs", "lnk.import": "Import config",
    "lnk.paste": "Paste vless / vmess / trojan links (one per line)",
    "lnk.createlistener": "Create a listener for each link",
    "lnk.client": "Client link", "lnk.activate": "Use for Xray",
    "lnk.active": "active", "lnk.sub": "Subscription URL", "lnk.rotate": "New token",
    "lnk.clienthost": "Address clients will connect to",
    "xr.title": "Xray", "xr.install": "Install Xray", "xr.httpport": "HTTP port",
    "xr.socksport": "SOCKS port", "xr.listen": "Listen address",
    "xr.auth": "Proxy username / password", "xr.enable": "Enable Xray",
    "xr.config": "Config preview", "xr.ipcheck": "Egress IP check",
    "xr.direct": "Direct", "xr.viahttp": "Via HTTP", "xr.viasocks": "Via SOCKS",
    "sc.title": "SNI scanner", "sc.target": "Target IP", "sc.timeout": "Timeout (s)",
    "sc.concurrency": "Concurrency", "sc.start": "Start scan", "sc.cancel": "Cancel",
    "sc.results": "Results", "sc.applysni": "Apply to listeners", "sc.list": "Candidate list",
    "sc.savelist": "Save list", "sc.running": "Scanning…", "sc.passed": "passed",
    "sc.history": "Previous scans", "sc.latency": "Latency",
    "lg.title": "Logs", "lg.lines": "Lines", "lg.auto": "Auto refresh",
    "bk.title": "Backup", "bk.create": "Create backup", "bk.size": "Size", "bk.date": "Date",
    "bk.upload": "Restore from file", "bk.export": "Export settings (JSON)",
    "bk.telegram": "Send to Telegram",
    "st.panel": "Panel", "st.core": "Core", "st.watchdog": "Watchdog",
    "st.stats": "Metrics", "st.telegram": "Telegram", "st.backup": "Automatic backup",
    "st.tls": "TLS certificate", "st.network": "Network",
    "st.restartneeded": "Restart the panel service for this to take effect",
    "st.selfsigned": "Generate self-signed certificate", "st.acme": "Issue Let's Encrypt certificate",
    "st.disabletls": "Disable TLS", "st.testtg": "Send test message",
    "us.title": "Users", "us.add": "New user", "us.password": "Password",
    "us.changepw": "Change password", "us.current": "Current password", "us.new": "New password",
    "us.2fa": "Two-factor authentication", "us.enable2fa": "Enable", "us.disable2fa": "Disable",
    "us.scanqr": "Scan this QR with Google Authenticator",
    "us.lastlogin": "Last login"
  }
};

var state = {
  lang: localStorage.getItem("lang") || "fa",
  theme: localStorage.getItem("theme") || "dark",
  page: "dashboard",
  user: null,
  timers: []
};

function t(key) {
  var dict = I18N[state.lang] || I18N.fa;
  return dict[key] || (I18N.en[key] || key);
}

// ---------------------------------------------------------------- helpers
function $(sel, root) { return (root || document).querySelector(sel); }
function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

function esc(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function api(path, options) {
  options = options || {};
  var init = {
    method: options.method || "GET",
    headers: { "X-Requested-With": "sni-spoof-panel", "X-Panel-Lang": state.lang },
    credentials: "same-origin"
  };
  if (options.body !== undefined) {
    if (options.raw) { init.body = options.body; }
    else { init.headers["Content-Type"] = "application/json"; init.body = JSON.stringify(options.body); }
  }
  return fetch(base() + path, init).then(function (response) {
    var ctype = response.headers.get("Content-Type") || "";
    if (ctype.indexOf("application/json") < 0) {
      return response.text().then(function (text) {
        if (!response.ok) { throw new Error(text.slice(0, 200) || response.statusText); }
        return text;
      });
    }
    return response.json().then(function (data) {
      if (!response.ok || data.ok === false) {
        var error = new Error(data.error || response.statusText);
        error.key = data.key; error.status = response.status;
        throw error;
      }
      return data;
    });
  });
}

function base() {
  var path = window.location.pathname.replace(/\/(index\.html)?$/, "");
  return path;
}

function toast(message, kind) {
  var node = document.createElement("div");
  node.className = "toast " + (kind || "");
  node.textContent = message;
  $("#toasts").appendChild(node);
  setTimeout(function () { node.remove(); }, kind === "err" ? 7000 : 3800);
}

function fail(error) { toast(error.message || String(error), "err"); }

function bytes(value) {
  value = Number(value || 0);
  var units = ["B", "KB", "MB", "GB", "TB", "PB"], i = 0;
  while (value >= 1024 && i < units.length - 1) { value /= 1024; i++; }
  return value.toFixed(i === 0 ? 0 : 1) + " " + units[i];
}

function duration(seconds) {
  seconds = Math.max(0, Math.floor(seconds || 0));
  var d = Math.floor(seconds / 86400), h = Math.floor((seconds % 86400) / 3600),
      m = Math.floor((seconds % 3600) / 60);
  if (d) { return d + "d " + h + "h"; }
  if (h) { return h + "h " + m + "m"; }
  return m + "m";
}

function stamp(unix) {
  if (!unix) { return "—"; }
  var date = new Date(unix * 1000);
  return date.toLocaleString(state.lang === "fa" ? "fa-IR" : "en-GB", { hour12: false });
}

function copy(text) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(function () { toast(t("common.copied"), "ok"); });
    return;
  }
  var area = document.createElement("textarea");
  area.value = text; area.style.position = "fixed"; area.style.opacity = "0";
  document.body.appendChild(area); area.select();
  try { document.execCommand("copy"); toast(t("common.copied"), "ok"); } catch (e) { fail(e); }
  area.remove();
}

function modal(title, bodyHtml, options) {
  options = options || {};
  var back = document.createElement("div");
  back.className = "modal-back";
  back.innerHTML =
    '<div class="modal"><h3>' + esc(title) + "</h3>" +
    '<div class="modal-body">' + bodyHtml + "</div>" +
    '<div class="modal-actions">' +
    (options.hideCancel ? "" : '<button data-act="cancel">' + esc(t("common.cancel")) + "</button>") +
    (options.submit === false ? "" :
      '<button class="btn-primary" data-act="ok">' + esc(options.okLabel || t("common.save")) + "</button>") +
    "</div></div>";
  document.getElementById("modal-root").appendChild(back);

  function close() { back.remove(); }
  back.addEventListener("click", function (event) {
    if (event.target === back || event.target.dataset.act === "cancel") { close(); }
    if (event.target.dataset.act === "ok" && options.onSubmit) {
      var result = options.onSubmit(back, close);
      if (result !== false) { close(); }
    }
  });
  if (options.onOpen) { options.onOpen(back, close); }
  return { root: back, close: close };
}

function confirmAction(message, onYes) {
  modal(t("common.confirm"), "<p>" + esc(message) + "</p>", {
    okLabel: t("common.yes"),
    onSubmit: function () { onYes(); }
  });
}

function value(root, name) {
  var node = root.querySelector('[name="' + name + '"]');
  if (!node) { return ""; }
  return node.type === "checkbox" ? node.checked : node.value.trim();
}

function field(label, name, opts) {
  opts = opts || {};
  var attrs = 'name="' + name + '" value="' + esc(opts.value === undefined ? "" : opts.value) + '"';
  if (opts.type) { attrs += ' type="' + opts.type + '"'; }
  if (opts.placeholder) { attrs += ' placeholder="' + esc(opts.placeholder) + '"'; }
  if (opts.dir) { attrs += ' dir="' + opts.dir + '"'; }
  return '<div class="field"><label>' + esc(label) +
    (opts.hint ? ' <span style="opacity:.7">(' + esc(opts.hint) + ")</span>" : "") +
    "</label><input " + attrs + "></div>";
}

function checkbox(label, name, checked) {
  return '<div class="check"><input type="checkbox" name="' + name + '"' +
    (checked ? " checked" : "") + ' id="cb-' + name + '"><label for="cb-' + name + '">' +
    esc(label) + "</label></div>";
}

function selectField(label, name, options, current) {
  var html = '<div class="field"><label>' + esc(label) + '</label><select name="' + name + '">';
  options.forEach(function (opt) {
    html += '<option value="' + esc(opt[0]) + '"' +
      (String(opt[0]) === String(current) ? " selected" : "") + ">" + esc(opt[1]) + "</option>";
  });
  return html + "</select></div>";
}

function clearTimers() {
  state.timers.forEach(clearInterval);
  state.timers = [];
}

function every(ms, fn) { state.timers.push(setInterval(fn, ms)); }

function badge(ok, okText, badText) {
  return '<span class="badge ' + (ok ? "ok" : "err") + '"><i class="dot"></i>' +
    esc(ok ? okText : badText) + "</span>";
}

function chart(canvas, series, labels) {
  var ctx = canvas.getContext("2d");
  var ratio = window.devicePixelRatio || 1;
  var width = canvas.clientWidth, height = canvas.clientHeight;
  canvas.width = width * ratio; canvas.height = height * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  var css = getComputedStyle(document.body);
  var grid = css.getPropertyValue("--border").trim() || "#26324f";
  var muted = css.getPropertyValue("--muted").trim() || "#94a3b8";
  var max = 1;
  series.forEach(function (s) { s.data.forEach(function (v) { if (v > max) { max = v; } }); });
  max = max * 1.15;

  ctx.strokeStyle = grid; ctx.lineWidth = 1; ctx.font = "10px sans-serif"; ctx.fillStyle = muted;
  ctx.direction = "ltr";   // axis labels are numbers; never mirror them
  for (var g = 0; g <= 4; g++) {
    var y = 12 + (height - 30) * g / 4;
    ctx.beginPath(); ctx.moveTo(38, y); ctx.lineTo(width - 6, y); ctx.stroke();
    ctx.fillText(labels.format(max - max * g / 4), 2, y + 3);
  }
  series.forEach(function (s) {
    if (!s.data.length) { return; }
    ctx.beginPath(); ctx.strokeStyle = s.color; ctx.lineWidth = 2;
    s.data.forEach(function (v, i) {
      var x = 38 + (width - 46) * (s.data.length === 1 ? 1 : i / (s.data.length - 1));
      var y = 12 + (height - 30) * (1 - v / max);
      if (i === 0) { ctx.moveTo(x, y); } else { ctx.lineTo(x, y); }
    });
    ctx.stroke();
  });
}

// ---------------------------------------------------------------- pages
var pages = {};

pages.dashboard = function (root) {
  root.innerHTML = '<div class="empty">' + esc(t("common.loading")) + "</div>";
  $("#page-tools").innerHTML =
    '<button class="btn-sm" id="check-all">' + esc(t("dash.checkall")) + "</button>" +
    '<button class="btn-sm" id="refresh-now">' + esc(t("common.refresh")) + "</button>";

  function draw(data) {
    var mem = data.memory, disk = data.disk;
    var svc = data.services || {};
    var html =
      '<div class="grid cols-4">' +
        statCard(t("dash.cpu"), data.cpu.toFixed(1) + "%", "load " + (data.load || []).join(" "), data.cpu) +
        statCard(t("dash.memory"), mem.percent + "%", bytes(mem.used) + " / " + bytes(mem.total), mem.percent) +
        statCard(t("dash.disk"), disk.percent + "%", bytes(disk.used) + " / " + bytes(disk.total), disk.percent) +
        statCard(t("dash.uptime"), duration(data.uptime), data.hostname, null) +
      "</div>" +
      '<div class="grid cols-2" style="margin-top:16px">' +
        '<div class="card"><h3>' + esc(t("dash.services")) + "</h3>" + servicesHtml(svc, data) + "</div>" +
        '<div class="card"><h3>' + esc(t("dash.network")) +
          '<span class="right">↓ ' + bytes(data.net.rx_rate) + "/s ↑ " + bytes(data.net.tx_rate) + "/s</span></h3>" +
          '<div class="kv"><b>' + esc(t("dash.network")) + " ↓</b><span>" + bytes(data.net.rx) + "</span>" +
          "<b>" + esc(t("dash.network")) + " ↑</b><span>" + bytes(data.net.tx) + "</span>" +
          "<b>core RSS</b><span>" + bytes((data.core_process || {}).rss || 0) + "</span>" +
          "<b>core fds</b><span>" + ((data.core_process || {}).open_fds || 0) + "</span></div>" +
        "</div>" +
      "</div>" +
      '<div class="card" style="margin-top:16px"><h3>' + esc(t("dash.traffic")) + "</h3>" +
        '<canvas id="dash-chart"></canvas>' +
        '<div class="legend"><span><i style="background:#38bdf8"></i>' + esc(t("dash.conns")) + "</span></div></div>" +
      '<div class="card" style="margin-top:16px"><h3>' + esc(t("dash.listeners")) + "</h3>" +
        listenerHealthHtml(data) + "</div>" +
      '<div class="card" style="margin-top:16px"><h3>' + esc(t("dash.events")) + '</h3><div id="dash-events" class="empty">…</div></div>';
    root.innerHTML = html;

    api("/api/history?hours=6").then(function (res) {
      var canvas = $("#dash-chart");
      if (!canvas) { return; }
      chart(canvas, [{ color: "#38bdf8", data: res.points.map(function (p) { return p.conns || 0; }) }],
        { format: function (v) { return Math.round(v); } });
    }).catch(function () {});

    api("/api/events?limit=12").then(function (res) {
      var node = $("#dash-events");
      if (!node) { return; }
      if (!res.events.length) { node.className = "empty"; node.textContent = t("common.none"); return; }
      node.className = "table-wrap";
      node.innerHTML = "<table><tbody>" + res.events.map(function (e) {
        return "<tr><td style='white-space:nowrap'>" + esc(stamp(e.ts)) + "</td><td>" +
          '<span class="badge ' + (e.level === "error" ? "err" : e.level === "warn" ? "warn" : "") + '">' +
          esc(e.category) + '</span></td><td dir="auto">' + esc(e.message) + "</td></tr>";
      }).join("") + "</tbody></table>";
    }).catch(function () {});
  }

  function statCard(label, val, hint, percent) {
    return '<div class="card stat"><div class="label">' + esc(label) + "</div>" +
      '<div class="value">' + esc(val) + "</div>" +
      '<div class="hint">' + esc(hint || "") + "</div>" +
      (percent === null ? "" : '<div class="bar"><i style="width:' + Math.min(100, percent) + '%"></i></div>') +
      "</div>";
  }

  function servicesHtml(svc, data) {
    var rows = Object.keys(svc).map(function (alias) {
      var info = svc[alias];
      var version = alias === "core" ? data.versions.core : alias === "xray" ? data.versions.xray : data.versions.panel;
      return "<tr><td><b>" + esc(alias) + "</b><br><small style='color:var(--muted)'>" +
        esc(version || "—") + "</small></td><td>" +
        badge(info.active, info.state, info.state || "inactive") +
        (info.enabled ? ' <span class="badge">auto</span>' : "") + "</td>" +
        '<td><div class="actions">' +
        ["start", "restart", "stop"].map(function (verb) {
          if (alias === "panel" && verb === "stop") { return ""; }
          return '<button class="btn-sm" data-svc="' + alias + '" data-verb="' + verb + '">' +
            esc(t("common." + verb)) + "</button>";
        }).join("") + "</div></td></tr>";
    }).join("");
    return '<div class="table-wrap"><table><tbody>' + rows + "</tbody></table></div>" +
      (data.systemd ? "" : '<p style="color:var(--warn);font-size:12px">systemd not available</p>');
  }

  function listenerHealthHtml(data) {
    if (!data.listeners.length) { return '<div class="empty">' + esc(t("common.none")) + "</div>"; }
    return '<div class="table-wrap"><table><thead><tr><th>#</th><th>' + esc(t("common.name")) +
      "</th><th>" + esc(t("common.port")) + "</th><th>" + esc(t("common.status")) +
      "</th><th>" + esc(t("dash.conns")) + "</th></tr></thead><tbody>" +
      data.listeners.map(function (item) {
        var health = (data.health || {})[item.id];
        return "<tr><td>" + item.id + "</td><td>" + esc(item.name || "—") + "</td><td>" + item.port + "</td>" +
          "<td>" + badge(item.listening, "listening", "down") +
          (health && health.tls_ok !== null ? " " + badge(health.tls_ok, "tls ok", "tls fail") : "") +
          "</td><td>" + item.established + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  function load() { api("/api/status").then(draw).catch(fail); }
  load();
  every(5000, load);

  root.addEventListener("click", function (event) {
    var target = event.target.closest("[data-svc]");
    if (!target) { return; }
    target.disabled = true;
    api("/api/service/" + target.dataset.svc + "/" + target.dataset.verb, { method: "POST" })
      .then(function (res) { toast(res.message || "ok", res.ok ? "ok" : "err"); load(); })
      .catch(fail).finally(function () { target.disabled = false; });
  });

  $("#refresh-now").onclick = load;
  $("#check-all").onclick = function () {
    this.disabled = true;
    api("/api/health/check", { method: "POST" })
      .then(function (res) {
        var ok = res.results.filter(function (r) { return r.tcp_ok; }).length;
        toast(ok + " / " + res.results.length + " ok", ok === res.results.length ? "ok" : "err");
        load();
      }).catch(fail).finally(function () { $("#check-all").disabled = false; });
  };
};

pages.listeners = function (root) {
  $("#page-tools").innerHTML =
    '<button class="btn-sm" id="apply-cfg">' + esc(t("common.apply")) + "</button>" +
    '<button class="btn-primary btn-sm" id="add-listener">+ ' + esc(t("lis.add")) + "</button>";

  function load() {
    api("/api/listeners").then(function (res) {
      if (!res.listeners.length) {
        root.innerHTML = '<div class="card"><div class="empty">' + esc(t("common.none")) + "</div></div>";
        return;
      }
      root.innerHTML = '<div class="card"><div class="table-wrap"><table><thead><tr>' +
        "<th>#</th><th>" + esc(t("common.name")) + "</th><th>" + esc(t("lis.listen")) +
        "</th><th>" + esc(t("lis.upstream")) + "</th><th>" + esc(t("lis.fakesni")) +
        "</th><th>" + esc(t("common.status")) + "</th><th>" + esc(t("common.actions")) +
        "</tr></thead><tbody>" + res.listeners.map(row).join("") + "</tbody></table></div></div>";
    }).catch(fail);
  }

  function row(item) {
    var health = item.health || {};
    return "<tr><td>" + item.id + "</td>" +
      "<td>" + esc(item.name || "—") + (item.remark ? "<br><small style='color:var(--muted)'>" + esc(item.remark) + "</small>" : "") + "</td>" +
      '<td class="mono ltr">' + esc(item.listen_host + ":" + item.listen_port) + "</td>" +
      '<td class="mono ltr">' + esc(item.connect_ip + ":" + item.connect_port) +
        (item.connect_host ? "<br><small style='color:var(--muted)'>" + esc(item.connect_host) + "</small>" : "") +
        (item.cloudflare ? ' <span class="badge ok">' + esc(t("lis.cf")) + "</span>" : "") + "</td>" +
      '<td class="mono ltr">' + esc(item.fake_sni) + "</td>" +
      "<td>" + badge(item.enabled === 1, t("common.enabled"), t("common.disabled")) +
        " " + badge(item.listening, "up", "down") +
        '<br><small style="color:var(--muted)">' + item.established + " " + esc(t("lis.conns")) + "</small>" +
        (health.tls_ok === true ? ' <span class="badge ok">tls</span>' : "") + "</td>" +
      '<td><div class="actions">' +
        '<button class="btn-sm" data-edit="' + item.id + '">' + esc(t("common.edit")) + "</button>" +
        '<button class="btn-sm" data-test="' + item.id + '">' + esc(t("common.test")) + "</button>" +
        '<button class="btn-sm" data-ip="' + item.id + '">' + esc(t("lis.refreship")) + "</button>" +
        '<button class="btn-sm" data-toggle="' + item.id + '" data-on="' + item.enabled + '">' +
          esc(item.enabled ? t("common.stop") : t("common.start")) + "</button>" +
        '<button class="btn-sm btn-danger" data-del="' + item.id + '">' + esc(t("common.delete")) + "</button>" +
      "</div></td></tr>";
  }

  function form(item) {
    item = item || {};
    return field(t("common.name"), "name", { value: item.name || "" }) +
      '<div class="row">' +
        field(t("lis.listen"), "listen_host", { value: item.listen_host || "0.0.0.0", dir: "ltr" }) +
        field(t("common.port"), "listen_port", { value: item.listen_port || 40443, type: "number", dir: "ltr" }) +
      "</div>" +
      field(t("lis.host"), "connect_host", { value: item.connect_host || "", dir: "ltr", hint: t("lis.hint") }) +
      '<div class="row">' +
        field("IP", "connect_ip", { value: item.connect_ip || "", dir: "ltr", hint: t("common.optional") }) +
        field(t("common.port"), "connect_port", { value: item.connect_port || 443, type: "number", dir: "ltr" }) +
      "</div>" +
      field(t("lis.fakesni"), "fake_sni", { value: item.fake_sni || "security.vercel.com", dir: "ltr" }) +
      '<div class="row">' +
        field("conn_timeout_sec", "conn_timeout_sec", { value: item.conn_timeout_sec || 5, type: "number" }) +
        field("handshake_timeout_sec", "handshake_timeout_sec", { value: item.handshake_timeout_sec || 2, type: "number" }) +
        field("keepalive_time_sec", "keepalive_time_sec", { value: item.keepalive_time_sec || 11, type: "number" }) +
        field("keepalive_interval_sec", "keepalive_interval_sec", { value: item.keepalive_interval_sec || 2, type: "number" }) +
      "</div>" +
      field("remark", "remark", { value: item.remark || "" }) +
      checkbox(t("common.enabled"), "enabled", item.id ? item.enabled === 1 : true);
  }

  function collect(node) {
    return {
      name: value(node, "name"),
      listen_host: value(node, "listen_host"),
      listen_port: Number(value(node, "listen_port")),
      connect_host: value(node, "connect_host"),
      connect_ip: value(node, "connect_ip"),
      connect_port: Number(value(node, "connect_port")),
      fake_sni: value(node, "fake_sni"),
      conn_timeout_sec: Number(value(node, "conn_timeout_sec")),
      handshake_timeout_sec: Number(value(node, "handshake_timeout_sec")),
      keepalive_time_sec: Number(value(node, "keepalive_time_sec")),
      keepalive_interval_sec: Number(value(node, "keepalive_interval_sec")),
      remark: value(node, "remark"),
      enabled: value(node, "enabled")
    };
  }

  $("#add-listener").onclick = function () {
    modal(t("lis.add"), form(), {
      onSubmit: function (node) {
        api("/api/listeners", { method: "POST", body: collect(node) })
          .then(function () { toast(t("lis.applied"), "ok"); load(); }).catch(fail);
      }
    });
  };
  $("#apply-cfg").onclick = function () {
    api("/api/listeners/apply", { method: "POST" })
      .then(function (res) { toast(res.apply.message || t("lis.applied"), "ok"); load(); }).catch(fail);
  };

  root.addEventListener("click", function (event) {
    var node = event.target;
    if (node.dataset.edit) {
      api("/api/listeners").then(function (res) {
        var item = res.listeners.filter(function (l) { return String(l.id) === node.dataset.edit; })[0];
        modal(t("common.edit") + " #" + item.id, form(item), {
          onSubmit: function (root2) {
            api("/api/listeners/" + item.id, { method: "PUT", body: collect(root2) })
              .then(function () { toast(t("lis.applied"), "ok"); load(); }).catch(fail);
          }
        });
      });
    } else if (node.dataset.del) {
      confirmAction("#" + node.dataset.del, function () {
        api("/api/listeners/" + node.dataset.del, { method: "DELETE" })
          .then(function () { toast(t("lis.applied"), "ok"); load(); }).catch(fail);
      });
    } else if (node.dataset.toggle) {
      api("/api/listeners/" + node.dataset.toggle + "/toggle",
        { method: "POST", body: { enabled: node.dataset.on !== "1" } })
        .then(load).catch(fail);
    } else if (node.dataset.ip) {
      node.disabled = true;
      api("/api/listeners/" + node.dataset.ip + "/refresh-ip", { method: "POST" })
        .then(function (res) {
          toast(res.ip + (res.changed ? " ✓" : " (unchanged)"), "ok"); load();
        }).catch(fail).finally(function () { node.disabled = false; });
    } else if (node.dataset.test) {
      node.disabled = true;
      api("/api/listeners/" + node.dataset.test + "/test", { method: "POST" })
        .then(function (res) {
          modal(t("common.test") + " #" + res.listener_id,
            '<div class="kv"><b>TCP</b><span>' + (res.tcp_ok ? "✅ " + res.tcp_ms + " ms" : "❌ " + esc(res.error)) + "</span>" +
            "<b>TLS</b><span>" + (res.tls_ok === null ? "—" : res.tls_ok ? "✅ " + res.tls_ms + " ms" : "❌ " + esc(res.error)) + "</span>" +
            "<b>upstream</b><span>" + (res.upstream.ok ? "✅ " + res.upstream.ms + " ms" : "❌ " + esc(res.upstream.error)) + "</span></div>",
            { submit: false, hideCancel: false });
        }).catch(fail).finally(function () { node.disabled = false; });
    }
  });

  load();
  every(8000, load);
};

pages.links = function (root) {
  $("#page-tools").innerHTML =
    '<button class="btn-primary btn-sm" id="import-link">+ ' + esc(t("lnk.import")) + "</button>";

  function load() {
    Promise.all([api("/api/links"), api("/api/subscription/token")]).then(function (res) {
      var links = res[0].links, active = res[0].active_link_id, sub = res[1];
      root.innerHTML =
        '<div class="card"><h3>' + esc(t("lnk.sub")) + "</h3>" +
          '<div class="copy-box"><code id="sub-url">' + esc(sub.url) + "</code>" +
          '<button class="btn-sm" id="copy-sub">' + esc(t("common.copy")) + "</button>" +
          '<button class="btn-sm" id="rotate-sub">' + esc(t("lnk.rotate")) + "</button></div></div>" +
        '<div class="card" style="margin-top:16px">' +
        (links.length ? '<div class="table-wrap"><table><thead><tr><th>#</th><th>' +
          esc(t("common.name")) + "</th><th>proto</th><th>" + esc(t("lis.upstream")) +
          "</th><th>listener</th><th>" + esc(t("common.actions")) + "</th></tr></thead><tbody>" +
          links.map(function (item) { return row(item, active); }).join("") + "</tbody></table></div>"
          : '<div class="empty">' + esc(t("common.none")) + "</div>") + "</div>";

      $("#copy-sub").onclick = function () { copy(sub.url); };
      $("#rotate-sub").onclick = function () {
        api("/api/subscription/rotate", { method: "POST" }).then(load).catch(fail);
      };
    }).catch(fail);
  }

  function row(item, active) {
    var parsed = item.parsed || {};
    return "<tr><td>" + item.id + "</td><td>" + esc(item.name || "—") +
      (item.id === active ? ' <span class="badge ok">' + esc(t("lnk.active")) + "</span>" : "") + "</td>" +
      "<td>" + esc(item.protocol) + (parsed.network ? " / " + esc(parsed.network) : "") + "</td>" +
      '<td class="mono ltr">' + esc((parsed.upstream_host || "") + ":" + (parsed.upstream_port || "")) + "</td>" +
      "<td>" + (item.listener_id || "—") + "</td>" +
      '<td><div class="actions">' +
        '<button class="btn-sm" data-client="' + item.id + '">' + esc(t("lnk.client")) + "</button>" +
        '<button class="btn-sm" data-activate="' + item.id + '">' + esc(t("lnk.activate")) + "</button>" +
        '<button class="btn-sm btn-danger" data-del="' + item.id + '">' + esc(t("common.delete")) + "</button>" +
      "</div></td></tr>";
  }

  $("#import-link").onclick = function () {
    var html =
      '<div class="field"><label>' + esc(t("lnk.paste")) + '</label>' +
      '<textarea name="links" dir="ltr" rows="6" placeholder="vless://..."></textarea></div>' +
      '<div class="row">' +
        field(t("lis.listen"), "listen_host", { value: "0.0.0.0", dir: "ltr" }) +
        field(t("common.port"), "listen_port", { value: 40443, type: "number", dir: "ltr" }) +
      "</div>" +
      field(t("lis.fakesni"), "fake_sni", { value: "security.vercel.com", dir: "ltr" }) +
      checkbox(t("lnk.createlistener"), "create_listener", true);
    modal(t("lnk.import"), html, {
      onSubmit: function (node) {
        api("/api/links/import", {
          method: "POST",
          body: {
            links: node.querySelector('[name="links"]').value,
            listen_host: value(node, "listen_host"),
            listen_port: Number(value(node, "listen_port")),
            fake_sni: value(node, "fake_sni"),
            create_listener: value(node, "create_listener")
          }
        }).then(function (res) {
          toast(res.created.length + " ✓" + (res.errors.length ? " / " + res.errors.length + " ✗" : ""),
            res.created.length ? "ok" : "err");
          if (res.errors.length) { res.errors.forEach(function (e) { toast(e.error, "err"); }); }
          load();
        }).catch(fail);
      }
    });
  };

  root.addEventListener("click", function (event) {
    var node = event.target;
    if (node.dataset.client) {
      showClient(node.dataset.client);
    } else if (node.dataset.activate) {
      api("/api/links/" + node.dataset.activate + "/activate", { method: "POST" })
        .then(function () { toast("ok", "ok"); load(); }).catch(fail);
    } else if (node.dataset.del) {
      confirmAction("#" + node.dataset.del, function () {
        api("/api/links/" + node.dataset.del, { method: "DELETE" }).then(load).catch(fail);
      });
    }
  });

  function showClient(id, host) {
    var query = "/api/links/" + id + "/client" + (host ? "?host=" + encodeURIComponent(host) : "");
    api(query).then(function (res) {
      var html =
        '<div style="text-align:center"><div class="qr">' + res.qr + "</div></div>" +
        '<div class="copy-box" style="margin-top:14px"><code id="cl-link">' + esc(res.link) + "</code>" +
        '<button class="btn-sm" id="cl-copy">' + esc(t("common.copy")) + "</button></div>" +
        '<div class="field" style="margin-top:14px"><label>' + esc(t("lnk.clienthost")) + "</label>" +
        '<input name="host" dir="ltr" value="' + esc(res.host) + '"></div>';
      modal(t("lnk.client"), html, {
        okLabel: t("common.refresh"),
        onSubmit: function (node) {
          var next = value(node, "host");
          showClient(id, next);
        },
        onOpen: function (node) {
          node.querySelector("#cl-copy").onclick = function () { copy(res.link); };
        }
      });
    }).catch(fail);
  }

  load();
};

pages.xray = function (root) {
  function load() {
    api("/api/xray").then(function (res) {
      var cfg = res.settings;
      root.innerHTML =
        '<div class="grid cols-2">' +
          '<div class="card"><h3>' + esc(t("xr.title")) +
            '<span class="right">' + esc(res.version || "—") + "</span></h3>" +
            '<div class="kv"><b>binary</b><span>' + (res.installed ? "✅" : "❌") + " " + esc(res.config_path) + "</span>" +
            "<b>service</b><span>" + badge(res.service.active, res.service.state, res.service.state || "inactive") + "</span></div>" +
            '<div class="actions" style="margin-top:14px">' +
              '<button class="btn-sm" id="xr-install">' + esc(t("xr.install")) + "</button>" +
              '<button class="btn-sm" id="xr-apply">' + esc(t("common.apply")) + "</button>" +
              '<button class="btn-sm" id="xr-restart">' + esc(t("common.restart")) + "</button>" +
              '<button class="btn-sm" id="xr-config">' + esc(t("xr.config")) + "</button>" +
            "</div></div>" +
          '<div class="card"><h3>' + esc(t("xr.ipcheck")) + "</h3>" +
            '<div class="actions">' +
              '<button class="btn-sm" data-ip="direct">' + esc(t("xr.direct")) + "</button>" +
              '<button class="btn-sm" data-ip="http">' + esc(t("xr.viahttp")) + "</button>" +
              '<button class="btn-sm" data-ip="socks">' + esc(t("xr.viasocks")) + "</button>" +
            "</div><pre class='log' id='ip-out' style='margin-top:12px;max-height:150px'>—</pre></div>" +
        "</div>" +
        '<div class="card" style="margin-top:16px"><h3>' + esc(t("nav.settings")) + "</h3>" +
          checkbox(t("xr.enable"), "enabled", cfg.enabled) +
          '<div class="row">' +
            field(t("xr.httpport"), "http_port", { value: cfg.http_port, type: "number", dir: "ltr" }) +
            field(t("xr.socksport"), "socks_port", { value: cfg.socks_port, type: "number", dir: "ltr" }) +
            field(t("xr.listen"), "listen", { value: cfg.listen, dir: "ltr" }) +
          "</div>" +
          '<div class="row">' +
            field(t("xr.auth"), "auth_user", { value: cfg.auth_user, dir: "ltr", hint: t("common.optional") }) +
            field("password", "auth_pass", { value: cfg.auth_pass, dir: "ltr", hint: t("common.optional") }) +
          "</div>" +
          checkbox("SOCKS UDP", "socks_udp", cfg.socks_udp) +
          selectField("log level", "log_level",
            [["none", "none"], ["error", "error"], ["warning", "warning"], ["info", "info"], ["debug", "debug"]],
            cfg.log_level) +
          '<button class="btn-primary" id="xr-save">' + esc(t("common.save")) + "</button></div>";

      $("#xr-install").onclick = function () {
        this.disabled = true; toast("…");
        api("/api/xray/install", { method: "POST", body: {} })
          .then(function (r) { toast("xray " + r.version, "ok"); load(); }).catch(fail);
      };
      $("#xr-apply").onclick = function () {
        api("/api/xray/apply", { method: "POST", body: {} })
          .then(function (r) {
            toast(r.message || "ok", r.config_test && r.config_test.ok ? "ok" : "err");
            if (r.config_test && !r.config_test.ok) {
              modal("xray -test", "<pre class='log'>" + esc(r.config_test.output) + "</pre>", { submit: false });
            }
          }).catch(fail);
      };
      $("#xr-restart").onclick = function () {
        api("/api/service/xray/restart", { method: "POST" })
          .then(function (r) { toast(r.message || "ok", "ok"); load(); }).catch(fail);
      };
      $("#xr-config").onclick = function () {
        api("/api/xray/config").then(function (r) {
          modal(t("xr.config"), "<pre class='log ltr'>" + esc(JSON.stringify(r.config, null, 2)) + "</pre>",
            { submit: false });
        }).catch(fail);
      };
      $("#xr-save").onclick = function () {
        api("/api/settings/xray", {
          method: "PUT",
          body: {
            enabled: value(root, "enabled"),
            http_port: Number(value(root, "http_port")),
            socks_port: Number(value(root, "socks_port")),
            listen: value(root, "listen"),
            auth_user: value(root, "auth_user"),
            auth_pass: value(root, "auth_pass"),
            socks_udp: value(root, "socks_udp"),
            log_level: value(root, "log_level")
          }
        }).then(function () { toast(t("common.save"), "ok"); load(); }).catch(fail);
      };

      $$("[data-ip]", root).forEach(function (button) {
        button.onclick = function () {
          $("#ip-out").textContent = t("common.loading");
          api("/api/tools/ip?via=" + button.dataset.ip)
            .then(function (r) { $("#ip-out").textContent = JSON.stringify(r, null, 2); })
            .catch(function (e) { $("#ip-out").textContent = "❌ " + e.message; });
        };
      });
    }).catch(fail);
  }
  load();
};

pages.scanner = function (root) {
  var pollTimer = null;

  function load() {
    Promise.all([api("/api/scan/list"), api("/api/scan/status"), api("/api/listeners")])
      .then(function (res) {
        var scans = res[0], status = res[1], listeners = res[2].listeners;
        root.innerHTML =
          '<div class="card"><h3>' + esc(t("sc.title")) +
            '<span class="right">' + scans.candidates + " SNI</span></h3>" +
            '<div class="row">' +
              field(t("sc.target"), "target", { value: status.target || "104.18.4.130:443", dir: "ltr" }) +
              field(t("sc.timeout"), "timeout", { value: 6, type: "number" }) +
              field(t("sc.concurrency"), "concurrency", { value: 20, type: "number" }) +
            "</div>" +
            '<div class="actions">' +
              '<button class="btn-primary" id="sc-start">' + esc(t("sc.start")) + "</button>" +
              '<button id="sc-cancel">' + esc(t("sc.cancel")) + "</button>" +
              '<button id="sc-list">' + esc(t("sc.list")) + "</button>" +
            "</div>" +
            '<div id="sc-progress" style="margin-top:16px"></div>' +
          "</div>" +
          '<div class="card" style="margin-top:16px"><h3>' + esc(t("sc.results")) + '</h3><div id="sc-results"></div></div>' +
          '<div class="card" style="margin-top:16px"><h3>' + esc(t("sc.history")) + "</h3>" +
            (scans.scans.length ? '<div class="table-wrap"><table><thead><tr><th>#</th><th>' +
              esc(t("bk.date")) + "</th><th>target</th><th>" + esc(t("common.status")) +
              "</th><th>" + esc(t("sc.passed")) + "</th></tr></thead><tbody>" +
              scans.scans.map(function (s) {
                return "<tr><td>" + s.id + "</td><td>" + esc(stamp(s.ts)) + "</td>" +
                  '<td class="mono ltr">' + esc(s.target) + "</td><td>" + esc(s.status) +
                  "</td><td>" + s.ok_count + " / " + s.total + "</td></tr>";
              }).join("") + "</tbody></table></div>"
              : '<div class="empty">' + esc(t("common.none")) + "</div>") + "</div>";

        $("#sc-start").onclick = function () {
          api("/api/scan/start", {
            method: "POST",
            body: {
              target: value(root, "target"),
              timeout: Number(value(root, "timeout")),
              concurrency: Number(value(root, "concurrency"))
            }
          }).then(function () { poll(); }).catch(fail);
        };
        $("#sc-cancel").onclick = function () {
          api("/api/scan/cancel", { method: "POST" }).then(function () { toast("ok", "ok"); }).catch(fail);
        };
        $("#sc-list").onclick = editList;
        renderStatus(status, listeners);
        if (status.running) { poll(); }
      }).catch(fail);
  }

  function renderStatus(status, listeners) {
    var progressNode = $("#sc-progress"), resultsNode = $("#sc-results");
    if (!progressNode) { return; }
    var percent = status.total ? Math.round(status.done / status.total * 100) : 0;
    progressNode.innerHTML = status.total
      ? '<div class="progress"><i style="width:' + percent + '%"></i></div>' +
        '<div style="margin-top:8px;color:var(--muted);font-size:12px">' +
        (status.running ? esc(t("sc.running")) + " " : "") + status.done + " / " + status.total +
        " — " + status.ok + " " + esc(t("sc.passed")) + "</div>"
      : "";
    if (!resultsNode) { return; }
    if (!status.results.length) {
      resultsNode.innerHTML = '<div class="empty">' + esc(t("common.none")) + "</div>";
      return;
    }
    resultsNode.innerHTML = '<div class="table-wrap"><table><thead><tr><th>SNI</th><th>' +
      esc(t("sc.latency")) + "</th><th>" + esc(t("common.actions")) + "</th></tr></thead><tbody>" +
      status.results.slice(0, 200).map(function (item) {
        return '<tr><td class="mono ltr">' + esc(item.sni) + "</td><td>" + item.ms + " ms</td>" +
          '<td><button class="btn-sm" data-sni="' + esc(item.sni) + '">' + esc(t("sc.applysni")) + "</button></td></tr>";
      }).join("") + "</tbody></table></div>";

    $$("[data-sni]", resultsNode).forEach(function (button) {
      button.onclick = function () {
        var options = listeners.map(function (l) {
          return '<div class="check"><input type="checkbox" name="l' + l.id + '" checked id="ls' + l.id + '">' +
            '<label for="ls' + l.id + '">#' + l.id + " " + esc(l.name || "") + " :" + l.listen_port + "</label></div>";
        }).join("");
        modal(t("sc.applysni") + " — " + button.dataset.sni, options || t("common.none"), {
          onSubmit: function (node) {
            var ids = listeners.filter(function (l) { return value(node, "l" + l.id); })
              .map(function (l) { return l.id; });
            api("/api/scan/apply", { method: "POST", body: { sni: button.dataset.sni, listener_ids: ids } })
              .then(function (r) { toast(r.updated.length + " ✓", "ok"); }).catch(fail);
          }
        });
      };
    });
  }

  function poll() {
    if (pollTimer) { clearInterval(pollTimer); }
    pollTimer = setInterval(function () {
      api("/api/scan/status").then(function (status) {
        api("/api/listeners").then(function (res) { renderStatus(status, res.listeners); });
        if (!status.running) { clearInterval(pollTimer); pollTimer = null; }
      }).catch(function () { clearInterval(pollTimer); pollTimer = null; });
    }, 700);
    state.timers.push(pollTimer);
  }

  function editList() {
    api("/api/scan-list").then(function (res) {
      modal(t("sc.list"),
        '<div class="field"><label>' + esc(res.path) + "</label>" +
        '<textarea name="text" dir="ltr" rows="16">' + esc(res.text) + "</textarea></div>",
        {
          okLabel: t("sc.savelist"),
          onSubmit: function (node) {
            api("/api/scan-list", { method: "PUT", body: { text: node.querySelector('[name="text"]').value } })
              .then(function (r) { toast(r.count + " SNI", "ok"); load(); }).catch(fail);
          }
        });
    }).catch(fail);
  }

  load();
};

pages.logs = function (root) {
  root.innerHTML =
    '<div class="card"><div class="tabs" id="log-tabs">' +
      ["core", "panel", "xray"].map(function (alias, index) {
        return '<div class="tab' + (index === 0 ? " active" : "") + '" data-log="' + alias + '">' + alias + "</div>";
      }).join("") + "</div>" +
    '<div class="row" style="max-width:520px">' +
      field(t("lg.lines"), "lines", { value: 300, type: "number" }) +
    "</div>" +
    '<div class="actions" style="margin-bottom:12px">' +
      '<button class="btn-sm" id="log-refresh">' + esc(t("common.refresh")) + "</button>" +
      '<label class="check" style="margin:0"><input type="checkbox" id="log-auto"> ' + esc(t("lg.auto")) + "</label>" +
    "</div>" +
    '<pre class="log ltr" id="log-body">…</pre></div>';

  var current = "core";
  function load() {
    api("/api/logs/" + current + "?lines=" + (value(root, "lines") || 300))
      .then(function (res) {
        var node = $("#log-body");
        node.textContent = res.text || "—";
        node.scrollTop = node.scrollHeight;
      }).catch(fail);
  }
  $("#log-tabs").addEventListener("click", function (event) {
    if (!event.target.dataset.log) { return; }
    $$(".tab", $("#log-tabs")).forEach(function (tab) { tab.classList.remove("active"); });
    event.target.classList.add("active");
    current = event.target.dataset.log;
    load();
  });
  $("#log-refresh").onclick = load;
  $("#log-auto").onchange = function () {
    if (this.checked) { every(4000, load); } else { clearTimers(); }
  };
  load();
};

pages.backup = function (root) {
  function load() {
    api("/api/backups").then(function (res) {
      root.innerHTML =
        '<div class="card"><h3>' + esc(t("bk.title")) + "</h3>" +
          '<div class="actions">' +
            '<button class="btn-primary btn-sm" id="bk-create">' + esc(t("bk.create")) + "</button>" +
            '<button class="btn-sm" id="bk-tg">' + esc(t("bk.telegram")) + "</button>" +
            '<a class="btn btn-sm" href="' + base() + '/api/export">' + esc(t("bk.export")) + "</a>" +
            '<label class="btn btn-sm">' + esc(t("bk.upload")) +
              '<input type="file" id="bk-file" accept=".gz,.tar.gz" style="display:none"></label>' +
          "</div></div>" +
        '<div class="card" style="margin-top:16px">' +
          (res.backups.length ? '<div class="table-wrap"><table><thead><tr><th>' + esc(t("common.name")) +
            "</th><th>" + esc(t("bk.size")) + "</th><th>" + esc(t("bk.date")) + "</th><th>" +
            esc(t("common.actions")) + "</th></tr></thead><tbody>" +
            res.backups.map(function (item) {
              return '<tr><td class="mono ltr">' + esc(item.name) + "</td><td>" + bytes(item.size) + "</td>" +
                "<td>" + esc(stamp(item.mtime)) + "</td>" +
                '<td><div class="actions">' +
                  '<a class="btn btn-sm" href="' + base() + "/api/backups/" + encodeURIComponent(item.name) + '/download">' +
                    esc(t("common.download")) + "</a>" +
                  '<button class="btn-sm" data-restore="' + esc(item.name) + '">' + esc(t("common.restore")) + "</button>" +
                  '<button class="btn-sm btn-danger" data-del="' + esc(item.name) + '">' + esc(t("common.delete")) + "</button>" +
                "</div></td></tr>";
            }).join("") + "</tbody></table></div>"
            : '<div class="empty">' + esc(t("common.none")) + "</div>") + "</div>";

      $("#bk-create").onclick = function () {
        api("/api/backups", { method: "POST", body: {} })
          .then(function (r) { toast(r.name, "ok"); load(); }).catch(fail);
      };
      $("#bk-tg").onclick = function () {
        api("/api/backups", { method: "POST", body: { telegram: true } })
          .then(function (r) { toast(r.name + " → telegram", "ok"); load(); }).catch(fail);
      };
      $("#bk-file").onchange = function () {
        var file = this.files[0];
        if (!file) { return; }
        confirmAction(file.name, function () {
          file.arrayBuffer().then(function (buffer) {
            return api("/api/backups/upload", { method: "POST", body: buffer, raw: true });
          }).then(function (r) { toast((r.restored || []).join(", "), "ok"); load(); }).catch(fail);
        });
      };
      root.addEventListener("click", function (event) {
        var node = event.target;
        if (node.dataset.restore) {
          confirmAction(node.dataset.restore, function () {
            api("/api/backups/" + encodeURIComponent(node.dataset.restore) + "/restore", { method: "POST" })
              .then(function (r) { toast((r.restored || []).join(", "), "ok"); }).catch(fail);
          });
        } else if (node.dataset.del) {
          confirmAction(node.dataset.del, function () {
            api("/api/backups/" + encodeURIComponent(node.dataset.del), { method: "DELETE" })
              .then(load).catch(fail);
          });
        }
      });
    }).catch(fail);
  }
  load();
};

pages.settings = function (root) {
  function load() {
    Promise.all([api("/api/settings"), api("/api/cert"), api("/api/system"), api("/api/core/update")])
      .then(function (res) {
        var s = res[0].settings, cert = res[1], sys = res[2], upd = res[3];
        root.innerHTML =
          section("st.panel", "panel",
            '<div class="row">' +
              field(t("common.host"), "panel.host", { value: s.panel.host, dir: "ltr" }) +
              field(t("common.port"), "panel.port", { value: s.panel.port, type: "number", dir: "ltr" }) +
              field("base path", "panel.base_path", { value: s.panel.base_path, dir: "ltr" }) +
            "</div>" +
            '<div class="row">' +
              selectField(t("nav.language"), "panel.language", [["fa", "فارسی"], ["en", "English"]], s.panel.language) +
              selectField(t("nav.theme"), "panel.theme", [["dark", "dark"], ["light", "light"]], s.panel.theme) +
              field("session ttl (min)", "panel.session_ttl_min", { value: s.panel.session_ttl_min, type: "number" }) +
            "</div>" +
            '<div class="row">' +
              field("login max attempts", "panel.login_max_attempts", { value: s.panel.login_max_attempts, type: "number" }) +
              field("ban minutes", "panel.login_ban_minutes", { value: s.panel.login_ban_minutes, type: "number" }) +
            "</div>" +
            '<div class="field"><label>IP allowlist (' + esc(t("common.optional")) + ')</label>' +
            '<textarea name="panel.ip_allowlist" dir="ltr" rows="3">' +
              esc((s.panel.ip_allowlist || []).join("\n")) + "</textarea></div>" +
            '<p style="color:var(--warn);font-size:12px">' + esc(t("st.restartneeded")) + "</p>") +

          section("st.core", "core",
            '<div class="kv" style="margin-bottom:14px"><b>version</b><span>' + esc(upd.current || "—") +
              (upd.update_available ? ' → <span class="badge warn">' + esc(upd.latest) + "</span>" : "") + "</span>" +
              "<b>arch</b><span>" + esc(sys.arch) + (sys.musl ? " (musl)" : "") + "</span>" +
              "<b>binary</b><span class='mono ltr'>" + esc(sys.paths.core_bin) + "</span></div>" +
            '<div class="actions" style="margin-bottom:14px">' +
              '<button class="btn-sm" id="core-install">' + esc(t("common.install")) + " / " + esc(t("common.update")) + "</button>" +
            "</div>" +
            '<div class="row">' +
              field("buffer_size (KiB)", "core.buffer_size", { value: s.core.buffer_size, type: "number" }) +
              field("graceful_shutdown_sec", "core.graceful_shutdown_sec", { value: s.core.graceful_shutdown_sec, type: "number" }) +
              field("idle_timeout", "core.idle_timeout", { value: s.core.idle_timeout === null ? "" : s.core.idle_timeout, hint: t("common.optional") }) +
              field("auto refresh IP (h)", "core.auto_refresh_ip_hours", { value: s.core.auto_refresh_ip_hours, type: "number" }) +
            "</div>" +
            selectField("log level", "core.log_level",
              [["error", "error"], ["warn", "warn"], ["info", "info"], ["debug", "debug"]], s.core.log_level)) +

          section("st.watchdog", "watchdog",
            checkbox(t("common.enabled"), "watchdog.enabled", s.watchdog.enabled) +
            '<div class="row">' +
              field("interval (s)", "watchdog.interval_sec", { value: s.watchdog.interval_sec, type: "number" }) +
              field("tcp timeout (s)", "watchdog.tcp_timeout_sec", { value: s.watchdog.tcp_timeout_sec, type: "number" }) +
              field("failures before restart", "watchdog.failures_before_restart", { value: s.watchdog.failures_before_restart, type: "number" }) +
            "</div>" +
            checkbox("restart core", "watchdog.restart_core", s.watchdog.restart_core)) +

          section("st.stats", "stats",
            checkbox(t("common.enabled"), "stats.enabled", s.stats.enabled) +
            '<div class="row">' +
              field("sample interval (s)", "stats.sample_interval_sec", { value: s.stats.sample_interval_sec, type: "number" }) +
              field("retention (h)", "stats.retention_hours", { value: s.stats.retention_hours, type: "number" }) +
            "</div>" +
            checkbox("iptables byte accounting" + (sys.accounting_available ? "" : " (unavailable)"),
              "stats.count_traffic", s.stats.count_traffic)) +

          section("st.telegram", "telegram",
            checkbox(t("common.enabled"), "telegram.enabled", s.telegram.enabled) +
            '<div class="row">' +
              field("bot token", "telegram.bot_token", { value: s.telegram.bot_token, dir: "ltr" }) +
              field("chat id", "telegram.chat_id", { value: s.telegram.chat_id, dir: "ltr" }) +
            "</div>" +
            checkbox("notify service down", "telegram.notify_service_down", s.telegram.notify_service_down) +
            checkbox("notify login", "telegram.notify_login", s.telegram.notify_login) +
            checkbox("notify backup", "telegram.notify_backup", s.telegram.notify_backup) +
            '<button class="btn-sm" id="tg-test" type="button">' + esc(t("st.testtg")) + "</button>") +

          section("st.backup", "backup",
            checkbox(t("common.enabled"), "backup.auto_enabled", s.backup.auto_enabled) +
            '<div class="row">' +
              field("interval (h)", "backup.interval_hours", { value: s.backup.interval_hours, type: "number" }) +
              field("keep", "backup.keep", { value: s.backup.keep, type: "number" }) +
            "</div>") +

          section("st.network", "network",
            field("github mirror", "network.github_mirror",
              { value: s.network.github_mirror, dir: "ltr", hint: "https://ghproxy.net/" }) +
            field("timeout (s)", "network.connect_timeout_sec", { value: s.network.connect_timeout_sec, type: "number" })) +

          '<div class="card" style="margin-top:16px"><h3>' + esc(t("st.tls")) + "</h3>" +
            '<div class="kv" style="margin-bottom:14px"><b>TLS</b><span>' +
              badge(cert.tls.enabled, "on", "off") + "</span>" +
              (cert.cert.exists ? "<b>subject</b><span class='mono ltr'>" + esc(cert.cert.subject || "") + "</span>" +
                "<b>expires</b><span>" + esc(cert.cert.not_after || "") +
                (cert.cert.days_left !== undefined ? " (" + cert.cert.days_left + "d)" : "") + "</span>" : "") +
            "</div>" +
            '<div class="row">' +
              field("domain / CN", "cert.domain", { dir: "ltr" }) +
              field("email (ACME)", "cert.email", { dir: "ltr" }) +
            "</div>" +
            '<div class="actions">' +
              '<button class="btn-sm" id="cert-self">' + esc(t("st.selfsigned")) + "</button>" +
              '<button class="btn-sm" id="cert-acme">' + esc(t("st.acme")) + "</button>" +
              '<button class="btn-sm btn-danger" id="cert-off">' + esc(t("st.disabletls")) + "</button>" +
            "</div></div>";

        bindSave();
      }).catch(fail);
  }

  function section(titleKey, name, body) {
    return '<div class="card" style="margin-top:16px"><h3>' + esc(t(titleKey)) + "</h3>" + body +
      '<button class="btn-primary" data-save="' + name + '" style="margin-top:6px">' +
      esc(t("common.save")) + "</button></div>";
  }

  function collect(name) {
    var out = {};
    $$('[name^="' + name + '."]', root).forEach(function (node) {
      var key = node.name.slice(name.length + 1);
      if (node.type === "checkbox") { out[key] = node.checked; }
      else if (node.tagName === "TEXTAREA") {
        out[key] = node.value.split("\n").map(function (x) { return x.trim(); })
          .filter(function (x) { return x; });
      } else if (node.type === "number") {
        out[key] = node.value === "" ? null : Number(node.value);
      } else { out[key] = node.value.trim(); }
    });
    return out;
  }

  function bindSave() {
    $$("[data-save]", root).forEach(function (button) {
      button.onclick = function () {
        var name = button.dataset.save;
        api("/api/settings/" + name, { method: "PUT", body: collect(name) })
          .then(function (res) {
            toast(t("common.save"), "ok");
            if (res.followups && res.followups.restart_required) { toast(t("st.restartneeded"), "err"); }
            if (name === "panel") {
              var lang = collect("panel").language;
              if (lang && lang !== state.lang) { setLang(lang); }
            }
          }).catch(fail);
      };
    });
    $("#core-install").onclick = function () {
      this.disabled = true; toast("…");
      api("/api/core/install", { method: "POST", body: {} })
        .then(function (r) { toast("core " + r.version, "ok"); load(); }).catch(fail);
    };
    $("#tg-test").onclick = function () {
      api("/api/telegram/test", { method: "POST", body: {} })
        .then(function () { toast("✓", "ok"); }).catch(fail);
    };
    $("#cert-self").onclick = function () {
      api("/api/cert/self-signed", { method: "POST", body: { common_name: value(root, "cert.domain") } })
        .then(function () { toast(t("st.restartneeded"), "ok"); load(); }).catch(fail);
    };
    $("#cert-acme").onclick = function () {
      this.disabled = true; toast("…");
      api("/api/cert/acme", {
        method: "POST",
        body: { domain: value(root, "cert.domain"), email: value(root, "cert.email") }
      }).then(function () { toast(t("st.restartneeded"), "ok"); load(); })
        .catch(fail).finally(function () { $("#cert-acme").disabled = false; });
    };
    $("#cert-off").onclick = function () {
      api("/api/cert/disable", { method: "POST", body: {} })
        .then(function () { toast(t("st.restartneeded"), "ok"); load(); }).catch(fail);
    };
  }

  load();
};

pages.users = function (root) {
  $("#page-tools").innerHTML = '<button class="btn-primary btn-sm" id="add-user">+ ' + esc(t("us.add")) + "</button>";

  function load() {
    api("/api/users").then(function (res) {
      root.innerHTML =
        '<div class="card"><div class="table-wrap"><table><thead><tr><th>#</th><th>' +
          esc(t("login.username")) + "</th><th>role</th><th>2FA</th><th>" + esc(t("us.lastlogin")) +
          "</th><th>" + esc(t("common.actions")) + "</th></tr></thead><tbody>" +
          res.users.map(function (user) {
            return "<tr><td>" + user.id + "</td><td>" + esc(user.username) + "</td>" +
              "<td>" + esc(user.role) + "</td><td>" + (user.totp ? "✅" : "—") + "</td>" +
              "<td>" + esc(stamp(user.last_login)) + (user.last_ip ? "<br><small style='color:var(--muted)'>" + esc(user.last_ip) + "</small>" : "") + "</td>" +
              '<td><div class="actions">' +
                (user.id === (state.user || {}).id ? "" :
                  '<button class="btn-sm btn-danger" data-del="' + user.id + '">' + esc(t("common.delete")) + "</button>") +
              "</div></td></tr>";
          }).join("") + "</tbody></table></div></div>" +
        '<div class="grid cols-2" style="margin-top:16px">' +
          '<div class="card"><h3>' + esc(t("us.changepw")) + "</h3>" +
            field(t("us.current"), "current", { type: "password" }) +
            field(t("us.new"), "new", { type: "password" }) +
            '<button class="btn-primary" id="pw-save">' + esc(t("common.save")) + "</button></div>" +
          '<div class="card"><h3>' + esc(t("us.2fa")) + "</h3>" +
            "<p style='color:var(--muted)'>" +
            ((state.user || {}).totp ? "✅ " + esc(t("common.enabled")) : "—") + "</p>" +
            '<div class="actions">' +
              '<button class="btn-sm" id="tfa-on">' + esc(t("us.enable2fa")) + "</button>" +
              '<button class="btn-sm btn-danger" id="tfa-off">' + esc(t("us.disable2fa")) + "</button>" +
            "</div></div>" +
        "</div>";

      $("#pw-save").onclick = function () {
        api("/api/password", { method: "POST", body: { current: value(root, "current"), new: value(root, "new") } })
          .then(function (r) { toast(r.message, "ok"); setTimeout(logout, 1200); }).catch(fail);
      };
      $("#tfa-on").onclick = function () {
        api("/api/2fa/setup", { method: "POST", body: {} }).then(function (r) {
          modal(t("us.2fa"),
            "<p>" + esc(t("us.scanqr")) + '</p><div style="text-align:center"><div class="qr">' + r.qr + "</div></div>" +
            '<div class="copy-box" style="margin:12px 0"><code>' + esc(r.secret) + "</code></div>" +
            field(t("login.totp"), "code", { placeholder: "000000" }),
            {
              onSubmit: function (node) {
                api("/api/2fa/enable", { method: "POST", body: { secret: r.secret, code: value(node, "code") } })
                  .then(function () { toast("✓", "ok"); refreshSession().then(load); }).catch(fail);
              }
            });
        }).catch(fail);
      };
      $("#tfa-off").onclick = function () {
        modal(t("us.disable2fa"), field(t("login.password"), "password", { type: "password" }), {
          onSubmit: function (node) {
            api("/api/2fa/disable", { method: "POST", body: { password: value(node, "password") } })
              .then(function () { toast("✓", "ok"); refreshSession().then(load); }).catch(fail);
          }
        });
      };
      root.addEventListener("click", function (event) {
        if (!event.target.dataset.del) { return; }
        confirmAction("#" + event.target.dataset.del, function () {
          api("/api/users/" + event.target.dataset.del, { method: "DELETE" }).then(load).catch(fail);
        });
      });
    }).catch(fail);
  }

  $("#add-user").onclick = function () {
    modal(t("us.add"),
      field(t("login.username"), "username") + field(t("us.password"), "password", { type: "password" }),
      {
        onSubmit: function (node) {
          api("/api/users", { method: "POST", body: { username: value(node, "username"), password: value(node, "password") } })
            .then(function () { toast("✓", "ok"); load(); }).catch(fail);
        }
      });
  };

  load();
};

// ---------------------------------------------------------------- shell
function applyLangDom() {
  document.documentElement.lang = state.lang;
  document.documentElement.dir = state.lang === "fa" ? "rtl" : "ltr";
  $$("[data-i18n]").forEach(function (node) { node.textContent = t(node.dataset.i18n); });
}

function setLang(lang) {
  state.lang = lang === "en" ? "en" : "fa";
  localStorage.setItem("lang", state.lang);
  applyLangDom();
  if (state.user) { go(state.page); }
}

function setTheme(theme) {
  state.theme = theme === "light" ? "light" : "dark";
  localStorage.setItem("theme", state.theme);
  document.documentElement.dataset.theme = state.theme;
}

function go(page) {
  if (!pages[page]) { page = "dashboard"; }
  state.page = page;
  clearTimers();
  $$(".nav-item[data-page]").forEach(function (node) {
    node.classList.toggle("active", node.dataset.page === page);
  });
  var title = $("#page-title");
  title.dataset.i18n = "nav." + page;
  title.textContent = t("nav." + page);
  $("#page-tools").innerHTML = "";
  $("#sidebar").classList.remove("open");
  var root = $("#page");
  root.innerHTML = '<div class="empty">' + esc(t("common.loading")) + "</div>";
  window.location.hash = page;
  pages[page](root);
}

function showApp(user) {
  state.user = user;
  $("#login").style.display = "none";
  $("#app").classList.add("visible");
  go((window.location.hash || "#dashboard").slice(1));
}

function showLogin() {
  clearTimers();
  state.user = null;
  $("#app").classList.remove("visible");
  $("#login").style.display = "grid";
}

function logout() {
  api("/api/logout", { method: "POST" }).finally(showLogin);
}

function refreshSession() {
  return api("/api/session").then(function (res) {
    $("#brand-version").textContent = "v" + res.version;
    if (res.authenticated) { state.user = res.user; }
    return res;
  });
}

function boot() {
  setTheme(state.theme);
  applyLangDom();

  $("#login-form").addEventListener("submit", function (event) {
    event.preventDefault();
    var button = event.target.querySelector("button[type=submit]");
    button.disabled = true;
    api("/api/login", {
      method: "POST",
      body: {
        username: $("#lg-user").value.trim(),
        password: $("#lg-pass").value,
        totp: $("#lg-totp").value.trim()
      }
    }).then(function (res) {
      $("#lg-pass").value = ""; $("#lg-totp").value = "";
      showApp(res.user);
    }).catch(function (error) {
      if (error.key === "totp_required" || error.key === "totp_invalid") {
        $("#lg-totp-field").style.display = "block";
        $("#lg-totp").focus();
      }
      fail(error);
    }).finally(function () { button.disabled = false; });
  });

  $("#lg-lang").onclick = function () { setLang(state.lang === "fa" ? "en" : "fa"); };
  $("#nav-lang").onclick = function () { setLang(state.lang === "fa" ? "en" : "fa"); };
  $("#nav-theme").onclick = function () { setTheme(state.theme === "dark" ? "light" : "dark"); };
  $("#nav-logout").onclick = logout;
  $("#menu-toggle").onclick = function () { $("#sidebar").classList.toggle("open"); };
  $$(".nav-item[data-page]").forEach(function (node) {
    node.onclick = function () { go(node.dataset.page); };
  });
  window.addEventListener("hashchange", function () {
    var page = (window.location.hash || "#dashboard").slice(1);
    if (state.user && page !== state.page) { go(page); }
  });

  refreshSession().then(function (res) {
    if (!localStorage.getItem("lang") && res.language) { setLang(res.language); }
    if (!localStorage.getItem("theme") && res.theme) { setTheme(res.theme); }
    if (res.authenticated) { showApp(res.user); } else { showLogin(); }
  }).catch(function () { showLogin(); });
}

document.addEventListener("DOMContentLoaded", boot);
})();
