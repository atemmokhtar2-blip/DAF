# fake_sites/facebook/__init__.py
# ============================================================
# قسم Facebook — 10 قوالب مواقع
# ============================================================

from logging_config import get_logger

logger = get_logger("fake_sites.facebook")


def init_facebook_templates(app):
    """تسجيل مسارات Facebook المزيفة"""
    from .routes import register_facebook_routes

    register_facebook_routes(app)
    logger.info("[+] Facebook templates registered")


__all__ = ['init_facebook_templates']
