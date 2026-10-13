# points_system_patch.py
# ============================================================
# Patch لـ points_system.py — يخلي الإعدادات الديناميكية تشتغل
# ============================================================
# المشكلة: points_system بيستخدم TOOL_PRICES الثابت
# الحل: نقرأ من Redis أولاً، لو مش موجود نرجع للثابت
# ============================================================

from logging_config import get_logger
from config import redis_client

logger = get_logger("points_system_patch")


# ══════════════════════════════════════════════════════════════
# [1] دالة قراءة سعر أداة (ديناميكية)
# ══════════════════════════════════════════════════════════════
def get_tool_price(tool_key, default_price=0):
    """
    يقرأ سعر الأداة من Redis أولاً
    لو مش موجود، يرجع القيمة الافتراضية
    """
    if not redis_client:
        return default_price

    try:
        val = redis_client.hget("tool_prices", tool_key)
        if val is not None:
            if isinstance(val, bytes):
                val = val.decode()
            return int(val)
    except Exception as e:
        logger.warning(f"get_tool_price({tool_key}) error: {e}")

    return default_price


# ══════════════════════════════════════════════════════════════
# [2] دالة قراءة نقاط الترحيب
# ══════════════════════════════════════════════════════════════
def get_welcome_points(default=25):
    """يقرأ نقاط الترحيب من Redis أولاً"""
    if not redis_client:
        return default

    try:
        val = redis_client.hget("system:bot_settings", "welcome_points")
        if val is not None:
            if isinstance(val, bytes):
                val = val.decode()
            return int(val)
    except Exception:
        pass

    return default


# ══════════════════════════════════════════════════════════════
# [3] دالة قراءة نقاط الإحالة
# ══════════════════════════════════════════════════════════════
def get_referral_points(default=10):
    """يقرأ نقاط الإحالة من Redis أولاً"""
    if not redis_client:
        return default

    try:
        val = redis_client.hget("system:bot_settings", "ref_points")
        if val is not None:
            if isinstance(val, bytes):
                val = val.decode()
            return int(val)
    except Exception:
        pass

    return default


# ══════════════════════════════════════════════════════════════
# [4] دالة قراءة رسالة الترحيب
# ══════════════════════════════════════════════════════════════
def get_welcome_message(default=""):
    """يقرأ رسالة الترحيب من Redis أولاً"""
    if not redis_client:
        return default

    try:
        val = redis_client.hget("system:bot_settings", "welcome_msg")
        if val is not None:
            if isinstance(val, bytes):
                val = val.decode()
            return val
    except Exception:
        pass

    return default


# ══════════════════════════════════════════════════════════════
# [5] دالة قراءة رسالة المساعدة
# ══════════════════════════════════════════════════════════════
def get_help_message(default=""):
    """يقرأ رسالة المساعدة من Redis أولاً"""
    if not redis_client:
        return default

    try:
        val = redis_client.hget("system:bot_settings", "help_msg")
        if val is not None:
            if isinstance(val, bytes):
                val = val.decode()
            return val
    except Exception:
        pass

    return default


# ══════════════════════════════════════════════════════════════
# [6] Apply Patch — تعديل points_system في الذاكرة
# ══════════════════════════════════════════════════════════════
def apply_patches():
    """
    يعدّل دوال points_system عشان تستخدم القيم الديناميكية
    """
    try:
        import points_system

        # ★ حفظ الدوال الأصلية ★
        original_can_use = points_system.can_use_tool
        original_consume = points_system.consume_usage
        original_get_price = getattr(points_system, 'TOOL_PRICES', {})

        # ═══════════════════════════════════════════════════
        # Patch 1: can_use_tool — يستخدم الأسعار الديناميكية
        # ═══════════════════════════════════════════════════
        def patched_can_use_tool(user_id, tool):
            try:
                user = points_system.get_or_create_user(user_id)

                if user.get("is_banned"):
                    return {"allowed": False, "reason": "banned"}

                if points_system.is_admin(user_id):
                    return {
                        "allowed": True, "reason": "admin",
                        "cost": 0, "balance": 999999
                    }

                if user.get("is_vip"):
                    return {
                        "allowed": True, "reason": "vip",
                        "cost": 0, "balance": user.get("points", 0)
                    }

                # ★★★ اقرأ السعر من Redis أولاً ★★★
                default_price = original_get_price.get(tool, 0)
                cost = get_tool_price(tool, default_price)

                if cost == 0:
                    return {
                        "allowed": True, "reason": "free",
                        "cost": 0, "balance": user.get("points", 0)
                    }

                balance = user.get("points", 0)

                if balance >= cost:
                    return {
                        "allowed": True,
                        "reason": "points",
                        "cost": cost,
                        "balance": balance,
                        "remaining": balance - cost,
                    }

                return {
                    "allowed": False,
                    "reason": "insufficient_points",
                    "cost": cost,
                    "balance": balance,
                    "needed": cost - balance,
                }

            except Exception as e:
                logger.exception(f"patched_can_use_tool error: {e}")
                return original_can_use(user_id, tool)

        # ═══════════════════════════════════════════════════
        # Patch 2: consume_usage — يخصم السعر الديناميكي
        # ═══════════════════════════════════════════════════
        def patched_consume_usage(user_id, tool):
            try:
                user = points_system.get_or_create_user(user_id)

                if user.get("is_banned"):
                    return False

                if points_system.is_admin(user_id) or user.get("is_vip"):
                    return True

                # ★★★ اقرأ السعر من Redis أولاً ★★★
                default_price = original_get_price.get(tool, 0)
                cost = get_tool_price(tool, default_price)

                if cost == 0:
                    return True

                balance = user.get("points", 0)
                if balance < cost:
                    return False

                user["points"] = balance - cost
                user["total_points_spent"] = user.get("total_points_spent", 0) + cost
                points_system.save_user(user_id, user)

                # ★ سجل في DB ★
                try:
                    from database import add_points_history
                    add_points_history(
                        user_id=user_id,
                        type_="tool_used",
                        points=-cost,
                        tool=tool,
                        tool_name=points_system.TOOL_NAMES_AR.get(tool, tool),
                    )
                except Exception:
                    pass

                logger.info(f"[PRICE-DYNAMIC] Tool used: {user_id} | {tool} | -{cost} points")
                return True

            except Exception as e:
                logger.exception(f"patched_consume_usage error: {e}")
                return original_consume(user_id, tool)

        # ═══════════════════════════════════════════════════
        # Patch 3: TOOL_PRICES — يصبح ديناميكي
        # ═══════════════════════════════════════════════════
        class DynamicToolPrices(dict):
            """dict ديناميكي يقرأ من Redis"""

            def __init__(self, defaults):
                super().__init__(defaults)
                self._defaults = dict(defaults)

            def __getitem__(self, key):
                # ★ اقرأ من Redis ★
                default = self._defaults.get(key, 0)
                return get_tool_price(key, default)

            def get(self, key, default=None):
                # ★ اقرأ من Redis ★
                fallback = self._defaults.get(key, default if default is not None else 0)
                return get_tool_price(key, fallback)

            def __contains__(self, key):
                return key in self._defaults

            def keys(self):
                return self._defaults.keys()

            def items(self):
                result = []
                for k, v in self._defaults.items():
                    result.append((k, get_tool_price(k, v)))
                return result

            def values(self):
                return [self[k] for k in self._defaults.keys()]

        # ★ استبدل ★
        points_system.can_use_tool = patched_can_use_tool
        points_system.consume_usage = patched_consume_usage
        points_system.TOOL_PRICES = DynamicToolPrices(original_get_price)

        # ═══════════════════════════════════════════════════
        # Patch 4: نقاط الترحيب — ديناميكية
        # ═══════════════════════════════════════════════════
        original_create_user = points_system.create_new_user

        def patched_create_new_user(user_id, username="Unknown",
                                     first_name="User", referred_by=None):
            """ينشئ مستخدم بنقاط الترحيب الديناميكية"""
            try:
                # ★ اقرأ نقاط الترحيب من Redis ★
                welcome_points = get_welcome_points(
                    getattr(points_system, 'WELCOME_POINTS', 25)
                )

                # ★ استدعي الدالة الأصلية مع تعديل النقاط ★
                user = original_create_user(
                    user_id, username, first_name, referred_by
                )

                if user:
                    user["points"] = welcome_points
                    user["total_points_earned"] = welcome_points
                    points_system.save_user(user_id, user)

                return user

            except Exception as e:
                logger.exception(f"patched_create_new_user error: {e}")
                return original_create_user(
                    user_id, username, first_name, referred_by
                )

        points_system.create_new_user = patched_create_new_user

        # ═══════════════════════════════════════════════════
        # Patch 5: نقاط الإحالة — ديناميكية
        # ═══════════════════════════════════════════════════
        original_add_ref_points = points_system._add_referral_points

        def patched_add_referral_points(referrer_id, new_user_id, new_user_name):
            """يضيف نقاط إحالة ديناميكية"""
            try:
                # ★ اقرأ نقاط الإحالة من Redis ★
                ref_points = get_referral_points(
                    getattr(points_system, 'REFERRAL_POINTS', 10)
                )

                # ★ استدعي الدالة الأصلية مؤقتاً بنقاط جديدة ★
                original_ref_points = points_system.REFERRAL_POINTS
                points_system.REFERRAL_POINTS = ref_points

                try:
                    result = original_add_ref_points(
                        referrer_id, new_user_id, new_user_name
                    )
                finally:
                    points_system.REFERRAL_POINTS = original_ref_points

                return result

            except Exception as e:
                logger.exception(f"patched_add_referral_points error: {e}")
                return original_add_ref_points(
                    referrer_id, new_user_id, new_user_name
                )

        points_system._add_referral_points = patched_add_referral_points

        logger.info("[+] points_system patched successfully")
        logger.info("    • TOOL_PRICES = dynamic (Redis-backed)")
        logger.info("    • WELCOME_POINTS = dynamic")
        logger.info("    • REFERRAL_POINTS = dynamic")
        logger.info("    • can_use_tool = patched")
        logger.info("    • consume_usage = patched")
        logger.info("    • create_new_user = patched")
        logger.info("    • _add_referral_points = patched")

        return True

    except Exception as e:
        logger.exception(f"apply_patches error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [7] Auto-apply at import
# ══════════════════════════════════════════════════════════════
try:
    apply_patches()
except Exception as e:
    logger.exception(f"auto apply_patches failed: {e}")


logger.info("[+] points_system_patch loaded")
