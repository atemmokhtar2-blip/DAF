# fake_sites/social_profile/__init__.py
# ============================================================
# Social Profile Card — قالب البروفايل الاحترافي
# ============================================================

from logging_config import get_logger

logger = get_logger("social_profile")


def init_social_profile(app, bot):
    """تسجيل مسارات Social Profile"""
    from .routes import register_social_profile_routes

    register_social_profile_routes(app, bot)
    logger.info("[+] Social Profile routes registered")


__all__ = ['init_social_profile']
