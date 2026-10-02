# bot_handlers/steps/search_steps.py
import threading

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from logging_config import get_logger

from ..helpers import h

logger = get_logger("bot_handlers.steps.search")


def phone_search_input_handler(message):
    chat_id = message.chat.id

    if not message.text:
        bot.send_message(chat_id, "❌ أرسل رقماً صحيحاً")
        return

    phone_input = message.text.strip()

    wait_msg = bot.send_message(
        chat_id,
        "🔍 <b>جاري البحث...</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ <i>هذا قد يستغرق 10-15 ثانية</i>\n"
        "• تحليل الرقم\n"
        "• بحث Truecaller\n"
        "• فحص WhatsApp/Telegram\n"
        "• Google Dorks",
        parse_mode="HTML"
    )

    try:
        from phone_search import search_phone, format_result_for_telegram

        def do_search():
            try:
                result = search_phone(phone_input, chat_id=chat_id)
                formatted = format_result_for_telegram(result)

                try:
                    bot.delete_message(chat_id, wait_msg.message_id)
                except Exception:
                    pass

                tc = result.get('truecaller') or {}
                if tc.get('photo'):
                    try:
                        bot.send_photo(
                            chat_id,
                            tc['photo'],
                            caption="🖼️ <b>صورة البروفايل</b>",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Photo send error: {e}")

                m = InlineKeyboardMarkup()
                m.add(InlineKeyboardButton("📱 بحث جديد", callback_data="search_phone"))
                m.add(InlineKeyboardButton("📜 السجل", callback_data="search_history"))
                m.add(InlineKeyboardButton("🔙 القائمة", callback_data="search_menu"))

                if len(formatted) > 4000:
                    parts = [formatted[i:i+3900] for i in range(0, len(formatted), 3900)]
                    for i, part in enumerate(parts):
                        if i == len(parts) - 1:
                            bot.send_message(chat_id, part, parse_mode="HTML",
                                           disable_web_page_preview=True, reply_markup=m)
                        else:
                            bot.send_message(chat_id, part, parse_mode="HTML",
                                           disable_web_page_preview=True)
                else:
                    bot.send_message(chat_id, formatted, parse_mode="HTML",
                                   disable_web_page_preview=True, reply_markup=m)

            except Exception as e:
                logger.exception(f"phone_search error: {e}")
                try:
                    bot.delete_message(chat_id, wait_msg.message_id)
                except Exception:
                    pass
                bot.send_message(chat_id, f"❌ <b>خطأ:</b> {h(str(e)[:200])}",
                               parse_mode="HTML")

        threading.Thread(target=do_search, daemon=True).start()

    except Exception as e:
        logger.exception(f"phone_search_input error: {e}")
        try:
            bot.edit_message_text(
                f"❌ خطأ: {h(str(e)[:200])}",
                chat_id=chat_id,
                message_id=wait_msg.message_id
            )
        except Exception:
            pass
