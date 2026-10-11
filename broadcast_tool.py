# broadcast_tool.py
# ============================================================
# Broadcast Tool v3 — إرسال رسائل جماعية احترافي
# ⚡ Handlers بتتنادى من router.py
# ============================================================
import os
import time
import json
import threading
from datetime import datetime
from typing import Optional

from config import bot, redis_client
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("broadcast_tool")


# ============================================================
# [1] الإعدادات
# ============================================================
# ⚡ أمان من الحظر - تلجرام بيسمح بـ 30 رسالة/ثانية
BROADCAST_DELAY = 0.06          # ~16 رسالة/ثانية
BATCH_SIZE = 200                # كل 200 مستخدم → راحة
BATCH_DELAY = 5                 # راحة 5 ثواني
MAX_RETRIES = 2                 # إعادة المحاولة عند الفشل
ADMIN_ID = 7631249810           # الأدمن الرئيسي


# ============================================================
# [2] Broadcast Session Storage (Redis)
# ============================================================
def _session_key(session_id):
    return f"broadcast:{session_id}"


def _stats_key(session_id):
    return f"broadcast_stats:{session_id}"


def create_broadcast_session(admin_id, message, total_users):
    """ينشئ session جديدة للبث"""
    if not redis_client:
        return None
    try:
        import uuid
        session_id = uuid.uuid4().hex[:12]

        data = {
            "session_id": session_id,
            "admin_id": admin_id,
            "message": message,
            "total": total_users,
            "started_at": time.time(),
            "started_at_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "running",
        }

        redis_client.setex(
            _session_key(session_id),
            86400 * 7,
            json.dumps(data, ensure_ascii=False)
        )

        return session_id
    except Exception as e:
        logger.exception(f"create_broadcast_session error: {e}")
        return None


def update_broadcast_stats(session_id, success, failed, blocked):
    """يزود إحصائيات البث"""
    if not redis_client:
        return
    try:
        key = _stats_key(session_id)
        pipe = redis_client.pipeline()
        pipe.hincrby(key, "success", success)
        pipe.hincrby(key, "failed", failed)
        pipe.hincrby(key, "blocked", blocked)
        pipe.expire(key, 86400 * 7)
        pipe.execute()
    except Exception as e:
        logger.warning(f"update_broadcast_stats error: {e}")


def get_broadcast_stats(session_id):
    """يجلب إحصائيات البث"""
    if not redis_client:
        return {}
    try:
        stats = redis_client.hgetall(_stats_key(session_id))
        return {
            k.decode() if isinstance(k, bytes) else k: int(v)
            for k, v in (stats or {}).items()
        }
    except Exception:
        return {}


def get_active_broadcasts(admin_id=None):
    """يجلب كل الجلسات النشطة"""
    if not redis_client:
        return []
    try:
        sessions = []
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(cursor, match="broadcast:*", count=100)
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                if "broadcast_stats" in key_str:
                    continue
                raw = redis_client.get(key_str)
                if raw:
                    try:
                        data = json.loads(raw)
                        if admin_id is None or data.get("admin_id") == admin_id:
                            sessions.append(data)
                    except Exception:
                        continue
            if cursor == 0:
                break
        return sorted(sessions, key=lambda x: x.get("started_at", 0), reverse=True)
    except Exception:
        return []


# ============================================================
# [3] Send Broadcast
# ============================================================
def send_broadcast(admin_id, message, target_users=None, notify_admin=True):
    """
    يبعت رسالة جماعية بشكل آمن
    """
    if not redis_client:
        logger.error("No Redis connection")
        return None

    # ═══ 1. جلب كل المستخدمين ═══
    if target_users is None:
        try:
            user_ids = redis_client.smembers("all_users") or set()
            target_users = [int(uid) for uid in user_ids if str(uid).isdigit()]
        except Exception as e:
            logger.exception(f"get users error: {e}")
            return None

    total = len(target_users)

    if total == 0:
        logger.warning("No users to broadcast")
        return None

    logger.info("=" * 60)
    logger.info(f"📢 BROADCAST START")
    logger.info(f"   Admin: {admin_id}")
    logger.info(f"   Total users: {total}")
    logger.info(f"   Message: {message[:80]}...")
    logger.info("=" * 60)

    # ═══ 2. إنشاء session ═══
    session_id = create_broadcast_session(admin_id, message, total)

    if not session_id:
        logger.error("Failed to create broadcast session")
        return None

    # ═══ 3. Background Thread ═══
    def _do_broadcast():
        _run_broadcast(session_id, admin_id, message, target_users, notify_admin)

    thread = threading.Thread(target=_do_broadcast, daemon=True)
    thread.start()

    logger.info(f"[+] Broadcast thread started: {session_id}")

    return session_id


def _run_broadcast(session_id, admin_id, message, users, notify_admin):
    """يشغل البث في الخلفية"""
    success = 0
    failed = 0
    blocked = 0
    start_time = time.time()

    # ═══ إشعار بدء للأدمن ═══
    if notify_admin:
        try:
            bot.send_message(
                admin_id,
                f"📢 <b>بدأ البث الجماعي</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🆔 <b>Session:</b> <code>{session_id}</code>\n"
                f"👥 <b>عدد المستخدمين:</b> <code>{len(users)}</code>\n"
                f"⏱️ <b>الوقت المتوقع:</b> ~{_estimate_time(len(users))}\n\n"
                f"📊 <b>الحالة:</b> ⏳ قيد الإرسال...",
                parse_mode="HTML"
            )
        except Exception:
            pass

    # ═══ 4. الإرسال ═══
    for i, uid in enumerate(users, 1):
        attempt = 0
        sent = False

        while attempt < MAX_RETRIES and not sent:
            try:
                bot.send_message(
                    uid,
                    message,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                success += 1
                sent = True

            except Exception as e:
                err = str(e).lower()

                # المستخدم حظر البوت
                if ("blocked" in err
                    or "chat not found" in err
                    or "user is deactivated" in err
                    or "kicked" in err):
                    blocked += 1
                    sent = True  # ما نعيدش المحاولة
                    logger.debug(f"User {uid} blocked bot")

                # Rate limit — استنى شوية
                elif "too many requests" in err or "retry after" in err:
                    wait_time = 30
                    logger.warning(f"Rate limit! Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    attempt += 1

                # خطأ آخر
                else:
                    logger.warning(f"Send to {uid} failed: {e}")
                    attempt += 1
                    if attempt >= MAX_RETRIES:
                        failed += 1

        # ═══ Progress Log ═══
        if i % 50 == 0:
            elapsed = time.time() - start_time
            speed = i / elapsed if elapsed > 0 else 0
            remaining = (len(users) - i) / speed if speed > 0 else 0

            logger.info(
                f"📤 Progress: {i}/{len(users)} | "
                f"✅ {success} | ❌ {failed} | 🚫 {blocked} | "
                f"⏱️ ETA: {int(remaining)}s"
            )

        # ═══ Batch Delay ═══
        if i % BATCH_SIZE == 0:
            logger.info(f"⏸️ Batch break: {BATCH_DELAY}s")
            time.sleep(BATCH_DELAY)
        else:
            time.sleep(BROADCAST_DELAY)

    # ═══ 5. النتيجة النهائية ═══
    duration = time.time() - start_time
    minutes = int(duration // 60)
    seconds = int(duration % 60)

    logger.info("=" * 60)
    logger.info(f"✅ BROADCAST COMPLETE")
    logger.info(f"   Session: {session_id}")
    logger.info(f"   Total: {len(users)}")
    logger.info(f"   Success: {success}")
    logger.info(f"   Failed: {failed}")
    logger.info(f"   Blocked: {blocked}")
    logger.info(f"   Duration: {minutes}m {seconds}s")
    logger.info("=" * 60)

    # ═══ حفظ النتيجة ═══
    try:
        stats = {
            "success": success,
            "failed": failed,
            "blocked": blocked,
            "completed_at": time.time(),
            "completed_at_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": round(duration, 1),
        }
        redis_client.setex(
            _stats_key(session_id),
            86400 * 7,
            json.dumps(stats, ensure_ascii=False)
        )

        # حدّث حالة الجلسة
        raw = redis_client.get(_session_key(session_id))
        if raw:
            data = json.loads(raw)
            data["status"] = "completed"
            data["stats"] = stats
            redis_client.setex(
                _session_key(session_id),
                86400 * 7,
                json.dumps(data, ensure_ascii=False)
            )
    except Exception as e:
        logger.warning(f"save broadcast stats error: {e}")

    metrics.inc_counter("broadcasts_completed")
    metrics.inc_counter("broadcast_success", value=success)
    metrics.inc_counter("broadcast_blocked", value=blocked)

    # ═══ إشعار الانتهاء للأدمن ═══
    if notify_admin:
        try:
            # نسبة النجاح
            success_rate = round((success / len(users)) * 100, 1) if users else 0

            # نص التقرير
            report = (
                f"✅ <b>اكتمل البث الجماعي</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🆔 <b>Session:</b> <code>{session_id}</code>\n\n"
                f"📊 <b>الإحصائيات:</b>\n"
                f"👥 الإجمالي: <code>{len(users)}</code>\n"
                f"✅ وصلت: <code>{success}</code>\n"
                f"❌ فشلت: <code>{failed}</code>\n"
                f"🚫 حظروني: <code>{blocked}</code>\n"
                f"📈 نسبة النجاح: <code>{success_rate}%</code>\n\n"
                f"⏱️ <b>المدة:</b> <code>{minutes}m {seconds}s</code>\n"
                f"🕐 <b>الوقت:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>\n"
            )

            # توصيات حسب الحالة
            if success_rate >= 90:
                report += f"\n🟢 <b>ممتاز!</b> البوت في حالة جيدة"
            elif success_rate >= 70:
                report += f"\n🟡 <b>جيد</b> — في شوية مشاكل بسيطة"
            elif success_rate >= 50:
                report += f"\n🟠 <b>متوسط</b> — راجع جودة المحتوى"
            else:
                report += f"\n🔴 <b>تحذير!</b> نص المستخدمين ما وصلتلهمش"

            bot.send_message(admin_id, report, parse_mode="HTML")

        except Exception as e:
            logger.warning(f"notify completion error: {e}")


def _estimate_time(total_users):
    """يحسب الوقت المتوقع"""
    per_user = BROADCAST_DELAY
    batches = total_users // BATCH_SIZE
    total_seconds = (total_users * per_user) + (batches * BATCH_DELAY)

    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)

    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


# ============================================================
# [4] Preview + Confirm Flow
# ============================================================
def broadcast_with_preview(admin_id, message):
    """
    يبعت معاينة للأدمن ويطلب تأكيد
    """
    try:
        # معاينة
        preview_text = (
            f"📢 <b>معاينة الرسالة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{message}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>هل أنت متأكد من الإرسال؟</b>"
        )

        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

        m = InlineKeyboardMarkup()
        m.row(
            InlineKeyboardButton(
                "✅ إرسال للجميع",
                callback_data="bc_confirm_send"
            ),
            InlineKeyboardButton(
                "❌ إلغاء",
                callback_data="bc_cancel"
            ),
        )
        m.add(InlineKeyboardButton(
            "📊 إحصائيات سابقة",
            callback_data="bc_stats"
        ))

        # خزّن الرسالة مؤقتاً
        if redis_client:
            redis_client.setex(
                f"broadcast_preview:{admin_id}",
                300,  # 5 دقايق
                message
            )

        bot.send_message(
            admin_id,
            preview_text,
            reply_markup=m,
            parse_mode="HTML"
        )

        return True

    except Exception as e:
        logger.exception(f"broadcast_with_preview error: {e}")
        return False


# ============================================================
# [5] Broadcast Stats Summary
# ============================================================
def build_broadcast_stats_text(admin_id=None):
    """
    يبني تقرير الإحصائيات
    """
    sessions = get_active_broadcasts(admin_id)

    if not sessions:
        return "📊 <b>إحصائيات البث</b>\n\n<i>لا يوجد بث سابق</i>"

    text = (
        f"📊 <b>إحصائيات البث الجماعي</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    for i, session in enumerate(sessions[:5], 1):
        sid = session.get("session_id", "?")
        total = session.get("total", 0)
        started = session.get("started_at_str", "?")
        status = session.get("status", "?")

        stats = session.get("stats", {})
        if not stats:
            stats = get_broadcast_stats(sid)

        success = stats.get("success", 0)
        failed = stats.get("failed", 0)
        blocked = stats.get("blocked", 0)

        rate = round((success / total) * 100, 1) if total > 0 else 0

        status_icon = "✅" if status == "completed" else "⏳"

        text += (
            f"{i}. {status_icon} <b>Session</b> <code>{sid}</code>\n"
            f"   📅 {started}\n"
            f"   👥 الإجمالي: <code>{total}</code>\n"
            f"   ✅ وصلت: <code>{success}</code>\n"
            f"   ❌ فشلت: <code>{failed}</code>\n"
            f"   🚫 محظرين: <code>{blocked}</code>\n"
            f"   📈 النسبة: <code>{rate}%</code>\n\n"
        )

    return text


# ============================================================
# [6] ⚡ Standalone Callback Handlers
# بتتنادى من router.py
# ============================================================

def handle_bc_confirm_send(call):
    """يتعامل مع زر الإرسال للجميع"""
    try:
        admin_id = call.from_user.id

        if admin_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
            return

        # هات الرسالة المحفوظة
        message = None
        if redis_client:
            raw = redis_client.get(f"broadcast_preview:{admin_id}")
            if raw:
                message = raw.decode() if isinstance(raw, bytes) else raw

        if not message:
            bot.answer_callback_query(call.id, "❌ الرسالة انتهت صلاحيتها", show_alert=True)
            return

        bot.answer_callback_query(call.id, "✅ جاري الإرسال...")

        # امسح الرسالة المحفوظة
        try:
            redis_client.delete(f"broadcast_preview:{admin_id}")
        except Exception:
            pass

        # امسح رسالة المعاينة
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        # ابدأ البث
        session_id = send_broadcast(admin_id, message)

        if not session_id:
            bot.send_message(
                admin_id,
                "❌ فشل بدء البث",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.exception(f"handle_bc_confirm_send error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ خطأ: {str(e)[:100]}", show_alert=True)
        except Exception:
            pass


def handle_bc_cancel(call):
    """يتعامل مع زر الإلغاء"""
    try:
        admin_id = call.from_user.id

        if admin_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
            return

        bot.answer_callback_query(call.id, "❌ تم الإلغاء")

        try:
            redis_client.delete(f"broadcast_preview:{admin_id}")
        except Exception:
            pass

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"handle_bc_cancel error: {e}")


def handle_bc_stats(call):
    """يتعامل مع زر الإحصائيات"""
    try:
        admin_id = call.from_user.id

        if admin_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
            return

        bot.answer_callback_query(call.id)

        text = build_broadcast_stats_text(admin_id)

        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="bc_back"))

        try:
            bot.edit_message_text(
                text=text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=m,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"edit stats message error: {e}")

    except Exception as e:
        logger.exception(f"handle_bc_stats error: {e}")


def handle_bc_back(call):
    """يتعامل مع زر الرجوع"""
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.warning(f"delete back message error: {e}")


# ============================================================
# [7] Init (بدون تسجيل handlers)
# ============================================================
def init_broadcast_handler(bot_instance=None):
    """
    تهيئة broadcast tool
    ⚠️ الـ handlers بتتسجل من router.py
    """
    global bot
    if bot_instance:
        bot = bot_instance

    logger.info("[+] Broadcast tool initialized (handlers via router)")
    return True


# ============================================================
# [8] Public API for Admin
# ============================================================
def admin_broadcast_confirm(admin_id, message):
    """يستخدم من admin_steps"""
    return broadcast_with_preview(admin_id, message)
