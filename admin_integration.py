# admin_integration.py
# ============================================================
# Admin Integration — ربط كل مكونات الأدمن
# ============================================================
# الوظائف:
# 1. تسجيل كل الأزرار الجديدة في البوت
# 2. Middleware للصيانة (يشتغل مع كل رسالة/callback)
# 3. تسجيل الـ callbacks في router
# 4. تهيئة الإشعارات الفورية
# 5. Hook لمراقبة الأخطاء الحرجة
# ============================================================

import time
from datetime import datetime

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import bot, redis_client
from logging_config import get_logger, get_logger as _get_logger

logger = get_logger("admin_integration")


# ══════════════════════════════════════════════════════════════
# [1] تكامل admin_buttons مع Router
# ══════════════════════════════════════════════════════════════
def register_admin_buttons_routes(router_routes):
    """
    تسجيل كل الـ routes الجديدة في Router
    router_routes: قائمة ROUTES الموجودة في router.py
    """
    try:
        from bot_handlers.callbacks import admin_buttons as admin_btn_cb

        # ★★★ الصيانة ★★★
        router_routes.append((
            lambda d: d in (
                "admin_maintenance",
                "maint_enable", "maint_disable",
                "maint_enable_30", "maint_enable_60",
                "maint_enable_180", "maint_enable_1440",
                "maint_edit_msg", "maint_custom",
                "maint_change_exempt"
            ) or d.startswith("maint_set_exempt_"),
            admin_btn_cb.handle
        ))

        # ★★★ صحة النظام ★★★
        router_routes.append((
            lambda d: d == "admin_health",
            admin_btn_cb.handle
        ))

        # ★★★ الجلسات والأجهزة ★★★
        router_routes.append((
            lambda d: d in (
                "admin_sessions", "admin_devices",
                "admin_sessions_kill_all",
                "admin_sessions_kill_all_confirm"
            ),
            admin_btn_cb.handle
        ))

        # ★★★ إعدادات البوت ★★★
        router_routes.append((
            lambda d: d in (
                "admin_settings",
                "setting_edit_welcome", "setting_edit_help",
                "setting_edit_tool_price",
                "setting_edit_welcome_points",
                "setting_edit_ref_points"
            ) or d.startswith("setting_set_price_"),
            admin_btn_cb.handle
        ))

        # ★★★ قائمة الحظر ★★★
        router_routes.append((
            lambda d: d in (
                "admin_ban_list", "admin_ban_add",
                "admin_ban_ip", "admin_unban_ip",
                "admin_unban_all"
            ),
            admin_btn_cb.handle
        ))

        # ★★★ النسخ الاحتياطي ★★★
        router_routes.append((
            lambda d: d in (
                "admin_backup", "backup_create",
                "backup_download_latest", "backup_list"
            ) or d.startswith("backup_download_"),
            admin_btn_cb.handle
        ))

        # ★★★ التحليلات ★★★
        router_routes.append((
            lambda d: d in ("admin_analytics", "admin_growth"),
            admin_btn_cb.handle
        ))

        # ★★★ البث الذكي ★★★
        router_routes.append((
            lambda d: d == "admin_smart_broadcast" or d.startswith("sbroadcast_"),
            admin_btn_cb.handle
        ))

        # ★★★ الإشعار المخصص ★★★
        router_routes.append((
            lambda d: d in (
                "admin_custom_notify", "cnotify_single", "cnotify_multi"
            ),
            admin_btn_cb.handle
        ))

        logger.info("[+] Admin buttons routes registered (10 additions)")
        return True

    except Exception as e:
        logger.exception(f"register_admin_buttons_routes error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [2] Middleware للصيانة
# ══════════════════════════════════════════════════════════════
def check_maintenance_for_message(message):
    """
    يتأكد من حالة الصيانة قبل معالجة أي رسالة
    Returns: True لو المستخدم مسموح له، False لو في صيانة
    """
    try:
        from admin_system import (
            is_maintenance, is_exempt_from_maintenance,
            get_maintenance_message
        )

        if not is_maintenance():
            return True

        user_id = message.from_user.id

        # ★ لو معفي ★
        if is_exempt_from_maintenance(user_id):
            return True

        # ★ أرسل رسالة الصيانة ★
        maint_msg = get_maintenance_message() or (
            "🔧 <b>وضع الصيانة</b>\n\n"
            "البوت تحت التحديث حالياً\n"
            "الرجاء المحاولة لاحقاً"
        )

        try:
            bot.send_message(
                message.chat.id,
                maint_msg,
                parse_mode="HTML"
            )
        except Exception:
            pass

        return False

    except Exception as e:
        logger.warning(f"check_maintenance error: {e}")
        return True  # ★ في حالة الخطأ، اسمح بالمرور ★


def check_maintenance_for_callback(call):
    """
    نفس الشيء للـ callbacks
    """
    try:
        from admin_system import (
            is_maintenance, is_exempt_from_maintenance,
            get_maintenance_message
        )
        from points_system import is_admin

        if not is_maintenance():
            return True

        user_id = call.from_user.id

        # ★ الأدمن دايماً معفي من القفل (عشان يقدر يوقف الصيانة) ★
        if is_admin(user_id):
            return True

        if is_exempt_from_maintenance(user_id):
            return True

        # ★ رسالة الصيانة ★
        maint_msg = get_maintenance_message() or (
            "🔧 <b>وضع الصيانة</b>\n\n"
            "البوت تحت التحديث حالياً"
        )

        try:
            bot.answer_callback_query(
                call.id,
                "🔧 البوت في وضع الصيانة",
                show_alert=True
            )
            bot.send_message(
                call.message.chat.id,
                maint_msg,
                parse_mode="HTML"
            )
        except Exception:
            pass

        return False

    except Exception as e:
        logger.warning(f"check_maintenance_callback error: {e}")
        return True


# ══════════════════════════════════════════════════════════════
# [3] Hook للإشعارات الفورية
# ══════════════════════════════════════════════════════════════
def install_notification_hooks():
    """
    تفعيل الإشعارات الفورية
    - Hook على الأخطاء الحرجة
    - Hook على الضحايا الجديدة
    - Hook على الجلسات الجديدة
    """
    try:
        # ★ Hook على uncaught exceptions ★
        import sys
        _original_hook = sys.excepthook

        def _error_hook(exc_type, exc_value, exc_traceback):
            try:
                if issubclass(exc_type, KeyboardInterrupt):
                    _original_hook(exc_type, exc_value, exc_traceback)
                    return

                # ★ سجل الخطأ ★
                _original_hook(exc_type, exc_value, exc_traceback)

                # ★ أبعت إشعار للأدمن ★
                try:
                    from admin_system import notify_critical_error
                    import traceback
                    tb = ''.join(traceback.format_exception(
                        exc_type, exc_value, exc_traceback
                    ))
                    notify_critical_error(
                        tb,
                        module=f"{exc_type.__module__}.{exc_type.__name__}"
                    )
                except Exception:
                    pass
            except Exception:
                pass

        sys.excepthook = _error_hook
        logger.info("[+] Error notification hook installed")

        return True

    except Exception as e:
        logger.exception(f"install_notification_hooks error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [4] دالة الواجهة الرئيسية
# ══════════════════════════════════════════════════════════════
def init_admin_integration(app=None, bot_instance=None):
    """
    تهيئة admin integration
    """
    logger.info("=" * 60)
    logger.info("🔌 Initializing Admin Integration v2.0")
    logger.info("=" * 60)

    # ★ 1. تثبيت الإشعارات ★
    try:
        install_notification_hooks()
        logger.info("[+] ✓ Notifications hook installed")
    except Exception as e:
        logger.warning(f"[-] Notifications hook failed: {e}")

    # ★ 2. اختبار الاتصال بـ Redis ★
    try:
        if redis_client:
            redis_client.ping()
            logger.info("[+] ✓ Redis connected")
        else:
            logger.warning("[-] Redis not available")
    except Exception as e:
        logger.warning(f"[-] Redis error: {e}")

    # ★ 3. اختبار admin_system ★
    try:
        from admin_system import (
            is_maintenance, get_system_health,
            build_maintenance_status_text
        )
        health = get_system_health()
        logger.info(
            f"[+] ✓ admin_system loaded | "
            f"CPU={health.get('cpu_percent')}% | "
            f"RAM={health.get('ram_percent')}% | "
            f"Redis={health.get('redis')}"
        )
    except Exception as e:
        logger.exception(f"[-] admin_system error: {e}")

    # ★ 4. اختبار admin_buttons ★
    try:
        from bot_handlers.callbacks import admin_buttons
        logger.info("[+] ✓ admin_buttons loaded")
    except Exception as e:
        logger.exception(f"[-] admin_buttons error: {e}")

    logger.info("=" * 60)
    logger.info("✅ Admin Integration READY")
    logger.info("=" * 60)

    return True


# ══════════════════════════════════════════════════════════════
# [5] Helper: تطبيق Middleware على رسالة
# ══════════════════════════════════════════════════════════════
def wrap_handler_with_maintenance(handler_func):
    """
    Decorator يلف أي handler بفحص الصيانة
    """
    def wrapper(message, *args, **kwargs):
        if not check_maintenance_for_message(message):
            return
        return handler_func(message, *args, **kwargs)

    return wrapper


def wrap_callback_with_maintenance(handler_func):
    """
    Decorator للـ callbacks
    """
    def wrapper(call, *args, **kwargs):
        if not check_maintenance_for_callback(call):
            return
        return handler_func(call, *args, **kwargs)

    return wrapper


# ══════════════════════════════════════════════════════════════
# [6] Broadcast Maintenance Trigger
# ══════════════════════════════════════════════════════════════
def trigger_maintenance_now(minutes=0, message=None, exempt_mode="all"):
    """
    تفعيل الصيانة برمجياً (للاستخدام الخارجي)
    """
    try:
        from admin_system import enable_maintenance
        success = enable_maintenance(
            custom_msg=message,
            admin_id=0,
            duration_minutes=minutes,
            exempt_mode=exempt_mode
        )
        if success:
            logger.warning(f"[MAINTENANCE] Triggered programmatically | {minutes}min")
        return success
    except Exception as e:
        logger.exception(f"trigger_maintenance error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [7] Startup Check
# ══════════════════════════════════════════════════════════════
def startup_check():
    """
    فحص شامل عند بدء البوت
    """
    try:
        from admin_system import (
            get_system_health, is_maintenance,
            get_banned_users, get_online_count
        )

        health = get_system_health()
        online = get_online_count()
        banned = len(get_banned_users())
        maint = is_maintenance()

        logger.info(
            f"[STARTUP] "
            f"Users Online: {online} | "
            f"Banned: {banned} | "
            f"Maintenance: {maint} | "
            f"Redis: {health.get('redis')} | "
            f"PG: {health.get('postgres')}"
        )
        return True
    except Exception as e:
        logger.warning(f"startup_check error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [8] Admin Panel Button (رسالة لوحة الأدمن)
# ══════════════════════════════════════════════════════════════
def build_admin_panel_header():
    """
    Header لرسالة لوحة الأدمن
    """
    try:
        from admin_system import (
            get_system_health, get_online_count,
            is_maintenance, get_maintenance_duration,
            format_uptime
        )

        health = get_system_health()
        online = get_online_count()
        maint = is_maintenance()

        text = (
            "👑 <b>لوحة تحكم الأدمن v2.0</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 <b>Online:</b> <code>{online}</code>\n"
            f"💻 <b>CPU:</b> <code>{health.get('cpu_percent')}%</code>\n"
            f"🧠 <b>RAM:</b> <code>{health.get('ram_percent')}%</code>\n"
            f"🔌 <b>Redis:</b> <code>{'✅' if health.get('redis') else '❌'}</code>\n"
            f"🗄️ <b>PostgreSQL:</b> <code>{'✅' if health.get('postgres') else '❌'}</code>\n"
        )

        if maint:
            duration = get_maintenance_duration()
            text += f"\n🔧 <b>وضع الصيانة:</b> مفعّل منذ <code>{format_uptime(duration)}</code>\n"

        text += "\n💡 <b>اختر عملية:</b>"

        return text
    except Exception as e:
        logger.warning(f"build_admin_panel_header error: {e}")
        return "👑 <b>لوحة الأدمن</b>\n\n💡 اختر عملية:"


# ══════════════════════════════════════════════════════════════
# [9] Cleanup Task
# ══════════════════════════════════════════════════════════════
def start_cleanup_thread():
    """
    Thread لتنظيف الإشعارات القديمة
    """
    import threading

    def _cleanup_loop():
        while True:
            try:
                time.sleep(3600)  # كل ساعة

                if not redis_client:
                    continue

                # ★ نظف إشعارات أقدم من 7 أيام ★
                cutoff = time.time() - (86400 * 7)

                for key in redis_client.scan_iter(match="notification:*", count=100):
                    try:
                        ts = redis_client.get(key)
                        if ts and float(ts) < cutoff:
                            redis_client.delete(key)
                    except Exception:
                        continue

            except Exception as e:
                logger.warning(f"cleanup error: {e}")

    thread = threading.Thread(target=_cleanup_loop, daemon=True)
    thread.start()
    logger.info("[+] Cleanup thread started")


# ══════════════════════════════════════════════════════════════
# [10] Auto-Init
# ══════════════════════════════════════════════════════════════
logger.info("[+] admin_integration v2.0 loaded")
