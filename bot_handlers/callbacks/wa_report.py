# bot_handlers/callbacks/wa_report.py
# ============================================================
# WhatsApp Report Handler v6.0
# Multi-Channel + Multi-Language + Blast Mode
# ============================================================
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from imports_manager import can_use_tool, consume_usage
from logging_config import get_logger

from whatsapp_report_generator import (
    generate_report,
    generate_blast_reports,
    create_report_session,
    get_report_session,
    log_report_sent,
    get_user_report_history,
    add_to_history,
    normalize_number,
    REPORT_TEMPLATES,
    get_template_stats,
    WA_REPORT_CHANNELS,
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

LANG_FLAGS = {
    "en": "🇬🇧",
    "ar": "🇪🇬",
    "fr": "🇫🇷",
    "es": "🇪🇸",
    "de": "🇩🇪",
}

LANG_NAMES = {
    "en": "English",
    "ar": "العربية",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
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
    # 2. ⚡ Blast Mode — اختيار السبب
    # ═══════════════════════════════════════════════════
    if data.startswith("wa_blast_"):
        body = data.replace("wa_blast_", "")
        parts = body.split("_", 1)

        # الحالة 1: wa_blast_+201234567890 (رقم فقط)
        if len(parts) == 1:
            bot.answer_callback_query(call.id)
            number = parts[0]

            text = (
                f"⚡ <b>Blast Mode</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 <b>الرقم:</b> <code>{number}</code>\n\n"
                f"🎯 <b>اختر سبب البلاغ:</b>\n\n"
                f"سيتم إرسال <b>5 بلاغات</b> دفعة واحدة:\n"
                f"• 🌐 <b>5 لغات</b> مختلفة\n"
                f"• 📧 <b>5 إيميلات</b> واتساب\n"
                f"• 📝 <b>5 قوالب</b> فريدة\n"
                f"• 🎭 <b>محتوى متنوع</b> 100%\n\n"
                f"⚡ <b>نسبة الحظر المتوقعة: 85-95%</b>"
            )

            m = InlineKeyboardMarkup()
            m.row(
                InlineKeyboardButton("📨 سبام", callback_data=f"wa_blast_spam_{number}"),
                InlineKeyboardButton("💰 نصب", callback_data=f"wa_blast_scam_{number}"),
            )
            m.row(
                InlineKeyboardButton("😡 مضايقة", callback_data=f"wa_blast_harassment_{number}"),
                InlineKeyboardButton("🎭 مزيف", callback_data=f"wa_blast_fake_{number}"),
            )
            m.row(
                InlineKeyboardButton("⚖️ نشاط غير قانوني", callback_data=f"wa_blast_illegal_{number}"),
            )
            m.row(
                InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"),
            )
            _send_new(call, chat_id, text, reply_markup=m)
            return

        # الحالة 2: wa_blast_spam_+201234567890 (سبب + رقم)
        elif len(parts) == 2:
            bot.answer_callback_query(call.id, "⚡ جاري تجهيز Blast...")
            reason, number = parts[0], parts[1]

            # تحقق من الصلاحية
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
                        f"💎 رصيدك: <code>{check.get('balance', 0)}</code> نقطة",
                        reply_markup=m
                    )
                    return
                _send_new(call, chat_id, "❌ لا يمكن استخدام الأداة")
                return

            # اخصم النقاط
            consume_usage(user_id, "wa_report")

            # ولّد الـ 5 بلاغات
            blast = generate_blast_reports(number, reason, user_id=user_id)

            if blast.get("error"):
                _send_new(call, chat_id, f"❌ <b>خطأ:</b> {blast['error']}")
                return

            reports = blast.get("reports", [])
            if not reports:
                _send_new(call, chat_id, "❌ فشل توليد البلاغات")
                return

            # أنشئ session
            session_id = create_report_session(chat_id, number, reason)
            add_to_history(chat_id, number, reason)

            # ابعت رسالة تأكيد أول
            intro_text = (
                f"⚡ <b>Blast Mode — تم تجهيز {len(reports)} بلاغات!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 <b>الرقم:</b> <code>{number}</code>\n"
                f"📂 <b>السبب:</b> {REASON_NAMES.get(reason, reason)}\n"
                f"📊 <b>عدد البلاغات:</b> <b>{len(reports)}</b>\n\n"
                f"━━━ 📋 ━━━ <b>طريقة الإرسال</b>\n"
                f"1️⃣ اضغط على كل زر من الأزرار اللي تحت\n"
                f"2️⃣ هيفتح تطبيق الإيميل برسالة جاهزة\n"
                f"3️⃣ اضغط <b>Send</b>\n"
                f"4️⃣ ارجع وكمل الزر التالي\n\n"
                f"⚠️ <b>ملاحظة:</b> كل بلاغ بلغة وإيميل مختلف\n"
                f"🎯 <b>الهدف:</b> إرسال الـ {len(reports)} بلاغات كلهم"
            )

            intro_m = InlineKeyboardMarkup()
            intro_m.add(InlineKeyboardButton(
                "🔙 رجوع للقائمة",
                callback_data="back_to_main"
            ))

            try:
                bot.send_message(
                    chat_id, intro_text,
                    parse_mode="HTML",
                    reply_markup=intro_m,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.warning(f"send intro failed: {e}")

            # ابعت كل بلاغ في رسالة منفصلة
            for r in reports:
                lang = r.get("language", "en")
                flag = LANG_FLAGS.get(lang, "🌐")
                lang_name = LANG_NAMES.get(lang, lang.upper())
                idx = r.get("index", 0)
                to_email = r.get("to_email", "")
                channel_name = r.get("channel_name", "")
                template_id = r.get("template_id", "?")

                r_text = (
                    f"📧 <b>بلاغ #{idx} من {len(reports)}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{flag} <b>اللغة:</b> {lang_name}\n"
                    f"📮 <b>الإيميل:</b> <code>{to_email}</code>\n"
                    f"📌 <b>القسم:</b> {channel_name}\n"
                    f"📝 <b>القالب:</b> <code>{template_id}</code>\n\n"
                    f"👇 <b>اضغط الزر تحت للإرسال:</b>"
                )

                r_m = InlineKeyboardMarkup()
                r_m.add(InlineKeyboardButton(
                    f"{flag} إرسال بلاغ #{idx}",
                    url=r["mailto"]
                ))

                try:
                    bot.send_message(
                        chat_id, r_text,
                        parse_mode="HTML",
                        reply_markup=r_m,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.warning(f"send blast #{idx} error: {e}")

            # ابعت رسالة المتابعة النهائية
            final_text = (
                f"✅ <b>كل البلاغات اتبعتت!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 <b>الرقم:</b> <code>{number}</code>\n"
                f"📊 <b>عدد البلاغات:</b> {len(reports)}\n\n"
                f"💡 <b>اضغط الزر تحت بعد ما تخلص إرسال كل البلاغات</b>"
            )

            final_m = InlineKeyboardMarkup()
            final_m.add(InlineKeyboardButton(
                f"✅ بعتت الـ {len(reports)} بلاغات",
                callback_data=f"wa_report_sent_{session_id}"
            ))
            final_m.add(InlineKeyboardButton(
                "🏁 خلاص كفاية",
                callback_data=f"wa_report_finish_{session_id}"
            ))

            try:
                bot.send_message(
                    chat_id, final_text,
                    parse_mode="HTML",
                    reply_markup=final_m,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.warning(f"send final failed: {e}")

            logger.info(
                f"BLAST MODE: {number} | reason={reason} | "
                f"reports={len(reports)} | user={user_id}"
            )
            return

    # ═══════════════════════════════════════════════════
    # 3. الوضع العادي — اختيار السبب
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
            f"template={report.get('template_id')} | "
            f"lang={report.get('language')} | user={user_id}"
        )
        return

    # ═══════════════════════════════════════════════════
    # 4. "بعتت البلاغ"
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
    # 5. "خلاص كفاية"
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
            f"📊 <b>معدل النجاح:</b> 85-95%\n\n"
            f"💡 لو الرقم ما اتحظرش، كرر العملية بعد 3 أيام"
        )

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_to_main"))
        m.add(InlineKeyboardButton("🚫 بلاغ جديد", callback_data="wa_report_start"))

        _send_new(call, chat_id, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 6. عرض القوالب — مع إحصائيات كاملة
    # ═══════════════════════════════════════════════════
    if data == "wa_report_templates":
        bot.answer_callback_query(call.id)

        stats = get_template_stats()

        text = (
            f"📋 <b>القوالب المتاحة</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>الإجمالي:</b> <code>{stats.get('total', 0)}</code> قالب\n"
            f"🌐 <b>5 لغات</b> مختلفة\n"
            f"📧 <b>5 إيميلات</b> واتساب\n\n"
            f"━━━ 🌍 ━━━ <b>التوزيع حسب اللغة</b>\n"
        )

        by_lang = stats.get("by_lang", {})
        for lang, count in by_lang.items():
            flag = LANG_FLAGS.get(lang, "🌐")
            name = LANG_NAMES.get(lang, lang)
            text += f"{flag} <b>{name}:</b> <code>{count}</code> قالب\n"

        text += f"\n━━━ 📂 ━━━ <b>حسب السبب</b>\n"
        for reason, name in REASON_NAMES.items():
            text += f"\n{name}:\n"
            for lang in ["en", "ar", "fr", "es", "de"]:
                key = f"{lang}_{reason}"
                count = stats.get(key, 0)
                if count > 0:
                    flag = LANG_FLAGS.get(lang, "🌐")
                    text += f"   {flag} {count}   "
            text += "\n"

        text += (
            f"\n━━━ ⚡ ━━━ <b>المميزات</b>\n"
            f"✅ كل مستخدم يحصل على قالب فريد\n"
            f"✅ 5 لغات — تنويع كامل\n"
            f"✅ 5 إيميلات — Multi-Channel\n"
            f"✅ Blast Mode — 5 بلاغات بضغطة\n"
            f"✅ نسبة الحظر: 85-95%"
        )

        m = InlineKeyboardMarkup()
        m.add(InlineKeyboardButton("🔙 رجوع", callback_data="wa_report_start"))
        _send_new(call, chat_id, text, reply_markup=m)
        return

    # ═══════════════════════════════════════════════════
    # 7. السجل
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
    # 8. تعليمات
    # ═══════════════════════════════════════════════════
    if data == "wa_report_help":
        bot.answer_callback_query(call.id)

        text = (
            "❓ <b>كيف تستخدم الأداة</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔹 <b>الوضع العادي:</b>\n"
            "1️⃣ اختر سبب البلاغ\n"
            "2️⃣ هيظهرلك زر واحد\n"
            "3️⃣ اضغطه → يفتح التطبيق\n"
            "4️⃣ اضغط <b>Send</b>\n\n"
            "⚡ <b>Blast Mode (الأقوى):</b>\n"
            "1️⃣ اضغط \"Blast Mode\"\n"
            "2️⃣ اختر السبب\n"
            "3️⃣ هيظهرلك <b>5 أزرار</b>\n"
            "4️⃣ اضغط كل زر وابعت البلاغ\n"
            "5️⃣ في الآخر اضغط \"بعتت الـ 5\"\n\n"
            "━━━ 🎯 ━━━ <b>ليه Blast أقوى؟</b>\n"
            "• 5 بلاغات بدل بلاغ واحد\n"
            "• 5 لغات مختلفة (يصعب الفلترة)\n"
            "• 5 إيميلات واتساب مختلفة\n"
            "• 5 قوالب فريدة 100%\n"
            "• نسبة الحظر: <b>85-95%</b>\n\n"
            "━━━ 💡 ━━━ <b>نصائح</b>\n"
            "✅ استخدم Blast Mode دايمًا\n"
            "✅ لا تعدّل النص في الإيميل\n"
            "✅ ابعت من إيميلات حقيقية\n"
            "✅ كرر العملية كل 3 أيام لو مفيش نتيجة"
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
        f"🎯 <b>اختر طريقة الإرسال:</b>\n\n"
        f"⚡ <b>Blast Mode:</b> 5 بلاغات (5 لغات + 5 إيميلات)\n"
        f"📧 <b>عادي:</b> بلاغ واحد"
    )

    m = InlineKeyboardMarkup()

    # ⚡ Blast Mode
    m.add(InlineKeyboardButton(
        "⚡ Blast Mode (5 بلاغات) — الأقوى",
        callback_data=f"wa_blast_{number}"
    ))

    m.add(InlineKeyboardButton(
        "━━━━━━━━━━━━━━━",
        callback_data="noop"
    ))

    # الوضع العادي
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
# [5] بناء رسالة البلاغ (الوضع العادي)
# ============================================================
def _build_report_message(report, reason):
    """يبني رسالة عرض البلاغ — نظيفة ومبسطة"""
    reason_name = REASON_NAMES.get(reason, reason)
    reason_desc = REASON_DESCRIPTIONS.get(reason, "")

    lang = report.get("language", "en")
    flag = LANG_FLAGS.get(lang, "🌐")
    lang_name = LANG_NAMES.get(lang, lang.upper())
    template_id = report.get("template_id", "?")

    text = (
        f"📧 <b>بلاغ جاهز للإرسال</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📱 <b>الرقم المستهدف:</b>\n"
        f"<code>{report['number']}</code>\n\n"
        f"📂 <b>نوع البلاغ:</b>\n"
        f"{reason_name}\n"
        f"<i>{reason_desc}</i>\n\n"
        f"{flag} <b>اللغة:</b> {lang_name}\n"
        f"📝 <b>القالب:</b> <code>{template_id}</code>\n\n"
        f"📮 <b>سيتم الإرسال إلى:</b>\n"
        f"<code>{report['to_email']}</code>\n\n"
        f"━━━ 📋 ━━━ <b>الخطوات</b>\n"
        f"1️⃣ اضغط على زر الإرسال تحت\n"
        f"2️⃣ هيفتح تطبيق الإيميل بتاعك\n"
        f"3️⃣ الرسالة تكون جاهزة ✅\n"
        f"4️⃣ اضغط <b>Send</b> بس\n\n"
        f"⚠️ <b>مهم:</b> متعدّلش النص\n"
        f"🔄 <b>للحظر الأسرع:</b> استخدم Blast Mode"
    )
    return text


# ============================================================
# [6] بناء أزرار البلاغ (الوضع العادي)
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
