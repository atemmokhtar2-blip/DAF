# points_system_patch.py
# ============================================================
# Patch لـ points_system — يخلي الإعدادات الديناميكية تشتغل
# ============================================================
# الحل:
# 1. TOOL_PRICES → يقرأ من Redis أولاً
# 2. WELCOME_POINTS → ديناميكي
# 3. REFERRAL_POINTS → ديناميكي
# 4. can_use_tool → يستخدم الأسعار الديناميكية
# 5. consume_usage → يخصم السعر الديناميكي
# ============================================================

from logging_config import get_logger
from config import redis_client

logger = get_logger("points_system_patch")


# ══════════════════════════════════════════════════════════════
# [1] القراءة الديناميكية
# ══════════════════════════════════════════════════════════════
def get_tool_price(tool_key, default_price=0):
    """يقرأ السعر من Redis أولاً"""
    if not redis_client:
        return default_price

    try:
        val = redis_client.hget("tool_prices", tool_key)
        if val is not None:
            if isinstance(val, bytes):
                val = val.decode()
            return int(val)
    except Exception as e:
        logger.debug(f"get_tool_price({tool_key}) error: {e}")

    return default_price


def get_welcome_points(default=25):
    """نقاط الترحيب الديناميكية"""
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


def get_referral_points(default=10):
    """نقاط الإحالة الديناميكية"""
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
# [2] Apply Patches
# ══════════════════════════════════════════════════════════════
def apply_patches():
    """يعدّل دوال points_system في الذاكرة"""
    try:
        import points_system

        # ★ حفظ القيم الأصلية ★
        original_can_use = points_system.can_use_tool
        original_consume = points_system.consume_usage
        original_prices = dict(getattr(points_system, 'TOOL_PRICES', {}))

        # ═══════════════════════════════════════════════
        # Patch 1: DynamicToolPrices
        # ═══════════════════════════════════════════════
        class DynamicToolPrices(dict):
            """dict ديناميكي يقرأ من Redis"""

            def __init__(self, defaults):
                super().__init__(defaults)
                self._defaults = dict(defaults)

            def __getitem__(self, key):
                default = self._defaults.get(key, 0)
                return get_tool_price(key, default)

            def get(self, key, default=None):
                fallback = self._defaults.get(key, default if default is not None else 0)
                return get_tool_price(key, fallback)

            def __contains__(self, key):
                return key in self._defaults

            def keys(self):
                return self._defaults.keys()

            def items(self):
                return [(k, get_tool_price(k, v)) for k, v in self._defaults.items()]

            def values(self):
                return [self[k] for k in self._defaults.keys()]

        # ═══════════════════════════════════════════════
        # Patch 2: can_use_tool
        # ═══════════════════════════════════════════════
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

                default_price = original_prices.get(tool, 0)
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

        # ═══════════════════════════════════════════════
        # Patch 3: consume_usage
        # ═══════════════════════════════════════════════
        def patched_consume_usage(user_id, tool):
            try:
                user = points_system.get_or_create_user(user_id)

                if user.get("is_banned"):
                    return False

                if points_system.is_admin(user_id) or user.get("is_vip"):
                    return True

                default_price = original_prices.get(tool, 0)
                cost = get_tool_price(tool, default_price)

                if cost == 0:
                    return True

                balance = user.get("points", 0)
                if balance < cost:
                    return False

                user["points"] = balance - cost
                user["total_points_spent"] = user.get("total_points_spent", 0) + cost
                points_system.save_user(user_id, user)

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

                logger.info(f"[DYNAMIC-PRICE] Tool used: {user_id} | {tool} | -{cost} points")
                return True

            except Exception as e:
                logger.exception(f"patched_consume_usage error: {e}")
                return original_consume(user_id, tool)

        # ═══════════════════════════════════════════════
        # Patch 4: create_new_user (نقاط الترحيب)
        # ═══════════════════════════════════════════════
        original_create_user = points_system.create_new_user

        def patched_create_new_user(user_id, username="Unknown",
                                     first_name="User", referred_by=None):
            try:
                welcome_points = get_welcome_points(
                    getattr(points_system, 'WELCOME_POINTS', 25)
                )

                # ★ استدعي الأصلية ★
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

        # ═══════════════════════════════════════════════
        # Patch 5: _add_referral_points (نقاط الإحالة)
        # ═══════════════════════════════════════════════
        original_add_ref = points_system._add_referral_points

        def patched_add_referral(referrer_id, new_user_id, new_user_name):
            try:
                ref_points = get_referral_points(
                    getattr(points_system, 'REFERRAL_POINTS', 10)
                )

                original_ref_points = points_system.REFERRAL_POINTS
                points_system.REFERRAL_POINTS = ref_points

                try:
                    return original_add_ref(referrer_id, new_user_id, new_user_name)
                finally:
                    points_system.REFERRAL_POINTS = original_ref_points

            except Exception as e:
                logger.exception(f"patched_add_referral error: {e}")
                return original_add_ref(referrer_id, new_user_id, new_user_name)

        # ═══════════════════════════════════════════════
        # Apply
        # ═══════════════════════════════════════════════
        points_system.can_use_tool = patched_can_use_tool
        points_system.consume_usage = patched_consume_usage
        points_system.TOOL_PRICES = DynamicToolPrices(original_prices)
        points_system.create_new_user = patched_create_new_user
        points_system._add_referral_points = patched_add_referral

        logger.info("[+] points_system patched (dynamic)")
        logger.info("    • TOOL_PRICES = dynamic")
        logger.info("    • WELCOME_POINTS = dynamic")
        logger.info("    • REFERRAL_POINTS = dynamic")
        logger.info("    • can_use_tool / consume_usage = patched")

        return True

    except Exception as e:
        logger.exception(f"apply_patches error: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# [3] Auto-apply
# ══════════════════════════════════════════════════════════════
try:
    apply_patches()
except Exception as e:
    logger.exception(f"auto apply_patches failed: {e}")


logger.info("[+] points_system_patch loaded")
