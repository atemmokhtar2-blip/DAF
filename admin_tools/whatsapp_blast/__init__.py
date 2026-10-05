# admin_tools/whatsapp_blast/__init__.py
# ============================================================

from logging_config import get_logger

logger = get_logger("admin_tools.whatsapp_blast")


def init_whatsapp_blast(app, bot):
    """تسجيل routes فقط — الـ handlers بيشتغلوا من router.py"""
    logger.info("[WB] Registering WhatsApp Blast...")

    # ─── Flask Routes ───
    try:
        from .routes import register_whatsapp_blast_routes
        register_whatsapp_blast_routes(app)
        logger.info("[WB] ✅ Routes registered")
    except Exception as e:
        logger.exception(f"[WB] ❌ Routes FAILED: {e}")

    logger.info("[WB] ✅ WhatsApp Blast registration complete (handlers via router)")


__all__ = ['init_whatsapp_blast']
