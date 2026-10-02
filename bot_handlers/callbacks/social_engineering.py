# bot_handlers/callbacks/social_engineering.py
# ============================================================
# هندسة اجتماعية — الجسر بين router.py و social_engineering.py
# ============================================================

from config import bot
from logging_config import get_logger

logger = get_logger("bot_handlers.callbacks.social_engineering")

# استيراد المعالج الأصلي
try:
    from social_engineering import handle_social_engineering_callback
    SE_ENABLED = True
    logger.info("[+] social_engineering imported")
except Exception as e:
    logger.exception(f"[-] social_engineering import failed: {e}")
    SE_ENABLED = False

    def handle_social_engineering_callback(call, bot, chat_id, user_id, data):
        return False


def handle(call, chat_id, user_id, data):
    """الجسر بين router والـ social_engineering الأصلي"""
    if not SE_ENABLED:
        bot.answer_callback_query(call.id, "❌ القسم غير متاح", show_alert=True)
        return

    try:
        handled = handle_social_engineering_callback(
            call, bot, chat_id, user_id, data
        )
        if not handled:
            logger.warning(f"SE handler returned False for: {data}")
            bot.answer_callback_query(call.id)
    except Exception as e:
        logger.exception(f"SE handler error for {data}: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)
        except Exception:
            pass
