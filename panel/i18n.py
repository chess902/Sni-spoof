"""Server-side strings. UI labels live in static/app.js; these are messages
returned by the API (errors, notifications, Telegram alerts)."""

LANGS = ("fa", "en")
DEFAULT_LANG = "fa"

STRINGS = {
    "bad_credentials": {
        "fa": "نام کاربری یا رمز عبور اشتباه است",
        "en": "Invalid username or password",
    },
    "totp_required": {"fa": "کد دو مرحله‌ای لازم است", "en": "Two-factor code required"},
    "totp_invalid": {"fa": "کد دو مرحله‌ای نامعتبر است", "en": "Invalid two-factor code"},
    "too_many_attempts": {
        "fa": "تلاش‌های ناموفق زیاد؛ کمی بعد دوباره امتحان کنید",
        "en": "Too many failed attempts; try again later",
    },
    "unauthorized": {"fa": "دسترسی ندارید", "en": "Unauthorized"},
    "forbidden_ip": {"fa": "آی‌پی شما مجاز نیست", "en": "Your IP is not allowed"},
    "not_found": {"fa": "یافت نشد", "en": "Not found"},
    "invalid_input": {"fa": "ورودی نامعتبر است", "en": "Invalid input"},
    "port_in_use": {"fa": "این پورت قبلاً استفاده شده است", "en": "Port already in use"},
    "core_missing": {
        "fa": "هستهٔ sni-spoof-rs نصب نیست",
        "en": "sni-spoof-rs core is not installed",
    },
    "xray_missing": {"fa": "Xray نصب نیست", "en": "Xray is not installed"},
    "saved": {"fa": "ذخیره شد", "en": "Saved"},
    "service_down": {"fa": "سرویس %s متوقف شده است", "en": "Service %s is down"},
    "service_restarted": {
        "fa": "سرویس %s به‌صورت خودکار ری‌استارت شد",
        "en": "Service %s was restarted automatically",
    },
    "login_success": {
        "fa": "ورود موفق به پنل از %s",
        "en": "Successful panel login from %s",
    },
    "backup_created": {"fa": "بکاپ ساخته شد: %s", "en": "Backup created: %s"},
}


def t(key, lang=DEFAULT_LANG, *args):
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get("en") or key
    if args:
        try:
            return text % args
        except TypeError:
            return text
    return text
