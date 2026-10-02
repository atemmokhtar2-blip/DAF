# bot_handlers/callbacks/misc.py
from config import bot
from logging_config import get_logger

from ..helpers import safe_edit
from ..keyboards import main_menu, main_menu_text

logger = get_logger("bot_handlers.callbacks.misc")


def handle(call, chat_id, user_id, data):
    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    if data == "back_to_main":
        bot.answer_callback_query(call.id)
        safe_edit(call, main_menu_text(user_id), reply_markup=main_menu(user_id))
        return
