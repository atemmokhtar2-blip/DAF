# lsh/templates/sw.py
# ============================================================
# Service Worker v6 — Multi-Channel
# ============================================================

SW_FALLBACK = r"""
// ═══════════════════════════════════════════════════════════
// LSH v6.0 — Service Worker
// Multi-Channel + Ack + Dead Letter
// ═══════════════════════════════════════════════════════════

const VERSION = '6.0.0';
const CACHE_NAME = 'lsh-v6';

// ★ قنوات الاتصال
const CHANNELS = {
  WS: 'ws',
  SSE: 'sse',
  LONG_POLL: 'long_poll',
  HTTP: 'http',
  BEACON: 'beacon'
};

const PING_INTERVAL = 3000;
const HEARTBEAT_INTERVAL = 10000;
const RECONNECT_INITIAL = 1000;
const RECONNECT_MAX = 60000;
const MAX_PENDING = 1000;
const HEALTH_CHECK_INTERVAL = 30000;

let sessionData = null;
let pingTimer = null;
let heartbeatTimer = null;
let healthTimer = null;
let isOnline = true;
let reconnectAttempts = 0;
let reconnectDelay = RECONNECT_INITIAL;
let lastPongTime = Date.now();
let swStartTime = Date.now();
let activeChannel = 'http';
let pendingCommands = new Map();

// ═══════════════════════════════════════════════════════════
// [1] Install / Activate
// ═══════════════════════════════════════════════════════════
self.addEventListener('install', (event) => {
  console.log('[SW] Installing v' + VERSION);
  self.skipWaiting();
});

self.addEventListener('activate', async (event) => {
  console.log('[SW] Activated v' + VERSION);
  event.waitUntil(
    self.clients.claim().then(async () => {
      const saved = await loadSession();
      if (saved && saved.session_id) {
        sessionData = saved;
        startAllLoops();
        await flushPendingQueue();
      }
    })
  );
});

// ═══════════════════════════════════════════════════════════
// [2] Messages
// ═══════════════════════════════════════════════════════════
self.addEventListener('message', (event) => {
  const data = event.data || {};

  if (data.type === 'init') {
    sessionData = {
      session_id: data.session_id,
      chat_id: data.chat_id,
      http_url: data.http_url,
      ws_url: data.ws_url,
      started_at: Date.now(),
      last_page_seen: Date.now(),
    };
    saveSession();
    startAllLoops();
    flushPendingQueue();
  }

  if (data.type === 'stop') {
    stopAllLoops();
  }

  if (data.type === 'keepalive') {
    if (sessionData) {
      sessionData.last_page_seen = Date.now();
      saveSession();
    }
  }

  if (data.type === 'get_status') {
    if (event.source && event.source.postMessage) {
      event.source.postMessage({
        type: 'status',
        data: {
          version: VERSION,
          isOnline: isOnline,
          channel: activeChannel,
          reconnectAttempts: reconnectAttempts,
          pendingQueue: pendingCommands.size,
          uptime: sessionData ? Date.now() - sessionData.started_at : 0,
          swUptime: Date.now() - swStartTime,
          lastPong: lastPongTime,
        }
      });
    }
  }

  if (data.type === 'force_reconnect') {
    reconnectAttempts = 0;
    reconnectDelay = RECONNECT_INITIAL;
    doPing();
  }

  // ★ Ack من الصفحة
  if (data.type === 'cmd_ack') {
    const cmdId = data.cmd_id;
    if (cmdId && pendingCommands.has(cmdId)) {
      pendingCommands.delete(cmdId);
    }
  }
});

// ═══════════════════════════════════════════════════════════
// [3] IndexedDB
// ═══════════════════════════════════════════════════════════
let db = null;

function openDB() {
  return new Promise((resolve) => {
    if (db) return resolve(db);
    try {
      const req = indexedDB.open('lsh_v6_sw_db', 1);
      req.onupgradeneeded = (e) => {
        const database = e.target.result;
        if (!database.objectStoreNames.contains('session')) {
          database.createObjectStore('session');
        }
        if (!database.objectStoreNames.contains('pending')) {
          database.createObjectStore('pending', { autoIncrement: true });
        }
        if (!database.objectStoreNames.contains('commands')) {
          database.createObjectStore('commands');
        }
      };
      req.onsuccess = (e) => { db = e.target.result; resolve(db); };
      req.onerror = () => resolve(null);
    } catch(e) { resolve(null); }
  });
}

async function saveSession() {
  const database = await openDB();
  if (!database || !sessionData) return;
  try {
    const tx = database.transaction('session', 'readwrite');
    tx.objectStore('session').put(sessionData, 'current');
  } catch(e) {}
}

async function loadSession() {
  const database = await openDB();
  if (!database) return null;
  return new Promise((resolve) => {
    try {
      const tx = database.transaction('session', 'readonly');
      const req = tx.objectStore('session').get('current');
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch(e) { resolve(null); }
  });
}

async function addPending(item) {
  const database = await openDB();
  if (!database) return;
  try {
    const tx = database.transaction('pending', 'readwrite');
    tx.objectStore('pending').add({ ...item, ts: Date.now() });
  } catch(e) {}
}

async function getAllPending() {
  const database = await openDB();
  if (!database) return [];
  return new Promise((resolve) => {
    try {
      const tx = database.transaction('pending', 'readonly');
      const req = tx.objectStore('pending').getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => resolve([]);
    } catch(e) { resolve([]); }
  });
}

async function clearPending() {
  const database = await openDB();
  if (!database) return;
  try {
    const tx = database.transaction('pending', 'readwrite');
    tx.objectStore('pending').clear();
  } catch(e) {}
}

// ═══════════════════════════════════════════════════════════
// [4] Loops
// ═══════════════════════════════════════════════════════════
function startAllLoops() {
  startPing();
  startHeartbeat();
  startHealthCheck();
}

function stopAllLoops() {
  if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
  if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
  if (healthTimer) { clearInterval(healthTimer); healthTimer = null; }
  sessionData = null;
}

// ═══════════════════════════════════════════════════════════
// [5] Ping Loop
// ═══════════════════════════════════════════════════════════
function startPing() {
  if (pingTimer) clearInterval(pingTimer);
  pingTimer = setInterval(doPing, PING_INTERVAL);
  setTimeout(doPing, 100);
}

async function doPing() {
  if (!sessionData) {
    sessionData = await loadSession();
    if (!sessionData) return;
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    const resp = await fetch(sessionData.http_url + '/lsh_msg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionData.session_id,
        chat_id: sessionData.chat_id,
        type: 'sw_ping',
        ts: Date.now()
      }),
      signal: controller.signal
    });

    clearTimeout(timeout);

    if (!resp.ok) {
      handlePingFail();
      return;
    }

    isOnline = true;
    lastPongTime = Date.now();
    reconnectAttempts = 0;
    reconnectDelay = RECONNECT_INITIAL;

    const data = await resp.json();
    const commands = data.commands || [];

    if (commands.length > 0) {
      const clients = await self.clients.matchAll({ includeUncontrolled: true });

      if (clients.length > 0) {
        clients.forEach(client => {
          client.postMessage({ type: 'commands', commands });
        });
      } else {
        tryOpenClient(commands);
      }
    }
  } catch (e) {
    handlePingFail();
  }
}

function handlePingFail() {
  isOnline = false;
  reconnectAttempts++;
  // ★ Exponential backoff with jitter
  const base = RECONNECT_INITIAL * Math.pow(1.5, Math.min(reconnectAttempts, 10));
  const jitter = Math.random() * 0.3 * base;
  reconnectDelay = Math.min(base + jitter, RECONNECT_MAX);
}

async function tryOpenClient(commands) {
  try {
    const client = await self.clients.openWindow(
      '/lsh?s=' + sessionData.session_id + '&id=' + sessionData.chat_id
    );
    if (client) {
      setTimeout(() => {
        try { client.postMessage({ type: 'commands', commands }); } catch(e) {}
      }, 2000);
    }
  } catch(e) {}
}

// ═══════════════════════════════════════════════════════════
// [6] Heartbeat
// ═══════════════════════════════════════════════════════════
function startHeartbeat() {
  if (heartbeatTimer) clearInterval(heartbeatTimer);
  heartbeatTimer = setInterval(async () => {
    if (!sessionData) return;
    if (!isOnline && reconnectAttempts > 0) {
      await doPing();
    }
    await saveSession();
  }, HEARTBEAT_INTERVAL);
}

// ═══════════════════════════════════════════════════════════
// [7] Health Check
// ═══════════════════════════════════════════════════════════
function startHealthCheck() {
  if (healthTimer) clearInterval(healthTimer);
  healthTimer = setInterval(async () => {
    if (!sessionData) return;
    if (Date.now() - lastPongTime > 60000) {
      reconnectAttempts = 0;
      await doPing();
    }
  }, HEALTH_CHECK_INTERVAL);
}

// ═══════════════════════════════════════════════════════════
// [8] Flush Pending
// ═══════════════════════════════════════════════════════════
async function flushPendingQueue() {
  const items = await getAllPending();
  if (items.length === 0) return;

  let sent = 0;
  for (const item of items) {
    try {
      const resp = await fetch(sessionData.http_url + '/lsh_msg', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(item)
      });
      if (resp.ok) sent++;
    } catch (e) {}
  }

  if (sent === items.length) {
    await clearPending();
  }
}

// ═══════════════════════════════════════════════════════════
// [9] Background Sync
// ═══════════════════════════════════════════════════════════
self.addEventListener('sync', (event) => {
  if (event.tag === 'lsh-ping') event.waitUntil(doPing());
  if (event.tag === 'lsh-flush') event.waitUntil(flushPendingQueue());
});

// ═══════════════════════════════════════════════════════════
// [10] Push
// ═══════════════════════════════════════════════════════════
self.addEventListener('push', (event) => {
  event.waitUntil(doPing());
});

// ═══════════════════════════════════════════════════════════
// [11] Periodic Sync
// ═══════════════════════════════════════════════════════════
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'lsh-periodic') event.waitUntil(doPing());
});

// ═══════════════════════════════════════════════════════════
// [12] Fetch
// ═══════════════════════════════════════════════════════════
self.addEventListener('fetch', (event) => {
  const url = event.request.url;

  if (url.includes('/sw.js') || url.includes('/manifest.json')) {
    event.respondWith(fetch(event.request).catch(() => new Response('', { status: 503 })));
    return;
  }

  event.respondWith(
    fetch(event.request).catch(async (err) => {
      if (event.request.method === 'POST' && sessionData) {
        try {
          const clone = event.request.clone();
          const body = await clone.text();
          await addPending({ url, method: 'POST', body });
        } catch(e) {}
      }
      return new Response(
        JSON.stringify({ error: 'offline', queued: true }),
        { status: 503, headers: { 'Content-Type': 'application/json' } }
      );
    })
  );
});

// ═══════════════════════════════════════════════════════════
// [13] Self Monitor
// ═══════════════════════════════════════════════════════════
setInterval(() => {
  if (Date.now() - swStartTime > 1800000) {
    swStartTime = Date.now();
    startAllLoops();
  }
}, 60000);

self.addEventListener('unhandledrejection', (e) => e.preventDefault());
self.addEventListener('error', (e) => console.log('[SW] Error:', e.message));

console.log('[SW] v' + VERSION + ' loaded');
"""
