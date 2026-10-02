# admin_system_hook.py
# ============================================================
# توصيل admin_system بالبوت تلقائياً
# ============================================================

from config import bot
from logging_config import get_logger

logger = get_logger("admin_system_hook")


def init_admin_system(bot_instance=None):
    """يفعّل admin_system تلقائياً"""

    # ─── 1. تحقق من الاستيراد ───
    try:
        from admin_system import (
            track_user_activity,
            get_online_count,
            get_system_stats,
            log_admin_event,
        )
        logger.info("[+] Admin System: ACTIVATED")
    except Exception as e:
        logger.exception(f"[-] Admin System: FAILED - {e}")
        return False

    # ─── 2. سجّل tracking لكل رسالة ───
    try:
        @bot.message_handler(func=lambda m: True, content_types=['text'])
        def _track_message(message):
            try:
                track_user_activity(
                    message.from_user.id,
                    action="message",
                    extra={
                        "text": (message.text or "")[:50],
                        "chat_id": message.chat.id,
                    }
                )
            except Exception:
                pass

        logger.info("[+] Admin System: Message tracker registered")
    except Exception as e:
        logger.warning(f"[-] Message tracker registration failed: {e}")

    # ─── 3. سجّل بدء التشغيل ───
    try:
        log_admin_event(
            admin_id=0,
            event_type="system_start",
            details="Admin System initialized"
        )
    except Exception:
        pass

    # ─── 4. اطبع حالة أولية ───
    try:
        stats = get_system_stats()
        logger.info(
            f"📊 Admin System Stats | "
            f"users={stats['total_users']} | "
            f"online={stats['online_now']} | "
            f"victims={stats['total_victims']}"
        )
    except Exception:
        pass

    logger.info("[+] Admin System: INITIALIZED ✅")
    return True
