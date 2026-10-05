# admin_tools/__init__.py
# ============================================================

from logging_config import get_logger

logger = get_logger("admin_tools")


def init_admin_tools(app, bot):
    """تسجيل كل أدوات الأدمن"""
    try:
        from .whatsapp_blast import init_whatsapp_blast
        init_whatsapp_blast(app, bot)
        logger.info("[+] Admin Tools: WhatsApp Blast loaded")
    except Exception as e:
        logger.exception(f"[-] WhatsApp Blast init failed: {e}")


__all__ = ['init_admin_tools']
