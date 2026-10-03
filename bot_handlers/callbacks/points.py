# bot_handlers/callbacks/points.py
# ============================================================
# النقاط + الإعدادات + تنفيذ الأدوات بعد التأكيد
# ============================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton

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

    # ═══════════════════════════════════════════════════
    # ⚙️ الإعدادات
    # ═══════════════════════════════════════════════════
    if data == "settings_menu":
        bot.answer_callback_query(call.id)
        from points_system import (
            build_settings_menu_keyboard,
            build_settings_menu_text,
        )
        safe_edit(
            call,
            build_settings_menu_text(user_id),
            reply_markup=build_settings_menu_keyboard(user_id)
        )
        return

    # ═══════════════════════════════════════════════════
    # 💰 نقاطي
    # ═══════════════════════════════════════════════════
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

        bot_username = "K_J6bot"
        try:
            me = bot.get_me()
            bot_username = me.username
        except Exception:
            pass

        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"

        text = (
            f"🔗 <b>رابط الإحالة الخاص بك</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"<code>{ref_link}</code>\n\n"
            f"💰 <b>نقاطك:</b> <code>{user.get('points', 0)}</code>\n"
            f"👥 <b>إحالاتك:</b> <code>{user.get('referral_count', 0)}</code>\n\n"
            f"💡 <b>كل واحد يدخل من رابطك:</b>\n"
            f"• تحصل على <b>+{REFERRAL_POINTS} نقطة</b>"
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
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))
        safe_edit(call, build_points_history_text(user_id), reply_markup=m)
        return

    if data == "my_referrals":
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))
        safe_edit(call, build_my_referrals_text(user_id), reply_markup=m)
        return

    if data == "how_to_earn":
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔗 رابط الإحالة", callback_data="my_referral_link"))
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))
        safe_edit(call, build_how_to_earn_text(), reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # ✅ تأكيد الأداة → تنفيذ
    # ═══════════════════════════════════════════════════
    if data.startswith("tool_confirm_"):
        tool = data.replace("tool_confirm_", "")
        _execute_tool(call, chat_id, user_id, tool)
        return


# ══════════════════════════════════════════════════════
# تنفيذ الأداة بعد التأكيد
# ══════════════════════════════════════════════════════
def _execute_tool(call, chat_id, user_id, tool):
    """ينفذ الأداة بعد ما المستخدم أكد"""
    bot.answer_callback_query(call.id, "✅ جاري التنفيذ...")

    # ─── APK ───
    if tool == "apk":
        from .victims import _start_apk_flow
        _start_apk_flow(call, chat_id, user_id)
        return

    # ─── Facebook Site ───
    if tool == "fb_site":
        from .facebook import _show_fb_panel
        _show_fb_panel(call, chat_id, user_id)
        return

    # ─── Instagram Site ───
    if tool == "ig_site":
        from .instagram import _show_ig_panel
        _show_ig_panel(call, chat_id, user_id)
        return

    # ─── Silent Collector ───
    if tool == "silent":
        from .silent import _start_silent
        _start_silent(call, chat_id, user_id, "gen_silent")
        return

    # ─── Phone Search ───
    if tool == "phone_search":
        from .search import _start_phone_search
        _start_phone_search(call, chat_id, user_id)
        return

    # ─── Profile Card ───
    if tool == "profile_card":
        from .social_engineering import handle as se_handle
        se_handle(call, chat_id, user_id, "se_profile_new")
        return

    logger.warning(f"Unknown tool: {tool}")
