# admin_tools/whatsapp_blast/__init__.py
# ============================================================

from logging_config import get_logger

logger = get_logger("admin_tools.whatsapp_blast")


def init_whatsapp_blast(app, bot):
    """تسجيل routes + handlers"""
    from .routes import register_whatsapp_blast_routes
    from .bot_handlers_real import register_whatsapp_blast_real_handlers

    register_whatsapp_blast_routes(app)
    register_whatsapp_blast_real_handlers(bot)

    logger.info("[+] WhatsApp Blast (REAL) registered")


__all__ = ['init_whatsapp_blast']
