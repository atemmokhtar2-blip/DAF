# bot_handlers/steps/social_profile_steps.py
# ============================================================
# Steps لبناء قالب البروفايل
# ============================================================

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot, PUBLIC_URL
from logging_config import get_logger

logger = get_logger("bot_handlers.steps.social_profile")


# ─── Session State ───
# بنحفظ حالة البناء في Redis
def _state_key(chat_id):
    return f"profile_build_state:{chat_id}"


def _save_state(chat_id, state):
    try:
        from config import redis_client
        if redis_client:
            import json
            redis_client.setex(_state_key(chat_id), 600, json.dumps(state))
    except Exception:
        pass


def _get_state(chat_id):
    try:
        from config import redis_client
        if redis_client:
            import json
            raw = redis_client.get(_state_key(chat_id))
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return {}


def _clear_state(chat_id):
    try:
        from config import redis_client
        if redis_client:
            redis_client.delete(_state_key(chat_id))
    except Exception:
        pass


# ══════════════════════════════════════════════════
# Step 1: الاسم
# ══════════════════════════════════════════════════
def step_name(message):
    chat_id = message.chat.id
    if not message.text or len(message.text.strip()) < 2:
        bot.send_message(chat_id, "❌ الاسم قصير جداً")
        return

    name = message.text.strip()[:50]
    _save_state(chat_id, {"name": name, "step": "title"})

    msg = bot.send_message(
        chat_id,
        "✏️ <b>المسمى / الوظيفة</b>\n\n"
        "مثال: <code>مبرمج</code>، <code>مدير تسويق</code>\n"
        "أو اكتب <code>تخطي</code> لو مش عايز",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_title)


# ══════════════════════════════════════════════════
# Step 2: المسمى
# ══════════════════════════════════════════════════
def step_title(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    title = "" if text == "تخطي" else text[:100]

    state = _get_state(chat_id)
    state["title"] = title
    state["step"] = "bio"
    _save_state(chat_id, state)

    msg = bot.send_message(
        chat_id,
        "📝 <b>نبذة قصيرة</b>\n\n"
        "مثال: <code>مهتم بالتكنولوجيا والبرمجة</code>\n"
        "أو اكتب <code>تخطي</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_bio)


# ══════════════════════════════════════════════════
# Step 3: النبذة
# ══════════════════════════════════════════════════
def step_bio(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    bio = "" if text == "تخطي" else text[:300]

    state = _get_state(chat_id)
    state["bio"] = bio
    state["step"] = "phone"
    _save_state(chat_id, state)

    msg = bot.send_message(
        chat_id,
        "📞 <b>رقم الهاتف</b>\n\n"
        "مثال: <code>+201012345678</code>\n"
        "أو اكتب <code>تخطي</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_phone)


# ══════════════════════════════════════════════════
# Step 4: الهاتف
# ══════════════════════════════════════════════════
def step_phone(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    phone = "" if text == "تخطي" else text[:30]

    state = _get_state(chat_id)
    state["phone"] = phone
    state["step"] = "whatsapp"
    _save_state(chat_id, state)

    msg = bot.send_message(
        chat_id,
        "💬 <b>رقم واتساب</b>\n\n"
        "مثال: <code>+201012345678</code>\n"
        "أو اكتب <code>تخطي</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_whatsapp)


# ══════════════════════════════════════════════════
# Step 5: WhatsApp
# ══════════════════════════════════════════════════
def step_whatsapp(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    whatsapp = "" if text == "تخطي" else text[:30]

    state = _get_state(chat_id)
    state["whatsapp"] = whatsapp
    state["step"] = "telegram"
    _save_state(chat_id, state)

    msg = bot.send_message(
        chat_id,
        "✈️ <b>يوزر تلجرام</b>\n\n"
        "مثال: <code>@username</code>\n"
        "أو اكتب <code>تخطي</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_telegram)


# ══════════════════════════════════════════════════
# Step 6: Telegram
# ══════════════════════════════════════════════════
def step_telegram(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    telegram = "" if text == "تخطي" else text[:50]

    state = _get_state(chat_id)
    state["telegram"] = telegram
    state["step"] = "instagram"
    _save_state(chat_id, state)

    msg = bot.send_message(
        chat_id,
        "📷 <b>يوزر انستقرام</b>\n\n"
        "مثال: <code>@username</code>\n"
        "أو اكتب <code>تخطي</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_instagram)


# ══════════════════════════════════════════════════
# Step 7: Instagram
# ══════════════════════════════════════════════════
def step_instagram(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    instagram = "" if text == "تخطي" else text[:50]

    state = _get_state(chat_id)
    state["instagram"] = instagram
    state["step"] = "facebook"
    _save_state(chat_id, state)

    msg = bot.send_message(
        chat_id,
        "📘 <b>يوزر فيسبوك</b>\n\n"
        "مثال: <code>username</code>\n"
        "أو اكتب <code>تخطي</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_facebook)


# ══════════════════════════════════════════════════
# Step 8: Facebook
# ══════════════════════════════════════════════════
def step_facebook(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    facebook = "" if text == "تخطي" else text[:50]

    state = _get_state(chat_id)
    state["facebook"] = facebook
    state["step"] = "email"
    _save_state(chat_id, state)

    msg = bot.send_message(
        chat_id,
        "✉️ <b>الإيميل</b>\n\n"
        "مثال: <code>user@example.com</code>\n"
        "أو اكتب <code>تخطي</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_email)


# ══════════════════════════════════════════════════
# Step 9: Email
# ══════════════════════════════════════════════════
def step_email(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    email = "" if text == "تخطي" else text[:80]

    state = _get_state(chat_id)
    state["email"] = email
    state["step"] = "website"
    _save_state(chat_id, state)

    msg = bot.send_message(
        chat_id,
        "🌐 <b>الموقع الرسمي</b>\n\n"
        "مثال: <code>https://example.com</code>\n"
        "أو اكتب <code>تخطي</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, step_website)


# ══════════════════════════════════════════════════
# Step 10: Website + إنشاء
# ══════════════════════════════════════════════════
def step_website(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    website = "" if text == "تخطي" else text[:200]

    state = _get_state(chat_id)
    state["website"] = website
    state["chat_id"] = chat_id

    # ─── أنشئ البروفايل ───
    try:
        from fake_sites.social_profile.routes import create_profile
        session_id = create_profile(chat_id, state)

        if not session_id:
            bot.send_message(chat_id, "❌ فشل إنشاء البروفايل")
            return

        link = f"{PUBLIC_URL}/profile/{session_id}"

        text_out = (
            f"✅ <b>تم إنشاء البروفايل!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"

            f"👤 <b>الاسم:</b> {state.get('name', '')}\n"
            f"💼 <b>المسمى:</b> {state.get('title') or '—'}\n"
            f"📝 <b>النبذة:</b> {state.get('bio') or '—'}\n"
            f"📞 <b>الهاتف:</b> {state.get('phone') or '—'}\n"
            f"💬 <b>واتساب:</b> {state.get('whatsapp') or '—'}\n"
            f"✈️ <b>تلجرام:</b> {state.get('telegram') or '—'}\n"
            f"📷 <b>انستقرام:</b> {state.get('instagram') or '—'}\n"
            f"📘 <b>فيسبوك:</b> {state.get('facebook') or '—'}\n"
            f"✉️ <b>الإيميل:</b> {state.get('email') or '—'}\n"
            f"🌐 <b>الموقع:</b> {state.get('website') or '—'}\n\n"

            f"🔗 <b>الرابط:</b>\n"
            f"<code>{link}</code>\n\n"

            f"💡 <i>أرسل الرابط للضحية. يقدر يرفع صوره في البروفايل.</i>"
        )

        m = InlineKeyboardMarkup()
        try:
            from telebot.types import CopyTextButton
            m.add(InlineKeyboardButton(
                "📋 نسخ الرابط",
                copy_text=CopyTextButton(text=link)
            ))
        except Exception:
            pass

        m.add(InlineKeyboardButton("🔙 رجوع للقوالب العامة", callback_data="se_cat_universal"))
        m.add(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main"))

        bot.send_message(chat_id, text_out, parse_mode="HTML", reply_markup=m)

        logger.info(f"Social profile created: {session_id} for chat {chat_id}")

    except Exception as e:
        logger.exception(f"step_website error: {e}")
        bot.send_message(chat_id, f"❌ خطأ: {str(e)[:200]}")

    finally:
        _clear_state(chat_id)
