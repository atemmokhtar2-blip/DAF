# bot_handlers/callbacks/search.py
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
    # ─── القائمة ───
    if data == "search_menu":
        bot.answer_callback_query(call.id)
        safe_edit(call, SEARCH_MENU_TEXT, reply_markup=build_search_menu())
        return

    # ─── بحث برقم ───
    if data == "search_phone":
        check = can_use_tool(chat_id, "phone_search")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            safe_edit(
                call,
                deny_message(check["reason"], chat_id, "phone_search", check),
                reply_markup=build_search_menu()
            )
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, PHONE_SEARCH_PROMPT, parse_mode="HTML")

        from ..steps.search_steps import phone_search_input_handler
        bot.register_next_step_handler(msg, phone_search_input_handler)
        return

    # ─── قريباً ───
    if data in SOON_PAGES:
        title, desc = SOON_PAGES[data]
        bot.answer_callback_query(call.id, "🚧 قريباً...", show_alert=True)
        safe_edit(
            call,
            f"{title}\n\n🚧 <i>{desc}</i>\n⏰ <i>سيتم إطلاقه قريباً</i>",
            reply_markup=build_search_menu()
        )
        return

    # ─── السجل ───
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
