# lsh/commands.py
# ============================================================
# نظام الأوامر v6 — Redis Streams + Ack + Dead Letter
# ============================================================

import json
import time
import uuid

from .config import (
    redis_client, streams_available, LSH_CONFIG,
    ws_connections, ws_lock, sse_connections, sse_lock,
)

from logging_config import get_logger

logger = get_logger("lsh.commands")


# ============================================================
# Push Command — Multi-Channel Dispatch
# ============================================================
def push_command(session_id, command_dict):
    """
    ★ إرسال أمر — 3 قنوات متوازية:
    1) WebSocket (فوري)
    2) SSE (فوري)
    3) Redis Streams/List (للـ polling)
    """
    if not redis_client:
        logger.error("PUSH FAIL: no Redis")
        return False

    try:
        # ★ تحضير الأمر
        cmd_id = f"cmd_{uuid.uuid4().hex[:12]}"
        cmd = dict(command_dict)
        cmd["_id"] = cmd_id
        cmd["_sent_at"] = time.time()
        cmd["_session_id"] = session_id

        payload = json.dumps(cmd)

        # ★ إرسال عبر WebSocket إن وُجد
        ws_sent = _send_via_ws(session_id, cmd)

        # ★ إرسال عبر SSE إن وُجد
        sse_sent = _send_via_sse(session_id, cmd)

        # ★ حفظ في Redis (مصدر الحقيقة)
        if streams_available:
            _save_to_stream(session_id, cmd)
        else:
            _save_to_list(session_id, payload)

        # ★ إحصائيات
        _increment_counter(session_id, "commands_sent")

        channel_info = f"ws={ws_sent} sse={sse_sent}"
        logger.info(
            f"PUSH >> {session_id[:8]} | {cmd.get('action')} | "
            f"{channel_info} | id={cmd_id[:12]}"
        )
        return True

    except Exception as e:
        logger.exception(f"PUSH ERROR: {e}")
        return False


# ============================================================
# WebSocket Dispatch
# ============================================================
def _send_via_ws(session_id, cmd):
    """إرسال عبر WebSocket"""
    try:
        with ws_lock:
            ws = ws_connections.get(session_id)

        if not ws:
            return False

        # ★ لو WS من نوع قائمة انتظار
        if isinstance(ws, list):
            ws.append(cmd)
            return True

        # ★ محاولة الإرسال المباشر
        if hasattr(ws, "send"):
            ws.send(json.dumps(cmd))
            return True

        return False

    except Exception as e:
        logger.warning(f"WS send error: {e}")
        return False


# ============================================================
# SSE Dispatch
# ============================================================
def _send_via_sse(session_id, cmd):
    """إرسال عبر SSE"""
    try:
        with sse_lock:
            queue = sse_connections.get(session_id)

        if not queue:
            return False

        # ★ Queue من نوع deque/list
        if hasattr(queue, "append"):
            queue.append(cmd)
            return True

        return False

    except Exception as e:
        logger.warning(f"SSE send error: {e}")
        return False


# ============================================================
# Redis Streams Save
# ============================================================
def _save_to_stream(session_id, cmd):
    """حفظ الأمر في Redis Stream"""
    try:
        stream_key = f"lsh_stream:{session_id}"

        fields = {
            "id": cmd["_id"],
            "action": cmd.get("action", ""),
            "payload": json.dumps(cmd.get("payload", {})),
            "ts": str(cmd["_sent_at"]),
            "data": json.dumps(cmd),
        }

        redis_client.xadd(
            stream_key,
            fields,
            maxlen=LSH_CONFIG["stream_maxlen"],
            approximate=True,
        )
        redis_client.expire(stream_key, LSH_CONFIG["cmd_ttl"])

        # ★ إضافة للقائمة (للتوافق)
        redis_client.lpush(f"lsh_cmd:{session_id}", json.dumps(cmd))
        redis_client.expire(
            f"lsh_cmd:{session_id}",
            LSH_CONFIG["cmd_ttl"]
        )
        redis_client.ltrim(
            f"lsh_cmd:{session_id}",
            0,
            LSH_CONFIG["cmd_max_pending"] - 1
        )

    except Exception as e:
        logger.warning(f"stream save error: {e} - falling back to list")
        _save_to_list(session_id, json.dumps(cmd))


# ============================================================
# List Fallback
# ============================================================
def _save_to_list(session_id, payload):
    """حفظ الأمر في List"""
    try:
        key = f"lsh_cmd:{session_id}"
        pipe = redis_client.pipeline()
        pipe.lpush(key, payload)
        pipe.expire(key, LSH_CONFIG["cmd_ttl"])
        pipe.ltrim(key, 0, LSH_CONFIG["cmd_max_pending"] - 1)
        pipe.execute()
    except Exception as e:
        logger.warning(f"list save error: {e}")


# ============================================================
# Pop Commands (Victim Side)
# ============================================================
def pop_commands(session_id, max_count=5):
    """★ سحب الأوامر — List أو Stream"""
    if not redis_client:
        return []

    commands = []
    try:
        key = f"lsh_cmd:{session_id}"

        # ★ نستخدم pipeline للسحب السريع
        pipe = redis_client.pipeline()
        for _ in range(max_count):
            pipe.rpop(key)
        results = pipe.execute()

        for item in results:
            if not item:
                break
            try:
                cmd = json.loads(item)
                # ★ تنظيف metadata
                cmd.pop("_session_id", None)
                commands.append(cmd)
            except json.JSONDecodeError as e:
                logger.warning(f"Parse error for cmd: {e}")

        if commands:
            logger.info(f"DELIVER >> {session_id[:8]} | {len(commands)} commands")

    except Exception as e:
        logger.exception(f"pop_commands error: {e}")

    return commands


# ============================================================
# Ack Command
# ============================================================
def ack_command(session_id, cmd_id):
    """تأكيد استلام أمر"""
    if not redis_client:
        return False
    try:
        key = f"lsh_acked:{session_id}"
        redis_client.sadd(key, cmd_id)
        redis_client.expire(key, 300)
        return True
    except Exception as e:
        logger.warning(f"ack error: {e}")
        return False


# ============================================================
# Nack Command → Dead Letter
# ============================================================
def nack_command(session_id, cmd_id, reason="unknown"):
    """أمر فشل — يُحفظ في Dead Letter Queue"""
    if not redis_client:
        return False
    try:
        dl_key = f"lsh_dead_letters:{session_id}"
        item = json.dumps({
            "cmd_id": cmd_id,
            "reason": reason,
            "ts": time.time(),
        })
        redis_client.lpush(dl_key, item)
        redis_client.expire(dl_key, LSH_CONFIG["dead_letter_ttl"])
        redis_client.ltrim(dl_key, 0, 99)
        return True
    except Exception as e:
        logger.warning(f"nack error: {e}")
        return False


# ============================================================
# Dead Letters
# ============================================================
def get_dead_letters(session_id, limit=20):
    """جلب الأوامر الفاشلة"""
    if not redis_client:
        return []
    try:
        dl_key = f"lsh_dead_letters:{session_id}"
        raw = redis_client.lrange(dl_key, 0, limit - 1)
        result = []
        for item in raw:
            try:
                result.append(json.loads(item))
            except json.JSONDecodeError:
                continue
        return result
    except Exception as e:
        logger.warning(f"get_dead_letters error: {e}")
        return []


def retry_dead_letters(session_id):
    """إعادة محاولة الأوامر الفاشلة"""
    if not redis_client:
        return 0
    try:
        dl_key = f"lsh_dead_letters:{session_id}"
        items = redis_client.lrange(dl_key, 0, -1)
        redis_client.delete(dl_key)
        return len(items)
    except Exception as e:
        logger.warning(f"retry_dead_letters error: {e}")
        return 0


# ============================================================
# Session Active
# ============================================================
def mark_session_active(session_id, ttl=None):
    """تحديث نشاط الجلسة"""
    if not redis_client:
        return
    try:
        if ttl is None:
            ttl = LSH_CONFIG["active_ttl"]
        redis_client.setex(
            f"lsh_active:{session_id}",
            ttl,
            str(time.time())
        )
    except Exception as e:
        logger.warning(f"mark_session_active error: {e}")


def is_session_active(session_id):
    """هل الجلسة نشطة؟"""
    if not redis_client:
        return False
    try:
        return bool(redis_client.get(f"lsh_active:{session_id}"))
    except Exception as e:
        logger.warning(f"is_session_active error: {e}")
        return False


def get_pending_count(session_id):
    """عدد الأوامر المعلقة"""
    if not redis_client:
        return 0
    try:
        return redis_client.llen(f"lsh_cmd:{session_id}")
    except Exception as e:
        logger.warning(f"get_pending_count error: {e}")
        return 0


# ============================================================
# Counters
# ============================================================
def _increment_counter(session_id, counter_name):
    """زيادة عداد"""
    if not redis_client:
        return
    try:
        key = f"lsh_stats:{session_id}:{counter_name}"
        redis_client.incr(key)
        redis_client.expire(key, 86400)
    except Exception as e:
        logger.debug(f"increment_counter error: {e}")


# ============================================================
# Clear
# ============================================================
def clear_commands(session_id):
    """حذف كل الأوامر"""
    if not redis_client:
        return
    try:
        pipe = redis_client.pipeline()
        pipe.delete(f"lsh_cmd:{session_id}")
        pipe.delete(f"lsh_stream:{session_id}")
        pipe.delete(f"lsh_dead_letters:{session_id}")
        pipe.execute()
    except Exception as e:
        logger.warning(f"clear_commands error: {e}")
