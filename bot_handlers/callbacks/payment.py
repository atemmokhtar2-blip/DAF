# bot_handlers/callbacks/payment.py
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from imports_manager import (
    build_main_payment_keyboard,
    build_plans_keyboard,
    build_plans_text,
    build_account_text,
    send_invoice,
)
from logging_config import get_logger

from ..helpers import safe_edit

logger = get_logger("bot_handlers.callbacks.payment")


def handle(call, chat_id, user_id, data):
    if data == "payment_menu":
        bot.answer_callback_query(call.id)
        safe_edit(call, "💎 <b>قسم الاشتراكات</b>",
                  reply_markup=build_main_payment_keyboard())
        return

    if data == "show_plans":
        bot.answer_callback_query(call.id)
        safe_edit(call, build_plans_text(), reply_markup=build_plans_keyboard())
        return

    if data.startswith("buy_plan_"):
        plan_key = data.replace("buy_plan_", "")
        bot.answer_callback_query(call.id, "جاري تجهيز الفاتورة...")
        send_invoice(bot, chat_id, plan_key)
        return

    if data == "my_account":
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        safe_edit(call, build_account_text(chat_id), reply_markup=m)
        return
