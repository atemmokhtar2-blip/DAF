# bot_handlers/callbacks/dashboard.py
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from logging_config import get_logger

from ..helpers import safe_edit, h

logger = get_logger("bot_handlers.callbacks.dashboard")


def handle(call, chat_id, user_id, data):
    bot.answer_callback_query(call.id, "🔄 جاري تجهيز الرابط...")
    try:
        from web_dashboard import generate_magic_link
        link = generate_magic_link(user_id)
        if not link:
            from ..keyboards import main_menu
            safe_edit(call, "❌ فشل توليد الرابط، حاول مرة أخرى",
                      reply_markup=main_menu(user_id))
            return
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 ادخل لوحة التحكم", url=link))
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        safe_edit(
            call,
            "🔐 <b>رابط الدخول للوحة التحكم</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "⏰ <i>الرابط صالح لمدة 5 دقائق فقط</i>\n"
            "🛡️ <i>لا تشاركه مع أي شخص</i>",
            reply_markup=markup
        )
    except Exception as e:
        logger.exception(f"open_dashboard error: {e}")
        from ..keyboards import main_menu
        safe_edit(call, f"❌ خطأ: {h(str(e)[:100])}",
                  reply_markup=main_menu(user_id))
