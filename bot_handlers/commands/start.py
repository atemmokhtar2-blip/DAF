# bot_handlers/commands/start.py
# ============================================================
# /start — مع Force Subscribe + Pending Referral
# ============================================================
from config import bot
from imports_manager import (
    get_or_create_user, is_admin,
    get_referral_by_code, WELCOME_POINTS, REFERRAL_POINTS,
    POINTS_SYSTEM_ENABLED,
)
from logging_config import get_logger
from monitoring import metrics

from ..helpers import h
from ..keyboards import main_menu
from ..messages import WELCOME_ADMIN, WELCOME_USER

logger = get_logger("bot_handlers.commands.start")


@bot.message_handler(commands=['start', 'panel'])
def start_command(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    username = message.from_user.username or "Unknown"

    # ═══════════════════════════════════════════════════
    # 1. استخراج كود الإحالة (قبل أي check)
    # ═══════════════════════════════════════════════════
    ref_code = None

    try:
        if message.text and len(message.text.split()) > 1:
            arg = message.text.split()[1].strip()
            if arg.startswith("ref_"):
                ref_code = arg.replace("ref_", "")
                logger.info(f"[START] Ref code detected: {ref_code} | user={user_id}")
    except Exception as e:
        logger.warning(f"[START] parse ref error: {e}")

    # ═══════════════════════════════════════════════════
    # 2. ⚡ لو فيه ref_code → احفظه كمعلّق (قبل FS check)
    # ═══════════════════════════════════════════════════
    if ref_code:
        try:
            from force_subscribe import save_pending_ref
            save_pending_ref(user_id, ref_code)
            logger.info(f"[START] Pending ref saved: {user_id} → {ref_code}")
        except Exception as e:
            logger.warning(f"[START] save_pending_ref error: {e}")

    # ═══════════════════════════════════════════════════
    # 3. ★ Force Subscribe Check ★
    # ═══════════════════════════════════════════════════
    try:
        from force_subscribe import check_and_prompt
        if not check_and_prompt(message):
            logger.info(f"[FS] Blocked /start from {user_id}")
            return
    except Exception as e:
        logger.warning(f"force_subscribe check error: {e}")

    # ═══════════════════════════════════════════════════
    # 4. جلب كود الإحالة المعلّق (لو مشترك من الأول)
    # ═══════════════════════════════════════════════════
    referred_by = None

    try:
        from force_subscribe import get_pending_ref, clear_pending_ref
        from imports_manager import get_user

        pending_ref = get_pending_ref(user_id)

        if pending_ref and POINTS_SYSTEM_ENABLED:
            existing_user = get_user(user_id)

            if not existing_user:
                referrer_id = get_referral_by_code(pending_ref)
                if referrer_id and int(referrer_id) != user_id:
                    referred_by = referrer_id
                    logger.info(
                        f"[START] ✅ Referral applied: "
                        f"{user_id} referred by {referrer_id}"
                    )
                else:
                    logger.info(f"[START] Invalid referrer for {pending_ref}")

            # امسح الكود (سواء صح أو غلط)
            clear_pending_ref(user_id)

    except Exception as e:
        logger.warning(f"[START] pending ref error: {e}")

    # ═══════════════════════════════════════════════════
    # 5. إنشاء/جلب المستخدم
    # ═══════════════════════════════════════════════════
    try:
        get_or_create_user(user_id, username, user_name, referred_by=referred_by)
    except Exception as e:
        logger.exception(f"get_or_create_user error: {e}")

    # ═══════════════════════════════════════════════════
    # 6. رسالة الترحيب
    # ═══════════════════════════════════════════════════
    try:
        if is_admin(user_id):
            welcome_text = WELCOME_ADMIN.format(name=h(user_name))
        else:
            welcome_text = WELCOME_USER.format(
                name=h(user_name),
                points=WELCOME_POINTS,
            )
    except Exception:
        welcome_text = f"👋 أهلاً <b>{h(user_name)}</b>!"

    # ═══════════════════════════════════════════════════
    # 7. إرسال
    # ═══════════════════════════════════════════════════
    try:
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode="HTML"
        )
        bot.send_message(
            message.chat.id,
            "📋 <b>القائمة الرئيسية:</b>",
            reply_markup=main_menu(user_id),
            parse_mode="HTML"
        )
        metrics.inc_counter("start_command")
    except Exception as e:
        logger.exception(f"start_command send error: {e}")
