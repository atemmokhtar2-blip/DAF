# bot_handlers/callbacks/search.py
# ============================================================
# محرك البحث — مع تأكيد الأدوات
# ============================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from imports_manager import can_use_tool, get_user_phone_searches
from logging_config import get_logger

from ..helpers import safe_edit, deny_message, h
from ..keyboards import build_search_menu
from ..messages import SEARCH_MENU_TEXT, PHONE_SEARCH_PROMPT

logger = get_logger("bot_handlers.callbacks.search")


SOON_PAGES = {
    "search_email_soon": ("📧 <b>البحث بالإيميل</b>", "قيد التطوير"),
    "search_username_soon": ("👤 <b>البحث باسم المستخدم</b>", "قيد التطوير"),
    "search_fb_soon": ("📘 <b>البحث بحساب فيسبوك</b>", "قيد التطوير"),
    "search_ig_soon": ("📷 <b>البحث بحساب انستقرام</b>", "قيد التطوير"),
}


def handle(call, chat_id, user_id, data):

    if data == "search_menu":
        bot.answer_callback_query(call.id)
        safe_edit(call, SEARCH_MENU_TEXT, reply_markup=build_search_menu())
        return

    # ═══════════════════════════════════════════════════
    # 📱 بحث برقم → تأكيد
    # ═══════════════════════════════════════════════════
    if data == "search_phone":
        bot.answer_callback_query(call.id)
        try:
            from points_system import (
                build_tool_confirm_text,
                build_tool_confirm_keyboard,
            )
            text, can_proceed = build_tool_confirm_text(user_id, "phone_search")
            m = build_tool_confirm_keyboard("phone_search", can_proceed)
            safe_edit(call, text, reply_markup=m)
            return
        except Exception as e:
            logger.exception(f"tool_confirm phone_search error: {e}")
            _start_phone_search(call, chat_id, user_id)
            return

    if data == "search_phone_start":
        _start_phone_search(call, chat_id, user_id)
        return

    if data in SOON_PAGES:
        title, desc = SOON_PAGES[data]
        bot.answer_callback_query(call.id, "🚧 قريباً...", show_alert=True)
        safe_edit(
            call,
            f"{title}\n\n🚧 <i>{desc}</i>\n⏰ <i>سيتم إطلاقه قريباً</i>",
            reply_markup=build_search_menu()
        )
        return

    if data == "search_history":
        bot.answer_callback_query(call.id, "📜 جاري التحميل...")
        history = get_user_phone_searches(chat_id, limit=10)

        if not history:
            safe_edit(
                call,
                "📭 <b>لا يوجد سجل بحث</b>\n\nابدأ بحثك الأول 👇",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("📱 بحث جديد", callback_data="search_phone"),
                    InlineKeyboardButton("🔙 رجوع", callback_data="search_menu")
                )
            )
            return

        lines = ["📋 <b>آخر 10 بحثات:</b>\n━━━━━━━━━━━━━━━━━━\n"]
        for i, item in enumerate(history, 1):
            phone = item.get('phone', '?')
            name = item.get('name', '')
            name_text = f" — {h(name)}" if name else ""
            lines.append(f"{i}. <code>{h(phone)}</code>{name_text}")

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("📱 بحث جديد", callback_data="search_phone"))
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="search_menu"))

        safe_edit(call, "\n".join(lines), reply_markup=m)
        return


def _start_phone_search(call, chat_id, user_id):
    """يبدأ البحث بعد التأكيد"""
    bot.answer_callback_query(call.id, "✅ جاري البدء...")

    check = can_use_tool(user_id, "phone_search")
    if not check["allowed"]:
        if check["reason"] == "insufficient_points":
            m = InlineKeyboardMarkup()
            m.add(InlineKeyboardButton("💰 نقاطي", callback_data="points_menu"))
            m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            safe_edit(
                call,
                f"❌ <b>رصيدك غير كافي!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 <b>المطلوب:</b> <code>{check.get('cost', 0)}</code> نقطة\n"
                f"💎 <b>رصيدك:</b> <code>{check.get('balance', 0)}</code> نقطة",
                reply_markup=m
            )
            return
        safe_edit(call, "❌ لا يمكن استخدام الأداة", reply_markup=build_search_menu())
        return

    consume_usage(user_id, "phone_search")

    msg = bot.send_message(chat_id, PHONE_SEARCH_PROMPT, parse_mode="HTML")

    from ..steps.search_steps import phone_search_input_handler
    bot.register_next_step_handler(msg, phone_search_input_handler)
