# bot_handlers/callbacks/points.py
# ============================================================
# معالجات النقاط والإحالات
# ============================================================

from config import bot
from imports_manager import (
    get_or_create_user,
    build_points_menu_text,
    build_points_menu_keyboard,
    build_points_history_text,
    build_my_referrals_text,
    build_how_to_earn_text,
    REFERRAL_POINTS,
)
from logging_config import get_logger

from ..helpers import safe_edit

logger = get_logger("bot_handlers.callbacks.points")


def handle(call, chat_id, user_id, data):
    if data == "points_menu":
        bot.answer_callback_query(call.id)
        safe_edit(
            call,
            build_points_menu_text(user_id),
            reply_markup=build_points_menu_keyboard(user_id)
        )
        return

    if data == "my_referral_link":
        bot.answer_callback_query(call.id, "🔗 جاري التجهيز...")
        user = get_or_create_user(user_id)
        ref_code = user.get("ref_code", "")

        # جيب username البوت
        bot_username = "K_J6bot"
        try:
            me = bot.get_me()
            bot_username = me.username
        except Exception:
            pass

        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"

        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton

        text = (
            f"🔗 <b>رابط الإحالة الخاص بك</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"<code>{ref_link}</code>\n\n"

            f"💰 <b>نقاطك:</b> <code>{user.get('points', 0)}</code>\n"
            f"👥 <b>إحالاتك:</b> <code>{user.get('referral_count', 0)}</code>\n\n"

            f"💡 <b>كل واحد يدخل من رابطك:</b>\n"
            f"• تحصل على <b>+{REFERRAL_POINTS} نقطة</b>\n"
            f"• مكافآت إضافية عند 5/10/25 إحالة"
        )

        m = InlineKeyboardMarkup()
        try:
            m.add(InlineKeyboardButton(
                "📋 نسخ الرابط",
                copy_text=CopyTextButton(text=ref_link)
            ))
        except Exception:
            pass
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))

        safe_edit(call, text, reply_markup=m)
        return

    if data == "points_history":
        bot.answer_callback_query(call.id)
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))
        safe_edit(call, build_points_history_text(user_id), reply_markup=m)
        return

    if data == "my_referrals":
        bot.answer_callback_query(call.id)
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))
        safe_edit(call, build_my_referrals_text(user_id), reply_markup=m)
        return

    if data == "how_to_earn":
        bot.answer_callback_query(call.id)
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))
        safe_edit(call, build_how_to_earn_text(), reply_markup=m)
        return
