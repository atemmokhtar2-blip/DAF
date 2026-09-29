# social_engineering.py
# ============================================================
# قسم الهندسة الاجتماعية — v2.0
# 19 قسم + WhatsApp شغال بالكامل
# يستخدم edit_message_text لتجنب التكرار
# ============================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from logging_config import get_logger

logger = get_logger("social_engineering")


# ============================================================
# قائمة الأقسام (19 قسم)
# ============================================================
CATEGORIES = {
    "whatsapp":   {"emoji": "📨", "name": "واتساب",             "available": True},
    "email":      {"emoji": "📧", "name": "البريد الإلكتروني",  "available": False},
    "sms":        {"emoji": "📱", "name": "الرسائل النصية",     "available": False},
    "voice":      {"emoji": "📞", "name": "المكالمات الصوتية",  "available": False},
    "facebook":   {"emoji": "📘", "name": "فيسبوك",             "available": False},
    "instagram":  {"emoji": "📷", "name": "انستقرام",           "available": False},
    "twitter":    {"emoji": "🐦", "name": "تويتر / X",           "available": False},
    "tiktok":     {"emoji": "🎵", "name": "تيك توك",            "available": False},
    "telegram":   {"emoji": "💬", "name": "تليجرام",            "available": False},
    "linkedin":   {"emoji": "💼", "name": "لينكد إن",           "available": False},
    "discord":    {"emoji": "🎮", "name": "ديسكورد",             "available": False},
    "giveaways":  {"emoji": "🎁", "name": "الجوائز والهدايا",    "available": False},
    "banking":    {"emoji": "💰", "name": "البنوك",              "available": False},
    "government": {"emoji": "🏛️", "name": "الجهات الحكومية",     "available": False},
    "university": {"emoji": "🎓", "name": "الجامعات",            "available": False},
    "jobs":       {"emoji": "👔", "name": "الوظائف",             "available": False},
    "emergency":  {"emoji": "🚨", "name": "الطوارئ",             "available": False},
    "romance":    {"emoji": "❤️", "name": "الحب والرومانسية",    "available": False},
    "universal":  {"emoji": "🎯", "name": "قوالب عامة",          "available": False},
}


# ============================================================
# قوالب WhatsApp العشرة
# ============================================================
WHATSAPP_TEMPLATES = {
    "whatsapp_1": {
        "emoji": "🔐",
        "name": "كود التحقق من جهاز جديد",
        "scenario": (
            "المستخدم ياخد رقم الضحية، يبعتله الرسالة دي.\n"
            "الضحية تخاف على حسابها، تبعت الكود، ثم تتم السيطرة على الحساب."
        ),
        "text": (
            "مرحباً [الاسم]،\n\n"
            "تم طلب رمز تحقق واتساب من جهاز جديد.\n\n"
            "لتأكيد أنك صاحب الحساب، يرجى إرسال الرمز المكون من 6 أرقام الذي وصلك الآن.\n\n"
            "⚠️ إذا لم تكن أنت من قام بهذا الطلب، أرسل الرمز فوراً لإلغاء العملية.\n\n"
            "واتساب - خدمة العملاء"
        ),
    },

    "whatsapp_2": {
        "emoji": "📱",
        "name": "تأكيد تغيير الرقم",
        "scenario": (
            "قالب يوهم الضحية بأن هناك طلب لتغيير رقمها المرتبط بحسابها.\n"
            "الضحية ترسل الكود لإتمام العملية المزعومة."
        ),
        "text": (
            "مرحباً،\n\n"
            "استلمنا طلبك لتغيير رقم الواتساب المرتبط بحسابك.\n\n"
            "لإتمام العملية، نحتاج:\n"
            "• الرمز الذي وصلك على الرقم القديم\n"
            "• تأكيد بتغيير الرقم\n\n"
            "⏱️ الرمز صالح لمدة 10 دقائق فقط.\n\n"
            "⚠️ إذا كنت لم تطلب هذا، يرجى الرد بكلمة \"إلغاء\".\n\n"
            "واتساب - الفريق الفني"
        ),
    },

    "whatsapp_3": {
        "emoji": "🚫",
        "name": "تحذير حظر الحساب",
        "scenario": (
            "تهديد الضحية بحظر حسابها لو ما أرسلتش البيانات.\n"
            "أسلوب التخويف الفعال."
        ),
        "text": (
            "🔴 تنبيه عاجل\n\n"
            "عزيزي [الاسم]،\n\n"
            "تم الإبلاغ عن نشاط غير عادي في حسابك على واتساب.\n"
            "الحساب معرض للحظر النهائي خلال 24 ساعة.\n\n"
            "لتفادي الحظر:\n"
            "يرجى إرسال الرمز الذي وصلك لتفعيل الحماية.\n\n"
            "🔒 الرمز هو خط الدفاع الأول لحسابك.\n\n"
            "فريق أمن واتساب"
        ),
    },

    "whatsapp_4": {
        "emoji": "🎁",
        "name": "استلام جائزة",
        "scenario": (
            "قالب يستهدف الطمع. الضحية تعتقد أنها فازت بجائزة.\n"
            "ترسل الكود لاستلام الجائزة."
        ),
        "text": (
            "🎉 مبروك!\n\n"
            "تم اختيار رقمك ضمن الفائزين بجائزة:\n\n"
            "💰 5000 جنيه مصري\n"
            "أو 📱 آيفون 15 برو\n\n"
            "لاستلام الجائزة:\n"
            "أرسل الرمز الذي وصلك للتأكيد.\n\n"
            "⏰ العرض صالح لمدة ساعة فقط!\n\n"
            "لجنة السحب على الجوائز"
        ),
    },

    "whatsapp_5": {
        "emoji": "📦",
        "name": "تتبع شحنة",
        "scenario": (
            "قالب يوهم الضحية بوجود شحنة باسمها.\n"
            "مناسب لأي شخص - عملية شائعة."
        ),
        "text": (
            "📦 إشعار من شركة الشحن\n\n"
            "مرحباً،\n\n"
            "وصلتنا شحنة باسمك من Amazon.\n"
            "📅 التاريخ: [التاريخ]\n"
            "⚖️ الوزن: 2.3 كجم\n\n"
            "لاستلام الشحنة:\n"
            "أرسل الرمز الذي وصلك للتأكيد.\n\n"
            "📍 أقرب مكتب شحن: [المنطقة]\n\n"
            "مع تحيات فريق Bosta"
        ),
    },

    "whatsapp_6": {
        "emoji": "💰",
        "name": "استرداد مبلغ مالي",
        "scenario": (
            "قالب مالي - الضحية تعتقد أن هناك مبلغ سيُعاد لها.\n"
            "أسلوب فعال جداً."
        ),
        "text": (
            "💰 إشعار استرداد مالي\n\n"
            "عزيزي العميل،\n\n"
            "تم استرداد مبلغ 2500 جنيه لحسابك.\n"
            "لإتمام التحويل، نحتاج التحقق من هويتك.\n\n"
            "🔐 يرجى إرسال الرمز الذي وصلك للتأكيد.\n\n"
            "⚠️ المبلغ سيتم إرجاعه للجهة الأصلية خلال ساعة إذا لم يتم التأكيد.\n\n"
            "قسم المدفوعات"
        ),
    },

    "whatsapp_7": {
        "emoji": "👥",
        "name": "دعوة جروب عمل",
        "scenario": (
            "قالب مناسب للضحية في مجال الأعمال.\n"
            "دعوة لجروب عمل رسمي."
        ),
        "text": (
            "👥 دعوة إلى مجموعة واتساب\n\n"
            "مرحباً [الاسم]،\n\n"
            "تم دعوتك للانضمام إلى:\n"
            "📊 مجموعة فريق العمل - [اسم الشركة]\n\n"
            "للقبول:\n"
            "أرسل الرمز الذي وصلك لتأكيد هويتك.\n\n"
            "⚠️ يجب تأكيد رقمك أولاً قبل الانضمام.\n\n"
            "إدارة الشركة"
        ),
    },

    "whatsapp_8": {
        "emoji": "📞",
        "name": "مكالمة فائتة مهمة",
        "scenario": (
            "قالب يوهم الضحية أن هناك جهة مهمة تحاول الاتصال بها.\n"
            "يستخدم الخوف من فوات شيء مهم."
        ),
        "text": (
            "📞 إشعار مكالمة فائتة\n\n"
            "مرحباً،\n\n"
            "جرى محاولة الاتصال بك من:\n"
            "🏢 جهة رسمية\n"
            "📞 الرقم: [الرقم]\n"
            "⏰ الوقت: [الوقت]\n\n"
            "الموضوع: هام جداً\n\n"
            "للرد، أرسل الرمز الذي وصلك لتأكيد هويتك.\n"
            "سيتم الاتصال بك مباشرة.\n\n"
            "الجهة الطالبة"
        ),
    },

    "whatsapp_9": {
        "emoji": "🆘",
        "name": "حالة طوارئ عائلية",
        "scenario": (
            "أقوى قالب عاطفي - الضحية تخاف على أهلها.\n"
            "نسبة نجاح عالية جداً."
        ),
        "text": (
            "🆘 حالة طوارئ\n\n"
            "مرحباً،\n\n"
            "نحاول التواصل معك بخصوص:\n"
            "👤 [اسم قريب للضحية]\n"
            "🏥 المستشفى: [اسم المستشفى]\n"
            "⚠️ الحالة: خطيرة\n\n"
            "للسؤال عن التفاصيل:\n"
            "أرسل الرمز الذي وصلك لتأكيد هويتك.\n\n"
            "📞 سيتم الاتصال بك مباشرة.\n\n"
            "مستشفى [الاسم]"
        ),
    },

    "whatsapp_10": {
        "emoji": "🔓",
        "name": "استرجاع الحساب المخترق",
        "scenario": (
            "قالب يوهم الضحية بأن حسابها اتعرض لمحاولة اختراق.\n"
            "الضحية تخاف وترسل الكود لحماية حسابها."
        ),
        "text": (
            "🚨 تنبيه أمني\n\n"
            "عزيزي [الاسم]،\n\n"
            "لاحظنا محاولة دخول غير مصرح بها لحسابك.\n"
            "🌐 IP المهاجم: 41.xxx.xxx.xxx\n\n"
            "🔒 لحماية حسابك، نحتاج تأكيد فوري:\n"
            "أرسل الرمز الذي وصلك لإلغاء الاختراق.\n\n"
            "⏱️ لديك 15 دقيقة، وإلا سيتم قفل الحساب مؤقتاً.\n\n"
            "فريق حماية واتساب"
        ),
    },
}


# ============================================================
# Safe Edit Helper
# ============================================================
def _safe_edit(bot, call, text, reply_markup=None, parse_mode="HTML"):
    """
    يحاول يعدل الرسالة، ولو فشل يبعت رسالة جديدة
    """
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

        # لو الرسالة نفسها — مش مشكلة
        if "message is not modified" in err:
            return True

        # لو الرسالة قديمة — ابعت جديدة
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
                logger.warning(f"_safe_edit fallback error: {e2}")
        else:
            logger.debug(f"_safe_edit error: {e}")

        return False


# ============================================================
# بناء لوحة الهندسة الاجتماعية الرئيسية
# ============================================================
def build_social_engineering_panel():
    """القائمة الرئيسية للهندسة الاجتماعية"""
    m = InlineKeyboardMarkup()

    # الأقسام المتاحة (شغالة)
    m.add(InlineKeyboardButton(
        "📨 واتساب ✨",
        callback_data="se_cat_whatsapp"
    ))

    # الأقسام "قريباً" — 18 قسم
    soon_categories = [
        ("email", "📧 البريد الإلكتروني"),
        ("sms", "📱 الرسائل النصية"),
        ("voice", "📞 المكالمات الصوتية"),
        ("facebook", "📘 فيسبوك"),
        ("instagram", "📷 انستقرام"),
        ("twitter", "🐦 تويتر / X"),
        ("tiktok", "🎵 تيك توك"),
        ("telegram", "💬 تليجرام"),
        ("linkedin", "💼 لينكد إن"),
        ("discord", "🎮 ديسكورد"),
        ("giveaways", "🎁 الجوائز والهدايا"),
        ("banking", "💰 البنوك"),
        ("government", "🏛️ الجهات الحكومية"),
        ("university", "🎓 الجامعات"),
        ("jobs", "👔 الوظائف"),
        ("emergency", "🚨 الطوارئ"),
        ("romance", "❤️ الحب والرومانسية"),
        ("universal", "🎯 قوالب عامة"),
    ]

    # جمع 2 في كل صف
    for i in range(0, len(soon_categories), 2):
        pair = soon_categories[i:i+2]
        buttons = []
        for key, name in pair:
            buttons.append(InlineKeyboardButton(
                f"{name} 🔒",
                callback_data=f"se_soon_{key}"
            ))
        if buttons:
            m.row(*buttons)

    # زر رجوع
    m.add(InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main"))

    return m


# ============================================================
# بناء قائمة WhatsApp (10 قوالب)
# ============================================================
def build_whatsapp_panel():
    """قائمة قوالب WhatsApp"""
    m = InlineKeyboardMarkup()

    templates_order = [
        "whatsapp_1", "whatsapp_2", "whatsapp_3", "whatsapp_4", "whatsapp_5",
        "whatsapp_6", "whatsapp_7", "whatsapp_8", "whatsapp_9", "whatsapp_10",
    ]

    for idx, key in enumerate(templates_order, 1):
        tpl = WHATSAPP_TEMPLATES.get(key)
        if not tpl:
            continue
        m.add(InlineKeyboardButton(
            f"{idx}. {tpl['emoji']} {tpl['name']}",
            callback_data=f"se_tpl_{key}"
        ))

    m.add(InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="gen_se"))
    return m


# ============================================================
# بناء صفحة قالب واحد
# ============================================================
def build_template_view(template_key):
    """يبني عرض قالب (نص + أزرار)"""
    tpl = WHATSAPP_TEMPLATES.get(template_key)
    if not tpl:
        return None, None

    # ─── الرسالة ───
    text = (
        f"<b>{tpl['emoji']} {tpl['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"

        f"📝 <b>نص الرسالة:</b>\n"
        f"<pre>{tpl['text']}</pre>\n\n"

        f"🎯 <b>السيناريو:</b>\n"
        f"<i>{tpl['scenario']}</i>\n\n"

        f"💡 <b>ملاحظة:</b> اضغط زر النسخ ثم الصق الرسالة في واتساب."
    )

    # ─── الأزرار ───
    m = InlineKeyboardMarkup()

    # ★ زر النسخ عبر CopyTextButton
    try:
        from telebot.types import CopyTextButton
        m.add(InlineKeyboardButton(
            "📋 نسخ نص الرسالة",
            copy_text=CopyTextButton(text=tpl['text'])
        ))
    except Exception:
        # fallback
        m.add(InlineKeyboardButton(
            "📋 نسخ النص (اضغط مطولاً)",
            callback_data=f"se_copy_{template_key}"
        ))

    m.row(
        InlineKeyboardButton("✏️ تعديل النص", callback_data=f"se_edit_{template_key}"),
        InlineKeyboardButton("💾 حفظ في المفضلة", callback_data=f"se_fav_{template_key}"),
    )
    m.add(InlineKeyboardButton("🔙 رجوع لقائمة واتساب", callback_data="se_cat_whatsapp"))

    return text, m


# ============================================================
# Handlers
# ============================================================
def handle_social_engineering_callback(call, bot, chat_id, user_id, data):
    """
    يعالج كل callbacks الهندسة الاجتماعية — يستخدم edit_message_text
    يرجع True لو اتعامل مع الـ callback، False لو لأ
    """

    # ═══════════════════════════════════════════════════
    # فتح اللوحة الرئيسية
    # ═══════════════════════════════════════════════════
    if data == "gen_se":
        bot.answer_callback_query(call.id)

        text = (
            "🎭 <b>قسم الهندسة الاجتماعية</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📚 <b>الأقسام المتاحة:</b> 19 قسم\n"
            "✅ <b>يعمل الآن:</b> واتساب فقط\n"
            "🚧 <b>قريباً:</b> باقي الأقسام\n\n"
            "💡 <i>اختر قسم للبدء</i>"
        )

        _safe_edit(bot, call, text,
                   reply_markup=build_social_engineering_panel())
        return True

    # ═══════════════════════════════════════════════════
    # القسم "قريباً"
    # ═══════════════════════════════════════════════════
    if data.startswith("se_soon_"):
        cat_key = data.replace("se_soon_", "")
        cat = CATEGORIES.get(cat_key, {})
        cat_name = cat.get("name", "القسم")
        cat_emoji = cat.get("emoji", "📁")

        bot.answer_callback_query(call.id, "🚧 قريباً...")

        text = (
            f"{cat_emoji} <b>{cat_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🚧 <i>هذا القسم قيد التطوير</i>\n"
            f"⏰ <i>سيتم إطلاقه قريباً</i>"
        )

        # زر الرجوع للأقسام
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="gen_se"))

        _safe_edit(bot, call, text, reply_markup=m)
        return True

    # ═══════════════════════════════════════════════════
    # فتح قسم WhatsApp
    # ═══════════════════════════════════════════════════
    if data == "se_cat_whatsapp":
        bot.answer_callback_query(call.id)

        text = (
            "📨 <b>قسم واتساب</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 <b>عدد القوالب:</b> 10\n"
            "🎯 <b>الهدف:</b> سرقة كود التحقق من واتساب\n\n"
            "💡 <i>اختر السيناريو المناسب للضحية</i>"
        )

        _safe_edit(bot, call, text, reply_markup=build_whatsapp_panel())
        return True

    # ═══════════════════════════════════════════════════
    # عرض قالب
    # ═══════════════════════════════════════════════════
    if data.startswith("se_tpl_"):
        template_key = data.replace("se_tpl_", "")

        tpl = WHATSAPP_TEMPLATES.get(template_key)
        if not tpl:
            bot.answer_callback_query(call.id, "❌ القالب غير موجود", show_alert=True)
            return True

        bot.answer_callback_query(call.id)

        text, m = build_template_view(template_key)
        if text and m:
            _safe_edit(bot, call, text, reply_markup=m)
        return True

    # ═══════════════════════════════════════════════════
    # نسخ نص (fallback)
    # ═══════════════════════════════════════════════════
    if data.startswith("se_copy_"):
        template_key = data.replace("se_copy_", "")
        tpl = WHATSAPP_TEMPLATES.get(template_key)
        if not tpl:
            bot.answer_callback_query(call.id, "❌ القالب غير موجود", show_alert=True)
            return True

        bot.answer_callback_query(call.id, "📋 النص في الرسالة")

        text = (
            f"📋 <b>انسخ النص التالي:</b>\n\n"
            f"<pre>{tpl['text']}</pre>"
        )

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع للقالب", callback_data=f"se_tpl_{template_key}"))

        _safe_edit(bot, call, text, reply_markup=m)
        return True

    # ═══════════════════════════════════════════════════
    # تعديل نص
    # ═══════════════════════════════════════════════════
    if data.startswith("se_edit_"):
        template_key = data.replace("se_edit_", "")
        tpl = WHATSAPP_TEMPLATES.get(template_key)
        if not tpl:
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return True

        bot.answer_callback_query(call.id)

        # نبعت رسالة جديدة لطلب النص (لأنها تحتاج input)
        msg = bot.send_message(
            chat_id,
            f"✏️ <b>أرسل النص الجديد للقالب:</b>\n\n"
            f"<i>ملاحظة: انسخ النص من الرسالة السابقة وعدّله ثم أرسله</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(
            msg,
            lambda m: _handle_edit_text(m, bot, template_key)
        )
        return True

    # ═══════════════════════════════════════════════════
    # المفضلة
    # ═══════════════════════════════════════════════════
    if data.startswith("se_fav_"):
        template_key = data.replace("se_fav_", "")
        tpl = WHATSAPP_TEMPLATES.get(template_key)
        if not tpl:
            bot.answer_callback_query(call.id, "❌", show_alert=True)
            return True

        try:
            from config import redis_client
            if redis_client:
                redis_client.sadd(f"se_favorites:{user_id}", template_key)
                bot.answer_callback_query(call.id, "⭐ تم الحفظ في المفضلة")
            else:
                bot.answer_callback_query(call.id, "✅ تم")
        except Exception as e:
            logger.warning(f"se_fav error: {e}")
            bot.answer_callback_query(call.id, "✅ تم")

        return True

    # لم يتعامل معه هذا الـ handler
    return False


# ============================================================
# تعديل النص
# ============================================================
def _handle_edit_text(message, bot, template_key):
    """يستقبل النص المعدل ويرجعه للمستخدم"""
    if not message.text:
        return

    new_text = message.text.strip()
    if len(new_text) < 10:
        bot.send_message(message.chat.id, "❌ النص قصير جداً")
        return

    chat_id = message.chat.id

    text = (
        f"✅ <b>النص المعدل جاهز</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<pre>{new_text}</pre>"
    )

    m = InlineKeyboardMarkup()

    try:
        from telebot.types import CopyTextButton
        m.add(InlineKeyboardButton(
            "📋 نسخ النص المعدل",
            copy_text=CopyTextButton(text=new_text)
        ))
    except Exception:
        pass

    m.add(InlineKeyboardButton("🔙 رجوع للقالب", callback_data=f"se_tpl_{template_key}"))

    try:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=m)
    except Exception as e:
        logger.warning(f"_handle_edit_text error: {e}")
        bot.send_message(chat_id, text[:4000], parse_mode="HTML")
