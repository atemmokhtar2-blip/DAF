# force_subscribe.py
# ============================================================
# Force Subscribe System — الاشتراك الإجباري في القنوات
# ============================================================
import time
import json
from typing import Optional
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot, redis_client
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("force_subscribe")


# ============================================================
# [1] ⚙️ الإعدادات — عدّل هنا
# ============================================================

# القنوات المطلوبة (ممكن تزود أكتر من واحدة)
# ⚠️ لازم البوت يكون ADMIN في كل قناة عشان يقدر يتحقق
REQUIRED_CHANNELS = [
    {
        "id": "-1001234567890",       # ← ID القناة (بالسالب)
        "username": "@your_channel",  # ← يوزرنيم القناة
        "name": "قناة البوت الرسمية",   # ← اسم القناة
        "url": "https://t.me/your_channel",  # ← لينك القناة
    },
    # ضيف قنوات تانية هنا لو عايز
    # {
    #     "id": "-1009876543210",
    #     "username": "@channel2",
    #     "name": "قناة الدعم",
    #     "url": "https://t.me/channel2",
    # },
]

# هل الاشتراك إجباري ولا لأ
FORCE_SUBSCRIBE_ENABLED = True

# مدة الكاش (بالثواني) — لو المستخدم اتأكد إنه عضو، مش هنسأل تاني
# 300 = 5 دقايق
CHECK_CACHE_TTL = 300

# هل الأدمن معفي؟
ADMIN_EXEMPT = True


# ============================================================
# [2] Helpers
# ============================================================
def _cache_key(user_id):
    return f"fs_verified:{user_id}"


def _is_cached(user_id):
    """لو اتحقق قبل كده — استخدم الكاش"""
    if not redis_client:
        return False
    try:
        return bool(redis_client.get(_cache_key(user_id)))
    except Exception:
        return False


def _set_cache(user_id):
    """احفظ إن المستخدم اتحقق"""
    if not redis_client:
        return
    try:
        redis_client.setex(_cache_key(user_id), CHECK_CACHE_TTL, "1")
    except Exception as e:
        logger.warning(f"_set_cache error: {e}")


def _clear_cache(user_id):
    """امسح الكاش (لو اشترك جديد)"""
    if not redis_client:
        return
    try:
        redis_client.delete(_cache_key(user_id))
    except Exception:
        pass


# ============================================================
# [3] التحقق من العضوية
# ============================================================
def check_user_membership(user_id, channel):
    """
    يتحقق لو المستخدم عضو في قناة معينة
    Returns: True لو عضو، False لو لأ
    """
    try:
        member = bot.get_chat_member(channel["id"], user_id)
        status = member.status

        # الحالات: creator, administrator, member, restricted, left, kicked
        if status in ("creator", "administrator", "member"):
            return True
        # restricted ممكن يكون عضو بس ممنوع من حاجة
        if status == "restricted":
            # لو is_member = True
            return getattr(member, "is_member", False)
        return False
    except Exception as e:
        err = str(e).lower()
        # لو البوت مش أدمن أو القناة غلط
        if "chat not found" in err or "bot is not a member" in err:
            logger.error(f"❌ Bot is not admin in {channel['id']}!")
            # نعتبره عضو عشان ما نمنعش المستخدمين
            return True
        if "user not found" in err:
            return False
        logger.warning(f"check_user_membership error: {e}")
        # في حالة خطأ غير معروف، نسمح (أمان)
        return True


def check_all_channels(user_id):
    """
    يتحقق من كل القنوات
    Returns: (is_member: bool, missing_channels: list)
    """
    if not FORCE_SUBSCRIBE_ENABLED:
        return True, []

    # الأدمن معفي؟
    if ADMIN_EXEMPT:
        try:
            from points_system import is_admin
            if is_admin(user_id):
                return True, []
        except Exception:
            pass

    # الكاش
    if _is_cached(user_id):
        return True, []

    missing = []
    for channel in REQUIRED_CHANNELS:
        if not check_user_membership(user_id, channel):
            missing.append(channel)

    if not missing:
        _set_cache(user_id)
        metrics.inc_counter("fs_check_passed")
        return True, []

    metrics.inc_counter("fs_check_failed")
    return False, missing


# ============================================================
# [4] بناء رسالة الاشتراك الإجباري
# ============================================================
def build_subscribe_message(missing_channels, user_name=""):
    """
    يبني رسالة "اشترك أولاً"
    """
    if len(missing_channels) == 1:
        ch = missing_channels[0]
        text = (
            f"🔒 <b>عذراً {user_name}، لازم تشترك في القناة أولاً</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📢 <b>القناة المطلوبة:</b>\n"
            f"<b>{ch['name']}</b>\n\n"
            f"⚠️ <b>للاستخدام البوت، لازم:</b>\n"
            f"1️⃣ تدخل القناة\n"
            f"2️⃣ تعمل <b>Join / اشتراك</b>\n"
            f"3️⃣ ترجع هنا وتدوس <b>✅ تحققت</b>\n\n"
            f"💡 <b>ليه ده مطلوب؟</b>\n"
            f"عشان نضمن إن المستخدمين نشطين\n"
            f"والبوت يستمر في التطوير"
        )
    else:
        text = (
            f"🔒 <b>عذراً {user_name}، لازم تشترك في القنوات دي أولاً</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📢 <b>القنوات المطلوبة:</b>\n"
        )
        for i, ch in enumerate(missing_channels, 1):
            text += f"{i}. <b>{ch['name']}</b>\n"
        text += (
            f"\n⚠️ <b>للاستخدام البوت:</b>\n"
            f"1️⃣ ادخل كل قناة\n"
            f"2️⃣ اشترك في كل واحدة\n"
            f"3️⃣ ارجع ودوس <b>✅ تحققت</b>"
        )

    m = InlineKeyboardMarkup()

    # أزرار القنوات
    for ch in missing_channels:
        m.add(InlineKeyboardButton(
            f"📢 {ch['name']}",
            url=ch['url']
        ))

    # زر التحقق
    m.add(InlineKeyboardButton(
        "✅ تحققت من الاشتراك",
        callback_data="fs_check"
    ))

    return text, m


# ============================================================
# [5] Middleware — يتحقق من كل رسالة
# ============================================================
def check_and_prompt(message_or_call):
    """
    يتحقق لو المستخدم مشترك
    Returns: True لو مسموح يكمل، False لو محتاج يشترك
    """
    if not FORCE_SUBSCRIBE_ENABLED:
        return True

    try:
        # استخرج info من message أو call
        if hasattr(message_or_call, "from_user"):
            user_id = message_or_call.from_user.id
            user_name = message_or_call.from_user.first_name or ""
            chat_id = message_or_call.chat.id if hasattr(message_or_call, "chat") else message_or_call.message.chat.id
        else:
            return True

        is_member, missing = check_all_channels(user_id)

        if is_member:
            return True

        # ابعتله رسالة الاشتراك
        text, m = build_subscribe_message(missing, user_name)

        try:
            bot.send_message(
                chat_id, text,
                reply_markup=m,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.warning(f"send subscribe message error: {e}")

        return False

    except Exception as e:
        logger.exception(f"check_and_prompt error: {e}")
        # في حالة خطأ، اسمح
        return True


# ============================================================
# [6] Init — تسجيل الـ handler
# ============================================================
def init_force_subscribe(bot_instance=None):
    """تسجيل handler زر التحقق"""
    global bot
    if bot_instance:
        bot = bot_instance

    @bot.callback_query_handler(func=lambda call: call.data == "fs_check")
    def _handle_check(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        user_name = call.from_user.first_name or ""

        # امسح الكاش الأول
        _clear_cache(user_id)

        is_member, missing = check_all_channels(user_id)

        if is_member:
            bot.answer_callback_query(call.id, "✅ تمام! تم التحقق", show_alert=False)

            # امسح رسالة الاشتراك
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass

            # ابعتله القائمة الرئيسية
            try:
                from bot_handlers.keyboards import main_menu, main_menu_text
                bot.send_message(
                    chat_id,
                    main_menu_text(user_id),
                    reply_markup=main_menu(user_id),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"send main menu error: {e}")
                bot.send_message(
                    chat_id,
                    "✅ <b>تم التحقق بنجاح!</b>\n\n"
                    "استخدم /start لفتح القائمة",
                    parse_mode="HTML"
                )
        else:
            bot.answer_callback_query(
                call.id,
                "❌ لسه مشتركتش! اشترك في القنوات الأول",
                show_alert=True
            )

            # حدّث رسالة الاشتراك
            text, m = build_subscribe_message(missing, user_name)
            try:
                bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=m,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except Exception:
                pass

    logger.info(f"[+] Force Subscribe initialized | Channels: {len(REQUIRED_CHANNELS)}")
    return True


# ============================================================
# [7] Public API
# ============================================================
def is_subscribed(user_id):
    """يتحقق لو المستخدم مشترك (بدون ما يبعت رسالة)"""
    is_member, _ = check_all_channels(user_id)
    return is_member


def get_required_channels():
    """يرجع قائمة القنوات"""
    return REQUIRED_CHANNELS
