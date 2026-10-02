# bot_handlers/callbacks/admin.py
# ============================================================
# ★ معالجات الأدمن الكاملة
# ============================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from imports_manager import (
    is_admin,
    build_admin_menu,
    build_admin_users_keyboard,
    build_user_detail_keyboard,
    build_user_info_text,
    build_admin_stats_text,
    get_all_users,
    get_user,
    get_or_create_user,
    save_user,
    ban_user, unban_user, delete_user,
    activate_subscription,
    PRICING_PLANS,
)
from logging_config import get_logger

from ..helpers import safe_edit, h

logger = get_logger("bot_handlers.callbacks.admin")


def handle(call, chat_id, user_id, data):
    """الموزّع الرئيسي لكل admin_*"""

    # ─── حماية عامة ───
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
        return

    # ─── اللوحة الرئيسية ───
    if data == "admin_panel":
        bot.answer_callback_query(call.id)
        safe_edit(call, "👑 <b>لوحة تحكم الأدمن</b>", reply_markup=build_admin_menu())
        return

    # ─── التحديثات ───
    if data == "admin_updates":
        bot.answer_callback_query(call.id, "⚙️ جاري الفتح...")
        from ..keyboards import build_update_panel
        safe_edit(call, "⚙️ <b>إدارة التحديثات</b>", reply_markup=build_update_panel())
        return

    # ─── المستخدمون (مع pagination) ───
    if data.startswith("admin_users_"):
        _handle_users_list(call, data)
        return

    # ─── تفاصيل مستخدم ───
    if data.startswith("admin_user_"):
        _handle_user_detail(call, data)
        return

    # ─── إجراءات المستخدم ───
    if data.startswith("admin_ban_user_"):
        _handle_ban(call, data)
        return

    if data.startswith("admin_unban_user_"):
        _handle_unban(call, data)
        return

    if data.startswith("admin_grant_vip_user_"):
        _handle_grant_vip(call, data)
        return

    if data.startswith("admin_remove_vip_"):
        _handle_remove_vip(call, data)
        return

    if data.startswith("admin_delete_user_"):
        _handle_delete(call, data)
        return

    if data.startswith("admin_give_sub_"):
        _handle_give_sub_prompt(call, data)
        return

    if data.startswith("admin_activate_"):
        _handle_activate_sub(call, data)
        return

    if data.startswith("admin_msg_user_"):
        _handle_msg_user(call, chat_id, data)
        return

    # ─── إحصائيات ───
    if data == "admin_stats":
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        safe_edit(call, build_admin_stats_text(), reply_markup=m)
        return

    if data == "admin_recent":
        _handle_recent(call)
        return

    # ─── بحث ───
    if data == "admin_search":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🔍 <b>أرسل ID أو username:</b>", parse_mode="HTML")
        from ..steps.admin_steps import admin_search_handler
        bot.register_next_step_handler(msg, admin_search_handler)
        return

    # ─── رسالة جماعية ───
    if data == "admin_broadcast":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 <b>أرسل الرسالة:</b>", parse_mode="HTML")
        from ..steps.admin_steps import admin_broadcast_handler
        bot.register_next_step_handler(msg, admin_broadcast_handler)
        return

    # ─── حظر / فك حظر ───
    if data == "admin_ban":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🚫 <b>أرسل ID للحظر:</b>", parse_mode="HTML")
        from ..steps.admin_steps import admin_ban_handler
        bot.register_next_step_handler(msg, admin_ban_handler)
        return

    if data == "admin_unban":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "✅ <b>أرسل ID لفك الحظر:</b>", parse_mode="HTML")
        from ..steps.admin_steps import admin_unban_handler
        bot.register_next_step_handler(msg, admin_unban_handler)
        return

    if data == "admin_delete":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🗑️ <b>أرسل ID للحذف:</b>", parse_mode="HTML")
        from ..steps.admin_steps import admin_delete_handler
        bot.register_next_step_handler(msg, admin_delete_handler)
        return

    # ─── منح VIP ───
    if data == "admin_grant_vip":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "💎 <b>أرسل ID لمنح VIP:</b>", parse_mode="HTML")
        from ..steps.admin_steps import admin_grant_vip_handler
        bot.register_next_step_handler(msg, admin_grant_vip_handler)
        return

    # ─── نجوم ───
    if data == "admin_give_stars":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "⭐ <b>أرسل:</b> <code>user_id|amount</code>",
            parse_mode="HTML"
        )
        from ..steps.admin_steps import admin_give_stars_handler
        bot.register_next_step_handler(msg, admin_give_stars_handler)
        return

    # ─── إعطاء اشتراك (من اللوحة) ───
    if data == "admin_add_sub":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "➕ <b>أرسل:</b> <code>user_id|plan_key</code>\n\n"
            "مثال: <code>123456|basic</code>\n"
            "الباقات: basic, pro, vip",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, _admin_add_sub_step)
        return

    # ─── أحداث ───
    if data == "admin_events":
        _handle_events(call)
        return

    # ─── سجل الأنشطة ───
    if data == "admin_activity_log":
        _handle_activity_log(call)
        return

    # ─── تنظيف Redis ───
    if data == "admin_clean_redis":
        _handle_clean_redis(call)
        return

    # ─── تصدير ───
    if data == "admin_export":
        _handle_export(call, chat_id)
        return

    # ─── إعدادات ───
    if data == "admin_settings":
        _handle_settings(call)
        return

    # ─── صيانة ───
    if data == "admin_maintenance_on":
        _handle_maint_on(call, user_id)
        return

    if data == "admin_maintenance_off":
        _handle_maint_off(call, user_id)
        return

    # ─── مراقبة ───
    if data == "admin_live":
        _handle_live(call)
        return

    if data == "admin_adv_stats":
        _handle_adv_stats(call)
        return

    if data == "admin_analytics":
        _handle_analytics(call)
        return

    if data == "admin_top_users":
        _handle_top_users(call)
        return

    # ─── غير معروف ───
    logger.warning(f"Unknown admin callback: {data}")
    bot.answer_callback_query(call.id)


# ══════════════════════════════════════════════════
# المستخدمون
# ══════════════════════════════════════════════════
def _handle_users_list(call, data):
    try:
        page = int(data.replace("admin_users_", ""))
    except ValueError:
        page = 0

    users = get_all_users()
    if not users:
        bot.answer_callback_query(call.id, "لا يوجد مستخدمون", show_alert=True)
        return

    users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
    bot.answer_callback_query(call.id)
    safe_edit(call, f"👥 <b>المستخدمون ({len(users)})</b>",
              reply_markup=build_admin_users_keyboard(users, page))


def _handle_user_detail(call, data):
    try:
        uid = int(data.replace("admin_user_", ""))
    except ValueError:
        return

    user = get_user(uid)
    if not user:
        bot.answer_callback_query(call.id, "❌ غير موجود", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    safe_edit(
        call,
        build_user_info_text(uid, user),
        reply_markup=build_user_detail_keyboard(uid, user)
    )


def _handle_ban(call, data):
    try:
        uid = int(data.replace("admin_ban_user_", ""))
    except ValueError:
        return
    ban_user(uid)
    bot.answer_callback_query(call.id, "✅ تم الحظر", show_alert=True)


def _handle_unban(call, data):
    try:
        uid = int(data.replace("admin_unban_user_", ""))
    except ValueError:
        return
    unban_user(uid)
    bot.answer_callback_query(call.id, "✅ تم فك الحظر", show_alert=True)


def _handle_grant_vip(call, data):
    try:
        uid = int(data.replace("admin_grant_vip_user_", ""))
    except ValueError:
        return
    u = get_or_create_user(uid)
    u["is_vip"] = True
    save_user(uid, u)
    bot.answer_callback_query(call.id, "💎 تم منح VIP", show_alert=True)
    try:
        bot.send_message(uid, "💎 <b>تهانينا!</b> VIP مُفعّل 🚀", parse_mode="HTML")
    except Exception:
        pass


def _handle_remove_vip(call, data):
    try:
        uid = int(data.replace("admin_remove_vip_", ""))
    except ValueError:
        return
    u = get_or_create_user(uid)
    u["is_vip"] = False
    save_user(uid, u)
    bot.answer_callback_query(call.id, "✅ تم إزالة VIP", show_alert=True)


def _handle_delete(call, data):
    try:
        uid = int(data.replace("admin_delete_user_", ""))
    except ValueError:
        return
    delete_user(uid)
    bot.answer_callback_query(call.id, "🗑️ تم الحذف", show_alert=True)


def _handle_give_sub_prompt(call, data):
    try:
        uid = int(data.replace("admin_give_sub_", ""))
    except ValueError:
        return
    bot.answer_callback_query(call.id)
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("⭐ أساسية", callback_data=f"admin_activate_basic_{uid}"),
        InlineKeyboardButton("💎 احترافية", callback_data=f"admin_activate_pro_{uid}"),
    )
    m.row(InlineKeyboardButton("👑 VIP", callback_data=f"admin_activate_vip_{uid}"))
    m.row(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))
    safe_edit(call, f"📅 <b>اختر الباقة</b> <code>{uid}</code>", reply_markup=m)


def _handle_activate_sub(call, data):
    # admin_activate_{plan}_{uid}
    parts = data.replace("admin_activate_", "").rsplit("_", 1)
    if len(parts) != 2:
        return

    plan_key, uid_str = parts
    try:
        uid = int(uid_str)
    except ValueError:
        return

    try:
        user = activate_subscription(uid, plan_key)
        plan = PRICING_PLANS.get(plan_key)
        if not plan:
            bot.answer_callback_query(call.id, "❌ باقة غير صالحة", show_alert=True)
            return

        bot.answer_callback_query(call.id, f"✅ {plan['name']}", show_alert=True)

        try:
            from datetime import datetime
            expires = datetime.fromisoformat(user["subscription"]["expires_at"])
            bot.send_message(
                uid,
                f"🎉 <b>تم تفعيل اشتراكك!</b>\n"
                f"📅 ينتهي: <code>{expires.strftime('%Y-%m-%d')}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    except Exception as e:
        logger.exception(f"activate_subscription error: {e}")
        bot.answer_callback_query(call.id, f"❌ {e}", show_alert=True)


def _handle_msg_user(call, chat_id, data):
    try:
        uid = int(data.replace("admin_msg_user_", ""))
    except ValueError:
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        chat_id,
        f"📨 <b>أرسل الرسالة لـ</b> <code>{uid}</code>:",
        parse_mode="HTML"
    )
    from ..steps.admin_steps import admin_msg_user_handler
    bot.register_next_step_handler(msg, lambda m: admin_msg_user_handler(m, uid))


def _handle_recent(call):
    users = get_all_users()
    users.sort(key=lambda u: u.get("created_at", ""), reverse=True)

    lines = ["🆕 <b>آخر 10 مستخدمين:</b>"]
    for u in users[:10]:
        uid = u.get("user_id")
        name = u.get("first_name", "Unknown")

        if is_admin(uid):
            icon = "👑"
        elif u.get("is_vip"):
            icon = "💎"
        elif u.get("is_banned"):
            icon = "🚫"
        else:
            icon = "👤"

        lines.append(f"{icon} <b>{h(name)}</b> — <code>{uid}</code>")

    bot.answer_callback_query(call.id)
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, "\n".join(lines), reply_markup=m)


def _handle_events(call):
    try:
        from admin_system import get_admin_events
        events = get_admin_events(limit=20)
    except Exception:
        events = []

    if not events:
        text = "📋 <b>سجل الأحداث</b>\n\n<i>لا يوجد أحداث بعد</i>"
    else:
        lines = ["📋 <b>آخر 20 حدث</b>\n━━━━━━━━━━━━━━━━━━\n"]
        for ev in events:
            ts = ev.get("time_str", "?")[11:19]
            admin_id = ev.get("admin_id", "?")
            etype = ev.get("type", "?")
            lines.append(f"• <code>{h(ts)}</code> — <code>{h(str(admin_id))[:10]}</code> — <b>{h(etype)}</b>")
        text = "\n".join(lines)

    bot.answer_callback_query(call.id)
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_activity_log(call):
    try:
        from admin_system import get_recent_activity
        activities = get_recent_activity(limit=20)
    except Exception:
        activities = []

    if not activities:
        text = "📡 <b>سجل الأنشطة</b>\n\n<i>لا يوجد</i>"
    else:
        lines = ["📡 <b>آخر 20 نشاط</b>\n━━━━━━━━━━━━━━━━━━\n"]
        for ev in activities:
            ts = ev.get("time_str", "?")[11:19]
            uid = ev.get("user_id", "?")
            action = ev.get("action", "?")
            lines.append(f"• <code>{h(ts)}</code> — <code>{h(str(uid))[:10]}</code> — <b>{h(action)}</b>")
        text = "\n".join(lines)

    bot.answer_callback_query(call.id)
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_clean_redis(call):
    bot.answer_callback_query(call.id, "🧹 جاري التنظيف...")
    try:
        from admin_system import clean_redis_cache
        result = clean_redis_cache()
        text = (
            "🧹 <b>تنظيف Redis</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ <b>تم حذف:</b> <code>{result['cleaned']}</code> مفتاح\n"
            f"❌ <b>أخطاء:</b> <code>{result['errors']}</code>\n"
        )
    except Exception as e:
        logger.exception(f"clean_redis error: {e}")
        text = f"❌ خطأ: {h(str(e)[:200])}"

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_export(call, chat_id):
    bot.answer_callback_query(call.id, "📥 جاري التصدير...")
    try:
        from admin_system import export_all_users
        json_data = export_all_users()

        if not json_data:
            safe_edit(call, "❌ فشل التصدير",
                      reply_markup=InlineKeyboardMarkup().add(
                          InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")))
            return

        import io
        buf = io.BytesIO(json_data.encode('utf-8'))
        buf.name = "users_export.json"
        bot.send_document(chat_id, buf, caption="📥 <b>تصدير كل المستخدمين</b>", parse_mode="HTML")

        safe_edit(call, "✅ تم إرسال الملف",
                  reply_markup=InlineKeyboardMarkup().add(
                      InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")))
    except Exception as e:
        logger.exception(f"export error: {e}")
        safe_edit(call, f"❌ خطأ: {h(str(e)[:200])}",
                  reply_markup=InlineKeyboardMarkup().add(
                      InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")))


def _handle_settings(call):
    bot.answer_callback_query(call.id)
    text = (
        "🔧 <b>إعدادات النظام</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⚙️ استخدم الأزرار للتحكم\n"
    )
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_maint_on(call, user_id):
    try:
        from admin_system import enable_maintenance
        enable_maintenance(admin_id=user_id)
        bot.answer_callback_query(call.id, "🔴 تم تفعيل الصيانة", show_alert=True)
        safe_edit(call, "🔴 <b>الصيانة مفعّلة</b>", reply_markup=build_admin_menu())
    except Exception as e:
        logger.exception(f"maint_on error: {e}")
        bot.answer_callback_query(call.id, f"❌ {e}", show_alert=True)


def _handle_maint_off(call, user_id):
    try:
        from admin_system import disable_maintenance
        disable_maintenance(admin_id=user_id)
        bot.answer_callback_query(call.id, "🟢 تم إيقاف الصيانة", show_alert=True)
        safe_edit(call, "🟢 <b>الصيانة متوقفة</b>", reply_markup=build_admin_menu())
    except Exception as e:
        logger.exception(f"maint_off error: {e}")
        bot.answer_callback_query(call.id, f"❌ {e}", show_alert=True)


def _handle_live(call):
    bot.answer_callback_query(call.id, "🔴 جاري التحديث...")
    try:
        from admin_system import build_live_monitor_text
        text = build_live_monitor_text()
    except Exception as e:
        text = f"❌ خطأ: {h(str(e)[:200])}"

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔄 تحديث", callback_data="admin_live"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_adv_stats(call):
    bot.answer_callback_query(call.id, "📊 جاري الحساب...")
    try:
        from admin_system import build_admin_stats_text as build_adv
        text = build_adv()
    except Exception:
        text = build_admin_stats_text()

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔄 تحديث", callback_data="admin_adv_stats"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_analytics(call):
    bot.answer_callback_query(call.id, "📈 جاري التحليل...")
    try:
        from admin_system import build_analytics_text
        text = build_analytics_text()
    except Exception as e:
        text = f"❌ خطأ: {h(str(e)[:200])}"

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔄 تحديث", callback_data="admin_analytics"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_top_users(call):
    bot.answer_callback_query(call.id, "👑 جاري الحساب...")
    try:
        from admin_system import build_top_users_text
        text = build_top_users_text()
    except Exception as e:
        text = f"❌ خطأ: {h(str(e)[:200])}"

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔄 تحديث", callback_data="admin_top_users"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


# ══════════════════════════════════════════════════
# Step: إضافة اشتراك
# ══════════════════════════════════════════════════
def _admin_add_sub_step(message):
    if not is_admin(message.chat.id):
        return

    try:
        parts = (message.text or "").strip().split("|")
        uid = int(parts[0].strip())
        plan_key = parts[1].strip()

        if plan_key not in PRICING_PLANS:
            bot.send_message(
                message.chat.id,
                f"❌ باقة غير صالحة. المتاح: {', '.join(PRICING_PLANS.keys())}",
                parse_mode="HTML"
            )
            return

        user = activate_subscription(uid, plan_key)
        plan = PRICING_PLANS[plan_key]
        bot.send_message(
            message.chat.id,
            f"✅ تم إعطاء <b>{plan['name']}</b> لـ <code>{uid}</code>",
            parse_mode="HTML"
        )

        try:
            from datetime import datetime
            expires = datetime.fromisoformat(user["subscription"]["expires_at"])
            bot.send_message(
                uid,
                f"🎉 <b>تم تفعيل اشتراكك!</b>\n"
                f"💎 الباقة: {plan['name']}\n"
                f"📅 ينتهي: <code>{expires.strftime('%Y-%m-%d')}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطأ: {h(str(e)[:200])}", parse_mode="HTML")
