# bot_handlers/commands/start.py
# ============================================================
# /start — يستقبل كود الإحالة من الرابط
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

    # ─── استخراج كود الإحالة ───
    referred_by = None
    ref_code = None

    try:
        # /start ref_XXXXXXXX
        if message.text and len(message.text.split()) > 1:
            arg = message.text.split()[1].strip()
            if arg.startswith("ref_"):
                ref_code = arg.replace("ref_", "")
                # هل المستخدم جديد؟
                from imports_manager import get_user
                existing_user = get_user(user_id)

                if not existing_user and POINTS_SYSTEM_ENABLED:
                    # ابحث عن صاحب الكود
                    referrer_id = get_referral_by_code(ref_code)
                    if referrer_id and int(referrer_id) != user_id:
                        referred_by = referrer_id
                        logger.info(f"New user via referral: {user_id} ← {referrer_id}")
    except Exception as e:
        logger.warning(f"parse ref error: {e}")

    logger.info(f"/start from {user_id} | ref_code={ref_code}")

    # ─── إنشاء/جلب المستخدم ───
    try:
        user = get_or_create_user(user_id, username, user_name, referred_by)
    except Exception as e:
        logger.exception(f"get_or_create_user error: {e}")
        user = None

    # ─── رسالة الترحيب ───
    if is_admin(user_id):
        text = WELCOME_ADMIN.format(name=h(user_name))
    else:
        points = user.get("points", 0) if user else 0

        if referred_by:
            text = (
                f"🎉 <b>مرحباً بك {h(user_name)}!</b>\n\n"
                f"🎁 <b>تم دعوتك من أحد المستخدمين</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>رصيدك الابتدائي:</b> <code>{points}</code> نقطة\n\n"
                f"🔗 <b>عندك كود خاص بيك!</b>\n"
                f"شارك رابطك → كل واحد يخش = <b>+{REFERRAL_POINTS} نقطة</b>\n\n"
                f"🎯 اختر أداة:"
            )
        else:
            text = (
                f"👋 <b>مرحباً بك {h(user_name)}!</b>\n\n"
                f"🎁 <b>حصلت على {points} نقطة مجانية!</b>\n\n"
                f"🎯 اختر الأداة التي تريدها:"
            )

    bot.send_message(
        message.chat.id, text,
        parse_mode="HTML",
        reply_markup=main_menu(user_id)
    )

    metrics.inc_counter("bot_commands", tags={"cmd": "start"})
