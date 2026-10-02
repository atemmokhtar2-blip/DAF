# bot_handlers/helpers.py
# ============================================================
# دوال مساعدة مشتركة
# ============================================================

import html

from config import bot
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("bot_handlers.helpers")


def h(text):
    """Escape HTML"""
    if text is None:
        return ""
    return html.escape(str(text))


def safe_edit(call, text, reply_markup=None, parse_mode="HTML"):
    """يحاول يعدل الرسالة، ولو فشل يبعت رسالة جديدة"""
    try:
        bot.edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        if "message to edit not found" in err or "message can't be edited" in err:
            try:
                bot.send_message(
                    call.message.chat.id,
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True,
                )
                return True
            except Exception as e2:
                logger.warning(f"safe_edit fallback error: {e2}")
        else:
            logger.debug(f"safe_edit error: {e}")
        return False


def deny_message(reason, user_id, tool, data=None):
    """رسالة رفض موحدة"""
    from .messages import FREE_TRIAL_USES
    data = data or {}
    if reason == "banned":
        return "🚫 <b>أنت محظور.</b>"
    if reason == "daily_limit_reached":
        return f"⚠️ <b>وصلت للحد اليومي</b> ({data.get('daily_limit', 0)})."
    if reason == "no_credit":
        return (
            "❌ <b>لا يوجد لديك استخدام متاح.</b>\n\n"
            f"🎁 حصلت على {FREE_TRIAL_USES} استخدام مجاني.\n"
            "💎 اشترك للاستمرار."
        )
    return "❌ لا يمكن استخدام الأداة."
