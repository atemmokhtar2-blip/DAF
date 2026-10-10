# bot_handlers/callbacks/misc.py
# ============================================================
# Misc Handler — مع الرد الفوري لتجنب query too old
# ============================================================
from config import bot
from logging_config import get_logger

from ..helpers import safe_edit
from ..keyboards import main_menu, main_menu_text

logger = get_logger("bot_handlers.callbacks.misc")


def handle(call, chat_id, user_id, data):
    """معالج الأزرار العامة"""

    # ⚡ الرد الفوري أول حاجة (عشان نتجنب query too old)
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        err_str = str(e).lower()
        # تجاهل خطأ "query too old" لأنه مش مشكلة حقيقية
        if "query is too old" not in err_str and "query id is invalid" not in err_str:
            logger.debug(f"answer_callback_query failed: {e}")

    # ═══ noop ═══
    if data == "noop":
        return

    # ═══ back_to_main ═══
    if data == "back_to_main":
        try:
            safe_edit(
                call,
                main_menu_text(user_id),
                reply_markup=main_menu(user_id)
            )
        except Exception as e:
            err_str = str(e).lower()
            if "query is too old" not in err_str and "message is not modified" not in err_str:
                logger.exception(f"back_to_main error: {e}")
        return
