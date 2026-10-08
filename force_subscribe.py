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
# [1] ⚙️ الإعدادات — ضفت قناتك
# ============================================================

REQUIRED_CHANNELS = [
    {
        "id": "-1002222222222",       # ⚠️ اتحقق من ID الحقيقي للقناة
        "username": "@K_J6k",          # ⚠️ يوزرنيم القناة
        "name": "K_J6 قناة البوت",      # اسم القناة المعروض
        "url": "https://t.me/K_J6k",  # رابط القناة
    },
]

FORCE_SUBSCRIBE_ENABLED = True
CHECK_CACHE_TTL = 300  # 5 دقائق كاش
ADMIN_EXEMPT = True


# ============================================================
# [2] Helpers
# ============================================================
def _cache_key(user_id):
    return f"fs_verified:{user_id}"


def _is_cached(user_id):
    if not redis_client:
        return False
    try:
        return bool(redis_client.get(_cache_key(user_id)))
    except Exception:
        return False


def _set_cache(user_id):
    if not redis_client:
        return
    try:
        redis_client.setex(_cache_key(user_id), CHECK_CACHE_TTL, "1")
    except Exception as e:
        logger.warning(f"_set_cache error: {e}")


def _clear_cache(user_id):
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
    try:
        member = bot.get_chat_member(channel["id"], user_id)
        status = member.status

        if status in ("creator", "administrator", "member"):
            return True
        if status == "restricted":
            return getattr(member, "is_member", False)
        return False
    except Exception as e:
        err = str(e).lower()

        # البوت مش أدمن في القناة → لازم نبلغ
        if "chat not found" in err:
            logger.error(
                f"❌ Chat not found: {channel['id']} — "
                f"تأكد إن البوت مضاف في القناة كـ Admin!"
            )
            return True  # اسمح للمستخدم عشان ما نوقفش البوت

        if "bot is not a member" in err or "not enough rights" in err:
            logger.error(
                f"❌ Bot not admin in {channel['id']} — "
                f"لازم تضيف البوت كـ Admin!"
            )
            return True  # اسمح

        if "user not found" in err:
            return False

        logger.warning(f"check_user_membership error: {e}")
        return True  # اسمح في حالة خطأ غير معروف


def check_all_channels(user_id):
    if not FORCE_SUBSCRIBE_ENABLED:
        return True, []

    if ADMIN_EXEMPT:
        try:
            from points_system import is_admin
            if is_admin(user_id):
                return True, []
        except Exception:
            pass

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
# [4] بناء رسالة الاشتراك
# ============================================================
def build_subscribe_message(missing_channels, user_name=""):
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

    for ch in missing_channels:
        m.add(InlineKeyboardButton(
            f"📢 {ch['name']}",
            url=ch['url']
        ))

    m.add(InlineKeyboardButton(
        "✅ تحققت من الاشتراك",
        callback_data="fs_check"
    ))

    return text, m


# ============================================================
# [5] Middleware
# ============================================================
def check_and_prompt(message_or_call):
    if not FORCE_SUBSCRIBE_ENABLED:
        return True

    try:
        if hasattr(message_or_call, "from_user"):
            user_id = message_or_call.from_user.id
            user_name = message_or_call.from_user.first_name or ""
            if hasattr(message_or_call, "chat"):
                chat_id = message_or_call.chat.id
            elif hasattr(message_or_call, "message"):
                chat_id = message_or_call.message.chat.id
            else:
                return True
        else:
            return True

        is_member, missing = check_all_channels(user_id)

        if is_member:
            return True

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
        return True


# ============================================================
# [6] Init — تسجيل الـ handler
# ============================================================
def init_force_subscribe(bot_instance=None):
    global bot
    if bot_instance:
        bot = bot_instance

    @bot.callback_query_handler(func=lambda call: call.data == "fs_check")
    def _handle_check(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        user_name = call.from_user.first_name or ""

        _clear_cache(user_id)

        is_member, missing = check_all_channels(user_id)

        if is_member:
            bot.answer_callback_query(call.id, "✅ تمام! تم التحقق", show_alert=False)

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

    logger.info(
        f"[+] Force Subscribe initialized | "
        f"Channels: {len(REQUIRED_CHANNELS)}"
    )
    return True


# ============================================================
# [7] Public API
# ============================================================
def is_subscribed(user_id):
    is_member, _ = check_all_channels(user_id)
    return is_member


def get_required_channels():
    return REQUIRED_CHANNELS
