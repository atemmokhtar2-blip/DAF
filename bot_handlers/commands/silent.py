# bot_handlers/commands/silent.py
from config import bot
from imports_manager import get_or_create_user, can_use_tool, consume_usage
from logging_config import get_logger

from ..helpers import deny_message
from ..messages import SILENT_PROMPT

logger = get_logger("bot_handlers.commands.silent")


@bot.message_handler(commands=['silent', 'collect'])
def silent_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    logger.info(f"/silent from {user_id}")

    try:
        get_or_create_user(
            user_id,
            message.from_user.username or "Unknown",
            message.from_user.first_name or "User"
        )
    except Exception as e:
        logger.exception(f"get_or_create_user error: {e}")

    check = can_use_tool(chat_id, "silent")
    if not check["allowed"]:
        bot.send_message(
            chat_id,
            deny_message(check["reason"], chat_id, "silent", check),
            parse_mode="HTML"
        )
        return

    consume_usage(chat_id, "silent")

    msg = bot.send_message(chat_id, SILENT_PROMPT, parse_mode="HTML")

    from ..steps.silent_steps import silent_label_handler
    bot.register_next_step_handler(msg, silent_label_handler)
