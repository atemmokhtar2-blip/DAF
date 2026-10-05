# admin_tools/whatsapp_blast/bot_handlers_real.py
# ============================================================

import io
import qrcode
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot
from logging_config import get_logger

from .core_real import (
    worker_health, worker_init, worker_get_qr,
    worker_get_contacts, worker_send_message,
    worker_send_file, worker_bulk_blast,
    worker_blast_status, worker_stop_blast, worker_logout,
    create_real_session, get_real_session,
    get_admin_real_sessions, delete_real_session,
)

logger = get_logger("admin_tools.whatsapp_blast.bot_real")


try:
    from points_system import ADMIN_IDS, is_admin
except Exception:
    ADMIN_IDS = [7631249810]
    def is_admin(uid):
        return int(uid) in ADMIN_IDS


# ─── State Management ───
_states = {}


def _get_state(admin_id):
    return _states.get(admin_id)


def _set_state(admin_id, session_id):
    _states[admin_id] = {"session_id": session_id}


def register_whatsapp_blast_real_handlers(bot):

    # ═══════════════════════════════════════════════════
    # Open Menu
    # ═══════════════════════════════════════════════════
    @bot.callback_query_handler(func=lambda c: c.data == "admin_wb_menu")
    def wb_menu(call):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        _show_main_menu(call.message.chat.id)

    # ═══════════════════════════════════════════════════
    # Main Router
    # ═══════════════════════════════════════════════════
    @bot.callback_query_handler(func=lambda c: c.data.startswith("wbr_"))
    def wb_real_callback(call):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
            return

        data = call.data
        chat_id = call.message.chat.id
        admin_id = call.from_user.id

        # ─── Sessions ───
        if data == "wbr_new":
            bot.answer_callback_query(call.id)
            _create_session(chat_id, admin_id)
            return

        if data == "wbr_list":
            bot.answer_callback_query(call.id)
            _list_sessions(chat_id, admin_id)
            return

        # ─── Health ───
        if data == "wbr_health":
            _check_health(call)
            return

        # ─── Init & QR ───
        if data == "wbr_init":
            _init_worker(call)
            return

        if data == "wbr_qr":
            _send_qr(call)
            return

        # ─── Contacts ───
        if data == "wbr_contacts":
            _fetch_contacts(call)
            return

        if data == "wbr_export_contacts":
            _export_contacts(call)
            return

        # ─── Set Message / File ───
        if data == "wbr_send_text":
            bot.answer_callback_query(call.id)
            _prompt_text_message(chat_id)
            return

        if data == "wbr_send_file":
            bot.answer_callback_query(call.id)
            _prompt_file_url(chat_id)
            return

        # ─── Blast ───
        if data == "wbr_blast":
            _start_blast(call)
            return

        if data == "wbr_confirm_blast":
            _confirm_blast(call)
            return

        if data == "wbr_cancel":
            bot.answer_callback_query(call.id, "❌ اتلغى")
            bot.send_message(chat_id, "❌ اتلغى", reply_markup=_main_keyboard())
            return

        if data == "wbr_status":
            _show_status(call)
            return

        if data == "wbr_stop":
            _stop_blast(call)
            return

        # ─── Logout ───
        if data == "wbr_logout":
            _logout(call)
            return

    # ═══════════════════════════════════════════════════
    # Step Handlers
    # ═══════════════════════════════════════════════════
    def _prompt_text_message(chat_id):
        msg = bot.send_message(
            chat_id,
            "✉️ <b>أرسل نص الرسالة</b>\n\n"
            "الرسالة هتتبعت لكل جهات الاتصال.",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, _save_text_message)

    def _save_text_message(message):
        if not is_admin(message.from_user.id):
            return
        state = _get_state(message.from_user.id)
        if not state:
            return
        session = get_real_session(state["session_id"])
        if session:
            session.message_text = message.text
            session.add_log(f"💬 Message set: {message.text[:50]}...")
        bot.send_message(
            message.chat.id,
            f"✅ <b>تم تسجيل الرسالة</b>\n\n<i>{message.text[:200]}</i>",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )

    def _prompt_file_url(chat_id):
        msg = bot.send_message(
            chat_id,
            "📎 <b>أرسل رابط الملف</b>\n\n"
            "مثال: <code>https://example.com/invoice.zip</code>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, _save_file_url)

    def _save_file_url(message):
        if not is_admin(message.from_user.id):
            return
        state = _get_state(message.from_user.id)
        if not state:
            return
        session = get_real_session(state["session_id"])
        if session:
            session.payload_url = message.text.strip()
            session.add_log(f"📎 File URL: {message.text[:50]}...")
        bot.send_message(
            message.chat.id,
            f"✅ <b>تم تسجيل رابط الملف</b>\n\n<code>{message.text[:200]}</code>",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )


# ============================================================
# UI Functions
# ============================================================
def _show_main_menu(chat_id):
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("🆕 جلسة جديدة", callback_data="wbr_new"))
    m.add(InlineKeyboardButton("📋 جلساتي", callback_data="wbr_list"))
    m.add(InlineKeyboardButton("💚 فحص الـ Worker", callback_data="wbr_health"))
    m.add(InlineKeyboardButton("🔙 رجوع للوحة الأدمن", callback_data="admin_panel"))

    bot.send_message(
        chat_id,
        "⚡ <b>WhatsApp Blast — Real Mode</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🔴 <b>الوضع الحقيقي</b>\n"
        "محتاج WA Worker شغال على سيرفر منفصل.\n\n"
        "🎯 ابدأ بجلسة جديدة:",
        parse_mode="HTML",
        reply_markup=m
    )


def _main_keyboard():
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("🔌 تهيئة Worker", callback_data="wbr_init"),
        InlineKeyboardButton("📱 عرض QR", callback_data="wbr_qr"),
    )
    m.row(
        InlineKeyboardButton("👥 جهات الاتصال", callback_data="wbr_contacts"),
        InlineKeyboardButton("📥 تصدير", callback_data="wbr_export_contacts"),
    )
    m.row(
        InlineKeyboardButton("✉️ تحديد رسالة", callback_data="wbr_send_text"),
        InlineKeyboardButton("📎 تحديد ملف", callback_data="wbr_send_file"),
    )
    m.row(InlineKeyboardButton("🚀 بدء الإرسال", callback_data="wbr_blast"))
    m.row(
        InlineKeyboardButton("📊 حالة", callback_data="wbr_status"),
        InlineKeyboardButton("⏹️ إيقاف", callback_data="wbr_stop"),
    )
    m.row(
        InlineKeyboardButton("🚪 تسجيل خروج", callback_data="wbr_logout"),
        InlineKeyboardButton("🔙 رجوع", callback_data="admin_wb_menu"),
    )
    return m


def _create_session(chat_id, admin_id):
    session = create_real_session(admin_id)
    _set_state(admin_id, session.session_id)
    bot.send_message(
        chat_id,
        f"✅ <b>جلسة جديدة</b>\n"
        f"🆔 <code>{session.session_id}</code>\n\n"
        f"الخطوة التالية: <b>تهيئة Worker</b>",
        parse_mode="HTML",
        reply_markup=_main_keyboard()
    )


def _list_sessions(chat_id, admin_id):
    sessions = get_admin_real_sessions(admin_id)
    if not sessions:
        bot.send_message(chat_id, "📭 مفيش جلسات", reply_markup=_main_keyboard())
        return

    m = InlineKeyboardMarkup()
    for s in sessions:
        m.add(InlineKeyboardButton(
            f"⚡ {s.session_id[:8]} | {s.status}",
            callback_data=f"wbr_view_{s.session_id}"
        ))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="admin_wb_menu"))

    bot.send_message(
        chat_id,
        f"📋 <b>جلساتي ({len(sessions)})</b>",
        parse_mode="HTML",
        reply_markup=m
    )


def _check_health(call):
    bot.answer_callback_query(call.id, "🔍 فحص...")
    result = worker_health()

    if "error" in result:
        text = (
            f"❌ <b>الـ Worker مش متاح</b>\n\n"
            f"<code>{result['error']}</code>\n\n"
            f"💡 تأكد من WA_WORKER_URL و WA_WORKER_SECRET"
        )
    else:
        ready = result.get("ready", False)
        text = (
            f"✅ <b>الـ Worker شغال</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>الحالة:</b> {'🟢 Ready' if ready else '🟡 Not ready'}\n"
            f"📱 <b>الجلسة:</b> <code>{result.get('session', '—')}</code>"
        )

    bot.send_message(call.message.chat.id, text, parse_mode="HTML",
                     reply_markup=_main_keyboard())


def _init_worker(call):
    bot.answer_callback_query(call.id, "⏳ تهيئة...")
    state = _get_state(call.from_user.id)
    session_name = state["session_id"] if state else "default"
    result = worker_init(session_name)

    if "error" in result:
        bot.send_message(call.message.chat.id,
                         f"❌ <b>فشل التهيئة</b>\n<code>{result['error']}</code>",
                         parse_mode="HTML", reply_markup=_main_keyboard())
        return

    if result.get("ok"):
        bot.send_message(
            call.message.chat.id,
            "✅ <b>تمت التهيئة</b>\n\n"
            "⏳ اضغط <b>عرض QR</b> بعد 5 ثواني",
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )
    else:
        bot.send_message(call.message.chat.id,
                         "⚠️ <b>فشل التهيئة</b>",
                         parse_mode="HTML", reply_markup=_main_keyboard())


def _send_qr(call):
    bot.answer_callback_query(call.id, "📱 جاري جلب QR...")
    result = worker_get_qr()

    if "error" in result:
        bot.send_message(call.message.chat.id,
                         f"❌ {result['error']}",
                         reply_markup=_main_keyboard())
        return

    if result.get("ready"):
        bot.send_message(call.message.chat.id,
                         "✅ <b>الجلسة مسجلة بالفعل!</b>",
                         parse_mode="HTML", reply_markup=_main_keyboard())
        return

    qr_text = result.get("qr")
    if not qr_text:
        bot.send_message(call.message.chat.id,
                         "⚠️ مفيش QR. جرب تهيئة الأول.",
                         reply_markup=_main_keyboard())
        return

    try:
        qr_img = qrcode.make(qr_text)
        buf = io.BytesIO()
        qr_img.save(buf, format='PNG')
        buf.seek(0)
        buf.name = "whatsapp_qr.png"

        bot.send_photo(
            call.message.chat.id, buf,
            caption=(
                "📱 <b>QR Code للواتساب</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "افتح WhatsApp → Linked Devices → Link a Device\n"
                "وامسح الكود ده.\n\n"
                "⏱️ <i>الكود صالح 60 ثانية</i>"
            ),
            parse_mode="HTML",
            reply_markup=_main_keyboard()
        )
    except Exception as e:
        logger.exception(f"QR generation failed: {e}")
        bot.send_message(call.message.chat.id,
                         f"❌ فشل توليد الصورة: {e}",
                         reply_markup=_main_keyboard())


def _fetch_contacts(call):
    bot.answer_callback_query(call.id, "⏳ جاري الجلب...")
    state = _get_state(call.from_user.id)
    if not state:
        bot.send_message(call.message.chat.id, "❌ ابدأ جلسة أولاً")
        return
    session = get_real_session(state["session_id"])
    if not session:
        bot.send_message(call.message.chat.id, "❌ الجلسة مش موجودة")
        return

    session.add_log("🔍 Fetching contacts...")
    result = worker_get_contacts()

    if "error" in result:
        bot.send_message(call.message.chat.id,
                         f"❌ {result['error']}",
                         reply_markup=_main_keyboard())
        return

    contacts = result.get("contacts", [])
    session.contacts = contacts
    session.status = "contacts_loaded"
    session.add_log(f"✅ Got {len(contacts)} contacts")

    text = (
        f"👥 <b>جهات الاتصال</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>العدد:</b> <code>{len(contacts)}</code>\n\n"
    )
    for c in contacts[:5]:
        text += f"• {c.get('name', 'Unknown')} — <code>{c.get('number', '')}</code>\n"
    if len(contacts) > 5:
        text += f"\n<i>... و {len(contacts) - 5} آخرين</i>"

    bot.send_message(call.message.chat.id, text,
                     parse_mode="HTML", reply_markup=_main_keyboard())


def _export_contacts(call):
    bot.answer_callback_query(call.id)
    state = _get_state(call.from_user.id)
    if not state:
        return
    session = get_real_session(state["session_id"])
    if not session or not session.contacts:
        bot.send_message(call.message.chat.id, "❌ مفيش جهات اتصال")
        return

    lines = []
    for c in session.contacts:
        lines.append(f"{c.get('number', '')} | {c.get('name', '')}")

    buf = io.BytesIO("\n".join(lines).encode('utf-8'))
    buf.name = f"contacts_{session.session_id}.txt"

    bot.send_document(call.message.chat.id, buf,
                      caption=f"📥 <b>{len(session.contacts)} جهة اتصال</b>",
                      parse_mode="HTML")


def _start_blast(call):
    bot.answer_callback_query(call.id)
    state = _get_state(call.from_user.id)
    if not state:
        return
    session = get_real_session(state["session_id"])
    if not session:
        return

    if not session.contacts:
        bot.answer_callback_query(call.id, "❌ اجلب جهات الاتصال أولاً", show_alert=True)
        return

    if not session.message_text and not session.payload_url:
        bot.answer_callback_query(call.id, "❌ حدد رسالة أو ملف", show_alert=True)
        return

    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("✅ تأكيد الإرسال", callback_data="wbr_confirm_blast"),
        InlineKeyboardButton("❌ إلغاء", callback_data="wbr_cancel"),
    )

    bot.send_message(
        call.message.chat.id,
        f"⚠️ <b>تأكيد الإرسال</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 <b>العدد:</b> <code>{len(session.contacts)}</code>\n"
        f"✉️ <b>الرسالة:</b> <code>{(session.message_text or '—')[:50]}</code>\n"
        f"📎 <b>الملف:</b> <code>{(session.payload_url or '—')[:50]}</code>\n\n"
        f"⏱️ <b>التأخير:</b> 3-8 ثواني بين كل رسالة",
        parse_mode="HTML",
        reply_markup=m
    )


def _confirm_blast(call):
    bot.answer_callback_query(call.id, "🚀 بدء...")
    state = _get_state(call.from_user.id)
    if not state:
        return
    session = get_real_session(state["session_id"])
    if not session:
        return

    contact_ids = [{"id": c["id"]} for c in session.contacts if c.get("id")]

    result = worker_bulk_blast(
        contacts=contact_ids,
        message=session.message_text,
        file_url=session.payload_url,
        caption=session.message_text,
        delay_min=3000,
        delay_max=8000,
        session_id=session.session_id
    )

    if "error" in result:
        bot.send_message(call.message.chat.id,
                         f"❌ {result['error']}",
                         reply_markup=_main_keyboard())
        return

    session.blast_id = result.get("blast_id")
    session.status = "blasting"
    session.add_log(f"🚀 Blast started: {session.blast_id}")

    bot.send_message(
        call.message.chat.id,
        f"🚀 <b>بدأ الإرسال!</b>\n\n"
        f"🆔 <code>{session.blast_id}</code>\n"
        f"👥 <code>{len(contact_ids)}</code> جهة اتصال\n\n"
        f"اضغط <b>📊 حالة</b> للمتابعة",
        parse_mode="HTML",
        reply_markup=_main_keyboard()
    )


def _show_status(call):
    bot.answer_callback_query(call.id, "🔄 تحديث...")
    state = _get_state(call.from_user.id)
    session = get_real_session(state["session_id"]) if state else None

    if not session or not session.blast_id:
        bot.send_message(call.message.chat.id, "⚠️ مفيش إرسال شغال",
                         reply_markup=_main_keyboard())
        return

    result = worker_blast_status(session.blast_id)

    if "error" in result:
        bot.send_message(call.message.chat.id, f"❌ {result['error']}",
                         reply_markup=_main_keyboard())
        return

    total = result.get("total", 0)
    sent = result.get("sent", 0)
    failed = result.get("failed", 0)
    status = result.get("status", "unknown")

    session.sent = sent
    session.failed = failed
    session.status = status

    text = (
        f"📊 <b>حالة الإرسال</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 <b>الحالة:</b> <code>{status}</code>\n"
        f"👥 <b>الإجمالي:</b> <code>{total}</code>\n"
        f"✅ <b>نجح:</b> <code>{sent}</code>\n"
        f"❌ <b>فشل:</b> <code>{failed}</code>\n"
    )
    bot.send_message(call.message.chat.id, text,
                     parse_mode="HTML", reply_markup=_main_keyboard())


def _stop_blast(call):
    bot.answer_callback_query(call.id, "⏹️ جاري الإيقاف...")
    state = _get_state(call.from_user.id)
    session = get_real_session(state["session_id"]) if state else None
    if not session or not session.blast_id:
        return

    result = worker_stop_blast(session.blast_id)
    if "error" in result:
        bot.send_message(call.message.chat.id, f"❌ {result['error']}")
        return

    session.status = "stopped"
    session.add_log("⏹️ Blast stopped")
    bot.send_message(call.message.chat.id, "⏹️ <b>تم الإيقاف</b>",
                     parse_mode="HTML", reply_markup=_main_keyboard())


def _logout(call):
    bot.answer_callback_query(call.id, "🚪 جاري الخروج...")
    result = worker_logout()
    bot.send_message(call.message.chat.id,
                     "🚪 <b>تم تسجيل الخروج</b>",
                     parse_mode="HTML", reply_markup=_main_keyboard())
