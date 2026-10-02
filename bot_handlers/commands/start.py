# bot_handlers/commands/start.py
from config import bot
from imports_manager import get_or_create_user, is_admin
from logging_config import get_logger
from monitoring import metrics

from ..helpers import h
from ..keyboards import main_menu
from ..messages import WELCOME_ADMIN, WELCOME_USER

logger = get_logger("bot_handlers.commands.start")


@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    logger.info(f"/start from {message.from_user.id}")
    metrics.inc_counter("bot_commands", tags={"cmd": "start"})

    user_name = message.from_user.first_name
    try:
        get_or_create_user(
            message.from_user.id,
            message.from_user.username or "Unknown",
            user_name
        )
    except Exception as e:
        logger.exception(f"get_or_create_user error: {e}")

    if is_admin(message.from_user.id):
        text = WELCOME_ADMIN.format(name=h(user_name))
    else:
        text = WELCOME_USER.format(name=h(user_name))

    bot.send_message(
        message.chat.id, text,
        parse_mode="HTML",
        reply_markup=main_menu(message.from_user.id)
  )
