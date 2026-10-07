# bot_handlers/callbacks/wa_report.py
# ============================================================
# WhatsApp Report Handler v5 — مع Anti-Repeat (50 قالب)
# ============================================================
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from imports_manager import can_use_tool, consume_usage
from logging_config import get_logger

from whatsapp_report_generator import (
    generate_report,
    create_report_session,
    get_report_session,
    log_report_sent,
    get_user_report_history,
    add_to_history,
    normalize_number,
    REPORT_TEMPLATES,
    get_template_stats,
)

logger = get_logger("bot_handlers.callbacks.wa_report")


# ============================================================
# [1] أسماء الأسباب
# ============================================================
REASON_NAMES = {
    "spam": "📨 سبام (رسائل مزعجة)",
    "scam": "💰 نصب واحتيال",
    "harassment": "😡 مضايقة وتهديد",
    "fake": "🎭 حساب مزيف",
    "illegal": "⚖️ نشاط غير قانوني",
}

REASON_DESCRIPTIONS = {
    "spam": "بلاغ عن رسائل سبام وإعلانات مزعجة",
    "scam": "بلاغ عن نصب مالي واحتيال",
    "harassment": "بلاغ عن تهديد ومضايقة",
    "fake": "بلاغ عن حساب مزيف أو انتحال شخصية",
    "illegal": "بلاغ عن أنشطة غير قانونية",
}


# ============================================================
# [2] Helper: إرسال رسالة جديدة (يمسح القديمة)
# ============================================================
def _send_new(call, chat_id, text, reply_markup=None):
    """يمسح الرسالة القديمة + يبعت جديدة"""
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    try:
        bot.send_message(
            chat_id, text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        logger.error(f"_send_new error: {e}")
        try:
            bot.send_message(
                chat_id, text,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e2:
            logger.error(f"_send_new fallback error: {e2}")
            return False


# ============================================================
# [3] المعالج الرئيسي
# ============================================================
def handle(call, chat_id, user_id, data):
    """الدالة الرئيسية"""

    # ═══════════════════════════════════════════════════
    # 1. بدء الأداة
    # ═══════════════════════════════════════════════════
    if data == "wa_report_start":
        bot.answer_callback_query(call.id)

        check = can_use_tool(user_id, "wa_report")
        if not check.get("allowed"):
            if check.get("reason") == "insufficient_points":
                m = InlineKeyboardMarkup()
                m.add(InlineKeyboardButton("💰 نقاطي", callback_data="points_menu"))
                m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
                _send_new(
                    call, chat_id,
                    f"❌ <b>رصيدك غير كافي</b>\n\n"
                    f"💰 المطلوب: <code>{check.get('cost', 0)}</code> نقطة\n"
                    f"💎 رصيدك: <code>{check.get('balance', 0)}</code> نقطة\n"
                    f"⚠️ ناقصك: <code>{check.get('needed', 0)}</code> نقطة",
                    reply_markup=m
                )
                return

            _send_new(call, chat_id, "❌ لا يمكن استخدام الأداة")
            return

        msg = bot.send_message(
            chat_id,
            "🚫 <b>حظر رقم واتساب</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📱 <b>ابعتلي رقم الضحية بالصيغة الدولية:</b>\n\n"
            "<b>✅ مثال صحيح:</b>\n"
            "<code>+201234567890</code>\n"
            "<code>+966501234567</code>\n"
            "<code>+971501234567</code>\n\n"
            "<b>❌ أمثلة خاطئة:</b>\n"
            "<code>01234567890</code>\n"
            "<code>201234567890</code>\n\n"
            "⚠️ الرقم لازم يبدأ بـ <b>+</b>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, _process_number_step, user_id)
        return

    # ═══════════════════════════════════════════════════
    # 2. اختيار السبب — مع Anti-Repeat
    # ═══════════════════════════════════════════════════
    if data.startswith("wa_reason_"):
        bot.answer_callback_query(call.id)

        body = data.replace("wa_reason_", "")
        parts = body.split("_", 1)
        if len(parts) != 2:
            return
        reason, number = parts[0], parts[1]

        # ⚡ نمرر user_id للحصول على قالب فريد
        report = generate_report(number, reason, user_id=user_id)
        if report.get("error"):
            _send_new(call, chat_id, f"❌ <b>خطأ:</b> {report['error']}")
            return

        session_id = create_report_session(chat_id, number, reason)
        add_to_history(chat_id, number, reason)
        consume_usage(user_id, "wa_report")

        text = _build_report_message(report, reason)
        m = _build_report_keyboard(report, session_id)

        _send_new(call, chat_id, text, reply_markup=m)

        logger.info(
            f"WA Report generated: {number} | reason={reason} | "
            f"template={report.get('template_id')} | user={user_id}"
        )
        return

    # ═══════════════════════════════════════════════════
    # 3. "بعتت البلاغ" — مع Anti-Repeat
    # ═══════════════════════════════════════════════════
    if data.startswith("wa_report_sent_"):
        session_id = data.replace("wa_report_sent_", "")
        bot.answer_callback_query(call.id, "✅ تم التسجيل")

        count = log_report_sent(session_id)
        session = get_report_session(session_id)

        if not session:
            _send_new(call, chat_id, "❌ Session انتهت، ابدأ من جديد")
            return

        number = session["victim_number"]
        reason = session["reason"]

        # ⚡ نمرر user_id للحصول على قالب فريد
        new_report = generate_report(number, reason, user_id=user_id)

        text = (
            f"✅ <b>تم تسجيل بلاغ #{count}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 الرقم: <code>{number}</code>\n"
            f"📊 البلاغات المرسلة: <b>{count}</b>\n\n"
        )

        if count < 3:
            text += (
                f"💡 <b>نصيحة:</b>\n"
                f"عشان تسرّع الحظر، ابعت بلاغ من إيميل تاني\n"
                f"كل بلاغ من إيميل مختلف = موثوق أكتر\n\n"
                f"🎯 <b>الهدف:</b> 3-5 بلاغات على الأقل\n"
            )
        elif count < 5:
            text += f"🔥 <b>ممتاز! كمل</b>\nإنت قربت من الهدف\n"
        else:
            text += f"🏆 <b>رائع! وصلت للحد الأمثل</b>\nالحظر متوقع خلال 24-72 ساعة\n"

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton(
            "📧 إرسال بلاغ جديد",
            url=new_report["mailto"]
        ))
        m.row(
            InlineKeyboardButton("✅ بعتت بلاغ تاني", callback_data=f"wa_report_sent_{session_id}"),
            InlineKeyboardButton("🏁 خلاص كفاية", callback_data=f"wa_report_finish_{session_id}"),
        )

        _send_new(call, chat_id, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 4. "خلاص كفاية"
    # ═══════════════════════════════════════════════════
    if data.startswith("wa_report_finish_"):
        session_id = data.replace("wa_report_finish_", "")
        bot.answer_callback_query(call.id)

        session = get_report_session(session_id)
        if not session:
            _send_new(call, chat_id, "✅ تم")
            return

        count = session.get("reports_sent", 0)
        number = session["victim_number"]

        text = (
            f"🏁 <b>انتهت العملية</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📱 الرقم المستهدف: <code>{number}</code>\n"
            f"📊 إجمالي البلاغات: <b>{count}</b>\n\n"
            f"⏰ <b>الحظر المتوقع:</b> 24-72 ساعة\n"
            f"📊 <b>معدل النجاح:</b> 60-80%\n\n"
            f"💡 لو الرقم ما اتحظرش، كرر العملية بعد 3 أيام"
        )

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
        m.add(InlineKeyboardButton("🚫 بلاغ جديد", callback_data="wa_report_start"))

        _send_new(call, chat_id, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 5. عرض القوالب — مع إحصائيات
    # ═══════════════════════════════════════════════════
    if data == "wa_report_templates":
        bot.answer_callback_query(call.id)

        stats = get_template_stats()

        text = (
            f"📋 <b>القوالب المتاحة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>الإجمالي:</b> <code>{stats.get('total', 0)}</code> قالب\n\n"
        )

        for reason, name in REASON_NAMES.items():
            count = stats.get(reason, 0)
            text += f"{name}\n"
            text += f"   ⤷ <b>{count}</b> قوالب متنوعة\n\n"

        text += (
            f"━━━ ⚡ ━━━ <b>مميزات</b>\n"
            f"✅ كل مستخدم يحصل على قالب فريد\n"
            f"✅ لا تكرار — كل بلاغ مختلف\n"
            f"✅ محتوى واقعي بتفاصيل دقيقة\n"
            f"✅ تعدي فلاتر واتساب"
        )

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="wa_report_start"))
        _send_new(call, chat_id, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 6. السجل
    # ═══════════════════════════════════════════════════
    if data == "wa_report_history":
        bot.answer_callback_query(call.id)

        history = get_user_report_history(chat_id, limit=15)

        if not history:
            text = "📊 <b>سجل البلاغات</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📭 لا يوجد سجل بلاغات بعد"
        else:
            text = f"📊 <b>سجل البلاغات ({len(history)})</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for i, item in enumerate(history, 1):
                num = item.get("number", "?")
                rsn = item.get("reason", "?")
                dt = item.get("date_str", "?")
                rsn_name = REASON_NAMES.get(rsn, rsn)
                text += f"{i}. <code>{num}</code>\n   {rsn_name}\n   🕐 {dt}\n\n"

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="wa_report_start"))
        _send_new(call, chat_id, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 7. تعليمات
    # ═══════════════════════════════════════════════════
    if data == "wa_report_help":
        bot.answer_callback_query(call.id)

        text = (
            "❓ <b>كيف تستخدم الأداة</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣ اختر سبب البلاغ\n"
            "2️⃣ هيتولّدلك رسالة جاهزة\n"
            "3️⃣ اضغط زر الإرسال → يفتح التطبيق\n"
            "4️⃣ اضغط <b>Send</b> فقط (متعدلش النص)\n"
            "5️⃣ كرر من إيميل تاني\n\n"
            "━━━ 💡 ━━━ نصائح\n\n"
            "✅ استخدم <b>3-5 إيميلات مختلفة</b>\n"
            "✅ لا تعدّل النص — ده يخلي البلاغ موثوق\n"
            "✅ ابعت من إيميلات حقيقية (Gmail/Outlook)\n"
            "✅ كرر العملية كل 3 أيام لو مفيش نتيجة\n\n"
            "━━━ 🎯 ━━━ <b>لماذا 50 قالب؟</b>\n"
            "• كل مستخدم يأخذ قالب فريد\n"
            "• لا تكرار في الرسائل\n"
            "• تفاصيل واقعية (أسماء، مدن، مبالغ)\n"
            "• تعدي فلاتر واتساب تلقائياً\n\n"
            "⏰ <b>مدة الحظر:</b> 24-72 ساعة\n"
            "📊 <b>معدل النجاح:</b> 60-80%"
        )

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="wa_report_start"))
        _send_new(call, chat_id, text, reply_markup=m)
        return


# ============================================================
# [4] Step Handler — استلام الرقم
# ============================================================
def _process_number_step(message, user_id):
    """بعد استلام الرقم من المستخدم"""
    chat_id = message.chat.id
    number_input = (message.text or "").strip()

    number = normalize_number(number_input)
    if not number:
        bot.send_message(
            chat_id,
            "❌ <b>رقم غير صالح</b>\n\n"
            "لازم يكون بالصيغة الدولية:\n"
            "<code>+201234567890</code>\n\n"
            "جرب تاني:",
            parse_mode="HTML"
        )
        msg = bot.send_message(chat_id, "📱 <b>ابعت الرقم الصحيح:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, _process_number_step, user_id)
        return

    text = (
        f"✅ <b>تم استلام الرقم:</b>\n"
        f"<code>{number}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>اختر سبب البلاغ:</b>\n\n"
        f"⚠️ اختر السبب المناسب عشان البلاغ يبقى فعّال"
    )

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("📨 سبام", callback_data=f"wa_reason_spam_{number}"),
        InlineKeyboardButton("💰 نصب", callback_data=f"wa_reason_scam_{number}"),
    )
    m.row(
        InlineKeyboardButton("😡 مضايقة", callback_data=f"wa_reason_harassment_{number}"),
        InlineKeyboardButton("🎭 مزيف", callback_data=f"wa_reason_fake_{number}"),
    )
    m.row(
        InlineKeyboardButton("⚖️ نشاط غير قانوني", callback_data=f"wa_reason_illegal_{number}"),
    )
    m.row(
        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"),
    )

    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=m)


# ============================================================
# [5] بناء رسالة البلاغ
# ============================================================
def _build_report_message(report, reason):
    """يبني رسالة عرض البلاغ — نظيفة ومبسطة"""
    reason_name = REASON_NAMES.get(reason, reason)
    reason_desc = REASON_DESCRIPTIONS.get(reason, "")

    text = (
        f"📧 <b>بلاغ جاهز للإرسال</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 <b>الرقم المستهدف:</b>\n"
        f"<code>{report['number']}</code>\n\n"
        f"📂 <b>نوع البلاغ:</b>\n"
        f"{reason_name}\n"
        f"<i>{reason_desc}</i>\n\n"
        f"📮 <b>سيتم الإرسال إلى:</b>\n"
        f"<code>{report['to_email']}</code>\n\n"
        f"━━━ 📋 ━━━ <b>الخطوات</b>\n"
        f"1️⃣ اضغط على زر الإرسال تحت\n"
        f"2️⃣ هيفتح تطبيق الإيميل بتاعك\n"
        f"3️⃣ الرسالة تكون جاهزة ✅\n"
        f"4️⃣ اضغط <b>Send</b> بس\n\n"
        f"⚠️ <b>مهم:</b> متعدّلش النص\n"
        f"🔄 <b>للحظر الأسرع:</b> كرر من إيميل تاني"
    )
    return text


# ============================================================
# [6] ★★★ بناء أزرار البلاغ — زر واحد فقط ★★★
# ============================================================
def _build_report_keyboard(report, session_id):
    """يبني أزرار الإرسال — زر واحد فقط (mailto)"""
    m = InlineKeyboardMarkup()

    # ⚡ زر واحد فقط — يفتح التطبيق الافتراضي مباشرة
    m.add(InlineKeyboardButton(
        "📧 إرسال البلاغ الآن",
        url=report["mailto"]
    ))

    # زر تأكيد الإرسال
    m.add(InlineKeyboardButton(
        "✅ بعتت البلاغ",
        callback_data=f"wa_report_sent_{session_id}"
    ))

    # أزرار مساعدة
    m.row(
        InlineKeyboardButton("❓ مساعدة", callback_data="wa_report_help"),
        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"),
    )

    return m
