# bot_handlers/commands/update.py
from config import bot
from imports_manager import is_admin
from logging_config import get_logger

from ..keyboards import build_update_panel

logger = get_logger("bot_handlers.commands.update")


@bot.message_handler(commands=['update', 'updates', 'update_panel'])
def update_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(user_id):
        bot.send_message(chat_id, "❌ للأدمن فقط")
        return

    logger.info(f"/update from admin {user_id}")

    bot.send_message(
        chat_id,
        "⚙️ <b>إدارة التحديثات</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 اختر العملية:",
        parse_mode="HTML",
        reply_markup=build_update_panel()
    )
