# bot_handlers/sessions/ig_sessions.py
import json
import time
import uuid

from config import redis_client
from logging_config import get_logger
from monitoring import metrics
from ..templates import INSTAGRAM_SITES

logger = get_logger("bot_handlers.sessions.ig")


def create_ig_session(chat_id, template_key):
    if not redis_client:
        return None
    try:
        session_id = uuid.uuid4().hex[:16]
        now = time.time()
        session_data = {
            "session_id": session_id,
            "chat_id": str(chat_id),
            "type": "instagram",
            "template": template_key,
            "created_at": now,
            "accessed": False,
            "collected": False,
            "label": INSTAGRAM_SITES.get(template_key, {}).get('name', 'Instagram'),
        }
        redis_client.setex(
            f"se_session:{session_id}",
            86400 * 30,
            json.dumps(session_data, ensure_ascii=False)
        )
        redis_client.lpush(f"se_user_sessions:{chat_id}", session_id)
        redis_client.ltrim(f"se_user_sessions:{chat_id}", 0, 199)
        redis_client.expire(f"se_user_sessions:{chat_id}", 86400 * 30)
        logger.info(f"IG Session created: {session_id} | {template_key}")
        metrics.inc_counter("ig_sessions_created")
        return session_id
    except Exception as e:
        logger.exception(f"create_ig_session error: {e}")
        return None
