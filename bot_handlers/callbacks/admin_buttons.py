# bot_handlers/callbacks/admin_buttons.py
# ============================================================
# Admin Buttons Handler — كل الـ Callbacks الجديدة
# ============================================================
# المسؤول عن:
# 1. وضع الصيانة
# 2. الإشعارات المخصصة
# 3. إدارة الجلسات
# 4. إعدادات البوت
# 5. قائمة الحظر
# 6. النسخ الاحتياطي
# 7. صحة النظام
# 8. التحليلات المتقدمة
# 9. البث الذكي
# ============================================================

import io
import json
import time
from datetime import datetime

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot, redis_client
from logging_config import get_logger
from imports_manager import is_admin

# ★ استيراد دوال admin_system ★
from admin_system import (
    # Maintenance
    is_maintenance, enable_maintenance, disable_maintenance,
    set_maintenance_message, get_maintenance_duration,
    get_maintenance_remaining, get_maintenance_exempt,
    get_maintenance_message, build_maintenance_status_text,
    # Notifications
    notify_admin, get_admin_ids, send_custom_notification,
    # Sessions
    get_active_sessions, get_online_devices, kill_session,
    build_sessions_text,
    # Settings
    get_bot_setting, set_bot_setting, get_all_settings,
    set_tool_price, get_tool_prices,
    # Ban
    ban_user_permanent, unban_user, unban_all,
    get_banned_users, ban_ip, unban_ip, get_banned_ips,
    build_ban_list_text,
    # Backup
    backup_redis_to_json, restore_redis_from_json,
    build_backup_text,
    # Health
    get_system_health, build_system_health_text,
    # Analytics
    get_tool_usage_today, get_users_growth, get_top_users,
    get_conversion_stats, get_recent_activity,
    build_advanced_analytics_text,
    # Broadcast
    broadcast_to_group,
    # Utils
    format_uptime
)

logger = get_logger("admin_buttons")


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════
def _safe_edit(call, text, reply_markup=None, parse_mode="HTML"):
    """تعديل آمن للرسالة"""
    try:
        bot.edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        if "message to edit not found" in err or "message can't be edited" in err:
            try:
                bot.send_message(
                    call.message.chat.id, text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True
                )
                return True
            except Exception as e2:
                logger.warning(f"_safe_edit fallback error: {e2}")
        else:
            logger.debug(f"_safe_edit error: {e}")
        return False


def _answer(call, text="", show_alert=False):
    """رد سريع على call"""
    try:
        bot.answer_callback_query(call.id, text=text, show_alert=show_alert)
    except Exception:
        pass


def _build_maintenance_panel():
    """لوحة وضع الصيانة"""
    m = InlineKeyboardMarkup()

    if is_maintenance():
        # ★ مفعّل — اعرض إيقاف ★
        m.row(
            InlineKeyboardButton("✅ إيقاف الصيانة", callback_data="maint_disable")
        )
        m.row(
            InlineKeyboardButton("📝 تعديل الرسالة", callback_data="maint_edit_msg"),
            InlineKeyboardButton("🔄 تحديث", callback_data="admin_maintenance")
        )
        m.row(
            InlineKeyboardButton("🛡️ تغيير المستثنى", callback_data="maint_change_exempt")
        )
    else:
        # ★ معطّل — اعرض تفعيل ★
        m.row(
            InlineKeyboardButton("▶️ تفعيل الصيانة", callback_data="maint_enable")
        )
        m.row(
            InlineKeyboardButton("⏱️ تفعيل 30 دقيقة", callback_data="maint_enable_30"),
            InlineKeyboardButton("⏱️ تفعيل ساعة", callback_data="maint_enable_60")
        )
        m.row(
            InlineKeyboardButton("⏱️ تفعيل 3 ساعات", callback_data="maint_enable_180"),
            InlineKeyboardButton("⏱️ تفعيل 24 ساعة", callback_data="maint_enable_1440")
        )
        m.row(
            InlineKeyboardButton("📝 رسالة مخصصة + تفعيل", callback_data="maint_custom")
        )
        m.row(
            InlineKeyboardButton("🛡️ خيارات المستثنى", callback_data="maint_change_exempt")
        )

    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))
    return m


def _build_exempt_panel():
    """لوحة اختيار المستثنى من الصيانة"""
    m = InlineKeyboardMarkup()
    current = get_maintenance_exempt()

    opts = [
        ("all", "🌐 كل المستخدمين"),
        ("admin_only", "👑 الأدمن فقط"),
        ("vip", "💎 VIP + الأدمن"),
        ("none", "🚫 لا أحد (حتى الأدمن)")
    ]

    for key, label in opts:
        icon = "✅" if key == current else "⚪"
        m.row(InlineKeyboardButton(
            f"{icon} {label}",
            callback_data=f"maint_set_exempt_{key}"
        ))

    m.row(InlineKeyboardButton("🔙 رجوع", callback_data="admin_maintenance"))
    return m


# ══════════════════════════════════════════════════════════════
# [1] ★★★ MAINTENANCE HANDLERS ★★★
# ══════════════════════════════════════════════════════════════
def handle_maintenance(call):
    """لوحة الصيانة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    text = build_maintenance_status_text()
    _safe_edit(call, text, reply_markup=_build_maintenance_panel())


def handle_maint_enable(call):
    """تفعيل الصيانة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    admin_id = call.from_user.id

    if is_maintenance():
        _answer(call, "⚠️ الصيانة مفعّلة بالفعل", True)
        return

    success = enable_maintenance(
        custom_msg=None,
        admin_id=admin_id,
        duration_minutes=0,
        exempt_mode=get_maintenance_exempt()
    )

    if success:
        _answer(call, "✅ تم تفعيل الصيانة", True)
        text = build_maintenance_status_text()
        _safe_edit(call, text, reply_markup=_build_maintenance_panel())
    else:
        _answer(call, "❌ فشل التفعيل", True)


def handle_maint_enable_with_duration(call, minutes):
    """تفعيل الصيانة لمدة محددة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    admin_id = call.from_user.id

    if is_maintenance():
        _answer(call, "⚠️ الصيانة مفعّلة بالفعل", True)
        return

    success = enable_maintenance(
        custom_msg=None,
        admin_id=admin_id,
        duration_minutes=minutes,
        exempt_mode=get_maintenance_exempt()
    )

    if success:
        duration_text = format_uptime(minutes * 60)
        _answer(call, f"✅ الصيانة مفعّلة لمدة {duration_text}", True)
        text = build_maintenance_status_text()
        _safe_edit(call, text, reply_markup=_build_maintenance_panel())
    else:
        _answer(call, "❌ فشل التفعيل", True)


def handle_maint_disable(call):
    """تعطيل الصيانة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    admin_id = call.from_user.id

    if not is_maintenance():
        _answer(call, "⚠️ الصيانة معطلة بالفعل", True)
        return

    success = disable_maintenance(admin_id=admin_id)

    if success:
        _answer(call, "✅ تم إيقاف الصيانة", True)
        text = build_maintenance_status_text()
        _safe_edit(call, text, reply_markup=_build_maintenance_panel())
    else:
        _answer(call, "❌ فشل الإيقاف", True)


def handle_maint_edit_msg(call):
    """تعديل رسالة الصيانة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    current = get_maintenance_message() or ""

    msg = bot.send_message(
        call.message.chat.id,
        f"📝 <b>تعديل رسالة الصيانة</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"الرسالة الحالية:\n<pre>{current[:300]}</pre>\n\n"
        f"أرسل الرسالة الجديدة:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("❌ إلغاء", callback_data="admin_maintenance")
        )
    )

    bot.register_next_step_handler(msg, _process_maint_msg)


def _process_maint_msg(message):
    """معالجة رسالة الصيانة الجديدة"""
    if not is_admin(message.chat.id):
        return

    if not message.text:
        bot.send_message(message.chat.id, "❌ أرسل نصاً صحيحاً")
        return

    text = message.text.strip()
    if len(text) < 5:
        bot.send_message(message.chat.id, "❌ الرسالة قصيرة جداً")
        return

    success = set_maintenance_message(text, admin_id=message.chat.id)

    if success:
        bot.send_message(
            message.chat.id,
            "✅ تم تحديث رسالة الصيانة",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔙 رجوع", callback_data="admin_maintenance")
            )
        )
    else:
        bot.send_message(message.chat.id, "❌ فشل التحديث")


def handle_maint_custom(call):
    """تفعيل صيانة برسالة مخصصة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    msg = bot.send_message(
        call.message.chat.id,
        "📝 <b>صيانة برسالة مخصصة</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "أرسل الرسالة اللي هتظهر للمستخدمين\n"
        "مثال:\n"
        "<code>🔧 البوت تحت التحديث\nالرجاء المحاولة بعد 30 دقيقة</code>",
        parse_mode="HTML"
    )

    bot.register_next_step_handler(msg, _process_maint_custom_msg)


def _process_maint_custom_msg(message):
    """معالجة رسالة الصيانة المخصصة + التفعيل"""
    if not is_admin(message.chat.id):
        return

    if not message.text:
        bot.send_message(message.chat.id, "❌ أرسل نصاً صحيحاً")
        return

    custom_msg = message.text.strip()
    if len(custom_msg) < 5:
        bot.send_message(message.chat.id, "❌ الرسالة قصيرة جداً")
        return

    success = enable_maintenance(
        custom_msg=custom_msg,
        admin_id=message.chat.id,
        duration_minutes=0,
        exempt_mode=get_maintenance_exempt()
    )

    if success:
        bot.send_message(
            message.chat.id,
            "✅ تم تفعيل الصيانة برسالة مخصصة",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🔧 لوحة الصيانة", callback_data="admin_maintenance")
            )
        )
    else:
        bot.send_message(message.chat.id, "❌ فشل التفعيل")


def handle_maint_change_exempt(call):
    """تغيير المستثنى من الصيانة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    text = (
        "🛡️ <b>اختيار المستثنى من الصيانة</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "اختر من سيتمكن من استخدام البوت أثناء الصيانة:"
    )
    _safe_edit(call, text, reply_markup=_build_exempt_panel())


def handle_maint_set_exempt(call, mode):
    """تعيين وضع المستثنى"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    if redis_client:
        try:
            redis_client.set("system:maintenance_exempt", mode)
            _answer(call, f"✅ تم التعيين: {mode}", True)
        except Exception:
            _answer(call, "❌ فشل التعيين", True)
            return
    else:
        _answer(call, "❌ Redis غير متصل", True)
        return

    text = (
        "🛡️ <b>اختيار المستثنى من الصيانة</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "اختر من سيتمكن من استخدام البوت أثناء الصيانة:"
    )
    _safe_edit(call, text, reply_markup=_build_exempt_panel())


# ══════════════════════════════════════════════════════════════
# [2] ★★★ HEALTH ★★★
# ══════════════════════════════════════════════════════════════
def handle_health(call):
    """صحة النظام"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    text = build_system_health_text()

    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton("🔄 تحديث", callback_data="admin_health"))
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


# ══════════════════════════════════════════════════════════════
# [3] ★★★ SESSIONS ★★★
# ══════════════════════════════════════════════════════════════
def handle_sessions(call):
    """الجلسات النشطة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    text = build_sessions_text()

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("🔄 تحديث", callback_data="admin_sessions"),
        InlineKeyboardButton("📱 الأجهزة", callback_data="admin_devices")
    )
    m.row(InlineKeyboardButton("🧹 حذف كل الجلسات", callback_data="admin_sessions_kill_all"))
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


def handle_devices(call):
    """الأجهزة المتصلة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    devices = get_online_devices()

    if not devices:
        text = "📱 <b>الأجهزة المتصلة</b>\n\n<i>لا يوجد أجهزة متصلة حالياً</i>"
    else:
        text = f"📱 <b>الأجهزة المتصلة ({len(devices)})</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for d in devices[:15]:
            type_icon = "📱" if d["type"] == "apk" else "🌐"
            name = d.get("name", "?")[:20]
            model = d.get("model", "?")[:20]
            ago = format_uptime(time.time() - d.get("last_seen", time.time()))

            text += (
                f"{type_icon} <b>{name}</b>\n"
                f"   📲 <code>{model}</code>\n"
                f"   ⏱️ قبل <code>{ago}</code>\n\n"
            )

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("🔄 تحديث", callback_data="admin_devices"),
        InlineKeyboardButton("👁️ الجلسات", callback_data="admin_sessions")
    )
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


def handle_sessions_kill_all(call):
    """حذف كل الجلسات"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    # ★ تأكيد ★
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("⚠️ نعم، احذف الكل", callback_data="admin_sessions_kill_all_confirm"),
        InlineKeyboardButton("❌ إلغاء", callback_data="admin_sessions")
    )

    _answer(call)
    _safe_edit(call, 
        "⚠️ <b>تأكيد الحذف</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "هل أنت متأكد من حذف كل الجلسات؟\n"
        "هذا الإجراء لا يمكن التراجع عنه!",
        reply_markup=m
    )


def handle_sessions_kill_all_confirm(call):
    """تأكيد حذف كل الجلسات"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    if not redis_client:
        _answer(call, "❌ Redis غير متصل", True)
        return

    killed = 0
    try:
        # ★ جلسات Silent ★
        for key in redis_client.scan_iter(match="silent:*", count=100):
            if isinstance(key, bytes):
                key = key.decode()
            session_id = key.replace("silent:", "")
            redis_client.delete(key)
            redis_client.delete(f"silent_data:{session_id}")
            killed += 1

        # ★ جلسات Facebook/Instagram ★
        for key in redis_client.scan_iter(match="se_session:*", count=100):
            if isinstance(key, bytes):
                key = key.decode()
            redis_client.delete(key)
            killed += 1

    except Exception as e:
        logger.warning(f"kill_all error: {e}")

    _answer(call, f"✅ تم حذف {killed} جلسة", True)
    handle_sessions(call)


# ══════════════════════════════════════════════════════════════
# [4] ★★★ SETTINGS ★★★
# ══════════════════════════════════════════════════════════════
def handle_settings(call):
    """إعدادات البوت"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    settings = get_all_settings()
    prices = get_tool_prices()

    text = (
        "⚙️ <b>إعدادات البوت</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>الإعدادات المحفوظة:</b> <code>{len(settings)}</code>\n"
        f"💰 <b>أسعار مخصصة:</b> <code>{len(prices)}</code>\n\n"
        "━━━ 🎯 <b>الإجراءات</b> ━━━\n"
        "• تعديل رسالة ترحيب\n"
        "• تعديل رسالة مساعدة\n"
        "• تعديل سعر أداة\n"
        "• تعديل نقاط الترحيب\n"
    )

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("💬 رسالة ترحيب", callback_data="setting_edit_welcome"),
        InlineKeyboardButton("❓ رسالة مساعدة", callback_data="setting_edit_help")
    )
    m.row(
        InlineKeyboardButton("💰 سعر أداة", callback_data="setting_edit_tool_price"),
        InlineKeyboardButton("🎁 نقاط ترحيب", callback_data="setting_edit_welcome_points")
    )
    m.row(
        InlineKeyboardButton("🎁 نقاط إحالة", callback_data="setting_edit_ref_points")
    )
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


def handle_setting_edit_welcome(call):
    """تعديل رسالة الترحيب"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    current = get_bot_setting("welcome_msg", "غير محدد")

    msg = bot.send_message(
        call.message.chat.id,
        f"💬 <b>تعديل رسالة الترحيب</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"الحالية:\n<pre>{current[:300]}</pre>\n\n"
        f"أرسل الرسالة الجديدة:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_setting_welcome)


def _process_setting_welcome(message):
    if not is_admin(message.chat.id):
        return
    if not message.text or len(message.text.strip()) < 5:
        bot.send_message(message.chat.id, "❌ نص قصير جداً")
        return

    set_bot_setting("welcome_msg", message.text.strip())
    bot.send_message(
        message.chat.id,
        "✅ تم تحديث رسالة الترحيب",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
        )
    )


def handle_setting_edit_help(call):
    """تعديل رسالة المساعدة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    current = get_bot_setting("help_msg", "غير محدد")

    msg = bot.send_message(
        call.message.chat.id,
        f"❓ <b>تعديل رسالة المساعدة</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"الحالية:\n<pre>{current[:300]}</pre>\n\n"
        f"أرسل الرسالة الجديدة:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_setting_help)


def _process_setting_help(message):
    if not is_admin(message.chat.id):
        return
    if not message.text or len(message.text.strip()) < 5:
        bot.send_message(message.chat.id, "❌ نص قصير جداً")
        return

    set_bot_setting("help_msg", message.text.strip())
    bot.send_message(
        message.chat.id,
        "✅ تم تحديث رسالة المساعدة",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
        )
    )


def handle_setting_edit_tool_price(call):
    """تعديل سعر أداة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    # ★ جلب الأسعار الحالية ★
    try:
        from points_system import TOOL_PRICES, TOOL_NAMES_AR
    except Exception:
        TOOL_PRICES = {}
        TOOL_NAMES_AR = {}

    custom_prices = get_tool_prices()

    text = "💰 <b>تعديل سعر أداة</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

    m = InlineKeyboardMarkup()
    for tool_key, default_price in TOOL_PRICES.items():
        current = custom_prices.get(tool_key, default_price)
        name = TOOL_NAMES_AR.get(tool_key, tool_key)[:20]
        marker = "⭐" if tool_key in custom_prices else "⚪"
        m.row(InlineKeyboardButton(
            f"{marker} {name} - {current}",
            callback_data=f"setting_set_price_{tool_key}"
        ))

    m.row(InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings"))

    _safe_edit(call, text, reply_markup=m)


def handle_setting_set_price(call, tool_key):
    """تعيين سعر أداة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    msg = bot.send_message(
        call.message.chat.id,
        f"💰 <b>سعر جديد للأداة: {tool_key}</b>\n\n"
        f"أرسل السعر الجديد (رقم فقط):",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(
        msg,
        lambda m: _process_set_tool_price(m, tool_key)
    )


def _process_set_tool_price(message, tool_key):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        return

    try:
        price = int(message.text.strip())
        if price < 0 or price > 100000:
            bot.send_message(message.chat.id, "❌ السعر غير منطقي")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ أرسل رقماً صحيحاً")
        return

    set_tool_price(tool_key, price)
    bot.send_message(
        message.chat.id,
        f"✅ تم تحديث سعر <code>{tool_key}</code> إلى <code>{price}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
        )
    )


def handle_setting_edit_welcome_points(call):
    """تعديل نقاط الترحيب"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    current = get_bot_setting("welcome_points", "25")

    msg = bot.send_message(
        call.message.chat.id,
        f"🎁 <b>نقاط الترحيب</b>\n\n"
        f"الحالية: <code>{current}</code>\n\n"
        f"أرسل العدد الجديد:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_welcome_points)


def _process_welcome_points(message):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        return

    try:
        points = int(message.text.strip())
        if points < 0 or points > 10000:
            bot.send_message(message.chat.id, "❌ العدد غير منطقي (0-10000)")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ أرسل رقماً صحيحاً")
        return

    set_bot_setting("welcome_points", points)
    bot.send_message(
        message.chat.id,
        f"✅ نقاط الترحيب: <code>{points}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
        )
    )


def handle_setting_edit_ref_points(call):
    """تعديل نقاط الإحالة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    current = get_bot_setting("ref_points", "10")

    msg = bot.send_message(
        call.message.chat.id,
        f"🎁 <b>نقاط الإحالة</b>\n\n"
        f"الحالية: <code>{current}</code>\n\n"
        f"أرسل العدد الجديد:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_ref_points)


def _process_ref_points(message):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        return

    try:
        points = int(message.text.strip())
        if points < 0 or points > 10000:
            bot.send_message(message.chat.id, "❌ العدد غير منطقي")
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ أرسل رقماً صحيحاً")
        return

    set_bot_setting("ref_points", points)
    bot.send_message(
        message.chat.id,
        f"✅ نقاط الإحالة: <code>{points}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 رجوع", callback_data="admin_settings")
        )
    )


# ══════════════════════════════════════════════════════════════
# [5] ★★★ BAN LIST ★★★
# ══════════════════════════════════════════════════════════════
def handle_ban_list(call):
    """قائمة الحظر"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    text = build_ban_list_text()

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("🔄 تحديث", callback_data="admin_ban_list"),
        InlineKeyboardButton("➕ حظر مستخدم", callback_data="admin_ban_add")
    )
    m.row(
        InlineKeyboardButton("🌐 حظر IP", callback_data="admin_ban_ip"),
        InlineKeyboardButton("🔓 فك حظر IP", callback_data="admin_unban_ip")
    )
    m.row(
        InlineKeyboardButton("🧹 فك حظر الكل", callback_data="admin_unban_all")
    )
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


def handle_ban_add(call):
    """إضافة حظر"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    msg = bot.send_message(
        call.message.chat.id,
        "🚫 <b>حظر مستخدم</b>\n\n"
        "أرسل الـ ID:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_ban_user)


def _process_ban_user(message):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        return

    try:
        uid = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "❌ أرسل ID صحيح")
        return

    ban_user_permanent(uid, reason="Admin manual ban")
    bot.send_message(
        message.chat.id,
        f"✅ تم حظر <code>{uid}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 قائمة الحظر", callback_data="admin_ban_list")
        )
    )


def handle_ban_ip(call):
    """حظر IP"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    msg = bot.send_message(
        call.message.chat.id,
        "🌐 <b>حظر IP</b>\n\n"
        "أرسل الـ IP:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_ban_ip)


def _process_ban_ip(message):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        return

    ip = message.text.strip()
    if not ip:
        bot.send_message(message.chat.id, "❌ IP غير صحيح")
        return

    ban_ip(ip)
    bot.send_message(
        message.chat.id,
        f"✅ تم حظر <code>{ip}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 قائمة الحظر", callback_data="admin_ban_list")
        )
    )


def handle_unban_ip(call):
    """فك حظر IP"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    msg = bot.send_message(
        call.message.chat.id,
        "🔓 <b>فك حظر IP</b>\n\n"
        "أرسل الـ IP:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_unban_ip)


def _process_unban_ip(message):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        return

    ip = message.text.strip()
    unban_ip(ip)
    bot.send_message(
        message.chat.id,
        f"✅ تم فك حظر <code>{ip}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 قائمة الحظر", callback_data="admin_ban_list")
        )
    )


def handle_unban_all(call):
    """فك حظر الكل"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    count = unban_all()
    _answer(call, f"✅ تم فك حظر {count} مستخدم", True)
    handle_ban_list(call)


# ══════════════════════════════════════════════════════════════
# [6] ★★★ BACKUP ★★★
# ══════════════════════════════════════════════════════════════
def handle_backup(call):
    """لوحة النسخ الاحتياطي"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    text = build_backup_text()

    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton("💾 إنشاء نسخة", callback_data="backup_create"))
    m.row(InlineKeyboardButton("📥 تنزيل آخر نسخة", callback_data="backup_download_latest"))
    m.row(InlineKeyboardButton("📋 قائمة النسخ", callback_data="backup_list"))
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


def handle_backup_create(call):
    """إنشاء نسخة احتياطية"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call, "⏳ جاري الإنشاء...")

    def _do_backup():
        try:
            backup = backup_redis_to_json()
            if not backup:
                bot.send_message(
                    call.message.chat.id,
                    "❌ فشل إنشاء النسخة",
                    reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton("🔙 رجوع", callback_data="admin_backup")
                    )
                )
                return

            # ★ احفظ النسخة في Redis ★
            backup_id = f"backup_{int(time.time())}"
            backup_json = json.dumps(backup, ensure_ascii=False)

            if redis_client:
                redis_client.setex(
                    f"system:backup:{backup_id}",
                    86400 * 30,  # 30 يوم
                    backup_json
                )

                # ★ احفظ ID في قائمة ★
                redis_client.lpush("system:backups_list", backup_id)
                redis_client.ltrim("system:backups_list", 0, 19)  # آخر 20 نسخة

            # ★ ابعت ملف ★
            buf = io.BytesIO(backup_json.encode('utf-8'))
            buf.name = f"backup_{backup_id}.json"

            bot.send_document(
                call.message.chat.id,
                buf,
                caption=(
                    f"✅ <b>تم إنشاء النسخة</b>\n"
                    f"🆔 <code>{backup_id}</code>\n"
                    f"🔑 <b>المفاتيح:</b> <code>{backup.get('total_keys', 0)}</code>\n"
                    f"📊 <b>الحجم:</b> <code>{len(backup_json) / 1024:.1f} KB</code>"
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 رجوع", callback_data="admin_backup")
                )
            )
        except Exception as e:
            logger.exception(f"backup error: {e}")
            bot.send_message(
                call.message.chat.id,
                f"❌ خطأ: {str(e)[:200]}",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🔙 رجوع", callback_data="admin_backup")
                )
            )

    import threading
    threading.Thread(target=_do_backup, daemon=True).start()


def handle_backup_download_latest(call):
    """تنزيل آخر نسخة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    if not redis_client:
        _answer(call, "❌ Redis غير متصل", True)
        return

    try:
        latest_ids = redis_client.lrange("system:backups_list", 0, 0) or []
        if not latest_ids:
            _answer(call, "❌ لا يوجد نسخ محفوظة", True)
            return

        backup_id = latest_ids[0]
        if isinstance(backup_id, bytes):
            backup_id = backup_id.decode()

        backup_json = redis_client.get(f"system:backup:{backup_id}")
        if not backup_json:
            _answer(call, "❌ النسخة غير موجودة", True)
            return

        if isinstance(backup_json, bytes):
            backup_json = backup_json.decode()

        buf = io.BytesIO(backup_json.encode('utf-8'))
        buf.name = f"backup_{backup_id}.json"

        bot.send_document(
            call.message.chat.id,
            buf,
            caption=f"📥 <b>آخر نسخة:</b> <code>{backup_id}</code>",
            parse_mode="HTML"
        )
        _answer(call)
    except Exception as e:
        logger.exception(f"download backup error: {e}")
        _answer(call, "❌ فشل التنزيل", True)


def handle_backup_list(call):
    """قائمة النسخ"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    if not redis_client:
        _answer(call, "❌ Redis غير متصل", True)
        return

    try:
        ids = redis_client.lrange("system:backups_list", 0, 19) or []
        if not ids:
            _answer(call, "❌ لا يوجد نسخ", True)
            return

        text = f"📋 <b>قائمة النسخ ({len(ids)})</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        m = InlineKeyboardMarkup()

        for bid in ids[:10]:
            if isinstance(bid, bytes):
                bid = bid.decode()
            text += f"• <code>{bid}</code>\n"
            m.row(InlineKeyboardButton(
                f"📥 {bid[:20]}",
                callback_data=f"backup_download_{bid}"
            ))

        m.row(InlineKeyboardButton("🔙 رجوع", callback_data="admin_backup"))
        _safe_edit(call, text, reply_markup=m)

    except Exception as e:
        logger.exception(f"backup list error: {e}")
        _answer(call, "❌ فشل", True)


def handle_backup_download(call, backup_id):
    """تنزيل نسخة محددة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    if not redis_client:
        _answer(call, "❌ Redis غير متصل", True)
        return

    try:
        backup_json = redis_client.get(f"system:backup:{backup_id}")
        if not backup_json:
            _answer(call, "❌ النسخة غير موجودة", True)
            return

        if isinstance(backup_json, bytes):
            backup_json = backup_json.decode()

        buf = io.BytesIO(backup_json.encode('utf-8'))
        buf.name = f"backup_{backup_id}.json"

        bot.send_document(
            call.message.chat.id,
            buf,
            caption=f"📥 <b>{backup_id}</b>",
            parse_mode="HTML"
        )
        _answer(call)
    except Exception as e:
        logger.exception(f"backup download error: {e}")
        _answer(call, "❌ فشل التنزيل", True)


# ══════════════════════════════════════════════════════════════
# [7] ★★★ ANALYTICS ★★★
# ══════════════════════════════════════════════════════════════
def handle_advanced_analytics(call):
    """التحليلات المتقدمة"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    text = build_advanced_analytics_text()

    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton("🔄 تحديث", callback_data="admin_analytics"))
    m.row(
        InlineKeyboardButton("📈 نمو المستخدمين", callback_data="admin_growth"),
        InlineKeyboardButton("🏆 أعلى المستخدمين", callback_data="admin_top_users")
    )
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


def handle_growth(call):
    """نمو المستخدمين"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    growth = get_users_growth(7)

    text = "📈 <b>نمو المستخدمين (آخر 7 أيام)</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

    if not growth:
        text += "<i>لا يوجد بيانات</i>"
    else:
        max_val = max(growth.values()) if growth else 1
        for date, count in sorted(growth.items()):
            bar_len = int((count / max_val) * 20) if max_val > 0 else 0
            bar = "█" * bar_len
            text += f"<code>{date}</code>\n{bar} <b>{count}</b>\n\n"

    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton("🔄 تحديث", callback_data="admin_growth"))
    m.row(InlineKeyboardButton("🔙 رجوع", callback_data="admin_analytics"))

    _safe_edit(call, text, reply_markup=m)


# ══════════════════════════════════════════════════════════════
# [8] ★★★ SMART BROADCAST ★★★
# ══════════════════════════════════════════════════════════════
def handle_smart_broadcast(call):
    """البث الذكي"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    text = (
        "📢 <b>البث الذكي</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "اختر المجموعة المستهدفة:"
    )

    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton("🌐 كل المستخدمين", callback_data="sbroadcast_all"))
    m.row(InlineKeyboardButton("💎 VIP فقط", callback_data="sbroadcast_vip"))
    m.row(InlineKeyboardButton("🟢 النشطين (24 ساعة)", callback_data="sbroadcast_active"))
    m.row(InlineKeyboardButton("🚫 المحظورين", callback_data="sbroadcast_banned"))
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


def handle_sbroadcast_group(call, group):
    """اختيار مجموعة البث"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    msg = bot.send_message(
        call.message.chat.id,
        f"📢 <b>البث لـ: {group}</b>\n\n"
        f"أرسل نص الرسالة:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, lambda m: _process_sbroadcast(m, group))


def _process_sbroadcast(message, group):
    if not is_admin(message.chat.id):
        return
    if not message.text or len(message.text.strip()) < 3:
        bot.send_message(message.chat.id, "❌ نص قصير")
        return

    text = message.text.strip()

    bot.send_message(
        message.chat.id,
        f"⏳ <b>جاري البث لـ {group}...</b>",
        parse_mode="HTML"
    )

    try:
        broadcast_to_group(group, text, admin_id=message.chat.id)
    except Exception as e:
        logger.exception(f"broadcast error: {e}")
        bot.send_message(message.chat.id, f"❌ فشل: {str(e)[:200]}")


# ══════════════════════════════════════════════════════════════
# [9] ★★★ CUSTOM NOTIFICATION ★★★
# ══════════════════════════════════════════════════════════════
def handle_custom_notify(call):
    """إشعار مخصص"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)

    text = (
        "✉️ <b>إشعار مخصص</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "اختر طريقة الإرسال:"
    )

    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton("👤 مستخدم واحد", callback_data="cnotify_single"))
    m.row(InlineKeyboardButton("👥 عدة مستخدمين", callback_data="cnotify_multi"))
    m.row(InlineKeyboardButton("📋 قائمة IDs", callback_data="cnotify_list"))
    m.row(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))

    _safe_edit(call, text, reply_markup=m)


def handle_cnotify_single(call):
    """إشعار لمستخدم واحد"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    msg = bot.send_message(
        call.message.chat.id,
        "👤 <b>إشعار لمستخدم واحد</b>\n\nأرسل ID المستخدم:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_cnotify_id)


def _process_cnotify_id(message):
    if not is_admin(message.chat.id):
        return
    try:
        uid = int(message.text.strip())
    except Exception:
        bot.send_message(message.chat.id, "❌ ID غير صحيح")
        return

    msg = bot.send_message(
        message.chat.id,
        f"✉️ أرسل الرسالة للمستخدم <code>{uid}</code>:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, lambda m: _process_cnotify_send(m, [uid]))


def handle_cnotify_multi(call):
    """إشعار لعدة مستخدمين"""
    if not is_admin(call.from_user.id):
        _answer(call, "❌ للأدمن فقط", True)
        return

    _answer(call)
    msg = bot.send_message(
        call.message.chat.id,
        "👥 <b>إشعار لعدة مستخدمين</b>\n\n"
        "أرسل IDs مفصولة بفواصل:\n"
        "<code>123456, 789012, 345678</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, _process_cnotify_multi)


def _process_cnotify_multi(message):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        return

    try:
        ids = [int(x.strip()) for x in message.text.split(",") if x.strip().isdigit()]
        if not ids:
            bot.send_message(message.chat.id, "❌ لم يتم العثور على IDs صحيحة")
            return
    except Exception:
        bot.send_message(message.chat.id, "❌ صيغة خاطئة")
        return

    msg = bot.send_message(
        message.chat.id,
        f"✉️ أرسل الرسالة لـ <code>{len(ids)}</code> مستخدم:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, lambda m: _process_cnotify_send(m, ids))


def _process_cnotify_send(message, ids):
    if not is_admin(message.chat.id):
        return
    if not message.text or len(message.text.strip()) < 3:
        bot.send_message(message.chat.id, "❌ نص قصير")
        return

    text = message.text.strip()

    bot.send_message(
        message.chat.id,
        f"⏳ <b>جاري الإرسال لـ {len(ids)} مستخدم...</b>",
        parse_mode="HTML"
    )

    try:
        sent = send_custom_notification(ids, text, admin_id=message.chat.id)
    except Exception as e:
        logger.exception(f"custom notify error: {e}")
        bot.send_message(message.chat.id, f"❌ فشل: {str(e)[:200]}")


# ══════════════════════════════════════════════════════════════
# [10] MAIN ROUTER
# ══════════════════════════════════════════════════════════════
def handle(call, chat_id, user_id, data):
    """
    المعالج الرئيسي لكل الـ callbacks الجديدة
    """
    # ★ فحص الأدمن ★
    if not is_admin(user_id):
        _answer(call, "❌ للأدمن فقط", True)
        return True

    # ═══ صيانة ═══
    if data == "admin_maintenance":
        handle_maintenance(call)
        return True

    if data == "maint_enable":
        handle_maint_enable(call)
        return True

    if data == "maint_enable_30":
        handle_maint_enable_with_duration(call, 30)
        return True

    if data == "maint_enable_60":
        handle_maint_enable_with_duration(call, 60)
        return True

    if data == "maint_enable_180":
        handle_maint_enable_with_duration(call, 180)
        return True

    if data == "maint_enable_1440":
        handle_maint_enable_with_duration(call, 1440)
        return True

    if data == "maint_disable":
        handle_maint_disable(call)
        return True

    if data == "maint_edit_msg":
        handle_maint_edit_msg(call)
        return True

    if data == "maint_custom":
        handle_maint_custom(call)
        return True

    if data == "maint_change_exempt":
        handle_maint_change_exempt(call)
        return True

    if data.startswith("maint_set_exempt_"):
        mode = data.replace("maint_set_exempt_", "")
        handle_maint_set_exempt(call, mode)
        return True

    # ═══ صحة ═══
    if data == "admin_health":
        handle_health(call)
        return True

    # ═══ جلسات ═══
    if data == "admin_sessions":
        handle_sessions(call)
        return True

    if data == "admin_devices":
        handle_devices(call)
        return True

    if data == "admin_sessions_kill_all":
        handle_sessions_kill_all(call)
        return True

    if data == "admin_sessions_kill_all_confirm":
        handle_sessions_kill_all_confirm(call)
        return True

    # ═══ إعدادات ═══
    if data == "admin_settings":
        handle_settings(call)
        return True

    if data == "setting_edit_welcome":
        handle_setting_edit_welcome(call)
        return True

    if data == "setting_edit_help":
        handle_setting_edit_help(call)
        return True

    if data == "setting_edit_tool_price":
        handle_setting_edit_tool_price(call)
        return True

    if data.startswith("setting_set_price_"):
        tool_key = data.replace("setting_set_price_", "")
        handle_setting_set_price(call, tool_key)
        return True

    if data == "setting_edit_welcome_points":
        handle_setting_edit_welcome_points(call)
        return True

    if data == "setting_edit_ref_points":
        handle_setting_edit_ref_points(call)
        return True

    # ═══ حظر ═══
    if data == "admin_ban_list":
        handle_ban_list(call)
        return True

    if data == "admin_ban_add":
        handle_ban_add(call)
        return True

    if data == "admin_ban_ip":
        handle_ban_ip(call)
        return True

    if data == "admin_unban_ip":
        handle_unban_ip(call)
        return True

    if data == "admin_unban_all":
        handle_unban_all(call)
        return True

    # ═══ نسخ احتياطي ═══
    if data == "admin_backup":
        handle_backup(call)
        return True

    if data == "backup_create":
        handle_backup_create(call)
        return True

    if data == "backup_download_latest":
        handle_backup_download_latest(call)
        return True

    if data == "backup_list":
        handle_backup_list(call)
        return True

    if data.startswith("backup_download_"):
        backup_id = data.replace("backup_download_", "")
        handle_backup_download(call, backup_id)
        return True

    # ═══ تحليلات ═══
    if data == "admin_analytics":
        handle_advanced_analytics(call)
        return True

    if data == "admin_growth":
        handle_growth(call)
        return True

    # ═══ بث ذكي ═══
    if data == "admin_smart_broadcast":
        handle_smart_broadcast(call)
        return True

    if data.startswith("sbroadcast_"):
        group = data.replace("sbroadcast_", "")
        handle_sbroadcast_group(call, group)
        return True

    # ═══ إشعار مخصص ═══
    if data == "admin_custom_notify":
        handle_custom_notify(call)
        return True

    if data == "cnotify_single":
        handle_cnotify_single(call)
        return True

    if data == "cnotify_multi":
        handle_cnotify_multi(call)
        return True

    # ★ غير معروف ★
    return False


# ══════════════════════════════════════════════════════════════
logger.info("[+] admin_buttons loaded — all handlers ready")
