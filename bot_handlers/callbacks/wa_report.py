# # bot_handlers/callbacks/wa_report.py
import traceback
try:
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    from config import bot
    from imports_manager import can_use_tool, consume_usage
    from logging_config import get_logger
    from ..helpers import safe_edit, h
    from whatsapp_report_generator import (
        generate_report,
        create_report_session,
        get_report_session,
        log_report_sent,
        get_user_report_history,
        add_to_history,
        normalize_number,
        REPORT_TEMPLATES,
    )
    logger = get_logger("bot_handlers.callbacks.wa_report")
    logger.info("✅ wa_report imported successfully")
except Exception as e:
    print("=" * 60)
    print("❌ wa_report IMPORT ERROR:")
    print("=" * 60)
    traceback.print_exc()
    print("=" * 60)
    raise
from ..helpers import safe_edit, h
from whatsapp_report_generator import (
    generate_report,
    create_report_session,
    get_report_session,
    log_report_sent,
    get_user_report_history,
    add_to_history,
    normalize_number,
    REPORT_TEMPLATES,
)

logger = get_logger("bot_handlers.callbacks.wa_report")


# ============================================================
# [1] أسماء الأسباب بالعربي
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
# [2] المعالج الرئيسي
# ============================================================
def handle(call, chat_id, user_id, data):
    """الدالة الرئيسية"""

    # ═══════════════════════════════════════════════════
    # 1. بدء الأداة
    # ═══════════════════════════════════════════════════
    if data == "wa_report_start":
        bot.answer_callback_query(call.id)

        # تحقق من الصلاحية والنقاط
        check = can_use_tool(user_id, "wa_report")
        if not check.get("allowed"):
            if check.get("reason") == "insufficient_points":
                m = InlineKeyboardMarkup()
                m.add(InlineKeyboardButton("💰 نقاطي", callback_data="points_menu"))
                m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
                safe_edit(
                    call,
                    f"❌ <b>رصيدك غير كافي</b>\n\n"
                    f"💰 المطلوب: <code>{check.get('cost', 0)}</code> نقطة\n"
                    f"💎 رصيدك: <code>{check.get('balance', 0)}</code> نقطة\n"
                    f"⚠️ ناقصك: <code>{check.get('needed', 0)}</code> نقطة",
                    reply_markup=m
                )
                return

            safe_edit(call, "❌ لا يمكن استخدام الأداة", reply_markup=None)
            return

        # ابدأ العملية - اطلب الرقم
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
    # 2. اختيار السبب
    # ═══════════════════════════════════════════════════
    if data.startswith("wa_reason_"):
        bot.answer_callback_query(call.id)

        # استخرج السبب والرقم
        # صيغة: wa_reason_spam_+201234567890
        body = data.replace("wa_reason_", "")
        parts = body.split("_", 1)
        if len(parts) != 2:
            return
        reason, number = parts[0], parts[1]

        # ولّد البلاغ
        report = generate_report(number, reason)
        if report.get("error"):
            safe_edit(
                call,
                f"❌ <b>خطأ:</b> {report['error']}",
                reply_markup=None
            )
            return

        # أنشئ session
        session_id = create_report_session(chat_id, number, reason)

        # سجل في الهيستوري
        add_to_history(chat_id, number, reason)

        # خصم النقاط
        consume_usage(user_id, "wa_report")

        # نص الرسالة
        text = _build_report_message(report, reason)

        # الأزرار
        m = _build_report_keyboard(report, session_id)

        safe_edit(call, text, reply_markup=m)

        logger.info(f"WA Report generated: {number} | reason={reason} | user={user_id}")
        return

    # ═══════════════════════════════════════════════════
    # 3. "بعتت البلاغ" — زود العداد واعرض تعليمات
    # ═══════════════════════════════════════════════════
    if data.startswith("wa_report_sent_"):
        session_id = data.replace("wa_report_sent_", "")
        bot.answer_callback_query(call.id, "✅ تم التسجيل")

        count = log_report_sent(session_id)
        session = get_report_session(session_id)

        if not session:
            safe_edit(call, "❌ Session انتهت، ابدأ من جديد", reply_markup=None)
            return

        number = session["victim_number"]
        reason = session["reason"]

        # ولّد بلاغ جديد لتنويع الرسالة
        new_report = generate_report(number, reason)

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
            text += (
                f"🔥 <b>ممتاز! كمل</b>\n"
                f"إنت قربت من الهدف — ابعت 1-2 بلاغ كمان\n"
            )
        else:
            text += (
                f"🏆 <b>رائع! وصلت للحد الأمثل</b>\n"
                f"الحظر متوقع خلال 24-72 ساعة\n"
            )

        # زر إرسال بلاغ جديد
        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton(
            "📧 إرسال بلاغ جديد (إيميل مختلف)",
            url=new_report["gmail"]
        ))
        m.row(
            InlineKeyboardButton("✅ بعتت بلاغ تاني", callback_data=f"wa_report_sent_{session_id}"),
            InlineKeyboardButton("🏁 خلاص كفاية", callback_data=f"wa_report_finish_{session_id}"),
        )

        safe_edit(call, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 4. "خلاص كفاية" — إنهاء
    # ═══════════════════════════════════════════════════
    if data.startswith("wa_report_finish_"):
        session_id = data.replace("wa_report_finish_", "")
        bot.answer_callback_query(call.id)

        session = get_report_session(session_id)
        if not session:
            safe_edit(call, "✅ تم", reply_markup=None)
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

        safe_edit(call, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 5. عرض القوالب المتاحة
    # ═══════════════════════════════════════════════════
    if data == "wa_report_templates":
        bot.answer_callback_query(call.id)

        text = (
            "📋 <b>القوالب المتاحة</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for reason, name in REASON_NAMES.items():
            count = len(REPORT_TEMPLATES.get(reason, []))
            text += f"{name}\n"
            text += f"   ⤷ {count} قوالب متنوعة\n\n"

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="wa_report_start"))
        safe_edit(call, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 6. سجل البلاغات
    # ═══════════════════════════════════════════════════
    if data == "wa_report_history":
        bot.answer_callback_query(call.id)

        history = get_user_report_history(chat_id, limit=15)

        if not history:
            text = (
                "📊 <b>سجل البلاغات</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                "📭 لا يوجد سجل بلاغات بعد"
            )
        else:
            text = (
                f"📊 <b>سجل البلاغات ({len(history)})</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            for i, item in enumerate(history, 1):
                num = item.get("number", "?")
                rsn = item.get("reason", "?")
                dt = item.get("date_str", "?")
                rsn_name = REASON_NAMES.get(rsn, rsn)
                text += f"{i}. <code>{num}</code>\n"
                text += f"   {rsn_name}\n"
                text += f"   🕐 {dt}\n\n"

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="wa_report_start"))
        safe_edit(call, text, reply_markup=m)
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
            "3️⃣ اضغط زر الإرسال → يفتح Gmail\n"
            "4️⃣ اضغط <b>Send</b> فقط (متعدلش النص)\n"
            "5️⃣ كرر من إيميل تاني\n\n"
            "━━━ 💡 ━━━ نصائح\n\n"
            "✅ استخدم <b>3-5 إيميلات مختلفة</b>\n"
            "✅ لا تعدّل النص — ده يخلي البلاغ موثوق\n"
            "✅ ابعت من إيميلات حقيقية (Gmail/Outlook)\n"
            "✅ كرر العملية كل 3 أيام لو مفيش نتيجة\n\n"
            "⏰ <b>مدة الحظر:</b> 24-72 ساعة\n"
            "📊 <b>معدل النجاح:</b> 60-80%"
        )

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="wa_report_start"))
        safe_edit(call, text, reply_markup=m)
        return


# ============================================================
# [3] Step Handlers
# ============================================================
def _process_number_step(message, user_id):
    """بعد استلام الرقم"""
    chat_id = message.chat.id
    number_input = (message.text or "").strip()

    # تحقق
    number = normalize_number(number_input)
    if not number:
        bot.send_message(
            chat_id,
            "❌ <b>رقم غير صالح</b>\n\n"
            "لازم يكون بالصيغة الدولية:\n"
            "<code>+201234567890</code>\n\n"
            "جرب تاني بالرقم الصح من فضلك:",
            parse_mode="HTML"
        )
        msg = bot.send_message(chat_id, "📱 <b>ابعت الرقم الصحيح:</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, _process_number_step, user_id)
        return

    # عرض قائمة الأسباب
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
# [4] بناء نص الرسالة
# ============================================================
def _build_report_message(report, reason):
    """يبني رسالة عرض البلاغ"""
    reason_name = REASON_NAMES.get(reason, reason)
    reason_desc = REASON_DESCRIPTIONS.get(reason, "")

    # عرض مقتطف من النص
    body_preview = report["body"][:250]
    if len(report["body"]) > 250:
        body_preview += "..."

    text = (
        f"📧 <b>بلاغ جاهز للإرسال</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 <b>الرقم المستهدف:</b>\n"
        f"<code>{report['number']}</code>\n\n"
        f"📂 <b>نوع البلاغ:</b>\n"
        f"{reason_name}\n"
        f"<i>{reason_desc}</i>\n\n"
        f"📮 <b>إيميل واتساب:</b>\n"
        f"<code>{report['to_email']}</code>\n\n"
        f"📝 <b>الموضوع:</b>\n"
        f"<code>{report['subject'][:80]}</code>\n\n"
        f"━━━ 📄 ━━━ <b>معاينة الرسالة</b>\n"
        f"<i>{h(body_preview)}</i>\n\n"
        f"⚠️ <b>مهم:</b> متعدّلش النص عشان البلاغ يبقى موثوق\n\n"
        f"👇 <b>اضغط على زر الإيميل بتاعك:</b>"
    )
    return text


def _build_report_keyboard(report, session_id):
    """يبني أزرار الإرسال"""
    m = InlineKeyboardMarkup()

    # أزرار الإرسال الرئيسية
    m.row(
        InlineKeyboardButton("📮 إرسال من Gmail", url=report["gmail"]),
        InlineKeyboardButton("📧 إرسال من Outlook", url=report["outlook"]),
    )
    m.row(
        InlineKeyboardButton("📨 إرسال من Yahoo", url=report["yahoo"]),
        InlineKeyboardButton("✉️ إيميل آخر", url=report["mailto"]),
    )

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
