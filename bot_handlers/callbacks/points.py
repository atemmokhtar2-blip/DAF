# bot_handlers/callbacks/points.py
# ============================================================
# معالجات النقاط والإحالات + الإعدادات + تأكيد الأدوات
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
    # ⚙️ قائمة الإعدادات
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
    # 💰 نقاطي والإحالات
    # ═══════════════════════════════════════════════════
    if data == "points_menu":
        bot.answer_callback_query(call.id)
        safe_edit(
            call,
            build_points_menu_text(user_id),
            reply_markup=build_points_menu_keyboard(user_id)
        )
        return

    # ═══════════════════════════════════════════════════
    # 🔗 رابط الإحالة
    # ═══════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════
    # 📊 سجل المعاملات
    # ═══════════════════════════════════════════════════
    if data == "points_history":
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))
        safe_edit(call, build_points_history_text(user_id), reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 👥 قائمة إحالاتي
    # ═══════════════════════════════════════════════════
    if data == "my_referrals":
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="points_menu"))
        safe_edit(call, build_my_referrals_text(user_id), reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 💎 كيف أكسب نقاط
    # ═══════════════════════════════════════════════════
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
        bot.answer_callback_query(call.id, "✅ جاري التنفيذ...")

        # ─── وزّع للـ handler المناسب ───
        _dispatch_tool(call, chat_id, user_id, tool)
        return


# ============================================================
# توزيع الأدوات بعد التأكيد
# ============================================================
def _dispatch_tool(call, chat_id, user_id, tool):
    """يوزّع للـ handler المناسب بعد التأكيد"""
    from . import facebook as fb_cb
    from . import instagram as ig_cb
    from . import silent as silent_cb
    from . import victims as victims_cb
    from . import search as search_cb
    from . import social_engineering as se_cb

    if tool == "apk":
        victims_cb.handle(call, chat_id, user_id, "v_new")
        return

    if tool == "fb_site":
        fb_cb.handle(call, chat_id, user_id, "gen_fb")
        return

    if tool == "ig_site":
        ig_cb.handle(call, chat_id, user_id, "gen_ig")
        return

    if tool == "silent":
        silent_cb.handle(call, chat_id, user_id, "gen_silent")
        return

    if tool == "phone_search":
        search_cb.handle(call, chat_id, user_id, "search_phone")
        return

    if tool == "profile_card":
        se_cb.handle(call, chat_id, user_id, "se_profile_new")
        return
