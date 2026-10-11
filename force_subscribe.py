# force_subscribe.py
# ============================================================
# Force Subscribe System — v3.0
# + Pending Referral Tracking
# ============================================================
import time
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot, redis_client
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("force_subscribe")


# ============================================================
# [1] الإعدادات
# ============================================================
REQUIRED_CHANNELS = [
    {
        "id": "-1004463431688",       # ⚠️ حط الـ ID الحقيقي
        "username": "@K_J6k",
        "name": "K_J6 قناة البوت",
        "url": "https://t.me/K_J6k",
    },
]

FORCE_SUBSCRIBE_ENABLED = True
CHECK_CACHE_TTL = 300
ADMIN_EXEMPT = True

# ⚡ TTL لكود الإحالة المعلّق (10 دقايق)
PENDING_REF_TTL = 600


# ============================================================
# [2] Helpers - Cache
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
# [3] ⚡ Pending Referral Storage
# ============================================================
def _pending_ref_key(user_id):
    return f"pending_ref:{user_id}"


def save_pending_ref(user_id, ref_code):
    """
    يحفظ كود الإحالة مؤقتاً لحد ما المستخدم يخلّص اشتراك
    """
    if not redis_client or not ref_code:
        return False
    try:
        redis_client.setex(
            _pending_ref_key(user_id),
            PENDING_REF_TTL,
            ref_code
        )
        logger.info(f"[PENDING-REF] Saved: user={user_id} | code={ref_code}")
        return True
    except Exception as e:
        logger.warning(f"save_pending_ref error: {e}")
        return False


def get_pending_ref(user_id):
    """
    يرجع كود الإحالة المعلّق (لو موجود)
    """
    if not redis_client:
        return None
    try:
        raw = redis_client.get(_pending_ref_key(user_id))
        if raw:
            code = raw.decode() if isinstance(raw, bytes) else raw
            logger.info(f"[PENDING-REF] Retrieved: user={user_id} | code={code}")
            return code
    except Exception as e:
        logger.warning(f"get_pending_ref error: {e}")
    return None


def clear_pending_ref(user_id):
    """
    يمسح كود الإحالة المعلّق بعد الاستخدام
    """
    if not redis_client:
        return
    try:
        redis_client.delete(_pending_ref_key(user_id))
        logger.info(f"[PENDING-REF] Cleared: user={user_id}")
    except Exception:
        pass


# ============================================================
# [4] التحقق من العضوية
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

        if "chat not found" in err:
            logger.error(
                f"❌ Chat not found: {channel['id']} — "
                f"تأكد إن البوت مضاف في القناة كـ Admin!"
            )
            return True

        if "bot is not a member" in err or "not enough rights" in err:
            logger.error(f"❌ Bot not admin in {channel['id']}!")
            return True

        if "user not found" in err:
            return False

        logger.warning(f"check_user_membership error: {e}")
        return True


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
# [5] رسالة الاشتراك
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
            f"💡 <b>ملاحظة:</b> لو دخلت من رابط إحالة،\n"
            f"الإحالة هتتحسب أوتوماتيك بعد التحقق ✨"
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
# [6] Middleware
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
# [7] ⚡ Handle fs_check - مع معالجة الإحالة
# ============================================================
def handle_fs_check_callback(call):
    """
    يتعامل مع زر "تحققت من الاشتراك"
    ⚡ الإضافة الجديدة: يتحقق من وجود كود إحالة معلّق ويسجّله
    """
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    user_name = call.from_user.first_name or ""
    username = call.from_user.username or "Unknown"

    logger.info(f"[FS_CHECK] user={user_id} pressed check button")

    _clear_cache(user_id)
    is_member, missing = check_all_channels(user_id)

    logger.info(
        f"[FS_CHECK] user={user_id} | is_member={is_member} | "
        f"missing={len(missing)}"
    )

    if is_member:
        # ✅ المستخدم مشترك
        try:
            bot.answer_callback_query(
                call.id,
                "✅ تمام! تم التحقق بنجاح",
                show_alert=False
            )
        except Exception:
            pass

        # امسح رسالة الاشتراك
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception as e:
            logger.debug(f"delete message error: {e}")

        # ═══════════════════════════════════════════════
        # 🎁 معالجة الإحالة المعلّقة
        # ═══════════════════════════════════════════════
        try:
            _process_pending_referral(user_id, user_name, username)
        except Exception as e:
            logger.exception(f"[FS_CHECK] pending referral error: {e}")

        # ابعتله القائمة الرئيسية
        try:
            from bot_handlers.keyboards import main_menu, main_menu_text
            bot.send_message(
                chat_id,
                main_menu_text(user_id),
                reply_markup=main_menu(user_id),
                parse_mode="HTML"
            )
            logger.info(f"[FS_CHECK] Main menu sent to {user_id}")
        except Exception as e:
            logger.warning(f"[FS_CHECK] send main menu error: {e}")
            try:
                bot.send_message(
                    chat_id,
                    "✅ <b>تم التحقق بنجاح!</b>\n\n"
                    "استخدم /start لفتح القائمة الرئيسية",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    else:
        # ❌ المستخدم مش مشترك
        try:
            bot.answer_callback_query(
                call.id,
                "❌ لسه مشتركتش! اشترك في القناة الأول",
                show_alert=True
            )
        except Exception:
            pass

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
        except Exception as e:
            logger.warning(f"[FS_CHECK] edit message error: {e}")


# ============================================================
# [8] 🎁 معالجة الإحالة المعلّقة
# ============================================================
def _process_pending_referral(user_id, user_name, username):
    """
    يتعامل مع كود الإحالة المعلّق بعد التحقق من الاشتراك
    """
    # هات كود الإحالة المعلّق
    pending_ref = get_pending_ref(user_id)

    if not pending_ref:
        logger.info(f"[FS_CHECK] No pending referral for user={user_id}")
        return

    logger.info(
        f"[FS_CHECK] Processing pending referral: "
        f"user={user_id} | code={pending_ref}"
    )

    try:
        from imports_manager import (
            get_user,
            get_or_create_user,
            get_referral_by_code,
        )
        from points_system import POINTS_SYSTEM_ENABLED

        # 1. تحقق إن المستخدم جديد (مش موجود قبل كده)
        existing_user = get_user(user_id)

        if existing_user:
            # المستخدم موجود بالفعل - مش هنحسب الإحالة
            logger.info(
                f"[FS_CHECK] User {user_id} already exists — "
                f"referral not counted"
            )
            clear_pending_ref(user_id)
            return

        # 2. تحقق من صحة الكود
        if not POINTS_SYSTEM_ENABLED:
            logger.warning("[FS_CHECK] Points system disabled")
            clear_pending_ref(user_id)
            return

        referrer_id = get_referral_by_code(pending_ref)

        if not referrer_id:
            logger.warning(
                f"[FS_CHECK] Invalid ref code: {pending_ref}"
            )
            clear_pending_ref(user_id)
            return

        # 3. تأكد إن المستخدم مش هو نفس صاحب الإحالة
        if int(referrer_id) == user_id:
            logger.info("[FS_CHECK] User tried to refer themselves")
            clear_pending_ref(user_id)
            return

        # 4. ✅ سجّل الإحالة
        logger.info(
            f"[FS_CHECK] ✅ Valid referral! "
            f"referrer={referrer_id} → new_user={user_id}"
        )

        new_user = get_or_create_user(
            user_id,
            username=username,
            first_name=user_name,
            referred_by=referrer_id
        )

        if new_user:
            logger.info(f"[FS_CHECK] ✅ User created with referral!")

            # إشعار للمستخدم الجديد
            try:
                bot.send_message(
                    user_id,
                    f"🎉 <b>مرحباً بك!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"✅ تم تسجيلك بنجاح\n"
                    f"💰 حصلت على <b>25 نقطة</b> ترحيبية\n"
                    f"🎁 تم احتساب الإحالة لصاحب الرابط\n\n"
                    f"شكراً لاستخدامك البوت 🙏",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"notify new user error: {e}")

        # امسح الكود المعلّق
        clear_pending_ref(user_id)

        metrics.inc_counter("referral_via_fs_check")

    except Exception as e:
        logger.exception(f"_process_pending_referral error: {e}")
        # امسح الكود عشان ما يفضلش معلّق
        clear_pending_ref(user_id)


# ============================================================
# [9] Init
# ============================================================
def init_force_subscribe(bot_instance=None):
    """تسجيل handler احتياطي"""
    global bot
    if bot_instance:
        bot = bot_instance

    @bot.callback_query_handler(func=lambda call: call.data == "fs_check")
    def _handle_check_fallback(call):
        logger.info("[FS_CHECK] Fallback handler called")
        handle_fs_check_callback(call)

    logger.info(
        f"[+] Force Subscribe initialized | "
        f"Channels: {len(REQUIRED_CHANNELS)} | "
        f"Pending ref tracking: ON"
    )
    return True


# ============================================================
# [10] Public API
# ============================================================
def is_subscribed(user_id):
    is_member, _ = check_all_channels(user_id)
    return is_member


def get_required_channels():
    return REQUIRED_CHANNELS
