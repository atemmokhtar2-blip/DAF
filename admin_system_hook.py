# admin_system_hook.py
# ============================================================
# توصيل admin_system v2.0 بالبوت تلقائياً
# ============================================================

import json
import time
from datetime import datetime

from config import bot, redis_client
from logging_config import get_logger

logger = get_logger("admin_system_hook")


def init_admin_system(bot_instance=None):
    """يفعّل admin_system v2.0 تلقائياً"""

    global bot
    if bot_instance:
        bot = bot_instance

    # ─── 1. تحقق من الاستيراد ───
    try:
        from admin_system import (
            track_user_activity,
            get_online_count,
            get_system_health,
            notify_admin,
            get_admin_ids,
            # ★★★ إضافات v2.0 ★★★
            is_maintenance,
            is_exempt_from_maintenance,
            get_maintenance_message,
        )
        logger.info("[+] Admin System v2.0: ACTIVATED")
    except Exception as e:
        logger.exception(f"[-] Admin System v2.0: FAILED - {e}")
        return False

    # ─── 2. سجّل tracking + maintenance check لكل رسالة ───
    try:
        @bot.message_handler(func=lambda m: True, content_types=['text'])
        def _track_message(message):
            try:
                # ★★★ فحص الصيانة أولاً ★★★
                try:
                    if is_maintenance():
                        if not is_exempt_from_maintenance(message.from_user.id):
                            maint_msg = get_maintenance_message() or (
                                "🔧 <b>وضع الصيانة</b>\n\n"
                                "البوت تحت التحديث حالياً\n"
                                "الرجاء المحاولة لاحقاً"
                            )
                            try:
                                bot.send_message(
                                    message.chat.id,
                                    maint_msg,
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass
                            return
                except Exception:
                    pass

                # ★★★ Track activity ★★★
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

        logger.info("[+] Admin System: Message tracker registered (with maintenance check)")
    except Exception as e:
        logger.warning(f"[-] Message tracker registration failed: {e}")

    # ─── 3. سجّل بدء التشغيل ───
    try:
        if redis_client:
            redis_client.lpush(
                "admin_events",
                json.dumps({
                    "admin_id": 0,
                    "type": "system_start",
                    "details": "Admin System v2.0 initialized",
                    "timestamp": time.time(),
                    "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, ensure_ascii=False)
            )
            redis_client.ltrim("admin_events", 0, 199)
            redis_client.expire("admin_events", 86400 * 30)
        logger.info("[+] Admin System: Startup event logged")
    except Exception as e:
        logger.debug(f"[-] Startup event log failed: {e}")

    # ─── 4. اطبع حالة أولية ───
    try:
        health = get_system_health()
        online = get_online_count()
        maint = is_maintenance()

        logger.info(
            f"📊 Admin System v2.0 Stats | "
            f"online={online} | "
            f"CPU={health.get('cpu_percent')}% | "
            f"RAM={health.get('ram_percent')}% | "
            f"Redis={'✅' if health.get('redis') else '❌'} | "
            f"PG={'✅' if health.get('postgres') else '❌'} | "
            f"Maintenance={'🔧 ON' if maint else '⚪ OFF'}"
        )
    except Exception as e:
        logger.debug(f"Stats print error: {e}")

    # ─── 5. إشعار الأدمن بالبدء ───
    try:
        admin_ids = get_admin_ids()
        notify_admin(
            admin_ids,
            "البوت اشتغل",
            "✅ Admin System v2.0 يعمل الآن\n"
            "🔧 وضع الصيانة جاهز\n"
            "❤️ صحة النظام متاحة",
            icon="🚀"
        )
    except Exception as e:
        logger.debug(f"Startup notify error: {e}")

    logger.info("[+] Admin System v2.0: INITIALIZED ✅")
    return True
