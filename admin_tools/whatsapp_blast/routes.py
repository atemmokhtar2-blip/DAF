# admin_tools/whatsapp_blast/routes.py
# ============================================================

import os
from flask import request, jsonify
from logging_config import get_logger
from .core_real import get_real_session, worker_health

logger = get_logger("admin_tools.whatsapp_blast.routes")

WORKER_SECRET = os.getenv("WA_WORKER_SECRET", "").strip()


def register_whatsapp_blast_routes(app):

    @app.route('/admin/wb/webhook', methods=['POST'])
    def wb_webhook():
        secret = request.headers.get('X-Worker-Secret', '')
        if secret != WORKER_SECRET:
            return jsonify({"error": "forbidden"}), 403

        data = request.get_json(silent=True) or {}
        event = data.get('event')
        payload = data.get('data', {})

        logger.info(f"[WB Webhook] {event}")

        try:
            from config import bot
            from points_system import ADMIN_IDS

            if event == 'ready':
                number = payload.get('number', '?')
                for admin in ADMIN_IDS:
                    try:
                        bot.send_message(
                            admin,
                            f"✅ <b>WhatsApp ready!</b>\n"
                            f"📱 الرقم: <code>{number}</code>",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass

            elif event == 'disconnected':
                for admin in ADMIN_IDS:
                    try:
                        bot.send_message(
                            admin,
                            f"⚠️ <b>WhatsApp disconnected</b>\n"
                            f"السبب: <code>{payload.get('reason', '?')}</code>",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Webhook notify error: {e}")

        return jsonify({"ok": True}), 200

    @app.route('/admin/wb/health', methods=['GET'])
    def wb_health():
        return jsonify(worker_health()), 200

    logger.info("[+] WhatsApp Blast routes registered")
