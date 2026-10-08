# bot_handlers/commands/start.py
# ============================================================
# /start — مع Force Subscribe
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
    # ★ Force Subscribe Check ★
    # ═══════════════════════════════════════════════════
    try:
        from force_subscribe import check_and_prompt
        if not check_and_prompt(message):
            logger.info(f"[FS] Blocked /start from {user_id}")
            return
    except Exception as e:
        logger.warning(f"force_subscribe check error: {e}")
        # لو حصل خطأ، كمّل عادي

    # ═══════════════════════════════════════════════════
    # --- استخراج كود الإحالة ---
    # ═══════════════════════════════════════════════════
    referred_by = None
    ref_code = None

    try:
        if message.text and len(message.text.split()) > 1:
            arg = message.text.split()[1].strip()
            if arg.startswith("ref_"):
                ref_code = arg.replace("ref_", "")
                # هل المستخدم جديد؟
                from imports_manager import get_user
                existing_user = get_user(user_id)
                if not existing_user and POINTS_SYSTEM_ENABLED:
                    referrer_id = get_referral_by_code(ref_code)
                    if referrer_id and int(referrer_id) != user_id:
                        referred_by = referrer_id
                        logger.info(f"New user via referral: {user_id} - {referrer_id}")
    except Exception as e:
        logger.warning(f"parse ref error: {e}")

    # ═══════════════════════════════════════════════════
    # --- إنشاء/جلب المستخدم ---
    # ═══════════════════════════════════════════════════
    try:
        get_or_create_user(user_id, username, user_name, referred_by=referred_by)
    except Exception as e:
        logger.exception(f"get_or_create_user error: {e}")

    # ═══════════════════════════════════════════════════
    # --- رسالة الترحيب ---
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
    # --- إرسال ---
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
